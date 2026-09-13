"""
Settlement Engine for locked bets.
Monitors active game status and determines WON / LOST outcomes.
"""
import logging
from engine import parse_score

logger = logging.getLogger("settlement")

def evaluate_strict_total_outcome(direction: str, target_line: float, total_goals: int) -> tuple:
    """
    Evaluates Total Over/Under under strict rules:
    - ONLY Full Won is calculated as a WIN ('WON').
    - Half Win (HW, e.g. +0.25) is calculated as a LOSS ('LOST')!
    - Half Loss (HL, e.g. -0.25) is calculated as a LOSS ('LOST')!
    - Push (exact whole line, e.g. 0.0) is 'VOID'.
    - Full Loss (diff <= -0.5) is 'LOST'.
    """
    diff = round(total_goals - target_line if direction == "OVER" else target_line - total_goals, 2)

    # 1. Full Win: goals beat line by >= 0.5
    if diff >= 0.5:
        return "WON", f"Full Win (+{diff:.2f} beyond line {target_line})"

    # 2. Asian Quarter Half Win (HW, +0.25) -> STRICTLY CALCULATED AS LOSS!
    elif diff == 0.25:
        return "LOST", f"Half Win (HW) calculated as LOSS per strict rules (+0.25 on line {target_line})"

    # 3. Asian Quarter Half Loss (HL, -0.25) -> CALCULATED AS LOSS!
    elif diff == -0.25:
        return "LOST", f"Half Loss (HL) calculated as LOSS (-0.25 on line {target_line})"

    # 4. Push (exact whole line refund)
    elif diff == 0.0:
        return "VOID", f"Push (Exact goal line {target_line} matched)"

    # 5. Full Loss
    else:
        return "LOST", f"Full Loss ({diff:.2f} from line {target_line})"

class SettlementEngine:
    def __init__(self, api_client, league_mgr=None, streak_tracker=None):
        self.api_client = api_client
        self.league_mgr = league_mgr
        self.streak_tracker = streak_tracker

    def _record_outcome(self, state: dict, outcome: dict) -> dict:
        if outcome.get("is_settled"):
            result = outcome.get("result")
            direction = state.get("direction", "OVER")  # "OVER" or "UNDER"

            # Update streak records
            if self.streak_tracker and result in ["WON", "LOST"]:
                outcome["streak_summary"] = self.streak_tracker.record_bet_result(result)

            # Update per-league, per-direction performance records
            if self.league_mgr:
                league_id = state.get("league_id")
                league_name = state.get("league")
                home = state.get("home_team", "Home")
                away = state.get("away_team", "Away")
                match_desc = f"{home} vs {away}"

                if result == "WON" and league_name:
                    self.league_mgr.record_win(league_id, league_name, direction, match_desc)
                elif result == "LOST" and league_name:
                    self.league_mgr.record_loss(league_id, league_name, direction, match_desc)
        return outcome


    def check_match_settlement(self, state: dict) -> dict:
        """
        Polls the locked match and checks if bet has settled.
        Returns {
            'is_settled': bool,
            'result': 'WON' | 'LOST' | 'VOID',
            'final_score': str,
            'note': str
        }
        """
        match_id = state.get("active_match_id")
        direction = state.get("direction")
        target_line = state.get("target_line")

        if not match_id or not direction or target_line is None:
            return {"is_settled": False}

        game_data = self.api_client.get_game_view(match_id)
        if not game_data:
            logger.warning(f"Could not fetch game view for active match {match_id}")
            return {"is_settled": False}

        time_status = str(game_data.get("timeStatus", ""))
        scores = game_data.get("scores", "0-0")
        h_score, a_score, total_goals = parse_score(scores)

        logger.info(f"Checking locked match {match_id}: score={scores} (Total: {total_goals}), line={target_line}, timeStatus={time_status}")

        # -----------------
        # OVER Settlement
        # -----------------
        if direction == "OVER":
            # Early Full Win: If current goals exceed target line by >= 0.5, Full Win is mathematically guaranteed!
            diff = round(total_goals - target_line, 2)
            if diff >= 0.5:
                return self._record_outcome(state, {
                    "is_settled": True,
                    "result": "WON",
                    "final_score": scores,
                    "note": f"Full Win confirmed! Total goals: {total_goals} >= Line {target_line} + 0.5"
                })

            # Finished match settlement
            if time_status == "3":
                res, note = evaluate_strict_total_outcome(direction, target_line, total_goals)
                return self._record_outcome(state, {
                    "is_settled": True,
                    "result": res,
                    "final_score": scores,
                    "note": f"Match finished. {note}"
                })

        # -----------------
        # UNDER Settlement
        # -----------------
        elif direction == "UNDER":
            # Early Full Loss: If current goals already exceed line by >= 0.5, bet is mathematically lost
            diff = round(target_line - total_goals, 2)
            if diff <= -0.5:
                return self._record_outcome(state, {
                    "is_settled": True,
                    "result": "LOST",
                    "final_score": scores,
                    "note": f"Full Loss confirmed. Total goals: {total_goals} exceeded line {target_line}"
                })

            # Finished match settlement
            if time_status == "3":
                res, note = evaluate_strict_total_outcome(direction, target_line, total_goals)
                return self._record_outcome(state, {
                    "is_settled": True,
                    "result": res,
                    "final_score": scores,
                    "note": f"Match finished. {note}"
                })

        # Cancelled, Postponed or Abandoned
        if time_status in ["4", "5", "6", "7", "8", "9"]:
            return self._record_outcome(state, {
                "is_settled": True,
                "result": "VOID",
                "final_score": scores,
                "note": f"Match cancelled or abandoned (timeStatus={time_status})"
            })

        return {"is_settled": False}
