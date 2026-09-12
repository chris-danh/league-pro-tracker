// frontend/src/components/MatchHistory.jsx
import React, { useState } from 'react';
import './MatchHistory.css';
import GameAsset from './GameAsset';
import ChampionAsset from './ChampionAsset';

const MatchHistory = ({ 
    matches, 
    loading, 
    getChampionName, 
    onLoadMore, 
    hasMore, 
    championMap 
}) => {
    const [expandedMatch, setExpandedMatch] = useState(null);

    if (loading) {
        return <div className="loading-text">Loading matches...</div>;
    }

    if (!matches || matches.length === 0) {
        return (
            <div className="empty-state">
                <p>No matches found.</p>
            </div>
        );
    }

    const toggleExpand = (matchId) => {
        setExpandedMatch(expandedMatch === matchId ? null : matchId);
    };

    return (
        <div className="match-history">
            {matches.map((match) => (
                <div key={match.match_id} className="match-container">
                    {/* Match Card */}
                    <div 
                        className={`match-card ${match.win ? 'win' : 'loss'}`}
                        onClick={() => toggleExpand(match.match_id)}
                    >
                        <div className="match-result">{match.win ? 'W' : 'L'}</div>
                        
                        <div className="match-champion-wrapper">
                            <ChampionAsset 
                                championId={match.champion_id} 
                                type="icon"
                                size="small"
                                championMap={championMap}  // ✅ Added
                            />
                        </div>
                        
                        <div className="match-kda">
                            {match.kills}/{match.deaths}/{match.assists}
                        </div>
                        
                        <div className="match-stats">
                            <span>CS: {match.cs}</span>
                            <span>Gold: {match.gold_earned}</span>
                        </div>
                        
                        <div className="match-items">
                            {match.items.slice(0, 6).map((itemId, i) => (
                                <GameAsset key={i} type="item" id={itemId} size="small" />
                            ))}
                        </div>
                        
                        <div className="match-expand">
                            {expandedMatch === match.match_id ? '▲' : '▼'}
                        </div>
                    </div>

                    {/* Expanded Match Details */}
                    {expandedMatch === match.match_id && (
                        <div className="match-details">
                            <div className="match-participants">
                                <h4>Match Details</h4>
                                
                                {/* Player's Build Section */}
                                <div className="build-section">
                                    <h5>Your Build</h5>
                                    <div className="build-items">
                                        {match.items.map((itemId, i) => (
                                            <GameAsset key={i} type="item" id={itemId} size="large" />
                                        ))}
                                    </div>
                                    {match.all_runes && (
                                        <div className="build-runes">
                                            <span>Runes: </span>
                                            {match.all_runes.slice(0, 6).map((runeId, i) => (
                                                <GameAsset key={i} type="rune" id={runeId} size="small" />
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* All Participants */}
                                <div className="participants-grid">
                                    {match.participants && match.participants.map((p, idx) => (
                                        <div 
                                            key={idx} 
                                            className={`participant-item ${p.team_id === 100 ? 'team-blue' : 'team-red'}`}
                                        >
                                            <ChampionAsset 
                                                championId={p.champion_id} 
                                                type="icon"
                                                size="small"
                                                championMap={championMap}  // ✅ Added
                                            />
                                            <span className="participant-kda">
                                                {p.kills}/{p.deaths}/{p.assists}
                                            </span>
                                            <span className="participant-items">
                                                {[p.item_0, p.item_1, p.item_2, p.item_3, p.item_4, p.item_5, p.item_6]
                                                    .filter(item => item > 0)
                                                    .slice(0, 6)
                                                    .map((itemId, i) => (
                                                        <GameAsset key={i} type="item" id={itemId} size="small" />
                                                    ))}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            ))}

            {/* Load More Button */}
            {hasMore && (
                <button className="load-more-btn" onClick={onLoadMore}>
                    Load More Matches
                </button>
            )}
        </div>
    );
};

export default MatchHistory;