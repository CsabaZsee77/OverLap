# main.py - MotoMeter főprogram (async)
# MotoMeter v0.1 - M5Stack CoreS3
#
# Modulok:
#   M01 — GPS parse + köridőmérés (gps.py, lap.py, kalman.py)
#   M02 — Szektordetektor + prediktált köridő (sector.py, delta.py)
#   M03 — Kijelző kezelés (display.py)
#   M04 — WiFi uplink + offline log (uplink.py, logger.py)
#
# Architektúra: 4 async task
#   gps_task     — 10 Hz GPS olvasás, lap + sector detektálás
#   display_task — 5 Hz kijelző frissítés
#   wifi_task    — 30 s-os reconnect
#   uplink_task  — 60 s-os offline flush (ha WiFi van)

import M5
from M5 import *
import uasyncio as asyncio
import time
import os
import network
import math

print("=" * 40)
print("MOTOMETER v0.1 - Starting...")
print("=" * 40)

# ============================================================
# M5STACK INIT
# ============================================================
M5.begin()
Widgets.fillScreen(0x000000)
print("M5Stack OK")

# ============================================================
# SD KÁRTYA
# ============================================================
sd_available = False
try:
    import machine
    sd = machine.SDCard(slot=3, sck=36, mosi=37, miso=35, cs=4)
    os.mount(sd, '/sd')
    sd_available = True
    print("SD: mounted at /sd")
    try:
        os.mkdir('/sd/overlap_logs')
    except OSError:
        pass
except Exception as e:
    print("SD: NOT available —", e)

# ============================================================
# KONFIGURÁCIÓ
# ============================================================
from overlap import config

# Device ID generálás MAC-ból
if not config.DEVICE_ID:
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        mac = wlan.config('mac')
        config.DEVICE_ID = 'mm_' + ''.join('{:02x}'.format(b) for b in mac)
    except Exception:
        config.DEVICE_ID = 'mm_unknown'
print("Device ID:", config.DEVICE_ID)

# ============================================================
# MODULOK
# ============================================================
print("Loading modules...")
from overlap.gps          import GPSSensor
from overlap.lap          import LapDetector, MODE_CIRCUIT, MODE_STAGE
from overlap.sector       import SectorDetector
from overlap.delta        import LapPredictor
from overlap.display      import MotoDisplay, MODE_IMU, MODE_CALIB, MODE_STATS
from overlap.track_loader import load_track, save_track, make_track_from_gps
from overlap.logger       import SessionLogger
from overlap.uplink       import Uplink
from overlap.telegram     import TelegramNotifier
from overlap.imu          import LeanSensor
print("Modules OK")

# ============================================================
# OBJEKTUMOK
# ============================================================
gps       = GPSSensor()
lap_det   = LapDetector()
sec_det   = SectorDetector()
predictor = LapPredictor()
disp      = MotoDisplay(M5.Lcd)
logger    = SessionLogger(sd_available=sd_available)
uplink    = Uplink(backend_url=config.BACKEND_URL)
telegram  = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
lean      = LeanSensor()

# Session állapot
max_speed_kmh     = 0.0   # session-szintű maximum (soha nem nullázódik)
lap_max_speed_kmh = 0.0   # aktuális kör maximuma (körönként nullázódik)
prev_lap_max_kmh  = 0.0   # előző befejezett kör max sebessége (kijelzőhöz)
prev_lap_ms       = None
wifi_connected    = False
battery_pct       = None
track_cfg         = None
session_started   = False
lap_start_ts      = None
lap_history       = []   # befejezett körök listája (kijelző görgetéshez)
telegram_queue    = []   # el nem küldött körök puffere
telegram_sent     = set()  # már elküldött kör számai (deduplikáció)

# Per-kör IMU csúcsértékek (körönként nullázódnak)
lap_peak_lean_right  = 0.0   # max jobb dőlés fokban (pozitív)
lap_peak_lean_left   = 0.0   # max bal dőlés fokban (pozitív)
lap_peak_kamm_g      = 0.0   # max kombinált G (Kamm kör)
lap_peak_kamm_angle  = 0.0   # irány fokban a max Kamm pillanatában

# Session-szintű IMU csúcsok (session végéig nem nullázódnak)
session_peak_lean_right = 0.0
session_peak_lean_left  = 0.0
session_peak_kamm_g     = 0.0
session_peak_kamm_angle = 0.0

