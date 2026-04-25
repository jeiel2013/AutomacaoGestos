#!/usr/bin/env python3
"""
overlay.py
----------
HUD transparente que aparece no centro da tela ao detectar um gesto.
"""

import threading
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk

GESTURE_INFO = {
    "FECHAR_JANELA":         ("🪟", "Fechar Janela"),
    "SCROLL_CIMA":           ("⬆️",  "Scroll Cima"),
    "SCROLL_BAIXO":          ("⬇️",  "Scroll Baixo"),
    "SELECIONAR_TUDO":       ("📋", "Selecionar Tudo"),
    "DELETAR":               ("🗑️", "Deletar"),
    "CONFIRMAR":             ("👍", "Confirmar"),
    "VOLTAR":                ("↩️",  "Voltar"),
    "TROCAR_JANELA":         ("🔄", "Trocar Janela"),
    "CAPTURA_TELA":          ("📸", "Captura de Tela"),
    "WORKSPACE_DIR":         ("➡️",  "Workspace →"),
    "NOVA_ABA":              ("➕", "Nova Aba"),
    "FECHAR_ABA":            ("✖️",  "Fechar Aba"),
    "MAXIMIZAR":             ("⬛", "Maximizar"),
    "MINIMIZAR":             ("▬",  "Minimizar"),
    "DESFAZER":              ("↪️",  "Desfazer"),
    "REFAZER":               ("↩️",  "Refazer"),
    "SWIPE_DIREITA":         ("👉", "Swipe →"),
    "SWIPE_ESQUERDA":        ("👈", "Swipe ←"),
    "SWIPE_CIMA":            ("👆", "Swipe ↑"),
    "SWIPE_BAIXO":           ("👇", "Swipe ↓"),
    "SWIPE_RAPIDO_DIREITA":  ("⚡", "Swipe Rápido →"),
    "SWIPE_RAPIDO_ESQUERDA": ("⚡", "Swipe Rápido ←"),
    "SWIPE_RAPIDO_CIMA":     ("⚡", "Swipe Rápido ↑"),
    "SWIPE_RAPIDO_BAIXO":    ("⚡", "Swipe Rápido ↓"),
    "SHAKE":                 ("🤝", "Shake"),
    "CIRCLE_CW":             ("🔃", "Círculo ↻"),
    "CIRCLE_CCW":            ("🔄", "Círculo ↺"),
    "FIGURE_EIGHT":          ("♾️",  "Figura 8"),
    "WAVE_W":                ("〰️", "Wave W"),
    "ZOOM_IN":               ("🔍", "Zoom +"),
    "ZOOM_OUT":              ("🔎", "Zoom -"),
    "PUSH_FRENTE":           ("🫸", "Push Frente"),
    "PULL_ATRAS":            ("🫷", "Pull Atrás"),
    "TILT_DIREITA":          ("↗️",  "Tilt →"),
    "TILT_ESQUERDA":         ("↖️",  "Tilt ←"),
}

SHOW_MS       = 1200
FADE_STEPS    = 20
FADE_INTERVAL = max(16, int((SHOW_MS * 0.4) / FADE_STEPS))

# CSS sem text-transform (não suportado no GTK 3)
CSS = b"""
window {
    background: transparent;
}
#hud-box {
    background: rgba(12, 12, 18, 0.92);
    border-radius: 22px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 24px 40px 20px 40px;
}
#hud-emoji {
    font-size: 52px;
    margin-bottom: 4px;
}
#hud-label {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
}
#hud-type {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.35);
    margin-top: 2px;
}
"""

_lock          = threading.Lock()
_current_win   = None
_hide_timer_id = None
_fade_timer_id = None
_css_loaded    = False


def _ensure_css():
    global _css_loaded
    if _css_loaded:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _css_loaded = True


