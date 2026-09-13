// frontend/src/components/RegionSummary.jsx
import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import './RegionSummary.css';
import ChampionAsset from './ChampionAsset';
import PlayerAvatar from './PlayerAvatar';
import { getRegionChampions } from '../api/client';

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

const RegionSummary = ({ groupedPlayers, getChampionName, championMap }) => {
    const { regionCode } = useParams();
    const navigate = useNavigate();

    const players = useMemo(
        () => groupedPlayers[regionCode] || [],
        [groupedPlayers, regionCode]
    );

    const regionName = REGION_NAMES[regionCode] || regionCode;
    const regionDisplay = REGION_DISPLAY[regionCode] || regionCode;

    const [championMeta, setChampionMeta] = useState([]);
    const [metaLoading, setMetaLoading] = useState(false);

    useEffect(() => {
        if (!players || players.length === 0) return;
        setMetaLoading(true);
        getRegionChampions(regionCode, 2, null, 50)
            .then(data => setChampionMeta(data))
            .catch(err => console.error('Failed to load region champions:', err))
            .finally(() => setMetaLoading(false));
    }, [regionCode, players]);

    const handleBack = () => {
        navigate('/');
    };

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
                        <span className="stat-value">{championMeta.length}</span>
                        <span className="stat-label">Champions Played</span>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">📈</div>
                    <div className="stat-content">
                        <span className="stat-value">
                            {championMeta.length > 0
                                ? (championMeta.reduce((a, c) => a + c.win_rate * c.games, 0)
                                   / championMeta.reduce((a, c) => a + c.games, 0)).toFixed(1)
                                : '-'}%
                        </span>
                        <span className="stat-label">Avg Win Rate</span>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">⭐</div>
                    <div className="stat-content">
                        <span className="stat-value">
                            {championMeta.length > 0 ? getChampionName(championMeta[0].champion_id) : '-'}
                        </span>
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
                            to={`/player/${encodeURIComponent(player.display_name || player.name)}`}
                            className="player-card"
                        >
                            <PlayerAvatar player={player} size="small" />
                            <div className="player-info">
                                <div className="player-name">
                                    {player.team && (
                                        <span className="player-team-badge">{player.team}</span>
                                    )}
                                    <span className="player-display-name">
                                        {player.display_name || player.name}
                                    </span>
                                </div>
                                <div className="player-ign">
                                    {player.name} #{player.tag}
                                </div>
                            </div>
                        </Link>
                    ))}
                </div>
            </div>

            {/* Champion Meta */}
            <div className="region-champions">
                <h3>🏆 Champion Pool</h3>
                {metaLoading ? (
                    <p className="placeholder-text">Loading champion stats...</p>
                ) : championMeta.length === 0 ? (
                    <p className="placeholder-text">
                        No champion data yet. Refresh some players to populate stats.
                    </p>
                ) : (
                    <div className="champion-meta-list">
                        {championMeta.map((champ) => (
                            <div key={champ.champion_id} className="champion-meta-card">
                                <div className="champion-meta-header">
                                    <ChampionAsset
                                        championId={champ.champion_id}
                                        type="icon"
                                        size="medium"
                                        championMap={championMap}
                                    />
                                    <div className="champion-meta-info">
                                        <span className="champion-meta-name">
                                            {getChampionName(champ.champion_id)}
                                        </span>
                                        <span className="champion-meta-stats">
                                            {champ.games} games · {champ.player_count} players
                                        </span>
                                    </div>
                                    <span className={`champion-meta-winrate ${champ.win_rate >= 50 ? 'positive' : 'negative'}`}>
                                        {champ.win_rate}%
                                    </span>
                                </div>

                                <div className="champion-meta-players">
                                    {champ.players.map((p) => (
                                        <Link
                                            key={p.puuid}
                                            to={`/player/${encodeURIComponent(p.display_name || p.player_name)}`}
                                            className="champion-meta-player"
                                        >
                                            <span className="champion-meta-player-name">
                                                {p.display_name || p.player_name}
                                            </span>
                                            <span className="champion-meta-player-games">{p.games}g</span>
                                            <span className={`champion-meta-player-wr ${p.win_rate >= 50 ? 'positive' : 'negative'}`}>
                                                {p.win_rate}%
                                            </span>
                                        </Link>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default RegionSummary;