# imu.py - BMI270 dőlésszög mérés complementary filterrel
# MotoMeter v0.1 - M5Stack CoreS3
#
# API:
#   lean = LeanSensor()
#   lean.begin()                  → inicializálás, BMI270 ellenőrzés
#   lean.calibrate()              → aktuális pozíció = 0° referencia
#   lean.update()                 → mérés frissítése, hívd 20-50 Hz-en
#   lean.angle                    → aktuális dőlésszög (fok, + = jobb, - = bal)
#   lean.peak_right               → session max jobb dőlés (fok)
#   lean.peak_left                → session max bal dőlés (fok)
#   lean.lateral_g                → oldalirányú G-erő (g × tan(angle))
#   lean.reset_peaks()            → peak hold nullázása
#   lean.is_ready                 → True ha sikeresen inicializálva
#
# Koordinátarendszer (CoreS3 alapértelmezett szerelési irány):
#   Az eszköz vízszintesen, kijelzővel felfelé van felszerelve.
#   Ha más szögben van felszerelve, a calibrate() ezt kezeli.
#
# Complementary filter: θ = α*(θ + gyro*dt) + (1-α)*accel_angle
#   α = 0.98 → gyro 98%, accel korrekció 2%
#   Nagy α: gyors reakció, lassabb drift-korrekció
#   Kis α: stabil, de késleltetett

import math
import time


# Complementary filter gyro súlya (0.95-0.99 között érdemes tartani)
_ALPHA = 0.98


