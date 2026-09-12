// frontend/src/components/ChampionList.jsx
import React, { useState } from 'react';
import './ChampionList.css';

const ChampionList = ({ champions, onSelectChampion, selectedChampionId, loading, getChampionName }) => {
    if (loading) {
        return <div className="loading-text">Loading champions...</div>;
    }

    if (!champions || champions.length === 0) {
        return (
            <div className="empty-state">
                <p>No champions found.</p>
                <p className="hint">Click "Refresh Data" to fetch matches.</p>
            </div>
        );
    }

    return (
        <div className="champion-list">
            {champions.map((champ) => (
                <button
                    key={champ.champion_id}
                    className={`champion-btn ${selectedChampionId === champ.champion_id ? 'active' : ''}`}
                    onClick={() => onSelectChampion(champ.champion_id)}
                >
                    <div className="champion-item">
                        <span className="champion-name">{getChampionName(champ.champion_id)}</span>
                        <span className="champion-games">{champ.games} games</span>
                        <span className={`champion-winrate ${champ.win_rate >= 50 ? 'positive' : 'negative'}`}>
                            {champ.win_rate}%
                        </span>
                    </div>
                </button>
            ))}
        </div>
    );
};

export default ChampionList;