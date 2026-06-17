# test_riot_watcher.py
from src.api.riot_client import RiotAPIClient
import config

client = RiotAPIClient()

# Test connection
print("Testing connection...")
if client.test_connection():
    print("✅ Connection successful!\n")
    
    # Test fetching a player
    print("Fetching Faker...")
    player, matches = client.get_player_with_matches("Hide on bush", "KR1", "KR", 5)
    
    if player:
        print(f"✅ Found: {player.game_name}")
        print(f"   Matches fetched: {len(matches)}")
        if matches:
            m = matches[0]
            print(f"   Most recent: {m.champion} ({m.kills}/{m.deaths}/{m.assists})")