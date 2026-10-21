#!/bin/sh
# /startup/ha-mdns-macvlan-route.sh

set -e

echo "[ha-mdns] Configuring mDNS route via macvlan interface..."

# Required env vars
: "${MACVLAN_PREFIX:?Set MACVLAN_PREFIX in the private environment}"

HA_IP="${MACVLAN_PREFIX}.242"

echo "[ha-mdns] Target HA IP: $HA_IP"

# Find the interface that owns the exact HA IP
IFACE="$(ip -o -4 addr show | awk -v ip="$HA_IP" '$4 ~ ("^" ip "/") {print $2; exit}')"

if [ -z "$IFACE" ]; then
  echo "[ha-mdns] ERROR: Could not find interface owning $HA_IP" >&2
  ip -o -4 addr show
  exit 1
fi

echo "[ha-mdns] Using interface: $IFACE for mDNS"

# IPv4 mDNS
ip route replace 224.0.0.251/32 dev "$IFACE" scope link

# IPv6 mDNS (Apple *will* use this)
ip -6 route replace ff02::fb dev "$IFACE" metric 0 || true

echo "[ha-mdns] Current IPv4 mDNS route:"
ip route show 224.0.0.251 || true

echo "[ha-mdns] Current IPv6 mDNS route:"
ip -6 route show ff02::fb || true

echo "[ha-mdns] mDNS routing configured successfully."
