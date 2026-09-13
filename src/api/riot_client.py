# src/api/riot_client.py
"""
Riot API wrapper built on top of riotwatcher.

Handles authentication, region routing, match fetching, timeline parsing,
and Data Dragon lookups for core item classification. Returns project
domain objects (Player, Match, Matchup, ItemPurchase) rather than raw
Riot JSON, so callers don't need to know Riot's response shape.

Notable Riot quirks handled here:
  - Platform vs. regional routing: match endpoints use platform
    (kr, na1, euw1), while account endpoints use region
    (asia, americas, europe). Both maps live on the class.
  - Timeline data must be fetched separately from the match payload.
    Skill order and item purchases are only available via this second
    call, which roughly doubles the number of HTTP requests per match
    when include_timeline=True.
  - Riot emits ITEM_UNDO when a purchase is reverted inside the shop's
    undo window. Players frequently mistake-buy their starting items
    and undo them, and no ITEM_SOLD is emitted in that case. Both
    events are treated identically when marking a purchase as removed.

All public methods catch ApiError and return empty/None rather than
raising, so callers can iterate a batch without one failure aborting
the whole run.

Note: get_recent_matches and get_matches_since_date share most of their
per-match parsing logic. They differ in scope (fixed count vs. date
window) and in the skip-existing optimization (only the date version
consults db_connection). Kept separate rather than parameterized because
the two call sites have meaningfully different contracts and merging
them would obscure both paths.
"""

from typing import Optional, Tuple
from datetime import datetime, timedelta
import json
import os

import requests
from riotwatcher import LolWatcher, RiotWatcher, ApiError

from src.models import Player, Match, Matchup, ItemPurchase
import config


