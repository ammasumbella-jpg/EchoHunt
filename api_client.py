"""
Polite, robust API Client for Inforadar with inter-request rate throttling,
exponential backoff, and transient error resilience (stdlib-based).
"""
import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from config import (
    API_BASE_URL,
    API_TIMEOUT,
    API_MIN_INTERVAL,
    REQUEST_HEADERS,
)

logger = logging.getLogger("api_client")


class InforadarClient:
    """
    Polite HTTP client enforcing minimum interval between calls,
    exponential backoff with jitter, and transient error tolerance.
    """

    def __init__(self, min_interval=API_MIN_INTERVAL, retries=3, timeout=API_TIMEOUT):
        self.min_interval = min_interval
        self.retries = retries
        self.timeout = timeout
        self._last = 0.0

    def _throttle(self):
        """Enforce spacing between calls to avoid triggering rate-limiting WAF."""
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def _request(self, path: str, params: dict = None, max_retries: int = None):
        if max_retries is None:
            max_retries = self.retries

        url = f"{API_BASE_URL}{path}"
        if params:
            cleaned = {k: v for k, v in params.items() if v is not None}
            url += "?" + urllib.parse.urlencode(cleaned)

        last_err = None
        for attempt in range(max_retries + 1):
            self._throttle()
            req = urllib.request.Request(url, headers=REQUEST_HEADERS)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw_bytes = resp.read()
                    text = raw_bytes.decode("utf-8", "replace").strip()
                    if not text:
                        raise ValueError("Empty response body received from API")
                    return json.loads(text)
            except urllib.error.HTTPError as e:
                last_err = e
                # Inforadar intermittently returns 400 on valid requests;
                # treat 400, 408, 429, 500, 502, 503, 504 as transient retries.
                if e.code not in (400, 408, 429, 500, 502, 503, 504):
                    logger.warning(f"Fatal HTTP {e.code} for {url}")
                    break
                logger.warning(f"Transient HTTP {e.code} on {url} (attempt {attempt + 1}/{max_retries + 1})")
            except Exception as e:
                # Catches timeouts, DNS/socket glitches, empty responses, and malformed JSON
                last_err = e
                logger.warning(f"Request error on {url} (attempt {attempt + 1}/{max_retries + 1}): {e}")

            if attempt < max_retries:
                sleep_s = min(2 ** attempt + random.random(), 8.0)
                time.sleep(sleep_s)

        logger.error(f"Exhausted {max_retries} retries for {url}: {last_err}")
        return None

    def get_live_games(self, sport_id: int = 1, page: int = 1, per_page: int = 1000) -> list:
        """Fetch all current in-play games."""
        params = {
            "sport_id": sport_id,
            "page": page,
            "per_page": per_page,
        }
        res = self._request("/live_games", params=params)
        if isinstance(res, dict):
            return res.get("results") or []
        return []

    def get_finished_games(self, sport_id: int = 1, page: int = 1, per_page: int = 50) -> list:
        """Fetch recently finished games archive (note trailing slash)."""
        params = {
            "sport_id": sport_id,
            "page": page,
            "per_page": per_page,
        }
        res = self._request("/finished_games/", params=params)
        if isinstance(res, dict):
            return res.get("results") or []
        return []

    def get_game_view(self, event_id: str) -> dict:
        """Fetch specific game details and match events."""
        params = {"event_id": str(event_id)}
        res = self._request("/soccer/game/view", params=params)
        if isinstance(res, dict) and "id" in res:
            return res
        return None

    def get_game_odds(self, event_id: str, odds_market: str = "3") -> list:
        """
        Fetch odds history.
        odds_market: CSV or market id (Inforadar returns all markets regardless,
        select market by name='Total').
        """
        params = {
            "event_id": str(event_id),
            "odds_market": odds_market,
        }
        res = self._request("/soccer/game/odds", params=params)
        if isinstance(res, list):
            return res
        return []
