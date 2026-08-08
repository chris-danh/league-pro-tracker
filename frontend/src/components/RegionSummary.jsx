// frontend/src/components/RegionSummary.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import './RegionSummary.css';

const REGION_NAMES = {
    'KR': '🇰🇷 LCK (Korea)',
    'CN': '🇨🇳 LPL (China)',
    'EUW': '🇪🇺 LEC (Europe)',
    'NA': '🇺🇸 LCS (North America)',
    'Unknown': '🌍 Unknown Region',
};

const REGION_DISPLAY = {
    'KR': 'LCK',
    'CN': 'LPL',
    'EUW': 'LEC',
    'NA': 'LCS',
};

const RegionSummary = ({ groupedPlayers, getChampionName }) => {
    const { regionCode } = useParams();
    const navigate = useNavigate();
    
    // Get players for this region, default to empty array
    const players = groupedPlayers[regionCode] || [];
    const regionName = REGION_NAMES[regionCode] || regionCode;
    const regionDisplay = REGION_DISPLAY[regionCode] || regionCode;

    const [regionStats, setRegionStats] = useState({
        totalChampions: 0,
        mostPlayed: null,
        avgWinRate: 0,
        championStats: [],
        loading: false,  // Start with false since we know immediately if there are players
    });

    // Helper to get initials for avatar
    const getInitials = (name) => {
        return name.charAt(0).toUpperCase();
    };

    // Navigate back to home
    const handleBack = () => {
        navigate('/');
    };

    // If no players, show empty state with helpful message
    if (!players || players.length === 0) {
        return (
            <div className="region-summary-empty">
                <h2>{regionName}</h2>
                <div className="empty-icon">📭</div>
                <p>No players found for {regionDisplay}.</p>
                <p className="hint">
                    Add players to <code>data/pros.json</code> and run 
                    <code>python -m src.main</code> to fetch data.
                </p>
                <button onClick={handleBack} className="back-link">← Back to all players</button>
            </div>
        );
    }

    return (
        <div className="region-summary">
            <div className="region-summary-header">
                <button onClick={handleBack} className="back-button">← Back</button>
                <div className="region-title">
                    <h2>{regionName}</h2>
                    <span className="player-count">{players.length} players</span>
                </div>
            </div>

            {/* Region Stats Cards */}
            <div className="region-stats-grid">
                <div className="stat-card">
                    <div className="stat-icon">👥</div>
                    <div className="stat-content">
                        <span className="stat-value">{players.length}</span>
                        <span className="stat-label">Players</span>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">🏆</div>
                    <div className="stat-content">
                        <span className="stat-value">-</span>
                        <span className="stat-label">Total Champions</span>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">📈</div>
                    <div className="stat-content">
                        <span className="stat-value">-</span>
                        <span className="stat-label">Avg Win Rate</span>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">⭐</div>
                    <div className="stat-content">
                        <span className="stat-value">-</span>
                        <span className="stat-label">Most Played</span>
                    </div>
                </div>
            </div>

            {/* Player List */}
            <div className="region-players">
                <h3>👥 Players</h3>
                <div className="player-grid">
                    {players.map((player) => (
                        <Link
                            key={player.puuid}
                            to={`/player/${player.name}`}
                            className="player-card"
                        >
                            <div className="player-avatar">
                                <span className="player-avatar-text">
                                    {getInitials(player.name)}
                                </span>
                            </div>
                            <div className="player-info">
                                <div className="player-name">{player.name}</div>
                                <div className="player-team">{player.team || 'Free Agent'}</div>
                                <div className="player-tag">{player.tag}</div>
                            </div>
                        </Link>
                    ))}
                </div>
            </div>

            {/* Champion Stats (Placeholder) */}
            <div className="region-champions">
                <h3>🏆 Top Champions</h3>
                <p className="placeholder-text">
                    Champion stats will appear here once practice data is collected.
                    <br />
                    <small>Click on a player to view their individual champion stats.</small>
                </p>
            </div>
        </div>
    );
};

export default RegionSummary;