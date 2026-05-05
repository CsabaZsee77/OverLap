# main.py - Launcher / Boot program választó
# Tiszta verzió - nincs villogás, pontos touch

import M5
from M5 import *
import time
import os

# ============================================================
# INICIALIZÁLÁS
# ============================================================
M5.begin()

# Színek
BLACK      = 0x000000
WHITE      = 0xFFFFFF
GREEN      = 0x00FF00
YELLOW     = 0xFFFF00
CYAN       = 0x00FFFF
GRAY       = 0x888888
DARK_GRAY  = 0x444444
DARKER_GRAY= 0x222222
RED        = 0xFF0000
BLUE       = 0x0055FF
ORANGE     = 0xFF8800

# ============================================================
# ESCAPE CHECK - bal alsó sarok induláskor = REPL
# ============================================================
M5.update()
time.sleep_ms(200)
M5.update()
if M5.Touch.getCount() > 0:
    x = M5.Touch.getX()
    y = M5.Touch.getY()
    if x < 80 and y > 160:
        M5.Lcd.fillScreen(BLACK)
        M5.Lcd.setTextSize(2)
        M5.Lcd.setTextColor(GREEN, BLACK)
        M5.Lcd.drawString("REPL Mode", 100, 100)
        M5.Lcd.setTextSize(1)
        M5.Lcd.setTextColor(GRAY, BLACK)
        M5.Lcd.drawString("Use Thonny or UIFlow", 80, 130)
        raise SystemExit

# ============================================================
# SD MOUNT
# ============================================================
sd_available = False
try:
    import machine
    sd = machine.SDCard(slot=3, sck=36, mosi=37, miso=35, cs=4)
    os.mount(sd, '/sd')
    sd_available = True
except:
    pass

# ============================================================
# ÁLLAPOT
# ============================================================
current_path = '/'
items = []
scroll_offset = 0
MAX_VISIBLE = 4
ITEM_HEIGHT = 40
LIST_TOP = 55
LIST_BOTTOM = LIST_TOP + MAX_VISIBLE * ITEM_HEIGHT

timeout_active = True
timeout_start = time.ticks_ms()
TIMEOUT_SEC = 5
DEFAULT_APP = '/flash/overlap/main.py'

running = True
need_redraw = True
last_timeout_shown = -1

# ============================================================
# OTA FRISSÍTÉS
# ============================================================

def run_ota(force=False):
    """OTA frissítés futtatása — WiFi csatlakozás + letöltés + reboot ha volt.
    force=True: state törlés → minden fájl újra letöltve."""
    M5.Lcd.fillScreen(BLACK)
    M5.Lcd.setTextSize(2)
    M5.Lcd.setTextColor(CYAN, BLACK)
    title = "FORCE Update" if force else "OTA Frissites"
    M5.Lcd.drawString(title, 55, 40)
    M5.Lcd.drawLine(0, 65, 320, 65, DARK_GRAY)

    def status(line1, line2='', color=WHITE):
        M5.Lcd.fillRect(0, 75, 320, 120, BLACK)
        M5.Lcd.setTextSize(2)
        M5.Lcd.setTextColor(color, BLACK)
        M5.Lcd.drawString(line1, 10, 80)
        if line2:
            M5.Lcd.setTextSize(1)
            M5.Lcd.setTextColor(GRAY, BLACK)
            M5.Lcd.drawString(line2, 10, 108)

    try:
        from overlap import config
    except Exception as e:
        status('Config hiba', str(e), RED)
        time.sleep_ms(2000)
        return

    repos = getattr(config, 'OTA_REPOS', None)
    if not repos:
        status('OTA_REPOS nincs', 'config.py-ban add meg', RED)
        time.sleep_ms(2000)
        return

    import network

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        ssid = getattr(config, 'WIFI_SSID', '')
        if not ssid:
            status('WIFI_SSID nincs', 'config.py-ban add meg', RED)
            time.sleep_ms(2000)
            return

        status('WiFi: ' + ssid, 'Csatlakozas...')
        wlan.connect(ssid, config.WIFI_PASS)
        t = time.ticks_ms()
        dots = 0
        while not wlan.isconnected():
            elapsed = time.ticks_diff(time.ticks_ms(), t)
            if elapsed > 30000:
                status('WiFi timeout', '30s utan feladta', RED)
                time.sleep_ms(2000)
                return
            dots = (dots % 6) + 1
            remaining = (30000 - elapsed) // 1000
            status('WiFi: ' + ssid,
                   'Csatlakozas' + '.' * dots + '  ({}s)'.format(remaining))
            time.sleep_ms(500)

    status('WiFi: OK', 'GitHub ellenorzes...')

    # Kényszer-újraellenőrzés: state törlése → minden fájl letöltve
    # Ha ez nélkül fut, csak a változottakat tölti le
    try:
        from ota import OTAUpdater
    except Exception as e:
        status('ota.py hiba', str(e), RED)
        time.sleep_ms(2000)
        return

    ota = OTAUpdater(repos)
    if force:
        status('Force update...', 'State torles, minden fajl ujra letolt')
        import os
        try:
            os.remove('/flash/ota_state.json')
        except Exception:
            pass
        ota._state = {}
    updated = ota.check_and_update()

    if updated:
        status('Frissites kesz!', 'Ujraindul 2 masodperc mulva...', GREEN)
        time.sleep_ms(2000)
        import machine
        machine.reset()
    else:
        status('Nincs ujabb verzio', 'Visszater a launcherhez...', YELLOW)
        time.sleep_ms(2000)


