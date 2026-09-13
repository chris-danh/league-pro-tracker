// frontend/src/api/client.js
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL;
const DD_BASE = 'https://ddragon.leagueoflegends.com';

const api = axios.create({
    baseURL: API_BASE,
    timeout: 120000,
    headers: { 'Content-Type': 'application/json' },
});

// ============================================
// DATA DRAGON VERSION (cached, shared)
// ============================================

// All Data Dragon lookups use the same patch. Fetching /api/versions.json
// once and caching the promise means every consumer resolves to the same
// version string without a redundant network call.
let ddragonVersionPromise = null;

export const getLatestDDragonVersion = () => {
    if (!ddragonVersionPromise) {
        ddragonVersionPromise = axios
            .get(`${DD_BASE}/api/versions.json`)
            .then(res => res.data[0]);
    }
    return ddragonVersionPromise;
};

// ============================================
// API FUNCTIONS
// ============================================

export const getPlayers = async () => {
    try {
        const response = await api.get('/players');
        return response.data;
    } catch (error) {
        console.error('Error fetching players:', error);
        throw error;
    }
};

export const refreshPlayer = async (gameName, tagLine, matchCount = 20, includeTimeline = false) => {
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
        if (error.response && (error.response.status === 404 || error.response.status === 400)) {
            return { success: false, message: 'No new matches found or player data is up to date.', matches_saved: 0 };
        }
        throw error;
    }
};

// ============================================
// DATA DRAGON - CHAMPIONS
// ============================================

export const getChampionMap = async () => {
    const cached = localStorage.getItem('championMap');
    const cachedTime = localStorage.getItem('championMapTime');

    if (cached && cachedTime && Date.now() - parseInt(cachedTime) < 24 * 60 * 60 * 1000) {
        return new Map(JSON.parse(cached));
    }

    try {
        const latestVersion = await getLatestDDragonVersion();
        const championResponse = await axios.get(
            `${DD_BASE}/cdn/${latestVersion}/data/en_US/champion.json`
        );
        const championData = championResponse.data.data;

        const championMap = new Map();
        for (const [championKey, championInfo] of Object.entries(championData)) {
            const championId = parseInt(championInfo.key, 10);
            championMap.set(championId, { name: championInfo.name, key: championKey });
        }

        localStorage.setItem('championMap', JSON.stringify([...championMap]));
        localStorage.setItem('championMapTime', Date.now().toString());
        return championMap;
    } catch (error) {
        console.error('❌ Failed to fetch champion map:', error);
        return new Map();
    }
};

export const getPlayerChampions = async (puuid, patch = null, minGames = 3) => {
    try {
        const response = await api.get(`/player/${puuid}/champions`, {
            params: { patch, min_games: minGames },
        });
        return response.data;
    } catch (error) {
        console.error('Error fetching player champions:', error);
        throw error;
    }
};

export const getChampionDetails = async (puuid, championId, enemyChampionId = null, patch = null) => {
    try {
        const response = await api.get(`/player/${puuid}/champion/${championId}/details`, {
            params: { enemy_champion_id: enemyChampionId, patch },
        });
        return response.data;
    } catch (error) {
        console.error('Error fetching champion details:', error);
        throw error;
    }
};

export const getMatchHistory = async (puuid, page = 1, pageSize = 20, patch = null) => {
    try {
        const response = await api.get(`/player/${puuid}/matches`, {
            params: { page, page_size: pageSize, patch },
        });
        return response.data;
    } catch (error) {
        console.error('Error fetching match history:', error);
        throw error;
    }
};

export const getRegionChampions = async (region, minGames = 2, role = null, limit = 50) => {
    try {
        const response = await api.get(`/region/${region}/champions`, {
            params: {
                min_games: minGames,
                role,
                limit,
            },
        });
        return response.data;
    } catch (error) {
        console.error('Error fetching region champions:', error);
        throw error;
    }
};

// ============================================
// DATA DRAGON - ITEMS
// ============================================

let itemMap = null;
let itemMapLoading = false;
let itemMapPromise = null;

export const getItemMap = async () => {
    if (itemMap) return itemMap;
    if (itemMapLoading) return itemMapPromise;

    itemMapLoading = true;
    itemMapPromise = (async () => {
        try {
            const latestVersion = await getLatestDDragonVersion();
            const itemResponse = await axios.get(
                `${DD_BASE}/cdn/${latestVersion}/data/en_US/item.json`
            );
            const itemData = itemResponse.data.data;

            itemMap = new Map();
            for (const [itemId, itemInfo] of Object.entries(itemData)) {
                if (itemInfo.gold) {
                    itemMap.set(parseInt(itemId), {
                        name: itemInfo.name,
                        image: `${DD_BASE}/cdn/${latestVersion}/img/item/${itemInfo.image.full}`,
                        description: itemInfo.description,
                        gold: itemInfo.gold.total,
                        plaintext: itemInfo.plaintext || '',
                    });
                }
            }
            return itemMap;
        } catch (error) {
            console.error('❌ Failed to fetch item map:', error);
            return new Map();
        } finally {
            itemMapLoading = false;
        }
    })();

    return itemMapPromise;
};

