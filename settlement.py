"""
Settlement Engine for locked bets.
Monitors active game status and determines WON / LOST outcomes.
"""
import time
import logging
from engine import parse_score

logger = logging.getLogger("settlement")

# Max minutes to wait before force-settling on current score
# (handles APIs that never return timeStatus=3 for some leagues)
FORCE_SETTLE_AFTER_MINUTES = 130


def evaluate_strict_total_outcome(direction: str, target_line: float, total_goals: int) -> tuple:
    """
    Evaluates Total Over/Under Asian handicap outcome:
    - Full Win  (diff >= +0.5)  -> WON
    - Half Win  (diff == +0.25) -> HALF_WIN  (50% stake profit; no longer counted as full loss)
    - Half Loss (diff == -0.25) -> HALF_LOSS (50% stake lost)
    - Push      (diff ==  0.0)  -> VOID      (full stake refund)
    - Full Loss (diff <= -0.5)  -> LOST

    FIX #4: Old code counted HW and HL both as full LOST.
    Real data showed 13 losses from OVER 1.75 HW trap alone.
    Now correctly returns HALF_WIN / HALF_LOSS for quarter-line splits.
    """
    diff = round(total_goals - target_line if direction == "OVER" else target_line - total_goals, 2)

    # 1. Full Win: goals beat line by >= 0.5
    if diff >= 0.5:
        return "WON", f"Full Win (+{diff:.2f} beyond line {target_line})"

    # 2. Asian Quarter Half Win (+0.25) -> HALF WIN (half stake returned as profit)
    elif diff == 0.25:
        return "HALF_WIN", f"Half Win (HW) +0.25 on line {target_line} — half stake profit"

    # 3. Asian Quarter Half Loss (-0.25) -> HALF LOSS (half stake lost)
    elif diff == -0.25:
        return "HALF_LOSS", f"Half Loss (HL) -0.25 on line {target_line} — half stake lost"

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
            # HALF_WIN / HALF_LOSS are passed through; streak_tracker handles them
            if self.streak_tracker and result in ["WON", "LOST", "VOID", "PUSH", "HALF_WIN", "HALF_LOSS"]:
                outcome["streak_summary"] = self.streak_tracker.record_bet_result(result)

            # Update per-league, per-direction performance records
            # HALF_WIN counts as a win; HALF_LOSS counts as a loss for league memory
            if self.league_mgr:
                league_id = state.get("league_id")
                league_name = state.get("league")
                home = state.get("home_team", "Home")
                away = state.get("away_team", "Away")
                match_desc = f"{home} vs {away}"

                if result in ["WON", "HALF_WIN"] and league_name:
                    self.league_mgr.record_win(league_id, league_name, direction, match_desc)
                elif result in ["LOST", "HALF_LOSS"] and league_name:
                    self.league_mgr.record_loss(league_id, league_name, direction, match_desc)
        return outcome

    def _detect_shootout_score(self, game: dict, state: dict) -> str | None:
        """
        Detect if a penalty shootout occurred and inflated the 'scores' string.
        Returns the actual in-game (90'/120') score if detected, else None.
        Shootout goals are lumped into 'scores' by the API, but bookmakers do not count them.
        """
        scores = game.get("scores") or ""
        _, _, total = parse_score(scores)
        stats = game.get("stats") or {}
        goals_stat = stats.get("goals")
        if not goals_stat or len(goals_stat) < 2:
            return None

        try:
            st_home = int(goals_stat[0])
            st_away = int(goals_stat[1])
            st_total = st_home + st_away
            st_score = f"{st_home}-{st_away}"
        except (ValueError, TypeError, IndexError):
            return None

        # Shootout goals cause a massive jump in total goals (>= 2)
        if total - st_total >= 2:
            events = game.get("events") or []
            event_goals = len([e for e in events if e.get("type") == "goal"])
            prev_score = state.get("_last_score") or state.get("score_at_pick")
            _, _, prev_total = parse_score(prev_score) if prev_score else (0, 0, None)

            # Highly reliable if stats matches events timeline or last polled score
            if event_goals == st_total or (prev_total is not None and prev_total == st_total):
                logger.info(f"Penalty shootout detected! Settling on regular score {st_score}, not shootout final {scores}")
                return st_score
        return None

    def _check_force_settle(self, state: dict, scores: str, total_goals: int,
                             time_status: str, match_minute) -> dict | None:
        """
        Force-settle checks for matches where the API gets stuck and never
        returns timeStatus=3. Returns a settled outcome dict or None.

        Triggers when ANY of the following are true:
          1. Elapsed time since pick > FORCE_SETTLE_AFTER_MINUTES
          2. timeStatus=2 (half-time signal) AND minute > 90
             (some APIs return HT=2 at FT instead of 3)
        """
        direction = state.get("direction")
        target_line = state.get("target_line")

        # If Extra Time normal-time score was locked, settle on that
        nt_score = state.get("score_at_normal_time_end")
        score_adj_note = ""
        if nt_score:
            _, _, nt_total = parse_score(nt_score)
            if nt_total is not None:
                scores = nt_score
                total_goals = nt_total
                score_adj_note = f" (Settled on 90' score {nt_score}, excluding ET)"

        # --- Trigger 1: Elapsed time timeout ---
        pick_ts = state.get("pick_timestamp")
        elapsed_min = 0
        if pick_ts:
            elapsed_min = (time.time() - pick_ts) / 60

        if elapsed_min >= FORCE_SETTLE_AFTER_MINUTES:
            res, note = evaluate_strict_total_outcome(direction, target_line, total_goals)
            logger.warning(
                f"FORCE SETTLE triggered (elapsed={elapsed_min:.0f} min > {FORCE_SETTLE_AFTER_MINUTES} min). "
                f"timeStatus={time_status}, score={scores}"
            )
            return self._record_outcome(state, {
                "is_settled": True,
                "result": res,
                "final_score": scores,
                "note": f"Force-settled after {elapsed_min:.0f} min (API stuck at timeStatus={time_status}).{score_adj_note} {note}"
            })

        # --- Trigger 2: API returns timeStatus=2 at minute > 90 ---
        # On Inforadar some competitions report timeStatus=2 instead of 3 at FT
        if time_status == "2" and match_minute is not None:
            try:
                minute_int = int(match_minute)
            except (ValueError, TypeError):
                minute_int = 0

            if minute_int >= 90:
                res, note = evaluate_strict_total_outcome(direction, target_line, total_goals)
                logger.warning(
                    f"FORCE SETTLE triggered (timeStatus=2 at minute={minute_int} >= 90). "
                    f"API likely stuck at HT code after FT. score={scores}"
                )
                return self._record_outcome(state, {
                    "is_settled": True,
                    "result": res,
                    "final_score": scores,
                    "note": f"Force-settled: API returned timeStatus=2 at minute {minute_int} (likely FT).{score_adj_note} {note}"
                })

        return None  # Not yet triggered

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
            logger.warning(f"Could not fetch game view for active match {match_id}. Checking finished_games archive...")
            try:
                finished_list = self.api_client.get_finished_games(sport_id=1, per_page=50)
                for fg in finished_list:
                    if str(fg.get("id")) == str(match_id):
                        logger.info(f"Match {match_id} found in finished_games archive! Score: {fg.get('scores')}")
                        game_data = fg
                        break
            except Exception as fe:
                logger.warning(f"Error querying finished_games fallback for {match_id}: {fe}")

        if not game_data:
            logger.warning(f"Match {match_id} not available in game_view or finished_games archive.")

            # --- API-down force-settle ---
            # If API has been broken for > FORCE_SETTLE_AFTER_MINUTES, use the
            # last successfully fetched score rather than waiting forever.
            pick_ts = state.get("pick_timestamp")
            if pick_ts:
                elapsed_min = (time.time() - pick_ts) / 60
                last_score = state.get("last_known_score")
                last_goals = state.get("last_known_goals", 0)
                if elapsed_min >= FORCE_SETTLE_AFTER_MINUTES and last_score is not None:
                    direction = state.get("direction")
                    target_line = state.get("target_line")
                    res, note = evaluate_strict_total_outcome(direction, target_line, last_goals)
                    logger.warning(
                        f"FORCE SETTLE (API DOWN) triggered: elapsed={elapsed_min:.0f} min, "
                        f"last known score={last_score}"
                    )
                    return self._record_outcome(state, {
                        "is_settled": True,
                        "result": res,
                        "final_score": last_score,
                        "note": (
                            f"Force-settled after {elapsed_min:.0f} min of API failure. "
                            f"Last known score: {last_score}. {note}"
                        )
                    })

            return {"is_settled": False}

        time_status = str(game_data.get("timeStatus", ""))
        scores = game_data.get("scores", "0-0")
        h_score, a_score, total_goals = parse_score(scores)
        match_minute = (game_data.get("time") or {}).get("tm")

        # Persist the last successfully fetched score to state for API-down fallback
        if state.get("_state_mgr"):
            state["_state_mgr"].update_last_known_score(scores, total_goals)

        # --- Extra-Time Clock Tracking (Spysheet Clock Dip Pattern) ---
        minute_val = None
        try:
            minute_val = int(match_minute) if match_minute is not None else None
        except (ValueError, TypeError):
            minute_val = None

        if minute_val is not None and time_status in ["1", "2"]:
            prev_minute = state.get("_last_minute")
            prev_score = state.get("_last_score")

            # 1. Detect clock dip: clock went backwards from >90' down to <=90' (Extra Time kickoff)
            if (prev_minute is not None and prev_minute > 90
                    and minute_val <= 90
                    and not state.get("score_at_normal_time_end")
                    and not state.get("_candidate_nt_score")
                    and prev_score is not None):
                state["_candidate_nt_score"] = prev_score
                logger.info(f"Clock dip detected (>90m -> {minute_val}m): candidate normal-time score saved as {prev_score}")
                if state.get("_state_mgr"):
                    state["_state_mgr"].update_extra_time_state(
                        minute_val, scores, candidate_nt=prev_score
                    )

            # 2. Confirm Extra Time: clock climbs past 95' with candidate score saved
            if (minute_val >= 95 and state.get("_candidate_nt_score")
                    and not state.get("score_at_normal_time_end")):
                candidate = state["_candidate_nt_score"]
                state["score_at_normal_time_end"] = candidate
                logger.info(f"Extra Time confirmed at {minute_val}m! Normal-time (90') score locked at {candidate}")
                if state.get("_state_mgr"):
                    state["_state_mgr"].update_extra_time_state(
                        minute_val, scores, score_at_nt=candidate
                    )

            state["_last_minute"] = minute_val
            state["_last_score"] = scores
            if state.get("_state_mgr"):
                state["_state_mgr"].update_extra_time_state(minute_val, scores)

        # Calculate elapsed minutes for logging
        pick_ts = state.get("pick_timestamp")
        elapsed_str = ""
        if pick_ts:
            elapsed_min = (time.time() - pick_ts) / 60
            elapsed_str = f", elapsed={elapsed_min:.0f}m"

        nt_locked = state.get("score_at_normal_time_end")
        nt_badge = f", NT_locked={nt_locked}" if nt_locked else ""
        logger.info(
            f"Checking locked match {match_id}: score={scores} (Total: {total_goals}), "
            f"line={target_line}, timeStatus={time_status}, minute={match_minute}{elapsed_str}{nt_badge}"
        )

        # --- Determine Effective Settlement Score (Extra Time & Shootout Filtering) ---
        so_score = self._detect_shootout_score(game_data, state)
        settle_score = scores
        settle_goals = total_goals
        score_adj_note = ""

        if nt_locked:
            _, _, nt_total = parse_score(nt_locked)
            if nt_total is not None:
                settle_score = nt_locked
                settle_goals = nt_total
                score_adj_note = f" (Settled on 90' normal-time score {nt_locked}, excluding ET goals)"
                logger.info(f"Extra Time active: settling on normal-time score {nt_locked} (total {nt_total}), not ET final {scores}")
        elif so_score:
            _, _, so_total = parse_score(so_score)
            if so_total is not None:
                settle_score = so_score
                settle_goals = so_total
                score_adj_note = f" (Settled on in-play score {so_score}, excluding shootout goals)"
                logger.info(f"Penalty Shootout active: settling on in-game score {so_score} (total {so_total}), not shootout final {scores}")

        # -----------------
        # OVER Settlement
        # -----------------
        if direction == "OVER":
            # Early Full Win: regular time goals exceed line by >= 0.5 → mathematically guaranteed
            # (Only allowed if NOT in Extra Time; ET goals do not count for standard 90-min bets)
            diff = round(settle_goals - target_line, 2)
            if diff >= 0.5:
                return self._record_outcome(state, {
                    "is_settled": True,
                    "result": "WON",
                    "final_score": settle_score,
                    "note": f"Full Win confirmed! Total goals: {settle_goals} >= Line {target_line} + 0.5{score_adj_note}"
                })

            # Normal finish (timeStatus=3)
            if time_status == "3":
                res, note = evaluate_strict_total_outcome(direction, target_line, settle_goals)
                return self._record_outcome(state, {
                    "is_settled": True,
                    "result": res,
                    "final_score": settle_score,
                    "note": f"Match finished.{score_adj_note} {note}"
                })

        # -----------------
        # UNDER Settlement
        # -----------------
        elif direction == "UNDER":
            # Early Full Loss: goals already exceed line by >= 0.5
            diff = round(target_line - settle_goals, 2)
            if diff <= -0.5:
                return self._record_outcome(state, {
                    "is_settled": True,
                    "result": "LOST",
                    "final_score": settle_score,
                    "note": f"Full Loss confirmed. Total goals: {settle_goals} exceeded line {target_line}{score_adj_note}"
                })

            # Normal finish (timeStatus=3)
            if time_status == "3":
                res, note = evaluate_strict_total_outcome(direction, target_line, settle_goals)
                return self._record_outcome(state, {
                    "is_settled": True,
                    "result": res,
                    "final_score": settle_score,
                    "note": f"Match finished.{score_adj_note} {note}"
                })

        # Cancelled, Postponed or Abandoned
        if time_status in ["4", "5", "6", "7", "8", "9"]:
            return self._record_outcome(state, {
                "is_settled": True,
                "result": "VOID",
                "final_score": scores,
                "note": f"Match cancelled or abandoned (timeStatus={time_status})"
            })

        # -----------------
        # Force-settle fallback (API stuck — never returns timeStatus=3)
        # -----------------
        force = self._check_force_settle(state, scores, total_goals, time_status, match_minute)
        if force:
            return force

        return {"is_settled": False}
