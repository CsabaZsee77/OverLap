# sector.py - Szektor időmérés és best sector tracking
# MotoMeter v0.1 - M5Stack CoreS3
#
# Feladat:
#   - TrackConfig.sectors lista alapján GPS vonalmetszés detektálás
#   - Szektoronkénti időmérés (szektor belépés → következő szektor belépés)
#   - Best sector idők megőrzése session-on belül
#   - Aktuális szektor index biztosítása a delta.py-nak
#
# Integráció:
#   - sector_det.update(lat, lon, ts_ms) → SectorResult | None
#   - sector_det.reset()                → körváltáskor (lap.py hívja)
#   - sector_det.get_best_times()       → dict {name: best_ms}
#   - sector_det.current_sector_idx     → int (delta.py-nak)
#   - sector_det.current_sector_elapsed → int ms (eltelt idő az aktuális szektorban)
#
# Megjegyzés: a szektorvonalakat ugyanaz a CCW-metszés algoritmus detektálja,
# mint a rajtvonalat (lap.py). A SectorDetector importálja a metszésfüggvényeket.

import time


class SectorResult:
    """Egy rögzített szektor eredménye."""
    __slots__ = ('name', 'sector_idx', 'time_ms', 'is_best', 'delta_ms')

    def __init__(self, name, sector_idx, time_ms, is_best, delta_ms):
        self.name        = name        # "S1", "S2", ...
        self.sector_idx  = sector_idx  # 0-alapú index
        self.time_ms     = time_ms
        self.is_best     = is_best
        self.delta_ms    = delta_ms    # vs own best (negatív = gyorsabb)


