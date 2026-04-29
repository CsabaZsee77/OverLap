#!/bin/bash
# deploy.sh — MotoMeter Hetzner deploy script
#
# Előfeltételek a szerveren:
#   - Docker + Docker Compose telepítve
#   - domain DNS → szerver IP beállítva
#   - .env fájl kitöltve (.env.example alapján)
#
# Első telepítés:
#   chmod +x deploy.sh && ./deploy.sh --first-run
#
# Update (kód push után):
#   ./deploy.sh

set -e

DOMAIN=${DOMAIN:-"motometer.yourdomain.com"}
EMAIL=${CERTBOT_EMAIL:-"your@email.com"}

echo "==> MotoMeter deploy: $DOMAIN"

# ── Let's Encrypt (csak --first-run esetén) ───────────────────────────────────
if [[ "$1" == "--first-run" ]]; then
    echo "==> Let's Encrypt cert kérése..."
    docker run --rm \
        -p 80:80 \
        -v /etc/letsencrypt:/etc/letsencrypt \
        certbot/certbot certonly \
        --standalone \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        -d "$DOMAIN"
    echo "==> Cert OK"
fi

# ── Docker build + indítás ────────────────────────────────────────────────────
echo "==> Docker build..."
docker compose build --no-cache

echo "==> Konténerek indítása..."
docker compose up -d

echo "==> Státusz:"
docker compose ps

echo ""
echo "✓ MotoMeter fut: https://$DOMAIN"
echo "  API docs:       https://$DOMAIN/docs"

# ── Auto-renewal cron (első telepítésnél) ────────────────────────────────────
if [[ "$1" == "--first-run" ]]; then
    CRON_JOB="0 3 * * * certbot renew --quiet && docker compose -f $(pwd)/docker-compose.yml restart nginx"
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "==> Certbot auto-renewal cron hozzáadva (naponta 03:00)"
fi
