# track_sync.py — Pályakonfiguráció szinkronizálás a szerverről
# Letölti a /api/tracks/{id}/firmware-json végpontot és menti
# /flash/track.json-ba, hogy a track_loader betölthesse.

import json

_TARGET = '/flash/track.json'


def sync(backend_url, track_id, timeout_ms=8000):
    """
    Letölti a track.json-t a szerverről.
    Returns: True ha sikerült, False ha hiba.

    Args:
        backend_url : pl. 'http://46.225.12.228:8080'
        track_id    : pálya ID a szerveren (int)
        timeout_ms  : max várakozás ms-ban
    """
    if not backend_url or not track_id:
        return False

    url = '{}/api/tracks/{}/firmware-json'.format(backend_url.rstrip('/'), track_id)
    print('TrackSync: letöltés → {}'.format(url))

    try:
        import urequests
        r = urequests.get(url)
        if r.status_code != 200:
            print('TrackSync: HTTP {} hiba'.format(r.status_code))
            r.close()
            return False

        data = r.text
        r.close()

        # Validáció: JSON parse + finish_line megléte
        parsed = json.loads(data)
        if 'finish_line' not in parsed:
            print('TrackSync: hiányzó finish_line a letöltött adatból')
            return False

        with open(_TARGET, 'w') as f:
            f.write(data)

        print('TrackSync: OK → {} ({} bájt)'.format(_TARGET, len(data)))
        return True

    except OSError as e:
        print('TrackSync: hálózati hiba —', e)
        return False
    except Exception as e:
        print('TrackSync: hiba —', e)
        return False


def wait_wifi(wlan, timeout_ms=10000):
    """Vár amíg a WiFi csatlakozik, max timeout_ms ms-ig."""
    import time
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while not wlan.isconnected():
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
            return False
        time.sleep_ms(200)
    return True
