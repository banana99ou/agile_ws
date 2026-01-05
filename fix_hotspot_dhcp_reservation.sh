#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Configure a DHCP reservation for NetworkManager "shared" hotspot (dnsmasq).

This writes a dnsmasq snippet to:
  /etc/NetworkManager/dnsmasq-shared.d/99-hotspot-dhcp-reservations.conf

Then restarts the hotspot connection (default: LIMO_AP).

Usage:
  sudo bash fix_hotspot_dhcp_reservation.sh --mac AA:BB:CC:DD:EE:FF --ip 10.42.0.50 [--name macbook] [--con LIMO_AP]

Notes:
  - The hotspot subnet here is typically 10.42.0.0/24 with gateway 10.42.0.1.
  - If your Mac uses "Private Wi‑Fi Address" / MAC randomization, the MAC may change and the reservation won't be stable.
EOF
}

CON_NAME="LIMO_AP"
HOST_NAME="client"
MAC=""
IP=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --con) CON_NAME="${2:-}"; shift 2;;
    --name) HOST_NAME="${2:-}"; shift 2;;
    --mac) MAC="${2:-}"; shift 2;;
    --ip) IP="${2:-}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [[ -z "$MAC" || -z "$IP" ]]; then
  echo "ERROR: --mac and --ip are required." >&2
  usage
  exit 2
fi

# Basic input validation
if ! [[ "$MAC" =~ ^([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}$ ]]; then
  echo "ERROR: Invalid MAC format: $MAC" >&2
  exit 2
fi
if ! [[ "$IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "ERROR: Invalid IPv4 format: $IP" >&2
  exit 2
fi

CONF_DIR="/etc/NetworkManager/dnsmasq-shared.d"
CONF_FILE="${CONF_DIR}/99-hotspot-dhcp-reservations.conf"
LINE="dhcp-host=${MAC},${IP},${HOST_NAME},infinite"

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: Please run as root (use sudo)." >&2
  exit 1
fi

mkdir -p "$CONF_DIR"
touch "$CONF_FILE"

# Remove any existing reservation lines for the same MAC (keep other reservations)
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
grep -v -i -E "^dhcp-host=${MAC}," "$CONF_FILE" > "$tmp" || true
{
  cat "$tmp"
  echo "$LINE"
} > "$CONF_FILE"

echo "Wrote reservation:"
echo "  $LINE"
echo "to:"
echo "  $CONF_FILE"

echo
echo "Restarting hotspot connection: $CON_NAME"
nmcli connection show "$CON_NAME" >/dev/null
nmcli connection down "$CON_NAME" || true
nmcli connection up "$CON_NAME"

echo
echo "Done. If the client is already connected, disconnect/reconnect Wi‑Fi on the client to pick up the reserved IP."


