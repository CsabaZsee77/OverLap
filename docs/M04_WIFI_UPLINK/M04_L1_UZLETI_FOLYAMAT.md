# L1 – Üzleti Folyamat – WiFi Uplink & Log

**Modul:** M04
**Szint:** L1 – Üzleti Folyamat
**Verzió:** v1.2.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-05-04
**Státusz:** ✅ Implementálva

---

## 1. Modul célja

Az M04 modul felelős a CoreS3 és a backend szerver közötti **adatátvitelért**, valamint az **offline lokális naplózásért**. Biztosítja, hogy egyetlen köridő se vesszen el hálózati kiesés esetén sem.

**Üzleti értékek:**
- Telefon hotspot → azonnali realtime feltöltés
- Pálya WiFi → infrastruktúra-alapú megoldás (jövő)
- Offline mód → flash log, batch feltöltés WiFi elérésekor
- Realtime leaderboard → mások azonnal látják az eredményeket

---

## 2. Adatátvitel architektúra

```
CoreS3 → WiFi → Backend (FastAPI)

Két csatorna:
  A) Lap summary: HTTP POST (kis adat, azonnal)
     Tartalom: lap_time, sector_times, timestamp, device_id
  
  B) GPS trace: HTTP POST (nagy adat, kör után)
     Tartalom: [(lat, lon, speed, ts), ...] ~600 pont/kör
     Opcionális: felhasználó beállíthatja (adathasználat vs. analitika)
```

---

## 3. Fő folyamat

```
[Boot] → WiFi connect kísérlet
  Sikerült → online mód
  Nem sikerült → offline mód (flash log)
      │
      ▼
[Kör rögzítve] (M01 esemény)
  → lap_data összeállítása
  → logger.write(lap_data)   ← mindig, offline biztonsági mentés
  → uplink_queue.append(lap_data)
      │
      ▼
[uplink_task, 1 Hz-es loop]
  WiFi connected?
    IGEN → queue üres?
              IGEN → wait
              NEM  → HTTP POST → siker: queue.pop, logger mark_synced
                               → hiba: retry 3×, majd pending marad
    NEM  → reconnect kísérlet (30 s-onként)
              Sikeres → queue flush indul
              Sikertelen → offline mód folytatódik
```

---

## 4. HTTP POST formátum

```json
POST /api/v1/laps
Content-Type: application/json

{
  "device_id": "overlap_abc123",
  "session_id": "2026-04-22T14:30:00",
  "lap_number": 5,
  "lap_time_ms": 61234,
  "sector_times_ms": [9800, 11500, 10900, 9700, 10800, 8530],
  "timestamp_utc": "2026-04-22T14:52:11Z",
  "gps_trace": [
    {
      "lat": 47.123456, "lon": 19.123456,
      "speed_kmh": 87.3, "ts_ms": 1745330531000,
      "lean_deg": -34.2,
      "lat_g": 0.612, "lon_g": -0.084,
      "kamm_angle": 97.8
    },
    ...
  ]
}
```

---

## 5. Offline log (logger.py)