# ============================================================
# PÁLYA KONFIGURÁCIÓ
# ============================================================
track_cfg = load_track()

if track_cfg and track_cfg.is_ready:
    # Üzemmód
    lap_det.set_mode(MODE_STAGE if track_cfg.is_stage else MODE_CIRCUIT)

    # Célvonal
    fl = track_cfg.finish_line
    lap_det.set_finish_line(fl.lat1, fl.lon1, fl.lat2, fl.lon2)

    # Startvonal (stage)
    if track_cfg.is_stage and track_cfg.has_start_line:
        sl = track_cfg.start_line
        lap_det.set_start_line(sl.lat1, sl.lon1, sl.lat2, sl.lon2)

    # Szektordetektor
    sec_det.set_sectors(track_cfg.sectors)
    predictor.set_sector_count(len(track_cfg.sectors))

    print("Pálya betöltve: {} ({} szektor, {})".format(
        track_cfg.name, track_cfg.sector_count, track_cfg.track_type))
else:
    print("Rajtvonal nincs — SETUP módban indul")

# ============================================================
# BOOT KÉPERNYŐ
# ============================================================
disp.begin()
disp._mode = 1              # Mindig SETUP-pal indul
disp._force_redraw = True

# ============================================================
# IMU INIT
# ============================================================
lean.begin()

# ============================================================
# GPS INIT
# ============================================================
gps.begin()

# ============================================================
# WIFI
# ============================================================

def connect_wifi():
    global wifi_connected
    if not config.WIFI_SSID:
        print("WiFi: SSID nincs beállítva — offline mód")
        return
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            print("WiFi: csatlakozás '{}'...".format(config.WIFI_SSID))
            wlan.connect(config.WIFI_SSID, config.WIFI_PASS)
        wifi_connected = wlan.isconnected()
    except Exception as e:
        print("WiFi hiba:", e)
        wifi_connected = False

connect_wifi()

# ============================================================
# SESSION INDÍTÁS
# ============================================================

def _start_session():
    """Logger session megnyitása."""
    global session_started
    if session_started:
        return
    track_id = getattr(track_cfg, '_backend_id', None) if track_cfg else None
    logger.start_session(
        device_id  = config.DEVICE_ID,
        track_id   = track_id,
        rider_name = config.RIDER_NAME,
    )
    session_started = True
    print("Session indítva (device={})".format(config.DEVICE_ID))

# ============================================================
# SET FINISH LINE — GPS alapú helyszíni felvétel
# ============================================================

def _beep(freq=1000, duration=200):
    try:
        M5.Speaker.setVolume(80)
        M5.Speaker.tone(freq, duration)
    except Exception:
        pass

def set_finish_line_from_gps():
    global track_cfg, lap_start_ts
    global lap_peak_lean_right, lap_peak_lean_left, lap_peak_kamm_g, lap_peak_kamm_angle
    global lap_max_speed_kmh, max_speed_kmh
    if not gps.is_valid():
        print("SET FINISH LINE: nincs GPS FIX!")
        _beep(400, 500)
        disp.flash_screen(0xFF0000, 1000)  # piros = nincs GPS fix
        return False

    tc = make_track_from_gps(
        name       = track_cfg.name if track_cfg else config.TRACK_NAME,
        center_lat = gps.lat,
        center_lon = gps.lon,
        course_deg = gps.course,
        width_m    = 30.0
    )
    if track_cfg:
        tc.sectors = track_cfg.sectors

    lap_det.set_finish_line(
        tc.finish_line.lat1, tc.finish_line.lon1,
        tc.finish_line.lat2, tc.finish_line.lon2
    )
    sec_det.set_sectors(tc.sectors)
    predictor.set_sector_count(len(tc.sectors))
    track_cfg = tc

    # Per-kör és session csúcsok nullázása új session-nél
    global session_peak_lean_right, session_peak_lean_left
    global session_peak_kamm_g, session_peak_kamm_angle
    lap_max_speed_kmh      = 0.0
    lap_peak_lean_right    = 0.0
    lap_peak_lean_left     = 0.0
    lap_peak_kamm_g        = 0.0
    lap_peak_kamm_angle    = 0.0
    session_peak_lean_right = 0.0
    session_peak_lean_left  = 0.0
    session_peak_kamm_g     = 0.0
    session_peak_kamm_angle = 0.0

    # Stopper azonnal indul a beállítás pillanatától
    if lap_start_ts is None:
        ts_now = time.ticks_ms()
        lap_start_ts = ts_now
        sec_det.start_lap(ts_now)
        _start_session()

    print("SET FINISH LINE GPS: OK (30m, csak memoria)")

    # Vizualis visszajelzes: teljes kepernyo 1mp-ig zold
    _beep(1200, 150)
    disp.flash_screen(0x00FF00, 2000)  # 2mp zold villanas, sisakbol is lathato
    return True


