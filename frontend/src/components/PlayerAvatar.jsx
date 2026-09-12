// frontend/src/components/PlayerAvatar.jsx
import React, { useState, useEffect } from 'react';
import './Assets.css';
import { getPlayerPortrait } from '../utils/playerPortraits';

const PlayerAvatar = ({ player, size = 'medium', className = '' }) => {
    const [imageError, setImageError] = useState(false);
    const [imageUrl, setImageUrl] = useState(null);

    // Set the image URL when player changes
    useEffect(() => {
        if (!player || !player.name) {
            setImageError(true);
            setImageUrl(null);
            return;
        }

        const url = getPlayerPortrait(player.name);
        console.log('🎯 PlayerAvatar: Setting imageUrl to:', url);
        
        setImageUrl(url);
        setImageError(false);  // ✅ Reset error when player changes
    }, [player]);

    // ✅ Also reset error when imageUrl changes
    useEffect(() => {
        setImageError(false);
    }, [imageUrl]);

    const sizeClass = {
        'small': 'avatar-small',
        'medium': 'avatar-medium',
        'large': 'avatar-large',
    }[size] || 'avatar-medium';

    // Show fallback if error or no URL
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
                onLoad={() => console.log('✅ PlayerAvatar: Image loaded:', imageUrl)}
                onError={() => {
                    console.log('❌ PlayerAvatar: Image failed:', imageUrl);
                    setImageError(true);
                }}
                loading="lazy"
            />
        </div>
    );
};

export default PlayerAvatar;