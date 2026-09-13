"""
State manager for tracking active locked prediction and persistent state.
"""
import json
import os
import logging
from config import STATE_FILE_PATH

logger = logging.getLogger("state_manager")

DEFAULT_STATE = {
    "is_locked": False,
    "active_match_id": None,
    "home_team": None,
    "away_team": None,
    "league": None,
    "league_id": None,
    "market": "Total Goals",
    "prediction": None,
    "direction": None,       # "OVER" or "UNDER"
    "target_line": None,     # float, e.g. 1.5, 2.5
    "odds": None,            # float, e.g. 1.85
    "score_at_pick": None,   # "0-0"
    "goals_at_pick": 0,
    "minute_at_pick": None,
    "edge_score": None,
    "pick_timestamp": None
}

class StateManager:
    def __init__(self, file_path: str = STATE_FILE_PATH):
        self.file_path = file_path
        self.state = self.load_state()

    def load_state(self) -> dict:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge with default state in case new fields were added
                    merged = DEFAULT_STATE.copy()
                    merged.update(data)
                    return merged
            except Exception as e:
                logger.error(f"Failed to read state from {self.file_path}: {e}")
        return DEFAULT_STATE.copy()

    def save_state(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save state to {self.file_path}: {e}")

    def lock_bet(self, match_info: dict, pick_info: dict):
        """Lock the bot onto an active bet."""
        self.state.update({
            "is_locked": True,
            "active_match_id": str(match_info.get("id")),
            "home_team": match_info.get("home", {}).get("name", "Home Team"),
            "away_team": match_info.get("away", {}).get("name", "Away Team"),
            "league": match_info.get("league", {}).get("name", "League"),
            "league_id": str(match_info.get("league", {}).get("id", "")),
            "market": "Total Goals",
            "prediction": pick_info.get("prediction"),
            "direction": pick_info.get("direction"),
            "target_line": pick_info.get("target_line"),
            "odds": pick_info.get("odds"),
            "score_at_pick": match_info.get("scores", "0-0"),
            "goals_at_pick": pick_info.get("current_goals", 0),
            "minute_at_pick": pick_info.get("minute"),
            "edge_score": pick_info.get("edge_score"),
            "pick_timestamp": pick_info.get("timestamp")
        })
        self.save_state()
        logger.info(f"Bot LOCKED on match {self.state['active_match_id']} ({self.state['prediction']})")

    def unlock_bet(self):
        """Reset lock to allow new predictions."""
        self.state = DEFAULT_STATE.copy()
        self.save_state()
        logger.info("Bot UNLOCKED. Scanning for new opportunities.")

    @property
    def is_locked(self) -> bool:
        return self.state.get("is_locked", False)

    @property
    def active_match_id(self):
        return self.state.get("active_match_id")
