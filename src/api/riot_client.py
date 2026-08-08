# src/api/riot_client.py
from typing import Optional, Tuple
from datetime import datetime, timedelta
from riotwatcher import LolWatcher, RiotWatcher, ApiError
from src.models import Player, Match, Matchup, ItemPurchase
import config


class RiotAPIClient:
    """Handles all Riot API interactions using Riot-Watcher"""
    
    def __init__(self, api_key: str = None):
        """Initialize the Riot API client."""
        if api_key is None:
            api_key = config.RIOT_API_KEY
        
        if not api_key:
            raise ValueError("Riot API key is required. Set RIOT_API_KEY in .env or pass it directly.")
        
        self.api_key = api_key
        self.lol_watcher = LolWatcher(api_key)
        self.riot_watcher = RiotWatcher(api_key)
        
        # Region mappings
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
        """Helper to fetch a summoner by name/tag (for debugging)."""
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
    
    def get_recent_matches(self, puuid: str, region: str, count: int = 20, include_timeline: bool = True) -> Tuple[list[Match], list[Matchup]]:
        """
        Get recent matches for a summoner using PUUID.
        
        Args:
            puuid: Player's PUUID
            region: Region (KR, NA, EUW)
            count: Number of matches to fetch (max 100)
            include_timeline: Whether to fetch timeline for skill order and item purchases
        
        Returns:
            Tuple of (matches, matchups)
        """
        try:
            # Validate region
            if region not in self.platform_routing:
                print(f"Unsupported region: {region}. Using KR as fallback.")
                region = "KR"
            
            platform = self.platform_routing[region]
            
            # Get match IDs (ranked solo)
            match_ids = self.lol_watcher.match.matchlist_by_puuid(
                platform, 
                puuid, 
                queue=420,  # Ranked Solo
                count=min(count, 100)
            )
            
            matches = []
            matchups = []
            
            for match_id in match_ids:
                # Get match details
                match_data = self.lol_watcher.match.by_id(platform, match_id)
                
                # Find participant for this player
                participant = None
                for p in match_data['info']['participants']:
                    if p['puuid'] == puuid:
                        participant = p
                        break
                
                if not participant:
                    continue
                
                # Get participant ID (1-indexed)
                participant_id = match_data['info']['participants'].index(participant) + 1
                
                # Find enemy laner (same role, opposite team)
                enemy_participant = None
                for p in match_data['info']['participants']:
                    if p['teamId'] != participant['teamId'] and p.get('teamPosition') == participant.get('teamPosition'):
                        enemy_participant = p
                        break
                
                # If no exact role match, find any enemy
                if not enemy_participant:
                    for p in match_data['info']['participants']:
                        if p['teamId'] != participant['teamId']:
                            enemy_participant = p
                            break
                
                # Extract patch info
                game_version = match_data['info']['gameVersion']
                patch = ".".join(game_version.split('.')[:2])
                
                # Extract skill order and item purchases if requested
                skill_order = None
                skill_order_levels = None
                item_purchases = None
                
                if include_timeline:
                    try:
                        skill_order, skill_order_levels = self._extract_skill_order(
                            match_id, platform, participant_id
                        )
                        
                        game_duration = match_data['info']['gameDuration']
                        item_purchases = self._extract_item_purchases(
                            match_id, platform, participant_id, game_duration
                        )
                    except Exception as e:
                        print(f"Warning: Could not extract timeline data for {match_id}: {e}")
                
                # Create Match object
                match_obj = Match(
                    match_id=match_id,
                    puuid=puuid,
                    champion_id=participant['championId'],  # Use ID instead of name
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
                    runes=self._get_runes_from_participant(participant),
                    summoner_spell_d=participant['summoner1Id'],
                    summoner_spell_f=participant['summoner2Id'],
                    patch=patch,
                    game_creation=match_data['info']['gameCreation'],
                    skill_order=skill_order,
                    skill_order_levels=skill_order_levels,
                    item_purchases=item_purchases
                )
                matches.append(match_obj)
                
                # Create Matchup object if enemy found
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
            
            print(f"Retrieved {len(matches)} matches and {len(matchups)} matchups for {region}")
            return matches, matchups
            
        except ApiError as err:
            print(f"API error fetching matches: {err}")
            return [], []
        except Exception as e:
            print(f"Error fetching matches: {e}")
            return [], []

