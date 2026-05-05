# track_sync.py — Pályakonfiguráció szinkronizálás a szerverről
# sync()           : egy pálya letöltése (boot-time, ACTIVE_TRACK_ID alapján)
# sync_all()       : összes pálya letöltése → helyi cache
# load_cache()     : helyi cache beolvasása (offline, WiFi nélkül)

import json

_ACTIVE  = '/flash/track.json'
_CACHE   = '/flash/tracks_cache.json'


def _http_get(url):
    """urequests vagy requests — M5Stack és standard MicroPython kompatibilis."""
    try:
        import urequests
        return urequests.get(url)
    except ImportError:
        import requests
        return requests.get(url)


def sync(backend_url, track_id):
    """Letölti az adott pálya firmware-json-ját → /flash/track.json."""
    if not backend_url or not track_id:
        return False
    url = '{}/api/tracks/{}/firmware-json'.format(backend_url.rstrip('/'), track_id)
    print('TrackSync: letöltés → {}'.format(url))
    try:
        r = _http_get(url)
        if r.status_code != 200:
            print('TrackSync: HTTP {} hiba'.format(r.status_code))
            r.close()
            return False
        data = r.text
        r.close()
        parsed = json.loads(data)
        if 'finish_line' not in parsed:
            print('TrackSync: hiányzó finish_line')
            return False
        with open(_ACTIVE, 'w') as f:
            f.write(data)
        print('TrackSync: OK → {}'.format(_ACTIVE))
        return True
    except Exception as e:
        print('TrackSync: hiba —', e)
        return False


def sync_all(backend_url):
    """
    Letölti az összes pályát a szerverről → /flash/tracks_cache.json.
    A track select screen ebből olvas, WiFi nélkül is.
    Returns: letöltött pályák száma (0 = hiba).
    """
    if not backend_url:
        return 0
    try:
        # 1. Lista
        r = _http_get(backend_url.rstrip('/') + '/api/tracks/')
        if r.status_code != 200:
            print('TrackSync sync_all: lista hiba HTTP {}'.format(r.status_code))
            r.close()
            return 0
        track_list = r.json()
        r.close()

        # 2. Minden pálya teljes adata
        full = []
        for t in track_list:
            tid = t.get('id')
            if not tid:
                continue
            try:
                r2 = _http_get(
                    backend_url.rstrip('/') + '/api/tracks/{}/firmware-json'.format(tid)
                )
                if r2.status_code == 200:
                    d = r2.json()
                    d['_id'] = tid
                    full.append(d)
                    print('TrackSync: OK — {}'.format(d.get('name', tid)))
                r2.close()
            except Exception as e:
                print('TrackSync: {} hiba —'.format(tid), e)

        if not full:
            return 0

        with open(_CACHE, 'w') as f:
            json.dump(full, f)
        print('TrackSync sync_all: {} palya cache-elve → {}'.format(len(full), _CACHE))
        return len(full)

    except Exception as e:
        print('TrackSync sync_all hiba —', e)
        return 0


def load_cache():
    """Helyi cache beolvasása. Returns: lista vagy None."""
    try:
        with open(_CACHE, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def wait_wifi(wlan, timeout_ms=10000):
    """Vár amíg a WiFi csatlakozik, max timeout_ms ms-ig."""
    import time
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while not wlan.isconnected():
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
            return False
        time.sleep_ms(200)
    return True
