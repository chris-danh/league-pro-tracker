# check_db.py
import sqlite3
import json

def check_database():
    print("=" * 60)
    print("🔍 Checking database for item_purchases")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect("league_data.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if matches table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matches'")
        if not cursor.fetchone():
            print("❌ Matches table not found!")
            return
        
        # Check columns in matches table
        cursor.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"📋 Columns in matches table: {columns}")
        
        if 'item_purchases' not in columns:
            print("❌ No 'item_purchases' column found! Need to add it.")
            return
        
        # Check a few matches
        cursor.execute("SELECT match_id, item_purchases FROM matches LIMIT 5")
        rows = cursor.fetchall()
        
        print(f"\n📊 Found {len(rows)} matches:")
        for row in rows:
            print(f"\n🏷️  Match: {row['match_id']}")
            print(f"   item_purchases: {row['item_purchases']}")
            
            if row['item_purchases']:
                try:
                    data = json.loads(row['item_purchases'])
                    print(f"   ✅ Parsed successfully: {len(data)} items")
                    if data:
                        print(f"   First purchase: {data[0]}")
                except json.JSONDecodeError as e:
                    print(f"   ❌ JSON error: {e}")
            else:
                print("   ⚠️  No item_purchases data (NULL or empty)")
        
        # Count how many matches have item_purchases data
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN item_purchases IS NOT NULL AND item_purchases != '' THEN 1 ELSE 0 END) as has_data
            FROM matches
        """)
        stats = cursor.fetchone()
        print(f"\n📊 Statistics:")
        print(f"   Total matches: {stats['total']}")
        print(f"   Matches with item_purchases: {stats['has_data']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_database()