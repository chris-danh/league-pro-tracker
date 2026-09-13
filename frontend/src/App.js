// frontend/src/App.js
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate, useLocation } from 'react-router-dom';
import './App.css';
import {
    getPlayers,
    refreshPlayer,
    getChampionMap,
    getPlayerChampions,
    getChampionDetails,
    getMatchHistory
} from './api/client';
import PlayerList from './components/PlayerList';
import PlayerDetail from './components/PlayerDetail';
import RegionSummary from './components/RegionSummary';

function AppContent() {
    const [players, setPlayers] = useState([]);
    const [championMap, setChampionMap] = useState(new Map());
    const [selectedPlayer, setSelectedPlayer] = useState(null);
    const [champions, setChampions] = useState([]);
    const [selectedChampionId, setSelectedChampionId] = useState(null);
    const [championDetails, setChampionDetails] = useState(null);
    const [matches, setMatches] = useState([]);
    const [matchPage, setMatchPage] = useState(1);
    const [totalMatches, setTotalMatches] = useState(0);
    const [loading, setLoading] = useState({
        players: true,
        champions: false,
        championDetails: false,
        matches: false,
        refresh: false,
        championMap: true
    });
    const [theme, setTheme] = useState('dark');

    const navigate = useNavigate();
    const location = useLocation();

    // ============================================
    // THEME TOGGLE
    // ============================================
    useEffect(() => {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            setTheme(savedTheme);
            document.documentElement.setAttribute('data-theme', savedTheme);
        }
    }, []);

    const toggleTheme = () => {
        const newTheme = theme === 'dark' ? 'light' : 'dark';
        setTheme(newTheme);
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    };

    // ============================================
    // LOAD CHAMPION MAP
    // ============================================
    useEffect(() => {
        const loadChampionMap = async () => {
            setLoading(prev => ({ ...prev, championMap: true }));
            try {
                const map = await getChampionMap();
                setChampionMap(map);
            } catch (error) {
                console.error('Failed to load champion map:', error);
            } finally {
                setLoading(prev => ({ ...prev, championMap: false }));
            }
        };
        loadChampionMap();
    }, []);

    // ============================================
    // LOAD PLAYERS
    // ============================================
    useEffect(() => {
        const loadPlayers = async () => {
            setLoading(prev => ({ ...prev, players: true }));
            try {
                const data = await getPlayers();
                setPlayers(data);
            } catch (error) {
                console.error('Failed to load players:', error);
            } finally {
                setLoading(prev => ({ ...prev, players: false }));
            }
        };
        loadPlayers();
    }, []);

    // ============================================
    // SYNC SELECTED PLAYER WITH URL
    // ============================================
    useEffect(() => {
        const path = location.pathname;
        const match = path.match(/\/player\/(.+)/);
        if (match && match[1]) {
            const urlSlug = decodeURIComponent(match[1]);

            // If already showing this player, do nothing.
            if (selectedPlayer && selectedPlayer.display_name
                    && selectedPlayer.display_name.toLowerCase() === urlSlug.toLowerCase()) {
                return;
            }

            // Find the player whose display_name matches the URL slug.
            const found = players.find(
                p => p.display_name && p.display_name.toLowerCase() === urlSlug.toLowerCase()
            );
            if (found) {
                setSelectedPlayer(found);
                handleSelectPlayer(found);
            }
        }
        // Intentionally only re-run on URL change and player list load.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [location.pathname, players]);

    // ============================================
    // HELPER FUNCTIONS
    // ============================================
    const getChampionName = (id) => {
        const info = championMap.get(id);
        return info?.name || `Champion ${id}`;
    };

    const loadChampions = async (puuid) => {
        setLoading(prev => ({ ...prev, champions: true }));
        try {
            const data = await getPlayerChampions(puuid);
            setChampions(data);
            if (data && data.length > 0) {
                setSelectedChampionId(data[0].champion_id);
                await loadChampionDetails(puuid, data[0].champion_id);
            }
        } catch (error) {
            console.error('Failed to load champions:', error);
            setChampions([]);
        } finally {
            setLoading(prev => ({ ...prev, champions: false }));
        }
    };

    const loadChampionDetails = async (puuid, championId) => {
        setLoading(prev => ({ ...prev, championDetails: true }));
        try {
            const data = await getChampionDetails(puuid, championId);
            setChampionDetails(data);
        } catch (error) {
            console.error('Failed to load champion details:', error);
            setChampionDetails(null);
        } finally {
            setLoading(prev => ({ ...prev, championDetails: false }));
        }
    };

    const loadMatches = async (puuid, page = 1) => {
        setLoading(prev => ({ ...prev, matches: true }));
        try {
            const data = await getMatchHistory(puuid, page, 20);
            if (page === 1) {
                setMatches(data.matches);
            } else {
                setMatches(prev => [...prev, ...data.matches]);
            }
            setTotalMatches(data.total);
            setMatchPage(page);
        } catch (error) {
            console.error('Failed to load matches:', error);
        } finally {
            setLoading(prev => ({ ...prev, matches: false }));
        }
    };

    // ============================================
    // EVENT HANDLERS
    // ============================================
    const handleSelectPlayer = async (player) => {
        setSelectedPlayer(player);
        setSelectedChampionId(null);
        setChampionDetails(null);
        setMatches([]);
        setMatchPage(1);

        const slug = player.display_name || player.name;
        navigate(`/player/${encodeURIComponent(slug)}`);

        await Promise.all([
            loadChampions(player.puuid),
            loadMatches(player.puuid, 1)
        ]);
    };

    const handleSelectChampion = async (championId) => {
        // Clicking the currently-selected champion deselects it.
        if (selectedChampionId === championId) {
            setSelectedChampionId(null);
            setChampionDetails(null);
            return;
        }

        setSelectedChampionId(championId);
        if (selectedPlayer) {
            await loadChampionDetails(selectedPlayer.puuid, championId);
        }
    };

    const handleLoadMoreMatches = () => {
        if (selectedPlayer) {
            loadMatches(selectedPlayer.puuid, matchPage + 1);
        }
    };

    const handleRefresh = async () => {
        if (!selectedPlayer) {
            alert('Please select a player first.');
            return;
        }

        setLoading(prev => ({ ...prev, refresh: true }));

        try {
            const result = await refreshPlayer(
                selectedPlayer.name,
                selectedPlayer.tag,
                20,
                false
            );

            if (result.success === false) {
                alert(`ℹ️ ${result.message || 'No new matches found'}`);
                setLoading(prev => ({ ...prev, refresh: false }));
                return;
            }

            if (result.matches_saved === 0 && result.matches_fetched === 0) {
                alert('ℹ️ No new matches found for this player.');
                setLoading(prev => ({ ...prev, refresh: false }));
                await Promise.all([
                    loadChampions(selectedPlayer.puuid),
                    loadMatches(selectedPlayer.puuid, 1)
                ]);
                return;
            }

            await Promise.all([
                loadChampions(selectedPlayer.puuid),
                loadMatches(selectedPlayer.puuid, 1)
            ]);

            const message = result.message || `✅ Refreshed! ${result.matches_saved || 0} new matches saved.`;
            alert(message);

        } catch (error) {
            console.error('Failed to refresh:', error);
            if (error.response && error.response.status === 401) {
                alert('❌ API key expired. Please regenerate your Riot API key.');
            } else if (error.response && error.response.status === 429) {
                alert('⏳ Rate limit hit. Please wait a moment and try again.');
            } else if (error.message && error.message.includes('Network Error')) {
                alert('🌐 Network error. Make sure the backend server is running.');
            } else {
                alert('❌ Failed to refresh data. Check the console for errors.');
            }
        } finally {
            setLoading(prev => ({ ...prev, refresh: false }));
        }
    };

    const handleBack = () => {
        setSelectedPlayer(null);
        navigate('/');
    };

    // ============================================
    // GROUP PLAYERS BY REGION
    // ============================================
    const groupedPlayers = players.reduce((acc, player) => {
        const region = player.region || 'Unknown';
        if (!acc[region]) acc[region] = [];
        acc[region].push(player);
        return acc;
    }, {});

    // ============================================
    // RENDER
    // ============================================
    if (loading.championMap) {
        return (
            <div className="loading-screen">
                <div className="loading-spinner"></div>
                <p>Loading champion data...</p>
            </div>
        );
    }

    return (
        <div className="app">
            {/* Header */}
            <header className="header">
                <div className="header-content">
                    <Link to="/" className="header-title">
                        <h1>League Pro Tracker</h1>
                        <p>Track champion practice habits of professional players</p>
                    </Link>
                </div>
                <div className="header-right">
                    <div className="header-status">
                        <span className="status-dot"></span>
                        {players.length} players tracked
                    </div>
                    <button className="theme-toggle" onClick={toggleTheme}>
                        {theme === 'dark' ? '☀️' : '🌙'}
                        <span className="toggle-label">{theme === 'dark' ? 'Light' : 'Dark'}</span>
                    </button>
                </div>
            </header>

            {/* Navigation */}
            <nav className="nav-bar">
                <Link to="/" className="nav-link">Players</Link>
                <Link to="/region/KR" className="nav-link">LCK</Link>
                <Link to="/region/CN" className="nav-link">LPL</Link>
                <Link to="/region/EUW" className="nav-link">LEC</Link>
                <Link to="/region/NA" className="nav-link">LCS</Link>
            </nav>

            {/* Main Content */}
            <div className="main-content">
                <Routes>
                    <Route path="/" element={
                        <PlayerList
                            groupedPlayers={groupedPlayers}
                            loading={loading.players}
                            getChampionName={getChampionName}
                            onSelectPlayer={handleSelectPlayer}
                        />
                    } />

                    <Route path="/player/:playerName" element={
                        <PlayerDetail
                            players={players}
                            selectedPlayer={selectedPlayer}
                            champions={champions}
                            championDetails={championDetails}
                            matches={matches}
                            totalMatches={totalMatches}
                            loading={loading}
                            getChampionName={getChampionName}
                            championMap={championMap}
                            selectedChampionId={selectedChampionId}
                            onSelectChampion={handleSelectChampion}
                            onLoadMoreMatches={handleLoadMoreMatches}
                            onRefresh={handleRefresh}
                            onBack={handleBack}
                        />
                    } />

                    <Route path="/region/:regionCode" element={
                        <RegionSummary
                            groupedPlayers={groupedPlayers}
                            getChampionName={getChampionName}
                            championMap={championMap}
                        />
                    } />
                </Routes>
            </div>

            {/* Footer */}
            <footer className="footer">
                <div className="footer-content">
                    <div className="disclaimer">
                        This website is not affiliated with Riot Games.
                        All game data and assets are property of Riot Games, Inc.
                    </div>
                    <div className="footer-links">
                        <span>© {new Date().getFullYear()}</span>
                    </div>
                </div>
            </footer>
        </div>
    );
}

// ============================================
// MAIN APP COMPONENT
// ============================================
function App() {
    return (
        <Router>
            <AppContent />
        </Router>
    );
}

export default App;