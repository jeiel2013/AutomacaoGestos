#!/usr/bin/env python3
"""
confirm_dialog.py
-----------------
Janela de confirmação flutuante que aparece quando um gesto destrutivo
é detectado. O usuário confirma com o gesto Joinha (Enter) ou cancela
com punho fechado (Escape) ou simplesmente esperando o timeout.

Uso interno — chamado pelo gesture_control.py via threading.
"""

import threading
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk

# Gestos que exigem confirmação e seus emojis
CONFIRM_GESTURES = {
    "FECHAR_JANELA":   ("🪟", "Fechar Janela"),
    "SELECIONAR_TUDO": ("📋", "Selecionar Tudo"),
    "DELETAR":         ("🗑️", "Deletar"),
    "VOLTAR":          ("↩️",  "Voltar"),
    "FECHAR_ABA":      ("✖️",  "Fechar Aba"),
    "DESFAZER":        ("↪️",  "Desfazer"),
    "REFAZER":         ("↩️",  "Refazer"),
}

TIMEOUT_SECONDS = 5   # cancela automaticamente após N segundos

CSS = b"""
window {
    background: transparent;
}

#confirm-box {
    background: rgba(18, 18, 24, 0.96);
    border-radius: 18px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 24px 28px 20px 28px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.6);
}

#emoji-label {
    font-size: 42px;
    margin-bottom: 4px;
}

#gesture-name {
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 2px;
}

#hint {
    font-size: 12px;
    color: rgba(255,255,255,0.45);
    margin-bottom: 16px;
}

#confirm-btn {
    background: rgba(40, 200, 100, 0.15);
    border: 1px solid rgba(40, 200, 100, 0.4);
    border-radius: 10px;
    color: #28c864;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 18px;
    margin-right: 6px;
}

#confirm-btn:hover {
    background: rgba(40, 200, 100, 0.28);
}

#cancel-btn {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    color: rgba(255,255,255,0.55);
    font-size: 13px;
    padding: 8px 18px;
}

#cancel-btn:hover {
    background: rgba(255,255,255,0.10);
    color: rgba(255,255,255,0.85);
}

#progress {
    background: rgba(255,255,255,0.08);
    border-radius: 4px;
    margin-top: 14px;
}

#progress progress {
    background: rgba(40, 200, 100, 0.5);
    border-radius: 4px;
}
"""


