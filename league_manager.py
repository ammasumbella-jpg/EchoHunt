"""
League Manager - Per-direction win/loss tracker.

Instead of blacklisting leagues on loss, this module tracks OVER and UNDER
win/loss counts per league and returns score modifiers that bias the engine
toward whichever direction has historically performed better.
"""
import json
import os
import logging
import time

logger = logging.getLogger("league_manager")

PERFORMANCE_FILE = "league_performance.json"

# Score modifier per net win/loss in a direction (capped at ±MAX_MODIFIER)
MODIFIER_PER_NET = 12
MAX_MODIFIER = 36


def _load_file(path: str, default) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
    return default


def _save_file(path: str, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save {path}: {e}")


class LeagueManager:
    """
    Tracks per-league, per-direction (OVER/UNDER) win/loss records.

    Returns score modifiers used by the engine:
      - Positive modifier  → boost that direction (historically wins here)
      - Negative modifier  → penalise that direction (historically loses here)
    """

    def __init__(self):
        self._perf = _load_file(PERFORMANCE_FILE, {"leagues": {}})
        # Ensure structure
        if "leagues" not in self._perf:
            self._perf["leagues"] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self):
        _save_file(PERFORMANCE_FILE, self._perf)

    def _get_or_create(self, league_id: str, league_name: str) -> dict:
        lid = str(league_id)
        if lid not in self._perf["leagues"]:
            self._perf["leagues"][lid] = {
                "id": lid,
                "name": league_name,
                "over": {"wins": 0, "losses": 0},
                "under": {"wins": 0, "losses": 0},
                "last_match": None,
                "last_updated": None,
            }
        return self._perf["leagues"][lid]

    # ------------------------------------------------------------------
    # Public API: recording outcomes
    # ------------------------------------------------------------------

    def record_win(self, league_id: str, league_name: str, direction: str, match_desc: str = ""):
        """Increment win counter for the given direction in this league."""
        entry = self._get_or_create(league_id, league_name)
        key = direction.lower()  # "over" or "under"
        if key in entry:
            entry[key]["wins"] += 1
        entry["last_match"] = match_desc
        entry["last_updated"] = int(time.time())
        self._save()
        logger.info(
            f"League '{league_name}' ({direction}) WIN recorded. "
            f"Record: {entry[key]['wins']}W-{entry[key]['losses']}L"
        )

    def record_loss(self, league_id: str, league_name: str, direction: str, match_desc: str = ""):
        """Increment loss counter for the given direction in this league."""
        entry = self._get_or_create(league_id, league_name)
        key = direction.lower()
        if key in entry:
            entry[key]["losses"] += 1
        entry["last_match"] = match_desc
        entry["last_updated"] = int(time.time())
        self._save()
        logger.info(
            f"League '{league_name}' ({direction}) LOSS recorded. "
            f"Record: {entry[key]['wins']}W-{entry[key]['losses']}L"
        )

    # ------------------------------------------------------------------
    # Public API: querying biases
    # ------------------------------------------------------------------

    def get_direction_modifiers(self, league_id: str, league_name: str) -> dict:
        """
        Returns score modifiers for each direction based on historical record.

        modifier = clamp(net_wins * MODIFIER_PER_NET, -MAX_MODIFIER, +MAX_MODIFIER)
        where net_wins = wins - losses for that direction.

        Returns:
            {"over": int, "under": int}  — positive = boost, negative = penalty
        """
        lid = str(league_id)
        if lid not in self._perf["leagues"]:
            return {"over": 0, "under": 0}

        entry = self._perf["leagues"][lid]

        def calc(rec):
            net = rec["wins"] - rec["losses"]
            return max(-MAX_MODIFIER, min(MAX_MODIFIER, net * MODIFIER_PER_NET))

        return {
            "over": calc(entry["over"]),
            "under": calc(entry["under"]),
        }

    def get_league_summary(self, league_id: str) -> dict | None:
        """Return the full record entry for a league, or None if unknown."""
        return self._perf["leagues"].get(str(league_id))

    def get_all_leagues(self) -> dict:
        return self._perf["leagues"]

    # ------------------------------------------------------------------
    # Convenience counts for startup logging
    # ------------------------------------------------------------------

    def get_over_preferred_count(self) -> int:
        """Leagues where OVER has a positive net record."""
        return sum(
            1 for e in self._perf["leagues"].values()
            if e["over"]["wins"] > e["over"]["losses"]
        )

    def get_under_preferred_count(self) -> int:
        """Leagues where UNDER has a positive net record."""
        return sum(
            1 for e in self._perf["leagues"].values()
            if e["under"]["wins"] > e["under"]["losses"]
        )

    def get_tracked_count(self) -> int:
        return len(self._perf["leagues"])
