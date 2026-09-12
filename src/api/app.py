# src/api/app.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.main import ProPlayerCollector
from src.database.db_manager import DatabaseManager
from src.models import SortBy
import config
import json
from typing import Optional

app = FastAPI(title="League Pro Tracker API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection factory
def get_db():
    return DatabaseManager(config.DATABASE_PATH)

collector = ProPlayerCollector()

# ============================================
# 1. HEALTH CHECK
# ============================================

@app.get("/")
def root():
    return {"message": "League Pro Tracker API", "status": "online"}

# ============================================
# 2. PLAYERS LIST
# ============================================

@app.get("/players")
def get_players():
    db = get_db()
    try:
        players = db.get_all_players()
        return [
            {
                "name": p.game_name,
                "tag": p.tag_line,
                "team": p.team,
                "region": p.region,
                "puuid": p.puuid,
                "role": p.role
            }
            for p in players
        ]
    finally:
        db.close()

# ============================================
# 3. CHAMPION LIST FOR A PLAYER
# ============================================

@app.get("/player/{puuid}/champions")
def get_player_champions(
    puuid: str,
    patch: Optional[str] = None,
    min_games: int = Query(3, ge=1)
):
    """Get list of champions played by a player with stats."""
    db = get_db()
    try:
        query = """
            SELECT 
                champion_id,
                COUNT(*) as games,
                SUM(win) as wins,
                ROUND(AVG(win) * 100, 1) as win_rate,
                ROUND(AVG(kills), 1) as avg_kills,
                ROUND(AVG(deaths), 1) as avg_deaths,
                ROUND(AVG(assists), 1) as avg_assists,
                ROUND(AVG(cs), 0) as avg_cs
            FROM matches
            WHERE puuid = ?
        """
        params = [puuid]
        
        if patch:
            query += " AND patch = ?"
            params.append(patch)
        
        query += " GROUP BY champion_id"
        query += " HAVING COUNT(*) >= ?"
        query += " ORDER BY games DESC"
        params.append(min_games)
        
        db.cursor.execute(query, params)
        rows = db.cursor.fetchall()
        
        return [
            {
                "champion_id": row["champion_id"],
                "games": row["games"],
                "wins": row["wins"],
                "win_rate": row["win_rate"],
                "avg_kills": row["avg_kills"],
                "avg_deaths": row["avg_deaths"],
                "avg_assists": row["avg_assists"],
                "avg_cs": row["avg_cs"]
            }
            for row in rows
        ]
    finally:
        db.close()

# ============================================
# 4. CHAMPION DETAILS (Runes, Items, Matchups)
# ============================================

@app.get("/player/{puuid}/champion/{champion_id}/details")
def get_champion_details(
    puuid: str,
    champion_id: int,
    enemy_champion_id: Optional[int] = None,
    patch: Optional[str] = None
):
    """
    Get detailed champion stats including runes, spells, items, skill order, and matchups.
    If enemy_champion_id is provided, returns matchup-specific data.
    """
    db = get_db()
    try:
        # ============================================
        # 1. BASE STATS
        # ============================================
        base_query = """
            SELECT 
                COUNT(*) as games,
                SUM(win) as wins,
                ROUND(AVG(win) * 100, 1) as win_rate,
                ROUND(AVG(kills), 1) as avg_kills,
                ROUND(AVG(deaths), 1) as avg_deaths,
                ROUND(AVG(assists), 1) as avg_assists,
                ROUND(AVG(cs), 0) as avg_cs
            FROM matches m
            WHERE m.puuid = ? AND m.champion_id = ?
        """
        base_params = [puuid, champion_id]

        if enemy_champion_id:
            base_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
            base_params.append(enemy_champion_id)
            base_params.append(champion_id)

        if patch:
            base_query += " AND m.patch = ?"
            base_params.append(patch)

        db.cursor.execute(base_query, base_params)
        base_stats = db.cursor.fetchone()

         # ============================================
        # 2. TREE RUNES (flat list — kept for backward compat)
        # ============================================
        rune_query = """
            SELECT 
                mr.rune_id,
                mr.rune_slot,
                COUNT(*) as usage_count,
                SUM(m.win) as wins,
                ROUND(AVG(m.win) * 100, 1) as win_rate
            FROM matches m
            JOIN match_runes mr ON m.match_id = mr.match_id AND m.puuid = mr.puuid
            WHERE m.puuid = ? AND m.champion_id = ?
              AND mr.rune_slot NOT LIKE 'shard_%'
        """
        rune_params = [puuid, champion_id]

        if enemy_champion_id:
            rune_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
            rune_params.append(enemy_champion_id)
            rune_params.append(champion_id)

        if patch:
            rune_query += " AND m.patch = ?"
            rune_params.append(patch)

        rune_query += " GROUP BY mr.rune_id, mr.rune_slot"
        rune_query += " ORDER BY mr.rune_slot, usage_count DESC"

        db.cursor.execute(rune_query, rune_params)
        runes = db.cursor.fetchall()

        # ============================================
        # 2a. RUNE PAGES (grouped)
        #
        # Each unique rune_page JSON blob is a distinct page. We group by it
        # so pages like "Conqueror + Triumph + Alacrity + Last Stand + Shield
        # Bash + Second Wind" stay together as a single row.
        # ============================================
        page_query = """
            SELECT 
                m.rune_page,
                COUNT(*) as usage_count,
                SUM(m.win) as wins,
                ROUND(AVG(m.win) * 100, 1) as win_rate
            FROM matches m
            WHERE m.puuid = ? AND m.champion_id = ?
              AND m.rune_page IS NOT NULL
              AND m.rune_page != ''
        """
        page_params = [puuid, champion_id]

        if enemy_champion_id:
            page_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
            page_params.append(enemy_champion_id)
            page_params.append(champion_id)

        if patch:
            page_query += " AND m.patch = ?"
            page_params.append(patch)

        page_query += " GROUP BY m.rune_page"
        page_query += " ORDER BY usage_count DESC"

        db.cursor.execute(page_query, page_params)
        rune_page_rows = db.cursor.fetchall()

        # Deserialize each page blob into a dict for the response.
        parsed_rune_pages = []
        for r in rune_page_rows:
            try:
                page_dict = json.loads(r["rune_page"])
                parsed_rune_pages.append({
                    "page": page_dict,
                    "usage_count": r["usage_count"],
                    "win_rate": r["win_rate"],
                })
            except (json.JSONDecodeError, TypeError):
                continue

        # ============================================
        # 2b. STAT SHARDS
        # ============================================
        shard_query = """
            SELECT 
                mr.rune_slot,
                mr.rune_id,
                COUNT(*) as usage_count,
                SUM(m.win) as wins,
                ROUND(AVG(m.win) * 100, 1) as win_rate
            FROM matches m
            JOIN match_runes mr ON m.match_id = mr.match_id AND m.puuid = mr.puuid
            WHERE m.puuid = ? AND m.champion_id = ?
              AND mr.rune_slot LIKE 'shard_%'
        """
        shard_params = [puuid, champion_id]

        if enemy_champion_id:
            shard_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
            shard_params.append(enemy_champion_id)
            shard_params.append(champion_id)

        if patch:
            shard_query += " AND m.patch = ?"
            shard_params.append(patch)

        shard_query += " GROUP BY mr.rune_slot, mr.rune_id"
        shard_query += " ORDER BY mr.rune_slot, usage_count DESC"

        db.cursor.execute(shard_query, shard_params)
        stat_shards = db.cursor.fetchall()

        # ============================================
        # 3. SUMMONER SPELLS
        # ============================================
        spell_query = """
            SELECT 
                summoner_spell_d,
                summoner_spell_f,
                COUNT(*) as usage_count,
                SUM(win) as wins,
                ROUND(AVG(win) * 100, 1) as win_rate
            FROM matches m
            WHERE m.puuid = ? AND m.champion_id = ?
        """
        spell_params = [puuid, champion_id]

        if enemy_champion_id:
            spell_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
            spell_params.append(enemy_champion_id)
            spell_params.append(champion_id)

        if patch:
            spell_query += " AND m.patch = ?"
            spell_params.append(patch)

        spell_query += " GROUP BY summoner_spell_d, summoner_spell_f"
        spell_query += " ORDER BY usage_count DESC"

        db.cursor.execute(spell_query, spell_params)
        spells = db.cursor.fetchall()

        # ============================================
        # 4. MATCHUPS
        # ============================================
        matchup_query = """
            SELECT 
                mu.enemy_champion_id,
                COUNT(*) as games,
                SUM(mu.win) as wins,
                ROUND(AVG(mu.win) * 100, 1) as win_rate
            FROM matchups mu
            WHERE mu.ally_champion_id = ? AND EXISTS (
                SELECT 1 FROM matches m WHERE m.match_id = mu.match_id AND m.puuid = ?
            )
        """
        matchup_params = [champion_id, puuid]

        if patch:
            matchup_query += " AND mu.patch = ?"
            matchup_params.append(patch)

        matchup_query += " GROUP BY mu.enemy_champion_id"
        matchup_query += " ORDER BY games DESC"

        db.cursor.execute(matchup_query, matchup_params)
        matchups = db.cursor.fetchall()

        # ============================================
        # 5. SKILL ORDER
        # ============================================
        skill_order_query = """
            SELECT 
                skill_order,
                COUNT(*) as usage_count,
                SUM(win) as wins,
                ROUND(AVG(win) * 100, 1) as win_rate
            FROM matches m
            WHERE m.puuid = ? AND m.champion_id = ? 
            AND m.skill_order IS NOT NULL AND m.skill_order != ''
        """
        skill_order_params = [puuid, champion_id]

        if enemy_champion_id:
            skill_order_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
            skill_order_params.append(enemy_champion_id)
            skill_order_params.append(champion_id)

        if patch:
            skill_order_query += " AND m.patch = ?"
            skill_order_params.append(patch)

        skill_order_query += " GROUP BY skill_order"
        skill_order_query += " ORDER BY usage_count DESC"

        db.cursor.execute(skill_order_query, skill_order_params)
        skill_orders = db.cursor.fetchall()

        # ============================================
        # 6. STARTING ITEMS
        #
        # An item counts as a starting item only if it was purchased within
        # the first 60 seconds AND was not sold within that same window.
        # This excludes "bought wrong item, sold, bought correct one" cases.
        # ============================================
        starting_items_query = """
            SELECT 
                json_extract(value, '$.item_id') as item_id,
                COUNT(*) as usage_count,
                SUM(m.win) as wins,
                ROUND(AVG(m.win) * 100, 1) as win_rate
            FROM matches m
            CROSS JOIN json_each(m.item_purchases)
            WHERE m.puuid = ? 
                AND m.champion_id = ?
                AND m.item_purchases IS NOT NULL 
                AND m.item_purchases != ''
                AND json_extract(value, '$.timestamp') <= 60
                AND (
                    json_extract(value, '$.sold_timestamp') IS NULL
                    OR json_extract(value, '$.sold_timestamp') > 60
                )
        """
        starting_params = [puuid, champion_id]

        if enemy_champion_id:
            starting_items_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
            starting_params.append(enemy_champion_id)
            starting_params.append(champion_id)

        if patch:
            starting_items_query += " AND m.patch = ?"
            starting_params.append(patch)

        starting_items_query += " GROUP BY item_id"
        starting_items_query += " ORDER BY usage_count DESC"

        db.cursor.execute(starting_items_query, starting_params)
        starting_items = db.cursor.fetchall()

        # ============================================
        # 7. ITEM BUILD TIMELINE
        # Same sold-before-60s filter applied here for consistency.
        # ============================================
        item_timeline_query = """
            SELECT 
                json_extract(value, '$.item_id') as item_id,
                json_extract(value, '$.timestamp') as timestamp,
                COUNT(*) as usage_count
            FROM matches m
            CROSS JOIN json_each(m.item_purchases)
            WHERE m.puuid = ? 
                AND m.champion_id = ?
                AND m.item_purchases IS NOT NULL 
                AND m.item_purchases != ''
        """
        item_params = [puuid, champion_id]

        if enemy_champion_id:
            item_timeline_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
            item_params.append(enemy_champion_id)
            item_params.append(champion_id)

        if patch:
            item_timeline_query += " AND m.patch = ?"
            item_params.append(patch)

        item_timeline_query += """
                AND json_extract(value, '$.timestamp') <= 60
                AND (
                    json_extract(value, '$.sold_timestamp') IS NULL
                    OR json_extract(value, '$.sold_timestamp') > 60
                )
        """
        item_timeline_query += " GROUP BY item_id, timestamp"
        item_timeline_query += " ORDER BY timestamp ASC"
        item_timeline_query += " LIMIT 20"

        db.cursor.execute(item_timeline_query, item_params)
        item_timeline = db.cursor.fetchall()

        return {
            "champion_id": champion_id,
            "base_stats": {
                "games": base_stats["games"] if base_stats else 0,
                "wins": base_stats["wins"] if base_stats else 0,
                "win_rate": base_stats["win_rate"] if base_stats else 0,
                "avg_kills": base_stats["avg_kills"] if base_stats else 0,
                "avg_deaths": base_stats["avg_deaths"] if base_stats else 0,
                "avg_assists": base_stats["avg_assists"] if base_stats else 0,
                "avg_cs": base_stats["avg_cs"] if base_stats else 0
            },
            "runes": [
                {
                    "rune_id": r["rune_id"],
                    "rune_slot": r["rune_slot"],
                    "usage_count": r["usage_count"],
                    "win_rate": r["win_rate"]
                }
                for r in runes
            ] if runes else [],
            "rune_pages": parsed_rune_pages,
            "stat_shards": [
                {
                    "slot": s["rune_slot"],
                    "rune_id": s["rune_id"],
                    "usage_count": s["usage_count"],
                    "win_rate": s["win_rate"]
                }
                for s in stat_shards
            ] if stat_shards else [],
            "spells": [
                {
                    "summoner_spell_d": s["summoner_spell_d"],
                    "summoner_spell_f": s["summoner_spell_f"],
                    "usage_count": s["usage_count"],
                    "win_rate": s["win_rate"]
                }
                for s in spells
            ] if spells else [],
            "matchups": [
                {
                    "enemy_champion_id": m["enemy_champion_id"],
                    "games": m["games"],
                    "wins": m["wins"],
                    "win_rate": m["win_rate"]
                }
                for m in matchups
            ] if matchups else [],
            "skill_orders": [
                {
                    "skill_order": s["skill_order"],
                    "usage_count": s["usage_count"],
                    "wins": s["wins"],
                    "win_rate": s["win_rate"]
                }
                for s in skill_orders
            ] if skill_orders else [],
            "starting_items": [
                {
                    "item_id": i["item_id"],
                    "usage_count": i["usage_count"],
                    "win_rate": i["win_rate"]
                }
                for i in starting_items
            ] if starting_items else [],
            "item_timeline": [
                {
                    "item_id": i["item_id"],
                    "timestamp": i["timestamp"],
                    "usage_count": i["usage_count"]
                }
                for i in item_timeline
            ] if item_timeline else []
        }
    finally:
        db.close()
# ============================================
# 5. PLAYER MATCH HISTORY (with participants)
# ============================================

@app.get("/player/{puuid}/matches")
def get_player_matches(
    puuid: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    patch: Optional[str] = None
):
    """Get paginated match history with all participants."""
    db = get_db()
    try:
        offset = (page - 1) * page_size
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM matches WHERE puuid = ?"
        count_params = [puuid]
        if patch:
            count_query += " AND patch = ?"
            count_params.append(patch)
        
        db.cursor.execute(count_query, count_params)
        total = db.cursor.fetchone()["total"]
        
        # Get matches
        query = """
            SELECT * FROM matches
            WHERE puuid = ?
        """
        params = [puuid]
        
        if patch:
            query += " AND patch = ?"
            params.append(patch)
        
        query += " ORDER BY game_creation DESC LIMIT ? OFFSET ?"
        params.extend([page_size, offset])
        
        db.cursor.execute(query, params)
        rows = db.cursor.fetchall()
        
        matches = []
        for row in rows:
            # Get participants for this match
            db.cursor.execute("""
                SELECT 
                    puuid, champion_id, team_id, role, win,
                    kills, deaths, assists, cs,
                    gold_earned, total_damage, vision_score,
                    summoner_spell_d, summoner_spell_f,
                    keystone_rune_id, secondary_rune_style_id,
                    item_0, item_1, item_2, item_3, item_4, item_5, item_6
                FROM participants
                WHERE match_id = ?
            """, (row["match_id"],))
            participants = db.cursor.fetchall()
            
            # Get items for the player
            db.cursor.execute("""
                SELECT item_id FROM match_items
                WHERE match_id = ? AND puuid = ?
                ORDER BY item_slot
            """, (row["match_id"], puuid))
            items = [r["item_id"] for r in db.cursor.fetchall()]
            
            # Get runes for the player
            db.cursor.execute("""
                SELECT rune_id FROM match_runes
                WHERE match_id = ? AND puuid = ?
                ORDER BY rune_slot
            """, (row["match_id"], puuid))
            runes = [r["rune_id"] for r in db.cursor.fetchall()]
            
            matches.append({
                "match_id": row["match_id"],
                "champion_id": row["champion_id"],
                "win": row["win"],
                "kills": row["kills"],
                "deaths": row["deaths"],
                "assists": row["assists"],
                "cs": row["cs"],
                "game_duration": row["game_duration"],
                "total_damage": row["total_damage"],
                "vision_score": row["vision_score"],
                "gold_earned": row["gold_earned"],
                "summoner_spell_d": row["summoner_spell_d"],
                "summoner_spell_f": row["summoner_spell_f"],
                "patch": row["patch"],
                "game_creation": row["game_creation"],
                "items": items,
                "runes": runes[:2] if runes else [],
                "all_runes": runes,
                "participants": [
                    {
                        "puuid": p["puuid"],
                        "champion_id": p["champion_id"],
                        "team_id": p["team_id"],
                        "role": p["role"],
                        "win": p["win"],
                        "kills": p["kills"],
                        "deaths": p["deaths"],
                        "assists": p["assists"],
                        "cs": p["cs"],
                        "gold_earned": p["gold_earned"],
                        "total_damage": p["total_damage"],
                        "vision_score": p["vision_score"],
                        "summoner_spell_d": p["summoner_spell_d"],
                        "summoner_spell_f": p["summoner_spell_f"],
                        "keystone_rune_id": p["keystone_rune_id"],
                        "secondary_rune_style_id": p["secondary_rune_style_id"],
                        "items": [
                            p["item_0"], p["item_1"], p["item_2"],
                            p["item_3"], p["item_4"], p["item_5"], p["item_6"]
                        ]
                    }
                    for p in participants
                ]
            })
        
        return {
            "matches": matches,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    finally:
        db.close()

# ============================================
# 6. REFRESH PLAYER DATA
# ============================================

@app.post("/player/refresh")
def refresh_player(
    game_name: str = Query(..., description="Player's IGN"),
    tag_line: str = Query(..., description="Player's tagline"),
    match_count: int = Query(20, ge=1, le=100),
    include_timeline: bool = Query(False)
):
    print(f"🔄 Refresh requested for: {game_name}#{tag_line}")
    print(f"   match_count: {match_count}")
    print(f"   include_timeline: {include_timeline}")
    
    try:
        result = collector.fetch_player(game_name, tag_line, match_count, include_timeline)
        print(f"   Result: {result}")
        return result
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to refresh: {e}"
        }

# src/api/app.py - Add this endpoint

# src/api/app.py - Fixed get_core_items

# src/api/app.py - Fixed get_core_items

@app.get("/player/{puuid}/champion/{champion_id}/core-items")
def get_core_items(
    puuid: str,
    champion_id: int,
    enemy_champion_id: Optional[int] = None,
    patch: Optional[str] = None
):
    """
    Get core item statistics for a champion.
    Returns the most common 1st, 2nd, 3rd, and 4th core items.
    """
    db = get_db()
    try:
        # Build the query step by step for debugging
        core_query = """
            WITH core_purchases AS (
                SELECT 
                    m.match_id,
                    json_each.value as purchase
                FROM matches m
                CROSS JOIN json_each(m.item_purchases)
                WHERE m.puuid = ? 
                    AND m.champion_id = ?
                    AND m.item_purchases IS NOT NULL 
                    AND m.item_purchases != ''
                    AND json_extract(json_each.value, '$.is_core') = 1
            """
        core_params = [puuid, champion_id]
        
        if enemy_champion_id:
            core_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
            core_params.append(enemy_champion_id)
            core_params.append(champion_id)
        
        if patch:
            core_query += " AND m.patch = ?"
            core_params.append(patch)
        
        core_query += """
            )
            SELECT 
                json_extract(purchase, '$.item_id') as item_id,
                json_extract(purchase, '$.core_order') as core_order,
                COUNT(*) as usage_count
            FROM core_purchases
            WHERE json_extract(purchase, '$.core_order') IS NOT NULL
            GROUP BY json_extract(purchase, '$.item_id'), json_extract(purchase, '$.core_order')
            ORDER BY core_order, usage_count DESC
        """
        
        db.cursor.execute(core_query, core_params)
        rows = db.cursor.fetchall()
        
        # Organize by core order (1st, 2nd, 3rd, 4th)
        result = {
            "first": [],
            "second": [],
            "third": [],
            "fourth": []
        }
        
        for row in rows:
            item_id = row["item_id"]
            core_order = row["core_order"]
            usage_count = row["usage_count"]
            
            # Map core_order to key
            order_map = {
                1: "first",
                2: "second", 
                3: "third",
                4: "fourth"
            }
            
            key = order_map.get(core_order)
            if key:
                result[key].append({
                    "item_id": item_id,
                    "usage_count": usage_count
                })
        
        return result
        
    except Exception as e:
        print(f"❌ Error in get_core_items: {e}")
        import traceback
        traceback.print_exc()
        return {"first": [], "second": [], "third": [], "fourth": []}
    finally:
        db.close()