// frontend/src/components/PracticeTable.jsx
import React, { useState } from 'react';
import './PracticeTable.css';

const PracticeTable = ({ data, loading, getChampionName }) => {
    const [sortBy, setSortBy] = useState('games');

    if (loading) {
        return (
            <div className="practice-loading">
                <div className="loading-spinner"></div>
                <p>Loading practice data...</p>
            </div>
        );
    }

    if (!data || !data.champions || data.champions.length === 0) {
        return (
            <div className="practice-empty">
                <p>No practice data available.</p>
                <p className="hint">Click "Refresh Data" to fetch matches.</p>
            </div>
        );
    }

    // Sort champions based on selection
    const sortedChampions = [...data.champions];
    if (sortBy === 'games') {
        sortedChampions.sort((a, b) => b.games - a.games);
    } else if (sortBy === 'winrate') {
        sortedChampions.sort((a, b) => b.win_rate - a.win_rate);
    } else if (sortBy === 'kda') {
        sortedChampions.sort((a, b) => b.kda - a.kda);
    }

    return (
        <div className="practice-table-container">
            <div className="practice-header">
                <div>
                    <h3>Practice Champions</h3>
                    <div className="practice-stats">
                        <span>{data.total_games} total games</span>
                        <span>•</span>
                        <span>{data.champions.length} champions</span>
                    </div>
                </div>
                <div className="sort-controls">
                    <label htmlFor="sort-select">Sort by: </label>
                    <select
                        id="sort-select"
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value)}
                    >
                        <option value="games">Games</option>
                        <option value="winrate">Win Rate</option>
                        <option value="kda">KDA</option>
                    </select>
                </div>
            </div>

            <table className="champion-table">
                <thead>
                    <tr>
                        <th>Champion</th>
                        <th>Games</th>
                        <th>Win Rate</th>
                        <th>KDA</th>
                    </tr>
                </thead>
                <tbody>
                    {sortedChampions.map((champ) => (
                        <tr key={champ.champion_id}>
                            <td className="champion-name">
                                {getChampionName(champ.champion_id)}
                            </td>
                            <td>{champ.games}</td>
                            <td className={champ.win_rate >= 50 ? 'positive' : 'negative'}>
                                {champ.win_rate}%
                            </td>
                            <td>{champ.kda}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default PracticeTable;