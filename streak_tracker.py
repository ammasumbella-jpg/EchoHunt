"""
Streak and Performance Tracker for betting bot.
Tracks:
- Current Win Streak
- Best Win Streak (All-time record)
- Current Loss Streak
- Worst Loss Streak (All-time drawdown record)
- Total Bets, Wins, Losses, and Win Rate %
"""
import json
import os
import logging

logger = logging.getLogger("streak_tracker")
STREAK_FILE = "streak_stats.json"

DEFAULT_STREAKS = {
    "total_bets": 0,
    "total_wins": 0,
    "total_losses": 0,
    "current_win_streak": 0,
    "best_win_streak": 0,
    "current_loss_streak": 0,
    "worst_loss_streak": 0,
    "history": []  # e.g. ['W', 'W', 'L']
}

class StreakTracker:
    def __init__(self, file_path: str = STREAK_FILE):
        self.file_path = file_path
        self.stats = self.load_stats()

    def load_stats(self) -> dict:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    merged = DEFAULT_STREAKS.copy()
                    merged.update(data)
                    return merged
            except Exception as e:
                logger.error(f"Error reading {self.file_path}: {e}")
        return DEFAULT_STREAKS.copy()

    def save_stats(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving {self.file_path}: {e}")

    def record_bet_result(self, result: str) -> dict:
        """
        Record 'WON' or 'LOST' and update all streak metrics.
        """
        self.stats["total_bets"] += 1

        if result == "WON":
            self.stats["total_wins"] += 1
            self.stats["current_win_streak"] += 1
            self.stats["current_loss_streak"] = 0
            if self.stats["current_win_streak"] > self.stats["best_win_streak"]:
                self.stats["best_win_streak"] = self.stats["current_win_streak"]
            self.stats["history"].append("W")
        elif result == "LOST":
            self.stats["total_losses"] += 1
            self.stats["current_loss_streak"] += 1
            self.stats["current_win_streak"] = 0
            if self.stats["current_loss_streak"] > self.stats["worst_loss_streak"]:
                self.stats["worst_loss_streak"] = self.stats["current_loss_streak"]
            self.stats["history"].append("L")

        # Keep recent history to last 20
        if len(self.stats["history"]) > 20:
            self.stats["history"] = self.stats["history"][-20:]

        self.save_stats()
        logger.info(
            f"Streaks Updated: Current Win Streak={self.stats['current_win_streak']} | "
            f"Best Win Streak={self.stats['best_win_streak']} | "
            f"Worst Loss Streak={self.stats['worst_loss_streak']}"
        )
        return self.get_summary()

    def get_summary(self) -> dict:
        wins = self.stats["total_wins"]
        losses = self.stats["total_losses"]
        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0.0

        return {
            "current_win_streak": self.stats["current_win_streak"],
            "best_win_streak": self.stats["best_win_streak"],
            "current_loss_streak": self.stats["current_loss_streak"],
            "worst_loss_streak": self.stats["worst_loss_streak"],
            "total_wins": wins,
            "total_losses": losses,
            "total_bets": total,
            "win_rate": round(win_rate, 1),
            "recent_form": "".join(self.stats["history"][-5:])
        }
