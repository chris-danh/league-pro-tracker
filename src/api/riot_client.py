import cassiopeia as cass
from typing import Optional
from src.models import Player, Match
import config

class RiotAPIClient:

    def __init__(self, api_key: str = None):
        # initializes the API key
        if api_key is None:
            api_key = config.RIOT_API_KEY
        
        if api_key:
            cass.set_riot_api_key(api_key)
    

    def get_summoner(self, game_name: str, tag_line: str, region: str) -> Optional[Player]:
        # creates a player given the summoner details
        try:
            summoner = cass.get_summoner(name=game_name, tagline=tag_line, region=region)

            if summoner:
                player = Player(puuid = summoner.puuid, game_name = summoner.name
                                ,tag_line = tag_line, region = region, team = None, role = None
                                return Player
                )
            return None
        except Exception as e:
            return None
    

    def get_recent_matches(self, puuid: str, region: str, count = 20) -> list[Match]:
        # gets the recent matches of the player with the according stats to store
        try:
            summoner = cass.get_summoner(puuid=puuid, region=region)
            if(summoner):
                match_history = summoner.match_history(queue=cass.Queue.ranked_solo_fives)[:count]

                matches = []
                for match in match_history:
                    participant = match.participants[summoner]
                
                    match_obj = Match(
                    match_id=match.id,
                    puuid=puuid,
                    champion=participant.champion.name,
                    role=self._determine_role(participant),
                    win=participant.win,
                    kills=participant.stats.kills,
                    deaths=participant.stats.deaths,
                    assists=participant.stats.assists,
                    cs=participant.stats.total_minions_killed,
                    game_duration=match.duration.seconds,
                    total_damage=participant.stats.total_damage_dealt_to_champions,
                    vision_score=participant.stats.vision_score,
                    gold_earned=participant.stats.gold_earned,
                    items=self._get_items(participant),
                    runes=self._get_runes(participant),
                    summoner_spell_d=self._get_summoner_spell_d(participant),
                    summoner_spell_f=self._get_summoner_spell_f(participant)
                    )
                    matches.append(match_obj)
                
                return matches
            return []
        except Exception as e:
            return []
    
    def get_player_with_matches(self, game_name: str, tag_line: str, region: str, match_count: int = 20) -> tuple[Optional[Player], list[Match]]:
        player = self.get_summoner(game_name, tag_line, region)
        if player:
            matches = self.get_recent_matches(player.puuid, region, match_count)
            return player, matches
        return None, []
    
    def _determine_role(self, participant) -> str:
        """Determine role from participant data."""
        if hasattr(participant, 'individual_position') and participant.individual_position:
            return participant.individual_position
        
        lane = getattr(participant, 'lane', '')
        role = getattr(participant, 'role', '')
        
        role_map = {
            ("MID_LANE", "SOLO"): "MIDDLE",
            ("TOP_LANE", "SOLO"): "TOP",
            ("JUNGLE", "NONE"): "JUNGLE",
            ("BOT_LANE", "DUO_CARRY"): "BOTTOM",
            ("BOT_LANE", "DUO_SUPPORT"): "UTILITY",
        }
        
        return role_map.get((lane, role), "UNKNOWN")
    
    def _get_items(self, participant) -> list[int]:
        """Extract item IDs from participant stats."""
        items = []
        for i in range(7):
            item_id = getattr(participant.stats, f'item_{i}', 0)
            if item_id and item_id != 0:
                items.append(item_id)
        return items
    
    def _get_runes(self, participant) -> list[int]:
        """Extract rune IDs from participant."""
        runes = []
        if hasattr(participant, 'perks') and participant.perks:
            if hasattr(participant.perks, 'perk_ids'):
                runes.extend(participant.perks.perk_ids)
        return runes
    
    def test_connection(self, test_region: str = "KR") -> bool:
        """Test if the API key works by fetching a known summoner."""
        try:
            summoner = cass.get_summoner(name="Hide on bush", tagline="KR1", region=test_region)
            if summoner:
                print(f"✅ API connection successful! Found: {summoner.name} on {test_region}")
                return True
            return False
        except Exception as e:
            print(f"❌ API connection failed: {e}")
            return False

    
    def _get_summoner_spell_d(self, participant) -> int:
        try:
            return participant.stats.summoner_spell_d
        except AttributeError:
            return 0

    def _get_summoner_spell_f(self, participant) -> int:
        try:
            return participant.stats.summoner_spell_f
        except AttributeError:
            return 0
