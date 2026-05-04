# L3 – Állapotgép és Engine – GPS & Köridőmérés

**Modul:** M01
**Szint:** L3 – Állapotgép és Engine
**Verzió:** v1.2.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-05-04
**Státusz:** ✅ Implementálva

---

## 1. Fájl-szintű leképzés

```
firmware/
  gps.py      → GPSSensor osztály (UART olvasás, NMEA parse, Kalman)
  imu.py      → IMUSensor osztály (BMI270 I2C olvasás)
  kalman.py   → KalmanFilter osztály (1D, újrahasználható)
  lap.py      → LapDetector osztály (vonalmetszés, köridő)
  config.py   → FINISH_LINE, SECTORS, WIFI_SSID, MIN_LAP_TIME, stb.
  main.py     → async loop, task scheduler
```

**Referencia: Kormoran projekt** (`lib_sensors.py`, `lib_filters.py`, `main.py`)
- GPS UART: `UART2, tx=Pin(17), rx=Pin(18), baudrate=115200, rxbuf=1024, timeout=10`
- KalmanFilter: `KalmanFilter(Q=0.01, R=0.5)` — MotoMeter-ben Q=0.1 ajánlott
- LCD: `M5.Lcd` — `drawString`, `fillRect`, `setTextSize`, `setTextColor`
- SD kártya: `machine.SDCard(slot=3, sck=36, mosi=37, miso=35, cs=4)` → `/sd` mountpont
- Config: `/flash/config.json` flash-ről töltendő (NEM SD-ről)
- Screen pattern: `Screen` alaposztály, `on_enter()`, `draw()`, `handle_touch(x, y)`

---

## 2. GPSSensor állapotgép

```
States:
  INIT        → UART nyitva, GPS parancs küldve, fix várakozás
  NO_FIX      → UART aktív, érvényes fix nincs
  FIX_OK      → Pozíció érvényes, mérés lehetséges

Átmenetek:
  INIT → NO_FIX:   UART sikeresen megnyílt
  NO_FIX → FIX_OK: RMC status='A' érkezett
  FIX_OK → NO_FIX: RMC status='V' vagy timeout > 5 s

Metódusok:
  GPSSensor.__init__(uart_id=2, tx=17, rx=18, baud=115200)
  GPSSensor.begin()          → UART init + 10Hz konfig
  GPSSensor.update()         → NMEA buffer olvasás, parse
  GPSSensor.get_position()   → (lat, lon, speed_kmh, timestamp_ms)
  GPSSensor.is_valid()       → bool
  GPSSensor.get_sats()       → int

Belső adatok:
  self.lat, self.lon         → szűrt pozíció (Kalman output)
  self.raw_lat, self.raw_lon → nyers GPS pozíció
  self.speed_kmh             → szűrt sebesség
  self.valid                 → bool
  self.sats                  → műholdak száma
  self.last_fix_ms           → utolsó érvényes fix timestamp
```

---

## 3. LeanSensor állapotgép (imu.py)

```
Két backend (config.IMU_BACKEND):
  'bmi270'  → beépített CoreS3 BMI270 (M5Unified API)
  'mpu6886' → külső MPU6886 I2C (Grove Port A)

States:
  (init)   → begin() hívás előtt, _ready = False
  READY    → begin() sikeres, update() hívható
  (error)  → begin() sikertelen, _ready = False, update() no-op

Metódusok:
  LeanSensor.begin()          → backend init + alap kalibráció (10 minta)
  LeanSensor.calibrate()      → 20 mintás újrakalibrálás (accel ref + gyro bias)
  LeanSensor.update()         → complementary filter léptetése (25 Hz-en hívandó)
  LeanSensor.reset_peaks()    → peak hold nullázása

Publikus property-k:
  .angle       → aktuális dőlésszög fokban (+ = bal, - = jobb)
  .peak_right  → session max jobb dőlés (fok, pozitív)
  .peak_left   → session max bal dőlés (fok, pozitív)
  .lateral_g   → oldalirányú G-erő: tan(radians(angle))
  .lon_g       → hosszirányú G-erő (+ = gyorsítás, - = fékezés)
  .yaw_rate    → kanyar szögsebesség (gz, rad/s)
  .is_ready    → bool

Complementary filter:
  α = 0.98
  angle = α*(angle + sign*gyro*dt) + (1-α)*accel_angle
```

---

## 4. KalmanFilter engine

```
Forrás: Kormoran lib_filters.py (tesztelt, működő implementáció)

class KalmanFilter:
  __init__(Q=0.1, R=2.0)   ← MotoMeter paraméterek (Q nagyobb mint hajónál)
  update(measurement) → filtered_value
  reset()

Két példány M01-ben:
  kalman_lat = KalmanFilter(Q=0.1, R=2.0)  ← szélességi fok
  kalman_lon = KalmanFilter(Q=0.1, R=2.0)  ← hosszúsági fok

Sebesség szűréshez (opcionális):
  kalman_speed = KalmanFilter(Q=0.05, R=1.0)
```

