import pytest
from src.models import Player, Match, ChampionStats, PlayerSummary, SortBy

class TestPlayer:

    # test player constructor with team
    def test_player_with_team(self):
        player = Player(
            puuid="abc123",
            game_name="Faker",
            tag_line="KR1",
            region="KR",
            team="T1",
            role="MIDDLE"
        )
        
        assert player.puuid == "abc123"
        assert player.game_name == "Faker"
        assert player.tag_line == "KR1"
        assert player.region == "KR"
        assert player.team == "T1"
        assert player.role == "MIDDLE"

    # test player constructor without team
    def test_player_no_team(self):
        player = Player(
            puuid="abc123",
            game_name="Faker",
            tag_line="KR1",
            region="KR"
        )
        
        assert player.team is None
        assert player.role is None

    # team player equality
    def test_player_equals(self):
        player1 = Player("abc123", "Faker", "KR1", "KR", "T1", "MIDDLE")
        player2 = Player("abc123", "Faker", "KR1", "KR", "T1", "MIDDLE")
        
        assert player1 == player2

class TestMatch:

    def test_match_creation(self):
        match = Match(
            match_id="KR_123456",
            puuid="abc123",
            champion="Ahri",
            role="MIDDLE",
            win=True,
            kills=10,
            deaths=2,
            assists=8,
            cs=250,
            game_duration=1800,
            total_damage=28000,
            vision_score=45,
            gold_earned=12000,
            items=[3151, 3285, 4645],
            runes=[8112, 8126, 8138],
            summoner_spell_d=4,
            summoner_spell_f=12
        )
                
        assert match.match_id == "KR_123456"
        assert match.champion == "Ahri"
        assert match.win is True
        assert match.kills == 10
        assert match.deaths == 2
        assert match.assists == 8
        assert match.cs == 250
        assert match.game_duration == 1800
        assert match.total_damage == 28000
        assert match.vision_score == 45
        assert match.gold_earned == 12000
        assert len(match.items) == 3
        assert match.items[0] == 3151
        assert len(match.runes) == 3

class TestChampionStats:

    def test_win_rate_calculation(self):
        stats = ChampionStats(
            champion_name="Ahri",
            games_played=20,
            wins=12,
            losses=8,
            total_kills=150,
            total_deaths=40,
            total_assists=200
        )
        
        assert stats.win_rate == 60.0

    def test_win_rate_with_no_games(self):
        stats = ChampionStats(
                champion_name="Ahri",
                games_played=0,
                wins=0,
                losses=0,
                total_kills=0,
                total_deaths=0,
                total_assists=0
            )
            
        assert stats.win_rate == 0.0
    
    def test_kda_calculation(self):
        stats = ChampionStats(
            champion_name="Ahri",
            games_played=20,
            wins=12,
            losses=8,
            total_kills=150,
            total_deaths=40,
            total_assists=200
        )
        
        assert stats.kda == 8.75

    def test_kda_with_no_deaths(self):
        stats = ChampionStats(
            champion_name="Ahri",
            games_played=5,
            wins=5,
            losses=0,
            total_kills=25,
            total_deaths=0,
            total_assists=15
        )
        
        assert stats.kda == 40.0
    
class TestSortBy:
    def test_enum_values(self):
        assert SortBy.GAMES.value == "games"
        assert SortBy.WINRATE.value == "winrate"
        assert SortBy.KDA.value == "kda"
        assert SortBy.NAME.value == "name"
    
    def test_enum_string_conversion(self):
        assert str(SortBy.GAMES) == "games"
        assert str(SortBy.WINRATE) == "winrate"
    
    def test_enum_from_string(self):
        assert SortBy("games") == SortBy.GAMES
        assert SortBy("winrate") == SortBy.WINRATE

