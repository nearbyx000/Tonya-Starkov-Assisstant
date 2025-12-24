#!/bin/bash

# Configuration
SERVER_IP="100.0.0.2"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- HARDWARE INIT ---
echo "Initializing Robot Hardware..."
# Hardware commands added here:
mbctl daemon start
mbctl chip start
sleep 5

# --- NETWORK WAIT ---
echo "Waiting for Server ($SERVER_IP)..."
while ! ping -c 1 -W 1 $SERVER_IP > /dev/null; do
    sleep 2
done

# --- CLIENT LOOP ---
cd "$DIR"
while true; do
    echo "Starting Tonya Client..."
    python3 client.py
    echo "Client stopped. Restarting in 3s..."
    sleep 3
done