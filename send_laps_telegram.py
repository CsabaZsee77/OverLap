"""Send logged laps from session log file to Telegram."""
import json
import requests

BOT_TOKEN = '8630230971:AAFe_XwgznHmNfzE5Kq_P7kcD7-DFkGZUHs'
CHAT_ID   = '8133479839'
TRACK_NAME = 'Kakucs Ring'

SESSION_DATA = r'C:\Users\zsigm\OneDrive\Dokumentumok\GitHub\MotoMeter\session_log.json'

def fmt_time(ms):
    m = ms // 60000
    s = (ms % 60000) / 1000.0
    return '{}:{:06.3f}'.format(m, s)

def send_text(text):
    url = 'https://api.telegram.org/bot{}/sendMessage'.format(BOT_TOKEN)
    r = requests.post(url, json={'chat_id': CHAT_ID, 'text': text})
    return r.status_code == 200

def send_laps(laps):
    best_ms = min(l['lap_time_ms'] for l in laps if l['lap_time_ms'] < 120000)
    prev_ms = None
    ok_count = 0

    for lap in laps:
        n  = lap['lap_number']
        ms = lap['lap_time_ms']

        # Skip obvious outliers (pit stops, safety car, >2 min)
        if ms > 120000:
            print(f'Kor #{n}: KIHAGYVA ({fmt_time(ms)} - outlier)')
            prev_ms = None
            continue

        is_best = (ms == best_ms)

        lines = ['MotoMeter - {}'.format(TRACK_NAME)]
        lines.append('')
        lines.append('Kor #{}: {}{}'.format(n, fmt_time(ms), '  LEGJOBB!' if is_best else ''))

        if prev_ms and not is_best:
            delta = ms - prev_ms
            sign  = '+' if delta >= 0 else '-'
            lines.append('Delta: {}{:.3f}s'.format(sign, abs(delta) / 1000.0))

        text = '\n'.join(lines)
        ok = send_text(text)
        status = 'OK' if ok else 'HIBA'
        print(f'Kor #{n}: {fmt_time(ms)} [{status}]')
        if ok:
            ok_count += 1
        prev_ms = ms

    return ok_count


if __name__ == '__main__':
    laps = [
        {"lap_number": 1,  "lap_time_ms": 58578},
        {"lap_number": 2,  "lap_time_ms": 57494},
        {"lap_number": 3,  "lap_time_ms": 57601},
        {"lap_number": 4,  "lap_time_ms": 57833},
        {"lap_number": 5,  "lap_time_ms": 58015},
        {"lap_number": 6,  "lap_time_ms": 57092},
        {"lap_number": 7,  "lap_time_ms": 57182},
        {"lap_number": 8,  "lap_time_ms": 57624},
        {"lap_number": 9,  "lap_time_ms": 57450},
        {"lap_number": 10, "lap_time_ms": 58190},
        {"lap_number": 11, "lap_time_ms": 188141},  # outlier
        {"lap_number": 12, "lap_time_ms": 62526},
        {"lap_number": 13, "lap_time_ms": 59589},
        {"lap_number": 14, "lap_time_ms": 60358},
        {"lap_number": 15, "lap_time_ms": 61420},
        {"lap_number": 16, "lap_time_ms": 61966},
        {"lap_number": 17, "lap_time_ms": 60244},
        {"lap_number": 18, "lap_time_ms": 61128},
        {"lap_number": 19, "lap_time_ms": 60292},
        {"lap_number": 20, "lap_time_ms": 62844},
        {"lap_number": 21, "lap_time_ms": 63781},
        {"lap_number": 22, "lap_time_ms": 63487},
        {"lap_number": 23, "lap_time_ms": 62384},
        {"lap_number": 24, "lap_time_ms": 62694},
        {"lap_number": 25, "lap_time_ms": 62204},
        {"lap_number": 26, "lap_time_ms": 63391},
        {"lap_number": 27, "lap_time_ms": 62353},
        {"lap_number": 28, "lap_time_ms": 63110},
        {"lap_number": 29, "lap_time_ms": 62765},
        {"lap_number": 30, "lap_time_ms": 62322},
        {"lap_number": 31, "lap_time_ms": 62371},
        {"lap_number": 32, "lap_time_ms": 62988},
        {"lap_number": 33, "lap_time_ms": 63085},
    ]

    print(f'Kuldes: {len(laps)} kor -> Telegram')
    sent = send_laps(laps)
    print(f'\nElkuldve: {sent}/32 uzenet (1 outlier kihagyva)')
