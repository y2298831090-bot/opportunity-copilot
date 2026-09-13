#!/bin/zsh
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
URL="http://127.0.0.1:8501"

if ! curl --silent --fail "$URL" >/dev/null 2>&1; then
  cd "$PROJECT_DIR"
  nohup python3 -m streamlit run app.py --server.headless true --server.port 8501 --server.fileWatcherType none \
    > /tmp/opportunity-copilot-streamlit.log 2>&1 &
  for _ in {1..20}; do
    sleep 1
    if curl --silent --fail "$URL" >/dev/null 2>&1; then
      break
    fi
  done
fi

open "$URL"
