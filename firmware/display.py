# display.py - CoreS3 kijelző kezelés (320x240)
# MotoMeter v0.1 - M5Stack CoreS3

import time

# ============================================================
# SZINEK
# ============================================================
BLACK      = 0x000000
WHITE      = 0xFFFFFF
GREEN      = 0x00FF00
RED        = 0xFF0000
YELLOW     = 0xFFFF00
ORANGE     = 0xFF8C00
CYAN       = 0x00FFFF
GRAY       = 0x888888
DARK_GRAY  = 0x333333
DIM_GRAY   = 0x1A1A1A

# ============================================================
# KEPERNYO MODOK
# ============================================================
MODE_MAIN        = 0
MODE_SETUP       = 1
MODE_STATS       = 2
MODE_DIAG        = 3

MODE_NAMES = {
    MODE_MAIN:  "MAIN",
    MODE_SETUP: "SETUP",
    MODE_STATS: "STATS",
    MODE_DIAG:  "DIAG",
}


def _format_lap(ms):
    if ms is None:
        return "--:--.--"
    s_total = ms // 1000
    m = s_total // 60
    s = s_total % 60
    cs = (ms % 1000) // 10
    return "{}:{:02d}.{:02d}".format(m, s, cs)


def _format_delta(ms):
    if ms is None:
        return "---"
    sign = '+' if ms >= 0 else '-'
    abs_ms = abs(ms)
    s = abs_ms // 1000
    cs = (abs_ms % 1000) // 10
    return "{}{}.{:02d}".format(sign, s, cs)


