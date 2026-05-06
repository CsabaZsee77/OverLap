# logger.py - Offline session log (flash / SD kártyára)
# MotoMeter v0.1 - M5Stack CoreS3
#
# Feladat:
#   - Minden kör adatait azonnal elmenti (áramkimaradás-biztos)
#   - Az uplink.py a mentett fájlokat olvassa be és tölti fel
#   - Sikeres feltöltés után a fájl törlésre kerül
#
# Fájlrendszer stratégia:
#   /sd/overlap_logs/  → elsődleges (SD kártya)
#   /flash/mm_logs/      → fallback (belső flash, ~500 KB szabad)
#
# Egy session = egy JSON fájl:
#   session_<device_id>_<epoch_ms>.json
#
# JSON struktúra (egyezik a backend SessionUpload sémájával):
#   {
#     "device_id":  "mm_abc123",
#     "track_id":   1,
#     "rider_name": "",
#     "started_at": "2026-04-24T10:30:00+00:00",
#     "conditions": {},
#     "laps": [
#       {
#         "lap_number":      1,
#         "lap_time_ms":     63400,
#         "lap_start_ts":    1000,
#         "lap_end_ts":      64400,
#         "sector_times_ms": [10200, 12100, 11500],
#         "gps_trace":       [{"lat":47.0,"lon":19.0,"speed_kmh":80.0,"ts_ms":1000}, ...]
#       }
#     ],
#     "_uploaded": false   ← belső flag
#   }

import json
import os
import time


# Log könyvtárak (prioritás sorrendben)
_LOG_DIRS = ['/sd/overlap_logs', '/flash/mm_logs']
# Max trace pont / kör (memóriavédelem: ~5 KB/kör 10 Hz-en)
MAX_TRACE_POINTS = 600


