#!/usr/bin/env python3
"""
confirm_dialog.py
-----------------
Popup de confirmação para gestos destrutivos no Windows.
Usa uma janela tkinter simples que aparece no canto da tela.
A confirmação também pode ser feita com o gesto Joinha pela câmera.
"""

import threading
import time
import logging
import tkinter as tk
from tkinter import ttk
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# Gestos que exigem confirmação
CONFIRM_GESTURES = {
    "FECHAR_JANELA":   ("🪟", "Fechar Janela"),
    "SELECIONAR_TUDO": ("📋", "Selecionar Tudo"),
    "DELETAR":         ("🗑️", "Deletar"),
    "VOLTAR":          ("↩️",  "Voltar"),
    "FECHAR_ABA":      ("✖️",  "Fechar Aba"),
    "DESFAZER":        ("↪️",  "Desfazer"),
    "REFAZER":         ("↩️",  "Refazer"),
    "TOGGLE_DYNAMIC":  ("🔀", "Gestos Dinâmicos"),
}

TIMEOUT_SECONDS = 5

# ── Estado global ─────────────────────────────────────────────────────────────
_lock             = threading.Lock()
_pending_gesture  = None
_pending_callback = None
_timeout_timer    = None
_dialog_window    = None


def needs_confirmation(gesture_name: str) -> bool:
    return gesture_name in CONFIRM_GESTURES


def has_pending() -> bool:
    with _lock:
        return _pending_gesture is not None


def show(gesture_name: str, on_result) -> None:
    """
    Exibe janela de confirmação no canto inferior direito da tela.
    on_result(confirmed: bool) é chamado quando o usuário decide.
    """
    global _pending_gesture, _pending_callback, _timeout_timer

    emoji, label = CONFIRM_GESTURES.get(gesture_name, ("❓", gesture_name))

    with _lock:
        _cancel_timeout()
        _pending_gesture  = gesture_name
        _pending_callback = on_result
        _timeout_timer    = threading.Timer(TIMEOUT_SECONDS, _on_timeout)
        _timeout_timer.daemon = True
        _timeout_timer.start()

    # Roda janela em thread separada (tkinter precisa de sua própria thread)
    threading.Thread(
        target=_show_window,
        args=(emoji, label, on_result),
        daemon=True,
    ).start()


def _show_window(emoji: str, label: str, on_result) -> None:
    global _dialog_window
    try:
        root = tk.Tk()
        root.overrideredirect(True)       # sem barra de título
        root.attributes("-topmost", True) # sempre à frente
        root.attributes("-alpha", 0.95)
        root.configure(bg="#0C0C12")

        # Borda arredondada via canvas
        frame = tk.Frame(root, bg="#0C0C12", padx=20, pady=16)
        frame.pack()

        lbl_emoji = tk.Label(frame, text=emoji, font=("Segoe UI Emoji", 28),
                             bg="#0C0C12", fg="white")
        lbl_emoji.pack()

        lbl_name = tk.Label(frame, text=label, font=("Segoe UI", 13, "bold"),
                            bg="#0C0C12", fg="white")
        lbl_name.pack(pady=(2, 0))

        lbl_hint = tk.Label(frame, text="👍 Joinha ou clique para confirmar",
                            font=("Segoe UI", 9), bg="#0C0C12",
                            fg="#666688")
        lbl_hint.pack(pady=(2, 10))

        btn_frame = tk.Frame(frame, bg="#0C0C12")
        btn_frame.pack()

        def confirm():
            root.destroy()
            _finish(True, on_result, label)

        def cancel():
            root.destroy()
            _finish(False, on_result, label)

        btn_ok = tk.Button(btn_frame, text="✅ Confirmar",
                           font=("Segoe UI", 9, "bold"),
                           bg="#1a3a28", fg="#28c864",
                           relief="flat", padx=12, pady=5,
                           cursor="hand2", command=confirm)
        btn_ok.grid(row=0, column=0, padx=(0, 6))

        btn_cancel = tk.Button(btn_frame, text="❌ Cancelar",
                               font=("Segoe UI", 9),
                               bg="#1e1e28", fg="#888899",
                               relief="flat", padx=12, pady=5,
                               cursor="hand2", command=cancel)
        btn_cancel.grid(row=0, column=1)

        # Barra de progresso (timeout)
        progress = ttk.Progressbar(frame, length=200, mode="determinate",
                                   maximum=100, value=100)
        progress.pack(pady=(10, 0))

        # Posicionar no canto inferior direito
        root.update_idletasks()
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = sw - w - 24
        y = sh - h - 60   # acima da barra de tarefas
        root.geometry(f"+{x}+{y}")

        # Animar progresso
        steps      = TIMEOUT_SECONDS * 10
        interval   = 100  # ms
        step_value = 100 / steps

        def tick(remaining):
            if not root.winfo_exists():
                return
            val = remaining * step_value
            progress["value"] = max(0, val)
            if remaining > 0:
                root.after(interval, tick, remaining - 1)
            else:
                root.destroy()
                _finish(False, on_result, label)

        root.after(interval, tick, steps - 1)

        # Guardar referência para fechar de fora (via gesto)
        with _lock:
            _dialog_window = root

        root.mainloop()

    except Exception as ex:
        log.warning("confirm_dialog erro: %s", ex)
        _finish(False, on_result, label)
    finally:
        with _lock:
            _dialog_window = None


def _finish(confirmed: bool, on_result, label: str) -> None:
    with _lock:
        if _pending_gesture is None:
            return
        _cancel_timeout()
        _clear_pending()

    log.info("Confirmação: %s → %s", label, "ACEITA" if confirmed else "CANCELADA")
    on_result(confirmed)


def confirm_current() -> bool:
    """Confirma via gesto Joinha detectado pela câmera."""
    global _pending_callback, _dialog_window
    with _lock:
        if _pending_gesture is None:
            return False
        cb      = _pending_callback
        gesture = _pending_gesture
        win     = _dialog_window
        _cancel_timeout()
        _clear_pending()

    # Fechar janela tkinter de outra thread
    if win is not None:
        try:
            win.after(0, win.destroy)
        except Exception:
            pass

    if cb:
        log.info("Confirmação via Joinha: %s → ACEITA", gesture)
        cb(True)
    return True


def cancel_current() -> bool:
    """Cancela via gesto punho."""
    global _pending_callback, _dialog_window
    with _lock:
        if _pending_gesture is None:
            return False
        cb      = _pending_callback
        gesture = _pending_gesture
        win     = _dialog_window
        _cancel_timeout()
        _clear_pending()

    if win is not None:
        try:
            win.after(0, win.destroy)
        except Exception:
            pass

    if cb:
        log.info("Confirmação via Punho: %s → CANCELADA", gesture)
        cb(False)
    return True


def _on_timeout() -> None:
    global _pending_callback, _dialog_window
    with _lock:
        if _pending_gesture is None:
            return
        cb      = _pending_callback
        gesture = _pending_gesture
        win     = _dialog_window
        _clear_pending()

    if win is not None:
        try:
            win.after(0, win.destroy)
        except Exception:
            pass

    if cb:
        log.info("Confirmação timeout: %s → CANCELADA", gesture)
        cb(False)


def _cancel_timeout() -> None:
    global _timeout_timer
    if _timeout_timer is not None:
        _timeout_timer.cancel()
        _timeout_timer = None


def _clear_pending() -> None:
    global _pending_gesture, _pending_callback, _timeout_timer
    _pending_gesture  = None
    _pending_callback = None
    _timeout_timer    = None
