# kalman.py - Kalman szűrő
# MotoMeter v0.1 - M5Stack CoreS3
#
# Referencia: Kormoran lib_filters.py (tesztelt, működő implementáció)
# MotoMeter módosítás: Q=0.1 (motor: gyors irányváltás, Q>hajó)

class KalmanFilter:
    """
    1D Kalman szűrő pozíció / sebesség simításához.

    Használat:
        kf = KalmanFilter()
        filtered = kf.update(raw_measurement)

    Paraméterek:
        Q = process noise  (mennyit bízunk a modellben)
        R = measurement noise (mennyit bízunk a mérésben)

    MotoMeter ajánlott értékek:
        Pozíció (lat/lon): Q=0.1, R=2.0
        Sebesség (km/h):   Q=0.05, R=1.0
    """

    def __init__(self, Q=0.1, R=2.0):
        self.x = 0.0   # becsült állapot
        self.P = 1.0   # bizonytalanság
        self.Q = Q     # folyamat zaj
        self.R = R     # mérési zaj

    def update(self, measurement):
        """
        Kalman frissítés új méréssel.

        Args:
            measurement: nyers GPS / szenzor érték

        Returns:
            float: szűrt érték
        """
        # Predikciós lépés
        self.P += self.Q

        # Kalman gain
        K = self.P / (self.P + self.R)

        # Állapot frissítés
        self.x = self.x + K * (measurement - self.x)
        self.P = (1 - K) * self.P

        return self.x

    def reset(self, value=0.0):
        """Filter reset (új session kezdetekor)."""
        self.x = value
        self.P = 1.0

    def set(self, value):
        """Kezdőérték beállítása (első GPS fix után érdemes hívni)."""
        self.x = value
        self.P = 1.0
