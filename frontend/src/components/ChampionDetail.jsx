// frontend/src/components/ChampionDetail.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import './ChampionDetail.css';
import ChampionAsset from './ChampionAsset';
import GameAsset from './GameAsset';
import {
    getChampionDetails,
    getCoreItems,
    getRuneMap,
    getRuneName,
} from '../api/client';

const formatCount = (occurrences, totalGames) => {
    if (!totalGames || totalGames === 0) return '0 / 0';
    return `${occurrences} / ${totalGames}`;
};

const ChampionDetail = ({
    details,
    loading,
    getChampionName,
    championMap,
    puuid,
}) => {
    const [selectedMatchup, setSelectedMatchup] = useState(null);
    const [showSkillOrder, setShowSkillOrder] = useState(true);
    const [filteredDetails, setFilteredDetails] = useState(details);
    const [filterLoading, setFilterLoading] = useState(false);
    const [coreItems, setCoreItems] = useState({
        first: [], second: [], third: [], fourth: []
    });
    const [coreItemsLoading, setCoreItemsLoading] = useState(false);
    const [expandedKeystone, setExpandedKeystone] = useState(null);
    const [runeMapReady, setRuneMapReady] = useState(false);

    // Preload the rune map so keystone names render on first paint.
    useEffect(() => {
        getRuneMap()
            .then(() => setRuneMapReady(true))
            .catch(() => setRuneMapReady(true));
    }, []);

    const fetchCoreItems = useCallback(async (championId, enemyChampionId) => {
        if (!puuid || !championId) return;
        setCoreItemsLoading(true);
        try {
            const data = await getCoreItems(puuid, championId, enemyChampionId, null);
            setCoreItems(data);
        } catch (error) {
            console.error('Error fetching core items:', error);
        } finally {
            setCoreItemsLoading(false);
        }
    }, [puuid]);

    useEffect(() => {
        setFilteredDetails(details);
        setSelectedMatchup(null);
        setExpandedKeystone(null);
        if (details?.champion_id && puuid) {
            fetchCoreItems(details.champion_id, null);
        }
    }, [details, puuid, fetchCoreItems]);

    const clearMatchupFilter = () => {
        setSelectedMatchup(null);
        setExpandedKeystone(null);
        setFilteredDetails(details);
        fetchCoreItems(details?.champion_id, null);
    };

    const handleMatchupClick = async (enemyChampionId) => {
        if (!puuid) return;
        if (selectedMatchup === enemyChampionId) {
            clearMatchupFilter();
            return;
        }
        setFilterLoading(true);
        setSelectedMatchup(enemyChampionId);
        setExpandedKeystone(null);
        try {
            const championId = details?.champion_id;
            const data = await getChampionDetails(puuid, championId, enemyChampionId, null);
            setFilteredDetails(data);
            await fetchCoreItems(championId, enemyChampionId);
        } catch (error) {
            console.error('Error fetching filtered champion details:', error);
        } finally {
            setFilterLoading(false);
        }
    };

    // Group rune pages by keystone and canonicalize secondary-rune ordering
    // so [A, B] and [B, A] collapse into the same variation.
    const keystoneList = useMemo(() => {
        const runePages = filteredDetails?.rune_pages;
        if (!runePages || runePages.length === 0) return [];

        const byKeystone = {};
        runePages.forEach(entry => {
            const keystoneId = entry.page?.keystone;
            if (!keystoneId) return;

            if (!byKeystone[keystoneId]) {
                byKeystone[keystoneId] = {
                    keystone: keystoneId,
                    total_usage: 0,
                    total_wins: 0,
                    variations: {},
                };
            }

            const group = byKeystone[keystoneId];
            group.total_usage += entry.usage_count;
            group.total_wins += (entry.usage_count * entry.win_rate) / 100;

            // Sort secondary runes so order doesn't create distinct variations.
            const sortedSecondary = [...(entry.page.secondary_runes || [])].sort((a, b) => a - b);
            const shards = entry.page.shards || {};
            const shardsSig = [
                shards.offense || 0,
                shards.flex || 0,
                shards.defense || 0,
            ].join(',');
            const sig = `${sortedSecondary.join(',')}|${shardsSig}`;

            if (!group.variations[sig]) {
                group.variations[sig] = {
                    secondary_runes: sortedSecondary,
                    secondary_style: entry.page.secondary_style,
                    shards: shards,
                    usage_count: 0,
                    wins: 0,
                };
            }
            group.variations[sig].usage_count += entry.usage_count;
            group.variations[sig].wins += (entry.usage_count * entry.win_rate) / 100;
        });

        return Object.values(byKeystone)
            .map(g => ({
                ...g,
                win_rate: g.total_usage > 0 ? (g.total_wins / g.total_usage) * 100 : 0,
                variations: Object.values(g.variations)
                    .map(v => ({
                        ...v,
                        win_rate: v.usage_count > 0 ? (v.wins / v.usage_count) * 100 : 0,
                    }))
                    .sort((a, b) => b.usage_count - a.usage_count),
            }))
            .sort((a, b) => b.total_usage - a.total_usage);
    }, [filteredDetails]);

    if (loading || filterLoading || coreItemsLoading) {
        return <div className="loading-text">Loading champion details...</div>;
    }

    if (!filteredDetails || !filteredDetails.base_stats || filteredDetails.base_stats.games === 0) {
        return (
            <div className="empty-state">
                <p>No details available for this champion.</p>
            </div>
        );
    }

    const {
        base_stats,
        stat_shards,
        spells,
        matchups,
        skill_orders,
        starting_items,
    } = filteredDetails;
    const totalGames = base_stats.games;

    return (
        <div className="champion-detail">
            {/* Champion Header */}
            <div className="champion-detail-header">
                <ChampionAsset
                    championId={filteredDetails.champion_id}
                    type="icon"
                    size="large"
                    championMap={championMap}
                />
                <div className="champion-detail-title">
                    <h3>{getChampionName(filteredDetails.champion_id)}</h3>
                    <span className="champion-games">
                        {selectedMatchup ? `vs ${getChampionName(selectedMatchup)}` : `${totalGames} games`}
                    </span>
                    {selectedMatchup && (
                        <button
                            className="clear-filter-btn"
                            onClick={clearMatchupFilter}
                        >
                            Clear Filter
                        </button>
                    )}
                </div>
            </div>

            {/* Base Stats */}
            <div className="stat-grid">
                <div className="stat-card">
                    <span className="stat-label">Games</span>
                    <span className="stat-value">{totalGames}</span>
                </div>
                <div className="stat-card">
                    <span className="stat-label">Win Rate</span>
                    <span className={`stat-value ${base_stats.win_rate >= 50 ? 'positive' : 'negative'}`}>
                        {base_stats.win_rate}%
                    </span>
                </div>
                <div className="stat-card">
                    <span className="stat-label">KDA</span>
                    <span className="stat-value">
                        {base_stats.avg_kills}/{base_stats.avg_deaths}/{base_stats.avg_assists}
                    </span>
                </div>
            </div>

            {/* Skill Order */}
            {skill_orders && skill_orders.length > 0 && (
                <div className="detail-section">
                    <div className="section-header">
                        <h4>Skill Order</h4>
                        <button
                            className="toggle-btn"
                            onClick={() => setShowSkillOrder(!showSkillOrder)}
                        >
                            {showSkillOrder ? '▼' : '▶'}
                        </button>
                    </div>

                    {showSkillOrder && (() => {
                        const groupedOrders = {};
                        skill_orders.forEach(order => {
                            if (!order.skill_order) return;
                            if (order.skill_order.length < 13) return;
                            const key = order.skill_order.slice(0, 13);
                            if (!groupedOrders[key]) {
                                groupedOrders[key] = {
                                    skill_order: key,
                                    usage_count: 0,
                                    variations: []
                                };
                            }
                            groupedOrders[key].usage_count += order.usage_count;
                            groupedOrders[key].variations.push(order);
                        });

                        const sortedGroups = Object.values(groupedOrders)
                            .sort((a, b) => b.usage_count - a.usage_count)
                            .slice(0, 5);

                        if (sortedGroups.length === 0) {
                            return (
                                <div className="skill-order-empty">
                                    <p>No skill order data with 13+ levels available.</p>
                                </div>
                            );
                        }

                        const abilities = ['Q', 'W', 'E', 'R'];
                        const totalLevels = 13;

                        const getAbilityPriority = (order) => {
                            const priorityAbilities = ['Q', 'W', 'E'];
                            const counts = {};
                            const addedToPriority = {};
                            priorityAbilities.forEach(ability => {
                                counts[ability] = 0;
                                addedToPriority[ability] = false;
                            });
                            const priorityOrder = [];
                            for (let i = 0; i < order.length && i < totalLevels; i++) {
                                const ability = order[i];
                                if (priorityAbilities.includes(ability)) {
                                    counts[ability]++;
                                    if (counts[ability] === 5 && !addedToPriority[ability]) {
                                        priorityOrder.push(ability);
                                        addedToPriority[ability] = true;
                                    }
                                }
                            }
                            const firstAppearance = {};
                            priorityAbilities.forEach(ability => { firstAppearance[ability] = null; });
                            for (let i = 0; i < order.length && i < totalLevels; i++) {
                                const ability = order[i];
                                if (priorityAbilities.includes(ability)) {
                                    if (firstAppearance[ability] === null) {
                                        firstAppearance[ability] = i + 1;
                                    }
                                }
                            }
                            const remaining = priorityAbilities
                                .filter(ability => counts[ability] > 0 && !addedToPriority[ability])
                                .sort((a, b) => (firstAppearance[a] || 999) - (firstAppearance[b] || 999));
                            const finalOrder = [...priorityOrder, ...remaining];
                            return finalOrder.join(' > ');
                        };

                        return (
                            <div className="skill-order-container">
                                {sortedGroups.map((group, idx) => {
                                    const order = group.skill_order;
                                    const priority = getAbilityPriority(order);
                                    const orderMap = {};
                                    abilities.forEach(ability => {
                                        orderMap[ability] = Array(totalLevels).fill(null);
                                    });
                                    for (let i = 0; i < order.length && i < totalLevels; i++) {
                                        const ability = order[i];
                                        if (abilities.includes(ability)) {
                                            orderMap[ability][i] = i + 1;
                                        }
                                    }
                                    return (
                                        <div key={idx} className="skill-order-grid-wrapper">
                                            <div className="skill-order-grid-header">
                                                <span className="skill-order-priority">Priority: {priority}</span>
                                                <span className="skill-order-usage">
                                                    {formatCount(group.usage_count, totalGames)}
                                                </span>
                                            </div>
                                            <div className="skill-order-grid">
                                                {abilities.map((ability) => (
                                                    <div key={ability} className="skill-order-grid-row">
                                                        <div className="skill-order-grid-cell ability-icon-cell">
                                                            <ChampionAsset
                                                                championId={filteredDetails.champion_id}
                                                                type="ability"
                                                                ability={ability}
                                                                size="small"
                                                            />
                                                        </div>
                                                        {Array.from({ length: totalLevels }, (_, levelIndex) => {
                                                            const levelNumber = orderMap[ability][levelIndex];
                                                            return (
                                                                <div
                                                                    key={levelIndex}
                                                                    className={`skill-order-grid-cell skill-square ${levelNumber ? 'filled' : 'empty'}`}
                                                                >
                                                                    {levelNumber && <span className="skill-level-number">{levelNumber}</span>}
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        );
                    })()}
                </div>
            )}

            {/* Core Items */}
            {coreItems && (coreItems.first.length > 0 || coreItems.second.length > 0 || coreItems.third.length > 0 || coreItems.fourth.length > 0) && (
                <div className="detail-section">
                    <h4>Core Items</h4>
                    <div className="core-items-grid">
                        {coreItems.first && coreItems.first.length > 0 && (
                            <div className="core-items-column">
                                <span className="core-items-label">1st Core Item</span>
                                <div className="core-items-list">
                                    {coreItems.first.slice(0, 5).map((item, idx) => (
                                        <div key={idx} className="core-item">
                                            <GameAsset type="item" id={item.item_id} size="medium" />
                                            <span className="core-item-usage">{item.usage_count}g</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {coreItems.second && coreItems.second.length > 0 && (
                            <div className="core-items-column">
                                <span className="core-items-label">2nd Core Item</span>
                                <div className="core-items-list">
                                    {coreItems.second.slice(0, 5).map((item, idx) => (
                                        <div key={idx} className="core-item">
                                            <GameAsset type="item" id={item.item_id} size="medium" />
                                            <span className="core-item-usage">{item.usage_count}g</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {coreItems.third && coreItems.third.length > 0 && (
                            <div className="core-items-column">
                                <span className="core-items-label">3rd Core Item</span>
                                <div className="core-items-list">
                                    {coreItems.third.slice(0, 5).map((item, idx) => (
                                        <div key={idx} className="core-item">
                                            <GameAsset type="item" id={item.item_id} size="medium" />
                                            <span className="core-item-usage">{item.usage_count}g</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {coreItems.fourth && coreItems.fourth.length > 0 && (
                            <div className="core-items-column">
                                <span className="core-items-label">4th Core Item</span>
                                <div className="core-items-list">
                                    {coreItems.fourth.slice(0, 5).map((item, idx) => (
                                        <div key={idx} className="core-item">
                                            <GameAsset type="item" id={item.item_id} size="medium" />
                                            <span className="core-item-usage">{item.usage_count}g</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Starting Items */}
            {starting_items && starting_items.length > 0 && (
                <div className="detail-section">
                    <h4>Starting Items</h4>
                    <div className="starting-items-grid">
                        {starting_items.slice(0, 8).map((item, idx) => (
                            <div key={idx} className="starting-item">
                                <GameAsset type="item" id={item.item_id} size="medium" />
                                <span className="item-usage">
                                    {formatCount(item.usage_count, totalGames)}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Keystones (grouped, expandable) */}
            {keystoneList.length > 0 && (
                <div className="detail-section">
                    <h4>Keystones</h4>
                    <div className="keystone-list">
                        {keystoneList.map((ks) => {
                            const isExpanded = expandedKeystone === ks.keystone;
                            return (
                                <div key={ks.keystone} className="keystone-group">
                                    <div
                                        className={`keystone-header ${isExpanded ? 'expanded' : ''}`}
                                        onClick={() => setExpandedKeystone(isExpanded ? null : ks.keystone)}
                                    >
                                        <GameAsset type="rune" id={ks.keystone} size="medium" />
                                        <span className="keystone-name">
                                            {runeMapReady
                                                ? (getRuneName(ks.keystone) || `Rune ${ks.keystone}`)
                                                : '...'}
                                        </span>
                                        <span className="keystone-usage">
                                            {formatCount(ks.total_usage, totalGames)}
                                        </span>
                                        <span className={`keystone-winrate ${ks.win_rate >= 50 ? 'positive' : 'negative'}`}>
                                            {ks.win_rate.toFixed(1)}%
                                        </span>
                                        <span className="keystone-expand">
                                            {isExpanded ? '▼' : '▶'}
                                        </span>
                                    </div>

                                    {isExpanded && (
                                        <div className="keystone-variations">
                                            {ks.variations.map((v, idx) => (
                                                <div key={idx} className="rune-variation">
                                                    <div className="rune-variation-header">
                                                        <span className="rune-variation-usage">
                                                            {formatCount(v.usage_count, totalGames)}
                                                        </span>
                                                        <span className={`rune-variation-winrate ${v.win_rate >= 50 ? 'positive' : 'negative'}`}>
                                                            {v.win_rate.toFixed(1)}%
                                                        </span>
                                                    </div>
                                                    <div className="rune-variation-row">
                                                        {v.secondary_runes.map((runeId, i) => (
                                                            <GameAsset
                                                                key={`sec-${i}`}
                                                                type="rune"
                                                                id={runeId}
                                                                size="small"
                                                            />
                                                        ))}
                                                        <span className="rune-variation-divider" />
                                                        {v.shards.offense > 0 && (
                                                            <GameAsset
                                                                type="rune"
                                                                id={v.shards.offense}
                                                                slot="shard_offense"
                                                                size="small"
                                                            />
                                                        )}
                                                        {v.shards.flex > 0 && (
                                                            <GameAsset
                                                                type="rune"
                                                                id={v.shards.flex}
                                                                slot="shard_flex"
                                                                size="small"
                                                            />
                                                        )}
                                                        {v.shards.defense > 0 && (
                                                            <GameAsset
                                                                type="rune"
                                                                id={v.shards.defense}
                                                                slot="shard_defense"
                                                                size="small"
                                                            />
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Stat Shards fallback (only if keystone list is empty) */}
            {keystoneList.length === 0 && stat_shards && stat_shards.length > 0 && (
                <div className="detail-section">
                    <h4>Stat Shards</h4>
                    <div className="rune-grid">
                        {stat_shards.map((shard) => (
                            <div key={`${shard.slot}-${shard.rune_id}`} className="rune-item">
                                <GameAsset type="rune" id={shard.rune_id} slot={shard.slot} size="small" />
                                <span className="rune-usage">
                                    {formatCount(shard.usage_count, totalGames)}
                                </span>
                                <span className={`rune-winrate ${shard.win_rate >= 50 ? 'positive' : 'negative'}`}>
                                    {shard.win_rate}%
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Summoner Spells */}
            {spells && spells.length > 0 && (
                <div className="detail-section">
                    <h4>Common Summoner Spells</h4>
                    <div className="spell-grid">
                        {spells.slice(0, 5).map((spell, idx) => (
                            <div key={idx} className="spell-item">
                                <div className="spell-icons">
                                    <GameAsset type="spell" id={spell.summoner_spell_d} size="small" />
                                    <GameAsset type="spell" id={spell.summoner_spell_f} size="small" />
                                </div>
                                <span className="spell-usage">
                                    {formatCount(spell.usage_count, totalGames)}
                                </span>
                                <span className={`spell-winrate ${spell.win_rate >= 50 ? 'positive' : 'negative'}`}>
                                    {spell.win_rate}%
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Matchups */}
            {matchups && matchups.length > 0 && (
                <div className="detail-section">
                    <h4>Matchups {selectedMatchup && `(Filtered: ${getChampionName(selectedMatchup)})`}</h4>
                    {selectedMatchup && (
                        <button
                            className="clear-filter-btn"
                            onClick={clearMatchupFilter}
                        >
                            Clear Filter
                        </button>
                    )}
                    <div className="matchup-grid">
                        {matchups
                            .filter(m => !selectedMatchup || m.enemy_champion_id === selectedMatchup)
                            .map((matchup) => (
                                <div
                                    key={matchup.enemy_champion_id}
                                    className={`matchup-item ${selectedMatchup === matchup.enemy_champion_id ? 'active' : ''}`}
                                    onClick={() => handleMatchupClick(matchup.enemy_champion_id)}
                                >
                                    <ChampionAsset
                                        championId={matchup.enemy_champion_id}
                                        type="icon"
                                        size="small"
                                        championMap={championMap}
                                    />
                                    <span className="matchup-games">
                                        {formatCount(matchup.games, totalGames)}
                                    </span>
                                    <span className={`matchup-winrate ${matchup.win_rate >= 50 ? 'positive' : 'negative'}`}>
                                        {matchup.win_rate}%
                                    </span>
                                </div>
                            ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ChampionDetail;