#!/usr/bin/env python3
"""
overlay.py
----------
Notificação discreta ao lado da bandeja mostrando o emoji do gesto detectado.
Usa notify-send (libnotify) — aparece no canto superior direito nativamente.
"""

import subprocess
from pathlib import Path
import tempfile
import os

# ── Ícones temporários para cada gesto ───────────────────────────────────────
# O notify-send aceita caminho de imagem como ícone
_icon_cache: dict[str, str] = {}

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

def _make_emoji_icon(emoji: str) -> str:
    """
    Gera um PNG 64x64 com o emoji usando Pillow e retorna o caminho.
    Cacheia para não recriar a cada gesto.
    """
    if emoji in _icon_cache:
        return _icon_cache[emoji]

    try:
        from PIL import Image, ImageDraw, ImageFont
        import unicodedata

        img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Tenta usar fonte do sistema que suporte emoji
        font = None
        font_paths = [
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
            "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
        ]
        for fp in font_paths:
            if Path(fp).exists():
                try:
                    font = ImageFont.truetype(fp, 48)
                    break
                except Exception:
                    pass

        if font:
            draw.text((8, 4), emoji, font=font, embedded_color=True)
        else:
            # fallback sem emoji colorido
            draw.text((8, 8), emoji, fill=(255, 255, 255, 255))

        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", delete=False,
            prefix="gesture_overlay_"
        )
        img.save(tmp.name)
        _icon_cache[emoji] = tmp.name
        return tmp.name

    except Exception:
        return "input-mouse"   # ícone do sistema como fallback


def show(gesture_name: str, gesture_type: str = "static") -> None:
    """
    Exibe notificação discreta com o emoji do gesto.
    Aparece ao lado da bandeja, some automaticamente em 1.5s.
    """
    emoji, label = GESTURE_INFO.get(gesture_name, ("✋", gesture_name))

    icon_path = _make_emoji_icon(emoji)

    subprocess.Popen(
        [
            "notify-send",
            emoji,                      # título = só o emoji (grande)
            "--icon", icon_path,
            "--expire-time", "1500",    # 1.5 segundos
            "--urgency", "low",         # não interrompe foco
            "--hint", "int:transient:1",# some do histórico de notificações
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