---

## 5. LapDetector állapotgép (lap.py)

```
Állapotok (STATE_* konstansok):
  STATE_NO_LINE   → rajtvonal nincs definiálva
  STATE_WAITING   → rajtvonal OK, első áthaladásra vár (outlap)
  STATE_IN_LAP    → kör folyamatban (első áthaladás megtörtént)

Átmenetek:
  NO_LINE → WAITING: set_finish_line() hívva
  WAITING → IN_LAP:  első rajtvonal-átlépés, DE csak ha
                     ticks_diff(t_cross, _line_set_ms) >= MIN_OUTLAP_MS (5s)
  IN_LAP  → IN_LAP:  minden újabb átlépés = kör rögzítve (ha MIN_LAP_MS < elapsed < MAX_LAP_MS)

Konstansok:
  MIN_LAP_MS    = 10 000 ms   (10 s)
  MAX_LAP_MS    = 600 000 ms  (10 min)
  MIN_OUTLAP_MS = 5 000 ms    (5 s — outlap guard)

Metódusok:
  LapDetector.set_finish_line(lat1, lon1, lat2, lon2)  → rögzíti _line_set_ms-t is
  LapDetector.set_start_line(lat1, lon1, lat2, lon2)   → csak stage módban
  LapDetector.update(lat, lon, ts_ms, speed_kmh) → LapResult | None
  LapDetector.get_best_lap_ms()  → int | None
  LapDetector.get_lap_count()    → int
  LapDetector.get_state()        → str
  LapDetector.reset()

LapResult (osztály, __slots__):
  lap_time_ms    → int
  is_best        → bool
  delta_ms       → int (lap_time - best_lap, negatív = javulás)
  lap_number     → int
  cross_ts_ms    → int (interpolált átlépési időbélyeg)

Belső adatok:
  _fl_lat1/lon1/lat2/lon2  → célvonal koordinátái
  _sl_lat1/lon1/lat2/lon2  → startvonal koordinátái (stage)
  _prev_lat, _prev_lon     → előző GPS pont (Kalman szűrt)
  _prev_ts_ms              → előző GPS pont időbélyege
  _last_cross_ms           → utolsó érvényes átlépés időbélyege
  _line_set_ms             → vonal beállításának időbélyege (outlap guard)
  _best_lap_ms             → legjobb köridő
  _lap_count               → kör számláló
  current_trace            → aktuális kör GPS+IMU trace (list of dict)
```

---

## 6. Async task struktúra (main.py)

```python
# Referencia: Kormoran main.py async architektúra

async def gps_task():
    """10 Hz-es GPS olvasás és Kalman frissítés"""
    while True:
        gps.update()
        if gps.is_valid():
            lat, lon, speed, ts = gps.get_position()
            result = lap_detector.update(lat, lon, ts)
            if result:
                on_lap_complete(result)
        await asyncio.sleep_ms(100)  # 10 Hz

async def imu_task():
    """50 Hz-es IMU olvasás (lean angle, future: EKF)"""
    while True:
        imu.update()
        await asyncio.sleep_ms(20)  # 50 Hz

async def display_task():
    """Kijelző frissítés (5 Hz elegendő)"""
    while True:
        display.render(gps, lap_detector)
        await asyncio.sleep_ms(200)  # 5 Hz

async def uplink_task():
    """WiFi uplink, queue feldolgozás"""
    while True:
        uplink.process_queue()
        await asyncio.sleep_ms(1000)  # 1 Hz

# Main
async def main():
    await asyncio.gather(
        gps_task(),
        imu_task(),
        display_task(),
        uplink_task()
    )

asyncio.run(main())
```

---

## 7. config.py struktúra

```python
# Rajtvonal (helyszíni GPS felvétel vagy kézi)
FINISH_LINE = {
    'lat1': 47.123456, 'lon1': 19.123456,
    'lat2': 47.123789, 'lon2': 19.123789
}

# Szektorok (s-koordináta alapján, 0.0–1.0)
# Részletes definíció: M02 modul
SECTORS = [0.0, 0.15, 0.32, 0.51, 0.68, 0.84, 1.0]

# WiFi
WIFI_SSID = "telefon_hotspot"
WIFI_PASS = "jelszo"

# Köridő érvényességi határok
MIN_LAP_TIME_MS = 30000   # 30 s
MAX_LAP_TIME_MS = 600000  # 10 min

# GPS UART
GPS_UART_ID = 2
GPS_TX_PIN = 17
GPS_RX_PIN = 18
GPS_BAUD = 115200

# Kalman paraméterek
KALMAN_Q = 0.1
KALMAN_R = 2.0
```
