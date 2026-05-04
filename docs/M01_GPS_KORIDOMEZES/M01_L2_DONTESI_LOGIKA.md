# L2 – Döntési Logika – GPS & Köridőmérés

**Modul:** M01
**Szint:** L2 – Döntési Logika
**Verzió:** v1.2.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-05-04
**Státusz:** ✅ Implementálva

---

## 1. GPS FIX minőség döntés

```
GPS frissítésnél:

GGA mondat → fix_quality mező (0/1/2):
  0 = nincs fix → valid = False, mérés szünetel
  1 = GPS fix   → valid = True (minimum)
  2 = DGPS fix  → valid = True (jobb)

RMC mondat → status mező ('A'/'V'):
  'V' = Void (érvénytelen) → valid = False
  'A' = Active (érvényes)  → valid = True

Döntés: valid = (rmc_status == 'A') AND (fix_quality >= 1)

Satellit szám (GGA, mező 7):
  < 4 → gyenge fix, figyelmeztetés kijelzőn
  4–6 → elfogadható
  >= 7 → jó fix
```

---

## 2. Köridő érvényességi döntés

```
Rajtvonal metszés detektálva → érvényes-e a kör?

Feltételek:
  A) MIN_LAP_MS: eltelt idő > 10 000 ms (10 s) az előző metszés óta
     → IGEN: normál kör elfogadva
     → NEM: kihagyva (outlap, visszafordulás, false positive)

  B) MAX_LAP_MS: eltelt idő < 600 000 ms (10 perc)
     → IGEN: normál kör
     → NEM: kihagyva (eszköz leállt, GPS kiesett, stb.)

Végső döntés:
  MIN_LAP_MS < elapsed < MAX_LAP_MS → köridő rögzítve
  egyébként → eldobva, print-ben jelezve
```

---

## 2b. Outlap guard döntés (MIN_OUTLAP_MS)

```
Rajtvonal beállítása után az ELSŐ átlépés (STATE_WAITING → IN_LAP):

  MIN_OUTLAP_MS = 5 000 ms (5 s)

  Ha t_cross - t_line_set < MIN_OUTLAP_MS:
    → ELUTASÍTVA (túl korai, GPS kiesés utáni késett detektálás)
    → Állapot marad STATE_WAITING
    → Print: "outlap átlépés túl korai"

  Ha t_cross - t_line_set >= MIN_OUTLAP_MS:
    → ELFOGADVA → STATE_IN_LAP, _last_cross_ms = t_cross

Indoklás: ha a vonal beállításakor GPS kiesés van, a Kalman-szűrő
lassan konvergál; az első detektált átlépés késhet, és félkör-hosszú
"első kört" eredményezne. Az 5s guard ezt kizárja.
```

---

## 3. Best lap frissítési döntés

```
Köridő rögzítve → best_lap frissítendő?

Ha best_lap == None (első kör):
  → best_lap = lap_time (feltétel nélkül)

Ha lap_time < best_lap:
  → best_lap = lap_time
  → kijelzőn: "NEW BEST!" villogás (M03)
  → backend: best_lap frissítés (M04)

Ha lap_time >= best_lap:
  → best_lap változatlan
  → delta = lap_time - best_lap (pozitív → lassabb)
```

---

## 4. Kalman szűrő hangoló döntések

```
Q (folyamat zaj) — mennyit bízunk az IMU-ban:
  Motor: gyors irányváltás, nagy gyorsulások
  → Q = 0.1 (nagyobb mint Kormoran hajósnál, ahol Q=0.01)
  → Kalman gyorsan követi a valós mozgást

R (mérési zaj) — GPS CEP (~2 m AT6558-nál):
  → R = 2.0 (méteres CEP alapján, 10 Hz-es frissítésnél)

Ha GPS dropout (valid = False):
  → Csak IMU predikciós lépés fut
  → P (bizonytalanság) növekszik idővel
  → GPS visszatérésekor nagyobb Kalman gain → gyors visszaállás
```

---

## 5. Rajtvonal metszés geometriai döntés

```
Két szegmens: P1→P2 (GPS mozgás) és L1→L2 (rajtvonal, 30 m széles)

Döntés: metszik-e egymást? (_segments_intersect, CCW teszt)

Segédfüggvény — _direction(A, B, C):
  return (C.lat - A.lat) * (B.lon - A.lon)
       - (B.lat - A.lat) * (C.lon - A.lon)

Metszés feltétele (MINDKÉT feltétel kell):
  d1 = _direction(L1, L2, P1)   ← P1 melyik oldalon van a vonaltól?
  d2 = _direction(L1, L2, P2)   ← P2 melyik oldalon van a vonaltól?
  d3 = _direction(P1, P2, L1)   ← L1 melyik oldalon van a mozgástól?
  d4 = _direction(P1, P2, L2)   ← L2 melyik oldalon van a mozgástól?

  IF (d1>0 AND d2<0 OR d1<0 AND d2>0)    ← ellentétes oldalak a vonaltól
     AND
     (d3>0 AND d4<0 OR d3<0 AND d4>0):   ← metszés a szegmensen BELÜL van
    → METSZÉS VAN (véges 30m-es szegmens, nem végtelen egyenes)

Fontos: a d3/d4 feltétel kizárja a vonal MEGHOSSZABBÍTÁSÁN való
hamis keresztezést (pl. pályakanyarban 100m-re a vonaltól).

Interpolált áthaladási idő:
  ratio = |d1| / (|d1| + |d2|)
  t_cross = t_P1 + ratio * ticks_diff(t_P2, t_P1)
```

---

## 6. 10 Hz konfiguráció döntés

```
AT6558 alapértelmezés: 1 Hz

Boot-kor: küld-e 10 Hz konfigurációs parancsot?
  → IGEN, minden boot-kor (az eszköz nem tárolja)

PMTK parancs: $PMTK220,100*2F\r\n
  (100 ms frissítési intervallum = 10 Hz)

Ellenőrzés:
  $PMTK001,220,3 = sikeresen elfogadva
  $PMTK001,220,2 = parancs ismeretlen (régebbi firmware)
  → Fallback: 1 Hz-es mérés is működik, de pontosság csökken
```

---

## 7. WiFi kapcsolat döntés (M04-nek átadott)

```
Boot-kor WiFi connect kísérlet:
  Sikerült → online mód: lap-ok azonnal feltöltve
  Nem sikerült → offline mód: lap-ok flash-re mentve

Kör befejezésekor:
  WiFi connected? → azonnali HTTP POST
  WiFi disconnected? → queue-ba kerül

Queue mérete > 50 lap? → figyelmeztetés kijelzőn ("FULL")

WiFi újracsatlakozás (háttérben, 30 s-onként):
  Sikeres → queue flush indul
  Sikertelen → folytatja offline módban
```
