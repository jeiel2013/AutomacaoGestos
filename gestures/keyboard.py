#!/usr/bin/env python3
"""
gestures/keyboard.py
--------------------
Envia eventos de teclado e mouse no Windows usando pyautogui.
Substitui o evdev (Linux-only) por uma implementação 100% Windows.

Uso no custom.json — mesmo formato de antes:
  ["KEY",    "ctrl+t"]      — combinação de teclas
  ["KEY",    "alt+F4"]      — fechar janela
  ["SCROLL", "up"]          — scroll para cima
  ["SCROLL", "down"]        — scroll para baixo
  ["CMD",    "notepad"]     — executa comando externo
"""

import subprocess
import time
import logging

log = logging.getLogger(__name__)

try:
    import pyautogui
    pyautogui.FAILSAFE = False   # desativa canto superior esquerdo como stop
    pyautogui.PAUSE    = 0.0     # sem delay entre ações (controlamos nós)
    PYAUTOGUI_OK = True
except ImportError:
    PYAUTOGUI_OK = False
    log.warning("pyautogui não encontrado. Execute: pip install pyautogui")

# ── Mapa de nomes → teclas pyautogui ─────────────────────────────────────────
# pyautogui usa strings como 'ctrl', 'alt', 'win', etc.
# Referência completa: pyautogui.KEY_NAMES
KEY_ALIASES = {
    "super":     "win",
    "return":    "enter",
    "escape":    "esc",
    "del":       "delete",
    "pageup":    "pageup",
    "pagedown":  "pagedown",
    "plus":      "=",
    "equal":     "=",
}

def _normalize_key(key: str) -> str:
    """Normaliza nome de tecla para o formato do pyautogui."""
    k = key.lower().strip()
    return KEY_ALIASES.get(k, k)

def _parse_combo(combo: str) -> list[str]:
    """Converte 'ctrl+shift+t' em lista de teclas normalizadas."""
    parts = combo.lower().replace("-", "+").split("+")
    return [_normalize_key(p.strip()) for p in parts if p.strip()]

def send_key(combo: str) -> bool:
    """
    Pressiona uma combinação de teclas.
    Exemplo: send_key("ctrl+t")  send_key("alt+F4")
    """
    if not PYAUTOGUI_OK:
        return False
    keys = _parse_combo(combo)
    if not keys:
        return False
    try:
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        return True
    except Exception as ex:
        log.warning("send_key erro: %s", ex)
        return False

def send_scroll(direction: str, amount: int = 3) -> bool:
    """
    Envia evento de scroll.
    direction: 'up' ou 'down'
    """
    if not PYAUTOGUI_OK:
        return False
    try:
        clicks = amount if direction == "up" else -amount
        pyautogui.scroll(clicks)
        return True
    except Exception as ex:
        log.warning("send_scroll erro: %s", ex)
        return False

def send_cmd(cmd: list) -> bool:
    """Executa um comando externo (ex: abrir aplicativo)."""
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
        return True
    except Exception as ex:
        log.warning("send_cmd erro: %s", ex)
        return False

def dispatch(action: list) -> bool:
    """
    Ponto de entrada principal. Recebe lista do custom.json e despacha.

    Formatos:
      ["KEY",    "ctrl+t"]        — combinação de teclas
      ["SCROLL", "up"]            — scroll
      ["SCROLL", "down", "5"]     — scroll com quantidade
      ["CMD",    "notepad"]       — comando externo
      (outro formato)             — tenta como comando externo
    """
    if not action:
        return False
    kind = action[0].upper()

    if kind == "KEY" and len(action) >= 2:
        return send_key(action[1])
    if kind == "SCROLL" and len(action) >= 2:
        amount = int(action[2]) if len(action) >= 3 else 3
        return send_scroll(action[1], amount)
    if kind == "CMD" and len(action) >= 2:
        return send_cmd(action[1:])

    # fallback: trata a lista inteira como comando externo
    return send_cmd(action)

def close() -> None:
    """Compatibilidade com o contrato da versão Linux (sem-op no Windows)."""
    pass
