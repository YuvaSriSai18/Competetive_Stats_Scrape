# #!/bin/bash
# set -e

# echo "Installing Python dependencies..."
# pip install -r requirements.txt

# echo "Installing Playwright browsers..."
# playwright install chromium

# echo "Build complete!"


#!/usr/bin/env bash
set -e

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Installing Playwright browsers..."
playwright install chromium --with-deps

echo "Build complete!"
