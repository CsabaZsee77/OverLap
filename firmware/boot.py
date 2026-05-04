# boot.py - OTA ellenőrzés induláskor
# Telepítés: mpremote cp firmware/boot.py :/flash/boot.py
# (USB-n kell telepíteni, OTA maga nem frissíti)
#
# Logika:
#   1. WiFi csatlakozás (max 8s)
#   2. OTA ellenőrzés minden konfigurált repón
#   3. Ha volt frissítés → reboot (az újraindult app már az új kódot futtatja)
#   4. Ha nincs WiFi vagy nincs OTA konfig → silent skip, main.py fut tovább

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

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        if not getattr(config, 'WIFI_SSID', ''):
            return
        print('boot: WiFi csatlakozás OTA-hoz ({})...'.format(config.WIFI_SSID))
        wlan.connect(config.WIFI_SSID, config.WIFI_PASS)
        t = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t) > 8000:
                print('boot: WiFi timeout — OTA kihagyva')
                return
            time.sleep_ms(300)

    print('boot: OTA ellenőrzés...')
    from ota import OTAUpdater
    ota = OTAUpdater(repos)
    if ota.check_and_update():
        print('boot: frissítés kész — reboot')
        import machine
        time.sleep_ms(500)
        machine.reset()
    else:
        print('boot: nincs frissítés')


try:
    _try_ota()
except Exception as e:
    print('boot: OTA hiba (kihagyva) —', type(e).__name__, e)
