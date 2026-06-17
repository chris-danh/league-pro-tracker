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
            "KR": "kr1",
            "NA": "na1",
            "EUW": "euw1",
        }
        
        self.regional_routing = {
            "KR": "asia",
            "NA": "americas",
            "EUW": "europe",
        }
        
        print("✅ Riot API client initialized (Riot-Watcher)")

    def get_summoner(self, game_name: str, tag_line: str, region: str) -> Optional[Player]:
        """
        Get a summoner by Riot ID (game name + tag line).
        
        Step 1: Get PUUID from Account API
        Step 2: Get Summoner details using PUUID
        """
        try:
            # Validate region
            if region not in self.regional_routing:
                print(f"⚠️ Unsupported region: {region}. Using KR as fallback.")
                region = "KR"
            
            # Step 1: Get PUUID using Account API
            regional = self.regional_routing[region]
            account = self.riot_watcher.account.by_riot_id(regional, game_name, tag_line)
            puuid = account['puuid']
            
            # Step 2: Get Summoner details using PUUID
            platform = self.platform_routing[region]
            summoner = self.lol_watcher.summoner.by_puuid(platform, puuid)
            
            player = Player(
                puuid=puuid,
                game_name=summoner['name'],
                tag_line=tag_line,
                region=region,
                team=None,
                role=None
            )
            print(f"✅ Found summoner: {summoner['name']} (Level {summoner['summonerLevel']}) on {region}")
            return player
            
        except ApiError as err:
            if err.response.status_code == 404:
                print(f"⚠️ Summoner not found: {game_name}#{tag_line} on {region}")
            else:
                print(f"❌ API error: {err}")
            return None
        except Exception as e:
            print(f"❌ Error fetching summoner {game_name}#{tag_line} on {region}: {e}")
            return None

    def get_recent_matches(self, puuid: str, region: str, count: int = 20) -> list[Match]:
        """
        Get recent matches for a summoner using PUUID.
        """
        try:
            # Validate region
            if region not in self.platform_routing:
                print(f"⚠️ Unsupported region: {region}. Using KR as fallback.")
                region = "KR"
            
            platform = self.platform_routing[region]
            
            # Get match IDs (max 100)
            match_ids = self.lol_watcher.match.matchlist_by_puuid(
                platform, 
                puuid, 
                queue=420,  # Ranked Solo
                count=min(count, 100)
            )
            
            matches = []
            for match_id in match_ids:
                # Get full match details
                match_data = self.lol_watcher.match.by_id(platform, match_id)
                
                # Find the participant for this player
                participant_data = None
                for p in match_data['info']['participants']:
                    if p['puuid'] == puuid:
                        participant_data = p
                        break
                
                if not participant_data:
                    continue
                
                # Extract match data
                match_obj = Match(
                    match_id=match_id,
                    puuid=puuid,
                    champion=participant_data['championName'],
                    role=self._determine_role_from_participant(participant_data),
                    win=participant_data['win'],
                    kills=participant_data['kills'],
                    deaths=participant_data['deaths'],
                    assists=participant_data['assists'],
                    cs=participant_data['totalMinionsKilled'],
                    game_duration=match_data['info']['gameDuration'],
                    total_damage=participant_data['totalDamageDealtToChampions'],
                    vision_score=participant_data.get('visionScore', 0),
                    gold_earned=participant_data['goldEarned'],
                    items=self._get_items_from_participant(participant_data),
                    runes=self._get_runes_from_participant(participant_data),
                    summoner_spell_d=participant_data['summoner1Id'],  # D key
                    summoner_spell_f=participant_data['summoner2Id']   # F key
                )
                matches.append(match_obj)
            
            print(f"✅ Retrieved {len(matches)} matches for {region}")
            return matches
            
        except ApiError as err:
            print(f"❌ API error fetching matches: {err}")
            return []
        except Exception as e:
            print(f"❌ Error fetching matches for PUUID {puuid} on {region}: {e}")
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

    def test_connection(self, test_region: str = "KR") -> bool:
        """Test if the API key works by fetching a known summoner."""
        try:
            # Validate region
            if test_region not in self.regional_routing:
                test_region = "KR"
            
            regional = self.regional_routing[test_region]
            account = self.riot_watcher.account.by_riot_id(regional, "Hide on bush", "KR1")
            if account:
                print(f"✅ API connection successful! Found account")
                return True
            return False
        except ApiError as err:
            print(f"❌ API connection failed: {err}")
            return False
        except Exception as e:
            print(f"❌ API connection failed: {e}")
            return False

    # ============================================
    # Helper methods
    # ============================================

    def _determine_role_from_participant(self, participant: dict) -> str:
        """Determine role from participant data."""
        # individualPosition is the most accurate
        if participant.get('individualPosition'):
            return participant['individualPosition']
        
        # Fallback to lane + teamPosition
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
        """Extract rune IDs from participant data."""
        runes = []
        perks = participant.get('perks', {})
        styles = perks.get('styles', [])
        
        for style in styles:
            selections = style.get('selections', [])
            for selection in selections:
                rune_id = selection.get('perk', 0)
                if rune_id:
                    runes.append(rune_id)
        
        return runes

    def get_current_patch(self, region: str = "KR") -> str:
        """
        Get the current patch version by fetching a recent match.
        """
        try:
            platform = self.platform_routing.get(region, "kr")
            
            # Get a recent pro match (Faker's most recent game)
            summoner = self.lol_watcher.summoner.by_name(platform, "Hide on bush")
            match_ids = self.lol_watcher.match.matchlist_by_puuid(
                platform, 
                summoner['puuid'], 
                queue=420,  # Ranked Solo
                count=1
            )
            
            if match_ids:
                match_data = self.lol_watcher.match.by_id(platform, match_ids[0])
                full_version = match_data['info']['gameVersion']
                # Extract major.minor patch (e.g., "16.10" from "16.10.123.456")
                patch = ".".join(full_version.split('.')[:2])
                return patch
            
            return "Unknown"
        except Exception as e:
            print(f"⚠️ Could not fetch current patch: {e}")
            return "Unknown"