def set_finish_line_from_file():
    global track_cfg
    tc = load_track()
    if tc is None or not tc.is_ready:
        print("SET FINISH LINE FILE: nincs track.json vagy hiányos!")
        _beep(400, 500)
        disp.flash_screen(0xFF0000, 1000)  # piros = nincs / hibas track.json
        return False

    lap_det.set_mode(MODE_STAGE if tc.is_stage else MODE_CIRCUIT)
    fl = tc.finish_line
    lap_det.set_finish_line(fl.lat1, fl.lon1, fl.lat2, fl.lon2)
    if tc.is_stage and tc.has_start_line:
        sl = tc.start_line
        lap_det.set_start_line(sl.lat1, sl.lon1, sl.lat2, sl.lon2)
    sec_det.set_sectors(tc.sectors)
    predictor.set_sector_count(len(tc.sectors))
    track_cfg = tc
    print("SET FINISH LINE FILE: OK —", tc.name)
    _beep(1200, 150)
    disp.flash_screen(0x00FF00, 2000)  # zold = siker
    return True

# ============================================================
# ASYNC TASKOK
# ============================================================

async def imu_task():
    """IMU dőlésszög mérés + per-kör csúcskövetés — 25 Hz"""
    global lap_peak_lean_right, lap_peak_lean_left, lap_peak_kamm_g, lap_peak_kamm_angle
    while True:
        lean.update()
        if lean.is_ready:
            angle = lean.angle
            if angle < 0 and -angle > lap_peak_lean_right:
                lap_peak_lean_right = -angle
            elif angle > 0 and angle > lap_peak_lean_left:
                lap_peak_lean_left = angle
            lat_g = lean.lateral_g
            lon_g = lean.lon_g
            total_g = math.sqrt(lat_g * lat_g + lon_g * lon_g)
            if total_g > lap_peak_kamm_g:
                lap_peak_kamm_g    = total_g
                lap_peak_kamm_angle = math.degrees(math.atan2(lat_g, lon_g)) % 360
        await asyncio.sleep_ms(40)    # 25 Hz


async def gps_task():
    """GPS olvasás + köridő + szektor detektálás — 10 Hz"""
    global max_speed_kmh, lap_max_speed_kmh, prev_lap_ms, lap_start_ts

    while True:
        gps.update()

        if gps.is_valid():
            lat, lon, speed, ts = gps.get_position()

            if speed > max_speed_kmh:
                max_speed_kmh = speed
            if speed > lap_max_speed_kmh:
                lap_max_speed_kmh = speed

            # ── Szektor update ───────────────────────────────
            sec_result = sec_det.update(lat, lon, ts)
            if sec_result is not None:
                _on_sector_complete(sec_result)

            # ── Köridő update ────────────────────────────────
            lap_result = lap_det.update(lat, lon, ts, speed)

            # ── IMU adatok hozzáfűzése az utolsó trace ponthoz ──
            # A lap_det.update() tuple-t append-el; itt dict-re cseréljük
            # hogy a lean/Kamm adatok is bekerüljenek a visszajátszható logba.
            if lap_det.current_trace and lean.is_ready:
                lp = lap_det.current_trace[-1]
                lat_g = lean.lateral_g
                lon_g = lean.lon_g
                lap_det.current_trace[-1] = {
                    'lat':        lp[0],
                    'lon':        lp[1],
                    'speed_kmh':  round(lp[2], 1),
                    'ts_ms':      lp[3],
                    'lean_deg':   round(lean.angle, 1),
                    'lat_g':      round(lat_g, 3),
                    'lon_g':      round(lon_g, 3),
                    'kamm_angle': round(
                        math.degrees(math.atan2(lat_g, lon_g)) % 360, 1),
                }

            if lap_result is not None:
                prev_lap_ms = lap_result.lap_time_ms
                _on_lap_complete(lap_result, ts)

            # ── Kör indulás detektálása ──────────────────────
            # Ha STATE_WAITING → STATE_IN_LAP váltott, start_lap() kell
            from overlap.lap import STATE_IN_LAP
            if lap_det.get_state() == STATE_IN_LAP and lap_start_ts is None:
                lap_start_ts = ts
                sec_det.start_lap(ts)
                _start_session()
                print("Kör indult")

        await asyncio.sleep_ms(100)    # 10 Hz


