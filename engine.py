"""
Prediction & Analytics Engine for Inforadar live data.
Calculates Edge Scores and selects the optimal Total Over/Under opportunity.
"""
import re
import time
import logging
from config import (
    MIN_MATCH_MINUTE,
    MAX_MATCH_MINUTE,
    MIN_EDGE_SCORE,
    MIN_ODDS,
    MAX_ODDS,
    MAX_ODDS_LOOKUPS,
)

logger = logging.getLogger("engine")

# Regex to filter simulated / esports football with fake clocks & inflated scoring
SIMULATED = re.compile(
    r"esoccer|e-soccer|e\s?football|efootball|cyber|volta|fifa|pes\b|"
    r"battle|\bsim(ulated)?\b|liga\s?pro|\b(8|10|12)\s?min",
    re.I,
)

def parse_stat_pair(stat_val) -> tuple:
    """Safely parse [home, away] from API stats."""
    if isinstance(stat_val, list) and len(stat_val) >= 2:
        try:
            return int(stat_val[0]), int(stat_val[1])
        except (ValueError, TypeError):
            pass
    return 0, 0

def parse_score(score_str: str) -> tuple:
    """Parse '1-0' into (home, away, total_goals)."""
    if not score_str or "-" not in str(score_str):
        return 0, 0, 0
    try:
        parts = str(score_str).split("-")
        h, a = int(parts[0].strip()), int(parts[1].strip())
        return h, a, h + a
    except (ValueError, IndexError):
        return 0, 0, 0

