SUMMONER_SPELLS = {
    1: "SummonerBoost",      # Cleanse
    3: "SummonerExhaust",    # Exhaust
    4: "SummonerFlash",      # Flash
    6: "SummonerHaste",      # Ghost
    7: "SummonerHeal",       # Heal
    11: "SummonerSmite",     # Smite
    12: "SummonerTeleport",  # Teleport
    13: "SummonerMana",      # Clarity
    14: "SummonerDot",       # Ignite
    21: "SummonerBarrier",   # Barrier
    30: "SummonerPoroThrow", # Poro Throw (ARAM)
    31: "SummonerDemolishor", # Demolishor (ARAM)
    32: "SummonerSnowball",  # Snowball (ARAM)
    39: "SummonerSnowURFSnowball_Mark", # Snowball (URF)
}

def get_spell_name(spell_id: int) -> str:
    # convert spell id to in game spell name
    return SUMMONER_SPELLS.get(spell_id, f"Unknown({spell_id})")