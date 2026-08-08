// frontend/src/api/client.js
import axios from 'axios';

// API base URL - change this when deploying
const API_BASE = process.env.REACT_APP_API_URL;
const DD_BASE = 'https://ddragon.leagueoflegends.com';

// Create axios instance with default config
const api = axios.create({
    baseURL: API_BASE,
    timeout: 30000, // 30 seconds for refresh operations
    headers: {
        'Content-Type': 'application/json',
    },
});

// ============================================
// API FUNCTIONS
// ============================================

/**
 * Get all tracked pro players
 * GET /players
 */
export const getPlayers = async () => {
    try {
        const response = await api.get('/players');
        return response.data;
    } catch (error) {
        console.error('Error fetching players:', error);
        throw error;
    }
};

/**
 * Get practice stats for a specific player
 * GET /player/{puuid}/practice
 * 
 * @param {string} puuid - Player's PUUID
 * @param {string} sortBy - Sort by 'games', 'winrate', or 'kda'
 * @param {number} minGames - Minimum games required
 * @param {number} limit - Number of champions to return
 */
export const getPracticeStats = async (puuid, sortBy = 'games', minGames = 3, limit = 10) => {
    try {
        const response = await api.get(`/player/${puuid}/practice`, {
            params: {
                sort_by: sortBy,
                min_games: minGames,
                limit: limit,
            },
        });
        return response.data;
    } catch (error) {
        console.error('Error fetching practice stats:', error);
        throw error;
    }
};

/**
 * Refresh a player's match data from Riot API
 * POST /player/refresh
 * 
 * @param {string} gameName - Player's IGN (e.g., 'Hide on bush')
 * @param {string} tagLine - Player's tagline (e.g., 'KR1')
 * @param {number} matchCount - Number of matches to fetch
 * @param {boolean} includeTimeline - Whether to fetch timeline data
 */
export const refreshPlayer = async (gameName, tagLine, matchCount = 20, includeTimeline = true) => {
    try {
        const response = await api.post('/player/refresh', null, {
            params: {
                game_name: gameName,
                tag_line: tagLine,
                match_count: matchCount,
                include_timeline: includeTimeline,
            },
        });
        return response.data;
    } catch (error) {
        console.error('Error refreshing player:', error);
        throw error;
    }
};

/**
 * Health check - verify API is running
 * GET /
 */
export const checkHealth = async () => {
    try {
        const response = await api.get('/');
        return response.data;
    } catch (error) {
        console.error('API health check failed:', error);
        throw error;
    }
};

/**
 * Fetches champion data from Data Dragon and builds a mapping of ID -> Name.
 * @returns {Promise<Map<number, string>>} A map where the key is champion ID and the value is the champion name.
 */
export const getChampionMap = async () => {
    try {
        // 1. Get the latest patch version
        const versionResponse = await axios.get(`${DD_BASE}/api/versions.json`);
        const latestVersion = versionResponse.data[0]; // The first element is the latest version

        // 2. Get champion data for that version
        const championResponse = await axios.get(`${DD_BASE}/cdn/${latestVersion}/data/en_US/champion.json`);
        const championData = championResponse.data.data;

        // 3. Build the map: { '103': 'Ahri', '238': 'Zed', ... }
        const championMap = new Map();
        for (const championName in championData) {
            const champion = championData[championName];
            const championId = parseInt(champion.key, 10); // The 'key' is the numeric ID
            championMap.set(championId, champion.name);
        }

        console.log(`✅ Fetched ${championMap.size} champions from Data Dragon.`);
        return championMap;

    } catch (error) {
        console.error('❌ Failed to fetch champion map:', error);
        // Optionally, return a fallback map or throw the error
        return new Map();
    }
};


// ============================================
// EXPORT DEFAULT
// ============================================

export default api;