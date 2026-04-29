# L4 – Tranzakciós és Párhuzamos Kezelés – GPS & Köridőmérés

**Modul:** M01
**Szint:** L4 – Tranzakciós és párhuzamos kezelés, hibakezelés
**Verzió:** v0.1.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-04-22
**Státusz:** 🔲 Tervezve

---

## 1. Párhuzamos task-ok és adatmegosztás

```
gps_task()     → írja: gps.lat, gps.lon, gps.speed, gps.valid
imu_task()     → írja: imu.ax, imu.ay, imu.lean_angle
display_task() → olvassa: gps.*, imu.*, lap_detector.*
uplink_task()  → olvassa: uplink_queue (listából poppol)

MicroPython uasyncio: kooperatív multitasking (nem preemptív)
→ Race condition nincs, mert csak await pontoknál vált
→ Nem kell lock/mutex a megosztott adatokhoz
```

---

## 2. Tranzakció: köridő rögzítés

```
Trigger: LapDetector.update() → LapResult visszaad

Atomicitás: egyetlen szinkron blokk (await előtt lefut teljesen)

Lépések (on_lap_complete):
  1. lap_result validálás (MIN/MAX idő ellenőrzés)
  2. best_lap frissítés (ha szükséges)
  3. GPS trace lezárása a körre (logger.py)
  4. uplink_queue.append(lap_data)  ← M04
  5. display.notify_lap(lap_result) ← M03
  6. sector.reset()                 ← M02

Hibakezelés:
  Ha logger.write() MemoryError → lap_time elvész, de rendszer fut tovább
  Ha uplink_queue full (>50) → legrégebbi elem elvész (FIFO drop)
```

---

## 3. GPS UART hibakezelés

```
Lehetséges hibák:
  - UART init hiba (Pin konfliktus, hw fault)
  - Buffer overflow (lassú feldolgozás)
  - Érvénytelen NMEA (checksum hiba, részleges mondat)
  - GPS timeout (>5 s nincs érvényes adat)

Kezelés:
  try/except minden UART olvasásnál (Kormoran mintára)
  
  UART init hiba:
    → gps.available = False
    → Kijelzőn "GPS ERROR" szöveg
    → Rendszer többi része fut (IMU, kijelző)

  Buffer overflow:
    → gps_buffer = "" (buffer reset)
    → Következő teljes mondattól folytatja

  Érvénytelen NMEA:
    → Mondat eldobva, continue
    → Nem növeli hibaszámlálót (zajosság normális)

  GPS timeout (>5 s):
    → gps.valid = False
    → Kalman csak predikciós lépés (IMU alapján)
    → Kijelzőn "NO GPS" figyelmeztetés
    → Köridő mérés szünetel
```

---

## 4. IMU hibakezelés

```
Lehetséges hibák:
  - I2C init hiba (BMI270 nem válaszol)
  - Olvasási timeout

Kezelés:
  I2C init hiba:
    → imu.available = False
    → Kalman csak GPS adatokat használ (nem 2D IMU-fúzió)
    → Egyszerű 1D Kalman (sebesség szűrés) elegendő

  Olvasási hiba:
    → Előző értékek maradnak
    → Újrapróbálkozás következő task iterációban
```

---

## 5. Flash log hibakezelés

```
logger.py:

  Flash teli (OSError: ENOSPC):
    → Logging leáll
    → Kijelzőn "STORAGE FULL"
    → Köridő mérés FOLYTATÓDIK (csak log nincs)
    → uplink queue aktív marad

  Flash write hiba:
    → try/except, continue
    → Nem állítja meg a fő loop-ot
```

---

## 6. Rajtvonal koordináta érvényességi ellenőrzés

```
config.py betöltésekor:

  FINISH_LINE koordináták:
    lat1, lon1, lat2, lon2 mind != 0.0?
    → IGEN: rajtvonal betöltve
    → NEM: NO_FINISH_LINE állapot, helyszíni felvétel szükséges

  L1 és L2 távolsága > 1 m?
    → IGEN: elfogadva
    → NEM: hiba, koordináták azonosak vagy túl közel
    → Kijelzőn: "SET FINISH LINE"

  Maximális távolság < 100 m?
    → NEM: gyanús, lehet mértékegység-hiba
    → Figyelmeztetés logba, de elfogadva
```

---

## 7. Memóriagazdálkodás MicroPython-on

```
CoreS3: 512 KB SRAM, 8 MB PSRAM (kihasználható)

GPS trace tárolás:
  Egy kör ~600 GPS pont (10 Hz, ~60 s kör)
  Egy pont: (lat, lon, speed, ts) = ~40 byte
  Egy kör: ~24 KB
  
  Stratégia:
    - Kör közben: RAM-ban gyűjtés (ring buffer)
    - Kör végén: flash/SD-re írás, RAM felszabadítás
    - Max RAM-ban tartott körtrace: 1 db

uplink_queue:
  Maximális méret: 50 lap_summary rekord
  Egy rekord: ~200 byte (lap_time, szektor idők, timestamp)
  Össz: ~10 KB → biztonságos

Kalman belső állapot: ~50 byte/instance → negligálható
```

---

## 8. 10 Hz GPS konfiguráció tranzakció

```
Boot-kor, GPS UART megnyílása után:

  Parancs küldése:
    uart.write(b'$PMTK220,100*2F\r\n')
    time.sleep_ms(200)

  Válasz várakozás (opcionális):
    Ha '$PMTK001,220,3' érkezett → siker logolva
    Ha timeout (500 ms) → no-op, 1 Hz-en megy tovább

  Nem blokkoló: a boot nem akad el a konfiguráción
  Fallback: 1 Hz GPS → pontosság kisebb, de rendszer működik
```
