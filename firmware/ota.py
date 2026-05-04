# ota.py - Általános OTA frissítő MicroPython eszközökhöz
#
# Telepítés: mpremote cp firmware/ota.py :/flash/ota.py
# (USB-n kell telepíteni, OTA maga nem frissíti önmagát)
#
# Konfiguráció (config.py-ban):
#   OTA_REPOS = [
#       {
#           'repo':   'Owner/Repo',        # GitHub repo (privát is)
#           'branch': 'main',
#           'token':  'ghp_...',           # Personal Access Token (read:contents)
#           'subdir': 'firmware',          # repo-n belüli mappa amit szinkronizálunk
#           'target': '/flash/overlap/',   # device-on a célmappa
#           'skip':   ['config.py', 'ota.py', 'boot.py'],
#       },
#   ]

import json
import os


class OTAUpdater:

    def __init__(self, repos, state_path='/flash/ota_state.json'):
        self._repos      = repos
        self._state_path = state_path
        self._state      = _load_json(state_path) or {}

    def check_and_update(self):
        """
        Ellenőrzi az összes konfigurált repót.
        Returns True ha legalább egy fájl frissült (reboot szükséges).
        """
        updated = False
        for cfg in self._repos:
            repo = cfg.get('repo', '?')
            try:
                if self._update_one(cfg):
                    updated = True
            except Exception as e:
                print('OTA [{}]: hiba — {} {}'.format(repo, type(e).__name__, e))
        return updated

    def _update_one(self, cfg):
        repo   = cfg['repo']
        branch = cfg.get('branch', 'main')
        token  = cfg['token']
        subdir = cfg.get('subdir', 'firmware')
        target = cfg.get('target', '/flash/')
        skip   = set(cfg.get('skip', ['config.py', 'ota.py', 'boot.py']))

        # GitHub Contents API: könyvtár tartalmának lekérése (fájlnév + SHA)
        remote = _github_dir(repo, branch, subdir, token)
        if remote is None:
            print('OTA [{}]: API elérési hiba'.format(repo))
            return False

        local = self._state.get(repo, {})
        changed = [
            (f['path'], f['sha'], f['name'])
            for f in remote
            if f.get('type') == 'file' and f['name'] not in skip
            and local.get(f['path']) != f['sha']
        ]

        if not changed:
            print('OTA [{}]: nincs újabb verzió'.format(repo))
            return False

        print('OTA [{}]: {} fájl frissül'.format(repo, len(changed)))

        _ensure_dir(target)

        for path, sha, name in changed:
            dest = target + name
            print('OTA: {} letöltés...'.format(name))
            ok = _github_raw_to_file(repo, branch, path, token, dest)
            if not ok:
                print('OTA: {} letöltési hiba — leállítva'.format(name))
                return False
            local[path] = sha
            print('OTA: {} → {} OK'.format(name, dest))

        self._state[repo] = local
        _save_json(self._state_path, self._state)
        return True


# ------------------------------------------------------------------
# GitHub HTTPS segédfüggvények
# ------------------------------------------------------------------

def _github_dir(repo, branch, subdir, token):
    """Könyvtár tartalmának lekérése a GitHub Contents API-n."""
    host = 'api.github.com'
    path = '/repos/{}/contents/{}?ref={}'.format(repo, subdir, branch)
    headers = {
        'Authorization': 'token ' + token,
        'User-Agent':    'mp-ota/1.0',
        'Accept':        'application/vnd.github.v3+json',
    }
    status, body = _https_get(host, path, headers)
    if status != 200 or body is None:
        print('OTA dir API: HTTP', status)
        return None
    try:
        return json.loads(body)
    except Exception as e:
        print('OTA dir JSON parse hiba:', e)
        return None


def _github_raw_to_file(repo, branch, path, token, dest_path):
    """Fájl tartalmának streaming letöltése közvetlenül flash-re (memóriabarát)."""
    import socket
    import ssl

    host     = 'raw.githubusercontent.com'
    url_path = '/{}/{}/{}'.format(repo, branch, path)
    req = (
        'GET {} HTTP/1.0\r\n'
        'Host: {}\r\n'
        'Authorization: token {}\r\n'
        'User-Agent: mp-ota/1.0\r\n'
        'Connection: close\r\n\r\n'
    ).format(url_path, host, token)

    s = None
    try:
        s = socket.socket()
        s.settimeout(20)
        s.connect(socket.getaddrinfo(host, 443)[0][-1])
        s = ssl.wrap_socket(s, server_hostname=host)
        s.write(req.encode())

        # HTTP fejléc kiolvasása
        status = None
        while True:
            line = s.readline()
            if not line or line == b'\r\n':
                break
            decoded = line.decode().strip()
            if decoded.startswith('HTTP/'):
                status = int(decoded.split(' ')[1])

        if status != 200:
            print('OTA raw HTTP:', status)
            return False

        # Body streamelése fájlba (512 byte-os darabokban)
        with open(dest_path, 'wb') as f:
            while True:
                chunk = s.read(512)
                if not chunk:
                    break
                f.write(chunk)
        return True

    except Exception as e:
        print('OTA raw letöltési hiba:', e)
        return False
    finally:
        if s:
            try:
                s.close()
            except Exception:
                pass


def _https_get(host, path, headers):
    """
    HTTPS GET, visszaad (status_code, body_bytes).
    Max 16 KB body — elegendő a GitHub dir API válaszhoz.
    """
    import socket
    import ssl

    req = 'GET {} HTTP/1.0\r\nHost: {}\r\n'.format(path, host)
    for k, v in headers.items():
        req += '{}: {}\r\n'.format(k, v)
    req += 'Connection: close\r\n\r\n'

    s = None
    try:
        s = socket.socket()
        s.settimeout(20)
        s.connect(socket.getaddrinfo(host, 443)[0][-1])
        s = ssl.wrap_socket(s, server_hostname=host)
        s.write(req.encode())

        # Fejléc beolvasása soronként (nem tárolja az egészet)
        status = None
        while True:
            line = s.readline()
            if not line or line == b'\r\n':
                break
            try:
                decoded = line.decode().strip()
            except Exception:
                decoded = ''
            if decoded.startswith('HTTP/'):
                try:
                    status = int(decoded.split(' ')[1])
                except Exception:
                    pass

        if status is None:
            return None, None

        # Body beolvasása max 16 KB-ig
        body = bytearray()
        while len(body) < 16384:
            chunk = s.read(1024)
            if not chunk:
                break
            body.extend(chunk)

        return status, bytes(body)

    except Exception as e:
        print('OTA HTTPS hiba:', e)
        return None, None
    finally:
        if s:
            try:
                s.close()
            except Exception:
                pass


# ------------------------------------------------------------------
# Segédfüggvények
# ------------------------------------------------------------------

def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _save_json(path, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print('OTA state mentési hiba:', e)


def _ensure_dir(path):
    path = path.rstrip('/')
    try:
        os.listdir(path)
    except OSError:
        try:
            os.mkdir(path)
        except Exception:
            pass
