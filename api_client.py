"""
Robust API Client for Inforadar with session management and retry logic.
"""
import time
import requests
import logging
from config import API_BASE_URL, API_TIMEOUT, REQUEST_HEADERS

logger = logging.getLogger("api_client")

class InforadarClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def _request(self, method: str, endpoint: str, params: dict = None, max_retries: int = 3):
        url = f"{API_BASE_URL}{endpoint}"
        backoff = 2
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    timeout=API_TIMEOUT
                )
                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception as json_err:
                        logger.error(f"JSON decode error from {url}: {json_err}")
                        return None
                elif response.status_code == 429:
                    logger.warning(f"Rate limited (429) on {url}. Backing off for {backoff * 2}s...")
                    time.sleep(backoff * 2)
                else:
                    logger.warning(f"HTTP {response.status_code} on {url}: {response.text[:200]}")
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
                logger.warning(f"Attempt {attempt}/{max_retries} failed for {url}: {net_err}")
            except Exception as e:
                logger.error(f"Unexpected error querying {url}: {e}")

            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2

        logger.error(f"Exhausted {max_retries} retries for {url}.")
        return None

    def get_live_games(self, sport_id: int = 1, page: int = 1, per_page: int = 1000):
        """Fetch all current in-play games."""
        params = {
            "sport_id": sport_id,
            "page": page,
            "per_page": per_page
        }
        res = self._request("GET", "/live_games", params=params)
        if isinstance(res, dict):
            return res.get("results", [])
        return []

    def get_game_view(self, event_id: str):
        """Fetch specific game details and match events."""
        params = {"event_id": event_id}
        res = self._request("GET", "/soccer/game/view", params=params)
        if isinstance(res, dict) and "id" in res:
            return res
        return None

    def get_game_odds(self, event_id: str, odds_market: str = "3"):
        """
        Fetch odds history.
        odds_market: "3" is Total (Over/Under)
        """
        params = {
            "event_id": event_id,
            "odds_market": odds_market
        }
        res = self._request("GET", "/soccer/game/odds", params=params)
        if isinstance(res, list):
            return res
        return []
