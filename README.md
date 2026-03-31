# 🌡️ ClimateBrain

**Open-source AI-powered multi-person comfort controller for air conditioners.**

A drop-in replacement for the discontinued Ambi Climate — runs locally on your hardware, learns what's comfortable for everyone in the room, and controls your AC via IR through off-the-shelf devices. No cloud dependency. No subscriptions. You own your data.

---

## What It Does

1. **Learns your AC** — registers each air conditioner by name, learns all available modes, temperature ranges, fan speeds, and IR commands
2. **Monitors conditions** — reads indoor temperature/humidity, pulls outdoor weather and "feels like" data
3. **Learns your comfort** — each household member gives simple feedback ("too hot", "comfortable", "too cold") and the system builds a personal comfort profile
4. **Optimizes for everyone** — when multiple people are in the room, the system finds the AC setting that minimizes discomfort across all occupants
5. **Predicts and adjusts** — learns your room's thermal response and makes proactive changes before anyone gets uncomfortable

## Architecture

```
┌──────────────────────────────┐
│  Your iPhone / Mac / Siri    │
│  (Apple Home, from anywhere) │
└──────────┬───────────────────┘
           ↕ HomeKit / Matter
┌──────────────────────────────┐
│  SwitchBot Hub Mini (per room)│
│  + SwitchBot Meter (per room) │
└──────────┬───────────────────┘
           ↕ SwitchBot API
┌──────────────────────────────┐
│  ClimateBrain (Mac / Pi)     │
│  • FastAPI server            │
│  • Comfort learning engine   │
│  • Multi-person optimizer    │
│  • Weather integration       │
│  • Control loop (5 min)      │
│  • Web UI for feedback       │
└──────────────────────────────┘
```

## Hardware Required

| Item | Price | Notes |
|------|-------|-------|
| SwitchBot Hub Mini (Matter) | ~$30/room | IR blaster, HomeKit/Matter native |
| SwitchBot Meter Plus | ~$15/room | Temp/humidity, shows in Apple Home |
| Apple TV / HomePod Mini | ~$100 (one) | HomeKit hub for remote access |
| Mac Mini / Raspberry Pi 4+ | varies | Runs ClimateBrain 24/7 |

**Total per room: ~$45.** One-time cost, no subscriptions.

## Software Requirements

- Python 3.11+
- SQLite (included with Python)
- A SwitchBot account + API token
- OpenWeatherMap API key (free tier)

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/yourusername/climate-brain.git
cd climate-brain
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run

```bash
python -m climate_brain.main
```

The server starts at `http://localhost:8000`. Open the web UI to:
- Add rooms and register AC units
- Set up household members
- Start giving comfort feedback

### 4. Set up the control loop

Once you've registered at least one AC and one person, enable the scheduler:

```bash
# In .env
SCHEDULER_ENABLED=true
CONTROL_INTERVAL_MINUTES=5
```

The brain will start monitoring and adjusting every 5 minutes.

## How the Learning Works

### Thermal Model (per room)

Every 5 minutes, the system logs:
- Indoor temp & humidity
- Outdoor temp, humidity, feels-like
- Current AC state (mode, set temp, fan speed)
- Time of day, day of week

After a few days, it trains a model that predicts: *"Given current outdoor conditions and AC settings, what will the indoor temperature be in 15/30 minutes?"*

### Comfort Model (per person)

Each time someone taps a feedback button, the system logs the environmental conditions and the person's response. Over time, it learns each person's comfort function — which is conditional on temperature, humidity, time of day, and more.

### Multi-Person Optimization

When deciding what AC setting to use, the system:
1. Gets all present occupants (manual toggle or phone-based presence)
2. Predicts each person's comfort score for candidate AC settings
3. Picks the setting that minimizes worst-case discomfort (minimax fairness)

## Project Structure

```
climate-brain/
├── climate_brain/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration management
│   ├── scheduler.py         # Control loop scheduler
│   ├── api/
│   │   ├── routes_rooms.py  # Room & AC management endpoints
│   │   ├── routes_people.py # Person & feedback endpoints
│   │   ├── routes_status.py # Dashboard & status endpoints
│   │   └── routes_control.py# Manual control endpoints
│   ├── models/
│   │   ├── thermal.py       # Room thermal response model
│   │   ├── comfort.py       # Per-person comfort model
│   │   └── optimizer.py     # Multi-person AC optimizer
│   ├── services/
│   │   ├── switchbot.py     # SwitchBot API client
│   │   ├── weather.py       # OpenWeatherMap client
│   │   ├── ir_manager.py    # IR code learning & management
│   │   └── ac_controller.py # AC state tracking & control
│   └── db/
│       ├── database.py      # SQLite connection & setup
│       ├── models.py        # Data models / schemas
│       └── migrations.py    # Schema management
├── web_ui/
│   └── index.html           # Single-page feedback & dashboard UI
├── docs/
│   ├── SETUP_GUIDE.md       # Detailed setup instructions
│   ├── HARDWARE_GUIDE.md    # Hardware purchasing & setup
│   ├── API_REFERENCE.md     # REST API documentation
│   └── ARCHITECTURE.md      # System design deep-dive
├── tests/
│   ├── test_comfort.py
│   ├── test_thermal.py
│   ├── test_optimizer.py
│   └── test_simulator.py    # Test without hardware
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/rooms` | Add a room |
| POST | `/api/rooms/{id}/ac` | Register an AC unit |
| POST | `/api/rooms/{id}/ac/learn` | Start IR learning session |
| POST | `/api/people` | Add a household member |
| POST | `/api/feedback` | Submit comfort feedback |
| GET | `/api/status` | Current state of all rooms |
| POST | `/api/control/{room_id}` | Manual AC control |
| GET | `/api/history` | Sensor & comfort history |

Full API docs at `http://localhost:8000/docs` (auto-generated Swagger UI).

## Configuration

See `.env.example` for all options:

```env
# SwitchBot
SWITCHBOT_TOKEN=your_token_here
SWITCHBOT_SECRET=your_secret_here

# Weather
OPENWEATHER_API_KEY=your_key_here
OPENWEATHER_LAT=-6.2088    # Jakarta
OPENWEATHER_LON=106.8456

# Server
HOST=0.0.0.0
PORT=8000

# Scheduler
SCHEDULER_ENABLED=true
CONTROL_INTERVAL_MINUTES=5

# Learning
MIN_FEEDBACK_POINTS=20      # Min data before auto-adjusting
THERMAL_RETRAIN_HOURS=6     # How often to retrain thermal model
COMFORT_RETRAIN_HOURS=12    # How often to retrain comfort model
```

## Roadmap

- [x] Core architecture & API
- [x] SwitchBot integration
- [x] Weather integration
- [x] Per-person comfort learning
- [x] Multi-person optimization
- [x] Room thermal modeling
- [x] Web UI for feedback
- [ ] IR code database (pre-built codes for common brands)
- [ ] Phone-based presence detection
- [ ] Predictive pre-cooling/pre-heating
- [ ] Energy usage tracking & reporting
- [ ] Multiple optimization strategies (utilitarian, minimax, weighted)
- [ ] Broadlink RM4 support as alternative hardware
- [ ] Home Assistant integration (optional)

## License

MIT — use it however you want.

## Acknowledgments

Inspired by Ambi Climate, which proved that AI-powered comfort control works beautifully — and by its shutdown, which proved why local-first matters.
