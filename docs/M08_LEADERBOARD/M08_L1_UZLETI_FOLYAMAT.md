# L1 – Üzleti Folyamat – Leaderboard & Virtuális Bajnokság

**Modul:** M08
**Szint:** L1 – Üzleti Folyamat
**Verzió:** v0.1.0
**Létrehozva:** 2026-04-22
**Utolsó módosítás:** 2026-04-22
**Státusz:** 🔲 Tervezve (backend + frontend)

---

## 1. Modul célja

Az M08 modul kezeli az **időszakos ranglistákat** és a **virtuális bajnokságok** rendszerét. Motivációs réteg: a motoros nemcsak saját magával versenyez, hanem a közösséggel is.

**Üzleti értékek:**
- Napi/heti/havi best lap rangsorok
- Event-alapú bajnokság (pl. "Pünkösdi Motoros Bajnokság")
- Publikus profilok → közösségi versengés
- Díjazás nevezési díj ellenében
- Pálya számára vonzerő: aktív közösség, mérhető teljesítmény

---

## 2. Ranglisták

```
Szűrők:
  - Pálya (track_id)
  - Időszak: napi / heti / havi / all-time / event
  - Felhasználó: saját / mindenki / publikus profilok

Oszlopok:
  Rank | Avatar | Név | Best Lap | Best Szektor combo | Consistency | Delta top1-hez

Kiegészítők:
  "Ghost Leaderboard": theoretical best lapok rangsora
  Napszak-alapú rangsor (pl. "Reggeli mezőny" vs. "Esti mezőny")
  Esemény-specifikus (pl. "2026 Május Anyák Napi Kör")
```

---

## 3. Virtuális bajnokság

```
Bajnokság létrehozása:
  Neve, pálya, időszak (start/end dátum), kategória
  Nevezési díj (0 Ft = ingyenes, pl. 2 000 Ft = díjazott)
  Maximális résztvevők (opcionális)

Nevezés folyamata:
  1. Felhasználó megnyitja a bajnokságot
  2. Regisztrál + opcionálisan fizet (Stripe / SimplePay)
  3. Profilja nyilvánossá tehető (kép, bemutatkozás)
  4. Ranglistán megjelenik a neve

Eredmény meghatározás:
  A bajnokság időszakában mért legjobb köridő számít
  Nem kell egyszerre ott lenni — bármikor futhat
  Végeredmény: időszak végén rögzítve

Díjkiosztó:
  Top 3 díjazás
  Automatikus értesítés emailben
  Eredmények archívumban megmaradnak

Függetlenség a pályától:
  A bajnokság nem a pálya hivatalos versenye
  "MotoMeter virtuális rangsor" — külső szoftver mérése
  Pálya szervezhet saját bajnokságot a rendszer igénybevételével
```

---

## 4. Felhasználói profil

```
Alap (ingyenes):
  Nickname, saját köridők megtekintése
  Privát profil (mások nem látják)

Előfizetés (minimális havidíj):
  Feltöltési korlát nélkül
  Nyilvános profil opció

Publikus profil (nevezésnél választható):
  Profilkép, bemutatkozó szöveg
  Best lap / szektor nyilvános
  Bajnokság ranglistán látható

Device összerendelés:
  MAC address alapján auto-regisztrált device
  Felhasználó webes felületen összeköti a profiljával
```

---

## 5. Monitor / helyszíni kijelző

```
Célja: a pályán várakozók látják az aktuális ranglistát

Technikai megvalósítás:
  - Bármilyen monitor / TV + böngésző
  - /display URL → kiosk mód (fullscreen, auto-refresh)
  - Megjelenítés: top 10 köridő, aktuális nap
  - Realtime frissítés WebSocket-en
  - Nem kell külön hardver

Tartalom:
  Pálya neve | Dátum
  Rank | Név | Best Lap | Delta #1
  (top 10 sor)
  Alul: last updated timestamp
```

---

## 6. Backend API

```
GET /api/v1/leaderboard?track_id=kakucs&period=today
GET /api/v1/leaderboard?track_id=kakucs&period=week
GET /api/v1/leaderboard?event_id=punkosd_2026
GET /api/v1/events                        → bajnokságok listája
POST /api/v1/events/{id}/register         → nevezés
GET /api/v1/display/{track_id}            → kiosk mód adat
```

---

## 7. Események

| Esemény | Következmény |
|---------|-------------|
| Lap feltöltve (M04) | Ranglisták automatikus frissítése |
| Bajnokság nevezés | Profil megjelenés, fizetés kezelés |
| Időszak vége | Végeredmény rögzítés, díj értesítések |
| Display oldal megnyitás | WebSocket feliratkozás, live frissítés |

---

## 8. Kapcsolódó modulok

| Modul | Kapcsolat típusa |
|-------|-----------------|
| M04 WiFi Uplink | **Adatforrás** — feltöltött köridők |
| M06 Session Analitika | **Kapcsolódó nézet** — sorból session megnyitható |
| M07 Szinkronizált Replay | **Kapcsolódó nézet** — sorból replay indítható |
