# delta.py - Prediktált köridő és delta számítás
# MotoMeter v0.1 - M5Stack CoreS3
#
# Algoritmus:
#   predicted_ms = eltelt_idő_a_körben + hátralévő_szektorok_best_összege
#
# Feltétel: legalább egy befejezett kör kell a best sector időkhoz.
# Ha nincs best → predicted = None (a kijelzőn "--" jelenik meg).
#
# Példa (4 szektor, 2. szektornál járunk):
#   eltelt    = 22_100 ms (S1 + S2 tényleges)
#   hátralévő = best_S3 + best_S4 = 11_400 + 9_800 = 21_200 ms
#   predicted = 22_100 + 21_200 = 43_300 ms
#
# Stage mód: ugyanez, de az "összes szektor" a start→finish közöttiek.

import time


class LapPredictor:
    """
    Prediktált köridő számító.

    Publikus API:
        set_sector_count(n)                → szektor darabszám
        update(lap_start_ts, ts_ms,
               sector_idx, sector_times)   → (predicted_ms, delta_ms) | (None, None)
        reset()
    """

    def __init__(self):
        self._sector_count = 0     # szektorszám (set_sector_count-ból jön)

    def set_sector_count(self, n):
        self._sector_count = n

    # ------------------------------------------------------------------
    # Fő számítás
    # ------------------------------------------------------------------

    def predict(self, lap_start_ts, ts_ms, sector_idx, best_sector_list, best_lap_ms):
        """
        Aktuális prediktált köridő számítása.

        Args:
            lap_start_ts     : kör indulásának ts_ms időbélyege
            ts_ms            : jelenlegi időbélyeg
            sector_idx       : következő szektor indexe (0-alapú, sector.py-tól)
                               → ha 0: az első szektornál vagyunk még
                               → ha 2: az S1, S2 már megvolt, S3-ban vagyunk
            best_sector_list : [best_ms | None, ...] szektoronként (sector.py-tól)
            best_lap_ms      : eddigi best lap ms (lap.py-tól), None ha nincs

        Returns:
            (predicted_ms, delta_ms) — mindkettő None ha nincs elég adat
        """
        if not self._sector_count or lap_start_ts is None:
            return None, None

        elapsed = time.ticks_diff(ts_ms, lap_start_ts)

        # Hátralévő szektorok: sector_idx-től a végéig
        # sector_idx = a következő (még nem teljesített) szektor
        remaining_sectors = range(sector_idx, self._sector_count)

        # Ha bármely hátralévő szektorhoz nincs best, nem tudunk prediktálni
        remaining_best = []
        for i in remaining_sectors:
            b = best_sector_list[i] if i < len(best_sector_list) else None
            if b is None:
                return None, None
            remaining_best.append(b)

        predicted_ms = elapsed + sum(remaining_best)

        # Delta: predicted vs best lap
        delta_ms = None
        if best_lap_ms is not None:
            delta_ms = predicted_ms - best_lap_ms

        return predicted_ms, delta_ms

    def reset(self):
        pass   # nincs belső állapot, minden paramétert kívülről kap


# ------------------------------------------------------------------
# Segéd: ms → kijelző szöveg
# ------------------------------------------------------------------

def fmt_predicted(predicted_ms):
    """None → '--:--.---', egyébként '1:02.341' formátum."""
    if predicted_ms is None:
        return '--:--.---'
    ms = int(predicted_ms)
    sign = '-' if ms < 0 else ''
    abs_ms = abs(ms)
    m   = abs_ms // 60_000
    s   = (abs_ms % 60_000) // 1000
    frac = abs_ms % 1000
    return '{}{}:{:02d}.{:03d}'.format(sign, m, s, frac)


def fmt_delta(delta_ms):
    """None → '', egyébként '+1.234' / '-0.456' formátum."""
    if delta_ms is None:
        return ''
    sign = '+' if delta_ms > 0 else ''
    abs_ms = abs(delta_ms)
    sec  = abs_ms // 1000
    frac = abs_ms % 1000
    neg  = '-' if delta_ms < 0 else ''
    return '{}{}{}.{:03d}'.format(sign, neg, sec, frac)