```
Fájlrendszer stratégia (prioritás sorrendben):
  /sd/overlap_logs/   → elsődleges (SD kártya, ha elérhető)
  /flash/mm_logs/     → fallback (belső flash, ~500 KB szabad)

Fájlnév: session_<device_id>_<boot_ts_ms>.json
Format: JSON (egy fájl = egy session)

Session lezárása:
  - A fájl SOSEM törlődik újraindításkor — megmarad a következő boothoz
  - add_lap() minden körután azonnal ki is írja (áramkimaradás-biztos)
  - close_session() utolsó flush-t csinál, de opcionális
  - _uploaded = true → az uplink.py törli a fájlt feltöltés után

JSON struktúra:
{
  "device_id":  "mm_f412faba14ec",
  "track_id":   null,
  "rider_name": "",
  "started_at": "2026-05-04T...",
  "laps": [
    {
      "lap_number":       1,
      "lap_time_ms":      57092,
      "lap_start_ts":     421578,
      "lap_end_ts":       478670,
      "sector_times_ms":  [],
      "max_speed_kmh":    127.4,
      "max_lean_right":   41.3,    ← per-kör max jobb dőlés (fok) (v1.2+)
      "max_lean_left":    38.7,    ← per-kör max bal dőlés (fok) (v1.2+)
      "peak_kamm_g":      0.923,   ← per-kör max kombinált G-erő (v1.2+)
      "peak_kamm_angle":  97.8,    ← irányszög a max Kamm pillanatában (fok) (v1.2+)
      "gps_trace": [
        {
          "lat": 47.123456, "lon": 19.123456,
          "speed_kmh": 87.3, "ts_ms": 421578,
          "lean_deg": -34.2,
          "lat_g": 0.612, "lon_g": -0.084,
          "kamm_angle": 97.8
        },
        ...
      ]
    }
  ],
  "_uploaded": false
}

Tárhely becslés:
  Egy kör (trace nélkül): ~250 byte
  GPS trace (IMU mezőkkel): ~40 KB (600 pont × 68 byte)
  CoreS3 flash szabad: ~500 KB
  → kettőezer kör (trace nélkül) / ~12 kör (trace-szel flash-en)
  → SD kártyán: korlátlan
```

## 5b. Telegram értesítések

```
Telegram Bot API — minden kör után üzenet (ha WiFi elérhető):

Feladó neve: OverLAP (korábban: MotoMeter — v1.2-ben átnevezve)

Mező             | Tartalom
-----------------|------------------------------------------
lap_number       | kör sorszáma (#1, #2, ...)
lap_time_ms      | kör ideje (M:SS.mmm)
max_speed_kmh    | az adott KÖR maximuma (nem session max)
is_best          | "LEGJOBB!" jelölés ha new best
delta            | eltérés az előző körtől (+/- mp)
max_lean_right   | per-kör max jobb dőlés (fok) — "Max doles: Jobb X"
max_lean_left    | per-kör max bal dőlés (fok)  — "Max doles: Bal Y"
peak_kamm_g      | per-kör max Kamm G-erő        — "Max Kamm: X.XXG (szektor)"
peak_kamm_angle  | Kamm irányszög → szektornév (Gyorsítás / Kanyar / Fékezés stb.)

Példa üzenet:
  OverLAP #3  1:02.47  🏁 LEGJOBB!
  Max: 134 km/h  Delta: -0.88s
  Max doles: Bal 39  Jobb 42
  Max Kamm: 0.91G (Bal kanyar)

Retry logika:
  - Sikertelen küldés: telegram_queue-ban marad
  - Retry: lap detektáláskor (ha WiFi on) + uplink_task 30s-onként
  - Deduplikáció: telegram_sent set (lap_number kulcson)
```

---

## 6. Device azonosítás

```
device_id: MAC address alapján generált egyedi azonosító
  import network
  wlan = network.WLAN(network.STA_IF)
  mac = wlan.config('mac')
  device_id = 'mm_' + mac.hex()

Első regisztráció:
  Backend fogadja az ismeretlen device_id-t → auto-regisztráció
  Felhasználó a webes felületen összekötheti a profiljával
```

---

## 7. Eseményindítók

| Esemény | Következmény |
|---------|-------------|
| Boot | WiFi connect kísérlet |
| M01: lap_recorded | logger.write + queue.append |
| uplink_task tick (1 Hz) | Queue feldolgozás, reconnect kísérlet |
| WiFi connect sikeres | Batch queue flush indul |
| HTTP POST sikeres | Queue item törlése, logger mark_synced |
| HTTP POST 3× hiba | Item pending marad, következő ticknél retry |

---

## 8. Kapcsolódó modulok

| Modul | Kapcsolat típusa |
|-------|-----------------|
| M01 GPS & Köridőmérés | **Adatfogadás** — lap_time, GPS trace |
| M02 Szektorelemzés | **Adatfogadás** — sector_times |
| M03 Kijelző | **Státuszadat szolgáltatás** — WiFi state, queue size |
| Backend API | **HTTP POST** — /api/v1/laps végpont |
