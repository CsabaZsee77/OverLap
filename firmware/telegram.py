# telegram.py - Telegram Bot értesítések köridő eredményekhez
# OverLAP v1.2 - M5Stack CoreS3
#
# Beállítás (config.py):
#   TELEGRAM_BOT_TOKEN = '7123...:AAF...'   (@BotFather adja)
#   TELEGRAM_CHAT_ID   = '123456789'        (@userinfobot adja)

import json
import math


_API_BASE = 'https://api.telegram.org/bot{}/sendMessage'

_KAMM_SECTORS = [
    (22.5,  'gyorsítás'),
    (67.5,  'gyorsítás + bal kanyar'),
    (112.5, 'bal kanyar'),
    (157.5, 'fékezés + bal kanyar'),
    (202.5, 'fékezés'),
    (247.5, 'fékezés + jobb kanyar'),
    (292.5, 'jobb kanyar'),
    (337.5, 'gyorsítás + jobb kanyar'),
]


def _kamm_sector(angle_deg):
    """Kamm kör szektora az irányvektor szöge alapján.
    0° = gyorsítás, 90° = bal kanyar, 180° = fékezés, 270° = jobb kanyar."""
    a = angle_deg % 360
    for limit, name in _KAMM_SECTORS:
        if a < limit:
            return name
    return 'gyorsítás'


class TelegramNotifier:

    def __init__(self, bot_token, chat_id):
        self._token   = bot_token
        self._chat_id = str(chat_id)
        self._enabled = bool(bot_token and chat_id)

    def is_enabled(self):
        return self._enabled

    def send_lap(self, lap_number, lap_time_ms, delta_ms=None,
                 is_best=False, max_speed_kmh=0.0, sector_times_ms=None,
                 track_name='', prev_lap_ms=None,
                 max_lean_right=0.0, max_lean_left=0.0,
                 peak_kamm_g=0.0, peak_kamm_angle=0.0):
        """Köridő értesítés küldése."""
        if not self._enabled:
            return False

        mins     = lap_time_ms // 60000
        secs     = (lap_time_ms % 60000) / 1000.0
        time_str = '{:d}:{:06.3f}'.format(mins, secs)

        lines = []
        lines.append('OverLAP - {}'.format(track_name) if track_name else 'OverLAP')
        lines.append('')
        lines.append('Kor #{}: {}{}'.format(
            lap_number, time_str, '  LEGJOBB!' if is_best else ''))

        if delta_ms is not None and delta_ms != 0:
            sign = '+' if delta_ms > 0 else ''
            lines.append('Delta: {}{:.3f}s (vs legjobb)'.format(
                sign, delta_ms / 1000.0))

        lines.append('')

        if max_speed_kmh:
            lines.append('Max sebesseg: {:.0f} km/h'.format(max_speed_kmh))

        if max_lean_right or max_lean_left:
            lines.append('Max doles: Bal {:.0f}  Jobb {:.0f}'.format(
                max_lean_left, max_lean_right))

        if peak_kamm_g > 0.05:
            sector = _kamm_sector(peak_kamm_angle)
            lines.append('Max Kamm: {:.2f}G ({})'.format(peak_kamm_g, sector))

        if sector_times_ms:
            lines.append('')
            for i, st in enumerate(sector_times_ms):
                if st:
                    sm = st // 60000
                    ss = (st % 60000) / 1000.0
                    lines.append('  S{}: {:d}:{:06.3f}'.format(i + 1, sm, ss))

        text = '\n'.join(lines)
        return self._send(text)

    def send_text(self, text):
        """Szabad szöveges üzenet."""
        if not self._enabled:
            return False
        return self._send(text)

    def _send(self, text):
        url  = _API_BASE.format(self._token)
        body = json.dumps({'chat_id': self._chat_id, 'text': text})

        try:
            import requests
            resp = requests.post(
                url,
                json={'chat_id': self._chat_id, 'text': text},
            )
            ok = resp.status_code == 200
            resp.close()
            if ok:
                print("Telegram: uzenet elkuldve")
            else:
                print("Telegram: HTTP hiba", resp.status_code)
            return ok
        except Exception as e:
            print("Telegram: requests hiba ->", type(e).__name__, e)

        try:
            import socket, ssl
            host = 'api.telegram.org'
            path = '/bot{}/sendMessage'.format(self._token)
            req = ('POST {} HTTP/1.0\r\n'
                   'Host: {}\r\n'
                   'Content-Type: application/json\r\n'
                   'Content-Length: {}\r\n'
                   'Connection: close\r\n\r\n'
                   '{}').format(path, host, len(body), body)
            s = socket.socket()
            s.connect(socket.getaddrinfo(host, 443)[0][-1])
            s = ssl.wrap_socket(s, server_hostname=host)
            s.write(req.encode())
            resp_data = b''
            while True:
                chunk = s.read(256)
                if not chunk:
                    break
                resp_data += chunk
            s.close()
            ok = b'200 OK' in resp_data or b'"ok":true' in resp_data
            print("Telegram: socket", "OK" if ok else "HIBA")
            return ok
        except Exception as e2:
            print("Telegram: socket hiba ->", type(e2).__name__, e2)
            return False
