# OverLAP — Felhasználói Útmutató

**Verzió:** v1.2.0  
**Hardver:** M5Stack CoreS3 + AT6558 GPS + BMI270 IMU  
**Utolsó frissítés:** 2026-05-04

---

## Tartalom

1. [Első indítás](#1-első-indítás)
2. [Képernyő módok](#2-képernyő-módok)
3. [Rajtvonal felvétele](#3-rajtvonal-felvétele)
4. [Köridőmérés](#4-köridőmérés)
5. [IMU kalibráció](#5-imu-kalibráció)
6. [Log fájlok](#6-log-fájlok)
7. [Telegram értesítések](#7-telegram-értesítések)
8. [Hibaelhárítás](#8-hibaelhárítás)

---

## 1. Első indítás

1. Rögzítsd a CoreS3-at a motoron (tartóban, jó láthatóság + stabil pozíció).
2. Csatlakoztasd a GPS modult a Grove UART porthoz.
3. Kapcsold be — a boot képernyőn megjelenik az **OverLAP v1.2** felirat.
4. Várd meg a GPS FIX megszerzését (zöld ● a státuszsorban). Ez 30–60 másodpercet vehet igénybe első indításkor.

**Státuszsor jelzések:**
- `●GPS 9sat` — GPS fix OK, 9 műhold (zöld = jó, sárga = gyenge)
- `NO FIX` (piros ●) — nincs GPS fix, mérés nem lehetséges
- `WiFi●` — WiFi csatlakoztatva

---

## 2. Képernyő módok

Rövid érintéssel (bármely ponton, kivéve SETUP módban) váltasz a módok között:

```
MAIN → LEAN → KAMM → SLIP → CALIB → STATS → DIAG → SETUP → MAIN
```

| Mód | Mit látsz |
|-----|-----------|
| **MAIN** | Futó stopper, előző kör, best lap, delta, sebesség |
| **LEAN** | Dőlésszög műhorizont, peak-hold nyilak, lateral G |
| **KAMM** | Lat G vs Lon G trail, kerékenként tapadáskihasználtság |
| **SLIP** | Csúszásmonitor: mért vs. elvárt yaw rate |
| **CALIB** | IMU kalibráció (lásd §5) |
| **STATS** | Session statisztika: best lap, körök száma, max sebesség |
| **DIAG** | GPS nyers adatok: lat, lon, sebesség, műholdak |
| **SETUP** | Rajtvonal felvétel (lásd §3) |

---

## 3. Rajtvonal felvétele

### A) GPS alapú felvétel (ajánlott)

1. Állj a rajtvonal mellé (GPS FIX szükséges).
2. Navigálj **SETUP** módba (érintésekkel körbeforgatva).
3. Tartsd nyomva **2 másodpercig a bal oldalt** → zöld képernyővillanás (2 mp) + hangjelzés.
4. A stopper azonnal elindul — a következő áthaladásig az outlap fut.

**A rendszer automatikusan generál egy 30 m széles virtuális vonalat** a jelenlegi pozíció és haladási irány alapján, merőlegesen az útra.

> **Fontos:** Az első átlépés csak akkor számít érvényes körnek, ha a vonal beállítása óta legalább **5 másodperc** eltelt (outlap guard). Ez megakadályozza, hogy GPS-kiesés utáni késett detektálás rövid hamis első kört adjon.

### B) Fájlból betöltés (track.json)

SETUP módban érintsd a **jobb oldalt** → betölti a `/flash/track.json` fájlt:

```json
{
  "name": "Kakucs Ring",
  "track_type": "circuit",
  "finish_line": {
    "lat1": 47.246053, "lon1": 19.377900,
    "lat2": 47.246395, "lon2": 19.378474
  }
}
```

---

## 4. Köridőmérés

### MAIN képernyő elemei

```
┌──────────────────────────────────────┐
│ ●GPS 9sat    WiFi●   85%      MAIN  │  ← státuszsor
├──────────────────────────────────────┤
│ STOPPER                              │
│            0:42.17                   │  ← futó kör idő (CYAN)
├──────────────────────────────────────┤
│ BEST              ELOZO             │
│ 1:01.87           1:02.35           │
│                   127 km/h          │  ← előző kör max sebesség
│ DELTA +0.35s      PRED  1:01.50     │
├──────────────────────────────────────┤
│ SESSION MAX                          │
│ 127 km/h                             │
└──────────────────────────────────────┘
```

**Stopper színek:**
- **CYAN** — aktív mérés (körben vagy outlap)
- **Sötétszürke `--:--.--`** — nincs rajtvonal beállítva

### Köráthaladás logika

- A 30 m-es virtuális vonal mindkét végén zárt — csak tényleges átlépésnél tüzel, nem a meghosszabbításán.
- Érvényes kör: 10 s < körido < 10 perc (konfigurálható).
- Köráthaladáskor: stopper nullázódik, az előző kör adatai megjelennek.

---

## 5. IMU kalibráció

1. Navigálj **CALIB** módba.
2. Helyezd egyenesen, vízszintesen a motort (senki nem ül rajta).
3. Tartsd nyomva a képernyőt → 20 mintás újrakalibrálás indul.
4. Ha `OK – egyenes` jelenik meg (|szög| < 3°), a kalibráció sikeres.

**Megjegyzés:** A kalibrációs képernyő felirata „IMU KALIBRACIO" (ékezetek nélkül — a kijelző fontja nem támogatja az ékezetes karaktereket).

---

## 6. Log fájlok

### Hol tárolódnak?

Az OverLAP minden kör után azonnal lementi az adatokat:

| Prioritás | Hely | Feltétel |
|-----------|------|----------|
| 1. | `/sd/overlap_logs/` | SD kártya csatlakoztatva |
| 2. | `/flash/mm_logs/` | Fallback (belső flash) |

**A fájlok sosem törlődnek újraindításkor.** A session fájl megmarad, amíg az uplink.py sikeresen fel nem tölti a backendre (akkor törli).

### Fájlformátum

Minden indítás egy új JSON fájlt hoz létre:
```
session_mm_abc123_1746355200000.json
```

Tartalom köröként:
```json
{
  "lap_number": 3,
  "lap_time_ms": 62470,
  "max_speed_kmh": 134.2,
  "max_lean_right": 41.3,
  "max_lean_left": 38.7,
  "peak_kamm_g": 0.923,
  "peak_kamm_angle": 97.8,
  "gps_trace": [
    {
      "lat": 47.246100, "lon": 19.378100,
      "speed_kmh": 87.3, "ts_ms": 421578,
      "lean_deg": -34.2,
      "lat_g": 0.612, "lon_g": -0.084,
      "kamm_angle": 97.8
    },
    ...
  ]
}
```

### Tárhely becslés

| Tárolás | Kapacitás |
|---------|-----------|
| Flash (GPS trace-szel) | ~12 kör |
| Flash (trace nélkül) | ~2000 kör |
| SD kártya | Korlátlan (ajánlott) |

> **Ajánlás:** Használj SD kártyát, ha sok kört mész vagy GPS trace analitikát szeretnél.

---

## 7. Telegram értesítések

Ha WiFi elérhető, minden kör után Telegram üzenet érkezik:

```
OverLAP #3  1:02.47  🏁 LEGJOBB!
Max: 134 km/h  Delta: -0.88s
Max doles: Bal 39  Jobb 42
Max Kamm: 0.91G (Bal kanyar)
```

**Kamm szektor értelmezés:**
| Szög (°) | Szektor |
|----------|---------|
| 0 (±22.5) | Gyorsítás |
| 45 | Gyorsítás + Bal kanyar |
| 90 | Bal kanyar |
| 135 | Fékezés + Bal kanyar |
| 180 | Fékezés |
| 225 | Fékezés + Jobb kanyar |
| 270 | Jobb kanyar |
| 315 | Gyorsítás + Jobb kanyar |

**WiFi nélkül:** a Telegram üzenetek sorba kerülnek, és WiFi csatlakozáskor automatikusan elküldődnek.

---

## 8. Hibaelhárítás

### GPS fix nem jön

- Menj ki szabad ég alá (épület, fedél blokkolhatja).
- Várj 60–90 másodpercet (hideg indítás).
- Ellenőrizd a GPS kábel csatlakoztatását.

### Rajtvonalat nem érzékeli

- Ellenőrizd, hogy GPS FIX van (zöld ● státuszsorban).
- A vonal 30 m széles — ha jobban oldalra mész, esetleg nem metszi a szegmenst.
- Próbáld meg újra felvenni a rajtvonalat (SETUP → bal oldal 2 mp).

### Az első kör rövidebb mint kellene

- Ez a MIN_OUTLAP_MS guard miatt normális — az első detektálás csak 5 másodperccel a vonal beállítása után fogadható el.
- Ha a kör egyébként is rövid volt (< 10 s), a MIN_LAP_MS guard dobja el.

### IMU értékek nullák / furcsák

- Navigálj CALIB módba és végezz újrakalibrálást.
- Bizonyosodj meg, hogy a motor egyenesen áll kalibráció alatt.

### Telegram üzenetek nem érkeznek

- Ellenőrizd a WiFi kapcsolatot (státuszsorban `WiFi●`).
- Ellenőrizd a `config.py`-ban a `WIFI_SSID` és `WIFI_PASS` értékeket.
- Offline módban a queue-ban gyűlnek az üzenetek, WiFi csatlakozáskor küldődnek.

---

*OverLAP — Motoros Telemetria & Track Analytics Platform*
