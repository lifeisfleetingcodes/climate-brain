# Hardware Guide

## Complete Bill of Materials

### Server (pick ONE — runs ClimateBrain 24/7)

| Option | Price | Power | Notes |
|--------|-------|-------|-------|
| Raspberry Pi 4 (2GB) | ~$45 / Rp 700k | 5W | **Recommended.** Silent, cheap, plenty powerful |
| Raspberry Pi 4 (4GB) | ~$55 / Rp 850k | 5W | Extra headroom for other services |
| Raspberry Pi 5 (4GB) | ~$60 / Rp 950k | 5-10W | Faster, but overkill for this |
| Raspberry Pi Zero 2 W | ~$15 / Rp 250k | 1W | Absolute minimum. Works, just slower |
| Orange Pi Zero 3 (1GB) | ~$20 / Rp 300k | 3W | Budget alternative |
| Old laptop / PC | free | 30-60W | Works but noisy and wasteful |
| Mac Mini | ~$500+ | 10W | Only if you already own one |

**Server requirements:**
- WiFi or Ethernet
- Python 3.11+
- 512MB+ RAM (1GB recommended)
- 1GB+ free storage
- Runs 24/7

**Recommended server kit: Raspberry Pi 4 (2GB)**

| Item | Price |
|------|-------|
| Raspberry Pi 4 Model B 2GB | ~$45 / Rp 700k |
| 32GB microSD card (SanDisk Extreme, A2) | ~$8 / Rp 125k |
| Official USB-C power supply (5V 3A) | ~$8 / Rp 125k |
| Aluminum heatsink case (passive cooling) | ~$8 / Rp 125k |
| Ethernet cable (optional, more reliable) | ~$3 / Rp 50k |
| **Server total** | **~$60-70 / Rp 950k-1.1M** |

---

### Per Room (one set for each room with an AC)

| Item | Price | Purpose |
|------|-------|---------|
| SwitchBot Hub Mini (Matter-enabled) | ~$30 / Rp 470k | IR blaster — sends commands to AC |
| SwitchBot Meter Plus | ~$15 / Rp 235k | Temperature & humidity sensor |
| **Per room total** | **~$45 / Rp 700k** | |

---

### HomeKit Remote Access (ONE for whole house, optional)

| Item | Price | Notes |
|------|-------|-------|
| HomePod Mini | ~$100 / Rp 1.5M | Speaker + Siri + Home Hub |
| Apple TV 4K | ~$130 / Rp 2M | Streaming + Home Hub |
| iPad (always home) | free if you have one | Set as Home Hub in Settings |

Only needed to control AC from outside your home via Apple Home. Skip if you only need control on your home WiFi.

---

### Cost Summary

| Setup | Cost |
|-------|------|
| **1 room (minimum)** | ~$105 / Rp 1.65M |
| **2 rooms** | ~$150 / Rp 2.35M |
| **3 rooms** | ~$195 / Rp 3.05M |
| **+ HomeKit remote (optional)** | +$100 / +Rp 1.5M |

---

## Where to Buy (Indonesia)

**Tokopedia / Shopee:**
- "SwitchBot Hub Mini" — get the **Matter-enabled** version (white, rectangular)
- "SwitchBot Meter Plus" or "SwitchBot Thermometer Hygrometer"
- "Raspberry Pi 4 Model B 2GB"
- "MicroSD 32GB A2 SanDisk Extreme"
- "Raspberry Pi 4 Case Heatsink Aluminum"

**Official:** https://www.switch-bot.com/ (ships internationally)

**Alternative IR blasters (if SwitchBot unavailable):**

| Device | Price | HomeKit | Notes |
|--------|-------|---------|-------|
| Broadlink RM4 Mini | ~$25 / Rp 390k | Via Homebridge | No native HomeKit, needs bridge |
| Tuya IR Blaster | ~$15 / Rp 235k | No | Cheapest. Tuya app only |

---

## Network Layout

```
Internet ──→ WiFi Router ──→ SwitchBot Hub Mini (2.4GHz WiFi)
                         ──→ SwitchBot Meter (BLE → Hub Mini)
                         ──→ Raspberry Pi (WiFi or Ethernet)
                         ──→ Your phone (web UI + Apple Home)
```

**Important:**
- SwitchBot Hub Mini needs **2.4GHz WiFi** (not 5GHz)
- All devices on the **same local network**
- Internet needed for: SwitchBot API, OpenWeatherMap, HomeKit remote
- Brain runs locally — internet outage pauses it but no data is lost

---

## Physical Placement

### SwitchBot Hub Mini

```
    ┌─────────────────────────────┐
    │        AC UNIT              │  ← high on wall
    │   [IR receiver]             │
    └─────────────────────────────┘
                ↑
            IR signal (line of sight, <5m)
                ↑
          ┌───────────┐
          │ Hub Mini  │  ← shelf or wall-mount, facing AC
          └───────────┘
              │
           USB-C power
```

