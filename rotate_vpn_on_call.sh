#!/bin/bash

SERVERS=(
"/etc/openvpn/be-bru.prod.surfshark.comsurfshark_openvpn_udp.ovpn"
"/etc/openvpn/de-fra.prod.surfshark.comsurfshark_openvpn_udp.ovpn"
"/etc/openvpn/fr-par.prod.surfshark.comsurfshark_openvpn_udp.ovpn"
"/etc/openvpn/nl-ams.prod.surfshark.comsurfshark_openvpn_udp.ovpn"
)



SERVER=${SERVERS[$RANDOM % ${#SERVERS[@]}]}

echo "Switching to $SERVER"

sudo pkill openvpn

sleep 5

sudo openvpn \
  --config "$SERVER" \
  --daemon

sleep 30

IP=$(curl -s ifconfig.me)

echo "New IP: $IP"


