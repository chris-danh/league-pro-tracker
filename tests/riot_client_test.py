# tests/test_riot_client.py
"""
Tests for the RiotAPIClient using the real Riot API.

These tests require a valid API key in .env and will make real API calls.
Limited to essential tests to avoid hitting rate limits.
"""

import pytest
from src.api.riot_client import RiotAPIClient
from src.models import Player, Match
import config


@pytest.fixture
def client():
    """Create a real API client if API key is available."""
    if not config.RIOT_API_KEY:
        pytest.skip("No API key found in .env file. Please add RIOT_API_KEY=your_key_here")
    
    try:
        return RiotAPIClient()
    except ValueError as e:
        pytest.skip(f"Invalid API key: {e}")


class TestRiotAPIClient:
    """Real API tests for RiotAPIClient."""
    
    def test_get_faker_account(self, client):
        """
        Test: Fetch Faker's account and verify we get correct data.
        
        This test follows the two-step process:
        Step 1: Get PUUID and name from Account API
        Step 2: Get summoner level using PUUID from Summoner API
        """
        print("\n🔍 Testing Faker account access...")
        
        # Fetch Faker
        player = client.get_summoner("TOPKING", "asd", "KR")
        
        # Verify account data
        assert player is not None, "Failed to fetch Faker's account"
        assert player.puuid is not None, "PUUID not found"
        assert len(player.puuid) > 10, "PUUID seems invalid"
        assert player.game_name == "TOPKING", "Game name mismatch"
        assert player.region == "KR", "Region mismatch"
        
        print(f"✅ Account found: {player.game_name}")
        print(f"   PUUID: {player.puuid[:16]}...")
    
    def test_get_faker_recent_matches(self, client):
        """
        Test: Fetch Faker's recent matches and verify match data.
        
        This test follows the full data pipeline:
        Step 1: Get PUUID from Account API
        Step 2: Get summoner level using PUUID
        Step 3: Get match list using PUUID
        Step 4: Get match details by match ID
        Step 5: Parse participant data for the player
        """
        print("\n🔍 Testing Faker's recent matches...")
        
        # Get Faker's account
        player = client.get_summoner("Hide on bush", "KR1", "KR")
        assert player is not None, "Failed to fetch Faker's account"
        print(f"   Account: {player.game_name}")
        
        # Fetch 3 recent ranked solo matches
        matches = client.get_recent_matches(player.puuid, "KR", count=3)
        
        # Verify we got matches
        assert len(matches) == 3, f"Expected 3 matches, got {len(matches)}"
        print(f"   ✅ Found {len(matches)} matches")
        
        # Verify each match has required data
        for i, match in enumerate(matches, 1):
            print(f"\n   Match {i}: {match.match_id}")
            print(f"      Champion: {match.champion}")
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
            
            # Assert required fields exist
            assert match.match_id is not None, "Match ID missing"
            assert match.champion is not None, "Champion missing"
            assert match.champion != "", "Champion name empty"
            assert match.kills >= 0, "Invalid kills count"
            assert match.deaths >= 0, "Invalid deaths count"
            assert match.assists >= 0, "Invalid assists count"
            assert match.summoner_spell_d > 0, "Summoner spell D missing"
            assert match.summoner_spell_f > 0, "Summoner spell F missing"
            assert isinstance(match.items, list), "Items should be a list"
            assert isinstance(match.runes, list), "Runes should be a list"
    
    def test_verify_match_stats_completeness(self, client):
        """
        Test: Verify that all required stats are present in a match.
        
        This test checks that every field we need for analysis is available.
        """
        print("\n🔍 Testing match stats completeness...")
        
        # Get Faker's account
        player = client.get_summoner("Hide on bush", "KR1", "KR")
        assert player is not None, "Failed to fetch Faker's account"
        
        # Fetch 1 recent match
        matches = client.get_recent_matches(player.puuid, "KR", count=1)
        assert len(matches) >= 1, "No matches found"
        
        match = matches[0]
        
        # List of all required fields for analysis
        required_fields = {
            'match_id': match.match_id,
            'champion': match.champion,
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
        
        # Verify all fields are present and have valid values
        print("\n   ✅ All required fields present:")
        for field_name, value in required_fields.items():
            assert value is not None, f"Field '{field_name}' is None"
            print(f"      {field_name}: {value}")
        
        print("\n   ✅ Match stats complete - ready for analysis!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])