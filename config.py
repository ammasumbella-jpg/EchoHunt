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

# Heuristic & Strategy Thresholds (Postmortem Optimized)
MIN_MATCH_MINUTE = 45       # Look for matches in the 2nd half or late 1st half
MAX_MATCH_MINUTE = 80       # Late momentum picks (75-80') have 62.5% win rate
MIN_EDGE_SCORE = 65         # Minimum edge score required to trigger a pick
MIN_ODDS = 1.60             # Value odds floor
MAX_ODDS = 2.05             # Longshots (>2.05) have poor 37% win rate; capped for reliability

# Strict Statistical Momentum Filters (Critical Postmortem Insights)
# Matches with SoT < 5 lost heavily (-8.64u, 40% WR)
MIN_SOT = 5                 # Hard floor: at least 5 shots on target required
MIN_DA = 35                 # Hard floor: at least 35 dangerous attacks required
MIN_SOT_RATE = 0.08         # Shot intensity: minimum 1 shot on target per 12.5 mins

# Leagues with chronically negative ROI / high loss rate in live betting history
BLACKLISTED_LEAGUES = [
    "Israel Liga Bet North",
    "Romania Liga 2",
    "Serbia U19 League",
    "Peru Campeonato Nacional Women",
    "Africa Cup of Nations Qualification",
    "Mexico Liga TDP",
    "CONCACAF Nations League",
    "Europe Friendlies",
    "Brazil Serie B",
    "U19 International",
]