class LeanSensor:
    """
    BMI270 alapú dőlésszög becslés.

    A calibrate() híváskor rögzített gravitációs referencia alapján
    bármilyen szerelési szögnél helyes 0° értéket ad.
    """

    def __init__(self):
        self._angle      = 0.0    # aktuális dőlés (fok)
        self._peak_right = 0.0    # session max jobb dőlés
        self._peak_left  = 0.0    # session max bal dőlés
        self._last_ts    = None

        # Kalibrált nulla referencia (gravitációs vektor komponensei)
        # ax = roll tengely (oldalirányú dőlés), az = vertikális
        self._ref_ax = 0.0
        self._ref_az = 1.0

        self._ready = False

    # ------------------------------------------------------------------
    # Inicializálás
    # ------------------------------------------------------------------

    def begin(self):
        """
        BMI270 ellenőrzés és alapértelmezett kalibráció.
        Hívd egyszer, M5.begin() után.
        """
        try:
            import M5
            imu_type = M5.Imu.getType()
            print("IMU: típus =", imu_type)
            self._ready = True
        except Exception as e:
            print("IMU: inicializálás hiba —", e)
            self._ready = False
            return

        # API teszt: printeljük, mit kapunk a szenzortól
        ax, ay, az = self._read_accel()
        gx, gy, gz = self._read_gyro()
        print("IMU accel teszt: ax={} ay={} az={}".format(ax, ay, az))
        print("IMU gyro teszt:  gx={} gy={} gz={}".format(gx, gy, gz))

        self._do_calibrate()
        print("IMU: kész, alap kalibráció OK")

    # ------------------------------------------------------------------
    # Kalibráció
    # ------------------------------------------------------------------

    def calibrate(self):
        """
        Motor egyenesen áll → aktuális gravitációs irány = 0° referencia.
        Átlagol 20 mintát (~400ms) a zajcsökkentésért.
        """
        if not self._ready:
            return False

        samples = 20
        sum_ax, sum_az = 0.0, 0.0
        ok = 0

        for _ in range(samples):
            ax, ay, az = self._read_accel()
            if ax is not None:
                sum_ax += ax
                sum_az += az
                ok += 1
            time.sleep_ms(20)

        if ok < 5:
            print("IMU kalibráció: nem elég minta")
            return False

        self._ref_ax = sum_ax / ok
        self._ref_az = sum_az / ok
        self._angle  = 0.0
        self._last_ts = None
        print("IMU kalibráció: ref_ax={:.4f} ref_az={:.4f}".format(
            self._ref_ax, self._ref_az))
        return True

    def _do_calibrate(self):
        """Belső: egyetlen mintás gyors kalibráció bootkor."""
        ax, ay, az = self._read_accel()
        if ax is not None:
            self._ref_ax = ax
            self._ref_az = az if az != 0.0 else 1.0

    # ------------------------------------------------------------------
    # Mérés frissítése
    # ------------------------------------------------------------------

    def update(self):
        """
        Complementary filter léptetése.
        Hívd 20-50 Hz-en (imu_task-ból).
        """
        if not self._ready:
            return

        now = time.ticks_ms()

        ax, ay, az = self._read_accel()
        gx, gy, gz = self._read_gyro()

        if ax is None or gx is None:
            self._last_ts = now
            return

        # dt számítás
        if self._last_ts is None:
            self._last_ts = now
            return
        dt = time.ticks_diff(now, self._last_ts) / 1000.0
        self._last_ts = now

        if dt <= 0.0 or dt > 0.5:
            return

        # ── Accel alapú dőlésszög (kalibrált referenciához képest) ──────
        # ax = roll tengely: ez változik oldalirányú dőlésnél (CoreS3 screen-up)
        ax_rel = ax - self._ref_ax
        az_ref = self._ref_az
        angle_accel = math.degrees(math.atan2(ax_rel, az_ref))

        # ── Gyro alapú integráció (roll tengely = gy, negált előjel) ─────
        # gy előjele fordított a CoreS3-on az ax alapú dőlésirányhoz képest
        angle_gyro = self._angle - gy * dt

        # ── Complementary filter ─────────────────────────────────────────
        self._angle = _ALPHA * angle_gyro + (1.0 - _ALPHA) * angle_accel

        # ── Peak hold frissítése ─────────────────────────────────────────
        # Pozitív szög = bal dőlés, negatív = jobb dőlés
        if self._angle > self._peak_left:
            self._peak_left = self._angle
        if -self._angle > self._peak_right:
            self._peak_right = -self._angle

    # ------------------------------------------------------------------
    # Szenzor olvasás (M5Unified IMU API)
    # ------------------------------------------------------------------

    def _read_accel(self):
        """Visszaad: (ax, ay, az) g-ben, vagy (None, None, None) hiba esetén."""
        try:
            import M5
            data = M5.Imu.getAccel()
            return float(data[0]), float(data[1]), float(data[2])
        except Exception:
            return None, None, None

    def _read_gyro(self):
        """Visszaad: (gx, gy, gz) fok/sec-ben, vagy (None, None, None) hiba esetén."""
        try:
            import M5
            data = M5.Imu.getGyro()
            return float(data[0]), float(data[1]), float(data[2])
        except Exception:
            return None, None, None

    # ------------------------------------------------------------------
    # Publikus adatok
    # ------------------------------------------------------------------

    @property
    def angle(self):
        """Aktuális dőlésszög fokban. Pozitív = jobb, negatív = bal."""
        return self._angle

    @property
    def peak_right(self):
        """Session legtöbb jobb dőlés (fok, mindig pozitív)."""
        return self._peak_right

    @property
    def peak_left(self):
        """Session legtöbb bal dőlés (fok, mindig pozitív)."""
        return self._peak_left

    @property
    def lateral_g(self):
        """
        Oldalirányú G-erő (g).
        Kiegyensúlyozott kanyarban: lateral_g = g × tan(lean_angle)
        """
        try:
            return math.tan(math.radians(self._angle))
        except Exception:
            return 0.0

    @property
    def is_ready(self):
        return self._ready

    def reset_peaks(self):
        """Peak hold nullázása (pl. hosszú érintésre)."""
        self._peak_right = 0.0
        self._peak_left  = 0.0
        print("IMU: peak hold nullázva")
