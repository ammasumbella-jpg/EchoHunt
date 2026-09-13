"""
League Performance, Loss Blacklist, and Win Priority Manager.
- Leagues with 1 loss are blacklisted from future picks.
- Leagues with wins receive HIGH PRIORITY in match selection.
"""
import json
import os
import time
import logging

logger = logging.getLogger("league_manager")
LEAGUES_DATA_FILE = "league_performance.json"
BANNED_LEAGUES_LEGACY_FILE = "loss_leagues.json"

class LeagueManager:
    def __init__(self, file_path: str = LEAGUES_DATA_FILE):
        self.file_path = file_path
        self.data = self.load_data()

    def load_data(self) -> dict:
        data = {"banned": {}, "priority": {}}
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    data["banned"].update(loaded.get("banned", {}))
                    data["priority"].update(loaded.get("priority", {}))
            except Exception as e:
                logger.error(f"Error loading {self.file_path}: {e}")
        elif os.path.exists(BANNED_LEAGUES_LEGACY_FILE):
            try:
                with open(BANNED_LEAGUES_LEGACY_FILE, "r", encoding="utf-8") as f:
                    data["banned"] = json.load(f)
            except Exception:
                pass
        return data

    def save_data(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            # Keep legacy loss_leagues.json synced
            with open(BANNED_LEAGUES_LEGACY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data["banned"], f, indent=4)
        except Exception as e:
            logger.error(f"Error saving league data: {e}")

    def is_league_banned(self, league_id: str, league_name: str = "") -> bool:
        """Check if league has been blacklisted due to a loss."""
        str_id = str(league_id) if league_id is not None else ""
        clean_name = str(league_name).strip().lower() if league_name else ""

        if str_id and str_id in self.data["banned"]:
            return True

        for lid, info in self.data["banned"].items():
            b_name = info.get("name", "").strip().lower()
            if b_name and b_name == clean_name:
                return True

        return False

    def is_league_priority(self, league_id: str, league_name: str = "") -> tuple:
        """Returns (is_priority: bool, win_count: int)."""
        str_id = str(league_id) if league_id is not None else ""
        clean_name = str(league_name).strip().lower() if league_name else ""

        if str_id and str_id in self.data["priority"]:
            wins = self.data["priority"][str_id].get("wins", 1)
            return True, wins

        for lid, info in self.data["priority"].items():
            p_name = info.get("name", "").strip().lower()
            if p_name and p_name == clean_name:
                wins = info.get("wins", 1)
                return True, wins

        return False, 0

    def record_win(self, league_id: str, league_name: str, match_details: str = ""):
        """Promote a winning league to HIGH PRIORITY status."""
        str_id = str(league_id) if league_id else f"name_{league_name}"
        clean_name = league_name or "Unknown League"

        entry = self.data["priority"].get(str_id, {
            "id": str_id,
            "name": clean_name,
            "wins": 0,
            "first_win_time": int(time.time()),
            "last_match": match_details
        })
        entry["wins"] = entry.get("wins", 0) + 1
        entry["last_win_time"] = int(time.time())
        entry["last_match"] = match_details

        self.data["priority"][str_id] = entry
        self.save_data()
        logger.info(f"⭐ League PROMOTED to HIGH PRIORITY: '{clean_name}' (ID: {str_id}) now has {entry['wins']} win(s).")

    def record_loss(self, league_id: str, league_name: str, match_details: str = ""):
        """Add league to loss blacklist upon 1 loss and revoke any priority status."""
        str_id = str(league_id) if league_id else f"name_{league_name}"
        clean_name = league_name or "Unknown League"

        # Remove from priority if previously winning
        if str_id in self.data["priority"]:
            del self.data["priority"][str_id]

        entry = self.data["banned"].get(str_id, {
            "id": str_id,
            "name": clean_name,
            "losses": 0,
            "first_loss_time": int(time.time()),
            "last_match": match_details
        })
        entry["losses"] = entry.get("losses", 0) + 1
        entry["last_loss_time"] = int(time.time())
        entry["last_match"] = match_details

        self.data["banned"][str_id] = entry
        self.save_data()
        logger.warning(f"🚫 League SHORTLISTED/BANNED: '{clean_name}' (ID: {str_id}) added to loss blacklist after {entry['losses']} loss.")

    def get_banned_count(self) -> int:
        return len(self.data["banned"])

    def get_priority_count(self) -> int:
        return len(self.data["priority"])