class TestPlayerSummary:
    """Tests for the PlayerSummary dataclass"""
    
    def setup_method(self):
        """Create test data for summary tests"""
        self.player = Player(
            puuid="abc123",
            game_name="Faker",
            tag_line="KR1",
            region="KR",
            team="T1",
            role="MIDDLE"
        )
        
        self.champion_stats = [
            ChampionStats("Ahri", 20, 12, 8, 150, 40, 200),
            ChampionStats("Azir", 15, 9, 6, 120, 35, 180),
            ChampionStats("Corki", 8, 3, 5, 60, 25, 90),
            ChampionStats("Leblanc", 12, 8, 4, 100, 30, 150),
        ]
        
        self.summary = PlayerSummary(
            player=self.player,
            champion_stats=self.champion_stats,
            total_games=55
        )
    
    def test_sort_by_games_default(self):
        """Test sorting by games (most played first)"""
        sorted_stats = self.summary.sort_by(key=SortBy.GAMES)
        
        # Ahri (20), Azir (15), Leblanc (12), Corki (8)
        assert sorted_stats[0].champion_name == "Ahri"
        assert sorted_stats[0].games_played == 20
        assert sorted_stats[-1].champion_name == "Corki"
        assert sorted_stats[-1].games_played == 8
    
    def test_sort_by_games_ascending(self):
        """Test sorting by games with reverse=False (least played first)"""
        sorted_stats = self.summary.sort_by(key=SortBy.GAMES, reverse=False)
        
        # Corki (8), Leblanc (12), Azir (15), Ahri (20)
        assert sorted_stats[0].champion_name == "Corki"
        assert sorted_stats[0].games_played == 8
        assert sorted_stats[-1].champion_name == "Ahri"
        assert sorted_stats[-1].games_played == 20
    
    def test_sort_by_winrate(self):
        """Test sorting by win rate"""
        sorted_stats = self.summary.sort_by(key=SortBy.WINRATE)
        
        # Leblanc (66.7%), Ahri (60%), Azir (60%), Corki (37.5%)
        assert sorted_stats[0].champion_name == "Leblanc"
        assert sorted_stats[0].win_rate == 66.66666666666666
        assert sorted_stats[-1].champion_name == "Corki"
        assert sorted_stats[-1].win_rate == 37.5
    
    def test_sort_by_kda(self):
        """Test sorting by KDA"""
        sorted_stats = self.summary.sort_by(key=SortBy.KDA)
        
        # Ahri (8.75), Azir (8.57), Leblanc (8.33), Corki (6.0)
        assert sorted_stats[0].champion_name == "Ahri"
        assert sorted_stats[-1].champion_name == "Corki"
    
    def test_sort_by_name(self):
        """Test sorting alphabetically by champion name"""
        sorted_stats = self.summary.sort_by(key=SortBy.NAME, reverse=False)
        
        # Ahri, Azir, Corki, Leblanc
        assert sorted_stats[0].champion_name == "Ahri"
        assert sorted_stats[1].champion_name == "Azir"
        assert sorted_stats[2].champion_name == "Corki"
        assert sorted_stats[3].champion_name == "Leblanc"
    
    def test_sort_with_min_games(self):
        """Test filtering by minimum games"""
        # Only champions with 10+ games
        sorted_stats = self.summary.sort_by(min_games=10)
        
        # Ahri (20), Azir (15), Leblanc (12) - Corki (8) excluded
        assert len(sorted_stats) == 3
        assert "Corki" not in [c.champion_name for c in sorted_stats]
    
    def test_summary_attributes(self):
        """Test summary has correct attributes"""
        assert self.summary.player.game_name == "Faker"
        assert self.summary.total_games == 55
        assert len(self.summary.champion_stats) == 4


class TestIntegration:
    """Integration tests connecting multiple classes"""
    
    def test_player_to_summary_workflow(self):
        """Test creating a player and generating their summary"""
        # Create player
        player = Player(
            puuid="test123",
            game_name="TestPro",
            tag_line="NA1",
            region="NA"
        )
        
        # Simulate aggregated stats from database
        stats = [
            ChampionStats("Yasuo", 25, 15, 10, 200, 50, 180),
            ChampionStats("Zed", 18, 10, 8, 150, 45, 120),
        ]
        
        # Create summary
        summary = PlayerSummary(
            player=player,
            champion_stats=stats,
            total_games=43
        )
        
        # Verify
        assert summary.player.game_name == "TestPro"
        assert summary.total_games == 43
    
    def test_full_match_to_stats_flow(self):
        """Test creating matches and aggregating to stats"""
        # Create a player
        player = Player("test123", "TestPlayer", "NA1", "NA")
        
        # Create multiple matches for the same player
        matches = [
            Match("match1", "test123", "Ahri", "MIDDLE", True, 10, 2, 8, 250, 1800, 28000, 45, 12000, [], [], 4, 12),
            Match("match2", "test123", "Ahri", "MIDDLE", True, 8, 3, 10, 230, 1700, 25000, 40, 11000, [], [], 4, 12),
            Match("match3", "test123", "Ahri", "MIDDLE", False, 5, 6, 4, 200, 1600, 18000, 30, 9000, [], [], 4, 12),
            Match("match4", "test123", "Zed", "MIDDLE", True, 12, 4, 6, 220, 1750, 26000, 35, 11500, [], [], 4, 12),
            Match("match5", "test123", "Zed", "MIDDLE", False, 6, 7, 3, 190, 1550, 15000, 25, 8500, [], [], 4, 12),
        ]
        
        # Manual aggregation (what the database would do)
        from collections import defaultdict
        champ_data = defaultdict(lambda: {"wins": 0, "losses": 0, "kills": 0, "deaths": 0, "assists": 0})
        
        for match in matches:
            if match.win:
                champ_data[match.champion]["wins"] += 1
            else:
                champ_data[match.champion]["losses"] += 1
            champ_data[match.champion]["kills"] += match.kills
            champ_data[match.champion]["deaths"] += match.deaths
            champ_data[match.champion]["assists"] += match.assists
        
        # Verify aggregation
        assert champ_data["Ahri"]["wins"] == 2
        assert champ_data["Ahri"]["losses"] == 1
        assert champ_data["Zed"]["wins"] == 1
        assert champ_data["Zed"]["losses"] == 1
        
        # Calculate win rates
        ahri_winrate = champ_data["Ahri"]["wins"] / 3 * 100
        assert ahri_winrate == 66.66666666666666


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
        