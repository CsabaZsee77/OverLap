# imu.py - Dőlésszög mérés complementary filterrel
# MotoMeter v0.1 - M5Stack CoreS3
#
# Két backend, config.IMU_BACKEND alapján választ:
#   'bmi270'  — beépített CoreS3 BMI270 (M5Unified API)
#   'mpu6886' — külső MPU6886 I2C (Grove Port A: SDA=config.IMU_I2C_SDA, SCL=config.IMU_I2C_SCL)
#
# API (mindkét backendnél azonos):
#   lean = LeanSensor()
#   lean.begin()          → inicializálás
#   lean.calibrate()      → aktuális pozíció = 0° referencia (20 minta, ~400ms)
#   lean.update()         → mérés frissítése, hívd 20-50 Hz-en
#   lean.angle            → aktuális dőlésszög (fok, + = bal, - = jobb)
#   lean.peak_right       → session max jobb dőlés (fok, mindig pozitív)
#   lean.peak_left        → session max bal dőlés (fok, mindig pozitív)
#   lean.lateral_g        → oldalirányú G-erő (tan(angle))
#   lean.reset_peaks()    → peak hold nullázása
#   lean.is_ready         → True ha sikeresen inicializálva
#
# MPU6886 szerelési irány (config.IMU_BACKEND = 'mpu6886'):
#   Lapja felfelé néz, Y tengely = haladási irány, X tengely = oldalirány (merőleges motorra)
#   ax = laterális dőlés tengelye (ugyanúgy, mint BMI270-nél)
#   Gyro jel: GYRO_SIGN = -1.0 (ha fordítva reagál, change to +1.0 a driverben)
#
# Complementary filter: θ = α*(θ + sign*gy*dt) + (1-α)*accel_angle
#   α = 0.98 → gyro 98%, accel korrekció 2%

import math
import time


_ALPHA = 0.98


# ══════════════════════════════════════════════════════════════
#  BMI270 driver — belső CoreS3 szenzor (M5Unified)
# ══════════════════════════════════════════════════════════════

class _BMI270Driver:
    """
    Belső CoreS3 BMI270 via M5Unified API.
    Gyro előjele fordított az ax alapú dőlésirányhoz képest → GYRO_SIGN = -1.0
    """
    GYRO_SIGN = -1.0

    def init(self):
        try:
            import M5
            imu_type = M5.Imu.getType()
            print("IMU: BMI270 type =", imu_type)
            ax, ay, az = self.read_accel()
            gx, gy, gz = self.read_gyro()
            print("IMU accel: ax={} ay={} az={}".format(ax, ay, az))
            print("IMU gyro:  gx={} gy={} gz={}".format(gx, gy, gz))
            return True
        except Exception as e:
            print("IMU: BMI270 init hiba —", e)
            return False

    def read_accel(self):
        try:
            import M5
            d = M5.Imu.getAccel()
            return float(d[0]), float(d[1]), float(d[2])
        except Exception:
            return None, None, None

    def read_gyro(self):
        try:
            import M5
            d = M5.Imu.getGyro()
            return float(d[0]), float(d[1]), float(d[2])
        except Exception:
            return None, None, None


# ══════════════════════════════════════════════════════════════
#  MPU6886 driver — külső I2C szenzor (Grove Port A)
# ══════════════════════════════════════════════════════════════

