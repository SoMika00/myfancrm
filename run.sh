#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8501}"
HOST="${HOST:-0.0.0.0}"

# URL de l'API Sinhome_llm (ex: http://127.0.0.1:8000)
export SINHOME_API_URL="${SINHOME_API_URL:-http://127.0.0.1:8000}"

# Chemin DB SQLite (par défaut: myfancrm/myfancrm.sqlite3)
export MYFANCRM_DB_PATH="${MYFANCRM_DB_PATH:-$(pwd)/myfancrm.sqlite3}"

echo "[MyFanCRM] Starting Streamlit"
echo "- SINHOME_API_URL=$SINHOME_API_URL"
echo "- MYFANCRM_DB_PATH=$MYFANCRM_DB_PATH"
echo "- HOST=$HOST"
echo "- PORT=$PORT"

exec streamlit run streamlit_app.py \
  --server.address "$HOST" \
  --server.port "$PORT" \
  --server.headless true
