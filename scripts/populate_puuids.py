# scripts/populate_puuids.py
"""
Helper script to populate/update PUUIDs in pros.json.

Run this script when:
1. You get a new API key (every 24 hours for dev keys)
2. You add new players to the list
3. Existing PUUIDs are failing (API key expired)

The script will:
- Fetch PUUIDs for all players using the current API key
- Update the JSON file with fresh PUUIDs
- Skip players that already have valid PUUIDs (to save API calls)

- run with -f flag to force update
"""

import json
import sys
import os
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.riot_client import RiotAPIClient
import config


class RateLimiter:
    """Simple rate limiter to respect Riot API limits."""
    
    def __init__(self, requests_per_second: int = 20, requests_per_2min: int = 100):
        self.requests_per_second = requests_per_second
        self.requests_per_2min = requests_per_2min
        self.request_timestamps = []
        self.min_interval = 1.0 / requests_per_second
    
    def wait_if_needed(self):
        """Wait if we're approaching rate limits."""
        now = time.time()
        
        cutoff_2min = now - 120
        self.request_timestamps = [t for t in self.request_timestamps if t > cutoff_2min]
        
        if len(self.request_timestamps) >= self.requests_per_2min:
            oldest = min(self.request_timestamps)
            wait_time = 120 - (now - oldest) + 0.5
            if wait_time > 0:
                print(f"   ⏳ Rate limit: Waiting {wait_time:.1f}s for 2-minute window...")
                time.sleep(wait_time)
                self.request_timestamps = [t for t in self.request_timestamps if t > (time.time() - 120)]
        
        if self.request_timestamps:
            last_request = max(self.request_timestamps)
            time_since_last = now - last_request
            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last + 0.01
                if wait_time > 0:
                    time.sleep(wait_time)
        
        self.request_timestamps.append(time.time())


def populate_puuids(force_refresh: bool = False):
    """
    Fetch and store PUUIDs for all pro players.
    
    Args:
        force_refresh: If True, fetch PUUIDs for ALL players even if they exist.
                      If False, only fetch missing PUUIDs.
    """
    print("=" * 60)
    print("🔑 PUUID POPULATOR")
    print("=" * 60)
    
    if not config.RIOT_API_KEY:
        print("❌ No API key found in .env file")
        print("   Please add: RIOT_API_KEY=your_key_here")
        return
    
    print(f"✅ API Key loaded: {config.RIOT_API_KEY[:10]}...")
    print(f"   Force refresh: {force_refresh}")
    
    json_path = "data/pros.json"
    
    if not os.path.exists(json_path):
        print(f"❌ File not found: {json_path}")
        return
    
    # Load the file
    try:
        with open(json_path, "r", encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ Loaded pros.json")
    except Exception as e:
        print(f"❌ Error loading: {e}")
        return
    
    # Count players
    total_players = 0
    for region, players in data.items():
        total_players += len(players)
    
    print(f"\n📊 Found {total_players} players across {len(data)} regions")
    
    # Show how many already have PUUIDs
    existing_count = 0
    for region, players in data.items():
        for player in players:
            if player.get('puuid') and player['puuid'] != "":
                existing_count += 1
    
    if force_refresh:
        print(f"   🔄 Force refresh: All {total_players} players will be updated")
    else:
        print(f"   Existing PUUIDs: {existing_count} players")
        print(f"   Missing PUUIDs: {total_players - existing_count} players")
    
    # Initialize client and rate limiter
    client = RiotAPIClient()
    rate_limiter = RateLimiter()
    
    stats = {
        "total": total_players,
        "fetched": 0,
        "skipped": 0,
        "failed": 0,
        "modified": False,
        "start_time": datetime.now()
    }
    
    print("\n" + "-" * 60)
    
    # Process each player
    for region, players in data.items():
        print(f"\n🌍 Region: {region}")
        
        for i, player in enumerate(players, 1):
            # Get name
            if "IGN" in player:
                name = player["IGN"]
            elif "name" in player:
                name = player["name"]
            else:
                print(f"   ⚠️ Player {i} has no 'IGN' or 'name' field")
                stats["failed"] += 1
                continue
            
            # Get tagline
            if "tagline" in player:
                tag = player["tagline"]
            elif "tag" in player:
                tag = player["tag"]
            else:
                print(f"   ⚠️ Player {name} has no 'tagline' or 'tag' field")
                stats["failed"] += 1
                continue
            
            team = player.get("player", player.get("team", "Unknown"))
            
            # Check if we should skip (unless force refresh)
            if not force_refresh and player.get('puuid') and player['puuid'] != "":
                print(f"   ✅ {name}#{tag} ({team}) - Already has PUUID (skipping)")
                stats["skipped"] += 1
                continue
            
            print(f"   🔍 [{i}/{len(players)}] Fetching: {name}#{tag} ({team})...")
            
            # Wait for rate limit
            rate_limiter.wait_if_needed()
            
            try:
                p = client.get_summoner(name, tag, region)
                
                if p and p.puuid:
                    old_puuid = player.get('puuid', '')
                    player['puuid'] = p.puuid
                    stats["fetched"] += 1
                    stats["modified"] = True
                    
                    if old_puuid:
                        print(f"      ✅ PUUID updated: {p.puuid[:16]}... (was {old_puuid[:16]}...)")
                    else:
                        print(f"      ✅ PUUID added: {p.puuid[:16]}...")
                else:
                    stats["failed"] += 1
                    print(f"      ❌ Failed to fetch PUUID")
                    
            except Exception as e:
                stats["failed"] += 1
                print(f"      ❌ Error: {e}")
            
            # Progress update
            if i % 5 == 0 or i == len(players):
                elapsed = (datetime.now() - stats["start_time"]).total_seconds()
                print(f"      📊 Progress: {i}/{len(players)} in {region}, {elapsed:.1f}s elapsed")
    
    # Save if modified
    if stats["modified"]:
        print("\n" + "-" * 60)
        print(f"💾 Saving updated pros.json... ({stats['fetched']} PUUIDs {'updated' if force_refresh else 'added'})")
        
        try:
            # Create backup first
            backup_path = json_path + ".backup"
            with open(backup_path, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"   ✅ Backup saved to: {backup_path}")
            
            # Save the updated file
            with open(json_path, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            print("   ✅ Main file saved successfully!")
            
        except Exception as e:
            print(f"❌ Error saving: {e}")
            import traceback
            traceback.print_exc()
            return
    else:
        print("\n" + "-" * 60)
        if force_refresh:
            print("ℹ️ No changes made - all players already have PUUIDs")
        else:
            print("ℹ️ No new PUUIDs needed - all players already have them")
    
    # Print summary
    elapsed = (datetime.now() - stats["start_time"]).total_seconds()
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"   Total players: {stats['total']}")
    print(f"   Fetched/Updated: {stats['fetched']}")
    print(f"   Skipped (already had): {stats['skipped']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Force refresh: {force_refresh}")
    print(f"   File modified: {stats['modified']}")
    print(f"   Time elapsed: {elapsed:.1f} seconds")
    print("=" * 60)
    
    # Show PUUID status after update
    if stats["fetched"] > 0:
        print("\n📄 Updated PUUIDs:")
        for region, players in data.items():
            for player in players:
                if player.get('puuid') and 'name' in player:
                    print(f"   {player.get('name', player.get('IGN', 'N/A'))} -> {player['puuid'][:16]}...")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Populate/update PUUIDs in pros.json")
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force refresh all PUUIDs even if they exist"
    )
    args = parser.parse_args()
    
    populate_puuids(force_refresh=args.force)