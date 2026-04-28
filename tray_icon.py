#!/usr/bin/env python3
"""
tray_icon.py
------------
Ícone na bandeja usando AppIndicator3 (GNOME Wayland / Pop!_OS).
Quando um gesto é detectado, o ícone fica mais largo mostrando o emoji
por 1 segundo e depois volta ao normal.
Comunicação com gesture_control.py via arquivo IPC em /tmp.
"""

import os
import sys
import subprocess
import threading
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("AppIndicator3", "0.1")
from gi.repository import Gtk, GLib, AppIndicator3 as AppIndicator
from PIL import Image, ImageDraw, ImageFont
import tempfile

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE           = Path(__file__).parent
SCRIPT         = BASE / "gesture_control.py"
LOGFILE        = BASE / "gesture.log"
CONFIG         = BASE / "gestures" / "custom.json"
PIDFILE        = Path("/tmp/gesture-control.pid")
PAUSE          = Path("/tmp/gesture-control.pause")
QUIT           = Path("/tmp/gesture-control.quit")
GESTURE_SIGNAL = Path("/tmp/gesture-control.gesture")

PYTHON = sys.executable

# ── Cache de ícones PNG temporários ──────────────────────────────────────────
_icon_cache: dict[str, str] = {}

def _find_emoji_font() -> ImageFont.FreeTypeFont | None:
    for fp in [
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, 22)
            except Exception:
                pass
    return None

_EMOJI_FONT = _find_emoji_font()

def _make_icon(color: tuple, name: str, emoji: str = "") -> str:
    """
    Gera ícone PNG e retorna o caminho.
    Se emoji fornecido: ícone largo (círculo + emoji).
    Se não: ícone quadrado normal (só círculo).
    """
    key = f"{name}_{emoji}"
    if key in _icon_cache:
        return _icon_cache[key]

    if emoji:
        # Ícone largo: 80×32 — círculo à esquerda, emoji à direita
        img  = Image.new("RGBA", (80, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 28, 28], fill=color)
        draw.ellipse([9, 9, 21, 21], fill=(255, 255, 255, 200))
        try:
            if _EMOJI_FONT:
                draw.text((32, 4), emoji, font=_EMOJI_FONT, embedded_color=True)
            else:
                draw.text((32, 7), emoji, fill=(255, 255, 255, 255))
        except Exception:
            pass
    else:
        # Ícone normal: 32×32
        img  = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 30, 30], fill=color)
        draw.ellipse([10, 10, 22, 22], fill=(255, 255, 255, 200))

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="gc_icon_")
    img.save(tmp.name)
    _icon_cache[key] = tmp.name
    return tmp.name

# Ícones base (sem emoji)
def icon_active():  return _make_icon((40, 180, 100), "active")
def icon_paused():  return _make_icon((130, 130, 130), "paused")
def icon_error():   return _make_icon((220, 100, 40),  "error")

# Ícone com emoji do gesto
def icon_gesture(emoji: str): return _make_icon((40, 180, 100), "gesture", emoji)

# ── Helpers de processo ───────────────────────────────────────────────────────
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
    subprocess.Popen(
        [PYTHON, str(SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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

# ── AppIndicator ──────────────────────────────────────────────────────────────
class GestureIndicator:
    def __init__(self):
        self.ind = AppIndicator.Indicator.new(
            "gesture-control",
            icon_active(),
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.ind.set_menu(self._build_menu())
        self._flash_source: int | None = None

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

    def set_icon(self, path: str):
        GLib.idle_add(self.ind.set_icon_full, path, "gesture-control")

    def flash(self, emoji: str):
        """Troca para ícone largo com emoji por 1 segundo e volta ao normal."""
        # Cancela flash anterior se ainda estiver ativo
        if self._flash_source is not None:
            GLib.source_remove(self._flash_source)
            self._flash_source = None

        # Ícone com emoji
        GLib.idle_add(self.ind.set_icon_full, icon_gesture(emoji), "gesto")

        # Volta ao normal após 1s
        def _restore():
            self._flash_source = None
            base = icon_paused() if is_paused() else icon_active()
            GLib.idle_add(self.ind.set_icon_full, base, "gesture-control")
            return False

        self._flash_source = GLib.timeout_add(1000, _restore)

    def on_toggle(self, _):
        if is_paused():
            PAUSE.unlink(missing_ok=True)
            self.item_toggle.set_label("Pausar")
            self.set_icon(icon_active())
        else:
            PAUSE.touch()
            self.item_toggle.set_label("Retomar")
            self.set_icon(icon_paused())

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
        self.set_icon(icon_active())

    def on_quit(self, _):
        stop_daemon()
        PAUSE.unlink(missing_ok=True)
        for path in _icon_cache.values():
            try:
                Path(path).unlink()
            except Exception:
                pass
        Gtk.main_quit()

# ── Watchdog + polling do sinal de gesto ─────────────────────────────────────
def watchdog(indicator: GestureIndicator):
    tick = 0
    while True:
        time.sleep(0.1)
        tick += 1

        # Polling do arquivo IPC a cada 100ms
        if GESTURE_SIGNAL.exists():
            try:
                emoji = GESTURE_SIGNAL.read_text().strip()
                GESTURE_SIGNAL.unlink(missing_ok=True)
                if emoji and not is_paused():
                    indicator.flash(emoji)
            except Exception:
                pass

        # Verificação de saúde do daemon a cada 10s
        if tick % 100 == 0:
            if not get_pid() and not is_paused():
                try:
                    start_daemon()
                    GLib.idle_add(indicator.set_icon, icon_active())
                    GLib.idle_add(indicator.item_toggle.set_label, "Pausar")
                except Exception:
                    GLib.idle_add(indicator.set_icon, icon_error())

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not get_pid():
        start_daemon()

    indicator = GestureIndicator()

    t = threading.Thread(target=watchdog, args=(indicator,), daemon=True)
    t.start()

    Gtk.main()

if __name__ == "__main__":
    main()
