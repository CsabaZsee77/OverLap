# boot.py - Auto OTA induláskor + launcher bootstrap
# Telepítés: mpremote cp firmware/boot.py :/flash/boot.py
#            (vagy Thonny-val: /flash/boot.py)
#
# Mit csinál:
#   1. WiFi csatlakozás (max 15s)
#   2. OTA: firmware/ → /flash/overlap/  (csak a változott fájlok)
#   3. Ha /flash/main.py nem a launcher → letölti
#   4. Ha volt változás → reboot

def _try_ota():
    import network
    import time

    try:
        from overlap import config
    except Exception as e:
        print('boot: config hiba — OTA kihagyva:', e)
        return

    repos = getattr(config, 'OTA_REPOS', None)
    if not repos:
        print('boot: OTA_REPOS nincs beállítva')
        return

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        ssid = getattr(config, 'WIFI_SSID', '')
        if not ssid:
            print('boot: WIFI_SSID nincs — OTA kihagyva')
            return
        print('boot: WiFi csatlakozás ({})...'.format(ssid))
        wlan.connect(ssid, config.WIFI_PASS)
        t = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t) > 15000:
                print('boot: WiFi timeout — OTA kihagyva')
                return
            time.sleep_ms(300)

    print('boot: WiFi OK —', wlan.ifconfig()[0])

    # ── Firmware OTA ─────────────────────────────────────────
    from ota import OTAUpdater, _github_raw_to_file
    ota     = OTAUpdater(repos)
    updated = ota.check_and_update()

    # ── Launcher bootstrap ────────────────────────────────────
    # Ha /flash/main.py hiányzik vagy nem a launcher, letöltjük
    launcher_ok = False
    try:
        with open('/flash/main.py') as _f:
            _head = _f.read(300)
        launcher_ok = 'LAUNCHER' in _head or 'run_ota' in _head
    except Exception:
        launcher_ok = False

    if not launcher_ok:
        print('boot: launcher hiányzik — letöltés...')
        cfg = repos[0]
        ok  = _github_raw_to_file(
            cfg['repo'],
            cfg['branch'],
            'launcher/main.py',
            cfg['token'],
            '/flash/main.py',
        )
        if ok:
            print('boot: launcher OK')
            updated = True
        else:
            print('boot: launcher letöltés SIKERTELEN')

    # ── Reboot ha volt változás ───────────────────────────────
    if updated:
        print('boot: frissítés kész — újraindulás...')
        import machine
        import time as _t
        _t.sleep_ms(500)
        machine.reset()
    else:
        print('boot: nincs változás — app indul')


try:
    _try_ota()
except Exception as e:
    print('boot: hiba ({}) — app indul'.format(e))
