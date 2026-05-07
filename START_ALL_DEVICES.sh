#!/bin/bash
# Start all three OnStepX Alpaca devices in single process
cd "$(dirname "$0")/device"
python3 app.py