export const getItemDetails = async (itemId) => {
    const map = await getItemMap();
    return map.get(itemId) || null;
};

export const getItemImageUrl = async (itemId) => {
    const details = await getItemDetails(itemId);
    return details?.image || null;
};

// ============================================
// DATA DRAGON - RUNES (main trees only)
// ============================================

let runeMap = null;
let runeMapLoading = false;
let runeMapPromise = null;

export const getRuneMap = async () => {
    if (runeMap) return runeMap;
    if (runeMapLoading) return runeMapPromise;

    runeMapLoading = true;
    runeMapPromise = (async () => {
        try {
            const latestVersion = await getLatestDDragonVersion();
            const runeResponse = await axios.get(
                `${DD_BASE}/cdn/${latestVersion}/data/en_US/runesReforged.json`
            );
            const runeData = runeResponse.data;

            runeMap = new Map();
            for (const tree of runeData) {
                for (const slot of tree.slots) {
                    for (const rune of slot.runes) {
                        runeMap.set(rune.id, {
                            name: rune.name,
                            key: rune.key,
                            image: `${DD_BASE}/cdn/img/${rune.icon}`,
                            description: rune.shortDesc || rune.longDesc || '',
                        });
                    }
                }
            }
            return runeMap;
        } catch (error) {
            console.error('❌ Failed to fetch rune map:', error);
            return new Map();
        } finally {
            runeMapLoading = false;
        }
    })();

    return runeMapPromise;
};

// ============================================
// COMMUNITY DRAGON - STAT SHARDS (slot-aware)
// ============================================

const CDRAGON_BASE = 'https://raw.communitydragon.org/latest/game/assets/perks/statmods/';

// Keyed by `${slot}_${rune_id}` because the same ID can mean different
// things in different slots (e.g. 5008 in offense vs flex).
const STAT_SHARD_MAP = {
    // ── Offense slot ─────────────────────────────
    'shard_offense_5005': { name: 'Attack Speed',    file: 'statmodsattackspeedicon' },
    'shard_offense_5008': { name: 'Adaptive Force',  file: 'statmodsadaptiveforceicon' },
    'shard_offense_5007': { name: 'Ability Haste',   file: 'statmodscdrscalingicon' },

    // ── Flex slot ────────────────────────────────
    'shard_flex_5008':    { name: 'Adaptive Force',  file: 'statmodsadaptiveforceicon' },
    'shard_flex_5010':    { name: 'Move Speed',      file: 'statmodsmovementspeedicon' },
    'shard_flex_5001':    { name: 'Health Scaling',  file: 'statmodshealthplusicon' },

    // ── Defense slot ─────────────────────────────
    'shard_defense_5011': { name: 'Health',          file: 'statmodshealthscalingicon' },
    'shard_defense_5001': { name: 'Health Scaling',  file: 'statmodshealthplusicon' },
    'shard_defense_5013': { name: 'Tenacity',        file: 'statmodstenacityicon' },
};

let statShardCache = null;

export const getStatShardMap = () => {
    if (statShardCache) return statShardCache;

    statShardCache = new Map();
    for (const [key, info] of Object.entries(STAT_SHARD_MAP)) {
        statShardCache.set(key, {
            name: info.name,
            image: `${CDRAGON_BASE}${info.file}.png`,
        });
    }
    return statShardCache;
};

// ============================================
// DATA DRAGON - RUNE TREE STYLES (8000-8400)
// ============================================

// Rune tree/style IDs → icon URLs. These are separate from individual rune
// IDs and must be looked up on their own path in Data Dragon. Declared here
// (before getRuneDetails) so it's initialized when that function runs.
const RUNE_STYLE_MAP = new Map([
    [8000, { name: 'Precision',   image: 'https://ddragon.leagueoflegends.com/cdn/img/perk-images/Styles/7201_Precision.png' }],
    [8100, { name: 'Domination',  image: 'https://ddragon.leagueoflegends.com/cdn/img/perk-images/Styles/7200_Domination.png' }],
    [8200, { name: 'Sorcery',     image: 'https://ddragon.leagueoflegends.com/cdn/img/perk-images/Styles/7202_Sorcery.png' }],
    [8300, { name: 'Inspiration', image: 'https://ddragon.leagueoflegends.com/cdn/img/perk-images/Styles/7203_Whimsy.png' }],
    [8400, { name: 'Resolve',     image: 'https://ddragon.leagueoflegends.com/cdn/img/perk-images/Styles/7204_Resolve.png' }],
]);

// ============================================
// RUNE LOOKUP (combines tree runes + shards + styles)
// ============================================

