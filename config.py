import os
from dotenv import load_dotenv

# load environment variables (api key)
load_dotenv()

# riot API key
RIOT_API_KEY = os.getenv("RIOT_API_KEY", "")

# rate limits
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_SECONDS = 1

CURRENT_PATCH = "16.10.1"