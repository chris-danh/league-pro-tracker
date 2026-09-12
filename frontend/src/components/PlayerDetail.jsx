// frontend/src/components/PlayerDetail.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import './PlayerDetail.css';
import ChampionList from './ChampionList';
import ChampionDetail from './ChampionDetail';
import MatchHistory from './MatchHistory';
import PlayerAvatar from './PlayerAvatar';

const PlayerDetail = ({
    players,
    selectedPlayer,
    champions,
    championDetails,
    matches,
    totalMatches,
    loading,
    getChampionName,
    championMap,
    selectedChampionId,
    onSelectChampion,
    onLoadMoreMatches,
    onRefresh,
    onBack
}) => {
    const { playerName } = useParams();
    const navigate = useNavigate();
    const [player, setPlayer] = useState(null);

    useEffect(() => {
        if (selectedPlayer && selectedPlayer.name.toLowerCase() === playerName.toLowerCase()) {
            setPlayer(selectedPlayer);
            return;
        }
        if (players && players.length > 0) {
            const found = players.find(p => p.name.toLowerCase() === playerName.toLowerCase());
            setPlayer(found || null);
        }
    }, [playerName, players, selectedPlayer]);

    const handleBack = () => {
        if (onBack) {
            onBack();
        }
        navigate('/');
    };

    // ✅ Calculate hasMore
    const hasMore = matches.length < totalMatches;

    if (loading.players && !player) {
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
        {/* Header */}
        <div className="player-detail-header">
            <button onClick={handleBack} className="back-button">← Back</button>
            <div className="player-detail-info">
                <PlayerAvatar player={player} size="large" />
                <div className="player-info-text">
                    {/* Line 1: Player Name (e.g., "GEN Kiin" or "T1 Faker") */}
                    <h2>{player.name}</h2>
                    {/* Line 2: Region + IGN + Tagline */}
                    <div className="player-meta">
                        <span className="region-badge">{player.region}</span>
                        <span className="ign-tag">{player.ign} #{player.tag}</span>
                    </div>
                </div>
            </div>
            <button
                className={`refresh-btn ${loading.refresh ? 'loading' : ''}`}
                onClick={onRefresh}
                disabled={loading.refresh || !player}
            >
                {loading.refresh ? '⏳ Fetching...' : '🔄 Refresh Data'}
            </button>
        </div>

            {/* Two-column layout */}
            <div className="player-content">
                {/* Left column */}
                <div className="left-column">
                    <div className="section">
                        <h3>Champions Played</h3>
                        <ChampionList
                            champions={champions}
                            loading={loading.champions}
                            selectedChampionId={selectedChampionId}
                            onSelectChampion={onSelectChampion}
                            getChampionName={getChampionName}
                        />
                    </div>

                    <ChampionDetail
                        details={championDetails}
                        loading={loading.championDetails}
                        getChampionName={getChampionName}
                        championMap={championMap}
                        puuid={player?.puuid}
                        onRefresh={onRefresh}
                    />
                </div>

                {/* Right column */}
                <div className="right-column">
                    <div className="section">
                        <h3>Match History</h3>
                        <MatchHistory
                            matches={matches}
                            loading={loading.matches}
                            getChampionName={getChampionName}
                            championMap={championMap}
                            onLoadMore={onLoadMoreMatches}
                            hasMore={hasMore}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PlayerDetail;