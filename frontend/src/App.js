// frontend/src/App.js
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';
import { getPlayers, getPracticeStats, refreshPlayer, getChampionMap } from './api/client';  // ← ADD THESE IMPORTS
import PlayerList from './components/PlayerList';
import PlayerDetail from './components/PlayerDetail';
import RegionSummary from './components/RegionSummary';

function App() {
    const [players, setPlayers] = useState([]);
    const [championMap, setChampionMap] = useState(new Map());
    const [loading, setLoading] = useState({ players: true, champions: true });

    useEffect(() => {
        const fetchData = async () => {
            // Load champion map
            try {
                const map = await getChampionMap();
                setChampionMap(map);
            } catch (error) {
                console.error('Failed to load champion map:', error);
            } finally {
                setLoading(prev => ({ ...prev, champions: false }));
            }
            
            // Load players
            try {
                const data = await getPlayers();
                setPlayers(data);
            } catch (error) {
                console.error('Failed to load players:', error);
            } finally {
                setLoading(prev => ({ ...prev, players: false }));
            }
        };
        
        fetchData();
    }, []);

    const getChampionName = (id) => {
        return championMap.get(id) || `Champion ${id}`;
    };

    // Group players by region
    const groupedPlayers = players.reduce((acc, player) => {
        const region = player.region || 'Unknown';
        if (!acc[region]) acc[region] = [];
        acc[region].push(player);
        return acc;
    }, {});

    // Helper to get player by name (case insensitive)
    const getPlayerByName = (name) => {
        return players.find(p => p.name.toLowerCase() === name.toLowerCase());
    };

    // Define region mapping for navigation
    const regionMap = {
        'KR': 'LCK',
        'CN': 'LPL',
        'EUW': 'LEC',
        'NA': 'LCS',
    };

    return (
        <Router>
            <div className="app">
                {/* Header */}
                <header className="header">
                    <div className="header-content">
                        <Link to="/" className="header-title">
                            <h1>🏆 League Pro Tracker</h1>
                            <p>Track champion practice habits of professional players</p>
                        </Link>
                    </div>
                    <div className="header-status">
                        <span className="status-dot"></span>
                        {players.length} players tracked
                    </div>
                </header>

                {/* Navigation */}
                <nav className="nav-bar">
                    <Link to="/" className="nav-link">Players</Link>
                    {Object.keys(regionMap).map((regionCode) => (
                        <Link key={regionCode} to={`/region/${regionCode}`} className="nav-link">
                            {regionMap[regionCode]}
                        </Link>
                    ))}
                </nav>

                {/* Content */}
                <div className="main-content">
                    <Routes>
                        <Route path="/" element={
                            <PlayerList
                                groupedPlayers={groupedPlayers}
                                loading={loading.players}
                                getChampionName={getChampionName}
                            />
                        } />
                        
                        {/* Player route using name instead of puuid */}
                        <Route path="/player/:playerName" element={
                            <PlayerDetail
                                getPlayerByName={getPlayerByName}
                                getChampionName={getChampionName}
                                refreshPlayer={refreshPlayer}
                                getPracticeStats={getPracticeStats}
                            />
                        } />
                        
                        {/* Region summary routes */}
                        <Route path="/region/:regionCode" element={
                            <RegionSummary
                                groupedPlayers={groupedPlayers}
                                getChampionName={getChampionName}
                            />
                        } />
                    </Routes>
                </div>
            </div>
        </Router>
    );
}

export default App;