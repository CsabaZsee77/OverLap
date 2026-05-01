# display.py - CoreS3 kijelző kezelés (320x240)
# MotoMeter v0.1 - M5Stack CoreS3

import time
import math

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
SKY_BLUE   = 0x003366
GROUND_BRN = 0x4B2800
PEAK_COLOR = 0xFF6600   # narancssárga — peak hold mutatók

# ============================================================
# KEPERNYO MODOK
# ============================================================
MODE_MAIN        = 0
MODE_SETUP       = 1
MODE_STATS       = 2
MODE_DIAG        = 3
MODE_IMU         = 4
MODE_CALIB       = 5

MODE_NAMES = {
    MODE_MAIN:  "MAIN",
    MODE_SETUP: "SETUP",
    MODE_STATS: "STATS",
    MODE_DIAG:  "DIAG",
    MODE_IMU:   "LEAN",
    MODE_CALIB: "CALIB",
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

        self._c_best_lap        = None
        self._c_max_speed       = None
        self._c_gps_str         = None
        self._c_wifi            = None
        self._c_batt            = None
        self._c_lap_history_len = None

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
        # MAIN → IMU → CALIB → STATS → DIAG → SETUP → MAIN
        cycle = [MODE_MAIN, MODE_IMU, MODE_CALIB, MODE_STATS, MODE_DIAG, MODE_SETUP]
        if self._mode in cycle:
            self._mode = cycle[(cycle.index(self._mode) + 1) % len(cycle)]
        else:
            self._mode = MODE_MAIN
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
               battery_pct=None, lap_start_ts=None, prev_lap_max_kmh=None,
               lap_history=None, lean=None):
        if self._mode == MODE_MAIN:
            self._draw_main(gps, lap_detector, max_speed_kmh,
                            wifi_connected, predicted_ms, prev_lap_ms,
                            battery_pct, lap_start_ts, lap_history=lap_history)
        elif self._mode == MODE_SETUP:
            self._draw_setup(gps, wifi_connected, battery_pct)
        elif self._mode == MODE_STATS:
            self._draw_stats(gps, lap_detector, max_speed_kmh, wifi_connected, battery_pct)
        elif self._mode == MODE_DIAG:
            self._draw_diag(gps, wifi_connected, battery_pct)
        elif self._mode == MODE_IMU:
            self._draw_imu(gps, wifi_connected, battery_pct, lean)
        elif self._mode == MODE_CALIB:
            self._draw_calib(gps, wifi_connected, battery_pct, lean)

    # ------------------------------------------------------------------
    # MODE_MAIN  (320x240)
    #
    # y=0-15    statuszsor
    # y=16      elvalaszto
    # y=17-74   STOPPER szekció: bal=futo ido, jobb=pred (size 3)
    # y=75      elvalaszto
    # y=76-183  LAPS szekció: legutolso kor (size 3) + 2 regi kor (size 2)
    # y=184     elvalaszto
    # y=185-239 BOTTOM: BEST bal | SESSION MAX jobb (size 2)
    # ------------------------------------------------------------------

    def _draw_main(self, gps, lap_det, max_spd, wifi, predicted_ms,
                   prev_lap_ms=None, battery_pct=None, lap_start_ts=None,
                   prev_lap_max_kmh=None, lap_history=None):
        lcd = self._lcd
        if lap_history is None:
            lap_history = []

        best_lap_ms = lap_det.get_best_lap_ms()
        gps_str     = gps.get_status_str()

        if lap_start_ts is not None:
            elapsed_ms = max(0, time.ticks_diff(time.ticks_ms(), lap_start_ts))
        else:
            elapsed_ms = None

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

        # Stopper + pred — mindig ujrarajzol
        self._draw_stopper_and_pred(elapsed_ms, predicted_ms)

        # Kor-lista (csak uj kor vagy best-valtozaskor)
        hist_len = len(lap_history)
        hist_changed = (hist_len != self._c_lap_history_len or best_lap_ms != self._c_best_lap)
        if hist_changed:
            self._draw_lap_rows(lap_history, best_lap_ms)
            self._c_lap_history_len = hist_len
            self._c_best_lap        = best_lap_ms

        # BOTTOM: best + session max
        if hist_changed or max_spd != self._c_max_speed:
            self._draw_bottom_row(best_lap_ms, max_spd)
            self._c_max_speed = max_spd

    def _draw_main_static(self):
        lcd = self._lcd
        lcd.drawLine(0,   16,  320, 16,  DARK_GRAY)  # statuszsor alatt
        lcd.drawLine(0,   84,  320, 84,  DARK_GRAY)  # stopper alatt (size 4 miatt magasabb)
        lcd.drawLine(0,   190, 320, 190, DARK_GRAY)  # laps szekció alatt

        lcd.setTextSize(1)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("STOPPER", 4, 19)
        lcd.drawString("PRED", 220, 19)
        lcd.drawString("LAPS", 4, 87)

    def _draw_stopper_and_pred(self, elapsed_ms, predicted_ms):
        lcd = self._lcd
        lcd.fillRect(0, 27, 320, 55, BLACK)

        # BAL: futo stopper — size 4 (24px/char, 32px tall)
        lcd.setTextSize(4)
        if elapsed_ms is None:
            lcd.setTextColor(DARK_GRAY, BLACK)
            text = "--:--.--"
        else:
            lcd.setTextColor(CYAN, BLACK)
            text = _format_lap(elapsed_ms)
        lcd.drawString(text, 4, 31)

        # JOBB: prediktiv koridő — size 3, jobb szelen igazítva
        lcd.setTextSize(3)
        if predicted_ms is None:
            lcd.setTextColor(DARK_GRAY, BLACK)
            ptext = "--:--.--"
        else:
            lcd.setTextColor(WHITE, BLACK)
            ptext = _format_lap(predicted_ms)
        px = 320 - len(ptext) * 18 - 4
        lcd.drawString(ptext, px, 35)  # y+4: vertikalisan kozepon (size 4=32, size 3=24)

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

    def _draw_lap_rows(self, lap_history, best_lap_ms):
        """
        LAPS szekció (y=86..183):
          - legutolso kor: ido size 3, delta+sebesség size 2
          - 2 regi kor:   ido size 2, delta+sebesség size 1
        Delta = kor_ido - best_lap (vs best)
        """
        lcd = self._lcd
        lcd.fillRect(0, 95, 320, 95, BLACK)

        # ── Legutolso kor (size 4) ────────────────────────────
        last_lap = lap_history[-1] if lap_history else None
        if last_lap:
            lap_ms  = last_lap.get('lap_time_ms')
            max_spd = last_lap.get('max_speed_kmh')
            is_best = (lap_ms is not None and best_lap_ms is not None
                       and lap_ms == best_lap_ms)

            # Koridő (size 4, 32px tall)
            lcd.setTextSize(4)
            lcd.setTextColor(YELLOW if is_best else WHITE, BLACK)
            lcd.drawString(_format_lap(lap_ms), 4, 97)

            # Delta (size 2, vertikalisan kozepon: y+8)
            lcd.setTextSize(2)
            if best_lap_ms is not None and lap_ms is not None:
                if is_best:
                    lcd.setTextColor(YELLOW, BLACK)
                    lcd.drawString("BEST", 176, 105)
                else:
                    d = lap_ms - best_lap_ms
                    lcd.setTextColor(GREEN if d <= 0 else RED, BLACK)
                    lcd.drawString("{}s".format(_format_delta(d)), 176, 105)

            # Max sebesség (size 2, vertikalisan kozepon)
            if max_spd is not None and max_spd > 0:
                lcd.setTextColor(ORANGE, BLACK)
                lcd.drawString("{:.0f}".format(max_spd), 254, 105)
                lcd.setTextSize(1)
                lcd.setTextColor(GRAY, BLACK)
                lcd.drawString("km/h", 290, 109)

        # ── Regi korok: legfeljebb 2 sor (size 2 ido, size 1 delta+spd) ──
        older = lap_history[:-1][-2:][::-1] if len(lap_history) > 1 else []
        for i, lap in enumerate(older):
            y       = 138 + i * 22
            lap_ms  = lap.get('lap_time_ms')
            max_spd = lap.get('max_speed_kmh')
            lap_num = lap.get('lap_number', 0)
            is_best = (lap_ms is not None and best_lap_ms is not None
                       and lap_ms == best_lap_ms)

            # Korszam (size 1)
            lcd.setTextSize(1)
            lcd.setTextColor(GRAY, BLACK)
            lcd.drawString("#{:2d}".format(lap_num), 2, y + 4)

            # Koridő (size 2)
            lcd.setTextSize(2)
            lcd.setTextColor(YELLOW if is_best else WHITE, BLACK)
            lcd.drawString(_format_lap(lap_ms), 20, y)

            # Delta (size 1, vertikalisan kozepon)
            lcd.setTextSize(1)
            if best_lap_ms is not None and lap_ms is not None:
                if is_best:
                    lcd.setTextColor(YELLOW, BLACK)
                    lcd.drawString("BEST", 115, y + 4)
                else:
                    d = lap_ms - best_lap_ms
                    lcd.setTextColor(GREEN if d <= 0 else RED, BLACK)
                    lcd.drawString("{}s".format(_format_delta(d)), 115, y + 4)

            # Max sebesség (size 1)
            if max_spd is not None and max_spd > 0:
                lcd.setTextSize(1)
                lcd.setTextColor(ORANGE, BLACK)
                lcd.drawString("{:.0f}km/h".format(max_spd), 250, y + 4)

    def _draw_bottom_row(self, best_lap_ms, max_spd):
        lcd = self._lcd
        lcd.fillRect(0, 191, 320, 49, BLACK)

        # BEST (bal)
        lcd.setTextSize(1)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("BEST LAP", 6, 202)
        lcd.setTextSize(2)
        lcd.setTextColor(YELLOW, BLACK)
        lcd.drawString(_format_lap(best_lap_ms), 6, 212)

        # SESSION MAX (jobb)
        lcd.setTextSize(1)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("SESSION MAX", 190, 202)
        lcd.setTextSize(2)
        lcd.setTextColor(ORANGE, BLACK)
        lcd.drawString("{:.0f} km/h".format(max_spd), 190, 212)

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
        lcd.drawString("CRS:", 10, 102)
        lcd.drawString("SAT:", 10, 117)
        lcd.drawString("FIX:", 10, 132)
        lcd.drawString("WiFi:", 10, 147)

        self._update_diag_dynamic(gps, wifi, battery_pct)
        self._force_redraw = False

    def _update_diag_dynamic(self, gps, wifi, battery_pct=None):
        lcd = self._lcd
        self._draw_status_bar(gps.get_status_str(), wifi, battery_pct)
        lcd.fillRect(70, 54, 250, 110, BLACK)
        lcd.setTextSize(1)
        lcd.setTextColor(WHITE, BLACK)
        lcd.drawString("{:.6f}".format(gps.lat), 70, 57)
        lcd.drawString("{:.6f}".format(gps.lon), 70, 72)
        lcd.drawString("{:.1f} km/h".format(gps.speed_kmh), 70, 87)
        lcd.drawString("{:.1f} deg".format(gps.course), 70, 102)
        lcd.drawString(str(gps.sats), 70, 117)
        fix_c = GREEN if gps.is_valid() else RED
        lcd.setTextColor(fix_c, BLACK)
        lcd.drawString("OK" if gps.is_valid() else "NO FIX", 70, 132)
        wifi_c = GREEN if wifi else RED
        lcd.setTextColor(wifi_c, BLACK)
        lcd.drawString("CONNECTED" if wifi else "OFFLINE", 70, 147)

    # ------------------------------------------------------------------
    # MODE_IMU  (320x240)
    #
    # y=0-15    státuszsor
    # y=16      elválasztó
    # y=17-37   fejléc: szög + G érték
    # y=38-215  körbe zárt műhorizont (r=88, cx=160, cy=127)
    #           - scan-line kitöltés a körön belül (ég/talaj)
    #           - fehér kör kerület + fokjelzők a peremén
    #           - narancssárga peak tick-ek a peremén
    #           - fix referencia kereszt középen
    # y=216-239 alap: "BAL MAX: 34°  |  JOBB MAX: 28°"
    # ------------------------------------------------------------------

    _IMU_CX = 160
    _IMU_CY = 127
    _IMU_R  = 88

    def _draw_imu(self, gps, wifi, battery_pct, lean):
        lcd = self._lcd

        if self._force_redraw:
            lcd.fillScreen(BLACK)
            lcd.drawLine(0, 16,  320, 16,  DARK_GRAY)
            lcd.drawLine(0, 216, 320, 216, DARK_GRAY)
            lcd.setTextSize(1)
            lcd.setTextColor(GRAY, BLACK)
            lcd.drawString("LEAN", 4, 25)
            self._force_redraw = False

        self._draw_status_bar(gps.get_status_str(), wifi, battery_pct)

        angle      = lean.angle      if lean else 0.0
        peak_right = lean.peak_right if lean else 0.0
        peak_left  = lean.peak_left  if lean else 0.0
        lat_g      = lean.lateral_g  if lean else 0.0

        # ── Fejléc: szög + G ────────────────────────────────────────────
        lcd.fillRect(50, 19, 270, 16, BLACK)
        lcd.setTextSize(2)
        sign = '+' if angle >= 0 else ''
        lcd.setTextColor(WHITE, BLACK)
        lcd.drawString("{}{:.1f}d".format(sign, angle), 65, 19)
        lcd.setTextColor(ORANGE, BLACK)
        lcd.drawString("{:.2f}G".format(abs(lat_g)), 210, 19)

        # ── Kör alakú műhorizont ─────────────────────────────────────────
        self._draw_circular_horizon(lcd, angle, peak_left, peak_right)

        # ── Alap szekció: peak értékek ───────────────────────────────────
        lcd.fillRect(0, 217, 320, 23, BLACK)
        lcd.setTextSize(1)
        lcd.setTextColor(GRAY, BLACK)
        lcd.drawString("BAL MAX:", 4, 218)
        lcd.drawString("JOBB MAX:", 196, 218)
        lcd.setTextSize(2)
        lcd.setTextColor(PEAK_COLOR, BLACK)
        lcd.drawString("{:.1f}d".format(peak_left),  4,  225)
        lcd.drawString("{:.1f}d".format(peak_right), 196, 225)

    def _draw_circular_horizon(self, lcd, angle, peak_left, peak_right):
        """
        Körbe zárt műhorizont, scan-line módszerrel.

        Horizont implicit egyenlete a körön belül:
          sin_a*(x-cx) - cos_a*(y-cy) = 0
        Ég (sky) feltétel: sin_a*(x-cx) - cos_a*(y-cy) > 0
        Ez mindig helyes, még akkor is ha a horizont kilép a körből.

        Peak hold: narancssárga tick jelzők a körkerületen.
        """
        cx = self._IMU_CX
        cy = self._IMU_CY
        r  = self._IMU_R
        r2 = r * r

        rad   = math.radians(angle)
        sin_a = math.sin(rad)
        cos_a = math.cos(rad)

        # ── Scan-line kitöltés ───────────────────────────────────────────
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, r2 - dy * dy)))
            if dx == 0:
                continue
            xl = cx - dx
            xr = cx + dx

            if abs(sin_a) < 0.02:
                # Közel vízszintes horizont (angle ≈ 0°)
                color = SKY_BLUE if dy <= 0 else GROUND_BRN
                lcd.drawLine(xl, y, xr, y, color)
                continue

            # Horizont x a sor tengelyén: sin_a*(x-cx) = cos_a*dy → x_h
            x_h = int(cx + cos_a * dy / sin_a)

            # Ég-e a bal él? Sky feltétel: sin_a*(xl-cx) - cos_a*dy > 0
            sky_left = (sin_a * (xl - cx) - cos_a * dy) > 0

            if x_h <= xl:
                # Horizont a körön kívülre esik balra → egész sor egyszínű
                lcd.drawLine(xl, y, xr, y, SKY_BLUE if sky_left else GROUND_BRN)
            elif x_h >= xr:
                # Horizont a körön kívülre esik jobbra → egész sor egyszínű
                lcd.drawLine(xl, y, xr, y, SKY_BLUE if sky_left else GROUND_BRN)
            else:
                # Horizont átmetszi a sort a körön belül
                if sky_left:
                    lcd.drawLine(xl, y, x_h - 1, y, SKY_BLUE)
                    lcd.drawLine(x_h, y, xr, y, GROUND_BRN)
                else:
                    lcd.drawLine(xl, y, x_h - 1, y, GROUND_BRN)
                    lcd.drawLine(x_h, y, xr, y, SKY_BLUE)

        # ── Körkerület ───────────────────────────────────────────────────
        try:
            lcd.drawCircle(cx, cy, r, WHITE)
        except Exception:
            pass

        # ── Fokjelzők a peremén (-60, -45, -30, 0, +30, +45, +60) ────────
        for tick_a in (-60, -45, -30, -15, 0, 15, 30, 45, 60):
            length = 10 if tick_a % 30 == 0 else 5
            self._rim_tick(lcd, cx, cy, r, tick_a, GRAY, length)

        # ── Peak hold tick-ek ────────────────────────────────────────────
        if peak_right > 2.0:
            self._rim_tick(lcd, cx, cy, r, peak_right,  PEAK_COLOR, 14)
        if peak_left > 2.0:
            self._rim_tick(lcd, cx, cy, r, -peak_left, PEAK_COLOR, 14)

        # ── Horizont vonal (fehér) a körön belül ─────────────────────────
        self._circle_line(lcd, cx, cy, r, angle, WHITE)

        # ── Fix referencia kereszt (repülő szimbólum) ────────────────────
        lcd.drawLine(cx - 35, cy, cx - 12, cy, WHITE)
        lcd.drawLine(cx + 12, cy, cx + 35, cy, WHITE)
        lcd.drawLine(cx - 3, cy - 7, cx + 3, cy - 7, WHITE)
        lcd.drawLine(cx, cy - 7, cx, cy + 3, WHITE)
        lcd.drawPixel(cx, cy, WHITE)

    def _rim_tick(self, lcd, cx, cy, r, angle_deg, color, length):
        """Sugárirányú tick jel a körkerületen."""
        rad   = math.radians(angle_deg)
        sin_a = math.sin(rad)
        cos_a = math.cos(rad)
        x_out = int(cx + r * sin_a)
        y_out = int(cy - r * cos_a)
        x_in  = int(cx + (r - length) * sin_a)
        y_in  = int(cy - (r - length) * cos_a)
        lcd.drawLine(x_in, y_in, x_out, y_out, color)

    def _circle_line(self, lcd, cx, cy, r, angle_deg, color):
        """
        Vízszintes vonalat húz a körön belül, döntve angle_deg-gel.
        A vonal végpontjai a körkerületen lesznek.
        """
        rad   = math.radians(angle_deg)
        # Normálvektor a horizont vonalhoz (merőleges a dőlés irányára)
        # A horizont vonal iránya: (cos(angle), sin(angle)) — perpendicular to lean
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        # Végpontok: r × irányvektor a kör szélén
        x1 = int(cx - r * cos_a)
        y1 = int(cy - r * sin_a)
        x2 = int(cx + r * cos_a)
        y2 = int(cy + r * sin_a)
        lcd.drawLine(x1, y1, x2, y2, color)
        # Vastagabb vonal: egy párhuzamos eltolva
        lcd.drawLine(x1, y1 + 1, x2, y2 + 1, color)

    # ------------------------------------------------------------------
    # MODE_CALIB  (320x240)
    #
    # Kalibráció képernyő.
    # Mutatja a nyers szenzor értékeket és a kalibrált szöget.
    # Hosszú érintésre (touch_task kezeli) elvégzi a kalibrációt.
    # ------------------------------------------------------------------

    def _draw_calib(self, gps, wifi, battery_pct, lean):
        lcd = self._lcd

        if self._force_redraw:
            lcd.fillScreen(BLACK)
            lcd.drawLine(0, 16, 320, 16, DARK_GRAY)
            lcd.drawLine(0, 44, 320, 44, DARK_GRAY)

            lcd.setTextSize(2)
            lcd.setTextColor(CYAN, BLACK)
            lcd.drawString("IMU KALIBRÁCIÓ", 35, 22)

            lcd.setTextSize(1)
            lcd.setTextColor(GRAY, BLACK)
            lcd.drawString("Tartsd egyenesbe a motort,", 10, 52)
            lcd.drawString("majd tartsd 2mp-ig az erintot.", 10, 65)

            lcd.drawLine(0, 80, 320, 80, DARK_GRAY)
            self._force_redraw = False

        self._draw_status_bar(gps.get_status_str(), wifi, battery_pct)
        lcd.fillRect(0, 82, 320, 130, BLACK)

        if lean and lean.is_ready:
            angle = lean.angle
            lat_g = lean.lateral_g

            lcd.setTextSize(1)
            lcd.setTextColor(GRAY, BLACK)
            lcd.drawString("Aktualis dolés:", 10, 90)
            lcd.setTextSize(3)
            sign = '+' if angle >= 0 else ''
            lcd.setTextColor(WHITE if abs(angle) < 5 else YELLOW, BLACK)
            lcd.drawString("{}{:.1f} fok".format(sign, angle), 10, 107)

            lcd.setTextSize(1)
            lcd.setTextColor(GRAY, BLACK)
            lcd.drawString("Lateral G:", 10, 143)
            lcd.setTextColor(ORANGE, BLACK)
            lcd.drawString("{:.3f} G".format(lat_g), 90, 143)

            lcd.setTextColor(GREEN if abs(angle) < 3 else GRAY, BLACK)
            lcd.drawString(
                "OK - egyenes" if abs(angle) < 3 else "Igazitsd ki!", 10, 160)
        else:
            lcd.setTextSize(2)
            lcd.setTextColor(RED, BLACK)
            lcd.drawString("IMU nem elerheto", 10, 110)

        lcd.setTextSize(1)
        lcd.setTextColor(DARK_GRAY, BLACK)
        lcd.drawString("Hosszan: kalibral  |  Roviden: vissza", 10, 225)

    # ------------------------------------------------------------------
    # Seged
    # ------------------------------------------------------------------

    def _clear_cache(self):
        self._c_best_lap        = None
        self._c_max_speed       = None
        self._c_gps_str         = None
        self._c_wifi            = None
        self._c_batt            = None
        self._c_lap_history_len = None
