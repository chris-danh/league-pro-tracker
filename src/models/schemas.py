from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class SortBy(Enum):
    GAMES = "games"
    WINRATE = "winrate"
    KDA = "kda"
    NAME = "name"

    def __str__(self):
        return self.value

@dataclass
class Player:
    # this class represents a player

    # puuid is the API-key specific id for the account
    puuid: str

    # information for the riot api to fetch the account
    game_name: str
    tag_line: str
    region: str

    # optional tags for team and role
    team: Optional[str] = None
    role: Optional[str] = None

@dataclass
class Matchup:
    ally_champion_id: int
    enemy_champion_id: int
    role: str
    win: bool
    match_id: str
    patch: str

@dataclass
class ItemPurchase:
    # represents when and what item was purchased in a match
    item_id: int
    timestamp: int

@dataclass
class Match:
    # this class represents a single match

    # general stats
    match_id: str
    puuid: str
    champion_id: int
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
    patch: str
    game_creation: int

    # build and runes
    items: list[int]
    runes: list[int]
    summoner_spell_d: int
    summoner_spell_f: int

    
    # skill order
    skill_order: str
    skill_order_levels: list[int]

    # item build order
    item_purchases: list[ItemPurchase]



@dataclass
class ChampionStats:
    # represents aggregated stats for a champion
    champion_id: int
    games_played: int
    wins: int
    losses: int
    total_kills: int
    total_deaths: int
    total_assists: int

    item_counts: dict[int, int] = field(default_factory=dict)

    item_win_counts: dict[int, int] = field(default_factory=dict)

    rune_counts: dict[int, int] = field(default_factory=dict)

    rune_win_counts: dict[int, int] = field(default_factory=dict)

    spell_d_counts: dict[int, int] = field(default_factory=dict)

    spell_f_counts: dict[int, int] = field(default_factory=dict)

    spell_combos: dict[tuple[int,int], int] = field(default_factory=dict)
    skill_order_counts: dict[str, int] = field(default_factory=dict)

    match_ids: list[str] = field(default_factory=list)
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
    
    def get_top_items(self, n: int = 5) -> list[tuple[int, int, float]]:
        """
        Get top N items by usage with win rate.
        
        Returns:
            List of (item_id, count, win_rate)
        """
        results = []
        for item_id, count in sorted(self.item_counts.items(), key=lambda x: x[1], reverse=True)[:n]:
            wins = self.item_win_counts.get(item_id, 0)
            win_rate = (wins / count * 100) if count > 0 else 0
            results.append((item_id, count, win_rate))
        return results
    
    def get_top_runes(self, n: int = 5) -> list[tuple[int, int, float]]:
        """
        Get top N runes by usage with win rate.
        
        Returns:
            List of (rune_id, count, win_rate)
        """
        results = []
        for rune_id, count in sorted(self.rune_counts.items(), key=lambda x: x[1], reverse=True)[:n]:
            wins = self.rune_win_counts.get(rune_id, 0)
            win_rate = (wins / count * 100) if count > 0 else 0
            results.append((rune_id, count, win_rate))
        return results
    
    def get_top_spell_combos(self, n: int = 3) -> list[tuple[tuple[int, int], int, float]]:
        """
        Get top N summoner spell combos by usage with win rate.
        
        Returns:
            List of ((spell_d, spell_f), count, win_rate)
        """
        results = []
        for combo, count in sorted(self.spell_combos.items(), key=lambda x: x[1], reverse=True)[:n]:
            # TODO: Calculate win rate for each combo from match data
            results.append((combo, count, 0.0))
        return results

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
            SortBy.NAME: lambda x: str(x.champion_id),
        }

        key_func = key_map.get(key, lambda x: x.games_played)

        return sorted(filtered, key=key_func, reverse = reverse)

    

    
    