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
    const [activeTab, setActiveTab] = useState({});

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

    const setTabForMatch = (matchId, tab) => {
        setActiveTab(prev => ({ ...prev, [matchId]: tab }));
    };

    const formatTime = (seconds) => {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${String(s).padStart(2, '0')}`;
    };

    return (
        <div className="match-history">
            {matches.map((match) => {
                const tab = activeTab[match.match_id] || 'overview';

                return (
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
                                    championMap={championMap}
                                />
                                {match.enemy_champion_id && (
                                    <>
                                        <span className="matchup-vs">vs</span>
                                        <ChampionAsset
                                            championId={match.enemy_champion_id}
                                            type="icon"
                                            size="small"
                                            championMap={championMap}
                                        />
                                    </>
                                )}
                            </div>

                            <div className="match-loadout">
                                {match.summoner_spell_d > 0 && (
                                    <GameAsset type="spell" id={match.summoner_spell_d} size="small" />
                                )}
                                {match.summoner_spell_f > 0 && (
                                    <GameAsset type="spell" id={match.summoner_spell_f} size="small" />
                                )}
                                {match.rune_page?.keystone > 0 && (
                                    <GameAsset type="rune" id={match.rune_page.keystone} size="small" />
                                )}
                                {match.rune_page?.secondary_style > 0 && (
                                    <GameAsset type="rune" id={match.rune_page.secondary_style} size="small" />
                                )}
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
                                {/* Tab Bar */}
                                <div className="match-tabs">
                                    <button
                                        className={`match-tab ${tab === 'overview' ? 'active' : ''}`}
                                        onClick={() => setTabForMatch(match.match_id, 'overview')}
                                    >
                                        Overview
                                    </button>
                                    <button
                                        className={`match-tab ${tab === 'timeline' ? 'active' : ''}`}
                                        onClick={() => setTabForMatch(match.match_id, 'timeline')}
                                    >
                                        Purchase Timeline
                                    </button>
                                </div>

                                {/* Overview Tab */}
                                {tab === 'overview' && (
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
                                            <div className="build-spells">
                                                <span>Spells: </span>
                                                {match.summoner_spell_d > 0 && (
                                                    <GameAsset type="spell" id={match.summoner_spell_d} size="medium" />
                                                )}
                                                {match.summoner_spell_f > 0 && (
                                                    <GameAsset type="spell" id={match.summoner_spell_f} size="medium" />
                                                )}
                                            </div>
                                            {match.all_runes && (
                                                <div className="build-runes">
                                                    <span>Runes: </span>
                                                    {match.all_runes.map((runeId, i) => {
                                                        const slot = match.all_rune_slots?.[i] || null;
                                                        return (
                                                            <GameAsset
                                                                key={i}
                                                                type="rune"
                                                                id={runeId}
                                                                slot={slot}
                                                                size="small"
                                                            />
                                                        );
                                                    })}
                                                </div>
                                            )}
                                        </div>

                                        {/* Skill Order */}
                                        {match.skill_order && match.skill_order.length > 0 && (() => {
                                            const abilities = ['Q', 'W', 'E'];
                                            const sequence = match.skill_order.split('').slice(0, 18);

                                            const counts = { Q: 0, W: 0, E: 0 };
                                            const firstAppearance = { Q: null, W: null, E: null };
                                            const maxedOrder = [];

                                            sequence.forEach((ability, idx) => {
                                                if (abilities.includes(ability)) {
                                                    if (firstAppearance[ability] === null) {
                                                        firstAppearance[ability] = idx + 1;
                                                    }
                                                    counts[ability] += 1;
                                                    if (counts[ability] === 5 && !maxedOrder.includes(ability)) {
                                                        maxedOrder.push(ability);
                                                    }
                                                }
                                            });

                                            const remaining = abilities
                                                .filter(a => !maxedOrder.includes(a) && counts[a] > 0)
                                                .sort((a, b) => (firstAppearance[a] || 999) - (firstAppearance[b] || 999));

                                            const priorityOrder = [...maxedOrder, ...remaining];

                                            return (
                                                <div className="build-section">
                                                    <h5>Skill Order</h5>

                                                    {priorityOrder.length > 0 && (
                                                        <div className="skill-order-priority">
                                                            {priorityOrder.map((ability, idx) => (
                                                                <React.Fragment key={ability}>
                                                                    <span className="priority-ability-group">
                                                                        <ChampionAsset
                                                                            championId={match.champion_id}
                                                                            type="ability"
                                                                            ability={ability}
                                                                            size="small"
                                                                        />
                                                                        <span className={`priority-ability-letter ability-${ability}`}>
                                                                            {ability}
                                                                        </span>
                                                                    </span>
                                                                    {idx < priorityOrder.length - 1 && (
                                                                        <span className="priority-separator">&gt;</span>
                                                                    )}
                                                                </React.Fragment>
                                                            ))}
                                                        </div>
                                                    )}

                                                    <div className="skill-order-timeline">
                                                        {sequence.map((ability, idx) => {
                                                            const level = idx + 1;
                                                            return (
                                                                <div key={idx} className="skill-order-step">
                                                                    <span className="skill-order-level">{level}</span>
                                                                    <span className={`skill-order-ability ability-${ability}`}>
                                                                        {ability}
                                                                    </span>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                </div>
                                            );
                                        })()}

                                        {/* All Participants — blue on left, red on right */}
                                        {match.participants && (() => {
                                            const blueTeam = match.participants.filter(p => p.team_id === 100);
                                            const redTeam = match.participants.filter(p => p.team_id === 200);

                                            const renderParticipant = (p, idx) => {
                                                const standardItems = (p.items || []).slice(0, 7);
                                                const roleBoundItem = p.role_bound_item || 0;
                                                const showRoleBound = roleBoundItem > 0
                                                    && !standardItems.includes(roleBoundItem);

                                                return (
                                                    <div
                                                        key={idx}
                                                        className={`participant-item ${p.team_id === 100 ? 'team-blue' : 'team-red'}`}
                                                    >
                                                        <ChampionAsset
                                                            championId={p.champion_id}
                                                            type="icon"
                                                            size="small"
                                                            championMap={championMap}
                                                        />
                                                        <span className="participant-kda">
                                                            {p.kills}/{p.deaths}/{p.assists}
                                                        </span>
                                                        <span className="participant-loadout">
                                                            {p.summoner_spell_d > 0 && (
                                                                <GameAsset type="spell" id={p.summoner_spell_d} size="small" />
                                                            )}
                                                            {p.summoner_spell_f > 0 && (
                                                                <GameAsset type="spell" id={p.summoner_spell_f} size="small" />
                                                            )}
                                                            {p.keystone_rune_id > 0 && (
                                                                <GameAsset type="rune" id={p.keystone_rune_id} size="small" />
                                                            )}
                                                            {p.secondary_rune_style_id > 0 && (
                                                                <GameAsset type="rune" id={p.secondary_rune_style_id} size="small" />
                                                            )}
                                                        </span>
                                                        <span className="participant-items">
                                                            {/* Left: 6 inventory slots in a 2×3 grid */}
                                                            <span className="participant-inventory">
                                                                {[0, 1, 2, 3, 4, 5].map((slotIdx) => {
                                                                    const itemId = standardItems[slotIdx] || 0;
                                                                    return itemId > 0 ? (
                                                                        <GameAsset key={slotIdx} type="item" id={itemId} size="small" />
                                                                    ) : (
                                                                        <div key={slotIdx} className="game-asset asset-small empty-item-slot" />
                                                                    );
                                                                })}
                                                            </span>

                                                            {/* Right: trinket + role quest in a 2×1 column */}
                                                            <span className="participant-utility">
                                                                {standardItems[6] > 0 ? (
                                                                    <GameAsset type="item" id={standardItems[6]} size="small" />
                                                                ) : (
                                                                    <div className="game-asset asset-small empty-item-slot" />
                                                                )}
                                                                {showRoleBound ? (
                                                                    <div className="role-bound-slot" title="Role quest item">
                                                                        <GameAsset type="item" id={roleBoundItem} size="small" />
                                                                    </div>
                                                                ) : (
                                                                    <div className="game-asset asset-small empty-item-slot" />
                                                                )}
                                                            </span>
                                                        </span>
                                                    </div>
                                                );
                                            };

                                            return (
                                                <div className="participants-teams">
                                                    <div className="participants-column team-blue-column">
                                                        {blueTeam.map(renderParticipant)}
                                                    </div>
                                                    <div className="participants-column team-red-column">
                                                        {redTeam.map(renderParticipant)}
                                                    </div>
                                                </div>
                                            );
                                        })()}
                                    </div>
                                )}

                                {/* Purchase Timeline Tab */}
                                {tab === 'timeline' && (
                                    <div className="match-participants">
                                        <h4>Purchase Timeline</h4>
                                        {match.item_purchases && match.item_purchases.length > 0 ? (
                                            <div className="item-timeline">
                                                {match.item_purchases.map((p, idx) => {
                                                    const sold = p.sold_timestamp !== null
                                                        && p.sold_timestamp !== undefined;
                                                    return (
                                                        <div
                                                            key={idx}
                                                            className={`timeline-entry ${sold ? 'sold' : ''}`}
                                                        >
                                                            <span className="timeline-time">
                                                                {formatTime(p.timestamp)}
                                                            </span>
                                                            <div className="timeline-item">
                                                                <GameAsset
                                                                    type="item"
                                                                    id={p.item_id}
                                                                    size="small"
                                                                />
                                                                {sold && (
                                                                    <span className="timeline-sold-marker">
                                                                        sold {formatTime(p.sold_timestamp)}
                                                                    </span>
                                                                )}
                                                            </div>
                                                            {p.is_core && (
                                                                <span className="timeline-core-badge">
                                                                    {p.core_order === 1 ? '1st' :
                                                                     p.core_order === 2 ? '2nd' :
                                                                     p.core_order === 3 ? '3rd' :
                                                                     p.core_order ? `${p.core_order}th` : ''} core
                                                                </span>
                                                            )}
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        ) : (
                                            <p className="timeline-empty">
                                                No purchase data available for this match.
                                            </p>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                );
            })}

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