export const getRuneDetails = async (runeId, slot = null) => {
    // Slot-aware shard lookup first.
    if (slot) {
        const key = `${slot}_${runeId}`;
        const shard = getStatShardMap().get(key);
        if (shard) return shard;
    }

    // Rune tree styles (8000-8400) are separate from individual runes.
    const style = RUNE_STYLE_MAP.get(runeId);
    if (style) return style;

    // Fall back to the main rune map from Data Dragon.
    const map = await getRuneMap();
    return map.get(runeId) || null;
};

export const getRuneName = (runeId) => {
    if (!runeMap) return null;
    return runeMap.get(runeId)?.name || null;
};

export const getRuneImageUrl = async (runeId, slot = null) => {
    const details = await getRuneDetails(runeId, slot);
    return details?.image || null;
};

// ============================================
// DATA DRAGON - CHAMPION SPLASH
// ============================================

export const getChampionSplashUrl = (championId, championMap) => {
    if (!championId || !championMap) return null;
    const info = championMap.get(championId);
    if (!info) return null;
    return `${DD_BASE}/cdn/img/champion/splash/${info.key}_0.jpg`;
};

// ============================================
// DATA DRAGON - CHAMPION ABILITIES
// ============================================

let abilityMapCache = null;
let abilityMapLoading = false;
let abilityMapPromise = null;

export const getChampionAbilityMap = async () => {
    if (abilityMapCache) return abilityMapCache;
    if (abilityMapLoading) return abilityMapPromise;

    abilityMapLoading = true;
    abilityMapPromise = (async () => {
        try {
            const latestVersion = await getLatestDDragonVersion();
            const champListRes = await axios.get(
                `${DD_BASE}/cdn/${latestVersion}/data/en_US/champion.json`
            );
            const champList = champListRes.data.data;
            const abilityMap = {};
            const championKeys = Object.keys(champList);

            for (const championKey of championKeys) {
                try {
                    const champRes = await axios.get(
                        `${DD_BASE}/cdn/${latestVersion}/data/en_US/champion/${championKey}.json`
                    );
                    const championInfo = champRes.data.data[championKey];
                    const championId = parseInt(championInfo.key, 10);
                    const spells = championInfo.spells || [];

                    abilityMap[championId] = {
                        name: championInfo.name,
                        key: championKey,
                        spells: spells.map((spell) => ({
                            id: spell.id,
                            name: spell.name,
                            image: spell.image?.full
                                ? `${DD_BASE}/cdn/${latestVersion}/img/spell/${spell.image.full}`
                                : null,
                        })),
                    };
                } catch (err) {
                    const championInfo = champList[championKey];
                    const championId = parseInt(championInfo.key, 10);
                    abilityMap[championId] = {
                        name: championInfo.name,
                        key: championKey,
                        spells: [],
                    };
                }
            }

            abilityMapCache = abilityMap;
            return abilityMap;
        } catch (error) {
            console.error('❌ Failed to fetch ability map:', error);
            return {};
        } finally {
            abilityMapLoading = false;
        }
    })();

    return abilityMapPromise;
};

// ============================================
// DATA DRAGON - SUMMONER SPELLS
// ============================================

let summonerSpellMap = null;
let summonerSpellMapLoading = false;
let summonerSpellMapPromise = null;

export const getSummonerSpellMap = async () => {
    if (summonerSpellMap) return summonerSpellMap;
    if (summonerSpellMapLoading) return summonerSpellMapPromise;

    summonerSpellMapLoading = true;
    summonerSpellMapPromise = (async () => {
        try {
            const latestVersion = await getLatestDDragonVersion();
            const spellRes = await axios.get(
                `${DD_BASE}/cdn/${latestVersion}/data/en_US/summoner.json`
            );
            const spellData = spellRes.data.data;

            summonerSpellMap = new Map();
            for (const [spellKey, spellInfo] of Object.entries(spellData)) {
                const spellId = parseInt(spellInfo.key, 10);
                summonerSpellMap.set(spellId, {
                    name: spellInfo.name,
                    key: spellKey,
                    image: `${DD_BASE}/cdn/${latestVersion}/img/spell/${spellKey}.png`,
                });
            }
            return summonerSpellMap;
        } catch (error) {
            console.error('❌ Failed to fetch summoner spell map:', error);
            return new Map();
        } finally {
            summonerSpellMapLoading = false;
        }
    })();

    return summonerSpellMapPromise;
};

// ============================================
// CORE ITEMS
// ============================================

export const getCoreItems = async (puuid, championId, enemyChampionId = null, patch = null) => {
    try {
        const response = await api.get(`/player/${puuid}/champion/${championId}/core-items`, {
            params: { enemy_champion_id: enemyChampionId, patch },
        });
        return response.data;
    } catch (error) {
        console.error('Error fetching core items:', error);
        throw error;
    }
};

export default api;