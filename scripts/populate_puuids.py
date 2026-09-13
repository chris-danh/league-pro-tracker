"""
Populate the `puuid` field for every player in data/pros.json.

Riot's match APIs require a PUUID rather than a Riot ID (game_name +
tag_line), but PUUIDs aren't something you can derive from a name —
they must be looked up via Riot's Account-V1 endpoint. This script does
that lookup for the whole player list and writes the results back to
pros.json.

Behavior:
  - Skips players who already have a non-empty `puuid` field (unless
    --force is passed). PUUIDs never change, so re-fetching them is
    wasted API budget.
  - Fetches PUUIDs via RiotAPIClient.get_summoner for the rest.
  - Writes pros.json after each successful fetch, so a mid-run crash
    doesn't lose progress.
  - Prints a summary at the end with counts of fetched / skipped / failed.

Usage:
  python populate_puuids.py
  python populate_puuids.py --force     # re-fetch all PUUIDs

Requirements:
  - RIOT_API_KEY set in .env
  - data/pros.json with at least IGN and tagline fields per player
"""

import json
import sys
import os
import time
import argparse

# Ensure the project root is on sys.path so `from src...` imports work
# when this script is run directly (e.g. `python populate_puuids.py`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.riot_client import RiotAPIClient
import config


def _save(data: dict, path: str) -> bool:
    """Write the pros.json file in place, preserving structure."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving: {e}")
        return False


def populate_puuids(force: bool = False):
    """Fetch and store PUUIDs for all pro players in data/pros.json."""

    if not config.RIOT_API_KEY:
        print("❌ No API key found.")
        print("   Create a .env file at the project root with:")
        print("   RIOT_API_KEY=RGAPI-your-key-here")
        return

    json_path = "data/pros.json"

    if not os.path.exists(json_path):
        print(f"❌ File not found: {json_path}")
        print("   Create data/pros.json with your player list first.")
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading {json_path}: {e}")
        return

    client = RiotAPIClient()

    stats = {
        "total": 0,
        "fetched": 0,
        "already_had": 0,
        "failed": 0,
        "modified": False,
    }

    for region, players in data.items():
        stats["total"] += len(players)

    for region, players in data.items():
        print(f"\nRegion: {region}")

        for i, player in enumerate(players, 1):
            name = player.get("IGN", "")
            tag = player.get("tagline", "")
            display = player.get("player", name)

            if not name or not tag:
                print(f"⚠️  Player {i} has missing IGN or tagline — skipping")
                stats["failed"] += 1
                continue

            if not force and player.get("puuid"):
                print(f"  {display} ({name}#{tag}) - already has PUUID")
                stats["already_had"] += 1
                continue

            print(f"  [{i}/{len(players)}] Fetching: {name}#{tag} ({region})...")

            try:
                p = client.get_summoner(name, tag, region)

                if p and p.puuid:
                    player["puuid"] = p.puuid
                    stats["fetched"] += 1
                    stats["modified"] = True
                    print(f"    ✅ PUUID added")

                    # Persist immediately so a mid-run crash doesn't lose progress
                    _save(data, json_path)
                else:
                    stats["failed"] += 1
                    print(f"    ❌ Failed to fetch PUUID")

            except Exception as e:
                stats["failed"] += 1
                print(f"    ❌ Error: {e}")

            # Rate-limit safety: 10 requests/sec is well under the 20/sec
            # dev key limit.
            time.sleep(0.1)

    # Final save (in case nothing was written during the loop because no
    # PUUIDs were fetched, but a partial write failed)
    if stats["modified"]:
        print(f"\nFinal save of pros.json...")
        _save(data, json_path)

    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"  Total players:      {stats['total']}")
    print(f"  Already had PUUID:  {stats['already_had']}")
    print(f"  Newly fetched:      {stats['fetched']}")
    print(f"  Failed:             {stats['failed']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate PUUIDs in pros.json")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch PUUIDs even if they already exist",
    )
    args = parser.parse_args()
    populate_puuids(force=args.force)