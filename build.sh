#!/usr/bin/env bash
# build.sh
# Gera um executável único do gesture-control usando PyInstaller.
# O binário final fica em dist/gesture-control
# Execute: bash build.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SCRIPT_DIR}/.venv"
DIST="${SCRIPT_DIR}/dist"

echo "=== Build — Gesture Control ==="

# ── Instalar PyInstaller no venv ──────────────────────────────────────────────
echo "[1/3] Instalando PyInstaller e evdev..."
"${VENV}/bin/pip" install --quiet pyinstaller evdev

# ── Gerar executável ──────────────────────────────────────────────────────────
echo "[2/3] Compilando executável..."

cd "${SCRIPT_DIR}"

"${VENV}/bin/pyinstaller" \
    --onefile \
    --name gesture-control \
    --add-data "gestures/custom.json:gestures" \
    --hidden-import evdev \
    --hidden-import mediapipe \
    --hidden-import cv2 \
    --hidden-import pystray \
    --hidden-import PIL \
    --noconfirm \
    --clean \
    tray_icon.py

# ── Configurar permissões e atalho ────────────────────────────────────────────
echo "[3/3] Configurando permissões..."

chmod +x "${DIST}/gesture-control"

# Atualiza o .desktop para apontar para o binário compilado
DESKTOP_FILE="${HOME}/.local/share/applications/gesture-control.desktop"
if [ -f "${DESKTOP_FILE}" ]; then
    sed -i "s|Exec=.*|Exec=${DIST}/gesture-control|" "${DESKTOP_FILE}"
    echo "  .desktop atualizado → ${DIST}/gesture-control"
fi

echo ""
echo "=== Build concluído! ==="
echo ""
echo "Executável: ${DIST}/gesture-control"
echo ""
echo "Para rodar:"
echo "  ${DIST}/gesture-control"
echo ""
echo "Ou procure 'Gesture Control' no launcher de aplicativos."
echo ""
echo "NOTA: O executável lê o custom.json embutido."
echo "Para alterar gestos após o build, edite gestures/custom.json"
echo "e rode bash build.sh novamente."
