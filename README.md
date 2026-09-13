# ⚽ EchoHunt - Automated Inforadar Football Prediction Bot

An automated, intelligent live football prediction bot integrated with the **Inforadar API** (`https://inforadar.live/api/v1`) and **Telegram**.

---

## 🚀 Key Features

* **⚡ Real-Time Live Scanner**: Continuously monitors in-play football matches (`/live_games`) in prime betting minutes (45–80) with anti-rate-limit protection.
* **🎯 High-Edge Prediction Heuristics**: Ranks games using **Shots on Target** (statistically proven +21% edge), **Dangerous Attacks**, and tempo indicators.
* **💰 Real Live Odds Verification**: Queries the Total Goals market (`/soccer/game/odds?odds_market=3`) to ensure active lines and minimum value odds ($\ge 1.40$).
* **🔒 Single-Bet State Locking**: Locks onto one pick at a time. No new picks are published until the active wager settles, preserving bankroll management.
* **⚖️ Strict Settlement Policy**:
  * **Only Full Win = WON** ($\ge 0.5$ beyond line).
  * **Half Win (HW) and Half Loss (HL) are strictly calculated as a LOSS**.
* **🚫 1-Loss League Blacklist**: Automatically blacklists any league that produces a single loss (`loss_leagues.json`).
* **⭐ Winning League Priority**: Winning leagues receive **HIGH PRIORITY** and top ranking in future scans (`league_performance.json`).
* **📈 Streak & Drawdown Tracker**: Tracks Current Win Streak, Best Win Streak, Current Loss Streak, Worst Loss Streak, and Win Rate % (`streak_stats.json`).
* **📱 High-Impact Telegram Alerts**: Formatted with HTML, momentum meters, and streak performance dashboards.

---

## 🛠 Project Structure

```text
EchoHunt/
├── bot.py                  # Main orchestration & polling loop
├── config.py               # Credentials, API settings & strategy thresholds
├── api_client.py           # Robust HTTP client with session keep-alive & retries
├── engine.py               # Statistical ranking & odds validation engine
├── settlement.py           # Outcome resolver & strict Asian line evaluator
├── notifier.py             # Rich HTML Telegram notification dispatcher
├── league_manager.py       # Win priority & loss blacklist manager
├── streak_tracker.py       # Win/loss streak & drawdown tracker
├── state_manager.py        # Single active bet lock & persistence
├── Procfile                # 1-click cloud deployment worker
├── Dockerfile              # Docker container setup
└── requirements.txt        # Python dependencies
```

---

## 🏃 Local Run

1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the bot:
   ```bash
   python bot.py
   ```

---

## ☁️ 24/7 Cloud Deployment

### Option A: Railway / Render (1-Click Worker)
1. Push this repository to GitHub.
2. Link your repository on [Railway](https://railway.app) or [Render](https://render.com).
3. Select **Background Worker** (uses `Procfile`).
4. The bot will run 24/7 continuously.

### Option B: Docker Container
```bash
docker build -t echohunt-bot .
docker run -d --name echohunt --restart always echohunt-bot
```
