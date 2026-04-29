# L1 – Üzleti Folyamat – Session Analitika

**Modul:** M06
**Szint:** L1 – Üzleti Folyamat
**Verzió:** v0.1.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-04-22
**Státusz:** 🔲 Tervezve (backend + frontend)

---

## 1. Modul célja

Az M06 modul egy **edzés utáni elemzőfelület** a webes dashboardon. A motoros a session befejezése után részletes elemzést kap: hol volt gyors, hol lassú, mi az elméleti maximuma.

**Üzleti értékek:**
- Lap time breakdown: melyik körben, melyik szektorban volt legjobb
- Delta graph: best laphoz képesti eltérés s-koordináta mentén
- Speed vs. track position: hol fékezett, gyorsított
- Theoretical best: konkrét motiváló szám ("1.8 s maradt az asztalon")
- Consistency score: mennyire ismételhető a teljesítmény

---

## 2. Session struktúra

```
Session:
  id, user_id, track_id, date, conditions (weather, temperature)
  
  Körök listája:
    Lap 1: lap_time=63.4 s, sector_times=[10.1, 11.8, 11.2, 10.5, 11.1, 8.7]
    Lap 2: lap_time=61.2 s, sector_times=[9.8, 11.5, 10.9, 9.7, 10.8, 8.5]
    ...
    Lap N: ...

  GPS trace-ek:
    Minden körhöz: [(lat, lon, speed, ts), ...]
```

---

## 3. Fő analitikai nézetek

### 3.1 Lap Time Breakdown

```
Vizualizáció: stacked bar chart
X tengely: körök száma (1..N)
Y tengely: köridő (s)
Szegmensek: S1 / S2 / S3 / ... szektoronkénti idők

Interakció:
  - Kör kijelölése → delta gap megjelenítés
  - Best lap kiemelése (zöld keret)
  - Szűrés: csak első X kör, stb.
```

### 3.2 Delta Graph

```
Vizualizáció: vonalas grafikon
X tengely: s-koordináta (0.0–1.0, pálya mentén)
Y tengely: delta (s) aktuális kör vs. best lap

Értelmezés:
  Pozitív (vonal fent): lassabb mint a best lap
  Negatív (vonal lent): gyorsabb mint a best lap
  
Több kör egyszerre megjelenítve → látható a konsistencia
```

### 3.3 Speed vs. Track Position

```
Vizualizáció: vonalas grafikon
X tengely: s-koordináta
Y tengely: sebesség (km/h)

Több kör overlay:
  Best lap: narancs / kiemelés
  Többi kör: szürke

Megmutatja:
  - Hol fékez a motoros (sebesség csökken)
  - Hol gyorsít (sebesség nő)
  - Kanyar csúcssebesség (apex speed)
```

### 3.4 Theoretical Best

```
Megjelenítés: kiemelt kártya
  Best Lap:         1:01.234
  Theoretical Best: 0:59.600
  Különbség:        -1.634 s ("1.6 másodperc a tartalékod")

Best szektorok táblázat:
  S1: 9.500 s (Lap 3)
  S2: 11.200 s (Lap 7)
  ...
```

### 3.5 Consistency Score

```
Számítás:
  Szórás a köridőkből (std_dev)
  Consistency = 100 - (std_dev / mean * 100)

Értelmezés:
  > 95%: kiváló (profi szint)
  90–95%: jó
  < 90%: van mit javítani (fizikai fáradás, concentráció)
```

---

## 4. Backend API

```
GET /api/v1/sessions/{session_id}/analysis

Response:
{
  "session": {...},
  "laps": [...],
  "best_lap": {...},
  "theoretical_best_ms": 59600,
  "best_sectors": [...],
  "consistency_score": 94.2,
  "delta_data": {
    "lap_id": [...],  // s-koordináta alapján
    ...
  },
  "speed_data": {
    "lap_id": [...],
    ...
  }
}
```

---

## 5. Kapcsolódó modulok

| Modul | Kapcsolat típusa |
|-------|-----------------|
| M02 Szektorelemzés | **Adatforrás** — sector_times, theoretical_best |
| M04 WiFi Uplink | **Adatforrás** — session adatok backend-en |
| M05 Pálya Geometria | **Alap geometria** — s-koordináta számításhoz |
| M07 Szinkronizált Replay | **Kapcsolódó nézet** — session-ből replay indítható |