# ============================================================
# KÖNYVTÁR BETÖLTÉS
# ============================================================
def load_directory():
    global items, scroll_offset
    items = []
    scroll_offset = 0

    if current_path == '/':
        items.append({'name': 'flash', 'type': 'dir', 'path': '/flash'})
        if sd_available:
            items.append({'name': 'sd', 'type': 'dir', 'path': '/sd'})
        return

    items.append({'name': '.. (back)', 'type': 'up', 'path': ''})

    try:
        entries = sorted(os.listdir(current_path))

        # Mappák először
        for name in entries:
            if name.startswith('.'):
                continue
            full_path = current_path + '/' + name
            try:
                os.listdir(full_path)
                items.append({'name': name, 'type': 'dir', 'path': full_path})
            except:
                pass

        # Python fájlok
        for name in entries:
            if name.lower().endswith('.py') and not name.startswith('.'):
                full_path = current_path + '/' + name
                items.append({'name': name, 'type': 'py', 'path': full_path})
    except:
        pass

# ============================================================
# RAJZOLÁS - TELJES
# ============================================================
def draw_full():
    M5.Lcd.fillScreen(BLACK)

    # Header
    M5.Lcd.fillRect(0, 0, 320, 32, DARK_GRAY)
    M5.Lcd.setTextColor(WHITE, DARK_GRAY)
    M5.Lcd.setTextSize(2)
    M5.Lcd.drawString("LAUNCHER", 105, 7)

    # Path
    M5.Lcd.setTextSize(1)
    M5.Lcd.setTextColor(CYAN, BLACK)
    path_disp = current_path if len(current_path) < 30 else "..." + current_path[-27:]
    M5.Lcd.drawString(path_disp, 10, 40)

    # Lista
    draw_list()

    # Scroll gombok
    draw_scroll_buttons()

    # UPDATE gomb (bal alul)
    M5.Lcd.fillRoundRect(5, 210, 105, 28, 5, BLUE)
    M5.Lcd.setTextColor(WHITE, BLUE)
    M5.Lcd.setTextSize(2)
    M5.Lcd.drawString("UPDATE", 14, 214)

    # REPL gomb (jobb alul)
    M5.Lcd.fillRoundRect(250, 210, 65, 28, 5, DARK_GRAY)
    M5.Lcd.setTextColor(WHITE, DARK_GRAY)
    M5.Lcd.setTextSize(2)
    M5.Lcd.drawString("REPL", 258, 214)

    # Default info
    M5.Lcd.setTextSize(1)
    M5.Lcd.setTextColor(GRAY, BLACK)
    M5.Lcd.drawString("Default: " + DEFAULT_APP.split('/')[-1], 120, 218)

    # Timeout
    draw_timeout()

