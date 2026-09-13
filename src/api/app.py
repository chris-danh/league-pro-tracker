# src/api/app.py
"""
FastAPI application for the League Pro Tracker.

Exposes REST endpoints that the React frontend calls. All endpoints
read from a local SQLite database populated by the collector
(src.main.ProPlayerCollector). The refresh endpoint is the only one that
triggers new data collection.

Endpoint overview:
  GET  /                                              — health check
  GET  /players                                       — all tracked players
  GET  /player/{puuid}/champions                      — champion list for a player
  GET  /player/{puuid}/champion/{champion_id}/details — full champion breakdown
  GET  /player/{puuid}/champion/{champion_id}/core-items — core item build stats
  GET  /player/{puuid}/matches                        — paginated match history
  POST /player/refresh                                — trigger Riot data fetch
  GET  /region/{region}/champions                     — regional champion meta

Filtering conventions:
  Most endpoints accept an optional `patch` query param. When omitted,
  stats are aggregated across all saved patches. When provided, only
  matches on that patch count toward the result.

  The champion-detail endpoint additionally accepts `enemy_champion_id`.
  When provided, the response reflects only matches where the tracked
  player's champion faced that specific enemy laner. The matchup filter
  is implemented as a correlated EXISTS subquery on the `matchups` table.
"""

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
    """
    Create a fresh DatabaseManager for one request.

    Each route owns its connection and closes it in a `finally` block.
    This avoids sharing SQLite connections across concurrent requests,
    which is not thread-safe by default.
    """
    return DatabaseManager(config.DATABASE_PATH)

collector = ProPlayerCollector()

# ============================================
# 1. HEALTH CHECK
# ============================================

@app.get("/")
def root():
    """Simple liveness check used by the frontend during startup."""
    return {"message": "League Pro Tracker API", "status": "online"}

# ============================================
# 2. PLAYERS LIST
# ============================================