class SessionLogger:
    """
    Offline session és lap logger.

    Publikus API:
        start_session(device_id, track_id, rider_name, started_at)
        add_lap(lap_number, lap_time_ms, lap_start_ts, lap_end_ts,
                sector_times_ms, gps_trace)
        close_session()
        get_pending_files()  → [path, ...]
        mark_uploaded(path)
    """

    def __init__(self, sd_available=False):
        self._sd_available = sd_available
        self._log_dir      = self._find_log_dir()
        self._session_data = None
        self._session_path = None
        print("Logger: log könyvtár →", self._log_dir or "NINCS (log letiltva)")

    # ------------------------------------------------------------------
    # Session életciklus
    # ------------------------------------------------------------------

    def start_session(self, device_id, track_id, rider_name='', started_at=''):
        """Új session indítása."""
        ts = time.ticks_ms()
        self._session_data = {
            'device_id':  device_id,
            'track_id':   track_id,
            'rider_name': rider_name,
            'started_at': started_at or _iso_now(),
            'conditions': {},
            'laps':       [],
            '_uploaded':  False,
            '_ts':        ts,
        }
        fname = 'session_{}_{}.json'.format(
            device_id.replace('/', '_'), ts)
        self._session_path = '{}/{}'.format(self._log_dir, fname) if self._log_dir else None
        print("Logger: session kezdve ({})".format(fname))

    def add_lap(self, lap_number, lap_time_ms,
                lap_start_ts=None, lap_end_ts=None,
                sector_times_ms=None, gps_trace=None,
                max_speed_kmh=None,
                max_lean_right=None, max_lean_left=None,
                peak_kamm_g=None, peak_kamm_angle=None):
        """
        Kör hozzáadása és azonnali flush a fájlba.
        gps_trace: list of (lat, lon, speed_kmh, ts_ms) tuple-ök
        """
        if self._session_data is None:
            print("Logger: WARN — add_lap() session nélkül")
            return

        # GPS trace konverzió + csonkítás
        trace_dicts = []
        if gps_trace:
            for pt in gps_trace[-MAX_TRACE_POINTS:]:
                if isinstance(pt, dict):
                    trace_dicts.append(pt)
                else:
                    lat, lon, spd, ts = pt
                    trace_dicts.append({
                        'lat': lat, 'lon': lon,
                        'speed_kmh': round(spd, 1),
                        'ts_ms': ts
                    })

        lap = {
            'lap_number':       lap_number,
            'lap_time_ms':      lap_time_ms,
            'lap_start_ts':     lap_start_ts,
            'lap_end_ts':       lap_end_ts,
            'sector_times_ms':  sector_times_ms or [],
            'gps_trace':        trace_dicts,
            'max_speed_kmh':    round(max_speed_kmh, 1) if max_speed_kmh else None,
            'max_lean_right':   round(max_lean_right, 1) if max_lean_right else None,
            'max_lean_left':    round(max_lean_left, 1) if max_lean_left else None,
            'peak_kamm_g':      round(peak_kamm_g, 3) if peak_kamm_g else None,
            'peak_kamm_angle':  round(peak_kamm_angle, 1) if peak_kamm_angle else None,
        }
        self._session_data['laps'].append(lap)
        self._flush()
        print("Logger: kör #{} mentve ({} trace pont)".format(
            lap_number, len(trace_dicts)))

    def close_session(self):
        """Session lezárása — utolsó flush."""
        if self._session_data:
            self._flush()
            print("Logger: session lezárva →", self._session_path)
        self._session_data = None
        self._session_path = None

    # ------------------------------------------------------------------
    # Feltöltés kezelés
    # ------------------------------------------------------------------

    def get_pending_files(self):
        """
        Visszaadja az összes mentett, még nem feltöltött session fájlt.
        Returns: [path, ...]
        """
        if not self._log_dir:
            return []
        try:
            files = []
            for fname in os.listdir(self._log_dir):
                if not fname.endswith('.json'):
                    continue
                path = '{}/{}'.format(self._log_dir, fname)
                # Gyors ellenőrzés: feltöltve volt-e már
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                    if not data.get('_uploaded', False):
                        files.append(path)
                except Exception:
                    pass
            return files
        except Exception as e:
            print("Logger: pending scan hiba →", e)
            return []

    def mark_uploaded(self, path):
        """Feltöltött fájl törlése."""
        try:
            os.remove(path)
            print("Logger: törölve (feltöltve) →", path)
        except Exception as e:
            print("Logger: törlési hiba ({}) →".format(path), e)

    def mark_session_uploaded(self):
        """
        Az aktív session _uploaded=True flaggel jelöli a fájlban.
        Így bootkor a flush_pending nem küldi fel újra.
        """
        if self._session_data is None or self._session_path is None:
            return
        self._session_data['_uploaded'] = True
        self._flush()

    def load_session(self, path):
        """
        Egy mentett session betöltése dict-ként (uplink.py-nak).
        Returns: dict | None
        """
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print("Logger: betöltési hiba ({}) →".format(path), e)
            return None

    # ------------------------------------------------------------------
    # Belső segédek
    # ------------------------------------------------------------------

    def _flush(self):
        """Aktuális session adatok kiírása fájlba."""
        if not self._session_path or not self._session_data:
            return
        try:
            with open(self._session_path, 'w') as f:
                json.dump(self._session_data, f)
        except Exception as e:
            print("Logger: flush hiba →", e)

    def _find_log_dir(self):
        """Megkeresi az első elérhető log könyvtárat."""
        for d in _LOG_DIRS:
            parent = d.rsplit('/', 1)[0] or '/'
            try:
                os.listdir(parent)   # szülő létezik-e?
                try:
                    os.mkdir(d)
                except OSError:
                    pass             # már létezik
                os.listdir(d)
                return d
            except OSError:
                continue
        return None


# ------------------------------------------------------------------
# Segéd: ISO timestamp flash nélkül is
# ------------------------------------------------------------------

def _iso_now():
    """Egyszerű fallback ISO timestamp, ha nincs RTC."""
    try:
        import machine
        rtc = machine.RTC()
        dt = rtc.datetime()
        # dt = (year, month, day, weekday, hour, min, sec, subsec)
        return '{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}+00:00'.format(
            dt[0], dt[1], dt[2], dt[4], dt[5], dt[6])
    except Exception:
        return '1970-01-01T00:00:00+00:00'
