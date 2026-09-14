import os

# Telegram Bot Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8685338236:AAF41Q_kZGqjDJoIkBnpxFhSxl8TF3xc9zM")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7200809630")

# Inforadar API Settings
API_BASE_URL = "https://inforadar.live/api/v1"
API_TIMEOUT = 25.0  # seconds
API_MIN_INTERVAL = 0.6  # polite throttle interval between requests
MAX_ODDS_LOOKUPS = 10  # cap odds lookups per scan to avoid rate limits/blocks
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://inforadar.live/",
}

# Bot Operational Settings
POLL_INTERVAL_SECONDS = 60  # Safe polling delay to avoid rate limits/blocks
STATE_FILE_PATH = "state.json"

# Heuristic & Strategy Thresholds
MIN_MATCH_MINUTE = 45       # Look for matches in the 2nd half or late 1st half
MAX_MATCH_MINUTE = 80       # Don't pick too late to allow time for settlement
MIN_EDGE_SCORE = 65         # Minimum edge score required to trigger a pick
MIN_ODDS = 1.40             # Minimum acceptable decimal odds
MAX_ODDS = 3.50             # Maximum realistic decimal odds