class MotoDisplay:

    def __init__(self, lcd):
        self._lcd = lcd
        self._mode = MODE_MAIN

        self._c_prev_lap   = None
        self._c_best_lap   = None
        self._c_predicted  = None
        self._c_delta      = None
        self._c_max_speed  = None
        self._c_gps_str    = None
        self._c_wifi       = None
        self._c_batt       = None
        self._c_mode       = None
        self._c_prev_max   = None

        self._force_redraw = True

    # ------------------------------------------------------------------
    # Publikus API
    # ------------------------------------------------------------------

    def begin(self):
        lcd = self._lcd
        lcd.fillScreen(BLACK)
        lcd.setTextColor(CYAN, BLACK)
        lcd.setTextSize(3)
        lcd.drawString("OverLAP", 75, 85)
        lcd.setTextColor(GRAY, BLACK)
        lcd.setTextSize(1)
        lcd.drawString("v0.1  Lap Timing Platform", 55, 130)
        time.sleep_ms(1500)
        self._force_redraw = True

    def next_mode(self):
        self._mode = (self._mode + 1) % 4
        self._force_redraw = True
        self._clear_cache()

    def flash_screen(self, color=GREEN, duration_ms=800):
        """Teljes kepernyo villanas — rajtvonal beallitas visszajelzes."""
        self._lcd.fillScreen(color)
        time.sleep_ms(duration_ms)
        self._force_redraw = True
        self._clear_cache()

    def update(self, gps, lap_detector, max_speed_kmh=0.0,
               wifi_connected=False, predicted_ms=None, prev_lap_ms=None,
               battery_pct=None, lap_start_ts=None, prev_lap_max_kmh=None):
        if self._mode == MODE_MAIN:
            self._draw_main(gps, lap_detector, max_speed_kmh,
                            wifi_connected, predicted_ms, prev_lap_ms,
                            battery_pct, lap_start_ts, prev_lap_max_kmh)
        elif self._mode == MODE_SETUP:
            self._draw_setup(gps, wifi_connected, battery_pct)
        elif self._mode == MODE_STATS:
            self._draw_stats(gps, lap_detector, max_speed_kmh, wifi_connected, battery_pct)
        elif self._mode == MODE_DIAG:
            self._draw_diag(gps, wifi_connected, battery_pct)

    # ------------------------------------------------------------------
    # MODE_MAIN
    #
    # y=0-15    statuszsor (GPS, WiFi, akku, mod)
    # y=16      elvalaszto vonal
    # y=20      "STOPPER" felirat (size 1)
    # y=28-75   nagy futo szamlalo (size 5, CYAN ha aktiv, sotet ha nem)
    # y=105     elvalaszto vonal
    # y=110     BEST | ELOZO cimkek (size 2, szurke)
    # y=128     BEST ertek (sarga) | ELOZO ertek (feher)
    # y=152     DELTA ertek (szines) | PRED ertek (feher)
    # y=192     elvalaszto vonal
    # y=198     MAX sebesseg (narancs)
    # ------------------------------------------------------------------

    def _draw_main(self, gps, lap_det, max_spd, wifi, predicted_ms,
                   prev_lap_ms=None, battery_pct=None, lap_start_ts=None,
                   prev_lap_max_kmh=None):
        lcd = self._lcd

        best_lap_ms = lap_det.get_best_lap_ms()
        gps_str     = gps.get_status_str()

        # Futo stopper szamitasa
        if lap_start_ts is not None:
            elapsed_ms = max(0, time.ticks_diff(time.ticks_ms(), lap_start_ts))
        else:
            elapsed_ms = None

        # Delta (pred vs best, vagy elozo vs best)
        delta_ms = None
        if predicted_ms is not None and best_lap_ms is not None:
            delta_ms = predicted_ms - best_lap_ms
        elif prev_lap_ms is not None and best_lap_ms is not None:
            delta_ms = prev_lap_ms - best_lap_ms

        if self._force_redraw:
            lcd.fillScreen(BLACK)
            self._draw_main_static()
            self._force_redraw = False
            self._clear_cache()

        # Statuszsor
        if gps_str != self._c_gps_str or wifi != self._c_wifi or battery_pct != self._c_batt:
            self._draw_status_bar(gps_str, wifi, battery_pct)
            self._c_gps_str = gps_str
            self._c_wifi    = wifi
            self._c_batt    = battery_pct

        # Futo stopper — mindig ujrarajzol (mindig valtozik)
        self._draw_stopper(elapsed_ms)

        # BEST + ELOZO (és ELOZO max sebesseg)
        if (best_lap_ms != self._c_best_lap or prev_lap_ms != self._c_prev_lap
                or prev_lap_max_kmh != self._c_prev_max):
            self._draw_best_and_prev(best_lap_ms, prev_lap_ms, prev_lap_max_kmh)
            self._c_best_lap = best_lap_ms
            self._c_prev_lap = prev_lap_ms
            self._c_prev_max = prev_lap_max_kmh

        # DELTA + PRED
        if delta_ms != self._c_delta or predicted_ms != self._c_predicted:
            self._draw_pred_delta(delta_ms, predicted_ms)
            self._c_delta     = delta_ms
            self._c_predicted = predicted_ms

        # MAX sebesseg
        if max_spd != self._c_max_speed:
            self._draw_bottom_row(max_spd)
            self._c_max_speed = max_spd

    def _draw_main_static(self):
        lcd = self._lcd
        lcd.drawLine(0, 16,  320, 16,  DARK_GRAY)
        lcd.drawLine(0, 105, 320, 105, DARK_GRAY)
        lcd.drawLine(0, 192, 320, 192, DARK_GRAY)

        lcd.setTextSize(1)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("STOPPER", 4, 20)

    def _draw_stopper(self, elapsed_ms):
        lcd = self._lcd
        lcd.fillRect(0, 27, 320, 76, BLACK)
        lcd.setTextSize(5)
        if elapsed_ms is None:
            lcd.setTextColor(DARK_GRAY, BLACK)
            text = "--:--.--"
        else:
            lcd.setTextColor(CYAN, BLACK)
            text = _format_lap(elapsed_ms)
        x = max(4, (320 - len(text) * 30) // 2)
        lcd.drawString(text, x, 30)

    def _draw_status_bar(self, gps_str, wifi, battery_pct=None):
        lcd = self._lcd
        lcd.fillRect(0, 0, 320, 16, DIM_GRAY)
        lcd.setTextSize(1)

        gps_color = GREEN if gps_str.startswith('●') else RED
        lcd.setTextColor(gps_color, DIM_GRAY)
        lcd.drawString(gps_str, 2, 3)

        wifi_color = GREEN if wifi else GRAY
        lcd.setTextColor(wifi_color, DIM_GRAY)
        lcd.drawString("WiFi", 140, 3)

        if battery_pct is not None:
            batt_color = GREEN if battery_pct > 50 else (YELLOW if battery_pct > 20 else RED)
            lcd.setTextColor(batt_color, DIM_GRAY)
            lcd.drawString("{}%".format(battery_pct), 195, 3)

        lcd.setTextColor(GRAY, DIM_GRAY)
        lcd.drawString(MODE_NAMES.get(self._mode, ""), 270, 3)

    def _draw_best_and_prev(self, best_ms, prev_ms, prev_max_kmh=None):
        lcd = self._lcd
        # Harom sor kell: cimkek + idok + max sebesseg → 50 px
        lcd.fillRect(0, 106, 320, 50, BLACK)

        # Cimkek (size 1)
        lcd.setTextSize(1)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("BEST", 4, 109)
        lcd.drawString("ELOZO", 180, 109)

        # Idok (size 2)
        lcd.setTextSize(2)
        lcd.setTextColor(YELLOW, BLACK)
        lcd.drawString(_format_lap(best_ms), 4, 119)
        lcd.setTextColor(WHITE, BLACK)
        lcd.drawString(_format_lap(prev_ms), 180, 119)

        # Elozo kor max sebessege (size 1, narancs)
        if prev_max_kmh is not None and prev_max_kmh > 0:
            lcd.setTextSize(1)
            lcd.setTextColor(ORANGE, BLACK)
            lcd.drawString("{:.0f} km/h".format(prev_max_kmh), 180, 138)

    def _draw_pred_delta(self, delta_ms, predicted_ms):
        lcd = self._lcd
        # A BEST/ELOZO sor most 3 soros (y=106..156), ezert DELTA/PRED lejjebb
        lcd.fillRect(0, 156, 320, 36, BLACK)
        lcd.setTextSize(2)

        # DELTA (bal)
        if delta_ms is None:
            lcd.setTextColor(GRAY, BLACK)
            lcd.drawString("DELTA ---", 4, 159)
        else:
            color = GREEN if delta_ms <= 0 else RED
            lcd.setTextColor(color, BLACK)
            lcd.drawString("DELTA {}s".format(_format_delta(delta_ms)), 4, 159)

        # PRED (jobb)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("PRED", 190, 159)
        lcd.setTextColor(WHITE, BLACK)
        lcd.drawString(_format_lap(predicted_ms), 190, 175)

    def _draw_bottom_row(self, max_spd):
        lcd = self._lcd
        lcd.fillRect(0, 193, 320, 47, BLACK)
        lcd.setTextSize(1)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("SESSION MAX", 6, 196)
        lcd.setTextSize(2)
        lcd.setTextColor(ORANGE, BLACK)
        lcd.drawString("{:.0f} km/h".format(max_spd), 6, 206)

    # ------------------------------------------------------------------
    # MODE_SETUP
    # ------------------------------------------------------------------

    def _draw_setup(self, gps, wifi=False, battery_pct=None):
        if not self._force_redraw:
            self._update_setup_coords(gps, wifi, battery_pct)
            return

        lcd = self._lcd
        lcd.fillScreen(BLACK)

        self._draw_status_bar(gps.get_status_str(), wifi, battery_pct)

        lcd.setTextSize(2)
        lcd.setTextColor(CYAN, BLACK)
        lcd.drawString("RAJTVONAL FELVETEL", 10, 22)

        lcd.drawLine(0, 44, 320, 44, DARK_GRAY)
        lcd.drawLine(160, 44, 160, 112, DARK_GRAY)

        lcd.setTextSize(1)
        lcd.setTextColor(YELLOW, BLACK)
        lcd.drawString("[ BAL ] GPS 20m", 8, 52)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("Hajts el mellette,", 8, 68)
        lcd.drawString("tartsd 2mp-ig", 8, 80)

        lcd.setTextColor(GREEN, BLACK)
        lcd.drawString("[ JOBB ] Fajlbol", 168, 52)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("track.json erintsd", 168, 68)
        lcd.drawString("(SD vagy flash)", 168, 80)

        lcd.drawLine(0, 112, 320, 112, DARK_GRAY)

        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("Aktualis GPS pozicio:", 10, 118)

        self._update_setup_coords(gps, wifi, battery_pct)
        self._force_redraw = False

    def _update_setup_coords(self, gps, wifi=False, battery_pct=None):
        lcd = self._lcd
        self._draw_status_bar(gps.get_status_str(), wifi, battery_pct)
        lcd.fillRect(0, 130, 320, 80, BLACK)
        lcd.setTextSize(2)
        if gps.is_valid():
            lcd.setTextColor(GREEN, BLACK)
            lcd.drawString("LAT: {:.6f}".format(gps.lat), 10, 135)
            lcd.drawString("LON: {:.6f}".format(gps.lon), 10, 158)
            lcd.drawString("SAT: {}".format(gps.sats), 10, 181)
        else:
            lcd.setTextColor(RED, BLACK)
            lcd.drawString("GPS: NO FIX", 80, 158)

    # ------------------------------------------------------------------
    # MODE_STATS
    # ------------------------------------------------------------------

    def _draw_stats(self, gps, lap_det, max_spd, wifi=False, battery_pct=None):
        if not self._force_redraw:
            return

        lcd = self._lcd
        lcd.fillScreen(BLACK)

        self._draw_status_bar(gps.get_status_str(), wifi, battery_pct)

        lcd.setTextSize(2)
        lcd.setTextColor(CYAN, BLACK)
        lcd.drawString("SESSION STATS", 65, 22)
        lcd.drawLine(0, 44, 320, 44, DARK_GRAY)

        best = lap_det.get_best_lap_ms()
        laps = lap_det.get_lap_count()

        lcd.setTextSize(2)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("BEST LAP:", 10, 57)
        lcd.setTextColor(YELLOW, BLACK)
        lcd.drawString(_format_lap(best), 160, 57)

        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("KOROK:", 10, 87)
        lcd.setTextColor(WHITE, BLACK)
        lcd.drawString(str(laps), 160, 87)

        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("MAX SPEED:", 10, 117)
        lcd.setTextColor(ORANGE, BLACK)
        lcd.drawString("{:.0f} km/h".format(max_spd), 160, 117)

        lcd.setTextSize(1)
        lcd.setTextColor(DARK_GRAY, BLACK)
        lcd.drawString("Erintsd meg a kovetkezo modhoz", 40, 220)

        self._force_redraw = False

    # ------------------------------------------------------------------
    # MODE_DIAG
    # ------------------------------------------------------------------

    def _draw_diag(self, gps, wifi, battery_pct=None):
        if not self._force_redraw:
            self._update_diag_dynamic(gps, wifi, battery_pct)
            return

        lcd = self._lcd
        lcd.fillScreen(BLACK)

        self._draw_status_bar(gps.get_status_str(), wifi, battery_pct)

        lcd.setTextSize(2)
        lcd.setTextColor(CYAN, BLACK)
        lcd.drawString("DIAGNOSZTIKA", 65, 22)
        lcd.drawLine(0, 44, 320, 44, DARK_GRAY)

        lcd.setTextSize(1)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("LAT:", 10, 57)
        lcd.drawString("LON:", 10, 72)
        lcd.drawString("SPD:", 10, 87)
        lcd.drawString("SAT:", 10, 102)
        lcd.drawString("FIX:", 10, 117)
        lcd.drawString("WiFi:", 10, 132)

        self._update_diag_dynamic(gps, wifi, battery_pct)
        self._force_redraw = False

    def _update_diag_dynamic(self, gps, wifi, battery_pct=None):
        lcd = self._lcd
        self._draw_status_bar(gps.get_status_str(), wifi, battery_pct)
        lcd.fillRect(70, 54, 250, 95, BLACK)
        lcd.setTextSize(1)
        lcd.setTextColor(WHITE, BLACK)
        lcd.drawString("{:.6f}".format(gps.lat), 70, 57)
        lcd.drawString("{:.6f}".format(gps.lon), 70, 72)
        lcd.drawString("{:.1f} km/h".format(gps.speed_kmh), 70, 87)
        lcd.drawString(str(gps.sats), 70, 102)
        fix_c = GREEN if gps.is_valid() else RED
        lcd.setTextColor(fix_c, BLACK)
        lcd.drawString("OK" if gps.is_valid() else "NO FIX", 70, 117)
        wifi_c = GREEN if wifi else RED
        lcd.setTextColor(wifi_c, BLACK)
        lcd.drawString("CONNECTED" if wifi else "OFFLINE", 70, 132)

    # ------------------------------------------------------------------
    # Seged
    # ------------------------------------------------------------------

    def _clear_cache(self):
        self._c_prev_lap  = None
        self._c_best_lap  = None
        self._c_predicted = None
        self._c_delta     = None
        self._c_max_speed = None
        self._c_gps_str   = None
        self._c_wifi      = None
        self._c_batt      = None
        self._c_prev_max  = None