class _MPU6886Driver:
    """
    Külső MPU6886 via I2C (Grove Port A: SDA=config.IMU_I2C_SDA, SCL=config.IMU_I2C_SCL).

    Szerelési irány: lapja felfelé, Y tengely = haladási irány, X tengely = oldalirány.
    Lean axis: ax (laterális, mint BMI270-nél)
    Roll gyro: gy (Y tengely körüli forgás)
    GYRO_SIGN = -1.0 — ha fordítva reagál gyors döntésre, állítsd +1.0-ra config-ban.
    """
    _ADDR           = 0x68
    _REG_WHOAMI     = 0x75
    _REG_PWR        = 0x6B
    _REG_ACCEL_CFG  = 0x1C
    _REG_GYRO_CFG   = 0x1B
    _REG_ACCEL      = 0x3B
    _REG_GYRO       = 0x43
    _WHOAMI_OK      = 0x19   # MPU6886 gyári érték

    # ±8g = 4096 LSB/g, ±500 dps = 65.5 LSB/dps
    _ACCEL_SCALE = 4096.0
    _GYRO_SCALE  = 65.5

    GYRO_SIGN = 1.0

    def __init__(self):
        self._i2c = None

    def init(self):
        try:
            from machine import I2C, Pin
            from overlap import config
            sda_pin = getattr(config, 'IMU_I2C_SDA', 2)
            scl_pin = getattr(config, 'IMU_I2C_SCL', 1)
            self._i2c = I2C(0, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=400000)

            who = self._rb(self._REG_WHOAMI)
            print("IMU: MPU6886 WHO_AM_I = 0x{:02X}".format(who))
            if who != self._WHOAMI_OK:
                # Klónok esetén más értéket adhat — folytatjuk
                print("IMU: WHO_AM_I eltérés (várt 0x19) — folytatás")

            self._wb(self._REG_PWR, 0x00)   # sleep bit törlése
            time.sleep_ms(10)
            self._wb(self._REG_ACCEL_CFG, 0x10)  # ±8g
            self._wb(self._REG_GYRO_CFG,  0x08)  # ±500 dps

            ax, ay, az = self.read_accel()
            gx, gy, gz = self.read_gyro()
            print("IMU accel: ax={} ay={} az={}".format(ax, ay, az))
            print("IMU gyro:  gx={} gy={} gz={}".format(gx, gy, gz))
            print("IMU: MPU6886 init OK")
            return True
        except Exception as e:
            print("IMU: MPU6886 init hiba —", e)
            return False

    def _wb(self, reg, val):
        self._i2c.writeto_mem(self._ADDR, reg, bytes([val]))

    def _rb(self, reg):
        return self._i2c.readfrom_mem(self._ADDR, reg, 1)[0]

    def _read_raw(self, reg):
        """6 bájt = 3 db int16 big-endian."""
        buf = self._i2c.readfrom_mem(self._ADDR, reg, 6)
        vals = []
        for i in range(0, 6, 2):
            v = (buf[i] << 8) | buf[i + 1]
            if v > 32767:
                v -= 65536
            vals.append(v)
        return vals[0], vals[1], vals[2]

    def read_accel(self):
        try:
            rx, ry, rz = self._read_raw(self._REG_ACCEL)
            return rx / self._ACCEL_SCALE, ry / self._ACCEL_SCALE, rz / self._ACCEL_SCALE
        except Exception:
            return None, None, None

    def read_gyro(self):
        try:
            rx, ry, rz = self._read_raw(self._REG_GYRO)
            return rx / self._GYRO_SCALE, ry / self._GYRO_SCALE, rz / self._GYRO_SCALE
        except Exception:
            return None, None, None


# ══════════════════════════════════════════════════════════════
#  LeanSensor — publikus osztály
# ══════════════════════════════════════════════════════════════

