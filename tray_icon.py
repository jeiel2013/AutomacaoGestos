#!/usr/bin/env python3
"""
tray_icon.py
------------
Ícone na bandeja usando AppIndicator3 (funciona no GNOME Wayland / Pop!_OS).
Inicia e gerencia o gesture_control.py em segundo plano.
"""

import os
import sys
import subprocess
import threading
import time
from pathlib import Path

# Forçar backend GTK antes de importar pystray
os.environ.setdefault("PYSTRAY_BACKEND", "gtk")

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("AppIndicator3", "0.1")
from gi.repository import Gtk, GLib
try:
    from gi.repository import AppIndicator3 as AppIndicator
    HAS_INDICATOR = True
except Exception:
    HAS_INDICATOR = False

from PIL import Image, ImageDraw
import tempfile

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE    = Path(__file__).parent
SCRIPT  = BASE / "gesture_control.py"
LOGFILE = BASE / "gesture.log"
CONFIG  = BASE / "gestures" / "custom.json"
PIDFILE = Path("/tmp/gesture-control.pid")
PAUSE   = Path("/tmp/gesture-control.pause")
QUIT    = Path("/tmp/gesture-control.quit")
GESTURE_SIGNAL = Path("/tmp/gesture-control.gesture")

PYTHON  = sys.executable   # usa o mesmo python do venv atual

# ── Ícones ────────────────────────────────────────────────────────────────────
_icon_files: dict[str, str] = {}

def _make_icon_file(color: tuple, name: str) -> str:
    """Gera um PNG temporário e retorna o caminho."""
    if name in _icon_files:
        return _icon_files[name]
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=color)
    draw.ellipse([22, 22, 42, 42], fill=(255, 255, 255, 200))
    tmp  = tempfile.NamedTemporaryFile(suffix=f"_{name}.png", delete=False)
    img.save(tmp.name)
    _icon_files[name] = tmp.name
    return tmp.name

ICON_ACTIVE  = lambda: _make_icon_file((40, 180, 100), "active")
ICON_PAUSED  = lambda: _make_icon_file((130, 130, 130), "paused")
ICON_ERROR   = lambda: _make_icon_file((220, 100, 40), "error")