def _on_sector_complete(result):
    """Szektor zárásakor."""
    sign = '+' if result.delta_ms > 0 else ''
    print(">>> {} {:.3f}s {} {}".format(
        result.name,
        result.time_ms / 1000.0,
        "★ BEST" if result.is_best else "({}{}ms)".format(sign, result.delta_ms),
        "←" if result.is_best else ""
    ))


def _on_lap_complete(result, ts):
    """Köridő rögzítésekor — log + uplink + telegram sor."""
    global lap_start_ts, lap_max_speed_kmh, prev_lap_max_kmh, lap_history
    global lap_peak_lean_right, lap_peak_lean_left, lap_peak_kamm_g, lap_peak_kamm_angle
    global session_peak_lean_right, session_peak_lean_left
    global session_peak_kamm_g, session_peak_kamm_angle

    print("LAP #{}: {:.3f}s  {}  delta={:+.3f}s".format(
        result.lap_number,
        result.lap_time_ms / 1000.0,
        "★ BEST" if result.is_best else "",
        result.delta_ms / 1000.0
    ))
    if result.is_best:
        _beep(1400, 100); time.sleep_ms(120); _beep(1800, 200)
    else:
        _beep(1000, 300)

    # Szektoridők összegyűjtése
    best_times = sec_det.get_best_times()
    sector_times_ms = [
        best_times.get(ln.name, 0) or 0
        for ln in (track_cfg.sectors if track_cfg else [])
    ]

    # Per-kör csúcsok mentése, majd nullázás
    this_lap_max      = lap_max_speed_kmh
    this_lean_right   = lap_peak_lean_right
    this_lean_left    = lap_peak_lean_left
    this_kamm_g       = lap_peak_kamm_g
    this_kamm_angle   = lap_peak_kamm_angle

    prev_lap_max_kmh  = this_lap_max
    lap_max_speed_kmh  = 0.0
    lap_peak_lean_right = 0.0
    lap_peak_lean_left  = 0.0
    lap_peak_kamm_g     = 0.0
    lap_peak_kamm_angle = 0.0

    # Session-szintű csúcsok frissítése (sosem nullázódnak körön belül)
    if this_lean_right > session_peak_lean_right:
        session_peak_lean_right = this_lean_right
    if this_lean_left > session_peak_lean_left:
        session_peak_lean_left = this_lean_left
    if this_kamm_g > session_peak_kamm_g:
        session_peak_kamm_g     = this_kamm_g
        session_peak_kamm_angle = this_kamm_angle

    # STATS képernyő frissítése, ha éppen azt nézi
    disp._force_redraw = True

    # Kör hozzáadása a kijelző listához (max 10 kör)
    lap_history.append({
        'lap_number':    result.lap_number,
        'lap_time_ms':   result.lap_time_ms,
        'max_speed_kmh': this_lap_max,
        'is_best':       result.is_best,
    })
    if len(lap_history) > 10:
        lap_history.pop(0)

    # Mentés loggerbe
    logger.add_lap(
        lap_number      = result.lap_number,
        lap_time_ms     = result.lap_time_ms,
        lap_start_ts    = lap_start_ts,
        lap_end_ts      = result.cross_ts_ms,
        sector_times_ms = sector_times_ms,
        gps_trace       = list(lap_det.current_trace),
        max_speed_kmh   = this_lap_max,
        max_lean_right  = this_lean_right,
        max_lean_left   = this_lean_left,
        peak_kamm_g     = this_kamm_g,
        peak_kamm_angle = this_kamm_angle,
    )

    # Telegram pufferbe tesszük (mindig)
    telegram_queue.append({
        'lap_number':      result.lap_number,
        'lap_time_ms':     result.lap_time_ms,
        'delta_ms':        result.delta_ms,
        'is_best':         result.is_best,
        'max_speed_kmh':   this_lap_max,
        'sector_times_ms': sector_times_ms,
        'track_name':      track_cfg.name if track_cfg else '',
        'max_lean_right':  this_lean_right,
        'max_lean_left':   this_lean_left,
        'peak_kamm_g':     this_kamm_g,
        'peak_kamm_angle': this_kamm_angle,
    })

    # Ha van WiFi, azonnal kiküldjük a teljes sort
    if wifi_connected:
        if config.BACKEND_URL:
            _try_immediate_uplink(result)
        _flush_telegram_queue()

    # Reset lap start
    lap_start_ts = result.cross_ts_ms
    sec_det.start_lap(result.cross_ts_ms)


