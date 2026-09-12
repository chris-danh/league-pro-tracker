// frontend/src/utils/playerPortraits.js

// Map player names (as they appear in your JSON) to portrait filenames
export const PLAYER_PORTRAITS = {
    // Format: "Player IGN as in JSON": "filename_without_extension"
    "kiin": "kiin",
    "aierlanxiaozhu": "Breathe",
    "The shy": "TheShy",
    // Add more mappings as needed
};

// Helper function to find portrait for any player name
export const getPlayerPortrait = (playerName) => {
    console.log('🔍 getPlayerPortrait called with:', playerName);
    
    if (!playerName) {
        console.log('⚠️ No player name provided');
        return null;
    }
    
    // 1. Try exact match first
    if (PLAYER_PORTRAITS[playerName]) {
        console.log('✅ Exact match found:', PLAYER_PORTRAITS[playerName]);
        return `/portraits/${PLAYER_PORTRAITS[playerName]}.png`;
    }
    
    // 2. Try case-insensitive match
    const lowerName = playerName.toLowerCase();
    for (const [key, value] of Object.entries(PLAYER_PORTRAITS)) {
        if (key.toLowerCase() === lowerName) {
            console.log('✅ Case-insensitive match found:', key, '->', value);
            return `/portraits/${value}.png`;
        }
    }
    
    // 3. Try to find by checking if playerName contains any key (case-insensitive)
    for (const [key, value] of Object.entries(PLAYER_PORTRAITS)) {
        const lowerKey = key.toLowerCase();
        if (lowerName.includes(lowerKey) || lowerKey.includes(lowerName)) {
            console.log('✅ Partial match found:', key, '->', value);
            return `/portraits/${value}.png`;
        }
    }
    
    // 4. Try to extract the last word (e.g., "GEN Kiin" -> "Kiin")
    const parts = playerName.split(' ');
    if (parts.length > 1) {
        const lastName = parts[parts.length - 1];
        
        // Try exact match on last name
        if (PLAYER_PORTRAITS[lastName]) {
            console.log('✅ Last name match found:', lastName, '->', PLAYER_PORTRAITS[lastName]);
            return `/portraits/${PLAYER_PORTRAITS[lastName]}.png`;
        }
        
        // Try case-insensitive match on last name
        for (const [key, value] of Object.entries(PLAYER_PORTRAITS)) {
            if (key.toLowerCase() === lastName.toLowerCase()) {
                console.log('✅ Last name case-insensitive match found:', key, '->', value);
                return `/portraits/${value}.png`;
            }
        }
    }
    
    // 5. Fallback: use the player name directly (with URL encoding for spaces)
    console.log('⚠️ No mapping found, using player name as fallback:', playerName);
    return `/portraits/${encodeURIComponent(playerName)}.png`;
};