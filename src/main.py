# src/main.py
"""
League Pro Tracker - Main Data Collection Script

This module provides the ProPlayerCollector class for fetching match data.
The frontend interacts with this via FastAPI endpoints.
"""

import json
import time
from typing import List, Dict, Optional
from src.api.riot_client import RiotAPIClient
from src.database.db_manager import DatabaseManager
from src.models import Player
import config


class ProPlayerCollector:
    """Orchestrates the collection of pro player match data."""
    
    def __init__(self):
        """Initialize the collector with API client and database."""
        self.client = RiotAPIClient()
        self.db = DatabaseManager(config.DATABASE_PATH)
        self.stats = {
            "players_processed": 0,
            "matches_fetched": 0,
            "matches_saved": 0,
            "matchups_saved": 0,
            "errors": 0,
            "start_time": time.time()
        }
    
    def load_pro_players(self, filepath: str = "data/pros.json") -> List[Dict]:
        """Load pro player list from JSON file."""
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
    
    def process_player(self, player_data: Dict, include_timeline: bool = False) -> bool:
        """
        Process a single player: fetch matches using stored PUUID.
        
        Args:
            player_data: Player data from JSON
            include_timeline: Whether to fetch timeline data (skill order, item purchases)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get player info from JSON
            name = player_data.get('IGN', '')
            tag = player_data.get('tagline', '')
            region = player_data.get('region', config.DEFAULT_REGION)
            team = player_data.get('player', 'Unknown')
            puuid = player_data.get('puuid', None)
            
            if not name or not tag:
                print(f"   ⚠️ Missing IGN or tagline for player: {player_data}")
                self.stats["errors"] += 1
                return False
            
            if not puuid:
                print(f"   ⚠️ No PUUID found for {name}#{tag}. Run populate_puuids.py first.")
                self.stats["errors"] += 1
                return False
            
            print(f"\n🔍 Processing: {name}#{tag} ({team}) - {region}")
            
            # Create Player object from stored data
            player = Player(
                puuid=puuid,
                game_name=name,
                tag_line=tag,
                region=region,
                team=team,
                role=None
            )
            print(f"   ✅ Using stored PUUID: {puuid[:16]}...")
            
            # Check if player already exists in DB
            if self.db.player_exists(puuid):
                print(f"   ℹ️ Player already exists in database: {name}")
            else:
                self.db.save_player(player)
                print(f"   ✅ Saved player to database: {name}")
            
            # Fetch recent matches
            match_count = getattr(config, 'DEFAULT_MATCH_COUNT', 20)
            print(f"   📊 Fetching {match_count} recent matches (timeline: {include_timeline})...")
            
            matches, matchups = self.client.get_recent_matches(
                puuid,
                region,
                count=match_count,
                include_timeline=include_timeline
            )
            
            if not matches:
                print(f"   ⚠️ No matches found for {name}")
                return True
            
            # Save matches
            saved_count = 0
            for match in matches:
                if self.db.save_match(match):
                    saved_count += 1
            
            # Save matchups
            matchup_count = 0
            for matchup in matchups:
                if self.db.save_matchup(matchup):
                    matchup_count += 1
            
            print(f"   ✅ Saved {saved_count}/{len(matches)} matches and {matchup_count}/{len(matchups)} matchups for {name}")
            
            # Update stats
            self.stats["players_processed"] += 1
            self.stats["matches_fetched"] += len(matches)
            self.stats["matches_saved"] += saved_count
            self.stats["matchups_saved"] += matchup_count
            
            # Rate limit safety
            time.sleep(1.5)
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error processing player: {e}")
            self.stats["errors"] += 1
            return False
    
    def fetch_player(self, game_name: str, tag_line: str, match_count: int = 20, include_timeline: bool = False) -> Dict:
        """
        Fetch matches for a single player by name and tag.
        
        This is the main method called by the FastAPI endpoint.
        
        Returns:
            Dict with success status and stats
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
        
        # Process the player
        success = self.process_player(player_data, include_timeline)
        
        return {
            "success": success,
            "player": game_name,
            "tag": tag_line,
            "matches_fetched": self.stats["matches_fetched"],
            "matches_saved": self.stats["matches_saved"],
            "matchups_saved": self.stats["matchups_saved"],
            "errors": self.stats["errors"]
        }
    
    def fetch_all_players(self, include_timeline: bool = False) -> Dict:
        """Fetch matches for ALL players in pros.json (bulk mode)."""
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
            "errors": self.stats["errors"],
            "total_players": len(players)
        }
    
    def print_summary(self):
        """Print collection summary."""
        elapsed = time.time() - self.stats["start_time"]
        
        print("\n" + "=" * 60)
        print("📊 COLLECTION SUMMARY")
        print("=" * 60)
        print(f"✅ Players processed: {self.stats['players_processed']}")
        print(f"📊 Matches fetched: {self.stats['matches_fetched']}")
        print(f"💾 Matches saved: {self.stats['matches_saved']}")
        print(f"🔗 Matchups saved: {self.stats['matchups_saved']}")
        print(f"❌ Errors: {self.stats['errors']}")
        print(f"⏱️  Time elapsed: {elapsed:.1f} seconds")
        print("=" * 60)
        
        # Database stats
        all_players = self.db.get_all_players()
        print(f"\n📁 Database contains {len(all_players)} total players")
        
        # Sample a player's matches
        if all_players:
            sample = all_players[0]
            matches = self.db.get_player_matches(sample.puuid, limit=5)
            if matches:
                print(f"\n📊 Sample: {sample.game_name} - {len(matches)} recent matches")
                for m in matches[:3]:
                    status = 'Win' if m.win else 'Loss'
                    print(f"   • Champion {m.champion_id}: {m.kills}/{m.deaths}/{m.assists} ({status})")
    
    def close(self):
        """Close database connection."""
        self.db.close()


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
            timeline = sys.argv[4].lower() == 'true' if len(sys.argv) >= 5 else False
            
            result = collector.fetch_player(game_name, tag_line, count, timeline)
            print(f"\nResult: {result}")
        else:
            # Bulk mode
            result = collector.fetch_all_players()
            print(f"\nResult: {result}")
    finally:
        collector.close()