import os
from dotenv import load_dotenv

# load environment variables (api key)
load_dotenv()

# riot API key
RIOT_API_KEY = os.getenv("RIOT_API_KEY", "")

# rate limits
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_SECONDS = 1

# region
DEFAULT_REGION = "KR"
REGIONS = ["KR", "EUW", "NA"]

# database
DATABASE_PATH = "league_data.db"