def _flush_telegram_queue():
    """Elküldi az összes pufferelt Telegram üzenetet, kihagyja a már küldötteket."""
    while telegram_queue:
        item = telegram_queue[0]
        key = item['lap_number']
        if key in telegram_sent:
            telegram_queue.pop(0)
            continue
        ok = telegram.send_lap(**item)
        if ok:
            telegram_sent.add(key)
            telegram_queue.pop(0)
        else:
            print("Telegram: kuldesi hiba, kesobb probaljuk")
            break


def _send_session_to_telegram():
    """Aktuális session JSON fájl elküldése Telegram-ra dokumentumként."""
    if not telegram.is_enabled():
        print("Telegram: nincs beallitva, kuldés kihagyva")
        _beep(400, 300)
        return
    path = logger._session_path
    if not path:
        print("Telegram: nincs session fajl")
        _beep(400, 300)
        return
    laps = lap_det.get_lap_count()
    best = lap_det.get_best_lap_ms()
    best_str = '{:.3f}s'.format(best / 1000.0) if best else '---'
    caption = 'OverLAP session: {} kor, best {}'.format(laps, best_str)
    print("Telegram: session fajl kuldese ({})".format(path))
    ok = telegram.send_document(path, caption)
    if ok:
        _beep(1200, 150)
        time.sleep_ms(160)
        _beep(1600, 200)
    else:
        _beep(400, 500)


def _try_immediate_uplink(result):
    """
    Az aktuális session eddigi adatait feltölti.
    Ha nem sikerül, a logger.py-ban marad — uplink_task veszi fel.
    """
    try:
        if not logger._session_data:
            return
        ok = uplink.upload_session(logger._session_data)
        if ok:
            print("Uplink: kör #{} feltöltve".format(result.lap_number))
    except Exception as e:
        print("Uplink: immediate hiba →", e)


async def display_task():
    """Kijelző frissítés — 5 Hz, akkuszint olvasás 30s-onként"""
    global battery_pct
    batt_tick = 0

    while True:
        # Akkuszint 30s-onként
        if batt_tick <= 0:
            try:
                battery_pct = M5.Power.getBatteryLevel()
            except Exception:
                battery_pct = None
            batt_tick = 150   # 150 * 200ms = 30s

        batt_tick -= 1

        # Prediktált köridő számítás
        predicted_ms = None
        if lap_start_ts is not None and sec_det.has_sectors():
            ts_now = time.ticks_ms()
            predicted_ms, _ = predictor.predict(
                lap_start_ts     = lap_start_ts,
                ts_ms            = ts_now,
                sector_idx       = sec_det.current_sector_idx,
                best_sector_list = sec_det.get_best_times_list(),
                best_lap_ms      = lap_det.get_best_lap_ms(),
            )

        disp.update(
            gps                  = gps,
            lap_detector         = lap_det,
            max_speed_kmh        = max_speed_kmh,
            wifi_connected       = wifi_connected,
            predicted_ms         = predicted_ms,
            prev_lap_ms          = prev_lap_ms,
            battery_pct          = battery_pct,
            lap_start_ts         = lap_start_ts,
            prev_lap_max_kmh     = prev_lap_max_kmh,
            lap_history          = lap_history,
            lean                 = lean,
            session_lean_right   = session_peak_lean_right,
            session_lean_left    = session_peak_lean_left,
            session_kamm_g       = session_peak_kamm_g,
        )
        await asyncio.sleep_ms(200)    # 5 Hz