class RiotAPIClient:
    """Handles all Riot API interactions using Riot-Watcher."""

    def __init__(self, api_key: str = None):
        """
        Initialize the client.

        Args:
            api_key: Riot API key. If not provided, reads RIOT_API_KEY from
                config (which in turn reads from .env).

        Raises:
            ValueError: If no API key is available.

        Instantiates two riotwatcher clients:
          - LolWatcher: platform-routed match and summoner endpoints
          - RiotWatcher: regional-routed account endpoints

        The platform_routing and regional_routing dicts map the project's
        short region codes (KR/NA/EUW) to Riot's routing values. Adding a
        new region requires entries in both dicts and a corresponding
        region block in data/pros.json.
        """
        if api_key is None:
            api_key = config.RIOT_API_KEY

        if not api_key:
            raise ValueError("Riot API key is required. Set RIOT_API_KEY in .env or pass it directly.")

        self.api_key = api_key
        self.lol_watcher = LolWatcher(api_key)
        self.riot_watcher = RiotWatcher(api_key)

        self.platform_routing = {
            "KR": "kr",
            "NA": "na1",
            "EUW": "euw1",
        }

        self.regional_routing = {
            "KR": "asia",
            "NA": "americas",
            "EUW": "europe",
        }

    # ============================================
    # ACCOUNT LOOKUP
    # ============================================

    def get_summoner(self, game_name: str, tag_line: str, region: str) -> Optional[Player]:
        """
        Fetch account data for a Riot ID and return a partial Player.

        Uses Riot's Account-V1 endpoint (regional routing), which is the only
        way to look up a player by Riot ID. The returned Player has puuid,
        game_name, tag_line, and region populated; team, display_name, and
        role are left None because those come from data/pros.json, not Riot.

        Args:
            game_name: Riot ID game name (e.g. "Hide on bush").
            tag_line: Riot ID tag (e.g. "KR1").
            region: Project region code (KR/NA/EUW).

        Returns None on API error (invalid Riot ID, rate limit, network).
        """
        try:
            regional = self.regional_routing.get(region, "asia")
            account = self.riot_watcher.account.by_riot_id(regional, game_name, tag_line)

            return Player(
                puuid=account['puuid'],
                game_name=account['gameName'],
                tag_line=tag_line,
                region=region,
                team=None,
                role=None
            )
        except Exception as e:
            print(f"Error fetching summoner: {e}")
            return None

    # ============================================
    # MATCH FETCHING
    # ============================================

    def get_recent_matches(self, puuid: str, region: str, count: int = 20, include_timeline: bool = True) -> Tuple[list[Match], list[Matchup], list[dict]]:
        """
        Fetch the most recent N ranked-solo matches for a player.

        Used by the refresh path: fast, bounded, no date filtering. Does not
        check the database for existing matches — deduplication happens
        downstream in save_matches_batch.

        Args:
            puuid: Player's PUUID.
            region: Project region code (KR/NA/EUW). Falls back to KR if
                unrecognized.
            count: Number of matches to request. Capped at 100 by Riot.
            include_timeline: If True, fetch skill order and item purchases
                for each match. This doubles the number of HTTP calls but is
                required for the match history detail view to render.

        Returns:
            Tuple of (matches, matchups, participants) where:
              - matches: Match objects for the tracked player
              - matchups: Matchup objects for the tracked player (one per
                match where an enemy laner could be identified)
              - participants: flat list of dicts for all 10 players across
                all fetched matches
        """
        try:
            if region not in self.platform_routing:
                print(f"Unsupported region: {region}. Using KR as fallback.")
                region = "KR"

            platform = self.platform_routing[region]

            match_ids = self.lol_watcher.match.matchlist_by_puuid(
                platform,
                puuid,
                queue=420,
                count=min(count, 100)
            )

            matches = []
            matchups = []
            all_participants = []

            for match_id in match_ids:
                match_data = self.lol_watcher.match.by_id(platform, match_id)

                # Locate the tracked player within this match
                participant = None
                for p in match_data['info']['participants']:
                    if p['puuid'] == puuid:
                        participant = p
                        break

                if not participant:
                    continue

                # 1-indexed participant ID, required by timeline events
                participant_id = match_data['info']['participants'].index(participant) + 1

                # Find enemy laner: same role, opposite team. Falls back to
                # any enemy if role is missing (e.g. blind pick, ARAM).
                enemy_participant = None
                for p in match_data['info']['participants']:
                    if p['teamId'] != participant['teamId'] and p.get('teamPosition') == participant.get('teamPosition'):
                        enemy_participant = p
                        break

                if not enemy_participant:
                    for p in match_data['info']['participants']:
                        if p['teamId'] != participant['teamId']:
                            enemy_participant = p
                            break

                game_version = match_data['info']['gameVersion']
                patch = ".".join(game_version.split('.')[:2])

                skill_order = None
                item_purchases = None

                if include_timeline:
                    try:
                        skill_order = self._extract_skill_order(match_id, platform, participant_id)
                        game_duration = match_data['info']['gameDuration']
                        item_purchases = self._extract_item_purchases(match_id, platform, participant_id, game_duration)
                    except Exception as e:
                        print(f"Warning: Could not extract timeline data for {match_id}: {e}")

                rune_page = self._get_rune_page_from_participant(participant)

                match_obj = Match(
                    match_id=match_id,
                    puuid=puuid,
                    champion_id=participant['championId'],
                    role=participant.get('teamPosition', 'UNKNOWN'),
                    win=participant['win'],
                    kills=participant['kills'],
                    deaths=participant['deaths'],
                    assists=participant['assists'],
                    cs=participant['totalMinionsKilled'],
                    game_duration=match_data['info']['gameDuration'],
                    total_damage=participant['totalDamageDealtToChampions'],
                    vision_score=participant.get('visionScore', 0),
                    gold_earned=participant['goldEarned'],
                    items=self._get_items_from_participant(participant),
                    runes=rune_page['flat_ids'],
                    summoner_spell_d=participant['summoner1Id'],
                    summoner_spell_f=participant['summoner2Id'],
                    patch=patch,
                    game_creation=match_data['info']['gameCreation'],
                    skill_order=skill_order,
                    item_purchases=item_purchases,
                    rune_page=rune_page,
                )
                matches.append(match_obj)

                if enemy_participant:
                    matchup = Matchup(
                        puuid=puuid,
                        ally_champion_id=participant['championId'],
                        enemy_champion_id=enemy_participant['championId'],
                        role=participant.get('teamPosition', 'UNKNOWN'),
                        win=participant['win'],
                        match_id=match_id,
                        patch=patch
                    )
                    matchups.append(matchup)

                # Parse all 10 participants for storage in the shared
                # participants table
                match_participants = []
                for p in match_data['info']['participants']:
                    keystone_rune_id = None
                    secondary_style_id = None

                    perks = p.get('perks', {})
                    styles = perks.get('styles', [])

                    for style in styles:
                        description = style.get('description')
                        selections = style.get('selections', [])
                        if description == 'primaryStyle':
                            if selections:
                                keystone_rune_id = selections[0].get('perk')
                        elif description == 'subStyle':
                            secondary_style_id = style.get('style')

                    items = {}
                    for i in range(7):
                        items[f'item_{i}'] = p.get(f'item{i}', 0)

                    participant_data = {
                        'match_id': match_id,
                        'puuid': p['puuid'],
                        'champion_id': p['championId'],
                        'team_id': p['teamId'],
                        'role': p.get('teamPosition', 'UNKNOWN'),
                        'win': p['win'],
                        'kills': p['kills'],
                        'deaths': p['deaths'],
                        'assists': p['assists'],
                        'cs': p['totalMinionsKilled'],
                        'gold_earned': p['goldEarned'],
                        'total_damage': p['totalDamageDealtToChampions'],
                        'vision_score': p.get('visionScore', 0),
                        'summoner_spell_d': p['summoner1Id'],
                        'summoner_spell_f': p['summoner2Id'],
                        'keystone_rune_id': keystone_rune_id,
                        'secondary_rune_style_id': secondary_style_id,
                        'role_bound_item': p.get('roleBoundItem', 0),
                        'item_0': items.get('item_0', 0),
                        'item_1': items.get('item_1', 0),
                        'item_2': items.get('item_2', 0),
                        'item_3': items.get('item_3', 0),
                        'item_4': items.get('item_4', 0),
                        'item_5': items.get('item_5', 0),
                        'item_6': items.get('item_6', 0),
                    }
                    match_participants.append(participant_data)

                all_participants.extend(match_participants)

            print(f"Retrieved {len(matches)} matches, {len(matchups)} matchups, and {len(all_participants)} participants for {region}")
            return matches, matchups, all_participants

        except ApiError as err:
            print(f"API error fetching matches: {err}")
            return [], [], []
        except Exception as e:
            print(f"Error fetching matches: {e}")
            return [], [], []

    def get_matches_since_date(
        self,
        puuid: str,
        region: str,
        start_date: Optional[datetime] = None,
        db_connection=None,
        include_timeline: bool = True,
        batch_size: int = 20
    ) -> tuple[list[Match], list[Matchup], list[dict]]:
        """
        Fetch all ranked-solo matches for a player since a given date.

        Used by the bulk collection path. Paginates through the player's
        match history, stopping when a match older than start_date is
        reached. If a db_connection is provided, matches already present in
        the database for this player are skipped without fetching their
        details — this saves substantial API budget on repeat runs.

        Args:
            puuid: Player's PUUID.
            region: Project region code (KR/NA/EUW). Falls back to KR.
            start_date: Earliest match to include. Defaults to 31 days ago.
            db_connection: An open DatabaseManager. When provided, enables
                the skip-existing optimization.
            include_timeline: If True, fetch skill order and item purchases
                per match. Roughly doubles HTTP calls.
            batch_size: Matches per page when paging through Riot's matchlist.

        Returns:
            Same 3-tuple shape as get_recent_matches.

        Stops early (rather than raising) when:
          - Riot returns no more matches
          - A match older than start_date is encountered
          - 50 pages have been fetched (safety cap)
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=31)

        start_timestamp = int(start_date.timestamp() * 1000)

        try:
            if region not in self.platform_routing:
                print(f"Unsupported region: {region}. Using KR as fallback.")
                region = "KR"

            platform = self.platform_routing[region]

            matches = []
            matchups = []
            all_participants = []

            start = 0
            max_batches = 50
            batch_count = 0

            print(f"📡 Fetching matches since {start_date.strftime('%Y-%m-%d')}...")

            while batch_count < max_batches:
                batch_count += 1

                match_ids = self.lol_watcher.match.matchlist_by_puuid(
                    platform,
                    puuid,
                    queue=420,
                    count=batch_size,
                    start=start
                )

                if not match_ids:
                    print(f"   ✅ No more matches found")
                    break

                print(f"   📊 Batch {batch_count}: {len(match_ids)} matches")

                for match_id in match_ids:
                    # Skip matches already stored for this player. Uses
                    # the composite (match_id, puuid) check so a match
                    # where this pro played is re-fetched once per pro.
                    if db_connection:
                        try:
                            db_connection.cursor.execute(
                                "SELECT 1 FROM matches WHERE match_id = ? AND puuid = ? LIMIT 1",
                                (match_id, puuid)
                            )
                            if db_connection.cursor.fetchone():
                                print(f"   ⏭️ Skipping existing match for this player: {match_id}")
                                continue
                        except Exception as e:
                            print(f"   ⚠️ Could not check match existence: {e}")

                    match_data = self.lol_watcher.match.by_id(platform, match_id)
                    game_creation = match_data['info']['gameCreation']

                    # Stop paging once we cross the start_date threshold
                    if game_creation < start_timestamp:
                        print(f"   ⏹️ Reached matches before {start_date.strftime('%Y-%m-%d')}. Stopping.")
                        return matches, matchups, all_participants

                    participant = None
                    for p in match_data['info']['participants']:
                        if p['puuid'] == puuid:
                            participant = p
                            break

                    if not participant:
                        print(f"   ⚠️ Participant not found for match {match_id}")
                        continue

                    # 1-indexed participant ID, required by timeline events
                    participant_id = match_data['info']['participants'].index(participant) + 1

                    enemy_participant = None
                    for p in match_data['info']['participants']:
                        if p['teamId'] != participant['teamId'] and p.get('teamPosition') == participant.get('teamPosition'):
                            enemy_participant = p
                            break

                    if not enemy_participant:
                        for p in match_data['info']['participants']:
                            if p['teamId'] != participant['teamId']:
                                enemy_participant = p
                                break

                    game_version = match_data['info']['gameVersion']
                    patch = ".".join(game_version.split('.')[:2])

                    skill_order = None
                    item_purchases = None

                    if include_timeline:
                        try:
                            skill_order = self._extract_skill_order(match_id, platform, participant_id)
                            game_duration = match_data['info']['gameDuration']
                            item_purchases = self._extract_item_purchases(match_id, platform, participant_id, game_duration)
                        except Exception as e:
                            print(f"Warning: Could not extract timeline data for {match_id}: {e}")

                    rune_page = self._get_rune_page_from_participant(participant)

                    match_obj = Match(
                        match_id=match_id,
                        puuid=puuid,
                        champion_id=participant['championId'],
                        role=participant.get('teamPosition', 'UNKNOWN'),
                        win=participant['win'],
                        kills=participant['kills'],
                        deaths=participant['deaths'],
                        assists=participant['assists'],
                        cs=participant['totalMinionsKilled'],
                        game_duration=match_data['info']['gameDuration'],
                        total_damage=participant['totalDamageDealtToChampions'],
                        vision_score=participant.get('visionScore', 0),
                        gold_earned=participant['goldEarned'],
                        items=self._get_items_from_participant(participant),
                        runes=rune_page['flat_ids'],
                        summoner_spell_d=participant['summoner1Id'],
                        summoner_spell_f=participant['summoner2Id'],
                        patch=patch,
                        game_creation=game_creation,
                        skill_order=skill_order,
                        item_purchases=item_purchases,
                        rune_page=rune_page,
                    )
                    matches.append(match_obj)

                    if enemy_participant:
                        matchup = Matchup(
                            puuid=puuid,
                            ally_champion_id=participant['championId'],
                            enemy_champion_id=enemy_participant['championId'],
                            role=participant.get('teamPosition', 'UNKNOWN'),
                            win=participant['win'],
                            match_id=match_id,
                            patch=patch
                        )
                        matchups.append(matchup)

                    match_participants = []
                    for p in match_data['info']['participants']:
                        keystone_rune_id = None
                        secondary_rune_style_id = None

                        perks = p.get('perks', {})
                        styles = perks.get('styles', [])

                        for style in styles:
                            description = style.get('description')
                            selections = style.get('selections', [])
                            if description == 'primaryStyle':
                                if selections:
                                    keystone_rune_id = selections[0].get('perk')
                            elif description == 'subStyle':
                                secondary_rune_style_id = style.get('style')

                        participant_data = {
                            'match_id': match_id,
                            'puuid': p['puuid'],
                            'champion_id': p['championId'],
                            'team_id': p['teamId'],
                            'role': p.get('teamPosition', 'UNKNOWN'),
                            'win': p['win'],
                            'kills': p['kills'],
                            'deaths': p['deaths'],
                            'assists': p['assists'],
                            'cs': p['totalMinionsKilled'],
                            'gold_earned': p['goldEarned'],
                            'total_damage': p['totalDamageDealtToChampions'],
                            'vision_score': p.get('visionScore', 0),
                            'summoner_spell_d': p['summoner1Id'],
                            'summoner_spell_f': p['summoner2Id'],
                            'keystone_rune_id': keystone_rune_id,
                            'secondary_rune_style_id': secondary_rune_style_id,
                            'role_bound_item': p.get('roleBoundItem', 0),
                            'item_0': p.get('item0', 0),
                            'item_1': p.get('item1', 0),
                            'item_2': p.get('item2', 0),
                            'item_3': p.get('item3', 0),
                            'item_4': p.get('item4', 0),
                            'item_5': p.get('item5', 0),
                            'item_6': p.get('item6', 0),
                        }
                        match_participants.append(participant_data)

                    all_participants.extend(match_participants)

                start += len(match_ids)

            print(f"✅ Retrieved {len(matches)} matches, {len(matchups)} matchups, and {len(all_participants)} participants since {start_date.strftime('%Y-%m-%d')}")
            return matches, matchups, all_participants

        except ApiError as err:
            print(f"API error fetching matches since date: {err}")
            return [], [], []
        except Exception as e:
            print(f"Error fetching matches since date: {e}")
            import traceback
            traceback.print_exc()
            return [], [], []

    # ============================================
    # TIMELINE PARSING
    # ============================================

    def _extract_skill_order(self, match_id: str, platform: str, participant_id: int) -> Optional[str]:
        """
        Parse a match timeline and return the ability level-up order as a
        string like "QWEQRQWQ...".

        Args:
            participant_id: Riot's 1-indexed participant ID (1-10) for the
                player whose skill order should be extracted. This is NOT
                the same as the participant's index in the participants
                list — the caller must compute it as index + 1.

        Returns None if the timeline has no SKILL_LEVEL_UP events for this
        participant, or if the fetch fails.
        """
        try:
            timeline_data = self.lol_watcher.match.timeline_by_match(platform, match_id)

            # Riot uses 1=Q, 2=W, 3=E, 4=R in SKILL_LEVEL_UP events
            ability_map = {1: 'Q', 2: 'W', 3: 'E', 4: 'R'}
            skill_order = []

            for frame in timeline_data['info']['frames']:
                for event in frame.get('events', []):
                    if event.get('type') == 'SKILL_LEVEL_UP':
                        if event.get('participantId') == participant_id:
                            skill_slot = event.get('skillSlot', -1)
                            ability = ability_map.get(skill_slot, '?')
                            if ability != '?':
                                skill_order.append(ability)

            if skill_order:
                return ''.join(skill_order)
            return None

        except ApiError as err:
            print(f"   ❌ Error fetching timeline for skill order: {err}")
            return None
        except Exception as e:
            print(f"   ❌ Error parsing skill order: {e}")
            return None

    def _extract_item_purchases(self, match_id: str, platform: str, participant_id: int, game_duration: int) -> list[ItemPurchase]:
        """
        Parse a match timeline and return this participant's purchase history.

        Handles three event types:
          - ITEM_PURCHASED: item added to inventory
          - ITEM_SOLD: item sold (gold refunded at sell value)
          - ITEM_UNDO: purchase reverted inside the shop's undo window.
            Riot does not emit ITEM_SOLD for undos — from the game's
            perspective the purchase never happened. But in practice,
            players regularly mistake-buy starting items and undo them,
            so we treat ITEM_UNDO identically to ITEM_SOLD when marking a
            purchase as removed.

        Both ITEM_SOLD and ITEM_UNDO mark the matching purchase with a
        sold_timestamp. Downstream queries use this to filter mistake-buys
        out of the "starting items" aggregation.

        Core items (from _get_core_item_ids) get an is_core flag and a
        1-indexed core_order assigned in purchase order — the Nth core item
        purchased gets core_order=N, so the "1st core item" query can pull
        the right rows.

        Returns purchases sorted by timestamp, with any post-game-duration
        events filtered out.
        """
        try:
            core_item_ids = self._get_core_item_ids()

            timeline_data = self.lol_watcher.match.timeline_by_match(platform, match_id)

            purchases = []
            removals = []
            core_purchase_count = 0

            for frame in timeline_data['info']['frames']:
                timestamp = int(frame.get('timestamp', 0) / 1000)

                for event in frame.get('events', []):
                    event_type = event.get('type')
                    event_participant_id = event.get('participantId')

                    if event_participant_id != participant_id:
                        continue

                    if event_type == 'ITEM_PURCHASED':
                        item_id = event.get('itemId', 0)
                        if not item_id:
                            continue

                        is_core = item_id in core_item_ids
                        core_order = None
                        if is_core:
                            core_purchase_count += 1
                            core_order = core_purchase_count

                        purchases.append(ItemPurchase(
                            item_id=item_id,
                            timestamp=timestamp,
                            is_core=is_core,
                            core_order=core_order,
                        ))

                    elif event_type == 'ITEM_SOLD':
                        item_id = event.get('itemId', 0)
                        if item_id:
                            removals.append((item_id, timestamp))

                    elif event_type == 'ITEM_UNDO':
                        # beforeId is the item that was undone; afterId is
                        # what replaced it (usually 0). Only beforeId matters.
                        undone_item_id = event.get('beforeId', 0)
                        if undone_item_id:
                            removals.append((undone_item_id, timestamp))

            # Pair each removal with the most recent unmatched purchase of
            # the same item_id that occurred at or before the removal time.
            # Iterating purchases in reverse ensures FIFO pairing when the
            # same item was bought more than once.
            for removed_item_id, removed_ts in removals:
                for p in reversed(purchases):
                    if (p.item_id == removed_item_id
                            and p.sold_timestamp is None
                            and p.timestamp <= removed_ts):
                        p.sold_timestamp = removed_ts
                        break

            purchases = [p for p in purchases if p.timestamp <= game_duration]
            return sorted(purchases, key=lambda x: x.timestamp)

        except ApiError as err:
            print(f"   ❌ API error fetching timeline for item purchases: {err}")
            return []
        except Exception as e:
            print(f"   ❌ Error parsing item purchases: {e}")
            import traceback
            traceback.print_exc()
            return []

    # ============================================
    # PARTICIPANT PARSING HELPERS
    # ============================================

    def _get_items_from_participant(self, participant: dict) -> list[int]:
        """
        Extract non-zero item IDs from a participant's item_0..item_6 slots.

        Riot uses 0 for empty slots. This method drops those so the result
        is a compact list of items the player actually had at game end.
        Order is preserved (item_0 first, item_6 last).
        """
        items = []
        for i in range(7):
            item_id = participant.get(f'item{i}', 0)
            if item_id and item_id != 0:
                items.append(item_id)
        return items

    def _get_rune_page_from_participant(self, participant: dict) -> dict:
        """
        Parse a participant's perks payload into a structured rune page.

        Returns a dict with these keys:
          primary_style:    rune tree ID (8000/8100/8200/8300/8400)
          keystone:         first rune in the primary tree
          primary_runes:    all selections in the primary tree, in order
          secondary_style:  rune tree ID for the secondary tree
          secondary_runes:  selections in the secondary tree, in order
          shards:           dict of {offense, flex, defense} shard IDs
          flat_ids:         flattened list used for storage in the DB

        Ordering matters: flat_ids is always
          [primary_runes..., secondary_runes..., offense, flex, defense]
        The database layer relies on shards being the last 3 entries when
        assigning `shard_*` slot names.

        Riot's styles array uses `description` to distinguish primary from
        secondary (`"primaryStyle"` vs `"subStyle"`); the tree ID lives in
        `style`, not `styleId`.
        """
        perks = participant.get('perks', {})
        styles = perks.get('styles', [])

        primary_style = None
        keystone = None
        primary_runes = []
        secondary_style = None
        secondary_runes = []

        for style in styles:
            style_id = style.get('style')
            selections = style.get('selections', [])
            rune_ids = [s.get('perk') for s in selections if s.get('perk')]
            description = style.get('description')

            if description == 'primaryStyle':
                primary_style = style_id
                primary_runes = rune_ids
                if rune_ids:
                    keystone = rune_ids[0]
            elif description == 'subStyle':
                secondary_style = style_id
                secondary_runes = rune_ids

        stat_perks = perks.get('statPerks', {})
        shards = {
            'offense': stat_perks.get('offense', 0),
            'flex': stat_perks.get('flex', 0),
            'defense': stat_perks.get('defense', 0),
        }

        flat_ids = primary_runes + secondary_runes + [
            shards['offense'], shards['flex'], shards['defense']
        ]

        return {
            'primary_style': primary_style,
            'keystone': keystone,
            'primary_runes': primary_runes,
            'secondary_style': secondary_style,
            'secondary_runes': secondary_runes,
            'shards': shards,
            'flat_ids': [r for r in flat_ids if r],
        }

    # ============================================
    # CORE ITEM CLASSIFICATION
    # ============================================

    def _get_core_item_ids(self) -> set:
        """
        Return the set of item IDs considered "core" for the current patch.

        There is no official Riot definition of "core item," so this uses a
        heuristic: an item is core if it has a 4-digit ID and a total gold
        cost of at least 1700g. This captures completed legendary items
        while excluding components, consumables, and starting items. A
        second pass adds any item whose name contains "boots" and costs at
        least 400g, because tier-2 boots matter for build tracking even
        though they fall below the gold threshold.

        Results are cached for 24 hours in cache/core_items.json to avoid
        re-fetching Data Dragon on every collection run. Delete the cache
        file to force a refresh.

        Caveats:
          - The 1700g threshold is a guess and will drift as Riot adds
            items with unusual gold costs. Worth eyeballing occasionally.
          - 4-digit IDs alone would include starter items, which also
            have 4-digit IDs; the gold check is what filters them out.
          - Returns an empty set on any error, meaning no item will be
            flagged as core. This is safe but means the core items section
            of the UI will be blank until the fetch succeeds.
        """
        try:
            cache_file = 'cache/core_items.json'

            # Try the cache first
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    cache_time = datetime.fromisoformat(cache_data['timestamp'])
                    if datetime.now() - cache_time < timedelta(hours=24):
                        return set(cache_data['item_ids'])

            # Cache miss or stale — fetch Data Dragon fresh
            DD_BASE = 'https://ddragon.leagueoflegends.com'
            version_res = requests.get(f"{DD_BASE}/api/versions.json")
            version_res.raise_for_status()
            latest_version = version_res.json()[0]

            item_res = requests.get(f"{DD_BASE}/cdn/{latest_version}/data/en_US/item.json")
            item_res.raise_for_status()
            item_data = item_res.json()['data']

            core_item_ids = set()

            # Primary pass: 4-digit ID and >=1700g
            for item_id_str, item_info in item_data.items():
                if 'gold' not in item_info:
                    continue

                gold_total = item_info['gold'].get('total', 0)
                if len(item_id_str) == 4 and gold_total >= 1700:
                    core_item_ids.add(int(item_id_str))

            # Secondary pass: boots (below the gold threshold but still
            # meaningful for build tracking)
            for item_id_str, item_info in item_data.items():
                if len(item_id_str) != 4:
                    continue

                item_name = item_info.get('name', '').lower()
                if 'boots' in item_name and 'gold' in item_info:
                    gold_total = item_info['gold'].get('total', 0)
                    if gold_total >= 400:
                        core_item_ids.add(int(item_id_str))

            # Persist to cache
            os.makedirs('cache', exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'item_ids': list(core_item_ids)
                }, f)

            print(f"✅ Loaded {len(core_item_ids)} core items (gold >= 1700)")
            return core_item_ids

        except Exception as e:
            print(f"⚠️ Error fetching core item IDs: {e}")
            return set()