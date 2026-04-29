# uplink.py - WiFi HTTP uplink a MotoMeter backendhez
# MotoMeter v0.1 - M5Stack CoreS3
#
# Feladat:
#   - Session adatok feltöltése a backend /api/sessions/upload végpontra
#   - In-memory kör-sor (aktuális session, ~5 kör buffer)
#   - Offline sor: ha nincs WiFi, a logger.py-ba kerül az adat;
#     WiFi visszatérésekor a logger.py pendingből is feltölt
#   - Retry logika: 3 próbálkozás, exponenciális backoff
#
# Backend végpont: POST /api/sessions/upload
# Payload: SessionUpload JSON (lásd backend/schemas.py)
#
# MicroPython HTTP: urequests modul (M5Stack beépített)

import json
import time


# Retry konfiguráció
MAX_RETRIES   = 3
RETRY_DELAY_S = [2, 5, 15]   # egyre növekvő várakozás


class Uplink:
    """
    WiFi HTTP uplink manager.

    Publikus API:
        set_backend_url(url)
        upload_session(session_dict)      → bool (sikeres-e)
        flush_pending_from_logger(logger) → int (feltöltött fájlok száma)
    """

    def __init__(self, backend_url=''):
        self._url = backend_url.rstrip('/') if backend_url else ''

    def set_backend_url(self, url):
        self._url = url.rstrip('/')

    # ------------------------------------------------------------------
    # Session feltöltés
    # ------------------------------------------------------------------

    def upload_session(self, session_dict):
        """
        Egy session feltöltése a backendbe.

        session_dict: logger.py által mentett dict (vagy in-memory sor)
        Returns: True ha sikeres, False ha minden próbálkozás meghiúsult.
        """
        if not self._url:
            print("Uplink: nincs backend URL — feltöltés kihagyva")
            return False

        # _uploaded és _ts belső mezőket kiszűrjük
        payload = _strip_internal(session_dict)

        endpoint = self._url + '/api/sessions/upload'
        body     = json.dumps(payload)

        for attempt in range(MAX_RETRIES):
            try:
                import urequests
                resp = urequests.post(
                    endpoint,
                    data=body,
                    headers={'Content-Type': 'application/json'},
                )
                status = resp.status_code
                resp.close()

                if 200 <= status < 300:
                    print("Uplink: feltöltve (HTTP {})".format(status))
                    return True
                else:
                    print("Uplink: HTTP hiba {} ({}. kísérlet)".format(
                        status, attempt + 1))

            except Exception as e:
                print("Uplink: hálózati hiba ({}) →".format(attempt + 1), e)

            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY_S[attempt]
                print("Uplink: {}s várakozás...".format(wait))
                time.sleep(wait)

        print("Uplink: SIKERTELEN — offline sor")
        return False

    # ------------------------------------------------------------------
    # Offline sor kiürítése
    # ------------------------------------------------------------------

    def flush_pending_from_logger(self, logger):
        """
        A logger.py-ban várakozó (nem feltöltött) session fájlokat feltölti.
        Sikeres feltöltés után törli a fájlt.

        Returns: feltöltött fájlok száma
        """
        pending = logger.get_pending_files()
        if not pending:
            return 0

        uploaded = 0
        print("Uplink: {} offline session vár feltöltésre".format(len(pending)))

        for path in pending:
            data = logger.load_session(path)
            if data is None:
                continue

            ok = self.upload_session(data)
            if ok:
                logger.mark_uploaded(path)
                uploaded += 1
            else:
                print("Uplink: {} feltöltése sikertelen, következő WiFi-nél újra".format(path))
                break   # ha egy is meghiúsult, megállunk (nincs kapcsolat)

        return uploaded

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self):
        """
        Backend elérhetőség ellenőrzése.
        Returns: True ha a backend válaszol.
        """
        if not self._url:
            return False
        try:
            import urequests
            resp = urequests.get(self._url + '/api/health', timeout=5)
            ok   = resp.status_code == 200
            resp.close()
            return ok
        except Exception:
            return False


# ------------------------------------------------------------------
# Belső segéd
# ------------------------------------------------------------------

def _strip_internal(d):
    """Belső _mezőket és a _uploaded flaget kiveszi a payloadból."""
    result = {}
    for k, v in d.items():
        if k.startswith('_'):
            continue
        result[k] = v
    return result
