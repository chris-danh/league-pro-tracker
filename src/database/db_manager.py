# src/database/db_manager.py
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List
from src.models import Player, Match, Matchup, ChampionStats, PlayerSummary, ItemPurchase

class DatabaseManager:

    def __init__(self, db_path: str = "league_data.db"):
        self.db_path = db_path
        self._connect()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _ensure_connection(self):
        try:
            self.cursor.execute("SELECT 1")
        except (sqlite3.ProgrammingError, sqlite3.OperationalError, AttributeError):
            self._connect()


    def _create_tables(self):
        """Create all necessary tables if they don't exist"""
        
        # ============================================
        # 1. PLAYERS TABLE
        # ============================================
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
        
        # ============================================
        # 2. MATCHES TABLE
        # ============================================
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
        
        # ============================================
        # 3. PARTICIPANTS TABLE (UPDATED with runes and items)
        # ============================================
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                champion_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                role TEXT,
                win INTEGER NOT NULL,
                kills INTEGER NOT NULL,
                deaths INTEGER NOT NULL,
                assists INTEGER NOT NULL,
                cs INTEGER NOT NULL,
                gold_earned INTEGER NOT NULL,
                total_damage INTEGER NOT NULL,
                vision_score INTEGER NOT NULL,
                summoner_spell_d INTEGER NOT NULL,
                summoner_spell_f INTEGER NOT NULL,
                keystone_rune_id INTEGER,
                secondary_rune_style_id INTEGER,
                item_0 INTEGER,
                item_1 INTEGER,
                item_2 INTEGER,
                item_3 INTEGER,
                item_4 INTEGER,
                item_5 INTEGER,
                item_6 INTEGER,
                FOREIGN KEY (match_id) REFERENCES matches(match_id)
            )
        ''')
        
        # ============================================
        # 4. MATCH ITEMS TABLE (Pro player only - detailed)
        # ============================================
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_items (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                item_slot INTEGER NOT NULL,
                FOREIGN KEY (match_id, puuid) REFERENCES matches(match_id, puuid)
            )
        ''')
        
        # ============================================
        # 5. MATCH RUNES TABLE (Pro player only - detailed)
        # ============================================
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_runes (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                rune_id INTEGER NOT NULL,
                rune_slot INTEGER NOT NULL,
                FOREIGN KEY (match_id, puuid) REFERENCES matches(match_id, puuid)
            )
        ''')
        
        # ============================================
        # 6. MATCHUPS TABLE
        # ============================================
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
        
        # ============================================
        # INDEXES FOR PERFORMANCE
        # ============================================
        
        # Matches indexes
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_puuid ON matches(puuid)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_champion_id ON matches(champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_patch ON matches(patch)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_game_creation ON matches(game_creation)')
        
        # Participants indexes
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_participants_match_id ON participants(match_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_participants_puuid ON participants(puuid)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_participants_champion_id ON participants(champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_participants_keystone ON participants(keystone_rune_id)')
        
        # Matchups indexes
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchups_ally ON matchups(ally_champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchups_enemy ON matchups(enemy_champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchups_patch ON matchups(patch)')
        
        self.conn.commit()
        print("✅ Database tables created successfully")

    def save_player(self, player: Player) -> bool:
        try:
            self._ensure_connection()
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
            self._ensure_connection()
            
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
             patch, game_creation, 
             skill_order, skill_order_levels, item_purchases)
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
            
            # Save items if present
            if match.items:
                self.cursor.execute('DELETE FROM match_items WHERE match_id = ? AND puuid = ?', 
                                   (match.match_id, match.puuid))
                for slot, item_id in enumerate(match.items):
                    self.cursor.execute('''
                        INSERT INTO match_items (match_id, puuid, item_id, item_slot)
                        VALUES (?, ?, ?, ?)
                    ''', (match.match_id, match.puuid, item_id, slot))
            
            # Save runes if present
            if match.runes:
                self.cursor.execute('DELETE FROM match_runes WHERE match_id = ? AND puuid = ?',
                                   (match.match_id, match.puuid))
                for slot, rune_id in enumerate(match.runes):
                    self.cursor.execute('''
                        INSERT INTO match_runes (match_id, puuid, rune_id, rune_slot)
                        VALUES (?, ?, ?, ?)
                    ''', (match.match_id, match.puuid, rune_id, slot))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving match: {e}")
            return False

    def save_matchup(self, matchup: Matchup) -> bool:
        try:
            self._ensure_connection()
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
        self._ensure_connection()
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

    def get_player_matches(self, puuid: str, limit: int = 50, offset: int = 0) -> list[Match]:
        """Get recent matches for a player with pagination"""
        self._ensure_connection()
        
        query = """
            SELECT * FROM matches 
            WHERE puuid = ? 
            ORDER BY game_creation DESC, rowid DESC
            LIMIT ? OFFSET ?
        """
        
        self.cursor.execute(query, (puuid, limit, offset))
        rows = self.cursor.fetchall()
        
        return self._rows_to_matches(rows)

    def get_player_recent_matches(self, puuid: str, limit: int = 20) -> list[Match]:
        """Get recent matches for a player (without role filter)"""
        self._ensure_connection()
        
        query = """
            SELECT * FROM matches 
            WHERE puuid = ? 
            ORDER BY game_creation DESC
            LIMIT ?
        """
        
        self.cursor.execute(query, (puuid, limit))
        rows = self.cursor.fetchall()
        
        return self._rows_to_matches(rows)

    def _rows_to_matches(self, rows) -> list[Match]:
        """Convert database rows to Match objects"""
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
        self._ensure_connection()
        
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
        self._ensure_connection()
        self.cursor.execute('SELECT 1 FROM players WHERE puuid = ? LIMIT 1', (puuid,))
        return self.cursor.fetchone() is not None

    def match_exists(self, match_id: str) -> bool:
        """Check if a match already exists in the database."""
        self._ensure_connection()
        self.cursor.execute("SELECT 1 FROM matches WHERE match_id = ? LIMIT 1", (match_id,))
        return self.cursor.fetchone() is not None

    def get_all_players(self) -> list[Player]:
        self._ensure_connection()
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

    def get_last_refresh_time(self, puuid: str) -> Optional[datetime]:
        """Get the last time a player's data was refreshed."""
        self._ensure_connection()
        self.cursor.execute(
            "SELECT MAX(game_creation) as last_refresh FROM matches WHERE puuid = ?",
            (puuid,)
        )
        row = self.cursor.fetchone()
        if row and row["last_refresh"]:
            return datetime.fromtimestamp(row["last_refresh"] / 1000)
        return None

    def delete_old_matches(self, days_to_keep: int = 31):
        """
        Delete matches older than the specified number of days.
        
        Args:
            days_to_keep: Number of days of data to keep (default 31)
        """
        self._ensure_connection()
        
        cutoff_timestamp = int((datetime.now() - timedelta(days=days_to_keep)).timestamp() * 1000)
        
        # Get match IDs to delete
        self.cursor.execute(
            "SELECT match_id FROM matches WHERE game_creation < ?",
            (cutoff_timestamp,)
        )
        match_ids = [row["match_id"] for row in self.cursor.fetchall()]
        
        if not match_ids:
            print(f"✅ No matches older than {days_to_keep} days to delete")
            return
        
        # Delete from matchups first (foreign key)
        placeholders = ','.join('?' * len(match_ids))
        self.cursor.execute(
            f"DELETE FROM matchups WHERE match_id IN ({placeholders})",
            match_ids
        )
        
        # Delete from match_items
        self.cursor.execute(
            f"DELETE FROM match_items WHERE match_id IN ({placeholders})",
            match_ids
        )
        
        # Delete from match_runes
        self.cursor.execute(
            f"DELETE FROM match_runes WHERE match_id IN ({placeholders})",
            match_ids
        )
        
        # Delete from matches
        self.cursor.execute(
            f"DELETE FROM matches WHERE match_id IN ({placeholders})",
            match_ids
        )
        
        self.conn.commit()
        print(f"🗑️ Deleted {len(match_ids)} matches older than {days_to_keep} days")

    def save_matches_batch(self, matches: list[Match], matchups: list[Matchup]) -> tuple[int, int]:
        """
        Save multiple matches and matchups, skipping duplicates.
        
        Returns:
            tuple: (saved_matches_count, saved_matchups_count)
        """
        self._ensure_connection()
        
        saved_matches = 0
        saved_matchups = 0
        
        for match in matches:
            if not self.match_exists(match.match_id):
                if self.save_match(match):
                    saved_matches += 1
        
        for matchup in matchups:
            # Check if this matchup already exists (by match_id)
            self.cursor.execute(
                "SELECT 1 FROM matchups WHERE match_id = ? LIMIT 1",
                (matchup.match_id,)
            )
            if not self.cursor.fetchone():
                if self.save_matchup(matchup):
                    saved_matchups += 1
        
        self.conn.commit()
        return saved_matches, saved_matchups

    # src/database/db_manager.py

    def save_participants_batch(self, match_id: str, participants: list[dict]) -> bool:
        """
        Save all participants for a match with runes and items.
        
        Args:
            match_id: The match ID  
            participants: List of participant dictionaries with fields:
                - puuid, champion_id, team_id, role, win
                - kills, deaths, assists, cs
                - gold_earned, total_damage, vision_score
                - summoner_spell_d, summoner_spell_f
                - keystone_rune_id, primary_rune_style_id, secondary_rune_style_id
                - item_0 through item_6
        """
        try:
            self._ensure_connection()
            
            # Delete existing participants for this match (for REPLACE scenario)
            self.cursor.execute('DELETE FROM participants WHERE match_id = ?', (match_id,))
            
            for p in participants:
                self.cursor.execute('''
                    INSERT INTO participants (
                        match_id, puuid, champion_id, team_id, role, win,
                        kills, deaths, assists, cs, gold_earned, total_damage,
                        vision_score, summoner_spell_d, summoner_spell_f,
                        keystone_rune_id, secondary_rune_style_id,
                        item_0, item_1, item_2, item_3, item_4, item_5, item_6
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id,
                    p['puuid'],
                    p['champion_id'],
                    p['team_id'],
                    p['role'],
                    int(p['win']),
                    p['kills'],
                    p['deaths'],
                    p['assists'],
                    p['cs'],
                    p['gold_earned'],
                    p['total_damage'],
                    p['vision_score'],
                    p['summoner_spell_d'],
                    p['summoner_spell_f'],
                    p.get('keystone_rune_id'),
                    p.get('secondary_rune_style_id'),
                    p.get('item_0', 0),
                    p.get('item_1', 0),
                    p.get('item_2', 0),
                    p.get('item_3', 0),
                    p.get('item_4', 0),
                    p.get('item_5', 0),
                    p.get('item_6', 0)
                ))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving participants for match {match_id}: {e}")
            return False

    def close(self):
        """Close the database connection."""
        try:
            self.conn.close()
        except:
            pass