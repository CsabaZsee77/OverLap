# gps.py - AT6558 GPS modul kezelés (NMEA parser + Kalman + 10Hz konfig)
# MotoMeter v0.1 - M5Stack CoreS3
#
# Hardware: M5Stack GPS Unit (AT6558 chip)
# UART2, tx=Pin(17), rx=Pin(18), baudrate=115200
# Referencia: Kormoran lib_sensors.py GPSSensor osztály

import time
from machine import UART, Pin
from motometer.kalman import KalmanFilter

# AT6558 parancsok
_CMD_10HZ = b'$PMTK220,100*2F\r\n'   # 10 Hz frissítési sebesség
_CMD_GGA_RMC = b'$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28\r\n'  # csak RMC+GGA

# Állapotok
STATE_INIT    = 'init'
STATE_NO_FIX  = 'no_fix'
STATE_FIX_OK  = 'fix_ok'


class GPSSensor:
    """
    AT6558 GPS szenzor — NMEA parse, Kalman szűrés, köridő-mérő alapadatok.

    Publikus adatok (olvasható):
        lat, lon        — szűrt pozíció (fok, float)
        speed_kmh       — szűrt sebesség (km/h)
        course          — irány (fok, 0–360)
        sats            — műholdak száma
        valid           — bool: érvényes FIX
        last_fix_ms     — utolsó érvényes fix időbélyege (ticks_ms)
        state           — 'init' / 'no_fix' / 'fix_ok'
    """

    def __init__(self):
        self.state = STATE_INIT

        # GPS UART (Kormoran: UART2, GPIO 17/18, 115200)
        try:
            self._uart = UART(
                2,
                baudrate=115200,
                tx=Pin(17),
                rx=Pin(18),
                rxbuf=1024,
                timeout=10
            )
            self._available = True
            print("GPS: UART2 OK (GPIO 17/18)")
        except Exception as e:
            self._uart = None
            self._available = False
            print("GPS: UART hiba —", e)

        # Kalman szűrők (pozíció + sebesség)
        self._kf_lat   = KalmanFilter(Q=0.1, R=2.0)
        self._kf_lon   = KalmanFilter(Q=0.1, R=2.0)
        self._kf_speed = KalmanFilter(Q=0.05, R=1.0)

        # Nyers és szűrt adatok
        self.lat       = 0.0
        self.lon       = 0.0
        self.speed_kmh = 0.0
        self.course    = 0.0
        self.sats      = 0
        self.valid     = False
        self.last_fix_ms = 0
        self._first_fix  = True

        # NMEA buffer
        self._buf = ""

        self.state = STATE_NO_FIX

    # ------------------------------------------------------------------
    # Publikus API
    # ------------------------------------------------------------------

    def begin(self):
        """10 Hz konfiguráció küldése a GPS modulnak."""
        if not self._available:
            return
        try:
            self._uart.write(_CMD_10HZ)
            time.sleep_ms(200)
            self._uart.write(_CMD_GGA_RMC)
            time.sleep_ms(100)
            print("GPS: 10 Hz + GGA/RMC konfig elküldve")
        except Exception as e:
            print("GPS: konfig hiba —", e)

    def update(self):
        """
        NMEA buffer olvasás és feldolgozás.
        Hívandó: async task-ból ~10 Hz-en (100 ms-onként).
        """
        if not self._available:
            return

        try:
            if not self._uart.any():
                return

            raw = self._uart.read()
            if not raw:
                return

            try:
                text = raw.decode('utf-8', 'ignore')
            except Exception:
                return

            self._buf += text

            # Sorok feldolgozása
            while '\n' in self._buf:
                line, self._buf = self._buf.split('\n', 1)
                line = line.strip()
                if not line.startswith('$'):
                    continue

                if 'RMC' in line:
                    self._parse_rmc(line)
                elif 'GGA' in line:
                    self._parse_gga(line)

        except Exception as e:
            print("GPS update hiba:", e)
            self._buf = ""

    def is_valid(self):
        """True ha érvényes GPS FIX van és nem régebbi 5 másodpercnél."""
        if not self.valid:
            return False
        age_ms = time.ticks_diff(time.ticks_ms(), self.last_fix_ms)
        return age_ms < 5000

    def get_position(self):
        """
        Visszaad: (lat, lon, speed_kmh, ticks_ms)
        """
        return self.lat, self.lon, self.speed_kmh, self.last_fix_ms

    def get_status_str(self):
        """Rövid státusz string a kijelzőhöz: pl. '●9' vagy '○--'"""
        if self.valid:
            return "●{}".format(self.sats)
        else:
            return "○--"

    # ------------------------------------------------------------------
    # NMEA parsers
    # ------------------------------------------------------------------

    def _parse_rmc(self, line):
        """
        $GPRMC,HHMMSS.ss,A,LLLL.LL,a,YYYYY.YY,a,x.x,x.x,DDMMYY,...
        parts[2]: A=valid, V=invalid
        parts[3-6]: lat/lon
        parts[7]: speed (knots)
        parts[8]: course (deg)
        """
        parts = line.split(',')
        if len(parts) < 9:
            return

        # Érvényesség
        if parts[2] != 'A':
            self.valid = False
            self.state = STATE_NO_FIX
            return

        try:
            # Sebesség (knots → km/h)
            raw_speed_kts = float(parts[7]) if parts[7] else 0.0
            speed_kmh = raw_speed_kts * 1.852

            # Kalman szűrés
            self.speed_kmh = self._kf_speed.update(speed_kmh)

            # Irány
            if parts[8]:
                self.course = float(parts[8])

            # Pozíció
            if parts[3] and parts[4] and parts[5] and parts[6]:
                lat = self._nmea_to_deg(parts[3], parts[4])
                lon = self._nmea_to_deg(parts[5], parts[6])

                # Kalman: első FIX után inicializáljuk (ne 0-ból konvergáljon)
                if self._first_fix:
                    self._kf_lat.set(lat)
                    self._kf_lon.set(lon)
                    self._first_fix = False

                self.lat = self._kf_lat.update(lat)
                self.lon = self._kf_lon.update(lon)

            self.valid = True
            self.last_fix_ms = time.ticks_ms()
            self.state = STATE_FIX_OK

        except Exception as e:
            print("GPS RMC parse hiba:", e)

    def _parse_gga(self, line):
        """
        $GPGGA,...,fix_quality,...,sats,...
        parts[6]: fix quality (0=none, 1=gps, 2=dgps)
        parts[7]: műholdak száma
        """
        parts = line.split(',')
        if len(parts) < 8:
            return
        try:
            fix_q = int(parts[6]) if parts[6] else 0
            sats  = int(parts[7]) if parts[7] else 0
            self.sats = sats
            if fix_q == 0:
                self.valid = False
                self.state = STATE_NO_FIX
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Segédfüggvények
    # ------------------------------------------------------------------

    @staticmethod
    def _nmea_to_deg(value_str, direction):
        """
        NMEA DDDMM.MMMM formátumból tizedes fokra vált.
        pl. '4712.3456' N → 47.205760
        """
        if not value_str:
            return 0.0
        dot = value_str.index('.')
        deg = float(value_str[:dot - 2])
        minutes = float(value_str[dot - 2:])
        result = deg + minutes / 60.0
        if direction in ('S', 'W'):
            result = -result
        return result
