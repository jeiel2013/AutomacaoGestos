#!/usr/bin/env python3
"""
tray_icon.py
------------
Ícone na bandeja do sistema para controlar o gesture_control.py.

Funcionalidades:
  - Inicia o daemon automaticamente ao abrir
  - Ícone verde  = reconhecimento ativo
  - Ícone cinza  = pausado
  - Ícone laranja = daemon não encontrado / erro
  - Menu: Pausar/Retomar | Ver log | Configurações | Sair

Dependências:
  pip install pystray pillow

Uso:
  python3 tray_icon.py          # uso direto
  (ou clique duplo no .desktop) # via launcher
"""

import subprocess
import sys
import os
import time
import threading
from pathlib import Path
from PIL import Image, ImageDraw
import pystray

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE    = Path(__file__).parent
SCRIPT  = BASE / "gesture_control.py"
CONFIG  = BASE / "gestures" / "custom.json"
LOGFILE = BASE / "gesture.log"
PIDFILE = Path("/tmp/gesture-control.pid")
PAUSE   = Path("/tmp/gesture-control.pause")
QUIT    = Path("/tmp/gesture-control.quit")

# ── Cores do ícone ────────────────────────────────────────────────────────────
COLOR_ACTIVE  = (40,  180, 100)   # verde
COLOR_PAUSED  = (130, 130, 130)   # cinza
COLOR_ERROR   = (220, 100,  40)   # laranja


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_icon(color: tuple) -> Image.Image:
    """Cria um ícone circular 64×64 com a cor especificada."""
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([6, 6, 58, 58], fill=color)
    # pequeno indicador interno (círculo branco menor)
    draw.ellipse([24, 24, 40, 40], fill=(255, 255, 255, 180))
    return img


def get_pid() -> int | None:
    """Retorna o PID do daemon se estiver rodando, senão None."""
    if not PIDFILE.exists():
        return None
    try:
        pid = int(PIDFILE.read_text().strip())
        if Path(f"/proc/{pid}").exists():
            return pid
    except (ValueError, OSError):
        pass
    return None


def is_paused() -> bool:
    return PAUSE.exists()


def start_daemon():
    """Inicia o gesture_control.py como processo filho."""
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    subprocess.Popen(
        [sys.executable, str(SCRIPT)],
        stdout = subprocess.DEVNULL,
        stderr = subprocess.DEVNULL,
        env    = env,
    )
    # aguarda o PID ser criado (até 3s)
    for _ in range(30):
        time.sleep(0.1)
        if get_pid():
            break


def stop_daemon():
    """Envia sinal de encerramento ao daemon."""
    QUIT.touch()
    pid = get_pid()
    if pid:
        subprocess.run(["kill", "-TERM", str(pid)], check=False)
    time.sleep(0.5)
    PIDFILE.unlink(missing_ok=True)
    QUIT.unlink(missing_ok=True)


# ── Callbacks do menu ─────────────────────────────────────────────────────────

def on_toggle(icon: pystray.Icon, item):
    """Alterna entre pausado e ativo."""
    if is_paused():
        PAUSE.unlink(missing_ok=True)
        icon.icon  = make_icon(COLOR_ACTIVE)
        icon.title = "Gesture Control - ativo"
    else:
        PAUSE.touch()
        icon.icon  = make_icon(COLOR_PAUSED)
        icon.title = "Gesture Control - pausado"


def on_open_log(icon: pystray.Icon, item):
    """Abre o arquivo de log no editor de texto padrão do GNOME."""
    LOGFILE.touch()    # garante que o arquivo existe
    subprocess.Popen(
        ["xdg-open", str(LOGFILE)],
        stdout = subprocess.DEVNULL,
        stderr = subprocess.DEVNULL,
    )


def on_open_config(icon: pystray.Icon, item):
    """Abre o custom.json no editor de texto padrão."""
    subprocess.Popen(
        ["xdg-open", str(CONFIG)],
        stdout = subprocess.DEVNULL,
        stderr = subprocess.DEVNULL,
    )


def on_restart(icon: pystray.Icon, item):
    """Para e reinicia o daemon."""
    stop_daemon()
    time.sleep(0.3)
    start_daemon()
    icon.icon  = make_icon(COLOR_ACTIVE)
    icon.title = "Gesture Control - ativo"


def on_quit(icon: pystray.Icon, item):
    """Encerra daemon e remove o ícone da bandeja."""
    stop_daemon()
    PAUSE.unlink(missing_ok=True)
    icon.stop()


# ── Monitor de saúde (watchdog) ───────────────────────────────────────────────

def watchdog(icon: pystray.Icon):
    """
    Verifica a cada 10s se o daemon ainda está rodando.
    Se morreu inesperadamente, reinicia e atualiza o ícone.
    """
    while True:
        time.sleep(10)
        if not get_pid() and not PAUSE.exists():
            # daemon morreu — tenta reiniciar
            try:
                start_daemon()
                icon.icon  = make_icon(COLOR_ACTIVE)
                icon.title = "Gesture Control - ativo (reiniciado)"
            except Exception:
                icon.icon  = make_icon(COLOR_ERROR)
                icon.title = "Gesture Control - erro ao reiniciar"


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Iniciar daemon se ainda não estiver rodando
    if not get_pid():
        start_daemon()

    initial_color = COLOR_ACTIVE if get_pid() else COLOR_ERROR
    initial_title = "Gesture Control - ativo" if get_pid() else "Gesture Control - erro"

    icon = pystray.Icon(
        name  = "gesture-control",
        icon  = make_icon(initial_color),
        title = initial_title,
        menu  = pystray.Menu(
            pystray.MenuItem(
                lambda text, item: "Pausar" if not is_paused() else "Retomar",
                on_toggle,
                default = True,    # ação do clique simples
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Ver log",          on_open_log),
            pystray.MenuItem("Editar gestos",    on_open_config),
            pystray.MenuItem("Reiniciar daemon", on_restart),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair",             on_quit),
        ),
    )

    # Inicia watchdog em thread daemon (morre junto com o processo principal)
    t = threading.Thread(target=watchdog, args=(icon,), daemon=True)
    t.start()

    icon.run()


if __name__ == "__main__":
    main()
