# lap.py - Köridő / szakaszidő detektálás és mérés
# MotoMeter v0.1 - M5Stack CoreS3
#
# Két üzemmód:
#   MODE_CIRCUIT — zárt körpálya, a rajt/cél vonal azonos (default)
#   MODE_STAGE   — útszakasz, külön startvonal és célvonal
#                  Pl. hillclimb, gyorsulási mérés, útszakasz-időmérő
#
# Algoritmus: 2D szegmens-metszés (CCW teszt)
# Referencia: M01 L2 dokumentáció

import time


# Köridő / szakaszidő validitási határok (ms)
MIN_LAP_MS = 10_000    # 10 s  — kizárja a téves/visszafordulós detektálást
MAX_LAP_MS = 600_000   # 10 min — kizárja a GPS kiesés utáni hamis detektálást

# Üzemmódok
MODE_CIRCUIT = 'circuit'   # start = finish vonal
MODE_STAGE   = 'stage'     # külön start és finish vonal

# Állapotok
STATE_NO_LINE    = 'no_line'     # nincs definiált vonal
STATE_WAITING    = 'waiting'     # vár az (első) startvonal-átlépésre
STATE_IN_LAP     = 'in_lap'      # mérés folyamatban


class LapResult:
    """Egy rögzített kör / szakasz eredménye."""
    __slots__ = ('lap_time_ms', 'is_best', 'delta_ms', 'lap_number', 'cross_ts_ms')

    def __init__(self, lap_time_ms, is_best, delta_ms, lap_number, cross_ts_ms):
        self.lap_time_ms  = lap_time_ms
        self.is_best      = is_best
        self.delta_ms     = delta_ms      # negatív = gyorsabb a best lapnál
        self.lap_number   = lap_number
        self.cross_ts_ms  = cross_ts_ms   # UTC-helyett ticks_ms alapú


