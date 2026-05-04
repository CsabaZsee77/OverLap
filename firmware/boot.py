# boot.py - OTA ellenőrzés induláskor
# Telepítés: mpremote cp firmware/boot.py :/flash/boot.py
# (USB-n kell telepíteni, OTA maga nem frissíti)
#
# Logika:
#   1. WiFi csatlakozás (max 15s) — kijelzőn visszajelzés
#   2. OTA ellenőrzés minden konfigurált repón
#   3. Ha volt frissítés → reboot
#   4. Ha nincs WiFi vagy nincs OTA konfig → silent skip, main.py fut tovább

def _lcd_status(lcd, line1, line2='', line3=''):
    """Egyszerű státusz képernyő az OTA alatt."""
    lcd.fillScreen(0x000000)
    lcd.setTextColor(0x00FFFF, 0x000000)
    lcd.setTextSize(2)
    lcd.drawString("OverLAP", 95, 60)
    lcd.setTextColor(0x888888, 0x000000)
    lcd.setTextSize(1)
    lcd.drawString("OTA ellenorzes...", 90, 90)
    lcd.setTextColor(0xFFFFFF, 0x000000)
    lcd.drawString(line1, 10, 130)
    if line2:
        lcd.drawString(line2, 10, 148)
    if line3:
        lcd.setTextColor(0x888888, 0x000000)
        lcd.drawString(line3, 10, 166)


def _try_ota():
    import network
    import time

    try:
        from overlap import config
    except Exception as e:
        print('boot: config import hiba ({}) — OTA kihagyva'.format(e))
        return

    repos = getattr(config, 'OTA_REPOS', None)
    if not repos:
        return

    # LCD inicializálás státuszkijelzőhöz
    lcd = None
    try:
        import M5
        M5.begin()
        lcd = M5.Lcd
    except Exception:
        pass

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        if not getattr(config, 'WIFI_SSID', ''):
            return

        if lcd:
            _lcd_status(lcd, 'WiFi: {}'.format(config.WIFI_SSID), 'Csatlakozas...')
        print('boot: WiFi csatlakozás OTA-hoz ({})...'.format(config.WIFI_SSID))

        wlan.connect(config.WIFI_SSID, config.WIFI_PASS)
        t = time.ticks_ms()
        last_dot = 0
        dots = 0
        while not wlan.isconnected():
            elapsed = time.ticks_diff(time.ticks_ms(), t)
            if elapsed > 15000:
                if lcd:
                    _lcd_status(lcd, 'WiFi timeout', 'OTA kihagyva', 'Indul az app...')
                    time.sleep_ms(800)
                print('boot: WiFi timeout — OTA kihagyva')
                return
            # Másodpercenként frissíti a kijelzőt
            if lcd and time.ticks_diff(time.ticks_ms(), last_dot) > 1000:
                dots = (dots % 5) + 1
                remaining = (15000 - elapsed) // 1000
                _lcd_status(lcd,
                    'WiFi: {}'.format(config.WIFI_SSID),
                    'Csatlakozas' + '.' * dots,
                    '{}s mulva kihagyja'.format(remaining))
                last_dot = time.ticks_ms()
            time.sleep_ms(200)

    if lcd:
        _lcd_status(lcd, 'WiFi: OK', 'GitHub ellenorzes...')
    print('boot: OTA ellenőrzés...')

    from ota import OTAUpdater
    ota = OTAUpdater(repos)
    if ota.check_and_update():
        if lcd:
            _lcd_status(lcd, 'Frissites kesz!', 'Ujraindul...')
            time.sleep_ms(800)
        print('boot: frissítés kész — reboot')
        import machine
        time.sleep_ms(300)
        machine.reset()
    else:
        if lcd:
            _lcd_status(lcd, 'Nincs ujabb verzio', 'Indul az app...')
            time.sleep_ms(600)
        print('boot: nincs frissítés')


try:
    _try_ota()
except Exception as e:
    print('boot: OTA hiba (kihagyva) —', type(e).__name__, e)
