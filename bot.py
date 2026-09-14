"""
Main orchestrator for the Inforadar Automated Telegram Prediction Bot.
"""
import time
import sys
import logging
from config import POLL_INTERVAL_SECONDS, MIN_EDGE_SCORE
from api_client import InforadarClient
from state_manager import StateManager
from notifier import TelegramNotifier
from engine import PredictionEngine
from settlement import SettlementEngine
from league_manager import LeagueManager
from streak_tracker import StreakTracker

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Setup console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("main_bot")

def run_bot():
    logger.info("Initializing Inforadar Prediction Bot...")
    api_client = InforadarClient()
    state_mgr = StateManager()
    notifier = TelegramNotifier()
    league_mgr = LeagueManager()
    streak_tracker = StreakTracker()
    engine = PredictionEngine(api_client, league_mgr=league_mgr)
    settlement_engine = SettlementEngine(api_client, league_mgr=league_mgr, streak_tracker=streak_tracker)

    tracked = league_mgr.get_tracked_count()
    over_pref = league_mgr.get_over_preferred_count()
    under_pref = league_mgr.get_under_preferred_count()
    summary = streak_tracker.get_summary()
    logger.info(f"League Records: {tracked} Tracked | {over_pref} OVER-favoured | {under_pref} UNDER-favoured.")
    logger.info(f"Streak Records: Current Win Streak={summary['current_win_streak']} | Best Win Streak={summary['best_win_streak']} | Worst Loss Streak={summary['worst_loss_streak']}")
    logger.info(f"Bot State on start: {'LOCKED' if state_mgr.is_locked else 'UNLOCKED'}")
    
    # Send bot online greeting
    notifier.send_startup_alert()

    while True:
        try:
            # 1. If Locked: Monitor the active wager
            if state_mgr.is_locked:
                active_id = state_mgr.active_match_id
                pick_name = state_mgr.state.get("prediction")
                logger.info(f"Bot is currently LOCKED on match {active_id} ({pick_name}). Monitoring for settlement...")
                
                # Inject state_mgr reference so settlement can persist last known score
                active_state = dict(state_mgr.state)
                active_state["_state_mgr"] = state_mgr

                # Seed last_known_score from score_at_pick if never set yet
                if active_state.get("last_known_score") is None and active_state.get("score_at_pick"):
                    state_mgr.update_last_known_score(
                        active_state["score_at_pick"],
                        active_state.get("goals_at_pick", 0)
                    )
                    active_state["last_known_score"] = active_state["score_at_pick"]
                    active_state["last_known_goals"] = active_state.get("goals_at_pick", 0)

                settlement = settlement_engine.check_match_settlement(active_state)
                if settlement.get("is_settled"):
                    result = settlement["result"]
                    final_score = settlement["final_score"]
                    note = settlement.get("note", "")
                    streak_info = settlement.get("streak_summary")
                    logger.info(f"Match {active_id} settled: {result}! Final Score: {final_score}")
                    
                    # Alert Telegram and unlock
                    notifier.send_settlement_alert(state_mgr.state, result, final_score, note, streak_summary=streak_info)
                    state_mgr.unlock_bet()
                else:
                    logger.info(f"Match {active_id} is still in progress. Checking again in {POLL_INTERVAL_SECONDS}s.")

            # 2. If Unlocked: Scan live games for best single match
            else:
                logger.info("Bot is UNLOCKED. Scanning live games stream...")
                live_games = api_client.get_live_games(sport_id=1, page=1, per_page=1000)
                
                if live_games:
                    logger.info(f"Fetched {len(live_games)} active live games. Running prediction engine...")
                    best_pick = engine.find_best_pick(live_games)
                    
                    if best_pick:
                        match = best_pick["match"]
                        m_id = match.get("id")
                        home = match.get("home", {}).get("name")
                        away = match.get("away", {}).get("name")
                        pred = best_pick.get("prediction")
                        odds = best_pick.get("odds")
                        score = best_pick.get("edge_score")

                        # Guard: prevent picking the same match a second time
                        if state_mgr.is_match_already_picked(str(m_id)):
                            logger.info(f"Match {m_id} ({home} vs {away}) was already picked this session. Skipping duplicate.")
                        else:
                            logger.info(f"⚡ BEST PICK FOUND! Match {m_id} ({home} vs {away}) -> {pred} @ {odds} (Edge Score: {score}%)")
                            
                            # Send pick to Telegram
                            delivered = notifier.send_pick_alert(match, best_pick)
                            if delivered:
                                # Lock bot state
                                state_mgr.lock_bet(match, best_pick)
                            else:
                                logger.error("Failed to notify Telegram; not locking state.")
                    else:
                        logger.info(f"No match passed the {MIN_EDGE_SCORE}% edge threshold and odds filter this cycle.")
                else:
                    logger.warning("Empty response or connection issue fetching live games.")

        except KeyboardInterrupt:
            logger.info("Bot shutdown requested by user. Exiting cleanly.")
            break
        except Exception as e:
            logger.exception(f"Unexpected error in main polling loop: {e}")

        logger.info(f"Sleeping for {POLL_INTERVAL_SECONDS} seconds...\n" + ("-" * 60))
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    run_bot()
