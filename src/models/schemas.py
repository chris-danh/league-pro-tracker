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
    puuid: str
    game_name: str
    tag_line: str
    region: str
    team: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None


@dataclass
class Matchup:
    puuid: str
    ally_champion_id: int
    enemy_champion_id: int
    role: str
    win: bool
    match_id: str
    patch: str


@dataclass
class ItemPurchase:
    item_id: int
    timestamp: int
    is_core: bool = False
    core_order: Optional[int] = None
    sold_timestamp: Optional[int] = None


@dataclass
class Match:
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

    items: list[int]
    runes: list[int]
    summoner_spell_d: int
    summoner_spell_f: int

    skill_order: str
    item_purchases: list[ItemPurchase]

    rune_page: Optional[dict] = None


@dataclass
class ChampionStats:
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
    spell_combos: dict[tuple[int, int], int] = field(default_factory=dict)
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
        results = []
        for item_id, count in sorted(self.item_counts.items(), key=lambda x: x[1], reverse=True)[:n]:
            wins = self.item_win_counts.get(item_id, 0)
            win_rate = (wins / count * 100) if count > 0 else 0
            results.append((item_id, count, win_rate))
        return results

    def get_top_runes(self, n: int = 5) -> list[tuple[int, int, float]]:
        results = []
        for rune_id, count in sorted(self.rune_counts.items(), key=lambda x: x[1], reverse=True)[:n]:
            wins = self.rune_win_counts.get(rune_id, 0)
            win_rate = (wins / count * 100) if count > 0 else 0
            results.append((rune_id, count, win_rate))
        return results

    def get_top_spell_combos(self, n: int = 3) -> list[tuple[tuple[int, int], int, float]]:
        results = []
        for combo, count in sorted(self.spell_combos.items(), key=lambda x: x[1], reverse=True)[:n]:
            results.append((combo, count, 0.0))
        return results


@dataclass
class PlayerSummary:
    player: Player
    champion_stats: list[ChampionStats]
    total_games: int

    def sort_by(self, key: SortBy = SortBy.GAMES, reverse: bool = True, min_games: int = 1) -> list[ChampionStats]:
        filtered = [c for c in self.champion_stats if c.games_played >= min_games]

        key_map = {
            SortBy.GAMES: lambda x: x.games_played,
            SortBy.WINRATE: lambda x: x.win_rate,
            SortBy.KDA: lambda x: x.kda,
            SortBy.NAME: lambda x: str(x.champion_id),
        }

        key_func = key_map.get(key, lambda x: x.games_played)
        return sorted(filtered, key=key_func, reverse=reverse)