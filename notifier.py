"""
Advanced Telegram Notifier using Telegram Bot API with HTML formatting.
"""
import html
import logging
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("notifier")

def make_gauge_bar(score: int, length: int = 10) -> str:
    """Generate a visual progress gauge e.g. [████████░░]."""
    clamped = max(0, min(100, score))
    filled = int(round((clamped / 100) * length))
    empty = length - filled
    return "█" * filled + "░" * empty

class TelegramNotifier:
    def __init__(self, token: str = TELEGRAM_BOT_TOKEN, chat_id: str = TELEGRAM_CHAT_ID):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send_message(self, text: str) -> bool:
        """Send an HTML-formatted message to Telegram."""
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            res = requests.post(self.api_url, json=payload, timeout=15)
            if res.status_code == 200:
                logger.info("Telegram message delivered successfully.")
                return True
            else:
                logger.error(f"Failed to send Telegram message. HTTP {res.status_code}: {res.text}")
                return False
        except Exception as e:
            logger.error(f"Exception sending message to Telegram: {e}")
            return False

    def send_pick_alert(self, match: dict, pick: dict) -> bool:
        """Send high-tier advanced pick notification."""
        home = html.escape(str(match.get("home", {}).get("name", "Home Team")))
        away = html.escape(str(match.get("away", {}).get("name", "Away Team")))
        league = html.escape(str(match.get("league", {}).get("name", "Worldwide League")))
        score = html.escape(str(match.get("scores", "0-0")))
        minute = pick.get("minute", "Live")
        
        # Stats
        sot_h = pick.get("sot_h", 0)
        sot_a = pick.get("sot_a", 0)
        sot_tot = sot_h + sot_a

        da_h = pick.get("da_h", 0)
        da_a = pick.get("da_a", 0)
        da_tot = da_h + da_a

        corn_h = pick.get("corn_h", 0)
        corn_a = pick.get("corn_a", 0)
        corn_tot = corn_h + corn_a

        edge_score = int(pick.get("edge_score", 75))
        gauge = make_gauge_bar(edge_score)
        
        prediction = html.escape(str(pick.get("prediction", "TOTAL OVER")))
        odds = pick.get("odds", 1.80)
        direction = pick.get("direction", "OVER")

        dir_icon = "📈" if direction == "OVER" else "📉"

        event_id = html.escape(str(match.get("id", "")))
        event_link = f'🆔 <b>Event ID:</b> <a href="https://inforadar.live/#/dashboard/soccer/game/{event_id}">#{event_id}</a>\n' if event_id else ""

        priority_tag = ""
        if pick.get("is_priority_league"):
            wins_cnt = pick.get("league_wins", 1)
            priority_tag = f"⭐ <b>LEAGUE STATUS:</b> <code>HIGH PRIORITY ({wins_cnt}W)</code>\n"

        msg = (
            f"🎯 <b>RADAR LIVE PICK DETECTED</b> 🎯\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 <b>League:</b> {league}\n"
            f"{priority_tag}"
            f"⚔️ <b>Match:</b> <b>{home}</b> vs <b>{away}</b>\n"
            f"{event_link}"
            f"⏱ <b>In-Play:</b> <code>{minute}'</code> | <b>Current Score:</b> <code>{score}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>LIVE STATISTICAL MOMENTUM</b>\n"
            f"• <b>Shots on Target:</b> <code>{sot_h} - {sot_a}</code> (Total: <b>{sot_tot}</b>)\n"
            f"• <b>Dangerous Attacks:</b> <code>{da_h} - {da_a}</code> (Total: <b>{da_tot}</b>)\n"
            f"• <b>Corners:</b> <code>{corn_h} - {corn_a}</code> (Total: <b>{corn_tot}</b>)\n"
            f"• <b>Edge Rating:</b> <code>[{gauge}] {edge_score}%</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{dir_icon} <b>RECOMMENDED PLAY:</b>\n"
            f"👉 <b>{prediction}</b>\n"
            f"💰 <b>Live Value Odds:</b> <b>@{odds:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 <b>STATUS: BOT IS LOCKED</b>\n"
            f"<i>No new picks will be published until this match settles.</i>"
        )
        return self.send_message(msg)

    def send_settlement_alert(self, state: dict, result: str, final_score: str, note: str = "", streak_summary: dict = None) -> bool:
        """
        Send settlement result notification with win/loss streak metrics.
        result: 'WON' or 'LOST'
        """
        home = html.escape(str(state.get("home_team", "Home")))
        away = html.escape(str(state.get("away_team", "Away")))
        prediction = html.escape(str(state.get("prediction", "Bet")))
        odds = state.get("odds", 1.80)
        score_at_pick = html.escape(str(state.get("score_at_pick", "0-0")))
        final_score_esc = html.escape(str(final_score))
        
        if result == "WON":
            header = "✅ <b>BET SETTLED: WON!</b> 🚀🎉"
            status_text = f"<b>Profit:</b> +{(odds - 1.0):.2f} Units @ @{odds:.2f}"
        else:
            header = "❌ <b>BET SETTLED: MISSED</b> ⚠️"
            status_text = f"<b>Result:</b> -1.00 Unit"

        league = html.escape(str(state.get("league", "League")))
        league_notice = ""
        if result == "LOST":
            league_notice = (
                f"🚫 <b>LEAGUE SHORTLISTED/BLACKLISTED:</b>\n"
                f"• <code>{league}</code>\n"
                f"<i>(League excluded from future picks due to this loss)</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            )
        elif result == "WON":
            league_notice = (
                f"⭐ <b>WIN LEAGUE PROMOTED:</b>\n"
                f"• <code>{league}</code>\n"
                f"<i>(Granted HIGH PRIORITY status for future match scans)</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            )

        # Streak metrics display
        streak_block = ""
        if streak_summary:
            c_win = streak_summary.get("current_win_streak", 0)
            b_win = streak_summary.get("best_win_streak", 0)
            c_loss = streak_summary.get("current_loss_streak", 0)
            w_loss = streak_summary.get("worst_loss_streak", 0)
            tot_w = streak_summary.get("total_wins", 0)
            tot_l = streak_summary.get("total_losses", 0)
            wr = streak_summary.get("win_rate", 0.0)

            curr_streak_badge = f"🔥 {c_win} Wins in a row" if c_win > 0 else (f"⚠️ {c_loss} Losses in a row" if c_loss > 0 else "0")

            streak_block = (
                f"📈 <b>PERFORMANCE & STREAKS</b>\n"
                f"• <b>Current Streak:</b> <code>{curr_streak_badge}</code>\n"
                f"• <b>Best Win Streak:</b> <code>🏆 {b_win} Wins</code>\n"
                f"• <b>Worst Loss Streak:</b> <code>🛑 {w_loss} Losses</code>\n"
                f"• <b>All-Time Record:</b> <code>{tot_w}W - {tot_l}L ({wr}%)</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            )

        event_id = html.escape(str(state.get("active_match_id", "")))
        event_link = f'🆔 <b>Event ID:</b> <a href="https://inforadar.live/#/dashboard/soccer/game/{event_id}">#{event_id}</a>\n' if event_id else ""

        note_str = f"\n📝 <i>{html.escape(note)}</i>" if note else ""

        msg = (
            f"{header}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 <b>League:</b> {league}\n"
            f"⚔️ <b>Match:</b> {home} vs {away}\n"
            f"{event_link}"
            f"🎯 <b>Selection:</b> <b>{prediction}</b>\n"
            f"🔢 <b>Score at Pick:</b> <code>{score_at_pick}</code>\n"
            f"🏁 <b>Settled Score:</b> <code>{final_score_esc}</code>\n"
            f"💰 {status_text}{note_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{league_notice}"
            f"{streak_block}"
            f"🔓 <b>STATUS: BOT UNLOCKED</b>\n"
            f"<i>Scanning live games for the next high-value opportunity...</i>"
        )
        return self.send_message(msg)

    def send_startup_alert(self) -> bool:
        """Send a confirmation upon bot startup."""
        msg = (
            f"⚡ <b>RADAR BOT ONLINE & SCANNING</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Source:</b> Inforadar Live Stream\n"
            f"• <b>Market:</b> Total Goals (Over/Under)\n"
            f"• <b>Mode:</b> Single Active Bet Locking\n"
            f"• <b>Safety:</b> Anti-rate limit protection active\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Waiting for the next premium setup...</i>"
        )
        return self.send_message(msg)
