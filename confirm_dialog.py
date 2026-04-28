#!/usr/bin/env python3
"""
confirm_dialog.py
-----------------
Popup de confirmação para gestos destrutivos.
Aparece como notificação com ações clicáveis — saindo da bandeja,
integrado ao sistema de notificações do GNOME.

Usa notify-send com botões de ação (requer libnotify + GNOME).
A confirmação também pode ser feita com o gesto Joinha detectado pela câmera.
"""

import subprocess
import threading
import time
import logging

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
}

TIMEOUT_SECONDS = 5

# ── Estado global ─────────────────────────────────────────────────────────────
_lock            = threading.Lock()
_pending_gesture: str | None          = None
_pending_callback                     = None
_timeout_timer:   threading.Timer | None = None


def needs_confirmation(gesture_name: str) -> bool:
    return gesture_name in CONFIRM_GESTURES


def has_pending() -> bool:
    with _lock:
        return _pending_gesture is not None


def show(gesture_name: str, on_result) -> None:
    """
    Exibe notificação com botões Confirmar / Cancelar.
    on_result(confirmed: bool) é chamado quando o usuário decide.
    """
    global _pending_gesture, _pending_callback, _timeout_timer

    emoji, label = CONFIRM_GESTURES.get(gesture_name, ("❓", gesture_name))

    with _lock:
        # Cancela confirmação anterior se houver
        _cancel_timeout()
        _pending_gesture = gesture_name
        _pending_callback = on_result

        # Timeout automático
        _timeout_timer = threading.Timer(TIMEOUT_SECONDS, _on_timeout)
        _timeout_timer.daemon = True
        _timeout_timer.start()

    # Lança notify-send com ações em thread separada para não bloquear
    threading.Thread(target=_send_notification, args=(emoji, label, on_result), daemon=True).start()


def _send_notification(emoji: str, label: str, on_result) -> None:
    """
    Envia notificação com botões de ação e aguarda a resposta.
    notify-send --action retorna o id da ação escolhida no stdout.
    """
    try:
        result = subprocess.run(
            [
                "notify-send",
                f"{emoji}  {label}",
                "👍 Joinha ou clique em Confirmar para executar",
                "--icon", "dialog-question",
                "--urgency", "normal",
                "--expire-time", str(TIMEOUT_SECONDS * 1000),
                "--action", "confirm=✅ Confirmar",
                "--action", "cancel=❌ Cancelar",
                "--wait",   # aguarda o usuário clicar
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS + 1,
        )

        action = result.stdout.strip()

        with _lock:
            # Se já foi respondido pelo gesto (Joinha/punho), não chamar de novo
            if _pending_gesture is None:
                return
            _clear_pending()

        confirmed = (action == "confirm")
        log.info("Confirmação via botão: %s → %s", label, "ACEITA" if confirmed else "CANCELADA")
        on_result(confirmed)

    except subprocess.TimeoutExpired:
        with _lock:
            if _pending_gesture is None:
                return
            _clear_pending()
        on_result(False)
    except Exception as ex:
        log.warning("Erro na notificação de confirmação: %s", ex)
        with _lock:
            _clear_pending()
        on_result(False)


def confirm_current() -> bool:
    """Confirma via gesto Joinha detectado pela câmera."""
    global _pending_callback
    with _lock:
        if _pending_gesture is None:
            return False
        cb = _pending_callback
        gesture = _pending_gesture
        _cancel_timeout()
        _clear_pending()

    if cb:
        log.info("Confirmação via gesto Joinha: %s → ACEITA", gesture)
        cb(True)
    return True


def cancel_current() -> bool:
    """Cancela via gesto punho detectado pela câmera."""
    global _pending_callback
    with _lock:
        if _pending_gesture is None:
            return False
        cb = _pending_callback
        gesture = _pending_gesture
        _cancel_timeout()
        _clear_pending()

    if cb:
        log.info("Confirmação via gesto Punho: %s → CANCELADA", gesture)
        cb(False)
    return True


def _on_timeout() -> None:
    global _pending_callback
    with _lock:
        if _pending_gesture is None:
            return
        cb = _pending_callback
        gesture = _pending_gesture
        _clear_pending()

    if cb:
        log.info("Confirmação timeout: %s → CANCELADA", gesture)
        cb(False)


def _cancel_timeout() -> None:
    """Deve ser chamado com _lock adquirido."""
    global _timeout_timer
    if _timeout_timer is not None:
        _timeout_timer.cancel()
        _timeout_timer = None


def _clear_pending() -> None:
    """Deve ser chamado com _lock adquirido."""
    global _pending_gesture, _pending_callback, _timeout_timer
    _pending_gesture  = None
    _pending_callback = None
    _timeout_timer    = None