class LapDetector:
    """
    Virtuális vonal alapú köridő / szakaszidő mérő.

    CIRCUIT mód (default):
        - Egyetlen finish_line.
        - Outlap: az első átlépés indítja a mérést.
        - Minden következő átlépés rögzít egy kört.

    STAGE mód:
        - Külön start_line és finish_line.
        - start_line átlépése indítja a mérést.
        - finish_line átlépése rögzíti az időt, majd visszavár a start_line-ra.
        - Pl. hillclimb: megáll a célban, visszahajtás → újra start_line.

    Publikus API:
        set_mode(mode)
        set_finish_line(lat1, lon1, lat2, lon2)
        set_start_line(lat1, lon1, lat2, lon2)   — csak stage módban
        update(lat, lon, ts_ms, speed_kmh) → LapResult | None
        get_best_lap_ms()  → int | None
        get_lap_count()    → int
        get_state()        → str
        reset()
    """

    def __init__(self):
        self.mode  = MODE_CIRCUIT
        self.state = STATE_NO_LINE

        # Célvonal (circuit = ezt várja mindkét irányban, stage = ezt várja mérés alatt)
        self._fl_lat1 = 0.0
        self._fl_lon1 = 0.0
        self._fl_lat2 = 0.0
        self._fl_lon2 = 0.0
        self._has_finish = False

        # Startvonal (csak stage módban)
        self._sl_lat1 = 0.0
        self._sl_lon1 = 0.0
        self._sl_lat2 = 0.0
        self._sl_lon2 = 0.0
        self._has_start = False

        # Előző GPS pont
        self._prev_lat   = None
        self._prev_lon   = None
        self._prev_ts_ms = None

        # Statisztikák
        self._best_lap_ms   = None
        self._lap_count     = 0
        self._last_cross_ms = None   # utolsó érvényes start-átlépés ticks_ms-ben

        # GPS trace az aktuális körhöz (M04-nek)
        self.current_trace = []

    # ------------------------------------------------------------------
    # Konfiguráció
    # ------------------------------------------------------------------

    def set_mode(self, mode):
        """MODE_CIRCUIT vagy MODE_STAGE."""
        assert mode in (MODE_CIRCUIT, MODE_STAGE), "Ismeretlen mód: {}".format(mode)
        self.mode = mode
        self._update_state()
        print("LapDetector: mód → {}".format(mode))

    def set_finish_line(self, lat1, lon1, lat2, lon2):
        """Célvonal beállítása (circuit: start = cél; stage: csak cél)."""
        self._fl_lat1 = lat1;  self._fl_lon1 = lon1
        self._fl_lat2 = lat2;  self._fl_lon2 = lon2
        self._has_finish = True
        self._update_state()
        print("LapDetector: célvonal → ({:.6f},{:.6f})–({:.6f},{:.6f})".format(
            lat1, lon1, lat2, lon2))

    def set_start_line(self, lat1, lon1, lat2, lon2):
        """
        Startvonal beállítása (csak stage módban releváns).
        Circuit módban figyelmen kívül hagyható — a finish_line egyszerre start és cél.
        """
        self._sl_lat1 = lat1;  self._sl_lon1 = lon1
        self._sl_lat2 = lat2;  self._sl_lon2 = lon2
        self._has_start = True
        self._update_state()
        print("LapDetector: startvonal → ({:.6f},{:.6f})–({:.6f},{:.6f})".format(
            lat1, lon1, lat2, lon2))

    def has_finish_line(self):
        return self._has_finish

    # ------------------------------------------------------------------
    # Fő update ciklus
    # ------------------------------------------------------------------

    def update(self, lat, lon, ts_ms, speed_kmh=0.0):
        """
        GPS pont feldolgozása.

        Args:
            lat, lon   : szűrt GPS pozíció (fok)
            ts_ms      : ticks_ms időbélyeg
            speed_kmh  : aktuális sebesség (trace-hez)

        Returns:
            LapResult ha kör / szakasz zárult, egyébként None.
        """
        self.current_trace.append((lat, lon, speed_kmh, ts_ms))

        if self.state == STATE_NO_LINE or self._prev_lat is None:
            self._update_prev(lat, lon, ts_ms)
            return None

        result = None

        if self.mode == MODE_CIRCUIT:
            result = self._update_circuit(lat, lon, ts_ms)
        else:
            result = self._update_stage(lat, lon, ts_ms)

        self._update_prev(lat, lon, ts_ms)
        return result

    # ------------------------------------------------------------------
    # Circuit mód belső logika
    # ------------------------------------------------------------------

    def _update_circuit(self, lat, lon, ts_ms):
        crossed = self._crosses_finish(lat, lon)
        if not crossed:
            return None

        t_cross = self._interpolate_cross_time(
            self._prev_lat, self._prev_lon, self._prev_ts_ms,
            lat, lon, ts_ms,
            self._fl_lat1, self._fl_lon1, self._fl_lat2, self._fl_lon2
        )

        if self.state == STATE_WAITING:
            # Outlap vége — mérés indul
            self._last_cross_ms = t_cross
            self.state = STATE_IN_LAP
            self.current_trace = []
            print("LapDetector: outlap kész, mérés indul")
            return None

        if self.state == STATE_IN_LAP:
            elapsed = time.ticks_diff(t_cross, self._last_cross_ms)
            if MIN_LAP_MS <= elapsed <= MAX_LAP_MS:
                return self._record_lap(elapsed, t_cross)
            else:
                print("LapDetector: kör kihagyva ({}ms)".format(elapsed))
                return None

    # ------------------------------------------------------------------
    # Stage mód belső logika
    # ------------------------------------------------------------------

    def _update_stage(self, lat, lon, ts_ms):
        if self.state == STATE_WAITING:
            # Startvonalon kell átmenni
            crossed_start = self._crosses_start(lat, lon)
            if not crossed_start:
                return None

            t_cross = self._interpolate_cross_time(
                self._prev_lat, self._prev_lon, self._prev_ts_ms,
                lat, lon, ts_ms,
                self._sl_lat1, self._sl_lon1, self._sl_lat2, self._sl_lon2
            )
            self._last_cross_ms = t_cross
            self.state = STATE_IN_LAP
            self.current_trace = []
            print("LapDetector [stage]: startvonal átlépve, mérés indul")
            return None

        if self.state == STATE_IN_LAP:
            # Célvonalon kell átmenni
            crossed_finish = self._crosses_finish(lat, lon)
            if not crossed_finish:
                return None

            t_cross = self._interpolate_cross_time(
                self._prev_lat, self._prev_lon, self._prev_ts_ms,
                lat, lon, ts_ms,
                self._fl_lat1, self._fl_lon1, self._fl_lat2, self._fl_lon2
            )
            elapsed = time.ticks_diff(t_cross, self._last_cross_ms)

            if MIN_LAP_MS <= elapsed <= MAX_LAP_MS:
                result = self._record_lap(elapsed, t_cross)
                # Stage: visszaáll WAITING-ba (következő futamra vár)
                self.state = STATE_WAITING
                return result
            else:
                print("LapDetector [stage]: szakasz kihagyva ({}ms)".format(elapsed))
                self.state = STATE_WAITING
                return None

    # ------------------------------------------------------------------
    # Segédmetódusok
    # ------------------------------------------------------------------

    def _crosses_finish(self, lat, lon):
        return self._segments_intersect(
            self._prev_lat, self._prev_lon, lat, lon,
            self._fl_lat1, self._fl_lon1, self._fl_lat2, self._fl_lon2
        )

    def _crosses_start(self, lat, lon):
        return self._segments_intersect(
            self._prev_lat, self._prev_lon, lat, lon,
            self._sl_lat1, self._sl_lon1, self._sl_lat2, self._sl_lon2
        )

    def _update_state(self):
        """Állapot frissítése konfiguráció változáskor."""
        if self.mode == MODE_CIRCUIT:
            self.state = STATE_WAITING if self._has_finish else STATE_NO_LINE
        else:  # stage
            needs_both = self._has_finish and self._has_start
            self.state = STATE_WAITING if needs_both else STATE_NO_LINE

    # ------------------------------------------------------------------
    # Statisztikák
    # ------------------------------------------------------------------

    def get_best_lap_ms(self):
        return self._best_lap_ms

    def get_lap_count(self):
        return self._lap_count

    def get_state(self):
        return self.state

    def reset(self):
        """Teljes reset (új session), vonalak megmaradnak."""
        self._update_state()   # visszaállítja az állapotot a konfiguráció alapján
        self._prev_lat        = None
        self._prev_lon        = None
        self._prev_ts_ms      = None
        self._best_lap_ms     = None
        self._lap_count       = 0
        self._last_cross_ms   = None
        self.current_trace    = []

    # ------------------------------------------------------------------
    # Belső rögzítés
    # ------------------------------------------------------------------

    def _record_lap(self, elapsed_ms, t_cross):
        self._lap_count += 1
        is_best  = (self._best_lap_ms is None) or (elapsed_ms < self._best_lap_ms)
        delta_ms = 0 if self._best_lap_ms is None else (elapsed_ms - self._best_lap_ms)

        if is_best:
            self._best_lap_ms = elapsed_ms

        self._last_cross_ms = t_cross
        self.current_trace  = []

        label = "[stage]" if self.mode == MODE_STAGE else ""
        print("LapDetector{}: #{} → {:.3f}s {}".format(
            label,
            self._lap_count,
            elapsed_ms / 1000.0,
            "★ BEST" if is_best else "(+{:.3f}s)".format(delta_ms / 1000.0)
        ))
        return LapResult(
            lap_time_ms = elapsed_ms,
            is_best     = is_best,
            delta_ms    = delta_ms,
            lap_number  = self._lap_count,
            cross_ts_ms = t_cross
        )

    def _update_prev(self, lat, lon, ts_ms):
        self._prev_lat   = lat
        self._prev_lon   = lon
        self._prev_ts_ms = ts_ms

    # ------------------------------------------------------------------
    # Geometria: 2D szegmens-metszés (CCW teszt)
    # ------------------------------------------------------------------

    @staticmethod
    def _direction(ax, ay, bx, by, cx, cy):
        """Cross product előjele: (B-A) × (C-A)"""
        return (cx - ax) * (by - ay) - (bx - ax) * (cy - ay)

    @classmethod
    def _segments_intersect(cls, p1x, p1y, p2x, p2y, l1x, l1y, l2x, l2y):
        """Igaz ha a P1→P2 szegmens metszi az L1→L2 szegmenst."""
        d1 = cls._direction(l1x, l1y, l2x, l2y, p1x, p1y)
        d2 = cls._direction(l1x, l1y, l2x, l2y, p2x, p2y)
        d3 = cls._direction(p1x, p1y, p2x, p2y, l1x, l1y)
        d4 = cls._direction(p1x, p1y, p2x, p2y, l2x, l2y)

        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
           ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
            return True
        return False

    @classmethod
    def _interpolate_cross_time(cls, p1x, p1y, t1, p2x, p2y, t2,
                                l1x, l1y, l2x, l2y):
        """
        Interpolált átlépési időbélyeg (ticks_ms).
        A metszési pont arányát a P1→P2 szakaszon becsüljük a direction értékek alapján.
        """
        d1 = abs(cls._direction(l1x, l1y, l2x, l2y, p1x, p1y))
        d2 = abs(cls._direction(l1x, l1y, l2x, l2y, p2x, p2y))
        total = d1 + d2
        ratio = d1 / total if total != 0 else 0.5
        return int(t1 + ratio * time.ticks_diff(t2, t1))
