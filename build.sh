# #!/bin/bash
# set -e

# echo "Installing Python dependencies..."
# pip install -r requirements.txt

# echo "Installing Playwright browsers..."
# playwright install chromium

# echo "Build complete!"


#!/usr/bin/env bash
set -e

# Set Playwright browsers path
export PLAYWRIGHT_BROWSERS_PATH=/opt/render/.cache/ms-playwright

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Installing Playwright browsers without system deps..."
python -m playwright install chromium

echo "Verifying Playwright installation..."
python -c "import sys; from playwright.async_api import async_playwright; print('✓ Playwright imported successfully'); sys.exit(0)" || { echo "ERROR: Playwright verification failed"; exit 1; }

echo "Build complete!"
