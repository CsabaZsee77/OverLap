# demo.py - OverLap bemutatómód
# Telepítés: mpremote cp firmware/demo.py :/flash/overlap/demo.py
# Indítás:   launcher DEFAULT_APP = '/flash/overlap/demo.py'
#
# Viselkedés:
#   - SETUP képernyőn indul (● 12 sat, WiFi, 100% akku)
#   - Jobb oldal 2mp tartás → zöld villanas → MAIN
#   - Stopper 10x gyorsítva (5s real = 50s kijelzőn)
#   - Körök: ~50s ± 3s, ~95 km/h ± 8 km/h
#   - 3 szektoros predikcio

import M5
from M5 import *
import uasyncio as asyncio
import time
import random
import network

print("OverLap DEMO indulas...")
M5.begin()
Widgets.fillScreen(0x000000)

from overlap.display import MotoDisplay
from overlap import config
from overlap.telegram import TelegramNotifier

# ============================================================
# PARAMÉTEREK
# ============================================================
DEMO_SPEED    = 10       # 10x gyorsabb virtuális idő
LAP_MS        = 50_000   # cél körido (virtuális ms)
LAP_SCATTER   = 3_000    # ±szórás (virtuális ms)
SPEED_TGT     = 95.0     # cél max sebesség (km/h)
SPEED_SCT     = 8.0      # ±szórás
N_SECTORS     = 3        # szektorszám

# ============================================================
# FAKE OBJEKTUMOK
# ============================================================

class FakeGPS:
    sats      = 12
    lat       = 47.0880
    lon       = 19.2830
    speed_kmh = 90.0
    course    = 0.0
    valid     = True
    last_fix_ms = 0

    def get_status_str(self): return "●12"
    def is_valid(self):       return True
    def get_position(self):   return self.lat, self.lon, self.speed_kmh, self.last_fix_ms
    def update(self): pass
    def begin(self):  pass


class FakeLapDet:
    def __init__(self):
        self._best  = None
        self._count = 0

    def get_best_lap_ms(self): return self._best
    def get_lap_count(self):   return self._count

    def record(self, ms):
        self._count += 1
        if self._best is None or ms < self._best:
            self._best = ms

# ============================================================
# GLOBÁLIS ÁLLAPOT
# ============================================================
gps     = FakeGPS()
lap_det = FakeLapDet()
disp    = MotoDisplay(M5.Lcd)

lap_history       = []
wifi_connected    = False
battery_pct       = 100
session_active    = False
max_speed_session = 0.0

telegram       = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
telegram_queue = []
telegram_sent  = set()

_real_start  = None          # ticks_ms() a session indításakor
_lap_start_v = None          # virtuális ms a kör kezdetén
_lap_end_v   = None          # virtuális ms a kör végén
_lap_splits  = []            # aktuális kör szektorcéljai [ms, ms, ms]
_sector_best = [None] * N_SECTORS  # legjobb szektoridők

# ============================================================
# VIRTUÁLIS IDŐ
# ============================================================

def _vt():
    """Virtuális demo idő ms-ben (DEMO_SPEED-szeres gyorsítás)."""
    if _real_start is None:
        return 0
    return time.ticks_diff(time.ticks_ms(), _real_start) * DEMO_SPEED


def _lap_start_ts_for_display():
    """
    Visszaad egy fake ticks_ms értéket úgy, hogy
    ticks_diff(now, result) == virtuális_elapsed
    → a display pontosan a 10x-es időt mutatja.
    """
    if _lap_start_v is None:
        return None
    v_elapsed = int(_vt() - _lap_start_v)
    return time.ticks_add(time.ticks_ms(), -v_elapsed)

# ============================================================
# KÖR LOGIKA
# ============================================================

def _new_splits(lap_ms):
    """N_SECTORS szektort generál, összegük = lap_ms."""
    base = lap_ms // N_SECTORS
    spl  = []
    rem  = lap_ms
    for _ in range(N_SECTORS - 1):
        scatter = base // 5   # ±20%
        s = max(4000, base + random.randint(-scatter, scatter))
        spl.append(s)
        rem -= s
    spl.append(max(4000, rem))
    return spl


def _start_lap():
    global _lap_start_v, _lap_end_v, _lap_splits
    vt = _vt()
    _lap_start_v = vt
    lap_ms       = LAP_MS + random.randint(-LAP_SCATTER, LAP_SCATTER)
    _lap_end_v   = vt + lap_ms
    _lap_splits  = _new_splits(lap_ms)


def _finish_lap():
    global _sector_best, max_speed_session
    lap_ms = int(_vt() - _lap_start_v)

    # Szektoros best frissítés
    for i, s in enumerate(_lap_splits):
        if _sector_best[i] is None or s < _sector_best[i]:
            _sector_best[i] = s

    # Max sebesség
    spd = SPEED_TGT + random.uniform(-SPEED_SCT, SPEED_SCT)
    if spd > max_speed_session:
        max_speed_session = spd

    # Hang
    try:
        M5.Speaker.setVolume(60)
        M5.Speaker.tone(1000, 300)
    except Exception:
        pass

    prev_best = lap_det.get_best_lap_ms()
    lap_det.record(lap_ms)
    is_best  = (lap_ms == lap_det.get_best_lap_ms())
    delta_ms = 0 if prev_best is None else (lap_ms - prev_best)

    if is_best:
        try:
            M5.Speaker.tone(1400, 100)
            time.sleep_ms(120)
            M5.Speaker.tone(1800, 200)
        except Exception:
            pass

    lap_history.append({
        'lap_number':    lap_det._count,
        'lap_time_ms':   lap_ms,
        'max_speed_kmh': round(spd, 1),
        'is_best':       is_best,
    })
    if len(lap_history) > 10:
        lap_history.pop(0)

    telegram_queue.append({
        'lap_number':      lap_det._count,
        'lap_time_ms':     lap_ms,
        'delta_ms':        delta_ms,
        'is_best':         is_best,
        'max_speed_kmh':   round(spd, 1),
        'sector_times_ms': list(_lap_splits),
        'track_name':      'DEMO',
    })
    if wifi_connected:
        _flush_telegram_queue()


