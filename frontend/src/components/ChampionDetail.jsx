// frontend/src/components/ChampionDetail.jsx
import React, { useState, useEffect, useCallback } from 'react';
import './ChampionDetail.css';
import ChampionAsset from './ChampionAsset';
import GameAsset from './GameAsset';
import { getChampionDetails, getCoreItems } from '../api/client';

const ChampionDetail = ({
    details,
    loading,
    getChampionName,
    championMap,
    puuid,
    onRefresh
}) => {
    const [selectedMatchup, setSelectedMatchup] = useState(null);
    const [showSkillOrder, setShowSkillOrder] = useState(true);
    const [filteredDetails, setFilteredDetails] = useState(details);
    const [filterLoading, setFilterLoading] = useState(false);
    const [coreItems, setCoreItems] = useState({
        first: [], second: [], third: [], fourth: []
    });
    const [coreItemsLoading, setCoreItemsLoading] = useState(false);

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
        if (details?.champion_id && puuid) {
            fetchCoreItems(details.champion_id, null);
        }
    }, [details, puuid, fetchCoreItems]);

    const formatCount = (occurrences, totalGames) => {
        if (!totalGames || totalGames === 0) return '0 / 0';
        return `${occurrences} / ${totalGames}`;
    };

    const handleMatchupClick = async (enemyChampionId) => {
        if (!puuid) return;
        if (selectedMatchup === enemyChampionId) {
            setSelectedMatchup(null);
            setFilteredDetails(details);
            fetchCoreItems(details?.champion_id, null);
            return;
        }
        setFilterLoading(true);
        setSelectedMatchup(enemyChampionId);
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
        rune_pages,
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
                            onClick={() => {
                                setSelectedMatchup(null);
                                setFilteredDetails(details);
                                fetchCoreItems(details?.champion_id, null);
                            }}
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
                <div className="stat-card">
                    <span className="stat-label">Avg CS</span>
                    <span className="stat-value">{base_stats.avg_cs}</span>
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

            {/* ============================================
                RUNE PAGES (grouped by page)
                ============================================ */}
            {rune_pages && rune_pages.length > 0 && (
                <div className="detail-section">
                    <h4>Rune Pages</h4>
                    <div className="rune-pages-container">
                        {rune_pages.map((pageEntry, idx) => {
                            const page = pageEntry.page;
                            return (
                                <div key={idx} className="rune-page">
                                    <div className="rune-page-header">
                                        <span className="rune-page-usage">
                                            {formatCount(pageEntry.usage_count, totalGames)}
                                        </span>
                                        <span className={`rune-page-winrate ${pageEntry.win_rate >= 50 ? 'positive' : 'negative'}`}>
                                            {pageEntry.win_rate}%
                                        </span>
                                    </div>

                                    {/* Primary tree */}
                                    {page.primary_runes && page.primary_runes.length > 0 && (
                                        <div className="rune-page-row primary-tree">
                                            {page.primary_runes.map((runeId, i) => (
                                                <GameAsset key={`p-${i}`} type="rune" id={runeId} size="small" />
                                            ))}
                                        </div>
                                    )}

                                    {/* Secondary tree */}
                                    {page.secondary_runes && page.secondary_runes.length > 0 && (
                                        <div className="rune-page-row secondary-tree">
                                            {page.secondary_runes.map((runeId, i) => (
                                                <GameAsset key={`s-${i}`} type="rune" id={runeId} size="small" />
                                            ))}
                                        </div>
                                    )}

                                    {/* Stat shards */}
                                    {page.shards && (
                                        <div className="rune-page-row shards">
                                            {page.shards.offense > 0 && (
                                                <GameAsset type="rune" id={page.shards.offense} slot="shard_offense" size="small" />
                                            )}
                                            {page.shards.flex > 0 && (
                                                <GameAsset type="rune" id={page.shards.flex} slot="shard_flex" size="small" />
                                            )}
                                            {page.shards.defense > 0 && (
                                                <GameAsset type="rune" id={page.shards.defense} slot="shard_defense" size="small" />
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Stat Shards (flat list — kept as fallback if rune_pages not present) */}
            {(!rune_pages || rune_pages.length === 0) && stat_shards && stat_shards.length > 0 && (
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
                            onClick={() => {
                                setSelectedMatchup(null);
                                setFilteredDetails(details);
                                fetchCoreItems(details?.champion_id, null);
                            }}
                        >
                            Clear Filter
                        </button>
                    )}
                    <div className="matchup-grid">
                        {matchups
                            .filter(m => !selectedMatchup || m.enemy_champion_id === selectedMatchup)
                            .slice(0, 15)
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