@app.get("/players")
def get_players():
    """
    List all tracked players.

    Returns the minimum metadata needed to render the player grid:
    display_name (public name), team, region, and the Riot credentials
    (game_name, tag_line, puuid) needed for URL routing and follow-up
    API calls.
    """
    db = get_db()
    try:
        players = db.get_all_players()
        return [
            {
                "name": p.game_name,
                "tag": p.tag_line,
                "display_name": p.display_name,
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
    """
    Champion list for a single player, sorted by games played.

    Only champions with at least `min_games` games on the (optional)
    patch filter are returned. Default min_games=3 filters out one-off
    picks so the UI shows meaningful sample sizes.

    Args:
        puuid: Player's PUUID.
        patch: Optional patch filter (e.g. "16.16").
        min_games: Minimum games required to include a champion.
    """
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
    Full statistical breakdown for one champion played by one player.

    Returns:
        base_stats       — games, win rate, KDA, CS on this champion
        runes            — flat list of rune usage (tree runes only)
        rune_pages       — grouped full-page rune setups with usage
        stat_shards      — stat shard usage per slot
        spells           — summoner spell combo usage
        matchups         — win rate vs each enemy champion
        skill_orders     — ability level-up orders with usage
        starting_items   — items bought in the first 60s
        item_timeline    — first-60s purchase order with timestamps

    All blocks share the same optional filters:
        enemy_champion_id: restrict to games vs. this enemy laner
        patch: restrict to games on this patch

    The matchup filter is implemented as a correlated EXISTS subquery
    against the `matchups` table. The pattern is:

        AND EXISTS (
            SELECT 1 FROM matchups mu
            WHERE mu.match_id = m.match_id
              AND mu.puuid = m.puuid
              AND mu.enemy_champion_id = ?
              AND mu.ally_champion_id = ?
        )

    The `mu.puuid = m.puuid` clause is required: without it, a game
    where two tracked pros faced each other would count both players'
    matchup rows, inflating the numerator while the denominator (from
    `matches`) stays per-player.
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
            base_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.puuid = m.puuid AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
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
            rune_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.puuid = m.puuid AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
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
            page_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.puuid = m.puuid AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
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
            shard_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.puuid = m.puuid AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
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
            spell_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.puuid = m.puuid AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
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
        #
        # Scoped to this specific player's matchup rows. Without the
        # mu.puuid condition, a game where two tracked pros faced each
        # other would surface the opponent's matchup row on this page.
        # ============================================
        matchup_query = """
            SELECT 
                mu.enemy_champion_id,
                COUNT(*) as games,
                SUM(mu.win) as wins,
                ROUND(AVG(mu.win) * 100, 1) as win_rate
            FROM matchups mu
            WHERE mu.ally_champion_id = ? AND mu.puuid = ?
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
            skill_order_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.puuid = m.puuid AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
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
            starting_items_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.puuid = m.puuid AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
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
            item_timeline_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.puuid = m.puuid AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
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
    """
    Paginated match history for a player, newest first.

    Each match includes:
      - The tracked player's stats and build for that game
      - The enemy laner's champion_id (looked up from `matchups`)
      - The full 10-player roster with per-player runes and items
      - Purchase timeline and skill order for the tracked player

    Every match object is a single dict with nested structures rather
    than flat DB rows, so the frontend can render the collapsed card
    (top-level fields) and expanded detail (participants array) from
    one response.

    Args:
        puuid: Player's PUUID.
        page: 1-indexed page number.
        page_size: Matches per page, capped at 50.
        patch: Optional patch filter.
    """
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
        match_rows = db.cursor.fetchall()

        matches = []
        for row in match_rows:
            # Get participants for this match
            db.cursor.execute("""
                SELECT 
                    puuid, champion_id, team_id, role, win,
                    kills, deaths, assists, cs,
                    gold_earned, total_damage, vision_score,
                    summoner_spell_d, summoner_spell_f,
                    keystone_rune_id, secondary_rune_style_id, role_bound_item,
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

            # Get runes for the player (tree runes first, then shards)
            db.cursor.execute("""
                SELECT rune_id, rune_slot FROM match_runes
                WHERE match_id = ? AND puuid = ?
                ORDER BY 
                    CASE 
                        WHEN rune_slot LIKE 'tree_%' THEN 0 
                        ELSE 1 
                    END,
                    rune_slot
            """, (row["match_id"], puuid))
            rune_rows = db.cursor.fetchall()
            runes = [r["rune_id"] for r in rune_rows]
            rune_slots = [r["rune_slot"] for r in rune_rows]

            # Look up the enemy laner for this match. Scoped by puuid so
            # a game where two tracked pros faced each other returns the
            # correct directional matchup for this player.
            db.cursor.execute("""
                SELECT enemy_champion_id
                FROM matchups
                WHERE match_id = ? AND puuid = ? AND ally_champion_id = ?
                LIMIT 1
            """, (row["match_id"], row["puuid"], row["champion_id"]))
            enemy_row = db.cursor.fetchone()
            enemy_champion_id = enemy_row["enemy_champion_id"] if enemy_row else None

            # Parse item purchases (stored as JSON in the row)
            item_purchases = []
            if row["item_purchases"]:
                try:
                    item_purchases = json.loads(row["item_purchases"])
                except (json.JSONDecodeError, TypeError):
                    item_purchases = []

            # Parse the structured rune page (already stored as JSON in the row)
            rune_page = None
            if row["rune_page"]:
                try:
                    rune_page = json.loads(row["rune_page"])
                except (json.JSONDecodeError, TypeError):
                    rune_page = None

            # Skill order is a plain string like "QWEQWRQWE..."
            skill_order = row["skill_order"] or None

            matches.append({
                "match_id": row["match_id"],
                "champion_id": row["champion_id"],
                "enemy_champion_id": enemy_champion_id,
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
                "all_rune_slots": rune_slots,
                "rune_page": rune_page,
                "item_purchases": item_purchases,
                "skill_order": skill_order,
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
                        "role_bound_item": p["role_bound_item"],
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
    """
    Trigger a fresh data collection for a single player.

    Delegates to ProPlayerCollector.fetch_player, which fetches matches
    from Riot, parses them, and upserts into the database. Because this
    can take 30-90 seconds for a full fetch with timeline data, the
    frontend overrides its default axios timeout on this request.

    Args:
        game_name: Riot ID game name (e.g. "Athene").
        tag_line: Riot ID tag (e.g. "lll").
        match_count: Deprecated — the collector uses a 28-day window.
            Accepted for backward compat but not honored.
        include_timeline: If True, fetch skill order and item purchase
            data. Slower but required for the match history detail view.

    Returns the collector's response dict with success, matches_fetched,
    matches_saved, and other counts. On unexpected exceptions returns a
    success=False response rather than a 500, so the frontend can show
    the error message directly.
    """
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


# ============================================
# 7. CORE ITEMS
# ============================================

@app.get("/player/{puuid}/champion/{champion_id}/core-items")
def get_core_items(
    puuid: str,
    champion_id: int,
    enemy_champion_id: Optional[int] = None,
    patch: Optional[str] = None
):
    """
    Core item build statistics for a champion.

    A "core item" is defined by the collector's heuristic (see
    RiotAPIClient._get_core_item_ids): 4-digit item ID with total gold
    >= 1700, plus tier-2 boots. Each purchase flagged as core also
    carries a `core_order` (1st, 2nd, 3rd, 4th) determined at collection
    time by purchase sequence, so "first core item" means the first
    completed legendary item of the game — not just the earliest
    purchase in the 1700g+ tier.

    Returns a dict with four keys (first, second, third, fourth), each
    a list of {item_id, usage_count}, sorted by usage descending.

    Shares the standard matchup and patch filters with the details
    endpoint.
    """
    db = get_db()
    try:
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
            core_query += " AND EXISTS (SELECT 1 FROM matchups mu WHERE mu.match_id = m.match_id AND mu.puuid = m.puuid AND mu.enemy_champion_id = ? AND mu.ally_champion_id = ?)"
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

        # Riot doesn't guarantee a fixed core_order — items can be skipped
        # (e.g. if a player never completes a 3rd core, only 1 and 2 appear).
        # The map is defensive: unknown orders are silently dropped rather
        # than causing a KeyError.
        order_map = {
            1: "first",
            2: "second",
            3: "third",
            4: "fourth"
        }

        for row in rows:
            item_id = row["item_id"]
            core_order = row["core_order"]
            usage_count = row["usage_count"]

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


# ============================================
# 8. REGION CHAMPION META
# ============================================

@app.get("/region/{region}/champions")
def get_region_champions(
    region: str,
    min_games: int = Query(2, ge=1),
    role: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200)
):
    """
    Champion meta breakdown for an entire region.

    Returns one entry per champion played by any tracked player in the
    region, sorted by total games. Each entry has:
      - Aggregate stats: total games, win rate, number of distinct players
      - Per-player breakdown: who played this champion and how often

    This is a two-query aggregation:
      1. Aggregate at the champion level for the requested region
      2. Fetch per-player rows for those champions, then merge in Python

    The two-query approach (rather than one query with GROUP_CONCAT)
    keeps the per-player data structured rather than string-encoded,
    which the frontend consumes directly.

    Args:
        region: Region code (KR, CN, EUW, NA).
        min_games: Minimum games for a champion to appear.
        role: Optional role filter (TOP/JUNGLE/MIDDLE/BOTTOM/UTILITY).
            Filters both the champion aggregates and the per-player
            breakdown to players with this role.
        limit: Max number of champions to return, sorted by games desc.
    """
    db = get_db()
    try:
        # ---------------------------------------------------------------
        # 1. Aggregate at the champion level
        # ---------------------------------------------------------------
        agg_query = """
            SELECT 
                m.champion_id,
                COUNT(*) as games,
                SUM(m.win) as wins,
                ROUND(AVG(m.win) * 100, 1) as win_rate,
                COUNT(DISTINCT m.puuid) as player_count
            FROM matches m
            JOIN players p ON m.puuid = p.puuid
            WHERE p.region = ?
        """
        agg_params = [region]

        if role:
            agg_query += " AND p.role = ?"
            agg_params.append(role)

        agg_query += """
            GROUP BY m.champion_id
            HAVING COUNT(*) >= ?
            ORDER BY games DESC
            LIMIT ?
        """
        agg_params.extend([min_games, limit])

        db.cursor.execute(agg_query, agg_params)
        champion_rows = db.cursor.fetchall()

        if not champion_rows:
            return []

        champion_ids = [r["champion_id"] for r in champion_rows]

        # ---------------------------------------------------------------
        # 2. Per-player breakdown for those champions
        # ---------------------------------------------------------------
        placeholders = ",".join("?" * len(champion_ids))
        breakdown_query = f"""
            SELECT 
                m.champion_id,
                m.puuid,
                p.game_name,
                p.display_name,
                p.team,
                p.role as player_role,
                COUNT(*) as games,
                SUM(m.win) as wins,
                ROUND(AVG(m.win) * 100, 1) as win_rate
            FROM matches m
            JOIN players p ON m.puuid = p.puuid
            WHERE p.region = ?
              AND m.champion_id IN ({placeholders})
        """
        breakdown_params = [region] + champion_ids

        if role:
            breakdown_query += " AND p.role = ?"
            breakdown_params.append(role)

        breakdown_query += """
            GROUP BY m.champion_id, m.puuid
            ORDER BY m.champion_id, games DESC
        """

        db.cursor.execute(breakdown_query, breakdown_params)
        breakdown_rows = db.cursor.fetchall()

        # ---------------------------------------------------------------
        # 3. Merge: build a dict of champion_id -> list of player entries
        # ---------------------------------------------------------------
        players_by_champion = {}
        for r in breakdown_rows:
            cid = r["champion_id"]
            if cid not in players_by_champion:
                players_by_champion[cid] = []
            players_by_champion[cid].append({
                "puuid": r["puuid"],
                "player_name": r["game_name"],
                "display_name": r["display_name"],
                "team": r["team"],
                "role": r["player_role"],
                "games": r["games"],
                "wins": r["wins"],
                "win_rate": r["win_rate"],
            })

        # ---------------------------------------------------------------
        # 4. Build the response
        # ---------------------------------------------------------------
        return [
            {
                "champion_id": r["champion_id"],
                "games": r["games"],
                "wins": r["wins"],
                "win_rate": r["win_rate"],
                "player_count": r["player_count"],
                "players": players_by_champion.get(r["champion_id"], []),
            }
            for r in champion_rows
        ]
    finally:
        db.close()