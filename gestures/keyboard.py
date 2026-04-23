#!/usr/bin/env python3
"""
gestures/keyboard.py
--------------------
Envia eventos de teclado e mouse diretamente ao kernel via /dev/uinput
usando python-evdev. Funciona em Wayland, X11 e TTY sem nenhum daemon.

Requisitos:
  - Usuário no grupo 'input'  (sudo usermod -aG input $USER)
  - /dev/uinput acessível     (ls -la /dev/uinput)
  - pip install evdev

Uso no custom.json:
  Os comandos agora são listas de strings no formato:
    ["KEY", "ctrl+t"]          — pressiona Ctrl+T
    ["KEY", "alt+F4"]          — pressiona Alt+F4
    ["SCROLL", "up"]           — scroll para cima
    ["SCROLL", "down"]         — scroll para baixo
    ["CMD", "nautilus"]        — executa comando externo (fallback)

  O gesture_control.py detecta o primeiro elemento e chama a função certa.
"""

import time
import subprocess
from pathlib import Path

try:
    import evdev
    from evdev import UInput, ecodes as e
    EVDEV_OK = True
except ImportError:
    EVDEV_OK = False

# ── Mapa de nomes de tecla → código evdev ─────────────────────────────────────
KEY_MAP = {
    # Modificadores
    "ctrl":      e.KEY_LEFTCTRL,
    "shift":     e.KEY_LEFTSHIFT,
    "alt":       e.KEY_LEFTALT,
    "super":     e.KEY_LEFTMETA,
    "win":       e.KEY_LEFTMETA,

    # Letras
    "a": e.KEY_A, "b": e.KEY_B, "c": e.KEY_C, "d": e.KEY_D,
    "e": e.KEY_E, "f": e.KEY_F, "g": e.KEY_G, "h": e.KEY_H,
    "i": e.KEY_I, "j": e.KEY_J, "k": e.KEY_K, "l": e.KEY_L,
    "m": e.KEY_M, "n": e.KEY_N, "o": e.KEY_O, "p": e.KEY_P,
    "q": e.KEY_Q, "r": e.KEY_R, "s": e.KEY_S, "t": e.KEY_T,
    "u": e.KEY_U, "v": e.KEY_V, "w": e.KEY_W, "x": e.KEY_X,
    "y": e.KEY_Y, "z": e.KEY_Z,

    # Números
    "0": e.KEY_0, "1": e.KEY_1, "2": e.KEY_2, "3": e.KEY_3,
    "4": e.KEY_4, "5": e.KEY_5, "6": e.KEY_6, "7": e.KEY_7,
    "8": e.KEY_8, "9": e.KEY_9,

    # Funções
    "f1":  e.KEY_F1,  "f2":  e.KEY_F2,  "f3":  e.KEY_F3,  "f4":  e.KEY_F4,
    "f5":  e.KEY_F5,  "f6":  e.KEY_F6,  "f7":  e.KEY_F7,  "f8":  e.KEY_F8,
    "f9":  e.KEY_F9,  "f10": e.KEY_F10, "f11": e.KEY_F11, "f12": e.KEY_F12,

    # Especiais
    "return":    e.KEY_ENTER,
    "enter":     e.KEY_ENTER,
    "escape":    e.KEY_ESC,
    "esc":       e.KEY_ESC,
    "tab":       e.KEY_TAB,
    "space":     e.KEY_SPACE,
    "backspace": e.KEY_BACKSPACE,
    "delete":    e.KEY_DELETE,
    "del":       e.KEY_DELETE,
    "insert":    e.KEY_INSERT,
    "home":      e.KEY_HOME,
    "end":       e.KEY_END,
    "pageup":    e.KEY_PAGEUP,
    "pagedown":  e.KEY_PAGEDOWN,
    "up":        e.KEY_UP,
    "down":      e.KEY_DOWN,
    "left":      e.KEY_LEFT,
    "right":     e.KEY_RIGHT,

    # Símbolos comuns
    "plus":      e.KEY_EQUAL,     # Ctrl++ usa KEY_EQUAL
    "equal":     e.KEY_EQUAL,
    "minus":     e.KEY_MINUS,
    "slash":     e.KEY_SLASH,
    "comma":     e.KEY_COMMA,
    "dot":       e.KEY_DOT,
}

# Capacidades necessárias para o dispositivo virtual
_CAPABILITIES = {
    e.EV_KEY: list(KEY_MAP.values()) + [
        e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE,
    ],
    e.EV_REL: [e.REL_WHEEL, e.REL_X, e.REL_Y],
}

# Instância global do dispositivo virtual (criada uma vez, reutilizada)
_ui: UInput | None = None


def _get_device() -> "UInput | None":
    """Retorna o dispositivo uinput, criando se necessário."""
    global _ui
    if not EVDEV_OK:
        return None
    if _ui is None:
        try:
            _ui = UInput(_CAPABILITIES, name="gesture-control-virtual-kbd")
        except Exception as ex:
            return None
    return _ui


def _parse_combo(combo: str) -> list[int]:
    """
    Converte 'ctrl+shift+t' em lista de keycodes evdev.
    Aceita maiúsculas e minúsculas.
    """
    parts = combo.lower().replace("-", "+").split("+")
    codes = []
    for part in parts:
        part = part.strip()
        if part in KEY_MAP:
            codes.append(KEY_MAP[part])
        # ignora partes desconhecidas silenciosamente
    return codes


def send_key(combo: str) -> bool:
    """
    Pressiona e solta uma combinação de teclas.
    Exemplo: send_key("ctrl+t")  send_key("alt+F4")
    Retorna True se bem-sucedido.
    """
    ui = _get_device()
    if ui is None:
        return False

    codes = _parse_combo(combo)
    if not codes:
        return False

    try:
        # press all keys in order
        for code in codes:
            ui.write(e.EV_KEY, code, 1)
        ui.syn()
        time.sleep(0.02)
        # release in reverse order
        for code in reversed(codes):
            ui.write(e.EV_KEY, code, 0)
        ui.syn()
        return True
    except Exception:
        return False


def send_scroll(direction: str, amount: int = 3) -> bool:
    """
    Envia evento de scroll.
    direction: 'up' ou 'down'
    """
    ui = _get_device()
    if ui is None:
        return False

    value = amount if direction == "up" else -amount
    try:
        ui.write(e.EV_REL, e.REL_WHEEL, value)
        ui.syn()
        return True
    except Exception:
        return False


def send_cmd(cmd: list) -> bool:
    """Executa um comando externo como fallback (ex: abrir aplicativo)."""
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def dispatch(action: list) -> bool:
    """
    Ponto de entrada principal. Recebe uma lista do custom.json e despacha.

    Formatos aceitos:
      ["KEY",    "ctrl+t"]       — combinação de teclas via evdev
      ["SCROLL", "up"]           — scroll via evdev
      ["SCROLL", "down", "5"]    — scroll com quantidade customizada
      ["CMD",    "nautilus"]     — comando externo
      ["CMD",    "nautilus", "-w"] — comando com argumentos
      (qualquer outro formato)   — tenta executar como comando externo direto
    """
    if not action:
        return False

    kind = action[0].upper() if action else ""

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
    """Fecha o dispositivo virtual. Chame ao encerrar o programa."""
    global _ui
    if _ui is not None:
        try:
            _ui.close()
        except Exception:
            pass
        _ui = None