class ConfirmDialog:
    """
    Janela de confirmação flutuante.
    confirmed: True se confirmado, False se cancelado/timeout.
    """

    def __init__(self, gesture_name: str, on_result):
        """
        gesture_name: chave do gesto (ex: 'FECHAR_JANELA')
        on_result: callback(confirmed: bool) chamado ao fechar
        """
        self._on_result  = on_result
        self._answered   = False
        self._tick       = 0
        self._total_ticks = TIMEOUT_SECONDS * 10  # atualiza a cada 100ms

        emoji, label = CONFIRM_GESTURES.get(gesture_name, ("❓", gesture_name))

        # ── Aplicar CSS ───────────────────────────────────────────────────────
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # ── Janela principal ──────────────────────────────────────────────────
        self._win = Gtk.Window(type=Gtk.WindowType.POPUP)
        self._win.set_decorated(False)
        self._win.set_keep_above(True)
        self._win.set_skip_taskbar_hint(True)
        self._win.set_skip_pager_hint(True)
        self._win.set_app_paintable(True)

        # Transparência
        screen   = self._win.get_screen()
        visual   = screen.get_rgba_visual()
        if visual:
            self._win.set_visual(visual)

        # ── Layout ────────────────────────────────────────────────────────────
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_halign(Gtk.Align.CENTER)
        outer.set_valign(Gtk.Align.CENTER)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_name("confirm-box")
        box.set_halign(Gtk.Align.CENTER)

        # Emoji
        lbl_emoji = Gtk.Label(label=emoji)
        lbl_emoji.set_name("emoji-label")
        lbl_emoji.set_halign(Gtk.Align.CENTER)
        box.pack_start(lbl_emoji, False, False, 0)

        # Nome do gesto
        lbl_name = Gtk.Label(label=label)
        lbl_name.set_name("gesture-name")
        lbl_name.set_halign(Gtk.Align.CENTER)
        box.pack_start(lbl_name, False, False, 0)

        # Dica
        lbl_hint = Gtk.Label(label="👍 Joinha ou Enter para confirmar")
        lbl_hint.set_name("hint")
        lbl_hint.set_halign(Gtk.Align.CENTER)
        box.pack_start(lbl_hint, False, False, 6)

        # Botões
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        btn_row.set_halign(Gtk.Align.CENTER)

        btn_confirm = Gtk.Button(label="👍  Confirmar")
        btn_confirm.set_name("confirm-btn")
        btn_confirm.connect("clicked", self._on_confirm)

        btn_cancel = Gtk.Button(label="Cancelar")
        btn_cancel.set_name("cancel-btn")
        btn_cancel.connect("clicked", self._on_cancel)

        btn_row.pack_start(btn_confirm, False, False, 0)
        btn_row.pack_start(btn_cancel,  False, False, 0)
        box.pack_start(btn_row, False, False, 0)

        # Barra de progresso (timeout)
        self._progress = Gtk.ProgressBar()
        self._progress.set_name("progress")
        self._progress.set_fraction(1.0)
        self._progress.set_size_request(200, 4)
        box.pack_start(self._progress, False, False, 0)

        outer.pack_start(box, False, False, 0)
        self._win.add(outer)

        # ── Posicionar no canto superior direito ──────────────────────────────
        self._win.show_all()
        self._win.resize(1, 1)   # força recalcular tamanho
        GLib.idle_add(self._position_window)

        # ── Capturar Enter/Escape do teclado ──────────────────────────────────
        self._win.connect("key-press-event", self._on_key)

        # ── Timer de timeout ──────────────────────────────────────────────────
        GLib.timeout_add(100, self._tick_timeout)

    def _position_window(self):
        screen = Gdk.Screen.get_default()
        sw     = screen.get_width()
        w, h   = self._win.get_size()
        self._win.move(sw - w - 24, 48)
        return False

    def _tick_timeout(self):
        if self._answered:
            return False
        self._tick += 1
        fraction = 1.0 - (self._tick / self._total_ticks)
        self._progress.set_fraction(max(0.0, fraction))
        if self._tick >= self._total_ticks:
            self._finish(False)
            return False
        return True

    def _on_key(self, widget, event):
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._finish(True)
        elif event.keyval == Gdk.KEY_Escape:
            self._finish(False)

    def _on_confirm(self, *_):
        self._finish(True)

    def _on_cancel(self, *_):
        self._finish(False)

    def _finish(self, confirmed: bool):
        if self._answered:
            return
        self._answered = True
        GLib.idle_add(self._win.destroy)
        if self._on_result:
            self._on_result(confirmed)

    def confirm_gesture(self):
        """Chamado pelo gesture_control quando detecta Joinha durante confirmação."""
        self._finish(True)

    def cancel_gesture(self):
        """Chamado pelo gesture_control quando detecta punho durante confirmação."""
        self._finish(False)


# ── API pública ───────────────────────────────────────────────────────────────
_current_dialog: ConfirmDialog | None = None


def needs_confirmation(gesture_name: str) -> bool:
    """Retorna True se o gesto exige confirmação."""
    return gesture_name in CONFIRM_GESTURES


def show(gesture_name: str, on_result) -> None:
    """
    Mostra o diálogo de confirmação para o gesto.
    on_result(confirmed: bool) é chamado quando o usuário decide.
    Thread-safe — usa GLib.idle_add internamente.
    """
    global _current_dialog

    def _create():
        global _current_dialog
        _current_dialog = ConfirmDialog(gesture_name, on_result)
        return False

    GLib.idle_add(_create)


def confirm_current() -> bool:
    """Confirma o diálogo atual (chamado quando gesto Joinha é detectado)."""
    global _current_dialog
    if _current_dialog and not _current_dialog._answered:
        _current_dialog.confirm_gesture()
        _current_dialog = None
        return True
    return False


def cancel_current() -> bool:
    """Cancela o diálogo atual."""
    global _current_dialog
    if _current_dialog and not _current_dialog._answered:
        _current_dialog.cancel_gesture()
        _current_dialog = None
        return True
    return False


def has_pending() -> bool:
    """Retorna True se há um diálogo aguardando confirmação."""
    return _current_dialog is not None and not _current_dialog._answered
