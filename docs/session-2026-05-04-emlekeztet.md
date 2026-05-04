# OverLap fejlesztési session összefoglaló
**Dátum:** 2026-05-04  
**Branch:** main

---

## Elvégzett módosítások

### 1. Verzió: v1.1 → v1.2
**Fájl:** `firmware/display.py:100`  
A boot képernyőn megjelenő verziószám frissítve.

---

### 2. Rajtvonal-detektálás vizsgálata és javítások

#### A probléma
A rajtvonal GPS-sel való felvétele után több áthaladás után sem érzékelte az átlépést.

#### Hogyan működik az algoritmus

A `firmware/lap.py`-ban a `_segments_intersect` (CCW teszt) két feltételt ellenőriz egyszerre:

1. **d1, d2** – az előző és az aktuális GPS pont a rajtvonal ellentétes oldalán van-e
2. **d3, d4** – a rajtvonal két végpontja (L1, L2) a mozgási szegmens ellentétes oldalán van-e

```
Előző GPS pont (P1) ──────────────► Aktuális GPS pont (P2)
                         │
               ──────────┼──────────   ← 30m-es rajtvonal (L1 ←→ L2)
                         │
                   ← DETEKTÁLÁS (ha a szegmens metszi a vonalat)
```

A vonal nem végtelen egyenes, hanem **véges szegmens** – csak akkor tüzel, ha a tényleges GPS nyomvonal (P1→P2) ezen belül metszi.

#### Időmérés pontossága
- GPS: **10 Hz** (100ms között pozíciók) – NEM 5 Hz (az 5 Hz a kijelzőé)
- Az átlépési időt **interpolálja** a kód (`_interpolate_cross_time`):
  - arány = P1 távolsága / (P1 + P2 távolsága) a vonaltól
  - elméletileg ms-os felbontás lehetséges
- **Valódi korlát:** GPS pozíciós pontatlanság (±3–5 m)
  - 100 km/h-nál: ±180 ms időhiba
  - Professzionális transponder: ±1–5 ms (IR/RF technológia)
- A Kalman-szűrő lag **kör-kör összehasonlításnál kiesik** (relatív pontosság jó)

---

### 3. Rajtvonal szélessége: 20 m → 30 m
**Fájl:** `firmware/main.py:218`  
GPS-es vonalrögzítésnél (`set_finish_line_from_gps`) a generált vonal szélessége növelve, hogy GPS eltolódás esetén is biztosan érzékelje az átlépést.

---

### 4. Közbülső kísérlet és visszaállítás (tanulság!)

**Megpróbált fix:** A `_segments_intersect` helyett `_sign_changed` – csak az előjelváltást figyeli (d1, d2), nem a szegmens határait (d3, d4).

**Probléma:** A 30 m-es rajtvonal **végtelen meghosszabbítását** figyelte. Ha a pálya kanyarodik és a mozgás visszametszi ezt a képzeletbeli egyenest, **hamis detektálás** keletkezik ~100 m-rel a valódi vonaltól.

**Konklúzió:** Vissza kell állni a `_segments_intersect`-re – ez pontosan azt csinálja, amit kell: csak a tényleges GPS nyomvonal (P1→P2 szegmens) és a véges rajtvonal szegmens metszését figyeli.

---

## Jelenlegi állapot (main branch)

| Komponens | Állapot |
|---|---|
| `firmware/display.py` | v1.2 verzió kiírás |
| `firmware/lap.py` | `_segments_intersect` (CCW teszt, véges szegmens) |
| `firmware/main.py` | 30 m-es GPS rajtvonal |

---

## Nyitott kérdések / jövőbeli fejlesztési lehetőségek

- **GPS jitter / kiesés robusztusság:** Ha GPS kiesés történik éppen az átlépés pillanatában, az interpolált nyomvonal esetleg nem metszi a vonalat. Lehetséges megoldás: közelség alapú fallback, de csak a vonalon belüli zónára korlátozva.
- **Kalman szűrő hangolás:** Q érték növelése (`gps.py:57`, jelenleg `Q=0.1`) → gyorsabb reagálás, több zaj. Érdemes tesztelni `Q=0.5`-tel.
- **Időmérés pontosság javítása:** IMU + GPS fúzió (dead reckoning) magasabb frekvenciájú pozícióbecsléshez – nagyobb fejlesztés.
