# scripts/check_db.py
"""
Simple script to verify the database is working properly.
Prints the most recent game for a specific player.
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DatabaseManager
from src.models import SortBy


def get_player_puuid(db, player_name: str, tag_line: str) -> str:
    """Find a player's PUUID by their name and tag."""
    players = db.get_all_players()
    for player in players:
        if player.game_name.lower() == player_name.lower() and player.tag_line.lower() == tag_line.lower():
            return player.puuid
    return None


def print_recent_match(db, puuid: str, limit: int = 1):
    """Print the most recent match for a player."""
    matches = db.get_player_matches(puuid, limit=limit)
    
    if not matches:
        print("❌ No matches found for this player.")
        return
    
    match = matches[0]
    
    print("\n" + "=" * 60)
    print("📊 MOST RECENT MATCH")
    print("=" * 60)
    
    # Convert timestamp to readable date
    if match.game_creation:
        match_date = datetime.fromtimestamp(match.game_creation / 1000)
        print(f"📅 Date: {match_date.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"📅 Date: Unknown")
    
    print(f"🏷️  Match ID: {match.match_id}")
    print(f"🏆 Champion ID: {match.champion_id}")
    print(f"📌 Role: {match.role}")
    print(f"📊 Result: {'✅ Win' if match.win else '❌ Loss'}")
    
    print(f"\n📈 KDA: {match.kills}/{match.deaths}/{match.assists}")
    print(f"⚔️  CS: {match.cs}")
    print(f"💰 Gold Earned: {match.gold_earned:,}")
    print(f"💥 Total Damage: {match.total_damage:,}")
    print(f"👁️  Vision Score: {match.vision_score}")
    print(f"⏱️  Game Duration: {match.game_duration // 60}m {match.game_duration % 60}s")
    
    print(f"\n🛠️  Items: {match.items if match.items else 'None'}")
    print(f"🔮 Runes: {match.runes[:5] if match.runes else 'None'}...")
    print(f"⚡ Summoner Spells: D={match.summoner_spell_d}, F={match.summoner_spell_f}")
    
    if match.patch:
        print(f"📦 Patch: {match.patch}")
    
    if match.skill_order:
        print(f"📖 Skill Order: {match.skill_order}")
    
    print("=" * 60)
    print(f"✅ Match found! (Total matches: {len(matches)})")


def print_match_summary(db, puuid: str, limit: int = 5):
    """Print a summary of recent matches."""
    matches = db.get_player_matches(puuid, limit=limit)
    
    if not matches:
        print("❌ No matches found for this player.")
        return
    
    print("\n" + "=" * 60)
    print(f"📊 RECENT {len(matches)} MATCHES")
    print("=" * 60)
    
    for i, match in enumerate(matches, 1):
        # Convert timestamp to readable date
        if match.game_creation:
            match_date = datetime.fromtimestamp(match.game_creation / 1000)
            date_str = match_date.strftime('%Y-%m-%d %H:%M')
        else:
            date_str = "Unknown"
        
        result = "✅" if match.win else "❌"
        
        print(f"\n{i}. {date_str} | {result} | Champion {match.champion_id} | {match.kills}/{match.deaths}/{match.assists} | CS: {match.cs}")
        print(f"   Items: {match.items if match.items else 'None'}")
    
    print("=" * 60)


def main():
    """Main function to test database."""
    print("=" * 60)
    print("🔍 DATABASE VERIFICATION")
    print("=" * 60)
    
    # Default player to check (change these)
    PLAYER_NAME = "kiin"
    TAG_LINE = "KR1"
    
    # Allow command line overrides
    if len(sys.argv) >= 3:
        PLAYER_NAME = sys.argv[1]
        TAG_LINE = sys.argv[2]
    
    print(f"\n📌 Checking database for: {PLAYER_NAME}#{TAG_LINE}")
    
    # Connect to database
    db = DatabaseManager()
    
    try:
        # Check if players exist
        all_players = db.get_all_players()
        print(f"\n👥 Total players in database: {len(all_players)}")
        
        if not all_players:
            print("❌ No players found in database. Please run main.py first:")
            print("   python -m src.main 'Hide on bush' 'KR1'")
            return
        
        print("\n📋 Players in database:")
        for p in all_players:
            print(f"   • {p.game_name}#{p.tag_line} ({p.team}) - {p.region}")
        
        # Find the player
        puuid = get_player_puuid(db, PLAYER_NAME, TAG_LINE)
        
        if not puuid:
            print(f"\n❌ Player {PLAYER_NAME}#{TAG_LINE} not found in database.")
            print("Available players:")
            for p in all_players:
                print(f"   • {p.game_name}#{p.tag_line}")
            return
        
        print(f"\n✅ Found PUUID: {puuid[:16]}...")
        
        # Check match count
        matches = db.get_player_matches(puuid, limit=100)
        print(f"\n📊 Total matches for {PLAYER_NAME}: {len(matches)}")
        
        if not matches:
            print("❌ No matches found. Please run main.py to fetch data:")
            print(f"   python -m src.main '{PLAYER_NAME}' '{TAG_LINE}'")
            return
        
        # Print most recent match
        print_recent_match(db, puuid, limit=1)
        
        # Print recent matches summary
        print_match_summary(db, puuid, limit=5)
        
        # Print some database statistics
        print("\n" + "=" * 60)
        print("📊 DATABASE STATISTICS")
        print("=" * 60)
        
        # Count total matches
        db.cursor.execute("SELECT COUNT(*) as count FROM matches")
        total_matches = db.cursor.fetchone()["count"]
        print(f"📊 Total matches in database: {total_matches}")
        
        # Get patch distribution
        db.cursor.execute("""
            SELECT patch, COUNT(*) as count 
            FROM matches 
            WHERE patch IS NOT NULL 
            GROUP BY patch 
            ORDER BY count DESC
        """)
        patches = db.cursor.fetchall()
        if patches:
            print("\n📦 Patch distribution:")
            for p in patches[:5]:
                print(f"   • Patch {p['patch']}: {p['count']} matches")
        
    finally:
        db.close()
        print("\n✅ Database connection closed")


if __name__ == "__main__":
    main()