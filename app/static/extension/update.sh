#!/bin/bash
# update.sh — Copia l'estensione aggiornata nella tua cartella Chrome Extensions
# Uso: ./update.sh [percorso/cartella/destinazione]
#
# Esempio:
#   ./update.sh ~/Desktop/spl-extension
#   ./update.sh /Users/nome/chrome-extensions/spl

set -e

DEST="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "$DEST" ]; then
  echo "Uso: $0 <cartella destinazione>"
  echo ""
  echo "Esempio:"
  echo "  $0 ~/Desktop/spl-extension"
  exit 1
fi

echo "→ Copia extension/ in: $DEST"
mkdir -p "$DEST"
cp -r "$SCRIPT_DIR"/. "$DEST"/
rm -f "$DEST/update.sh"   # non serve nella cartella Chrome

echo "✓ Fatto! Ora vai su chrome://extensions/ e clicca il tasto ↺ su Silicon Psyche."
