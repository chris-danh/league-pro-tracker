// frontend/src/utils/playerPortraits.js

/**
 * Player portrait lookup.
 *
 * Maps each player's IGN (as it appears in data/pros.json) to a portrait
 * filename in frontend/public/portraits/. Values are filenames without
 * extension — the .png suffix is added by getPlayerPortrait.
 *
 * Matching is exact (case-insensitive). There is no fuzzy or partial
 * matching; if a name isn't here, the player falls back to their initial.
 * This is deliberate — substring matching produced silent mismatches.
 */
export const PLAYER_PORTRAITS = {
    // Top lane
    "kiin": "kiin",
    "TOPKING": "siwoo",
    "Athene": "zeus",
    "PerfecT": "perfect",
    "어리고싶다": "doran",
    "songman": "clear",
    "aierlanxiaozhu": "breathe",
    "빈스토리": "bin",
    "zdz": "zdz",
    "The shy": "theshy",
    "샤오 쑤A": "xiaoxu",
    "burdol": "burdol",
    "어쩌라고맞짱뜰까": "hoya",
    "WE choukesi": "cube",
    "leicingwaa": "keshi",
    "Pure Imagination": "zuian",
};

/**
 * Look up a portrait URL for a player by IGN.
 *
 * Matching is case-insensitive on the full name. Returns null if no
 * mapping exists, letting the caller fall back to initials.
 */
export const getPlayerPortrait = (playerName) => {
    if (!playerName) return null;

    // Exact match
    if (PLAYER_PORTRAITS[playerName]) {
        return `/portraits/${PLAYER_PORTRAITS[playerName]}.png`;
    }

    // Case-insensitive match
    const lower = playerName.toLowerCase();
    for (const [key, value] of Object.entries(PLAYER_PORTRAITS)) {
        if (key.toLowerCase() === lower) {
            return `/portraits/${value}.png`;
        }
    }

    return null;
};