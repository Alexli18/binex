#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
UI_DIR="$ROOT_DIR/ui"
STATIC_DIR="$ROOT_DIR/src/binex/ui/static"

echo "==> Installing frontend dependencies..."
cd "$UI_DIR"
npm ci

echo "==> Building frontend..."
npm run build

echo "==> Copying dist to $STATIC_DIR..."
rm -rf "$STATIC_DIR"
cp -r "$UI_DIR/dist" "$STATIC_DIR"

echo "==> Done. Frontend built and copied to $STATIC_DIR"
