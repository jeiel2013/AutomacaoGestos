#!/usr/bin/env python3
"""
tray_icon.py
------------
Ícone na bandeja do Windows usando pystray + Pillow.
Quando um gesto é detectado, o ícone alarga mostrando o emoji por 1 segundo.
Comunica com gesture_control.py via arquivo IPC em %TEMP%.
"""

import os
import sys
import subprocess
import threading
import time
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import MenuItem, Menu

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE    = Path(__file__).parent
SCRIPT  = BASE / "gesture_control.py"
LOGFILE = BASE / "gesture.log"
CONFIG  = BASE / "gestures" / "custom.json"
PYTHON  = sys.executable

_TEMP          = Path(tempfile.gettempdir())
PIDFILE        = _TEMP / "gesture-control.pid"
PAUSE          = _TEMP / "gesture-control.pause"
QUIT           = _TEMP / "gesture-control.quit"
GESTURE_SIGNAL = _TEMP / "gesture-control.gesture"

# ── Ícones ────────────────────────────────────────────────────────────────────
_SZ  = 64
_GAP = 6

def _emoji_font(size: int):
    # Fontes com suporte a emoji colorido no Windows
    for fp in [
        "C:/Windows/Fonts/seguiemj.ttf",   # Segoe UI Emoji (Windows 10/11)
        "C:/Windows/Fonts/seguisym.ttf",
    ]:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return None

def _draw_circle(draw, x, y, S, color):
    draw.ellipse([x, y, x + S - 1, y + S - 1], fill=color)
    m = S // 5
    draw.ellipse([x + m, y + m, x + S - 1 - m, y + S - 1 - m],
                 fill=(255, 255, 255, 200))

def _make_icon(color: tuple, emoji: str = "") -> Image.Image:
    """
    Normal:    64×64  — círculo
    Com emoji: 134×64 — círculo + emoji
    """
    S = _SZ
    if emoji:
        W    = S + _GAP + S
        img  = Image.new("RGBA", (W, S), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        _draw_circle(draw, 0, 0, S, color)
        font = _emoji_font(S - 8)
        x    = S + _GAP
        if font:
            try:
                bbox = font.getbbox(emoji)
                ey   = (S - (bbox[3] - bbox[1])) // 2 - bbox[1]
                draw.text((x, max(0, ey)), emoji, font=font, embedded_color=True)
            except Exception:
                draw.text((x, S // 8), emoji, font=font)
        else:
            draw.text((x, S // 4), emoji, fill=(255, 255, 255, 255))
    else:
        img  = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        _draw_circle(draw, 0, 0, S, color)
    return img

def icon_active():          return _make_icon((40, 180, 100))
def icon_paused():          return _make_icon((130, 130, 130))
def icon_error():           return _make_icon((220, 100, 40))
def icon_gesture(emoji):    return _make_icon((40, 180, 100), emoji)

# ── Helpers de processo ───────────────────────────────────────────────────────
def get_pid():
    if not PIDFILE.exists():
        return None
    try:
        pid = int(PIDFILE.read_text().strip())
        # No Windows: verifica se o processo existe via tasklist
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True
        )
        if str(pid) in result.stdout:
            return pid
    except Exception:
        pass
    return None

def is_paused():
    return PAUSE.exists()

def start_daemon():
    subprocess.Popen(
        [PYTHON, str(SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,  # sem janela de terminal
    )
    for _ in range(30):
        time.sleep(0.1)
        if get_pid():
            break

def stop_daemon():
    QUIT.touch()
    pid = get_pid()
    if pid:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    PIDFILE.unlink(missing_ok=True)
    QUIT.unlink(missing_ok=True)

# ── Tray icon ─────────────────────────────────────────────────────────────────
class GestureIndicator:
    def __init__(self):
        self._icon = pystray.Icon(
            name="GestureControl",
            icon=icon_active(),
            title="Gesture Control — ativo",
            menu=self._build_menu(),
        )
        self._flash_timer = None
        self._paused      = False

    def _build_menu(self):
        return Menu(
            MenuItem(
                lambda item: "Retomar" if self._paused else "Pausar",
                self._on_toggle,
                default=True,
            ),
            Menu.SEPARATOR,
            MenuItem("Ver log",          self._on_open_log),
            MenuItem("Editar gestos",    self._on_open_config),
            MenuItem("Reiniciar daemon", self._on_restart),
            Menu.SEPARATOR,
            MenuItem("Sair",             self._on_quit),
        )

    def flash(self, emoji: str):
        """Troca para ícone com emoji por 1 segundo."""
        if self._flash_timer:
            self._flash_timer.cancel()

        self._icon.icon  = icon_gesture(emoji)
        self._icon.title = f"Gesture Control — {emoji}"

        def _restore():
            self._flash_timer = None
            self._icon.icon  = icon_paused() if self._paused else icon_active()
            self._icon.title = "Gesture Control — pausado" if self._paused else "Gesture Control — ativo"

        self._flash_timer = threading.Timer(1.0, _restore)
        self._flash_timer.daemon = True
        self._flash_timer.start()

    def _on_toggle(self, icon, item):
        if self._paused:
            PAUSE.unlink(missing_ok=True)
            self._paused     = False
            icon.icon        = icon_active()
            icon.title       = "Gesture Control — ativo"
        else:
            PAUSE.touch()
            self._paused     = True
            icon.icon        = icon_paused()
            icon.title       = "Gesture Control — pausado"

    def _on_open_log(self, icon, item):
        LOGFILE.touch()
        os.startfile(str(LOGFILE))

    def _on_open_config(self, icon, item):
        os.startfile(str(CONFIG))

    def _on_restart(self, icon, item):
        stop_daemon()
        time.sleep(0.3)
        start_daemon()
        self._paused   = False
        icon.icon      = icon_active()
        icon.title     = "Gesture Control — ativo"

    def _on_quit(self, icon, item):
        stop_daemon()
        PAUSE.unlink(missing_ok=True)
        icon.stop()

    def run(self):
        self._icon.run()

# ── Watchdog ──────────────────────────────────────────────────────────────────
def watchdog(indicator: GestureIndicator):
    tick = 0
    while True:
        time.sleep(0.1)
        tick += 1

        # Polling do sinal de gesto
        if GESTURE_SIGNAL.exists():
            try:
                emoji = GESTURE_SIGNAL.read_text(encoding="utf-8").strip()
                GESTURE_SIGNAL.unlink(missing_ok=True)
                if emoji and not is_paused():
                    indicator.flash(emoji)
            except Exception:
                pass

        # Saúde do daemon a cada 10s
        if tick % 100 == 0:
            if not get_pid() and not is_paused():
                try:
                    start_daemon()
                    indicator._icon.icon  = icon_active()
                    indicator._icon.title = "Gesture Control — ativo"
                except Exception:
                    indicator._icon.icon  = icon_error()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not get_pid():
        start_daemon()

    indicator = GestureIndicator()

    t = threading.Thread(target=watchdog, args=(indicator,), daemon=True)
    t.start()

    indicator.run()

if __name__ == "__main__":
    main()
