import sqlite3
from typing import Optional
from src.models import Player, Match, ChampionStats, PlayerSummary

class DatabaseManager:

    def __init__(self, db_path: str = "league_data.db"):

        self.conn = sqlite3.connect(db_path)

        # to access columns by name
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
        
        # Matches table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT PRIMARY KEY,
                puuid TEXT NOT NULL,
                champion TEXT NOT NULL,
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
                FOREIGN KEY (puuid) REFERENCES players(puuid)
            )
        ''')
        
        # Items table (one match can have multiple items)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_items (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                item_slot INTEGER NOT NULL,
                FOREIGN KEY (match_id, puuid) REFERENCES matches(match_id, puuid)
            )
        ''')
        
        # Runes table (one match can have multiple runes)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_runes (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                rune_id INTEGER NOT NULL,
                rune_slot INTEGER NOT NULL,
                FOREIGN KEY (match_id, puuid) REFERENCES matches(match_id, puuid)
            )
        ''')
        
        # Create indexes for faster queries
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_puuid ON matches(puuid)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_champion ON matches(champion)')
        
        self.conn.commit()
    
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
            return False
    
    def save_match(self, match: Match) -> bool:
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO matches 
                (match_id, puuid, champion, role, win, kills, deaths, 
                 assists, cs, game_duration, total_damage, vision_score, gold_earned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (match.match_id, match.puuid, match.champion, match.role,
                  int(match.win), match.kills, match.deaths, match.assists,
                  match.cs, match.game_duration, match.total_damage,
                  match.vision_score, match.gold_earned, match.summoner_spell_d, match.summoner_spell_f))
            
            # Save items if present
            if match.items:
                # Delete old items first (for REPLACE scenario)
                self.cursor.execute('DELETE FROM match_items WHERE match_id = ? AND puuid = ?', 
                                   (match.match_id, match.puuid))
                for slot, item_id in enumerate(match.items):
                    self.cursor.execute('''
                        INSERT INTO match_items (match_id, puuid, item_id, item_slot)
                        VALUES (?, ?, ?, ?)
                    ''', (match.match_id, match.puuid, item_id, slot))
            
            # Save runes if present
            if match.runes:
                # Delete old runes first (for REPLACE scenario)
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
            return False
    
    def get_player(self, puuid: str) -> Optional[Player]:
        """Get player by PUUID"""
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
        """Get recent matches for a player"""
        query = """
            SELECT * FROM matches 
            WHERE puuid = ? 
            ORDER BY rowid DESC 
            LIMIT ?
        """
        
        self.cursor.execute(query, (puuid, limit))
        rows = self.cursor.fetchall()
        
        matches = []
        for row in rows:
            # Get items for this match
            self.cursor.execute('''
                SELECT item_id FROM match_items 
                WHERE match_id = ? AND puuid = ?
                ORDER BY item_slot
            ''', (row["match_id"], row["puuid"]))
            items = [r["item_id"] for r in self.cursor.fetchall()]
            
            # Get runes for this match
            self.cursor.execute('''
                SELECT rune_id FROM match_runes 
                WHERE match_id = ? AND puuid = ?
                ORDER BY rune_slot
            ''', (row["match_id"], row["puuid"]))
            runes = [r["rune_id"] for r in self.cursor.fetchall()]
            
            match = Match(
                match_id=row["match_id"],
                puuid=row["puuid"],
                champion=row["champion"],
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
                runes=runes
            )
            matches.append(match)
        
        return matches
    
    def get_practice_summary(self, puuid: str) -> PlayerSummary:
        """Get aggregated champion stats for a player (all matches)"""
        self.cursor.execute('''
            SELECT 
                champion,
                COUNT(*) as games,
                SUM(win) as wins,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(assists) as total_assists
            FROM matches
            WHERE puuid = ?
            GROUP BY champion
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
                champion_name=row["champion"],
                games_played=games,
                wins=wins,
                losses=losses,
                total_kills=row["total_kills"],
                total_deaths=row["total_deaths"],
                total_assists=row["total_assists"]
            )
            champion_stats.append(stats)
            total_games += games
        
        # Get player info
        player = self.get_player(puuid)
        if not player:
            raise ValueError(f"Player with puuid {puuid} not found")
        
        return PlayerSummary(
            player=player,
            champion_stats=champion_stats,
            total_games=total_games
        )
    
    def player_exists(self, puuid: str) -> bool:
        """Check if a player exists in the database"""
        self.cursor.execute('SELECT 1 FROM players WHERE puuid = ? LIMIT 1', (puuid,))
        return self.cursor.fetchone() is not None
    
    def get_all_players(self) -> list[Player]:
        """Get all players in the database"""
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
        """Close the database connection"""
        self.conn.close()
