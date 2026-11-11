#!/bin/bash
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python iniciar_demo.py "$@"
fi
exec python3 iniciar_demo.py "$@"
