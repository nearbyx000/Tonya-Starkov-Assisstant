#!/bin/bash

# Configuration
SERVER_IP="192.168.3.115"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Wait for Network & Server
echo "Waiting for server at $SERVER_IP..."
while ! ping -c 1 -W 1 $SERVER_IP > /dev/null; do
    sleep 2
done

# Run Client (Auto-restart on crash)
cd "$DIR"
while true; do
    echo "Starting Client..."
    python3 client.py
    echo "Client crashed/stopped. Restarting in 3s..."
    sleep 3
done