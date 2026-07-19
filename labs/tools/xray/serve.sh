#!/usr/bin/env bash
# LLM Stack X-Ray — serve the live visualizer with a same-origin Ollama proxy.
# serve.py does two jobs at once: serves this static page AND forwards
# /ollama/... to your local Ollama server. Same origin, so the page needs
# no tokens and no CORS.
set -euo pipefail

PORT="${PORT:-8010}"
XRAY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_URL="${OLLAMA_HOST_URL:-http://127.0.0.1:11434}"
OLLAMA_UP="$(curl -s --max-time 2 "${OLLAMA_URL}/api/version" 2>/dev/null || echo '')"

echo "┌─────────────────────────────────────────────────────────────"
echo "│  LLM Stack X-Ray · Tokens lens (M1) — more lenses land per module"
echo "│"
echo "│  ollama  : ${OLLAMA_URL}"
if [ -n "${OLLAMA_UP}" ]; then
  echo "│            reachable ✓ ${OLLAMA_UP}"
else
  echo "│            NOT reachable — start Ollama first ('ollama serve'"
  echo "│            or the desktop app), then reload the page"
fi
echo "│"
echo "│  open    : http://127.0.0.1:${PORT}/"
echo "│"
echo "│  Ctrl-C stops the server. Port busy? PORT=8011 bash serve.sh"
echo "└─────────────────────────────────────────────────────────────"

exec python3 "${XRAY_DIR}/serve.py"
