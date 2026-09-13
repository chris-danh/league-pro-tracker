// frontend/src/components/ChampionAsset.jsx
import React, { useState, useEffect } from 'react';
import './Assets.css';
import { getChampionAbilityMap, getLatestDDragonVersion } from '../api/client';

const ChampionAsset = ({
    championId,
    type = 'icon',
    ability = null,
    size = 'small',
    className = '',
    championMap = null
}) => {
    const [imageUrl, setImageUrl] = useState(null);
    const [championName, setChampionName] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
        const loadAsset = async () => {
            if (!championId) {
                setLoading(false);
                setError(true);
                return;
            }

            try {
                let url = null;
                let name = null;

                if (type === 'icon') {
                    if (championMap) {
                        const info = championMap.get(championId);
                        if (info && info.key) {
                            const version = await getLatestDDragonVersion();
                            url = `https://ddragon.leagueoflegends.com/cdn/${version}/img/champion/${info.key}.png`;
                            name = info.name;
                        }
                    }
                } else if (type === 'ability' && ability) {
                    const map = await getChampionAbilityMap();
                    const abilityIndexMap = { 'Q': 0, 'W': 1, 'E': 2, 'R': 3 };
                    const index = abilityIndexMap[ability];

                    if (index !== undefined && map[championId]?.spells?.[index]) {
                        const spell = map[championId].spells[index];
                        url = spell.image;
                        name = map[championId].name;
                    }
                } else if (type === 'splash') {
                    if (championMap) {
                        const info = championMap.get(championId);
                        if (info && info.key) {
                            url = `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${info.key}_0.jpg`;
                            name = info.name;
                        }
                    }
                }

                if (url) {
                    setImageUrl(url);
                    setChampionName(name || `Champion ${championId}`);
                    setError(false);
                } else {
                    setError(true);
                    setChampionName(name || `Champion ${championId}`);
                }
            } catch (err) {
                console.error('Error loading champion asset:', err);
                setError(true);
            } finally {
                setLoading(false);
            }
        };

        loadAsset();
    }, [championId, type, ability, championMap]);

    const sizeClass = {
        'small': 'asset-small',
        'medium': 'asset-medium',
        'large': 'asset-large',
    }[size] || 'asset-small';

    const getFallbackLetter = () => {
        if (type === 'ability' && ability) return ability;
        if (championName && championName.startsWith('Champion')) return '?';
        if (championName) return championName.charAt(0).toUpperCase();
        return '?';
    };

    const getFallbackClass = () => {
        if (type === 'ability' && ability) {
            return `ability-${ability}`;
        }
        return '';
    };

    if (loading) {
        return (
            <div className={`champion-asset ${sizeClass} loading ${className}`}>
                <span>{type === 'ability' ? ability : '?'}</span>
            </div>
        );
    }

    if (error || !imageUrl) {
        return (
            <div className={`champion-asset ${sizeClass} fallback ${getFallbackClass()} ${className}`}>
                <span>{getFallbackLetter()}</span>
            </div>
        );
    }

    return (
        <div className={`champion-asset ${sizeClass} ${className}`}>
            <img
                src={imageUrl}
                alt={championName || `Champion ${championId}`}
                loading="lazy"
                onError={() => setError(true)}
            />
        </div>
    );
};

export default ChampionAsset;