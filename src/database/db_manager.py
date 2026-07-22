# src/database/db_manager.py
import sqlite3
import json
from typing import Optional, List
from src.models import Player, Match, Matchup, ChampionStats, PlayerSummary, ItemPurchase


class DatabaseManager:

    def __init__(self, db_path: str = "league_data.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Create all necessary tables if they don't exist"""
        # Players table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                puuid TEXT PRIMARY KEY,
                game_name TEXT NOT NULL,
                tag_line TEXT NOT NULL,
                region TEXT NOT NULL,
                team TEXT,
                role TEXT
            )
        ''')
        
        # Matches table - UPDATED with new columns
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT PRIMARY KEY,
                puuid TEXT NOT NULL,
                champion_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                win INTEGER NOT NULL,
                kills INTEGER NOT NULL,
                deaths INTEGER NOT NULL,
                assists INTEGER NOT NULL,
                cs INTEGER NOT NULL,
                game_duration INTEGER NOT NULL,
                total_damage INTEGER NOT NULL,
                vision_score INTEGER NOT NULL,
                gold_earned INTEGER NOT NULL,
                summoner_spell_d INTEGER NOT NULL,
                summoner_spell_f INTEGER NOT NULL,
                patch TEXT,
                game_creation INTEGER,
                skill_order TEXT,
                skill_order_levels TEXT,
                item_purchases TEXT,
                FOREIGN KEY (puuid) REFERENCES players(puuid)
            )
        ''')
        
        # Items table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_items (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                item_slot INTEGER NOT NULL,
                FOREIGN KEY (match_id, puuid) REFERENCES matches(match_id, puuid)
            )
        ''')
        
        # Runes table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_runes (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                rune_id INTEGER NOT NULL,
                rune_slot INTEGER NOT NULL,
                FOREIGN KEY (match_id, puuid) REFERENCES matches(match_id, puuid)
            )
        ''')
        
        # Matchups table - NEW
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS matchups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                ally_champion_id INTEGER NOT NULL,
                enemy_champion_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                win INTEGER NOT NULL,
                patch TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(match_id)
            )
        ''')
        
        # Create indexes
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_puuid ON matches(puuid)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_champion_id ON matches(champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_patch ON matches(patch)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchups_ally ON matchups(ally_champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchups_enemy ON matchups(enemy_champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchups_patch ON matchups(patch)')
        
        self.conn.commit()
        print("✅ Database tables created successfully")

    def save_player(self, player: Player) -> bool:
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO players 
                (puuid, game_name, tag_line, region, team, role)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (player.puuid, player.game_name, player.tag_line, 
                  player.region, player.team, player.role))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving player: {e}")
            return False

    def save_match(self, match: Match) -> bool:
        try:
            # Convert lists to JSON strings
            skill_order_levels_json = json.dumps(match.skill_order_levels) if match.skill_order_levels else None
            
            item_purchases_json = None
           
            
            if match.item_purchases:
                item_purchases_json = json.dumps([
                    {"item_id": p.item_id, "timestamp": p.timestamp}
                    for p in match.item_purchases
                ])
        
            self.cursor.execute('''
                INSERT OR REPLACE INTO matches 
                (match_id, puuid, champion_id, role, win, kills, deaths, 
                assists, cs, game_duration, total_damage, vision_score, 
                gold_earned, summoner_spell_d, summoner_spell_f,
                patch, game_creation, skill_order, skill_order_levels, item_purchases)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                match.match_id, match.puuid, match.champion_id, match.role,
                int(match.win), match.kills, match.deaths, match.assists,
                match.cs, match.game_duration, match.total_damage,
                match.vision_score, match.gold_earned,
                match.summoner_spell_d, match.summoner_spell_f,
                match.patch, match.game_creation,
                match.skill_order, skill_order_levels_json, item_purchases_json
            ))
            
           
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving match: {e}")
            return False

    def save_matchup(self, matchup: Matchup) -> bool:
        """Save a champion matchup to the database."""
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO matchups 
                (match_id, ally_champion_id, enemy_champion_id, role, win, patch)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                matchup.match_id,
                matchup.ally_champion_id,
                matchup.enemy_champion_id,
                matchup.role,
                int(matchup.win),
                matchup.patch
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving matchup: {e}")
            return False

    def get_player(self, puuid: str) -> Optional[Player]:
        self.cursor.execute('''
            SELECT puuid, game_name, tag_line, region, team, role
            FROM players WHERE puuid = ?
        ''', (puuid,))
        
        row = self.cursor.fetchone()
        if row:
            return Player(
                puuid=row["puuid"],
                game_name=row["game_name"],
                tag_line=row["tag_line"],
                region=row["region"],
                team=row["team"],
                role=row["role"]
            )
        return None

    def get_player_matches(self, puuid: str, limit: int = 50) -> list[Match]:
        query = """
            SELECT * FROM matches 
            WHERE puuid = ? 
            ORDER BY game_creation DESC, rowid DESC
            LIMIT ?
        """
        
        self.cursor.execute(query, (puuid, limit))
        rows = self.cursor.fetchall()
        
        matches = []
        for row in rows:
            # Get items
            self.cursor.execute('''
                SELECT item_id FROM match_items 
                WHERE match_id = ? AND puuid = ?
                ORDER BY item_slot
            ''', (row["match_id"], row["puuid"]))
            items = [r["item_id"] for r in self.cursor.fetchall()]
            
            # Get runes
            self.cursor.execute('''
                SELECT rune_id FROM match_runes 
                WHERE match_id = ? AND puuid = ?
                ORDER BY rune_slot
            ''', (row["match_id"], row["puuid"]))
            runes = [r["rune_id"] for r in self.cursor.fetchall()]
            
            # Parse JSON fields
            skill_order_levels = json.loads(row["skill_order_levels"]) if row["skill_order_levels"] else None
            
            item_purchases = None
            if row["item_purchases"]:
                try:
                    purchases_data = json.loads(row["item_purchases"])
                    item_purchases = [
                        ItemPurchase(item_id=p["item_id"], timestamp=p["timestamp"])
                        for p in purchases_data
                    ]
                except:
                    item_purchases = None
            
            match = Match(
                match_id=row["match_id"],
                puuid=row["puuid"],
                champion_id=row["champion_id"],
                role=row["role"],
                win=bool(row["win"]),
                kills=row["kills"],
                deaths=row["deaths"],
                assists=row["assists"],
                cs=row["cs"],
                game_duration=row["game_duration"],
                total_damage=row["total_damage"],
                vision_score=row["vision_score"],
                gold_earned=row["gold_earned"],
                items=items,
                runes=runes,
                summoner_spell_d=row["summoner_spell_d"],
                summoner_spell_f=row["summoner_spell_f"],
                patch=row["patch"],
                game_creation=row["game_creation"],
                skill_order=row["skill_order"],
                skill_order_levels=skill_order_levels,
                item_purchases=item_purchases
            )
            matches.append(match)
        
        return matches

    def get_practice_summary(self, puuid: str) -> PlayerSummary:
        """Get aggregated champion stats for a player (all matches)"""
        self.cursor.execute('''
            SELECT 
                champion_id,
                COUNT(*) as games,
                SUM(win) as wins,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(assists) as total_assists
            FROM matches
            WHERE puuid = ?
            GROUP BY champion_id
            ORDER BY games DESC
        ''', (puuid,))
        
        rows = self.cursor.fetchall()
        
        champion_stats = []
        total_games = 0
        
        for row in rows:
            games = row["games"]
            wins = row["wins"]
            losses = games - wins
            
            stats = ChampionStats(
                champion_id=row["champion_id"],
                games_played=games,
                wins=wins,
                losses=losses,
                total_kills=row["total_kills"],
                total_deaths=row["total_deaths"],
                total_assists=row["total_assists"]
            )
            champion_stats.append(stats)
            total_games += games
        
        player = self.get_player(puuid)
        if not player:
            raise ValueError(f"Player with puuid {puuid} not found")
        
        return PlayerSummary(
            player=player,
            champion_stats=champion_stats,
            total_games=total_games
        )

    def player_exists(self, puuid: str) -> bool:
        self.cursor.execute('SELECT 1 FROM players WHERE puuid = ? LIMIT 1', (puuid,))
        return self.cursor.fetchone() is not None

    def get_all_players(self) -> list[Player]:
        self.cursor.execute('SELECT puuid, game_name, tag_line, region, team, role FROM players')
        rows = self.cursor.fetchall()
        
        return [
            Player(
                puuid=row["puuid"],
                game_name=row["game_name"],
                tag_line=row["tag_line"],
                region=row["region"],
                team=row["team"],
                role=row["role"]
            )
            for row in rows
        ]

    def close(self):
        self.conn.close()