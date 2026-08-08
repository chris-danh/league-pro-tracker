// frontend/src/components/PlayerDetail.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import './PlayerDetail.css';
import PracticeTable from './PracticeTable';
import { getPracticeStats, refreshPlayer } from '../api/client';

const PlayerDetail = ({ getPlayerByName, getChampionName }) => {
    const { playerName } = useParams();
    const navigate = useNavigate();
    const [player, setPlayer] = useState(null);
    const [practiceData, setPracticeData] = useState(null);
    const [loading, setLoading] = useState({ player: true, practice: false, refresh: false });
    const [refreshMessage, setRefreshMessage] = useState(null);

    useEffect(() => {
        // Find player by name
        const found = getPlayerByName(playerName);
        if (found) {
            setPlayer(found);
            loadPracticeData(found.puuid);
        }
        setLoading(prev => ({ ...prev, player: false }));
    }, [playerName]);

    const loadPracticeData = async (puuid) => {
        setLoading(prev => ({ ...prev, practice: true }));
        try {
            const data = await getPracticeStats(puuid);
            setPracticeData(data);
        } catch (error) {
            console.error('Failed to load practice stats:', error);
            setPracticeData(null);
        } finally {
            setLoading(prev => ({ ...prev, practice: false }));
        }
    };

    const handleRefresh = async () => {
        if (!player) return;

        setLoading(prev => ({ ...prev, refresh: true }));
        setRefreshMessage(null);

        try {
            const result = await refreshPlayer(player.name, player.tag);
            setRefreshMessage({
                type: 'success',
                text: `Refreshed! ${result.matches_saved || result.matches_fetched} matches saved.`
            });
            await loadPracticeData(player.puuid);
        } catch (error) {
            setRefreshMessage({
                type: 'error',
                text: error.message || 'Failed to refresh data'
            });
        } finally {
            setLoading(prev => ({ ...prev, refresh: false }));
        }
    };

    // Navigate back to home
    const handleBack = () => {
        navigate('/');
    };

    if (loading.player) {
        return <div className="loading-text">Loading player...</div>;
    }

    if (!player) {
        return (
            <div className="empty-state">
                <h2>Player not found</h2>
                <p>Could not find "{playerName}"</p>
                <button onClick={handleBack} className="back-button">← Back to players</button>
            </div>
        );
    }

    return (
        <div className="player-detail">
            <div className="player-detail-header">
                <button onClick={handleBack} className="back-button">← Back</button>
                <div className="player-detail-info">
                    <h2>{player.name}</h2>
                    <span className="team-badge">{player.team || 'Free Agent'}</span>
                    <span className="region-badge">{player.region}</span>
                    <span className="tag-badge">#{player.tag}</span>
                </div>
                <button
                    className={`refresh-btn ${loading.refresh ? 'loading' : ''}`}
                    onClick={handleRefresh}
                    disabled={loading.refresh}
                >
                    {loading.refresh ? '⏳ Fetching...' : '🔄 Refresh Data'}
                </button>
            </div>

            {refreshMessage && (
                <div className={`refresh-message ${refreshMessage.type}`}>
                    {refreshMessage.text}
                </div>
            )}

            <PracticeTable
                data={practiceData}
                loading={loading.practice}
                getChampionName={getChampionName}
            />
        </div>
    );
};

export default PlayerDetail;