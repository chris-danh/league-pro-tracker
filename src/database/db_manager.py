# src/database/db_manager.py
"""
SQLite persistence layer for the League Pro Tracker.

Owns the full schema and provides CRUD operations for players, matches,
participants, matchups, and the per-match detail tables (items, runes).

Key design choices:
  - `matches` is keyed by (match_id, puuid), not match_id alone, so the
    same game can be attached to multiple tracked pros (e.g. Zeus vs Kiin).
  - `participants` stores all 10 players in every saved game, keyed only
    by match_id. It is a shared table, not scoped per tracked player.
  - `matchups` is scoped by (match_id, puuid) so each tracked player has
    their own directional matchup rows.
  - `item_purchases` and `rune_page` are serialized to JSON on the
    `matches` row instead of living in separate tables, because they are
    always read together and never queried individually.
  - Each DatabaseManager instance opens its own connection. Callers are
    responsible for calling close() when done, though methods reconnect
    automatically if the connection was closed.
"""

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
        """Open a new connection and initialize the schema if needed."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _ensure_connection(self):
        """
        Reconnect if the underlying connection was closed.

        Every public method calls this first, so it's safe to reuse a
        DatabaseManager instance across long-lived processes even if the
        connection was closed by SQLite (e.g. timeout, or after close()).
        """
        try:
            self.cursor.execute("SELECT 1")
        except (sqlite3.ProgrammingError, sqlite3.OperationalError, AttributeError):
            self._connect()

    def _create_tables(self):
        """
        Create all tables and indexes if they don't already exist.

        Called on every connection, so it's idempotent. All CREATE TABLE
        statements use IF NOT EXISTS, and all indexes use IF NOT EXISTS.

        Schema notes:
          - `matches` uses a composite (match_id, puuid) primary key so two
            tracked pros in the same game each get their own row.
          - `participants` is keyed only by match_id — all 10 players in a
            game live in the same rows, and the same row set is shared
            across tracked pros.
          - `item_purchases` and `rune_page` are TEXT columns holding JSON.
            They are read as a unit and never filtered at the SQL level, so
            normalization would only add join overhead.
        """
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                puuid TEXT PRIMARY KEY,
                game_name TEXT NOT NULL,
                tag_line TEXT NOT NULL,
                region TEXT NOT NULL,
                team TEXT,
                display_name TEXT,
                role TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT NOT NULL,
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
                item_purchases TEXT,
                rune_page TEXT,
                PRIMARY KEY (match_id, puuid),
                FOREIGN KEY (puuid) REFERENCES players(puuid)
            )
        ''')

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
                role_bound_item INTEGER,
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

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_items (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                item_slot INTEGER NOT NULL,
                PRIMARY KEY (match_id, puuid, item_slot)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_runes (
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                rune_id INTEGER NOT NULL,
                rune_slot TEXT NOT NULL,
                PRIMARY KEY (match_id, puuid, rune_slot)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS matchups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT NOT NULL,
                puuid TEXT NOT NULL,
                ally_champion_id INTEGER NOT NULL,
                enemy_champion_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                win INTEGER NOT NULL,
                patch TEXT,
                UNIQUE (match_id, puuid, ally_champion_id, enemy_champion_id)
            )
        ''')

        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_puuid ON matches(puuid)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_champion_id ON matches(champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_patch ON matches(patch)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_game_creation ON matches(game_creation)')

        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_participants_match_id ON participants(match_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_participants_puuid ON participants(puuid)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_participants_champion_id ON participants(champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_participants_keystone ON participants(keystone_rune_id)')

        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchups_puuid ON matchups(puuid)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchups_ally ON matchups(ally_champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchups_enemy ON matchups(enemy_champion_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchups_patch ON matchups(patch)')

        self.conn.commit()
        print("✅ Database tables created successfully")

    # ============================================
    # PLAYERS
    # ============================================

    def save_player(self, player: Player) -> bool:
        """
        Insert or replace a player row.

        Uses the puuid as the primary key, so re-saving an existing player
        updates their metadata (team, display_name, role) in place.
        """
        try:
            self._ensure_connection()
            self.cursor.execute('''
                INSERT OR REPLACE INTO players 
                (puuid, game_name, tag_line, region, team, display_name, role)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (player.puuid, player.game_name, player.tag_line,
                  player.region, player.team, player.display_name, player.role))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving player: {e}")
            return False

    def get_player(self, puuid: str) -> Optional[Player]:
        """Fetch a single player by PUUID, or None if not found."""
        self._ensure_connection()
        self.cursor.execute('''
            SELECT puuid, game_name, tag_line, region, team, display_name, role
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
                display_name=row["display_name"],
                role=row["role"]
            )
        return None

    def get_all_players(self) -> list[Player]:
        """Fetch every tracked player."""
        self._ensure_connection()
        self.cursor.execute(
            'SELECT puuid, game_name, tag_line, region, team, display_name, role FROM players'
        )
        rows = self.cursor.fetchall()
        return [
            Player(
                puuid=row["puuid"],
                game_name=row["game_name"],
                tag_line=row["tag_line"],
                region=row["region"],
                team=row["team"],
                display_name=row["display_name"],
                role=row["role"]
            )
            for row in rows
        ]

    def player_exists(self, puuid: str) -> bool:
        """Check whether a player with this PUUID has been saved."""
        self._ensure_connection()
        self.cursor.execute('SELECT 1 FROM players WHERE puuid = ? LIMIT 1', (puuid,))
        return self.cursor.fetchone() is not None

    # ============================================
    # MATCHES
    # ============================================

    def save_match(self, match: Match) -> bool:
        """
        Persist a Match row, plus its items and runes, in a single transaction.

        Item purchases and the structured rune page are serialized as JSON
        on the `matches` row rather than stored in side tables.

        Runes are written to `match_runes` with semantic slot names:
          - `tree_0` .. `tree_N` for the primary + secondary tree runes,
            in the order Riot returns them.
          - `shard_offense`, `shard_flex`, `shard_defense` for the three
            stat shards. These are always the last 3 entries in the runes
            list, so they're assigned by position.

        Downstream queries in `app.py` rely on the `tree_%` / `shard_%`
        prefix distinction, so don't rename these slots.
        """
        try:
            self._ensure_connection()

            item_purchases_json = None
            if match.item_purchases:
                item_purchases_json = json.dumps([
                    {
                        "item_id": p.item_id,
                        "timestamp": p.timestamp,
                        "is_core": p.is_core,
                        "core_order": p.core_order,
                        "sold_timestamp": p.sold_timestamp,
                    }
                    for p in match.item_purchases
                ])

            rune_page_json = None
            if match.rune_page:
                rune_page_json = json.dumps(match.rune_page, sort_keys=True)

            self.cursor.execute('''
                INSERT OR REPLACE INTO matches 
                (match_id, puuid, champion_id, role, win, kills, deaths, 
                assists, cs, game_duration, total_damage, vision_score, 
                gold_earned, summoner_spell_d, summoner_spell_f,
                patch, game_creation, 
                skill_order, item_purchases, rune_page)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                match.match_id, match.puuid, match.champion_id, match.role,
                int(match.win), match.kills, match.deaths, match.assists,
                match.cs, match.game_duration, match.total_damage,
                match.vision_score, match.gold_earned,
                match.summoner_spell_d, match.summoner_spell_f,
                match.patch, match.game_creation,
                match.skill_order, item_purchases_json, rune_page_json
            ))

            # Items: wipe and reinsert for this (match, player) pair
            if match.items:
                self.cursor.execute(
                    'DELETE FROM match_items WHERE match_id = ? AND puuid = ?',
                    (match.match_id, match.puuid)
                )
                for slot, item_id in enumerate(match.items):
                    self.cursor.execute('''
                        INSERT INTO match_items (match_id, puuid, item_id, item_slot)
                        VALUES (?, ?, ?, ?)
                    ''', (match.match_id, match.puuid, item_id, slot))

            # Runes: same wipe-and-reinsert, with semantic slot names
            if match.runes:
                self.cursor.execute(
                    'DELETE FROM match_runes WHERE match_id = ? AND puuid = ?',
                    (match.match_id, match.puuid)
                )

                num_runes = len(match.runes)
                shard_start = max(0, num_runes - 3)
                shard_names = ['shard_offense', 'shard_flex', 'shard_defense']

                for slot, rune_id in enumerate(match.runes):
                    if slot >= shard_start:
                        slot_name = shard_names[slot - shard_start]
                    else:
                        slot_name = f'tree_{slot}'

                    self.cursor.execute('''
                        INSERT INTO match_runes (match_id, puuid, rune_id, rune_slot)
                        VALUES (?, ?, ?, ?)
                    ''', (match.match_id, match.puuid, rune_id, slot_name))

            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving match: {e}")
            return False

    def get_player_matches(self, puuid: str, limit: int = 50, offset: int = 0) -> list[Match]:
        """Fetch a paginated list of matches for a player, newest first."""
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
        """Fetch the N most recent matches for a player."""
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
        """
        Convert raw sqlite3.Row objects into Match dataclasses.

        For each row, fetches the associated items and runes from their side
        tables and deserializes the JSON columns (item_purchases, rune_page).
        Missing or malformed JSON is treated as None rather than raising —
        this keeps old rows with partial data readable.
        """
        matches = []
        for row in rows:
            self.cursor.execute('''
                SELECT item_id FROM match_items 
                WHERE match_id = ? AND puuid = ?
                ORDER BY item_slot
            ''', (row["match_id"], row["puuid"]))
            items = [r["item_id"] for r in self.cursor.fetchall()]

            self.cursor.execute('''
                SELECT rune_id FROM match_runes 
                WHERE match_id = ? AND puuid = ?
                ORDER BY 
                    CASE 
                        WHEN rune_slot LIKE 'tree_%' THEN 0 
                        ELSE 1 
                    END,
                    rune_slot
            ''', (row["match_id"], row["puuid"]))
            runes = [r["rune_id"] for r in self.cursor.fetchall()]

            item_purchases = None
            if row["item_purchases"]:
                try:
                    purchases_data = json.loads(row["item_purchases"])
                    item_purchases = [
                        ItemPurchase(
                            item_id=p["item_id"],
                            timestamp=p["timestamp"],
                            is_core=p.get("is_core", False),
                            core_order=p.get("core_order", None),
                            sold_timestamp=p.get("sold_timestamp", None),
                        )
                        for p in purchases_data
                    ]
                except Exception:
                    item_purchases = None

            rune_page = None
            try:
                if row["rune_page"]:
                    rune_page = json.loads(row["rune_page"])
            except (IndexError, KeyError):
                rune_page = None

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
                item_purchases=item_purchases,
                rune_page=rune_page,
            )
            matches.append(match)

        return matches

    def match_exists(self, match_id: str, puuid: str = None) -> bool:
        """
        Check whether a match has been saved.

        If `puuid` is provided, checks the composite (match_id, puuid) key —
        useful when checking whether a specific player's row exists.

        If `puuid` is omitted, checks for any row with this match_id — useful
        when checking whether the match has been saved for anyone at all
        (e.g. deciding whether participants need to be saved).
        """
        self._ensure_connection()
        if puuid:
            self.cursor.execute(
                "SELECT 1 FROM matches WHERE match_id = ? AND puuid = ? LIMIT 1",
                (match_id, puuid)
            )
        else:
            self.cursor.execute(
                "SELECT 1 FROM matches WHERE match_id = ? LIMIT 1",
                (match_id,)
            )
        return self.cursor.fetchone() is not None

    def save_matches_batch(self, matches: list[Match], matchups: list[Matchup]) -> tuple[int, int]:
        """
        Save a batch of matches and matchups, skipping ones that already exist.

        The existence check is per (match_id, puuid) for matches and per
        (match_id, puuid, ally, enemy) for matchups. This lets the collector
        be called repeatedly without duplicating rows or re-writing data
        that hasn't changed.

        Returns (saved_matches, saved_matchups) — counts of newly-inserted
        rows, not counts of inputs.
        """
        self._ensure_connection()
        saved_matches = 0
        saved_matchups = 0

        for match in matches:
            if not self.match_exists(match.match_id, match.puuid):
                if self.save_match(match):
                    saved_matches += 1

        for matchup in matchups:
            self.cursor.execute(
                "SELECT 1 FROM matchups WHERE match_id = ? AND puuid = ? AND ally_champion_id = ? AND enemy_champion_id = ? LIMIT 1",
                (matchup.match_id, matchup.puuid, matchup.ally_champion_id, matchup.enemy_champion_id)
            )
            if not self.cursor.fetchone():
                if self.save_matchup(matchup):
                    saved_matchups += 1

        self.conn.commit()
        return saved_matches, saved_matchups

    def delete_old_matches(self, days_to_keep: int = 31):
        """
        Delete all matches older than `days_to_keep` days, and everything
        that cascades from them.

        Deletion is manual (not via SQLite FOREIGN KEY ... ON DELETE CASCADE)
        because the schema doesn't declare cascade rules — this method
        deletes from matchups, match_items, match_runes, participants, and
        matches in that order.

        Match IDs are collected once, then fanned out to each table. This is
        deliberately distinct-by-match-id rather than distinct-by-row, so
        two tracked pros in the same game both get cleaned up together.
        """
        self._ensure_connection()
        cutoff_timestamp = int((datetime.now() - timedelta(days=days_to_keep)).timestamp() * 1000)

        self.cursor.execute(
            "SELECT DISTINCT match_id FROM matches WHERE game_creation < ?",
            (cutoff_timestamp,)
        )
        match_ids = [row["match_id"] for row in self.cursor.fetchall()]

        if not match_ids:
            print(f"✅ No matches older than {days_to_keep} days to delete")
            return

        placeholders = ','.join('?' * len(match_ids))
        self.cursor.execute(f"DELETE FROM matchups WHERE match_id IN ({placeholders})", match_ids)
        self.cursor.execute(f"DELETE FROM match_items WHERE match_id IN ({placeholders})", match_ids)
        self.cursor.execute(f"DELETE FROM match_runes WHERE match_id IN ({placeholders})", match_ids)
        self.cursor.execute(f"DELETE FROM participants WHERE match_id IN ({placeholders})", match_ids)
        self.cursor.execute(f"DELETE FROM matches WHERE match_id IN ({placeholders})", match_ids)

        self.conn.commit()
        print(f"🗑️ Deleted {len(match_ids)} matches older than {days_to_keep} days")

    # ============================================
    # MATCHUPS
    # ============================================

    def save_matchup(self, matchup: Matchup) -> bool:
        """
        Persist a single matchup row.

        Uses INSERT OR IGNORE keyed on the composite UNIQUE constraint, so
        re-saving the same (match_id, puuid, ally, enemy) combination is a
        no-op rather than a duplicate insert.
        """
        try:
            self._ensure_connection()
            self.cursor.execute('''
                INSERT OR IGNORE INTO matchups 
                (match_id, puuid, ally_champion_id, enemy_champion_id, role, win, patch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                matchup.match_id,
                matchup.puuid,
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

    # ============================================
    # PRACTICE SUMMARY
    # ============================================

    def get_practice_summary(self, puuid: str) -> PlayerSummary:
        """
        Aggregate per-champion stats for a player across all saved matches.

        Returns a PlayerSummary containing a Player and a list of
        ChampionStats — one entry per champion the player has played.
        Only games/wins/KDA fields are populated; the richer aggregation
        fields on ChampionStats (item_counts, rune_counts, etc.) are left
        empty and are reserved for future use.
        """
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

    # ============================================
    # REFRESH HELPERS
    # ============================================

    def get_last_refresh_time(self, puuid: str) -> Optional[datetime]:
        """
        Return the timestamp of the most recent match in the DB for this
        player.

        This is used by the refresh endpoint as a proxy for "when was this
        player's data last fetched" — it's not a true refresh timestamp, but
        since every refresh pulls the latest matches, the newest match time
        advances with each successful refresh. The 1-hour rate limit is
        enforced against this value.

        Returns None if the player has no matches in the DB.
        """
        self._ensure_connection()
        self.cursor.execute(
            "SELECT MAX(game_creation) as last_refresh FROM matches WHERE puuid = ?",
            (puuid,)
        )
        row = self.cursor.fetchone()
        if row and row["last_refresh"]:
            return datetime.fromtimestamp(row["last_refresh"] / 1000)
        return None

    # ============================================
    # PARTICIPANTS
    # ============================================

    def save_participants_batch(self, match_id: str, participants: list[dict]) -> bool:
        """
        Persist all 10 participants for a match.

        Uses a delete-then-insert pattern keyed by match_id: if the match was
        previously saved with a different set of participant stats (unlikely
        but possible if Riot revises data), the old rows are replaced cleanly
        rather than leaving stale entries behind.

        `participants` must be the full roster for the match — passing a
        partial list will delete the missing players' rows.
        """
        try:
            self._ensure_connection()
            self.cursor.execute('DELETE FROM participants WHERE match_id = ?', (match_id,))

            for p in participants:
                self.cursor.execute('''
                    INSERT INTO participants (
                        match_id, puuid, champion_id, team_id, role, win,
                        kills, deaths, assists, cs, gold_earned, total_damage,
                        vision_score, summoner_spell_d, summoner_spell_f,
                        keystone_rune_id, secondary_rune_style_id,
                        role_bound_item,
                        item_0, item_1, item_2, item_3, item_4, item_5, item_6
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    p.get('role_bound_item', 0),
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

    # ============================================
    # LIFECYCLE
    # ============================================

    def close(self):
        """
        Close the underlying SQLite connection.

        Safe to call multiple times. After close(), subsequent method calls
        will trigger _ensure_connection() and reopen the connection, so
        closing is not destructive to the instance's usability.
        """
        try:
            self.conn.close()
        except Exception:
            pass