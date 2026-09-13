// frontend/src/components/PlayerList.jsx
import React from 'react';
import { Link } from 'react-router-dom';
import './PlayerList.css';
import PlayerAvatar from './PlayerAvatar';

const REGION_NAMES = {
    'KR': '🇰🇷 LCK (Korea)',
    'NA': '🇺🇸 LCS (North America)',
    'EUW': '🇪🇺 LEC (Europe)',
    'CN': '🇨🇳 LPL (China)',
};

const REGION_ROUTES = {
    'KR': '/region/KR',
    'NA': '/region/NA',
    'EUW': '/region/EUW',
    'CN': '/region/CN',
};

const PlayerList = ({ groupedPlayers, loading, getChampionName, onSelectPlayer }) => {
    if (loading) {
        return <div className="loading-text">Loading players...</div>;
    }

    if (Object.keys(groupedPlayers).length === 0) {
        return (
            <div className="empty-state">
                <h2>No Players Found</h2>
                <p>Run <code>python -m src.main</code> to fetch data.</p>
            </div>
        );
    }

    return (
        <div className="player-list-container">
            {Object.entries(groupedPlayers).map(([region, players]) => (
                <div key={region} className="region-section">
                    <Link to={REGION_ROUTES[region] || '#'} className="region-header-link">
                        <div className="region-header">
                            <h2>{REGION_NAMES[region] || region}</h2>
                            <span className="player-count">{players.length} players</span>
                            <span className="region-arrow">→</span>
                        </div>
                    </Link>
                    <div className="player-grid">
                        {players.map((player) => (
                            <Link
                                key={player.puuid}
                                to={`/player/${encodeURIComponent(player.display_name || player.name)}`}
                                className="player-card"
                                onClick={() => onSelectPlayer && onSelectPlayer(player)}
                            >
                                <PlayerAvatar player={player} size="medium" />
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
            ))}
        </div>
    );
};

export default PlayerList;