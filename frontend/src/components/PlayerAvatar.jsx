// frontend/src/components/PlayerAvatar.jsx
import React, { useState, useEffect } from 'react';
import './PlayerAvatar.css';
import { getPlayerPortrait } from '../utils/playerPortraits';

const PlayerAvatar = ({ player, size = 'medium', className = '' }) => {
    const [imageError, setImageError] = useState(false);
    const [imageUrl, setImageUrl] = useState(null);

    useEffect(() => {
        if (!player || !player.name) {
            setImageError(true);
            setImageUrl(null);
            return;
        }

        const url = getPlayerPortrait(player.name);
        setImageUrl(url);
        setImageError(false);
    }, [player]);

    const sizeClass = {
        'small': 'avatar-small',
        'medium': 'avatar-medium',
        'large': 'avatar-large',
    }[size] || 'avatar-medium';

    if (imageError || !imageUrl) {
        const initials = player?.name?.charAt(0)?.toUpperCase() || '?';
        return (
            <div className={`player-avatar ${sizeClass} avatar-fallback ${className}`}>
                <span>{initials}</span>
            </div>
        );
    }

    return (
        <div className={`player-avatar ${sizeClass} ${className}`}>
            <img
                src={imageUrl}
                alt={player.name}
                onError={() => setImageError(true)}
                loading="lazy"
            />
        </div>
    );
};

export default PlayerAvatar;