# Arquivo IPC: gesture_control.py escreve o emoji aqui, tray lê e atualiza ícone
def _make_gesture_icon(emoji: str) -> str:
    """Gera ícone largo com círculo verde + emoji do gesto ao lado."""
    cache_key = f"gesture_{emoji}"
    if cache_key in _icon_files:
        return _icon_files[cache_key]

    try:
        from PIL import ImageFont
        font = None
        for fp in [
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]:
            if Path(fp).exists():
                try:
                    font = ImageFont.truetype(fp, 28)
                    break
                except Exception:
                    pass

        # Ícone largo: círculo verde (32px) + emoji (32px) = 80px total
        img  = Image.new("RGBA", (80, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Círculo verde à esquerda
        draw.ellipse([2, 2, 30, 30], fill=(40, 180, 100))
        draw.ellipse([10, 10, 22, 22], fill=(255, 255, 255, 200))

        # Emoji à direita
        if font:
            draw.text((34, 2), emoji, font=font, embedded_color=True)
        else:
            draw.text((34, 6), emoji, fill=(255, 255, 255, 255))

        tmp = tempfile.NamedTemporaryFile(suffix=f"_gesture.png", delete=False)
        img.save(tmp.name)
        _icon_files[cache_key] = tmp.name
        return tmp.name
    except Exception:
        return ICON_ACTIVE()

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_pid() -> int | None:
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
    env = os.environ.copy()
    subprocess.Popen(
        [PYTHON, str(SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    for _ in range(30):
        time.sleep(0.1)
        if get_pid():
            break

def stop_daemon():
    QUIT.touch()
    pid = get_pid()
    if pid:
        subprocess.run(["kill", "-TERM", str(pid)], check=False)
    time.sleep(0.5)
    PIDFILE.unlink(missing_ok=True)
    QUIT.unlink(missing_ok=True)

# ── AppIndicator UI ───────────────────────────────────────────────────────────
class GestureIndicator:
    def __init__(self):
        self.ind = AppIndicator.Indicator.new(
            "gesture-control",
            ICON_ACTIVE(),
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_menu(self._build_menu())

    def _build_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()

        self.item_toggle = Gtk.MenuItem(label="Pausar")
        self.item_toggle.connect("activate", self.on_toggle)
        menu.append(self.item_toggle)

        menu.append(Gtk.SeparatorMenuItem())

        item_log = Gtk.MenuItem(label="Ver log")
        item_log.connect("activate", self.on_open_log)
        menu.append(item_log)

        item_cfg = Gtk.MenuItem(label="Editar gestos")
        item_cfg.connect("activate", self.on_open_config)
        menu.append(item_cfg)

        item_restart = Gtk.MenuItem(label="Reiniciar daemon")
        item_restart.connect("activate", self.on_restart)
        menu.append(item_restart)

        menu.append(Gtk.SeparatorMenuItem())

        item_quit = Gtk.MenuItem(label="Sair")
        item_quit.connect("activate", self.on_quit)
        menu.append(item_quit)

        menu.show_all()
        return menu

    def _set_icon(self, icon_path: str):
        GLib.idle_add(self.ind.set_icon_full, icon_path, "gesture-control")

    def on_toggle(self, _):
        if is_paused():
            PAUSE.unlink(missing_ok=True)
            self.item_toggle.set_label("Pausar")
            self._set_icon(ICON_ACTIVE())
        else:
            PAUSE.touch()
            self.item_toggle.set_label("Retomar")
            self._set_icon(ICON_PAUSED())

    def on_open_log(self, _):
        LOGFILE.touch()
        subprocess.Popen(["xdg-open", str(LOGFILE)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def on_open_config(self, _):
        subprocess.Popen(["xdg-open", str(CONFIG)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def on_restart(self, _):
        stop_daemon()
        time.sleep(0.3)
        start_daemon()
        self.item_toggle.set_label("Pausar")
        self._set_icon(ICON_ACTIVE())

    def on_quit(self, _):
        stop_daemon()
        PAUSE.unlink(missing_ok=True)
        # limpa arquivos de ícone temporários
        for path in _icon_files.values():
            try:
                Path(path).unlink()
            except Exception:
                pass
        Gtk.main_quit()

# ── Flash do gesto no ícone ──────────────────────────────────────────────────
_flash_timer_id = None

def flash_gesture(indicator: "GestureIndicator", emoji: str):
    """Atualiza o ícone da bandeja com o emoji por 1 segundo e volta ao normal."""
    global _flash_timer_id

    # Cancela flash anterior se houver
    if _flash_timer_id is not None:
        GLib.source_remove(_flash_timer_id)
        _flash_timer_id = None

    gesture_icon = _make_gesture_icon(emoji)
    GLib.idle_add(indicator.ind.set_icon_full, gesture_icon, "gesto")

    def _restore():
        global _flash_timer_id
        _flash_timer_id = None
        active = ICON_ACTIVE() if not is_paused() else ICON_PAUSED()
        GLib.idle_add(indicator.ind.set_icon_full, active, "gesture-control")
        return False

    _flash_timer_id = GLib.timeout_add(1000, _restore)


# ── Watchdog ──────────────────────────────────────────────────────────────────
def watchdog(indicator: GestureIndicator):
    tick = 0
    while True:
        time.sleep(0.1)
        tick += 1

        # Verificar sinal de gesto a cada 100ms
        if GESTURE_SIGNAL.exists():
            try:
                emoji = GESTURE_SIGNAL.read_text().strip()
                GESTURE_SIGNAL.unlink(missing_ok=True)
                if emoji and not is_paused():
                    flash_gesture(indicator, emoji)
            except Exception:
                pass

        # Verificar saúde do daemon a cada 10s
        if tick % 100 == 0:
            if not get_pid() and not is_paused():
                try:
                    start_daemon()
                    GLib.idle_add(indicator._set_icon, ICON_ACTIVE())
                    GLib.idle_add(indicator.item_toggle.set_label, "Pausar")
                except Exception:
                    GLib.idle_add(indicator._set_icon, ICON_ERROR())

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not HAS_INDICATOR:
        print("ERRO: AppIndicator3 não encontrado.")
        print("Execute: sudo apt install gir1.2-appindicator3-0.1")
        sys.exit(1)

    if not get_pid():
        start_daemon()

    indicator = GestureIndicator()

    t = threading.Thread(target=watchdog, args=(indicator,), daemon=True)
    t.start()

    Gtk.main()

if __name__ == "__main__":
    main()