class PredictionEngine:
    def __init__(self, api_client, league_mgr=None):
        self.api_client = api_client
        self.league_mgr = league_mgr

    def evaluate_live_match(self, match: dict) -> dict:
        """
        Calculates match stats and edge score for a single live game.
        Returns evaluation dict or None if ineligible.
        """
        league_id = str(match.get("league", {}).get("id", ""))
        league_name = match.get("league", {}).get("name", "")

        # Reject simulated esports matches (FIFA, cyber, 8/10/12 min)
        if SIMULATED.search(league_name or ""):
            return None

        time_info = match.get("time") or {}
        minute = time_info.get("tm")
        time_status = match.get("timeStatus")

        # Must be in-play (timeStatus "1" or "2") and in target minute window
        if str(time_status) not in ["1", "2"] or minute is None:
            return None
        
        try:
            minute = int(minute)
        except ValueError:
            return None

        if minute < MIN_MATCH_MINUTE or minute > MAX_MATCH_MINUTE:
            return None

        stats = match.get("stats") or {}
        sot_h, sot_a = parse_stat_pair(stats.get("on_target"))
        da_h, da_a = parse_stat_pair(stats.get("dangerous_attacks"))
        corn_h, corn_a = parse_stat_pair(stats.get("corners"))
        
        sot_total = sot_h + sot_a
        da_total = da_h + da_a
        corn_total = corn_h + corn_a

        h_goals, a_goals, current_goals = parse_score(match.get("scores"))
        goal_diff = abs(h_goals - a_goals)

        # -----------------
        # OVER Calculation (Statistical Edge backed by historical data)
        # -----------------
        over_score = 0

        # Shots on Target is the #1 correlated factor (+21% Over rate)
        if sot_total >= 11:
            over_score += 45
        elif sot_total >= 8:
            over_score += 35
        elif sot_total >= 6:
            over_score += 25
        elif sot_total >= 4:
            over_score += 15

        # Dangerous Attacks intensity
        if da_total >= 110:
            over_score += 25
        elif da_total >= 80:
            over_score += 18
        elif da_total >= 55:
            over_score += 10

        # Corners pressure
        if corn_total >= 8:
            over_score += 10

        # Close game pressure (0-0, 1-1, or 1-goal difference where teams must attack)
        if goal_diff <= 1:
            over_score += 15

        # Prime 2nd half acceleration window
        if 55 <= minute <= 78:
            over_score += 10

        # -----------------
        # UNDER Calculation
        # -----------------
        under_score = 0
        if minute >= 65:
            if sot_total <= 2:
                under_score += 45
            elif sot_total <= 4:
                under_score += 25

            if da_total <= 50:
                under_score += 25
            elif da_total <= 70:
                under_score += 15

            if goal_diff >= 2:  # One team has put the game away, slower tempo
                under_score += 15

        # Apply per-league, per-direction historical bias
        dir_mods = {"over": 0, "under": 0}
        if self.league_mgr:
            dir_mods = self.league_mgr.get_direction_modifiers(league_id, league_name)
            over_score += dir_mods["over"]
            under_score += dir_mods["under"]
            if dir_mods["over"] != 0 or dir_mods["under"] != 0:
                logger.debug(
                    f"League '{league_name}' modifiers: OVER {dir_mods['over']:+d} / UNDER {dir_mods['under']:+d}"
                )

        # Decide raw statistical direction
        raw_direction = None
        raw_edge_score = 0
        if over_score >= under_score and over_score >= MIN_EDGE_SCORE:
            raw_direction = "OVER"
            raw_edge_score = min(99, over_score)
        elif under_score > over_score and under_score >= MIN_EDGE_SCORE:
            raw_direction = "UNDER"
            raw_edge_score = min(99, under_score)
        else:
            return None

        # Check for league contrarian inversion:
        # If this league has net losses in raw_direction, invert it!
        direction = raw_direction
        edge_score = raw_edge_score
        was_inverted = False
        inversion_reason = ""

        if self.league_mgr:
            is_inv, new_dir, reason = self.league_mgr.check_direction_inversion(league_id, raw_direction)
            if is_inv:
                direction = new_dir
                was_inverted = True
                inversion_reason = reason
                logger.info(
                    f"Contrarian Flip for league '{league_name}': "
                    f"Model suggested {raw_direction} ({raw_edge_score}%) -> Flipped to {direction}! {reason}"
                )

        # Fetch league summary for display in alerts
        league_summary = None
        if self.league_mgr:
            league_summary = self.league_mgr.get_league_summary(league_id)

        return {
            "match": match,
            "direction": direction,
            "raw_direction": raw_direction,
            "was_inverted": was_inverted,
            "inversion_reason": inversion_reason,
            "edge_score": edge_score,
            "over_mod": dir_mods["over"],
            "under_mod": dir_mods["under"],
            "league_summary": league_summary,
            "minute": minute,
            "current_goals": current_goals,
            "sot_h": sot_h,
            "sot_a": sot_a,
            "da_h": da_h,
            "da_a": da_a,
            "corn_h": corn_h,
            "corn_a": corn_a,
        }

    def fetch_verified_odds(self, candidate: dict) -> dict:
        """
        Fetches live odds for candidate from /soccer/game/odds?odds_market=3
        and validates that the line is active and meets criteria.
        """
        match = candidate["match"]
        match_id = match.get("id")
        direction = candidate["direction"]
        current_goals = candidate["current_goals"]

        odds_data = self.api_client.get_game_odds(match_id, odds_market="3")
        if not odds_data or not isinstance(odds_data, list):
            logger.info(f"No odds returned for match {match_id}")
            return None

        # Find Total Goals market
        total_market = None
        for m in odds_data:
            if isinstance(m, dict) and m.get("name") == "Total":
                total_market = m
                break

        if not total_market or not total_market.get("odds"):
            logger.info(f"Total market not found or empty for match {match_id}")
            return None

        selected_odds = None
        target_line = None
        prediction = None

        # Check recent live odds rows to find an active qualifying line
        for tick in total_market["odds"][:5]:
            try:
                line_val = float(tick.get("row2"))
                over_val = tick.get("row1")
                under_val = tick.get("row3")

                over_odds = float(over_val) if over_val is not None else None
                under_odds = float(under_val) if under_val is not None else None
            except (TypeError, ValueError):
                continue

            if direction == "OVER":
                if over_odds and MIN_ODDS <= over_odds <= MAX_ODDS:
                    if line_val > current_goals:
                        selected_odds = over_odds
                        target_line = line_val
                        prediction = f"TOTAL OVER {line_val:g}"
                        break
            elif direction == "UNDER":
                if under_odds and MIN_ODDS <= under_odds <= MAX_ODDS:
                    if line_val >= current_goals:
                        selected_odds = under_odds
                        target_line = line_val
                        prediction = f"TOTAL UNDER {line_val:g}"
                        break

        if not selected_odds:
            logger.info(f"Match {match_id} ({direction}) did not have qualifying live odds on total market.")
            return None

        pick = candidate.copy()
        pick.update({
            "prediction": prediction,
            "target_line": target_line,
            "odds": selected_odds,
            "timestamp": int(time.time())
        })
        return pick

    def find_best_pick(self, live_games: list) -> dict:
        """
        Scans all live games, evaluates edge score, sorts by score,
        and retrieves live odds for the highest ranking candidate.
        """
        candidates = []
        for match in live_games:
            evaluated = self.evaluate_live_match(match)
            if evaluated:
                candidates.append(evaluated)

        if not candidates:
            logger.info(f"Scanned {len(live_games)} games; 0 met live statistical criteria.")
            return None

        # Sort by edge score descending (modifiers are already baked in)
        candidates.sort(key=lambda x: x["edge_score"], reverse=True)
        top_cand = candidates[0]
        over_mod = top_cand.get("over_mod", 0)
        under_mod = top_cand.get("under_mod", 0)
        mod_badge = ""
        if over_mod != 0 or under_mod != 0:
            mod_badge = f" [League bias: OVER {over_mod:+d} / UNDER {under_mod:+d}]"
        logger.info(f"Found {len(candidates)} qualifying candidates. Top pick: {top_cand['edge_score']}%{mod_badge}")

        # Check odds for the top candidates, bounded by MAX_ODDS_LOOKUPS
        odds_check_limit = min(len(candidates), MAX_ODDS_LOOKUPS)
        for top_candidate in candidates[:odds_check_limit]:
            verified = self.fetch_verified_odds(top_candidate)
            if verified:
                return verified

        logger.info(f"Checked top {odds_check_limit} candidates; none had qualifying live odds.")
        return None
