#!/usr/bin/env bash
# install.sh
# Instala dependências e configura o projeto no Pop!_OS / Ubuntu 24.04.
# Execute uma única vez: bash install.sh

set -e

echo "=== Gesture Control — instalação ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

# ── 1. Dependências do sistema ────────────────────────────────────────────────
echo "[1/4] Instalando dependências do sistema..."
sudo apt update -qq
sudo apt install -y \
    python3-pip \
    python3-dev \
    python3-venv \
    python3-full \
    libgirepository1.0-dev \
    libcairo2-dev \
    pkg-config \
    gir1.2-gtk-3.0 \
    gnome-screenshot \
    v4l-utils

# ── 2. Adicionar usuário ao grupo input ───────────────────────────────────────
# Necessário para acessar /dev/uinput (evdev)
echo "[2/4] Adicionando ${USER} ao grupo input..."
sudo usermod -aG input "${USER}"

# Dar permissão ao uinput agora mesmo (sem precisar reiniciar)
sudo chmod 660 /dev/uinput 2>/dev/null || true
sudo chown root:input /dev/uinput 2>/dev/null || true

# Regra udev permanente para /dev/uinput
UDEV_RULE="/etc/udev/rules.d/99-uinput.rules"
if [ ! -f "${UDEV_RULE}" ]; then
    echo 'KERNEL=="uinput", GROUP="input", MODE="0660"' | sudo tee "${UDEV_RULE}" > /dev/null
    sudo udevadm control --reload-rules
    echo "  Regra udev criada: ${UDEV_RULE}"
fi

# ── 3. Criar virtualenv e instalar bibliotecas Python ────────────────────────
echo "[3/4] Criando virtualenv e instalando bibliotecas Python..."

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade --quiet pip
"${VENV_DIR}/bin/pip" install --quiet \
    opencv-python \
    mediapipe \
    pystray \
    pillow \
    evdev

echo "  Virtualenv: ${VENV_DIR}"
echo "  Python:     $("${VENV_DIR}/bin/python" --version)"

# ── 4. Criar lançador .desktop ────────────────────────────────────────────────
echo "[4/4] Criando lançador .desktop..."

DESKTOP_DIR="${HOME}/.local/share/applications"
mkdir -p "${DESKTOP_DIR}"
DESKTOP_FILE="${DESKTOP_DIR}/gesture-control.desktop"

{
    printf '[Desktop Entry]\n'
    printf 'Type=Application\n'
    printf 'Name=Gesture Control\n'
    printf 'Comment=Controle por gestos em segundo plano\n'
    printf 'Exec=%s %s/tray_icon.py\n' "${VENV_DIR}/bin/python" "${SCRIPT_DIR}"
    printf 'Icon=input-mouse\n'
    printf 'Terminal=false\n'
    printf 'Categories=Utility;Accessibility;\n'
    printf 'StartupNotify=false\n'
} > "${DESKTOP_FILE}"

chmod +x "${DESKTOP_FILE}"
chmod +x "${SCRIPT_DIR}/tray_icon.py"
chmod +x "${SCRIPT_DIR}/gesture_control.py"
chmod +x "${SCRIPT_DIR}/debug_landmarks.py"

# ── Verificação final ─────────────────────────────────────────────────────────
echo ""
echo "=== Verificação ==="

if python3 -c "import evdev" &>/dev/null || "${VENV_DIR}/bin/python" -c "import evdev" &>/dev/null; then
    echo "  evdev:       OK"
else
    echo "  evdev:       ERRO"
fi

ls -la /dev/uinput &>/dev/null && echo "  /dev/uinput: OK" || echo "  /dev/uinput: ERRO"

if groups | grep -q input; then
    echo "  grupo input: OK"
else
    echo "  grupo input: pendente — faça logout/login"
fi

echo "  venv Python: OK ($("${VENV_DIR}/bin/python" --version))"

echo ""
echo "=== Instalação concluída! ==="
echo ""
echo "PRÓXIMOS PASSOS:"
echo ""
echo "  1. Faça LOGOUT e LOGIN  (para o grupo 'input' ativar)"
echo ""
echo "  2. Teste os gestos com a câmera:"
echo "       ${VENV_DIR}/bin/python ${SCRIPT_DIR}/debug_landmarks.py"
echo ""
echo "  3. Inicie o Gesture Control:"
echo "       ${VENV_DIR}/bin/python ${SCRIPT_DIR}/tray_icon.py"
echo "     ou procure 'Gesture Control' no launcher"
echo ""
echo "  Opcional — gerar executável único (sem precisar do venv):"
echo "       bash ${SCRIPT_DIR}/build.sh"
