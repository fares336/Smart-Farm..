# Smart Farm — Full-stack starter

A Flask + SQLite project scaffold for the Smart Farm prototype. Includes user registration/login, a 16×16 zone map, sensor-reading storage, CSV import, device-ingestion API, and separate water/fertilizer planning records.

## Run locally (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```
Open `http://127.0.0.1:5000`.

Demo login: `demo` / `SmartFarm123!`. Change/remove this demo account before public deployment.

## ESP32 API

`POST /api/device/readings`

Headers:
- `Content-Type: application/json`
- `X-Device-Token: <DEVICE_TOKEN>`

JSON:
```json
{"farm_id":1,"zone_code":"A1","moisture":30.0,"ec":1.1,"soil_temp":25.0}
```

Set the same strong `DEVICE_TOKEN` as an environment variable on the server and in the device firmware. For local Wi-Fi testing, use the computer's LAN IPv4 address, not `127.0.0.1`. The computer and ESP32 must be on the same network. Do not expose the development server directly to the public internet.

## GitHub and hosting

GitHub stores source code; it does not run this Flask backend as GitHub Pages. For a public running backend, deploy as a Render **Web Service** (or another Python host), not a GitHub Pages static site.

Render settings:
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Environment variables: `SECRET_KEY`, `DEVICE_TOKEN`

Important: SQLite on an ephemeral host may not persist across restarts/redeploys. For a real multi-user deployment, use managed PostgreSQL or a persistent disk and backups.

## Scope and limitations

This is a runnable integration foundation, not a scientifically validated production agronomy system. It does **not** yet include verified 200-crop global dataset, live weather forecast, Sentinel-2 processing, plant-disease AI model, market prices, or validated irrigation/fertilizer dose calculations. Those require separate datasets/services, calibration, testing, and in some cases API credentials. The pump endpoints only save review/planning records and never actuate hardware.

Soil EC is not a direct measurement of sodium or individual nutrients. Use an appropriate lab method for SAR/ESP and nutrient analysis. Satellite indices are vegetation proxies, not direct soil nutrient tests.
