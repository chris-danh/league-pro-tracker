# src/api/riot_client.py
from typing import Optional, Tuple
from datetime import datetime, timedelta
from riotwatcher import LolWatcher, RiotWatcher, ApiError
from src.models import Player, Match, Matchup, ItemPurchase
import json
import os
import config


class RiotAPIClient:
    """Handles all Riot API interactions using Riot-Watcher"""

    def __init__(self, api_key: str = None):
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

    def get_summoner(self, game_name: str, tag_line: str, region: str) -> Optional[Player]:
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

    def get_recent_matches(self, puuid: str, region: str, count: int = 20, include_timeline: bool = True) -> Tuple[list[Match], list[Matchup], list[dict]]:
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

                participant = None
                for p in match_data['info']['participants']:
                    if p['puuid'] == puuid:
                        participant = p
                        break

                if not participant:
                    continue

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
                    game_creation=match_data['info']['gameCreation'],
                    skill_order=skill_order,
                    item_purchases=item_purchases,
                    rune_page=rune_page,
                )
                matches.append(match_obj)

                if enemy_participant:
                    matchup = Matchup(
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
                    secondary_style_id = None

                    perks = p.get('perks', {})
                    styles = perks.get('styles', [])

                    for style in styles:
                        selections = style.get('selections', [])
                        if selections:
                            keystone_rune_id = selections[0].get('perk')

                        if style.get('style') == 'secondary':
                            secondary_style_id = style.get('styleId')

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
                    if db_connection:
                        try:
                            db_connection.cursor.execute(
                                "SELECT 1 FROM matches WHERE match_id = ? LIMIT 1",
                                (match_id,)
                            )
                            if db_connection.cursor.fetchone():
                                print(f"   ⏭️ Skipping existing match: {match_id}")
                                continue
                        except Exception as e:
                            print(f"   ⚠️ Could not check match existence: {e}")

                    match_data = self.lol_watcher.match.by_id(platform, match_id)
                    game_creation = match_data['info']['gameCreation']

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
                            selections = style.get('selections', [])
                            if selections and keystone_rune_id is None:
                                keystone_rune_id = selections[0].get('perk')

                            if style.get('style') == 'secondary':
                                secondary_rune_style_id = style.get('styleId')

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

    def _extract_skill_order(self, match_id: str, platform: str, participant_id: int) -> Optional[str]:
        try:
            timeline_data = self.lol_watcher.match.timeline_by_match(platform, match_id)

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
        Extract item purchase, sale, and undo timestamps from timeline data.

        ITEM_UNDO is treated the same as ITEM_SOLD — the purchase is marked as
        removed so downstream queries exclude mistake-buys from starting items.
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
                        undone_item_id = event.get('beforeId', 0)
                        if undone_item_id:
                            removals.append((undone_item_id, timestamp))

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

    def _get_items_from_participant(self, participant: dict) -> list[int]:
        items = []
        for i in range(7):
            item_id = participant.get(f'item{i}', 0)
            if item_id and item_id != 0:
                items.append(item_id)
        return items

    def _get_rune_page_from_participant(self, participant: dict) -> dict:
        """
        Returns a structured rune page:
          {
            'primary_style': 8000,
            'keystone': 8010,
            'primary_runes': [8010, 9111, 8009, 8299],
            'secondary_style': 8100,
            'secondary_runes': [8135, 8106],
            'shards': {'offense': 5005, 'flex': 5008, 'defense': 5001},
            'flat_ids': [8010, 9111, 8009, 8299, 8135, 8106, 5005, 5008, 5001]
          }
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

    def _get_core_item_ids(self) -> set:
        try:
            import requests

            cache_file = 'cache/core_items.json'

            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    cache_time = datetime.fromisoformat(cache_data['timestamp'])
                    if datetime.now() - cache_time < timedelta(hours=24):
                        return set(cache_data['item_ids'])

            DD_BASE = 'https://ddragon.leagueoflegends.com'
            version_res = requests.get(f"{DD_BASE}/api/versions.json")
            version_res.raise_for_status()
            latest_version = version_res.json()[0]

            item_res = requests.get(f"{DD_BASE}/cdn/{latest_version}/data/en_US/item.json")
            item_res.raise_for_status()
            item_data = item_res.json()['data']

            core_item_ids = set()
            for item_id_str, item_info in item_data.items():
                if 'gold' not in item_info:
                    continue

                gold_total = item_info['gold'].get('total', 0)
                if len(item_id_str) == 4 and gold_total >= 1700:
                    core_item_ids.add(int(item_id_str))

            for item_id_str, item_info in item_data.items():
                if len(item_id_str) != 4:
                    continue

                item_name = item_info.get('name', '').lower()
                if 'boots' in item_name and 'gold' in item_info:
                    gold_total = item_info['gold'].get('total', 0)
                    if gold_total >= 400:
                        core_item_ids.add(int(item_id_str))

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