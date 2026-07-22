# src/api/app.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.main import ProPlayerCollector
from src.database.db_manager import DatabaseManager
from src.models import SortBy
import config

app = FastAPI(title="League Pro Tracker API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create collector once (doesn't use database)
collector = ProPlayerCollector()

# Database connection factory
def get_db():
    """Create a new database connection for each request."""
    return DatabaseManager(config.DATABASE_PATH)


@app.get("/")
def root():
    return {"message": "League Pro Tracker API", "status": "online"}


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
                "puuid": p.puuid
            }
            for p in players
        ]
    finally:
        db.close()


@app.get("/player/{puuid}/practice")
def get_practice(
    puuid: str,
    sort_by: str = Query("games", regex="^(games|winrate|kda)$"),
    min_games: int = Query(3, ge=1),
    limit: int = Query(10, ge=1, le=50)
):
    db = get_db()
    try:
        summary = db.get_practice_summary(puuid)
        sort_map = {"games": SortBy.GAMES, "winrate": SortBy.WINRATE, "kda": SortBy.KDA}
        champions = summary.sort_by(key=sort_map.get(sort_by, SortBy.GAMES), min_games=min_games)[:limit]
        return {
            "player": summary.player.game_name,
            "team": summary.player.team,
            "region": summary.player.region,
            "total_games": summary.total_games,
            "champions": [
                {
                    "champion_id": c.champion_id,
                    "games": c.games_played,
                    "win_rate": round(c.win_rate, 1),
                    "kda": round(c.kda, 2)
                }
                for c in champions
            ]
        }
    finally:
        db.close()


@app.post("/player/refresh")
def refresh_player(
    game_name: str = Query(..., description="Player's IGN"),
    tag_line: str = Query(..., description="Player's tagline"),
    match_count: int = Query(20, ge=1, le=100),
    include_timeline: bool = Query(False)
):
    # This uses the collector, which creates its own database connection
    result = collector.fetch_player(game_name, tag_line, match_count, include_timeline)
    return result