def draw_list():
    y = LIST_TOP

    for i in range(MAX_VISIBLE):
        idx = scroll_offset + i

        bg = DARKER_GRAY if i % 2 == 0 else BLACK
        M5.Lcd.fillRect(0, y, 240, ITEM_HEIGHT, bg)

        if idx < len(items):
            item = items[idx]
            M5.Lcd.setTextSize(2)

            if item['type'] == 'up':
                M5.Lcd.setTextColor(YELLOW, bg)
                M5.Lcd.drawString("<Back", 10, y + 10)
            elif item['type'] == 'dir':
                M5.Lcd.setTextColor(CYAN, bg)
                M5.Lcd.drawString("> " + item['name'][:14], 10, y + 10)
            elif item['type'] == 'py':
                M5.Lcd.setTextColor(GREEN, bg)
                M5.Lcd.drawString("  " + item['name'][:14], 10, y + 10)

        y += ITEM_HEIGHT

    M5.Lcd.fillRect(245, LIST_TOP, 30, 20, BLACK)
    if len(items) > MAX_VISIBLE:
        M5.Lcd.setTextSize(1)
        M5.Lcd.setTextColor(GRAY, BLACK)
        M5.Lcd.drawString("{}/{}".format(scroll_offset + 1, max(1, len(items) - MAX_VISIBLE + 1)), 248, LIST_TOP + 5)

def draw_scroll_buttons():
    btn_x = 260
    btn_w = 55
    btn_h = 35

    can_up = scroll_offset > 0
    color = DARK_GRAY if can_up else 0x111111
    M5.Lcd.fillRoundRect(btn_x, 75, btn_w, btn_h, 5, color)
    M5.Lcd.setTextColor(WHITE if can_up else GRAY, color)
    M5.Lcd.setTextSize(3)
    M5.Lcd.drawString("^", btn_x + 18, 80)

    can_down = scroll_offset < len(items) - MAX_VISIBLE
    color = DARK_GRAY if can_down else 0x111111
    M5.Lcd.fillRoundRect(btn_x, 130, btn_w, btn_h, 5, color)
    M5.Lcd.setTextColor(WHITE if can_down else GRAY, color)
    M5.Lcd.setTextSize(3)
    M5.Lcd.drawString("v", btn_x + 18, 133)

