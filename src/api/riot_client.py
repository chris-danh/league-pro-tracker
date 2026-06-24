
from typing import Optional
from riotwatcher import LolWatcher, RiotWatcher, ApiError
from src.models import Player, Match
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
        """
        Get a summoner by Riot ID (game name + tag line).
        
        Step 1: Get PUUID and name from Account API
        Step 2: Get summoner level using PUUID from Summoner API
        """
        try:
            # Validate region
            if region not in self.regional_routing:
                print(f"Unsupported region: {region}. Using KR as fallback.")
                region = "KR"
            
            # Step 1: Get account info (contains puuid and gameName)
            regional = self.regional_routing[region]
            account = self.riot_watcher.account.by_riot_id(regional, game_name, tag_line)
            
            puuid = account['puuid']
            account_name = account['gameName']  # This is the summoner name
            
            # Step 2: Get summoner level using PUUID
            platform = self.platform_routing[region]
            summoner = self.lol_watcher.summoner.by_puuid(platform, puuid)
            
            player = Player(
                puuid=puuid,
                game_name=account_name,  # Use name from Account API
                tag_line=tag_line,
                region=region,
                team=None,
                role=None
            )
            print(f"Found summoner: {account_name} on {region}")
            return player
            
        except ApiError as err:
            if err.response.status_code == 404:
                print(f"Summoner not found: {game_name}#{tag_line} on {region}")
            else:
                print(f"API error: {err}")
            return None
        except Exception as e:
            print(f"Error fetching summoner {game_name}#{tag_line} on {region}: {e}")
            return None

    def get_recent_matches(self, puuid: str, region: str, count: int = 20) -> list[Match]:
        """
        Get recent matches for a summoner using PUUID.
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
            for match_id in match_ids:
                # Get match details
                match_data = self.lol_watcher.match.by_id(platform, match_id)
                print(platform)
                print(match_id)
                # Find participant for this player
                participant = None
                for p in match_data['info']['participants']:
                    if p['puuid'] == puuid:
                        participant = p
                        break
                
                if not participant:
                    continue
                
                match_obj = Match(
                    match_id=match_id,
                    puuid=puuid,
                    champion=participant['championName'],
                    role=participant['role'],
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
                    summoner_spell_f=participant['summoner2Id']
                )
                matches.append(match_obj)
            
            print(f"Retrieved {len(matches)} matches for {region}")
            return matches
            
        except ApiError as err:
            print(f"API error fetching matches: {err}")
            return []
        except Exception as e:
            print(f"Error fetching matches: {e}")
            return []

    def get_player_with_matches(
        self, 
        game_name: str, 
        tag_line: str, 
        region: str, 
        match_count: int = 20
    ) -> tuple[Optional[Player], list[Match]]:
        """Get a player and their recent matches."""
        player = self.get_summoner(game_name, tag_line, region)
        
        if player:
            matches = self.get_recent_matches(player.puuid, region, match_count)
            return player, matches
        
        return None, []



    def _determine_role_from_participant(self, participant: dict) -> str:
        """Determine role from participant data."""
        if participant.get('individualPosition'):
            return participant['individualPosition']
        
        lane = participant.get('lane', '')
        role = participant.get('teamPosition', '')
        
        role_map = {
            ("MID_LANE", "SOLO"): "MIDDLE",
            ("TOP_LANE", "SOLO"): "TOP",
            ("JUNGLE", ""): "JUNGLE",
            ("BOT_LANE", "BOTTOM"): "BOTTOM",
            ("BOT_LANE", "UTILITY"): "UTILITY",
        }
        
        return role_map.get((lane, role), "UNKNOWN")

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
        
        # Stat shard IDs (these are the minor runes)
        # The keys are: offense, flex, defense
        stat_rune_ids = [
            stat_perks.get('offense', 0),   # Attack Speed, Adaptive Force, etc.
            stat_perks.get('flex', 0),      # Adaptive Force, Armor, Magic Resist, etc.
            stat_perks.get('defense', 0),   # Armor, Magic Resist, Health, etc.
        ]
        
        # Add non-zero stat runes
        for stat_id in stat_rune_ids:
            if stat_id and stat_id != 0:
                runes.append(stat_id)
        
        return runes