#!/usr/bin/env bash
# Prepara y arranca la demostración de ComParte en macOS/Linux.
#
#   ./scripts/demo.sh                 # hora de demo 16:00, datos recién cargados, puerto 8000
#   HORA=15:30 PUERTO=8080 ./scripts/demo.sh
#
# Crea el entorno virtual si no existe, instala dependencias, recarga los datos de prueba, fija la hora de
# la aplicación (así el video no depende de la hora real) y arranca el servidor.
set -euo pipefail
cd "$(dirname "$0")/.."

HORA="${HORA:-16:00}"
PUERTO="${PUERTO:-8000}"
VENV="${COMPARTE_VENV:-.venv}"

[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet -r requirements.txt

echo "Abre http://127.0.0.1:${PUERTO}  (Ctrl+C para detener)"
exec "$VENV/bin/python" -m comparte servir --puerto "$PUERTO" --hora-demo "$HORA" --reiniciar
