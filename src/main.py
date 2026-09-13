# src/main.py
"""
League Pro Tracker - Main Data Collection Script

This module provides the ProPlayerCollector class for fetching match data.
The frontend interacts with this via FastAPI endpoints.
"""

import json
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from src.api.riot_client import RiotAPIClient
from src.database.db_manager import DatabaseManager
from src.models import Player
import config


class ProPlayerCollector:
    """Orchestrates the collection of pro player match data."""

    def __init__(self):
        """
        Initialize the collector with an API client and a fresh stats
        accumulator.

        The stats dict is reset at the start of each fetch_player /
        fetch_all_players call so that per-invocation results are
        distinguishable from previous runs.
        """
        self.client = RiotAPIClient()
        self.stats = {
            "players_processed": 0,
            "matches_fetched": 0,
            "matches_saved": 0,
            "matchups_saved": 0,
            "participants_saved": 0,
            "errors": 0,
            "start_time": time.time()
        }

    def _get_db(self):
        """Create a fresh database connection for each operation."""
        return DatabaseManager(config.DATABASE_PATH)

    def load_pro_players(self, filepath: str = "data/pros.json") -> List[Dict]:
        """
        Load the pro player list from JSON and flatten it into a single list.

        The JSON is keyed by region (e.g. {"KR": [...], "EUW": [...]}).
        This method flattens it and injects the region key into each player
        dict, so downstream code can read `player['region']` uniformly.

        Returns an empty list on file-not-found or JSON parse errors.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            players = []
            for region, player_list in data.items():
                for player in player_list:
                    player['region'] = region
                    players.append(player)

            print(f"✅ Loaded {len(players)} pro players from {filepath}")
            return players
        except FileNotFoundError:
            print(f"❌ File not found: {filepath}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON: {e}")
            return []

    def find_player(self, game_name: str, tag_line: str) -> Optional[Dict]:
        """Find a player in pros.json by IGN and tagline."""
        players = self.load_pro_players()
        for player in players:
            if player.get('IGN', '') == game_name and player.get('tagline', '') == tag_line:
                return player
        return None

    def process_player(self, player_data: Dict, include_timeline: bool = True) -> bool:
        """
        Process a single player: fetch matches using stored PUUID.

        Reads the player's IGN, tagline, region, PUUID, display name, team,
        and target role from the JSON entry. Fetches all matches from the
        last 28 days, filters by target_role if specified, and persists
        matches, matchups, and participants to the database.

        Args:
            player_data: Player dict from pros.json.
            include_timeline: Whether to fetch per-match timeline data
                (skill order, item purchases). Slower but required for
                the match history purchase timeline UI.

        Returns:
            bool: True if the player was processed without fatal errors,
            False on unrecoverable errors (missing IGN, missing PUUID, etc.).
        """
        db = self._get_db()
        try:
            # Get player info from JSON
            name = player_data.get('IGN', '')
            tag = player_data.get('tagline', '')
            region = player_data.get('region', config.DEFAULT_REGION)
            display_name = player_data.get('player', None)
            team = player_data.get('team', None)
            puuid = player_data.get('puuid', None)
            target_role = player_data.get('role', None)

            if not name or not tag:
                print(f"   ⚠️ Missing IGN or tagline for player: {player_data}")
                self.stats["errors"] += 1
                return False

            if not puuid:
                print(f"   ⚠️ No PUUID found for {name}#{tag}. Run populate_puuids.py first.")
                self.stats["errors"] += 1
                return False

            print(f"\n🔍 Processing: {name}#{tag} ({team}) - {region}")
            if target_role:
                print(f"   🎯 Target role: {target_role}")

            # Create Player object from stored data
            player = Player(
                puuid=puuid,
                game_name=name,
                tag_line=tag,
                region=region,
                team=team,
                display_name=display_name,
                role=target_role
            )
            print(f"   ✅ Using stored PUUID: {puuid[:16]}...")

            # Check if player already exists in DB
            if db.player_exists(puuid):
                print(f"   ℹ️ Player already exists in database: {name}")
            else:
                db.save_player(player)
                print(f"   ✅ Saved player to database: {name}")

            # Delete matches older than 28 days before fetching new ones
            db.delete_old_matches(28)

            # Fetch matches from the last 28 days
            start_date = datetime.now() - timedelta(days=28)
            print(f"   📊 Fetching matches since {start_date.strftime('%Y-%m-%d')} (timeline: {include_timeline})...")

            matches, matchups, participants = self.client.get_matches_since_date(
                puuid,
                region,
                start_date=start_date,
                db_connection=db,
                include_timeline=True,
                batch_size=20
            )

            print(f"   📊 Found {len(matches)} matches, {len(matchups)} matchups, and {len(participants)} participants in date range")

            if not matches:
                print(f"   ⚠️ No matches found for {name} in the last 28 days")
                return True

            # Filter matches by role if target_role is specified
            if target_role:
                original_match_count = len(matches)
                matches = [m for m in matches if m.role == target_role]
                print(f"   🎯 Filtered to role '{target_role}': {len(matches)}/{original_match_count} matches kept")

                # Also filter matchups to match the filtered matches
                matchup_match_ids = {m.match_id for m in matches}
                original_matchup_count = len(matchups)
                matchups = [mu for mu in matchups if mu.match_id in matchup_match_ids]
                if original_matchup_count > 0:
                    print(f"   🔗 Filtered matchups: {len(matchups)}/{original_matchup_count} kept")

            if not matches:
                print(f"   ⚠️ No matches found for {name} in role '{target_role}'")
                return True

            # Save matches and matchups (skip duplicates)
            saved_matches, saved_matchups = db.save_matches_batch(matches, matchups)
            print(f"   ✅ Saved {saved_matches}/{len(matches)} new matches and {saved_matchups}/{len(matchups)} new matchups for {name}")

            # Save participants
            participant_count = 0
            if participants:
                # Group participants by match_id
                participants_by_match = {}
                for p in participants:
                    match_id = p['match_id']
                    if match_id not in participants_by_match:
                        participants_by_match[match_id] = []
                    participants_by_match[match_id].append(p)

                for match_id, match_participants in participants_by_match.items():
                    # Single-arg match_exists checks whether ANY row for this
                    # match_id is present. That's what we want here: the
                    # participants table stores all 10 players in a game and
                    # is shared across tracked pros, so we save it once per
                    # match, not once per (match, puuid).
                    if db.match_exists(match_id):
                        if db.save_participants_batch(match_id, match_participants):
                            participant_count += len(match_participants)

                self.stats["participants_saved"] += participant_count
                print(f"   ✅ Saved {participant_count} participants for {len(participants_by_match)} matches")

            # Update stats
            self.stats["players_processed"] += 1
            self.stats["matches_fetched"] += len(matches)
            self.stats["matches_saved"] += saved_matches
            self.stats["matchups_saved"] += saved_matchups

            # Rate limit safety
            time.sleep(1.5)

            return True

        except Exception as e:
            print(f"   ❌ Error processing player: {e}")
            import traceback
            traceback.print_exc()
            self.stats["errors"] += 1
            return False
        finally:
            db.close()

    def refresh_player(self, game_name: str, tag_line: str) -> Dict:
        """
        Quick refresh: fetches the most recent 20 matches for a player.

        Differs from fetch_player in two ways:
          - Uses get_recent_matches (last 20) rather than
            get_matches_since_date (last 28 days), so it's fast but may
            miss older games.
          - Refuses to run if the last refresh was less than 1 hour ago,
            to avoid hammering the Riot API during development.

        Saves matches, matchups, and participants for any new matches,
        matching the behavior of process_player so that match history
        detail views work for freshly-refreshed games.

        Returns a dict with success, matches_fetched, matches_saved,
        matchups_saved, and a human-readable message.
        """
        player_data = self.find_player(game_name, tag_line)
        if not player_data:
            return {"success": False, "error": "Player not found"}

        db = self._get_db()
        try:
            puuid = player_data.get('puuid')
            region = player_data.get('region', config.DEFAULT_REGION)

            # Check last refresh time to prevent spam
            last_refresh = db.get_last_refresh_time(puuid)
            if last_refresh:
                hours_since = (datetime.now() - last_refresh).total_seconds() / 3600
                if hours_since < 1:
                    return {
                        "success": True,
                        "message": f"Data recently refreshed ({hours_since:.1f} hours ago). Please wait before refreshing again.",
                        "matches_saved": 0
                    }

            # Use get_recent_matches for quick refresh (only 20 matches)
            matches, matchups, participants = self.client.get_recent_matches(
                puuid,
                region,
                count=20,
                include_timeline=True
            )

            # Save only new matches (duplicate check handled in batch save)
            saved_matches, saved_matchups = db.save_matches_batch(matches, matchups)

            # Also save participants for any new matches. Without this, freshly-
            # refreshed matches would have no participant rows and the match
            # history detail view would show an empty participants grid.
            if participants:
                participants_by_match = {}
                for p in participants:
                    match_id = p['match_id']
                    if match_id not in participants_by_match:
                        participants_by_match[match_id] = []
                    participants_by_match[match_id].append(p)

                for match_id, match_participants in participants_by_match.items():
                    if db.match_exists(match_id):
                        db.save_participants_batch(match_id, match_participants)

            return {
                "success": True,
                "matches_fetched": len(matches),
                "matches_saved": saved_matches,
                "matchups_saved": saved_matchups,
                "message": f"Saved {saved_matches} new matches"
            }

        finally:
            db.close()

    def fetch_player(self, game_name: str, tag_line: str, match_count: int = 20, include_timeline: bool = True) -> Dict:
        """
        Full collection pass for a single player.

        Looks up the player in data/pros.json by IGN + tagline, then fetches
        all matches since 28 days ago (via get_matches_since_date). Unlike
        refresh_player, this has no rate limit and will not skip players whose
        data was recently refreshed.

        Args:
            game_name: Riot ID game name (e.g. "Athene").
            tag_line: Riot ID tag (e.g. "lll").
            match_count: Deprecated. Unused — collection uses a fixed 28-day
                window. Kept for backward compatibility with the
                /player/refresh endpoint.
            include_timeline: Whether to fetch per-match timeline data
                (skill order, item purchases). Slower but required for the
                match history purchase timeline UI.

        Returns:
            Dict with success, player, tag, role, matches_fetched,
            matches_saved, matchups_saved, participants_saved, errors,
            and a human-readable message.
        """
        print("=" * 60)
        print(f"🎯 Fetching matches for: {game_name}#{tag_line}")
        print("=" * 60)

        # Find player in pros.json
        player_data = self.find_player(game_name, tag_line)

        if not player_data:
            print(f"❌ Player not found in pros.json: {game_name}#{tag_line}")
            return {
                "success": False,
                "error": f"Player {game_name}#{tag_line} not found in pros.json"
            }

        # Show role if available
        target_role = player_data.get('role', 'Unknown')
        print(f"📌 Player role: {target_role}")

        # Reset stats for this run
        self.stats = {
            "players_processed": 0,
            "matches_fetched": 0,
            "matches_saved": 0,
            "matchups_saved": 0,
            "participants_saved": 0,
            "errors": 0,
            "start_time": time.time()
        }

        success = self.process_player(player_data, include_timeline)

        return {
            "success": success,
            "player": game_name,
            "tag": tag_line,
            "role": target_role,
            "matches_fetched": self.stats["matches_fetched"],
            "matches_saved": self.stats["matches_saved"],
            "matchups_saved": self.stats["matchups_saved"],
            "participants_saved": self.stats["participants_saved"],
            "errors": self.stats["errors"],
            "message": (
                f"Fetched {self.stats['matches_fetched']} matches, saved "
                f"{self.stats['matches_saved']} new ones"
                if self.stats['matches_saved'] > 0
                else "No new matches found"
            )
        }

    def fetch_all_players(self, include_timeline: bool = True) -> Dict:
        """
        Bulk collection: fetch matches for every player in pros.json.

        Each player is processed sequentially with a 1.5-second sleep
        between calls to stay well under Riot's rate limit. Progress is
        logged per player, and a summary is returned at the end.

        Args:
            include_timeline: Whether to fetch per-match timeline data.
                Strongly recommended — without it, skill order and item
                purchase data will be missing from the match history UI.

        Returns:
            Dict with success, aggregate stats across all players, and
            the total number of players processed.
        """
        players = self.load_pro_players()
        if not players:
            return {"success": False, "error": "No players found in pros.json"}

        print(f"\n📋 Processing {len(players)} players...")

        for i, player in enumerate(players, 1):
            print(f"\n{'─' * 40}")
            print(f"📌 Player {i}/{len(players)}")
            self.process_player(player, include_timeline)

        return {
            "success": True,
            "players_processed": self.stats["players_processed"],
            "matches_fetched": self.stats["matches_fetched"],
            "matches_saved": self.stats["matches_saved"],
            "matchups_saved": self.stats["matchups_saved"],
            "participants_saved": self.stats["participants_saved"],
            "errors": self.stats["errors"],
            "total_players": len(players)
        }

    def print_summary(self):
        """Print a human-readable summary of the last collection run."""
        elapsed = time.time() - self.stats["start_time"]

        print("\n" + "=" * 60)
        print("📊 COLLECTION SUMMARY")
        print("=" * 60)
        print(f"✅ Players processed: {self.stats['players_processed']}")
        print(f"📊 Matches fetched: {self.stats['matches_fetched']}")
        print(f"💾 Matches saved: {self.stats['matches_saved']}")
        print(f"🔗 Matchups saved: {self.stats['matchups_saved']}")
        print(f"👥 Participants saved: {self.stats['participants_saved']}")
        print(f"❌ Errors: {self.stats['errors']}")
        print(f"⏱️  Time elapsed: {elapsed:.1f} seconds")
        print("=" * 60)

        # Database stats
        db = self._get_db()
        try:
            all_players = db.get_all_players()
            print(f"\n📁 Database contains {len(all_players)} total players")

            if all_players:
                sample = all_players[0]
                matches = db.get_player_matches(sample.puuid, limit=5)
                if matches:
                    print(f"\n📊 Sample: {sample.game_name} - {len(matches)} recent matches")
                    for m in matches[:3]:
                        status = 'Win' if m.win else 'Loss'
                        print(f"   • Champion {m.champion_id}: {m.kills}/{m.deaths}/{m.assists} ({status})")
        finally:
            db.close()

    def close(self):
        """Close database connection (no-op, kept for compatibility)."""
        pass


# For testing/debugging directly
if __name__ == "__main__":
    import sys

    collector = ProPlayerCollector()

    try:
        if len(sys.argv) >= 3:
            # Command line usage for debugging
            game_name = sys.argv[1]
            tag_line = sys.argv[2]
            count = int(sys.argv[3]) if len(sys.argv) >= 4 else 20
            timeline = True

            result = collector.fetch_player(game_name, tag_line, count, timeline)
            print(f"\nResult: {result}")
        else:
            # Bulk mode
            result = collector.fetch_all_players()
            print(f"\nResult: {result}")
    finally:
        collector.close()