# src/api/riot_client.py

    def get_matches_since_date(
        self,
        puuid: str,
        region: str,
        start_date: Optional[datetime] = None,
        max_count: int = 100
    ) -> tuple[list[Match], list[Matchup]]:
        """
        Get matches for a player since a specific date.
        If no start_date provided, get last 31 days.
        
        Args:
            puuid: Player's PUUID
            region: Region (KR, NA, EUW)
            start_date: Optional datetime to fetch matches from
            max_count: Maximum number of matches to fetch (default 100)
        
        Returns:
            tuple: (list of Match objects, list of Matchup objects)
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=31)
        
        start_timestamp = int(start_date.timestamp() * 1000)
        
        try:
            # Validate region
            if region not in self.platform_routing:
                print(f"Unsupported region: {region}. Using KR as fallback.")
                region = "KR"
            
            platform = self.platform_routing[region]
            
            # Get match IDs (ranked solo)
            match_ids = self.lol_watcher.match.matchlist_by_puuid(
                platform,
                puuid,
                queue=420,  # Ranked Solo
                count=min(max_count, 100)  # Riot API max is 100
            )
            
            matches = []
            matchups = []
            
            for match_id in match_ids:
                # Get match details
                match_data = self.lol_watcher.match.by_id(platform, match_id)
                
                # Check if match is within our date range
                game_creation = match_data['info']['gameCreation']
                if game_creation < start_timestamp:
                    break  # Matches are in descending order, so we can break
                
                # Find participant for this player
                participant = None
                for p in match_data['info']['participants']:
                    if p['puuid'] == puuid:
                        participant = p
                        break

                if not participant:
                    continue
                
                # Get participant ID (1-indexed)
                participant_id = match_data['info']['participants'].index(participant) + 1
                
                # Find enemy laner (same role, opposite team)
                enemy_participant = None
                for p in match_data['info']['participants']:
                    if p['teamId'] != participant['teamId'] and p.get('teamPosition') == participant.get('teamPosition'):
                        enemy_participant = p
                        break
                
                # If no exact role match, find any enemy
                if not enemy_participant:
                    for p in match_data['info']['participants']:
                        if p['teamId'] != participant['teamId']:
                            enemy_participant = p
                            break
                
                # Extract patch info
                game_version = match_data['info']['gameVersion']
                patch = ".".join(game_version.split('.')[:2])
                
                # Extract skill order and item purchases from timeline
                skill_order = None
                skill_order_levels = None
                item_purchases = None
                
                try:
                    skill_order, skill_order_levels = self._extract_skill_order(
                        match_id, platform, participant_id
                    )
                    
                    game_duration = match_data['info']['gameDuration']
                    item_purchases = self._extract_item_purchases(
                        match_id, platform, participant_id, game_duration
                    )
                except Exception as e:
                    print(f"Warning: Could not extract timeline data for {match_id}: {e}")
                
                # Create Match object
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
                    runes=self._get_runes_from_participant(participant),
                    summoner_spell_d=participant['summoner1Id'],
                    summoner_spell_f=participant['summoner2Id'],
                    patch=patch,
                    game_creation=game_creation,
                    skill_order=skill_order,
                    skill_order_levels=skill_order_levels,
                    item_purchases=item_purchases
                )
                matches.append(match_obj)
                
                # Create Matchup object if enemy found
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
            
            print(f"Retrieved {len(matches)} matches and {len(matchups)} matchups since {start_date.strftime('%Y-%m-%d')}")
            return matches, matchups
            
        except ApiError as err:
            print(f"API error fetching matches since date: {err}")
            return [], []
        except Exception as e:
            print(f"Error fetching matches since date: {e}")
            return [], []

    def _extract_skill_order(self, match_id: str, platform: str, participant_id: int) -> Tuple[Optional[str], Optional[list[int]]]:
        """
        Extract skill order from timeline data.
        
        Returns:
            Tuple of (skill_order_string, skill_order_levels)
            skill_order_string: e.g., "Q-E-W-Q-Q-R"
            skill_order_levels: e.g., [1, 2, 3, 4, 5, 6]
        """
        try:
            timeline_data = self.lol_watcher.match.timeline_by_match(platform, match_id)
            
            ability_map = {0: 'Q', 1: 'W', 2: 'E', 3: 'R'}
            
            skill_order = []
            skill_order_levels = []
            
            for frame in timeline_data['info']['frames']:
                events = frame.get('events', [])
                for event in events:
                    if event['type'] == 'SKILL_LEVEL_UP':
                        if event.get('participantId') == participant_id:
                            ability = ability_map.get(event.get('skillSlot', -1), '?')
                            if ability != '?':
                                skill_order.append(ability)
                                skill_order_levels.append(event.get('level', 0))
            
            if skill_order:
                return ''.join(skill_order), skill_order_levels
            return None, None
            
        except ApiError as err:
            print(f"Error fetching timeline for skill order: {err}")
            return None, None
        except Exception as e:
            print(f"Error parsing skill order: {e}")
            return None, None

    def _extract_item_purchases(self, match_id: str, platform: str, participant_id: int, game_duration: int) -> list[ItemPurchase]:
        """
        Extract item purchase timestamps from timeline data.
        
        Returns:
            List of ItemPurchase objects sorted by timestamp
        """
        try:
            timeline_data = self.lol_watcher.match.timeline_by_match(platform, match_id)
            
            purchases = []
            previous_items = set()
            
            for frame in timeline_data['info']['frames']:
                timestamp = int(frame.get('timestamp', 0) / 1000)  # Convert ms to seconds
                
                participant_frames = frame.get('participantFrames', {})
                participant_key = str(participant_id)
                
                if participant_key in participant_frames:
                    p_frame = participant_frames[participant_key]
                    current_items = set()
                    
                    for i in range(7):
                        item_id = p_frame.get(f'item{i}', 0)
                        if item_id and item_id != 0:
                            current_items.add(item_id)
                    
                    new_items = current_items - previous_items
                    for item_id in new_items:
                        purchases.append(ItemPurchase(
                            item_id=item_id,
                            timestamp=timestamp
                        ))
                    
                    previous_items = current_items
            
            # Filter out purchases after game end
            purchases = [p for p in purchases if p.timestamp <= game_duration]
            
            return sorted(purchases, key=lambda x: x.timestamp)
            
        except ApiError as err:
            print(f"Error fetching timeline for item purchases: {err}")
            return []
        except Exception as e:
            print(f"Error parsing item purchases: {e}")
            return []

    def _get_items_from_participant(self, participant: dict) -> list[int]:
        """Extract item IDs from participant data."""
        items = []
        for i in range(7):
            item_id = participant.get(f'item{i}', 0)
            if item_id and item_id != 0:
                items.append(item_id)
        return items

    def _get_runes_from_participant(self, participant: dict) -> list[int]:
        """
        Extract all rune IDs from participant data, including minor stat shards.
        
        Returns a list of all rune IDs in order:
        - Primary path runes (keystone + other primary runes)
        - Secondary path runes
        - Minor stat shards (offense, flex, defense)
        """
        runes = []
        
        # 1. Get primary and secondary runes from styles
        perks = participant.get('perks', {})
        styles = perks.get('styles', [])
        
        for style in styles:
            selections = style.get('selections', [])
            for selection in selections:
                rune_id = selection.get('perk', 0)
                if rune_id:
                    runes.append(rune_id)
        
        # 2. Get minor stat shards from statPerks
        stat_perks = perks.get('statPerks', {})
        
        stat_rune_ids = [
            stat_perks.get('offense', 0),
            stat_perks.get('flex', 0),
            stat_perks.get('defense', 0),
        ]
        
        for stat_id in stat_rune_ids:
            if stat_id and stat_id != 0:
                runes.append(stat_id)
        
        return runes