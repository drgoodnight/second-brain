#!/bin/bash
# Renew the Tailscale TLS cert that Caddy serves for iOS CalDAV sync.
# Must run as root — `tailscale cert` requires it.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERTS="$PROJECT_DIR/data/caddy/certs"
SRC=/var/snap/tailscale/common/certs

source "$PROJECT_DIR/.env"
DOMAIN="${TAILSCALE_DOMAIN:?TAILSCALE_DOMAIN not set in .env}"
OWNER="${CERT_OWNER:-cypherdoc}"

# Snap-confined tailscale cannot export to an arbitrary path. The error is
# expected and harmless — the cert is still refreshed in tailscale's own store.
tailscale cert "$DOMAIN" 2>/dev/null || true

cp "$SRC/$DOMAIN.crt" "$CERTS/$DOMAIN.crt"
cp "$SRC/$DOMAIN.key" "$CERTS/$DOMAIN.key"
chown -R "$OWNER:$OWNER" "$CERTS"
chmod 600 "$CERTS/$DOMAIN.key"
docker restart caddy

echo "$(date -Is) renewed — $(openssl x509 -enddate -noout -in "$CERTS/$DOMAIN.crt")"
