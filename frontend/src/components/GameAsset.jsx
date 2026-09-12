// frontend/src/components/GameAsset.jsx
import React, { useState, useEffect } from 'react';
import { getItemMap, getRuneDetails, getSummonerSpellMap } from '../api/client';

const GameAsset = ({
    type,
    id,
    slot = null,   // ← new: passes shard slot through to the lookup
    size = 'small',
    className = ''
}) => {
    const [imageUrl, setImageUrl] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
        const loadAsset = async () => {
            if (!id) {
                setLoading(false);
                setError(true);
                return;
            }

            try {
                if (type === 'item') {
                    const map = await getItemMap();
                    const item = map.get(id);
                    setImageUrl(item?.image || null);
                } else if (type === 'rune') {
                    const rune = await getRuneDetails(id, slot);
                    setImageUrl(rune?.image || null);
                } else if (type === 'spell') {
                    const map = await getSummonerSpellMap();
                    const spell = map.get(id);
                    setImageUrl(spell?.image || null);
                }
            } catch (err) {
                console.error(`Error loading ${type}:`, err);
                setError(true);
            } finally {
                setLoading(false);
            }
        };

        loadAsset();
    }, [type, id, slot]);

    const sizeClass = {
        'small': 'asset-small',
        'medium': 'asset-medium',
        'large': 'asset-large',
    }[size] || 'asset-small';

    if (loading) {
        return <div className={`game-asset ${sizeClass} loading ${className}`} />;
    }

    if (error || !imageUrl) {
        return <div className={`game-asset ${sizeClass} empty ${className}`}>◻</div>;
    }

    return (
        <div className={`game-asset ${sizeClass} ${className}`}>
            <img src={imageUrl} alt={`${type} ${id}`} loading="lazy" />
        </div>
    );
};

export default GameAsset;