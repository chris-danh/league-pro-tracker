from dataclasses import dataclass
from typing import Optional
from enum import Enum

class SortBy(Enum):
    GAMES = "games"
    WINRATE = "winrate"
    KDA = "kda"
    NAME = "name"
    CHAMPION_NAME = "champion_name"

    def __str__(self):
        return self.value

@dataclass
class Player:
    # this class represents a player

    # puuid is the pro player name
    puuid: str

    # information for the riot api to fetch the account
    game_name: str
    tag_line: str
    region: str

    # optional tags for team and role
    team: Optional[str] = None
    role: Optional[str] = None

@dataclass
class Match:
    # this class represents a single match

    match_id: str
    puuid: str
    champion: str
    role: str
    win: bool
    kills: int
    deaths: int
    assists: int
    cs: int
    game_duration: int
    total_damage: int
    vision_score: int
    gold_earned: int
    items: list[int]
    runes: list[int]

    # skill order -TODO: implement later with timeline data when i want to expand on the project

@dataclass
class ChampionStats:
    # represents aggregated stats for a champion
    champion_name: str
    games_played: int
    wins: int
    losses: int
    total_kills: int
    total_deaths: int
    total_assists: int

    @property
    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return (self.wins / self.games_played) * 100
    
    @property
    def kda(self) -> float:
        if self.total_deaths == 0:
            return float(self.total_kills + self.total_assists)
        return (self.total_kills + self.total_assists) / self.total_deaths

@dataclass
class PlayerSummary:
    player: Player
    champion_stats: list[ChampionStats]
    total_games: int

    def sort_by(self, key: SortBy = SortBy.GAMES, reverse: bool = True, min_games: int = 1) -> list[ChampionStats]:

        # key: SortBy enum value (GAMES, WINRATE, KDA, NAME)
        # reverse: True for highest value and false for lowest value
        # min_games: minimum games to include the champion in the list

        filtered = [c for c in self.champion_stats if c.games_played >= min_games]

        key_map = {
            SortBy.GAMES: lambda x: x.games_played,
            SortBy.WINRATE: lambda x: x.win_rate,
            SortBy.KDA: lambda x: x.kda,
            SortBy.NAME: lambda x: x.champion_name,
            SortBy.CHAMPION_NAME: lambda x: x.champion_name,
        }

        key_func = key_map.get(key, lambda x: x.games_played)

        return sorted(filtered, key=key_func, reverse = reverse)

    

    
    