def draw_timeout():
    global last_timeout_shown

    M5.Lcd.fillRect(120, 195, 125, 15, BLACK)

    if timeout_active:
        remaining = TIMEOUT_SEC - (time.ticks_diff(time.ticks_ms(), timeout_start) // 1000)
        if remaining != last_timeout_shown:
            last_timeout_shown = remaining
            M5.Lcd.setTextSize(1)
            M5.Lcd.setTextColor(YELLOW, BLACK)
            M5.Lcd.drawString("Auto {}s".format(remaining), 120, 198)

# ============================================================
# APP INDÍTÁS
# ============================================================
def run_app(filepath):
    global running

    M5.Lcd.fillScreen(BLACK)
    M5.Lcd.setTextSize(2)
    M5.Lcd.setTextColor(GREEN, BLACK)
    M5.Lcd.drawString("Starting...", 100, 100)
    M5.Lcd.setTextSize(1)
    M5.Lcd.setTextColor(WHITE, BLACK)
    M5.Lcd.drawString(filepath, 50, 130)
    time.sleep_ms(300)

    running = False

    try:
        exec(open(filepath).read(), {'__name__': '__main__'})
    except KeyboardInterrupt:
        print("App stopped")
    except Exception as e:
        print("Error:", e)
        M5.Lcd.fillScreen(BLACK)
        M5.Lcd.setTextColor(RED, BLACK)
        M5.Lcd.setTextSize(2)
        M5.Lcd.drawString("ERROR", 130, 80)
        M5.Lcd.setTextSize(1)
        M5.Lcd.setTextColor(WHITE, BLACK)
        M5.Lcd.drawString(str(e)[:40], 10, 120)
        M5.Lcd.setTextColor(GRAY, BLACK)
        M5.Lcd.drawString("Touch to continue", 100, 200)
        time.sleep_ms(500)
        while M5.Touch.getCount() == 0:
            M5.update()
            time.sleep_ms(100)

# ============================================================
# TOUCH KEZELÉS
# ============================================================
def handle_touch(x, y):
    global current_path, scroll_offset, timeout_active, need_redraw

    timeout_active = False

    # UPDATE gomb (bal alul)
    if x < 115 and y > 205:
        run_ota()
        need_redraw = True
        return

    # REPL gomb (jobb alul)
    if x > 245 and y > 205:
        M5.Lcd.fillScreen(BLACK)
        M5.Lcd.setTextSize(2)
        M5.Lcd.setTextColor(GREEN, BLACK)
        M5.Lcd.drawString("REPL Mode", 100, 100)
        raise SystemExit

    # Scroll FEL
    if x > 255 and 70 < y < 120:
        if scroll_offset > 0:
            scroll_offset -= 1
            draw_list()
            draw_scroll_buttons()
        return

    # Scroll LE
    if x > 255 and 125 < y < 175:
        if scroll_offset < len(items) - MAX_VISIBLE:
            scroll_offset += 1
            draw_list()
            draw_scroll_buttons()
        return

    # Lista érintés
    if x < 245 and LIST_TOP <= y < LIST_BOTTOM:
        row = (y - LIST_TOP) // ITEM_HEIGHT
        idx = scroll_offset + row

        if idx < len(items):
            item = items[idx]

            if item['type'] == 'up':
                if current_path in ['/flash', '/sd']:
                    current_path = '/'
                else:
                    parts = current_path.split('/')
                    current_path = '/'.join(parts[:-1]) or '/'
                load_directory()
                need_redraw = True

            elif item['type'] == 'dir':
                current_path = item['path']
                load_directory()
                need_redraw = True

            elif item['type'] == 'py':
                run_app(item['path'])

# ============================================================
# FŐ CIKLUS
# ============================================================
load_directory()
draw_full()

last_touch_time = 0
TOUCH_DEBOUNCE = 400

while running:
    try:
        M5.update()
        now = time.ticks_ms()

        if timeout_active:
            remaining = TIMEOUT_SEC - (time.ticks_diff(now, timeout_start) // 1000)
            if remaining <= 0:
                run_app(DEFAULT_APP)
                break
            if remaining != last_timeout_shown:
                draw_timeout()

        if need_redraw:
            draw_full()
            need_redraw = False

        if M5.Touch.getCount() > 0:
            if time.ticks_diff(now, last_touch_time) > TOUCH_DEBOUNCE:
                x = M5.Touch.getX()
                y = M5.Touch.getY()
                last_touch_time = now
                touch_start = time.ticks_ms()
                is_update_btn = x < 115 and y > 205
                force_shown = False

                while M5.Touch.getCount() > 0:
                    M5.update()
                    time.sleep_ms(30)
                    if is_update_btn and not force_shown:
                        held = time.ticks_diff(time.ticks_ms(), touch_start)
                        if held >= 2000:
                            force_shown = True
                            M5.Lcd.fillRoundRect(5, 210, 105, 28, 5, ORANGE)
                            M5.Lcd.setTextColor(BLACK, ORANGE)
                            M5.Lcd.setTextSize(2)
                            M5.Lcd.drawString("FORCE! ", 14, 214)

                held_ms = time.ticks_diff(time.ticks_ms(), touch_start)
                if is_update_btn and held_ms >= 2000:
                    run_ota(force=True)
                    need_redraw = True
                else:
                    handle_touch(x, y)

        time.sleep_ms(30)

    except KeyboardInterrupt:
        print("Launcher stopped")
        break
    except SystemExit:
        break

print("Launcher exited")