class LeanSensor:
    """
    Dőlésszög becslés complementary filterrel.
    Backend: config.IMU_BACKEND ('bmi270' vagy 'mpu6886').
    """

    def __init__(self):
        self._angle         = 0.0
        self._peak_right    = 0.0
        self._peak_left     = 0.0
        self._last_ts       = None
        self._ref_al        = 0.0   # laterális accel referencia (lean tengely = ay)
        self._ref_az        = 1.0   # vertikális accel referencia
        self._ref_alon      = 0.0   # longitudinális accel referencia (= ax)
        self._gyro_bias_l   = 0.0   # lean tengelyre eső gyro DC offset
        self._lean_sign     = 1.0   # +1.0 vagy -1.0, config.IMU_LEAN_INVERT alapján
        self._lon_g         = 0.0   # aktuális hosszirányú G (+ = gyorsítás, - = fékezés)
        self._yaw_rate      = 0.0   # yaw rate (gz, rad/s) — kanyar szögsebessége
        self._ready         = False
        self._driver        = None

    # ------------------------------------------------------------------
    # Inicializálás
    # ------------------------------------------------------------------

    def begin(self):
        """Backend kiválasztása és inicializálása. Hívd egyszer, M5.begin() után."""
        try:
            from overlap import config
            backend = getattr(config, 'IMU_BACKEND', 'bmi270').lower()
        except Exception:
            backend = 'bmi270'

        if backend == 'mpu6886':
            self._driver = _MPU6886Driver()
            print("IMU: backend = MPU6886 (külső I2C)")
        else:
            self._driver = _BMI270Driver()
            print("IMU: backend = BMI270 (beépített)")

        invert = getattr(config, 'IMU_LEAN_INVERT', False)
        self._lean_sign = -1.0 if invert else 1.0
        print("IMU: lean_sign =", self._lean_sign)

        self._ready = self._driver.init()
        if not self._ready:
            return

        self._do_calibrate()
        print("IMU: kész, alap kalibráció OK")

    # ------------------------------------------------------------------
    # Kalibráció
    # ------------------------------------------------------------------

    def calibrate(self):
        """
        Motor egyenesen áll → aktuális pozíció = 0° referencia.
        Átlagol 20 mintát (~400 ms): accel referencia + gyro bias becslés.
        """
        if not self._ready:
            return False

        samples = 20
        sum_ax = sum_az = sum_gy = 0.0
        ok = 0

        sum_alon = 0.0
        for _ in range(samples):
            ax, ay, az = self._driver.read_accel()
            gx, gy, gz = self._driver.read_gyro()
            if ax is not None and gx is not None:
                sum_ax   += ay   # lean tengely = ay
                sum_az   += az
                sum_gy   += gx   # lean gyro   = gx
                sum_alon += ax   # longitudinális tengely = ax
                ok += 1
            time.sleep_ms(20)

        if ok < 5:
            print("IMU kalibráció: nem elég minta")
            return False

        self._ref_al       = sum_ax  / ok
        self._ref_az       = sum_az  / ok
        self._gyro_bias_l  = sum_gy  / ok
        self._ref_alon     = sum_alon / ok
        self._angle        = 0.0
        self._last_ts      = None
        print("IMU kalibráció: ref_al={:.4f} ref_az={:.4f} gyro_bias_l={:.4f}".format(
            self._ref_al, self._ref_az, self._gyro_bias_l))
        return True

    def _do_calibrate(self):
        """Belső: 10 mintás gyors kalibráció bootkor (accel + gyro bias)."""
        samples = 10
        sum_al = sum_az = sum_gl = sum_alon = 0.0
        ok = 0
        for _ in range(samples):
            ax, ay, az = self._driver.read_accel()
            gx, gy, gz = self._driver.read_gyro()
            if ax is not None and gx is not None:
                sum_al   += ay   # lean tengely = ay
                sum_az   += az
                sum_gl   += gx   # lean gyro   = gx
                sum_alon += ax   # longitudinális = ax
                ok += 1
            time.sleep_ms(10)
        if ok > 0:
            self._ref_al      = sum_al   / ok
            self._ref_az      = (sum_az  / ok) if (sum_az / ok) != 0.0 else 1.0
            self._gyro_bias_l = sum_gl   / ok
            self._ref_alon    = sum_alon / ok

    # ------------------------------------------------------------------
    # Mérés frissítése
    # ------------------------------------------------------------------

    def update(self):
        """Complementary filter léptetése. Hívd 20-50 Hz-en."""
        if not self._ready:
            return

        now = time.ticks_ms()
        ax, ay, az = self._driver.read_accel()
        gx, gy, gz = self._driver.read_gyro()

        if ax is None or gx is None:
            self._last_ts = now
            return

        if self._last_ts is None:
            self._last_ts = now
            return

        dt = time.ticks_diff(now, self._last_ts) / 1000.0
        self._last_ts = now

        if dt <= 0.0 or dt > 0.5:
            return

        # Accel alapú dőlésszög — 2D forgatási formula:
        # atan2(ref_az*a_lean - ref_al*az, ref_al*a_lean + ref_az*az)
        # Lean tengely = ay, vertikális = az.
        # Nullát ad a kalibrált pozícióban, helyes bármilyen ref_az előjelnél.
        # _lean_sign forgatja meg az egész dőlésértelmezést (fordított szerelés esetén).
        ral = self._ref_al
        raz = self._ref_az
        angle_accel = self._lean_sign * math.degrees(math.atan2(
            raz * ay - ral * az,
            ral * ay + raz * az
        ))

        # Gyro integráció — lean gyro = gx, bias levonás + GYRO_SIGN + _lean_sign
        gx_corr    = gx - self._gyro_bias_l
        angle_gyro = self._angle + self._lean_sign * self._driver.GYRO_SIGN * gx_corr * dt

        # Complementary filter
        self._angle = _ALPHA * angle_gyro + (1.0 - _ALPHA) * angle_accel

        # Longitudinális G (+ = gyorsítás, - = fékezés)
        self._lon_g = ax - self._ref_alon

        # Yaw rate (kanyar szögsebesség) — gz, rad/s
        self._yaw_rate = gz

        # Peak hold (pozitív = bal dőlés, negatív = jobb dőlés)
        if self._angle > self._peak_left:
            self._peak_left = self._angle
        if -self._angle > self._peak_right:
            self._peak_right = -self._angle

    # ------------------------------------------------------------------
    # Publikus adatok
    # ------------------------------------------------------------------

    @property
    def angle(self):
        """Aktuális dőlésszög fokban. Pozitív = bal, negatív = jobb."""
        return self._angle

    @property
    def peak_right(self):
        """Session max jobb dőlés (fok, mindig pozitív)."""
        return self._peak_right

    @property
    def peak_left(self):
        """Session max bal dőlés (fok, mindig pozitív)."""
        return self._peak_left

    @property
    def lon_g(self):
        """Hosszirányú G-erő. + = gyorsítás, - = fékezés. (Ha fordítva van, negate config-ban.)"""
        return self._lon_g

    @property
    def lateral_g(self):
        """Oldalirányú G-erő (g). Kiegyensúlyozott kanyarban ≈ tan(lean_angle)."""
        try:
            return math.tan(math.radians(self._angle))
        except Exception:
            return 0.0

    @property
    def yaw_rate(self):
        """Yaw rate (kanyar szögsebesség), rad/s. Pozitív = bal kanyar (CCW felülről)."""
        return self._yaw_rate

    @property
    def is_ready(self):
        return self._ready

    def reset_peaks(self):
        """Peak hold nullázása."""
        self._peak_right = 0.0
        self._peak_left  = 0.0
        print("IMU: peak hold nullázva")
