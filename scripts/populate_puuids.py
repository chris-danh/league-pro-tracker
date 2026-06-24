"""
Helper script to populate PUUIDs in pros.json.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.riot_client import RiotAPIClient
import config


def populate_puuids():
    """Fetch and store PUUIDs for all pro players."""
    
    if not config.RIOT_API_KEY:
        print("No API key found in .env file")
        return
    
    json_path = "data/pros.json"
    
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return
    
    try:
        with open(json_path, "r", encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading: {e}")
        return
    
    client = RiotAPIClient()
    
    stats = {
        "total": 0,
        "fetched": 0,
        "already_had": 0,
        "failed": 0,
        "modified": False
    }
    
    for region, players in data.items():
        stats["total"] += len(players)
    
    for region, players in data.items():
        print(f"\nRegion: {region}")
        
        for i, player in enumerate(players, 1):
            # Get name and tag
            name = player.get("name", player.get("IGN", ""))
            tag = player.get("tag", player.get("tagline", ""))
            
            if not name or not tag:
                print(f"Player {i} has missing name or tag")
                stats["failed"] += 1
                continue
            
            team = player.get("team", player.get("player", "Unknown"))
            
            # Skip if already has PUUID
            if player.get('puuid') and player['puuid'] != "":
                print(f"{name}#{tag} ({team}) - Already has PUUID")
                stats["already_had"] += 1
                continue
            
            print(f"[{i}/{len(players)}] Fetching: {name}#{tag} ({team})...")
            
            try:
                p = client.get_summoner(name, tag, region)
                
                if p and p.puuid:
                    player['puuid'] = p.puuid
                    stats["fetched"] += 1
                    stats["modified"] = True
                    print("PUUID added.")
                else:
                    stats["failed"] += 1
                    print(f"Failed to fetch PUUID")
                    
            except Exception as e:
                stats["failed"] += 1
                print(f"Error: {e}")
    
    if stats["modified"]:
        print(f"Saving updated pros.json... ({stats['fetched']} new PUUIDs)")
        
        try:
            with open(json_path, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
            print("Saved successfully!")
        except Exception as e:
            print(f"Error saving: {e}")
    else:
        print("\nNo new PUUIDs needed")
    
    print(f"   Total players: {stats['total']}")
    print(f"   Already had PUUID: {stats['already_had']}")
    print(f"   Newly fetched: {stats['fetched']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   File modified: {stats['modified']}")



if __name__ == "__main__":
    populate_puuids()