- **Clear line of sight** to AC's IR receiver (usually right side of front panel)
- Within **5 meters**
- No furniture, curtains, obstacles between Hub and AC
- Powered by USB-C (cable included)

### SwitchBot Meter Plus

- Place at **human height** (1-1.5m above floor)
- **Away from** AC airflow, direct sunlight, heat sources (TV, lamp), walls (<30cm)
- Battery powered (CR2477, ~1 year life) — no cable needed

### Example Room Layout

```
    ┌──────────────────────────────────────┐
    │               CEILING                │
    │  ┌──────────────────┐                │
    │  │    AC UNIT       │                │
    │  └──────────────────┘                │
    │         ↑ IR                         │
    │    [Hub Mini]           [Meter Plus] │
    │    on shelf             on bookshelf │
    │                                      │
    │        ┌──────┐                      │
    │        │ BED  │                      │
    │        └──────┘                      │
    │              FLOOR                   │
    └──────────────────────────────────────┘
```

---

## Raspberry Pi Setup

### 1. Flash the OS

1. Download **Raspberry Pi Imager**: https://www.raspberrypi.com/software/
2. Insert microSD into your MacBook (USB-C adapter if needed)
3. In Imager:
   - OS: **Raspberry Pi OS Lite (64-bit)**
   - Click gear ⚙ and set:
     - Hostname: `climatebrain`
     - Enable SSH: yes
     - Username: `pi`, Password: (choose one)
     - WiFi: your network name + password
     - Locale: Asia/Jakarta
4. Write and eject

### 2. Boot and Connect

```bash
# Insert SD into Pi, plug in power, wait 2-3 minutes
# Then from your Mac:
ssh pi@climatebrain.local

# Update system
sudo apt update && sudo apt upgrade -y
```

### 3. Install ClimateBrain

```bash
sudo apt install -y python3 python3-pip python3-venv git

git clone https://github.com/yourusername/climate-brain.git
cd climate-brain

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # fill in your API keys
```

### 4. Run as System Service (auto-starts on boot)

```bash
sudo nano /etc/systemd/system/climatebrain.service
```

Paste:
```ini
[Unit]
Description=ClimateBrain Comfort Controller
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/climate-brain
Environment=PATH=/home/pi/climate-brain/venv/bin:/usr/bin
ExecStart=/home/pi/climate-brain/venv/bin/python -m climate_brain.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable climatebrain
sudo systemctl start climatebrain
sudo systemctl status climatebrain   # should show "active (running)"
```

Web UI now at: **http://climatebrain.local:8000**

### 5. View Logs

```bash
sudo journalctl -u climatebrain -f
```

### Docker Alternative

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker pi
logout   # SSH back in

cd climate-brain
cp .env.example .env && nano .env
docker compose up -d
docker compose logs -f
```

---

## SwitchBot Setup

### 1. Hub Mini

1. Download **SwitchBot** app → create account
2. Tap `+` → Hub Mini → follow pairing
3. **Add your AC:**
   - Hub Mini → Add Remote → Air Conditioner → choose brand
   - Test on/off, temperature, mode changes
   - Note **Device ID** (Settings → Device Info)
4. **Enable Matter for HomeKit:**
   - Hub Mini settings → Matter Setup → scan QR in Apple Home

### 2. Meter Plus

1. SwitchBot app → `+` → Meter Plus → pair
2. Enable **Cloud Service** (so API can read it)
3. Note **Device ID**

### 3. Get API Token

1. SwitchBot app → Profile → Preferences
2. Tap **Developer Options** (tap app version 10x to unlock)
3. Copy **Token** and **Secret** → paste into `.env`

### 4. Verify

Open `http://climatebrain.local:8000/api/switchbot/devices` — you should see your devices listed.

---

## OpenWeatherMap Setup

1. Sign up free at https://openweathermap.org/api
2. Copy your API key → paste into `.env`
3. Set coordinates:
   - Jakarta: `LAT=-6.2088` `LON=106.8456`
   - Solo: `LAT=-7.5755` `LON=110.8243`

Free tier: 1,000 calls/day. ClimateBrain uses ~288/day.

---

## Troubleshooting

**Hub Mini won't connect to WiFi**
→ Must be 2.4GHz. Split your router's 2.4/5GHz bands or temporarily disable 5GHz.

**AC doesn't respond to IR**
→ Check line of sight. Move Hub closer. Re-learn remote in SwitchBot app.

**Meter shows wrong temperature**
→ Wait 10 min to acclimate. Check it's not near heat sources or sunlight.

**ClimateBrain not reading sensors**
→ Check API token. Enable Cloud Service on Meter. Test `/api/switchbot/devices`.

**Pi not accessible via SSH**
→ Try `ping climatebrain.local`. If no response, find its IP in your router admin page.

**Service won't start**
→ Check `sudo journalctl -u climatebrain -e` for errors. Usually a missing `.env` value.