async def wifi_task():
    """WiFi újracsatlakozás — hotspot kiesés kezelése"""
    global wifi_connected
    while True:
        try:
            wlan = network.WLAN(network.STA_IF)
            wifi_connected = wlan.isconnected()

            if not wifi_connected and config.WIFI_SSID:
                print("WiFi: reconnect kísérlet...")
                connect_wifi()
                await asyncio.sleep_ms(5000)
                wifi_connected = wlan.isconnected()
                if wifi_connected:
                    print("WiFi: reconnect OK —", wlan.ifconfig()[0])
                    _flush_telegram_queue()   # pufferelt körök elküldése

        except Exception as e:
            print("WiFi task hiba:", e)

        await asyncio.sleep_ms(config.WIFI_RETRY_INTERVAL_S * 1000)


async def uplink_task():
    """
    Offline sor kiürítése — 30 s-onként, ha van WiFi.
    Telegram queue retry + session feltöltés.
    """
    while True:
        await asyncio.sleep_ms(30_000)   # 30 s

        if not wifi_connected:
            continue

        # Telegram puffer retry (blokkoló, de 30s-onként elfogadható)
        try:
            if telegram_queue:
                print("Uplink: Telegram retry ({} sor)".format(len(telegram_queue)))
                _flush_telegram_queue()
        except Exception as e:
            print("Telegram retry hiba:", e)

        await asyncio.sleep_ms(0)   # event loop légzési lehetőség

        try:
            n = uplink.flush_pending_from_logger(logger)
            if n:
                print("Uplink: {} offline session feltöltve".format(n))
        except Exception as e:
            print("Uplink task hiba:", e)


async def touch_task():
    """
    Touch logika:
      Normál módban: rövid érintés = mód váltás
      SETUP módban:
        Bal oldal (x<160) hosszú (2mp) = GPS 20m rajtvonal
        Jobb oldal (x>=160) rövid      = Fájlból (track.json)
    """
    held_since   = None
    touch_x      = 0
    SET_HOLD_MS  = 2000
    action_taken = False   # megakadályozza, hogy az ujj felengedése is triggereljon

    while True:
        M5.update()
        touch_count = M5.Touch.getCount()

        if touch_count > 0:
            if held_since is None:
                held_since   = time.ticks_ms()
                action_taken = False
                try:
                    touch_x = M5.Touch.getX()
                except Exception:
                    touch_x = 160

            if not action_taken:
                held_ms = time.ticks_diff(time.ticks_ms(), held_since)
                if held_ms >= SET_HOLD_MS:
                    action_taken = True
                    if disp._mode == 1 and touch_x < 160:   # SETUP bal = GPS
                        ok = set_finish_line_from_gps()
                        if ok:
                            disp._mode = 0
                    elif disp._mode == 1 and touch_x >= 160:  # SETUP jobb = fajlbol
                        ok = set_finish_line_from_file()
                        if ok:
                            disp._mode = 0
                    elif disp._mode == MODE_CALIB:   # CALIB hosszú = kalibrálás
                        ok = lean.calibrate()
                        if ok:
                            _beep(1200, 150)
                            disp.flash_screen(0x003366, 800)   # kék villanas
                        else:
                            _beep(400, 500)
                    elif disp._mode == MODE_IMU:     # IMU hosszú = peak nullázás
                        lean.reset_peaks()
                        _beep(1000, 200)
                        disp._force_redraw = True
                    elif disp._mode == 2:   # MODE_STATS — session küldése Telegram-ra
                        _send_session_to_telegram()
        else:
            if held_since is not None and not action_taken:
                held_ms = time.ticks_diff(time.ticks_ms(), held_since)
                if held_ms < SET_HOLD_MS:
                    if disp._mode == 1:   # SETUP-ban bármilyen rövid érintés = időmérő
                        disp._mode = 0
                        disp._force_redraw = True
                    else:
                        disp.next_mode()
            held_since   = None
            action_taken = False

        await asyncio.sleep_ms(50)    # 20 Hz


# ============================================================
# MAIN
# ============================================================

async def main():
    print("Starting async tasks...")
    await asyncio.gather(
        imu_task(),
        gps_task(),
        display_task(),
        wifi_task(),
        uplink_task(),
        touch_task(),
    )

print("MotoMeter READY")
asyncio.run(main())
