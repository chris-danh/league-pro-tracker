# tests/riot_client_test.py
"""
Tests for the RiotAPIClient using the real Riot API.

These tests require a valid API key in .env and will make real API calls.
Limited to essential tests to avoid hitting rate limits.
Run with python -m pytest tests/riot_client_test.py
"""

import pytest
from src.api.riot_client import RiotAPIClient
import config


@pytest.fixture
def client():
    if not config.RIOT_API_KEY:
        pytest.skip("No API key found in .env file. Please add RIOT_API_KEY=your_key_here")

    try:
        return RiotAPIClient()
    except ValueError as e:
        pytest.skip(f"Invalid API key: {e}")


class TestRiotAPIClient:

    def test_get_account(self, client):
        """Fetch a known account and verify PUUID + name come back."""
        print("\n🔍 Testing account access...")

        player = client.get_summoner("Hide on bush", "KR1", "KR")

        assert player is not None, "Failed to fetch account"
        assert player.puuid is not None, "PUUID not found"
        assert len(player.puuid) > 10, "PUUID seems invalid"
        assert player.game_name == "Hide on bush", "Game name mismatch"
        assert player.region == "KR", "Region mismatch"

        print(f"✅ Account found: {player.game_name}")
        print(f"   PUUID: {player.puuid[:16]}...")

    def test_get_recent_matches(self, client):
        """Fetch recent matches and verify the pipeline returns valid Match objects."""
        print("\n🔍 Testing recent matches...")

        player = client.get_summoner("Hide on bush", "KR1", "KR")
        assert player is not None, "Failed to fetch account"

        # NOTE: get_recent_matches now returns a 3-tuple
        matches, matchups, participants = client.get_recent_matches(
            player.puuid, "KR", count=3
        )

        assert len(matches) == 3, f"Expected 3 matches, got {len(matches)}"
        print(f"   ✅ Found {len(matches)} matches")

        for i, match in enumerate(matches, 1):
            print(f"\n   Match {i}: {match.match_id}")
            print(f"      Champion ID: {match.champion_id}")
            print(f"      KDA: {match.kills}/{match.deaths}/{match.assists}")
            print(f"      Win: {match.win}")
            print(f"      CS: {match.cs}")
            print(f"      Duration: {match.game_duration}s")
            print(f"      Damage: {match.total_damage}")
            print(f"      Vision Score: {match.vision_score}")
            print(f"      Gold: {match.gold_earned}")
            print(f"      Summoner Spells: D={match.summoner_spell_d}, F={match.summoner_spell_f}")
            print(f"      Items: {match.items}")
            print(f"      Runes: {match.runes}")

            assert match.match_id is not None
            assert match.champion_id > 0, "Champion ID missing or invalid"
            assert match.kills >= 0
            assert match.deaths >= 0
            assert match.assists >= 0
            assert match.summoner_spell_d > 0
            assert match.summoner_spell_f > 0
            assert isinstance(match.items, list)
            assert isinstance(match.runes, list)

    def test_match_stats_completeness(self, client):
        """Verify every field needed for downstream analysis is present."""
        print("\n🔍 Testing match stats completeness...")

        player = client.get_summoner("Hide on bush", "KR1", "KR")
        assert player is not None

        matches, _, _ = client.get_recent_matches(player.puuid, "KR", count=1)
        assert len(matches) >= 1, "No matches found"

        match = matches[0]

        required_fields = {
            'match_id': match.match_id,
            'champion_id': match.champion_id,
            'win': match.win,
            'kills': match.kills,
            'deaths': match.deaths,
            'assists': match.assists,
            'cs': match.cs,
            'game_duration': match.game_duration,
            'total_damage': match.total_damage,
            'vision_score': match.vision_score,
            'gold_earned': match.gold_earned,
            'summoner_spell_d': match.summoner_spell_d,
            'summoner_spell_f': match.summoner_spell_f,
            'items': match.items,
            'runes': match.runes,
        }

        print("\n   ✅ All required fields present:")
        for field_name, value in required_fields.items():
            assert value is not None, f"Field '{field_name}' is None"
            print(f"      {field_name}: {value}")

        print("\n   ✅ Match stats complete - ready for analysis!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])