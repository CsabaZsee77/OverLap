# config.py - MotoMeter konfiguráció
# MotoMeter v0.1 - M5Stack CoreS3
#
# Szerkeszd ezt a fájlt a helyszínen, vagy használd a kijelzőn a
# "SET FINISH LINE" funkciót a rajtvonal automatikus felvételéhez.

# ============================================================
# RAJTVONAL (két GPS koordináta = virtuális szegmens)
# ============================================================
# 0.0 értékek esetén a rendszer "SET FINISH LINE" módba lép.
FINISH_LINE = {
    'lat1': 0.0, 'lon1': 0.0,
    'lat2': 0.0, 'lon2': 0.0,
}

# Kakucs Ring előre beállított rajtvonal (opcionális):
# FINISH_LINE = {
#     'lat1': 47.0880, 'lon1': 19.2830,
#     'lat2': 47.0882, 'lon2': 19.2832,
# }

# ============================================================
# SZEKTOROK
# ============================================================
# Lista GPS koordináta-párokban (mint a rajtvonal).
# Üresen hagyva = nincs szektormérés (csak köridő).
# Részletes definíció: M05 webes Track Explorer → Export config
SECTORS = []

# ============================================================
# KÖRIDŐ ÉRVÉNYESSÉGI HATÁROK
# ============================================================
MIN_LAP_MS = 30_000    # 30 s  — kizárja az outlap / visszafordulást
MAX_LAP_MS = 600_000   # 10 min

# ============================================================
# GPS UART
# ============================================================
GPS_UART_ID  = 2
GPS_TX_PIN   = 17
GPS_RX_PIN   = 18
GPS_BAUD     = 115200

# ============================================================
# KALMAN SZŰRŐ PARAMÉTEREK
# ============================================================
KALMAN_POS_Q   = 0.1    # pozíció folyamat zaj (motor: gyors irányváltás)
KALMAN_POS_R   = 2.0    # pozíció mérési zaj (~2 m GPS CEP)
KALMAN_SPEED_Q = 0.05
KALMAN_SPEED_R = 1.0

# ============================================================
# SD KÁRTYA
# ============================================================
SD_SLOT  = 3
SD_SCK   = 36
SD_MOSI  = 37
SD_MISO  = 35
SD_CS    = 4
SD_MOUNT = '/sd'
LOG_DIR  = '/sd/overlap_logs'

# ============================================================
# WIFI
# ============================================================
# Telefon hotspot adatai — megszakadás esetén auto-újracsatlakozás
WIFI_SSID  = 'Csaba iPhone-ja'
WIFI_PASS  = '234567891'
WIFI_RETRY_INTERVAL_S = 30

# ============================================================
# BACKEND
# ============================================================
BACKEND_URL   = ''    # ha üres, backend uplink kimarad
DEVICE_ID     = ''    # auto-generált MAC alapján, ha üres
RIDER_NAME    = ''    # pl. 'Kiss Péter' — megjelenik a ranglistán

# ============================================================
# TELEGRAM BOT
# ============================================================
# 1. Nyisd meg a Telegram appot, keresd: @BotFather
# 2. Küldj neki: /newbot  → megkapod a BOT_TOKEN-t
# 3. Nyisd meg a botodat, küldj egy üzenetet, majd keresd:
#    @userinfobot  → megkapod a CHAT_ID-t
TELEGRAM_BOT_TOKEN = '8630230971:AAFe_XwgznHmNfzE5Kq_P7kcD7-DFkGZUHs'
TELEGRAM_CHAT_ID   = '8133479839'

# ============================================================
# KIJELZŐ
# ============================================================
DISPLAY_BRIGHTNESS = 80   # % (0–100)

# ============================================================
# PÁLYA NÉV (megjelenítéshez, feltöltéshez)
# ============================================================
TRACK_NAME = 'Kakucs Ring'

# ============================================================
# OTA FRISSÍTÉS
# ============================================================
# token: GitHub Personal Access Token, csak "Contents: Read" jog kell
# subdir: a repo-n belüli mappa (pl. 'firmware')
# target: a device-on hova kerüljenek a fájlok
# skip: ezeket OTA sosem írja felül
OTA_REPOS = [
    {
        'repo':   'CsabaZsee77/OverLap',
        'branch': 'main',
        'token':  '',  # GitHub Personal Access Token — csak a device-on töltsd ki, ne commitold!
        'subdir': 'firmware',
        'target': '/flash/overlap/',
        'skip':   ['config.py', 'ota.py', 'boot.py', 'track.json'],
    },
]
