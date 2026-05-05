# Hetzner Cloud — Deploy útmutató (OverLAP)

**Szerver:** `46.225.12.228` (ugyanaz, mint a Dronterapia)
**Domain (majdan):** overlap.hu
**Ideiglenes elérés:** http://46.225.12.228

---

## Áttekintés

Az OverLAP rendszer telepítési folyamata:

1. SSH belépés a szerverre
2. Repo klónozása (vagy frissítése)
3. `setup.sh` futtatása — frontend build, backend venv, pályák betöltése (seed), systemd + nginx
4. Kész — elérhető IP-n, domain aktiválásakor domain-re is

---

## SSH belépés

```powershell
ssh root@46.225.12.228
```

---

## Első telepítés

```bash
# Repo klónozás és setup (egy parancs)
git clone https://github.com/CsabaZsee77/OverLap.git /tmp/OverLap
bash /tmp/OverLap/deploy/setup.sh https://github.com/CsabaZsee77/OverLap.git
```

A `setup.sh` elvégzi:
- apt frissítés, git, nginx, python3, Node.js 20 telepítés
- `overlap` user létrehozása
- Repo klónozás → `/home/overlap/OverLap/`
- Frontend build (`npm ci && npm run build`) → `frontend/dist/`
- Backend Python venv + `pip install -r requirements.txt`
- Pályák betöltése az adatbázisba (`seed_tracks.py` — 3 pálya)
- Systemd service aktiválás (`overlap-api.service`)
- Nginx konfig aktiválás, default site letiltása

---

## Kódfrissítés (deploy workflow)

```bash
ssh root@46.225.12.228
cd /home/overlap/OverLap
sudo -u overlap git pull origin main

# Frontend módosítás esetén:
sudo -u overlap npm ci --prefix frontend
sudo -u overlap npm run build --prefix frontend

# Backend módosítás esetén:
sudo -u overlap /home/overlap/OverLap/backend/venv/bin/pip install -r backend/requirements.txt

# Mindig:
systemctl restart overlap-api
```

---

## Hasznos parancsok a szerveren

```bash
# API service állapot és logok
systemctl status overlap-api
journalctl -u overlap-api -f

# Nginx teszt és újraindítás
nginx -t && systemctl reload nginx

# Backend log (ha van)
cat /home/overlap/OverLap/backend/uvicorn.log
```

---

## SSL (overlap.hu domain aktiválásakor)

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d overlap.hu -d www.overlap.hu \
  --email zsigmond.csaba.logpilot@gmail.com \
  --agree-tos --no-eff-email
```

Ezután a `deploy/nginx.conf` `server_name _;` sorát cseréld le:
```nginx
server_name overlap.hu www.overlap.hu;
```

---

## Fontos fájlok a szerveren

| Fájl/Mappa | Tartalom |
|------------|----------|
| `/home/overlap/OverLap/` | A teljes alkalmazás (git repo) |
| `/home/overlap/OverLap/backend/motometer.db` | SQLite adatbázis (sessions, tracks) |
| `/etc/systemd/system/overlap-api.service` | Systemd unit |
| `/etc/nginx/sites-available/overlap` | Nginx konfig |

---

## Architektúra

```
Internet (HTTP → IP vagy domain)
   │
   ▼
nginx (port 80)
   │
   ├── /api/*  → uvicorn FastAPI (127.0.0.1:8000, csak belső)
   │
   └── /*      → React SPA statikus fájlok (frontend/dist/)
```

---

## Nginx IP cache megjegyzés

Ha az API nem válaszol 502-vel újratelepítés után:
```bash
systemctl restart overlap-api
systemctl reload nginx
```