def _predicted_ms():
    """Szektoros predikcio: elapsed + legjobb maradék szektorok."""
    if _lap_start_v is None or not _lap_splits:
        return None
    elapsed = _vt() - _lap_start_v
    cumul   = 0
    for i, split in enumerate(_lap_splits):
        cumul += split
        if elapsed < cumul:
            pred = elapsed
            for j in range(i + 1, N_SECTORS):
                b     = _sector_best[j]
                pred += b if b is not None else _lap_splits[j]
            return int(pred)
    return None

# ============================================================
# WIFI + TELEGRAM
# ============================================================

def connect_wifi():
    global wifi_connected
    if not config.WIFI_SSID:
        return
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            print("DEMO WiFi: csatlakozas '{}'...".format(config.WIFI_SSID))
            wlan.connect(config.WIFI_SSID, config.WIFI_PASS)
        wifi_connected = wlan.isconnected()
    except Exception as e:
        print("DEMO WiFi hiba:", e)
        wifi_connected = False


def _flush_telegram_queue():
    while telegram_queue:
        item = telegram_queue[0]
        key  = item['lap_number']
        if key in telegram_sent:
            telegram_queue.pop(0)
            continue
        ok = telegram.send_lap(**item)
        if ok:
            telegram_sent.add(key)
            telegram_queue.pop(0)
        else:
            print("DEMO Telegram: hiba, kesobb probaljuk")
            break


connect_wifi()

# ============================================================
# BOOT KÉPERNYŐ
# ============================================================
disp.begin()
disp._mode        = 1     # SETUP-pal indul
disp._force_redraw = True

# ============================================================
# ASYNC TASKOK
# ============================================================

async def demo_task():
    """Körido szimuláció — 100ms-onként ellenőriz."""
    while True:
        if session_active and _lap_end_v is not None:
            if _vt() >= _lap_end_v:
                _finish_lap()
                _start_lap()
        await asyncio.sleep_ms(100)


async def display_task():
    global battery_pct
    batt_tick = 0
    while True:
        if batt_tick <= 0:
            try:
                battery_pct = M5.Power.getBatteryLevel()
            except Exception:
                battery_pct = 100
            batt_tick = 150

        batt_tick -= 1

        pred_ms      = _predicted_ms() if session_active else None
        lap_start_ts = _lap_start_ts_for_display() if session_active else None

        disp.update(
            gps            = gps,
            lap_detector   = lap_det,
            max_speed_kmh  = max_speed_session,
            wifi_connected = wifi_connected,
            predicted_ms   = pred_ms,
            prev_lap_ms    = None,
            battery_pct    = battery_pct,
            lap_start_ts   = lap_start_ts,
            lap_history    = lap_history,
        )
        await asyncio.sleep_ms(200)


async def wifi_task():
    global wifi_connected
    while True:
        await asyncio.sleep_ms(config.WIFI_RETRY_INTERVAL_S * 1000)
        try:
            wlan = network.WLAN(network.STA_IF)
            wifi_connected = wlan.isconnected()
            if not wifi_connected and config.WIFI_SSID:
                connect_wifi()
                await asyncio.sleep_ms(5000)
                wifi_connected = wlan.isconnected()
                if wifi_connected and telegram_queue:
                    print("DEMO WiFi reconnect OK — Telegram flush")
                    _flush_telegram_queue()
        except Exception as e:
            print("DEMO wifi_task hiba:", e)


async def touch_task():
    global session_active, _real_start
    held_since   = None
    touch_x      = 160
    SET_HOLD_MS  = 2000
    action_taken = False

    while True:
        M5.update()
        tc = M5.Touch.getCount()

        if tc > 0:
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
                    if disp._mode == 1 and touch_x >= 160:
                        # SETUP jobb oldal: demo inditasa
                        disp.flash_screen(0x00FF00, 2000)
                        _real_start    = time.ticks_ms()
                        session_active = True
                        _start_lap()
                        disp._mode        = 0
                        disp._force_redraw = True
        else:
            if held_since is not None and not action_taken:
                held_ms = time.ticks_diff(time.ticks_ms(), held_since)
                if held_ms < SET_HOLD_MS:
                    if disp._mode != 1:
                        disp.next_mode()
            held_since   = None
            action_taken = False

        await asyncio.sleep_ms(50)


async def main():
    print("DEMO KESZ — SETUP kepernyon jobb oldal 2mp-ig tartva indit")
    await asyncio.gather(
        demo_task(),
        display_task(),
        wifi_task(),
        touch_task(),
    )


asyncio.run(main())