class _HUD:
    def __init__(self, gesture_name: str, gesture_type: str):
        emoji, label = GESTURE_INFO.get(gesture_name, ("✋", gesture_name))
        kind         = "DINÂMICO" if gesture_type == "dynamic" else "ESTÁTICO"

        _ensure_css()

        # Janela toplevel normal — funciona em Wayland via XWayland
        self.win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.win.set_decorated(False)
        self.win.set_keep_above(True)
        self.win.set_skip_taskbar_hint(True)
        self.win.set_skip_pager_hint(True)
        self.win.set_accept_focus(False)
        self.win.set_resizable(False)
        self.win.set_app_paintable(True)

        # Transparência
        screen = self.win.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.win.set_visual(visual)

        self.win.connect("draw", self._on_draw)

        # Layout
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_halign(Gtk.Align.CENTER)
        outer.set_valign(Gtk.Align.CENTER)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_name("hud-box")

        lbl_emoji = Gtk.Label(label=emoji)
        lbl_emoji.set_name("hud-emoji")
        lbl_emoji.set_halign(Gtk.Align.CENTER)
        box.pack_start(lbl_emoji, False, False, 0)

        lbl_name = Gtk.Label(label=label)
        lbl_name.set_name("hud-label")
        lbl_name.set_halign(Gtk.Align.CENTER)
        box.pack_start(lbl_name, False, False, 0)

        lbl_type = Gtk.Label(label=kind)
        lbl_type.set_name("hud-type")
        lbl_type.set_halign(Gtk.Align.CENTER)
        box.pack_start(lbl_type, False, False, 0)

        outer.pack_start(box, True, True, 0)
        self.win.add(outer)

        self._opacity = 1.0
        self.win.set_opacity(1.0)
        self.win.show_all()

        # Centralizar após mostrar (tamanho calculado só depois do show)
        GLib.idle_add(self._center)

    def _on_draw(self, widget, cr):
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(1)  # CLEAR
        cr.paint()
        return False

    def _center(self):
        display  = Gdk.Display.get_default()
        monitor  = display.get_primary_monitor()
        if monitor is None:
            monitor = display.get_monitor(0)
        geo      = monitor.get_geometry()
        w, h     = self.win.get_size()
        x        = geo.x + (geo.width  - w) // 2
        y        = geo.y + (geo.height - h) // 2
        self.win.move(x, y)
        return False

    def fade_out(self) -> bool:
        self._opacity -= 1.0 / FADE_STEPS
        if self._opacity <= 0:
            self.destroy()
            return False
        self.win.set_opacity(max(0.0, self._opacity))
        return True

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass


# ── API pública ───────────────────────────────────────────────────────────────

def show(gesture_name: str, gesture_type: str = "static") -> None:
    """Thread-safe — pode ser chamado de qualquer thread."""
    GLib.idle_add(_show_in_main, gesture_name, gesture_type)


def _show_in_main(gesture_name: str, gesture_type: str) -> bool:
    global _current_win, _hide_timer_id, _fade_timer_id

    with _lock:
        if _hide_timer_id is not None:
            GLib.source_remove(_hide_timer_id)
            _hide_timer_id = None
        if _fade_timer_id is not None:
            GLib.source_remove(_fade_timer_id)
            _fade_timer_id = None
        if _current_win is not None:
            _current_win.destroy()
            _current_win = None

        try:
            _current_win  = _HUD(gesture_name, gesture_type)
            _hide_timer_id = GLib.timeout_add(int(SHOW_MS * 0.6), _start_fade)
        except Exception as e:
            print(f"[overlay] erro ao criar HUD: {e}")

    return False


def _start_fade() -> bool:
    global _hide_timer_id, _fade_timer_id
    _hide_timer_id = None
    if _current_win is not None:
        _fade_timer_id = GLib.timeout_add(FADE_INTERVAL, _fade_step)
    return False


def _fade_step() -> bool:
    global _current_win, _fade_timer_id
    if _current_win is None:
        _fade_timer_id = None
        return False
    still_fading = _current_win.fade_out()
    if not still_fading:
        _current_win   = None
        _fade_timer_id = None
        return False
    return True
