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
    "total_voids": 0,
    "current_win_streak": 0,
    "best_win_streak": 0,
    "current_loss_streak": 0,
    "worst_loss_streak": 0,
    "history": []  # e.g. ['W', 'W', 'L', 'P']
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
        Record 'WON', 'LOST', 'VOID', 'PUSH', 'HALF_WIN', or 'HALF_LOSS' and update streak metrics.

        - VOID / PUSH: stake refunded, streak preserved (no win or loss)
        - HALF_WIN: half-stake profit — counted as a win for streak purposes
        - HALF_LOSS: half-stake lost — counted as a loss for streak purposes
        """
        if result in ["VOID", "PUSH"]:
            self.stats["total_voids"] = self.stats.get("total_voids", 0) + 1
            self.stats["history"].append("P")
            if len(self.stats["history"]) > 20:
                self.stats["history"] = self.stats["history"][-20:]
            self.save_stats()
            logger.info(
                f"Bet Settled as {result} (Stake Refunded). Streak preserved: "
                f"Win Streak={self.stats['current_win_streak']} | "
                f"Loss Streak={self.stats['current_loss_streak']}"
            )
            return self.get_summary()

        self.stats["total_bets"] = self.stats.get("total_bets", 0) + 1

        if result in ["WON", "HALF_WIN"]:
            self.stats["total_wins"] += 1
            self.stats["current_win_streak"] += 1
            self.stats["current_loss_streak"] = 0
            if self.stats["current_win_streak"] > self.stats["best_win_streak"]:
                self.stats["best_win_streak"] = self.stats["current_win_streak"]
            self.stats["history"].append("HW" if result == "HALF_WIN" else "W")
        elif result in ["LOST", "HALF_LOSS"]:
            self.stats["total_losses"] += 1
            self.stats["current_loss_streak"] += 1
            self.stats["current_win_streak"] = 0
            if self.stats["current_loss_streak"] > self.stats["worst_loss_streak"]:
                self.stats["worst_loss_streak"] = self.stats["current_loss_streak"]
            self.stats["history"].append("HL" if result == "HALF_LOSS" else "L")

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
        voids = self.stats.get("total_voids", 0)
        total_decided = wins + losses
        win_rate = (wins / total_decided * 100) if total_decided > 0 else 0.0

        return {
            "current_win_streak": self.stats["current_win_streak"],
            "best_win_streak": self.stats["best_win_streak"],
            "current_loss_streak": self.stats["current_loss_streak"],
            "worst_loss_streak": self.stats["worst_loss_streak"],
            "total_wins": wins,
            "total_losses": losses,
            "total_voids": voids,
            "total_bets": total_decided + voids,
            "win_rate": round(win_rate, 1),
            "recent_form": "".join(self.stats["history"][-5:])
        }