class SectorDetector:
    """
    Szektor időmérő és best sector tracker.

    Szektorsorrend: a TrackConfig.sectors listájának sorrendje.
    Egy körhöz tartozó szektorok egymás után detektálandók —
    a 3. szektor csak akkor érvényes, ha az 1. és 2. már megvolt.

    Publikus API:
        set_sectors(lines)             → TrackLine lista betöltése
        update(lat, lon, ts_ms)        → SectorResult | None
        reset()                        → körváltás, aktuális szektoridők nullázása
        get_best_times()               → {name: best_ms, ...}
        current_sector_idx             → aktuális szektor index (0-alapú)
        current_sector_elapsed(ts_ms)  → ms eltelt az aktuális szektorban
    """

    def __init__(self):
        self._lines      = []     # TrackLine lista (szektorvonalak sorrendben)
        self._best_ms    = {}     # {name: best_ms}
        self._sector_start_ms = None
        self._current_idx     = 0
        self._prev_lat   = None
        self._prev_lon   = None
        self._prev_ts_ms = None
        self._active     = False  # False ha nincs szektor, vagy kör nem indult

    # ------------------------------------------------------------------
    # Konfiguráció
    # ------------------------------------------------------------------

    def set_sectors(self, lines):
        """
        Szektorvonalak betöltése.
        lines: TrackLine objektumok listája (track_cfg.sectors)
        """
        self._lines = lines if lines else []
        self._best_ms = {ln.name: None for ln in self._lines}
        self._current_idx = 0
        self._sector_start_ms = None
        self._active = False
        if self._lines:
            print("SectorDetector: {} szektor betöltve: {}".format(
                len(self._lines), [l.name for l in self._lines]))

    def has_sectors(self):
        return len(self._lines) > 0

    # ------------------------------------------------------------------
    # Kör kezdete (lap.py STATE_IN_LAP esetén)
    # ------------------------------------------------------------------

    def start_lap(self, ts_ms):
        """
        Köridőmérés indul — szektordetektor reset és aktiválás.
        Hívja a main.py, amikor a LapDetector STATE_WAITING → STATE_IN_LAP vált.
        """
        self._current_idx = 0
        self._sector_start_ms = ts_ms
        self._prev_lat   = None
        self._prev_lon   = None
        self._active     = len(self._lines) > 0
        print("SectorDetector: kör indult (ts={})".format(ts_ms))

    def reset(self):
        """Körváltáskor: az aktuális szektoridők nullázása, best értékek megmaradnak."""
        self._current_idx = 0
        self._sector_start_ms = None
        self._prev_lat   = None
        self._prev_lon   = None
        self._active     = False

    # ------------------------------------------------------------------
    # Fő update ciklus
    # ------------------------------------------------------------------

    def update(self, lat, lon, ts_ms):
        """
        GPS pont feldolgozása.
        Returns: SectorResult ha szektor zárul, egyébként None.
        """
        if not self._active or not self._lines:
            self._prev_lat, self._prev_lon, self._prev_ts_ms = lat, lon, ts_ms
            return None

        if self._prev_lat is None:
            self._prev_lat, self._prev_lon, self._prev_ts_ms = lat, lon, ts_ms
            return None

        # Várakozás a soron következő szektorvonalra
        target = self._lines[self._current_idx]
        crossed = _segments_intersect(
            self._prev_lat, self._prev_lon, lat, lon,
            target.lat1, target.lon1, target.lat2, target.lon2
        )

        result = None
        if crossed:
            t_cross = _interpolate_cross_time(
                self._prev_lat, self._prev_lon, self._prev_ts_ms,
                lat, lon, ts_ms,
                target.lat1, target.lon1, target.lat2, target.lon2
            )
            elapsed = time.ticks_diff(t_cross, self._sector_start_ms)

            # Best update
            prev_best = self._best_ms.get(target.name)
            is_best   = (prev_best is None) or (elapsed < prev_best)
            delta_ms  = 0 if prev_best is None else (elapsed - prev_best)

            if is_best:
                self._best_ms[target.name] = elapsed

            result = SectorResult(
                name        = target.name,
                sector_idx  = self._current_idx,
                time_ms     = elapsed,
                is_best     = is_best,
                delta_ms    = delta_ms,
            )
            print("Szektor {}: {:.3f}s {}".format(
                target.name,
                elapsed / 1000.0,
                "★" if is_best else "(+{:.3f}s)".format(delta_ms / 1000.0)
            ))

            # Következő szektorra lép
            self._sector_start_ms = t_cross
            self._current_idx = (self._current_idx + 1) % len(self._lines)

        self._prev_lat, self._prev_lon, self._prev_ts_ms = lat, lon, ts_ms
        return result

    # ------------------------------------------------------------------
    # Lekérdezések a delta.py-nak
    # ------------------------------------------------------------------

    @property
    def current_sector_idx(self):
        """Soron következő szektor indexe (0-alapú)."""
        return self._current_idx

    def current_sector_elapsed(self, ts_ms):
        """Ms eltelt az aktuális szektor kezdete óta."""
        if self._sector_start_ms is None:
            return 0
        return max(0, time.ticks_diff(ts_ms, self._sector_start_ms))

    def get_best_times(self):
        """Visszaadja a best szektoridőket: {name: ms | None}."""
        return dict(self._best_ms)

    def get_best_times_list(self):
        """Best szektoridők sorban, None ha még nincs: [ms, ms, None, ...]"""
        return [self._best_ms.get(ln.name) for ln in self._lines]

    def sectors_done_in_lap(self):
        """Hány szektor lett teljesítve az aktuális körben."""
        return self._current_idx  # mert a current_idx az _épp következő_ szektorra mutat


# ------------------------------------------------------------------
# Geometria segédfüggvények (lap.py-ból átmásolva, hogy nincs import-függőség)
# ------------------------------------------------------------------

def _direction(ax, ay, bx, by, cx, cy):
    return (cx - ax) * (by - ay) - (bx - ax) * (cy - ay)


def _segments_intersect(p1x, p1y, p2x, p2y, l1x, l1y, l2x, l2y):
    d1 = _direction(l1x, l1y, l2x, l2y, p1x, p1y)
    d2 = _direction(l1x, l1y, l2x, l2y, p2x, p2y)
    d3 = _direction(p1x, p1y, p2x, p2y, l1x, l1y)
    d4 = _direction(p1x, p1y, p2x, p2y, l2x, l2y)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


def _interpolate_cross_time(p1x, p1y, t1, p2x, p2y, t2, l1x, l1y, l2x, l2y):
    d1    = abs(_direction(l1x, l1y, l2x, l2y, p1x, p1y))
    d2    = abs(_direction(l1x, l1y, l2x, l2y, p2x, p2y))
    total = d1 + d2
    ratio = d1 / total if total != 0 else 0.5
    return int(t1 + ratio * time.ticks_diff(t2, t1))
