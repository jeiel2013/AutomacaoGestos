#!/usr/bin/env python3
"""
gestures/dynamic.py
-------------------
Detecção de gestos dinâmicos baseados em trajetória e movimento.

Como funciona:
  - Cada frame alimenta buffers de posição (deque de tamanho fixo)
  - classify() analisa os padrões acumulados e retorna o nome do gesto
  - reset() limpa os buffers após um gesto ser detectado

Tipos de gestos suportados:
  Swipe       — deslocamento linear em qualquer direção
  Swipe rápido— mesmo, mas em janela curta (prioridade maior)
  Shake       — vai-e-vem horizontal (inversões de direção)
  Círculo     — rotação acumulada > MIN_CIRCLE_DEG
  Zoom        — duas mãos se afastando ou aproximando
  Push/Pull   — movimento no eixo Z (profundidade)
  Tilt        — inclinação lateral da mão
  Wave W      — sobe-desce-sobe (exemplo de gesto totalmente personalizado)

Para adicionar um gesto novo:
  1. Escreva uma função _detect_NOME() → str | None
  2. Adicione-a em classify() na ordem de prioridade desejada
  3. Mapeie o nome retornado no custom.json

Thresholds (ajuste conforme necessário):
  MIN_SWIPE_DIST   — distância mínima para contar como swipe (0.0 a 1.0)
  MIN_SHAKE_FLIPS  — número mínimo de inversões de direção para shake
  MIN_CIRCLE_DEG   — graus mínimos de rotação para círculo
  MIN_ZOOM_DELTA   — variação mínima de distância entre mãos para zoom
  MIN_Z_DELTA      — variação mínima no eixo Z para push/pull
  MIN_TILT_DEG     — desvio mínimo em graus da vertical para tilt
"""

import math
from collections import deque

# ── Configuração do buffer ────────────────────────────────────────────────────
HISTORY_SIZE = 25          # frames analisados por vez (~1.6s a 15fps)

# ── Buffers de posição ────────────────────────────────────────────────────────
_palm      = deque(maxlen=HISTORY_SIZE)   # (x, y, z) — landmark 9 (palma)
_wrist     = deque(maxlen=HISTORY_SIZE)   # (x, y)    — landmark 0 (pulso)
_tip       = deque(maxlen=HISTORY_SIZE)   # (x, y)    — landmark 12 (ponta do médio)
_hand_dist = deque(maxlen=HISTORY_SIZE)   # distância entre duas mãos (zoom)

# ── Thresholds ────────────────────────────────────────────────────────────────
MIN_SWIPE_DIST  = 0.18
MIN_SHAKE_FLIPS = 3
MIN_CIRCLE_DEG  = 280
MIN_ZOOM_DELTA  = 0.12
MIN_Z_DELTA     = 0.08
MIN_TILT_DEG    = 25


# ══════════════════════════════════════════════════════════════════════════════
#  ALIMENTAÇÃO DOS BUFFERS
# ══════════════════════════════════════════════════════════════════════════════

def update(hand_landmarks):
    """
    Alimenta os buffers com os dados da mão detectada.
    Chame uma vez por frame para cada mão principal.
    """
    lm = hand_landmarks.landmark
    _palm.append( (lm[9].x,  lm[9].y,  lm[9].z)  )
    _wrist.append((lm[0].x,  lm[0].y)             )
    _tip.append(  (lm[12].x, lm[12].y)            )


def update_two_hands(hand1, hand2):
    """
    Alimenta o buffer de distância entre duas mãos para detecção de zoom.
    Chame somente quando MediaPipe detectar exatamente duas mãos.
    """
    lm1  = hand1.landmark
    lm2  = hand2.landmark
    dist = math.hypot(lm1[9].x - lm2[9].x, lm1[9].y - lm2[9].y)
    _hand_dist.append(dist)


def reset():
    """Limpa todos os buffers. Chame após detectar e executar um gesto."""
    _palm.clear()
    _wrist.clear()
    _tip.clear()
    _hand_dist.clear()


# ══════════════════════════════════════════════════════════════════════════════
#  DETECTORES INDIVIDUAIS
# ══════════════════════════════════════════════════════════════════════════════

def _detect_swipe():
    """
    Analisa o deslocamento total da palma ao longo do buffer completo.
    Retorna: SWIPE_DIREITA / SWIPE_ESQUERDA / SWIPE_CIMA / SWIPE_BAIXO
    """
    if len(_palm) < HISTORY_SIZE:
        return None

    xs   = [p[0] for p in _palm]
    ys   = [p[1] for p in _palm]
    dx   = xs[-1] - xs[0]
    dy   = ys[-1] - ys[0]
    dist = math.hypot(dx, dy)

    if dist < MIN_SWIPE_DIST:
        return None

    angle = math.degrees(math.atan2(dy, dx))

    if  -40 < angle <  40:  return "SWIPE_DIREITA"
    if   140 < abs(angle):  return "SWIPE_ESQUERDA"
    if  -130 < angle < -50: return "SWIPE_CIMA"
    if    50 < angle < 130: return "SWIPE_BAIXO"

    return None


def _detect_speed_swipe():
    """
    Versão rápida: analisa apenas os últimos 8 frames.
    Detecta gestos bruscos antes do buffer encher.
    Tem prioridade sobre _detect_swipe() no classify().
    """
    if len(_palm) < 8:
        return None

    recent = list(_palm)[-8:]
    dx     = recent[-1][0] - recent[0][0]
    dy     = recent[-1][1] - recent[0][1]
    dist   = math.hypot(dx, dy)

    # threshold ligeiramente maior para evitar falsos positivos na janela curta
    if dist < 0.20:
        return None

    angle = math.degrees(math.atan2(dy, dx))

    if  -40 < angle <  40:  return "SWIPE_RAPIDO_DIREITA"
    if   140 < abs(angle):  return "SWIPE_RAPIDO_ESQUERDA"
    if  -130 < angle < -50: return "SWIPE_RAPIDO_CIMA"
    if    50 < angle < 130: return "SWIPE_RAPIDO_BAIXO"

    return None


def _detect_shake():
    """
    Detecta movimento de balançar no eixo X (vai-e-vem).
    Conta inversões de direção horizontal; ignora micro-tremores.
    """
    if len(_palm) < HISTORY_SIZE:
        return None

    xs       = [p[0] for p in _palm]
    flips    = 0
    prev_dir = None

    for i in range(1, len(xs)):
        d = xs[i] - xs[i - 1]
        if abs(d) < 0.005:       # ignora ruído de câmera
            continue
        cur_dir = 1 if d > 0 else -1
        if prev_dir is not None and cur_dir != prev_dir:
            flips += 1
        prev_dir = cur_dir

    return "SHAKE" if flips >= MIN_SHAKE_FLIPS else None


def _detect_circle():
    """
    Detecta trajetória circular somando a rotação angular acumulada
    em torno do centróide do caminho percorrido.

    Retorna:
      CIRCLE_CW  — sentido horário
      CIRCLE_CCW — sentido anti-horário
    """
    if len(_palm) < HISTORY_SIZE:
        return None

    pts   = [(p[0], p[1]) for p in _palm]
    cx    = sum(p[0] for p in pts) / len(pts)
    cy    = sum(p[1] for p in pts) / len(pts)

    angles    = [math.atan2(p[1] - cy, p[0] - cx) for p in pts]
    total_rot = 0.0

    for i in range(len(angles) - 1):
        diff = angles[i + 1] - angles[i]
        # normaliza para [-π, π]
        diff       = (diff + math.pi) % (2 * math.pi) - math.pi
        total_rot += diff

    deg = abs(math.degrees(total_rot))

    if deg >= MIN_CIRCLE_DEG:
        return "CIRCLE_CW" if total_rot < 0 else "CIRCLE_CCW"

    return None


def _detect_zoom():
    """
    Detecta afastamento ou aproximação entre duas mãos.
    Requer que update_two_hands() tenha sido chamado neste ciclo.
    """
    if len(_hand_dist) < HISTORY_SIZE:
        return None

    delta = _hand_dist[-1] - _hand_dist[0]

    if  delta >  MIN_ZOOM_DELTA: return "ZOOM_IN"
    if  delta < -MIN_ZOOM_DELTA: return "ZOOM_OUT"

    return None


def _detect_push_pull():
    """
    Detecta movimento no eixo Z (profundidade em relação à câmera).
      Z diminui → mão se aproximou da câmera  → PUSH_FRENTE
      Z aumenta → mão se afastou da câmera    → PULL_ATRAS

    O eixo Z do MediaPipe é menos preciso que X e Y.
    Aumente MIN_Z_DELTA se tiver falsos positivos.
    """
    if len(_palm) < HISTORY_SIZE:
        return None

    zs = [p[2] for p in _palm]
    dz = zs[-1] - zs[0]

    if dz < -MIN_Z_DELTA: return "PUSH_FRENTE"
    if dz >  MIN_Z_DELTA: return "PULL_ATRAS"

    return None


def _detect_tilt():
    """
    Detecta inclinação lateral da mão medindo o ângulo entre
    o pulso (lm 0) e a palma (lm 9) em relação ao eixo vertical.
    Usa média dos últimos 5 frames para estabilidade.
    """
    if len(_wrist) < 5 or len(_palm) < 5:
        return None

    wx = sum(p[0] for p in list(_wrist)[-5:]) / 5
    wy = sum(p[1] for p in list(_wrist)[-5:]) / 5
    px = sum(p[0] for p in list(_palm) [-5:]) / 5
    py = sum(p[1] for p in list(_palm) [-5:]) / 5

    # ângulo do vetor pulso→palma em relação ao eixo X
    angle     = math.degrees(math.atan2(py - wy, px - wx))
    # desvio da vertical pura (±90°)
    deviation = abs(abs(angle) - 90)

    if deviation > MIN_TILT_DEG:
        return "TILT_DIREITA" if angle > 0 else "TILT_ESQUERDA"

    return None


def _detect_wave_w():
    """
    Gesto em forma de W: o movimento vertical sobe, desce e sobe de novo.
    Detecta 2 inversões de direção no eixo Y com amplitude real.

    Exemplo de uso: abrir o gerenciador de arquivos ou launcher.
    Para desativar: remova a chamada em classify() abaixo.
    """
    if len(_palm) < HISTORY_SIZE:
        return None

    ys       = [p[1] for p in _palm]
    flips_y  = 0
    prev_dir = None
    segment  = 0.0

    for i in range(1, len(ys)):
        d = ys[i] - ys[i - 1]
        if abs(d) < 0.008:        # ignora ruído
            continue
        cur_dir  = 1 if d > 0 else -1
        segment += abs(d)
        if prev_dir is not None and cur_dir != prev_dir:
            if segment > 0.06:    # só conta se o segmento teve amplitude real
                flips_y += 1
            segment = 0.0
        prev_dir = cur_dir

    return "WAVE_W" if flips_y >= 2 else None


def _detect_figure_eight():
    """
    Gesto em figura de 8: rotação que inverte sentido no meio.
    Detecta mudança de sinal na rotação angular acumulada com magnitude suficiente.

    Exemplo de uso: abrir menu de configurações.
    """
    if len(_palm) < HISTORY_SIZE:
        return None

    pts    = [(p[0], p[1]) for p in _palm]
    cx     = sum(p[0] for p in pts) / len(pts)
    cy     = sum(p[1] for p in pts) / len(pts)
    angles = [math.atan2(p[1] - cy, p[0] - cx) for p in pts]

    rots    = []
    acc     = 0.0
    sign_changes = 0
    last_sign    = None

    for i in range(len(angles) - 1):
        diff  = angles[i + 1] - angles[i]
        diff  = (diff + math.pi) % (2 * math.pi) - math.pi
        acc  += diff
        cur_sign = 1 if diff > 0 else -1
        if last_sign is not None and cur_sign != last_sign and abs(acc) > 1.0:
            sign_changes += 1
            acc = 0.0
        last_sign = cur_sign

    return "FIGURE_EIGHT" if sign_changes >= 2 else None


# ── Portão de movimento ────────────────────────────────────────────────────────
# Antes de gastar processamento tentando achar swipe/circle/tilt/etc, verifica
# se a mão realmente se moveu o suficiente no buffer inteiro. Se o deslocamento
# total (maior distância entre dois pontos quaisquer do trajeto) for pequeno,
# a mão está parada ou só tremendo — provavelmente é um gesto ESTÁTICO, então
# nem tenta classificar como dinâmico.
MIN_MOTION_GATE = 0.045   # deslocamento mínimo (0.0 a 1.0) para liberar os detectores


def _movement_amount() -> float:
    """
    Calcula o quanto a mão se moveu no buffer, usando a amplitude máxima
    (maior menos menor) em X e Y — mais robusto que só olhar início/fim,
    pois pega tremores em qualquer direção do trajeto.
    """
    if len(_palm) < 4:
        return 0.0

    xs = [p[0] for p in _palm]
    ys = [p[1] for p in _palm]

    amp_x = max(xs) - min(xs)
    amp_y = max(ys) - min(ys)

    return math.hypot(amp_x, amp_y)


def has_enough_motion() -> bool:
    """
    Retorna True se o movimento acumulado no buffer ultrapassa o portão.
    Uso externo: gesture_control.py chama antes de decidir se tenta
    gestos dinâmicos ou vai direto para os estáticos.
    """
    return _movement_amount() >= MIN_MOTION_GATE


# ══════════════════════════════════════════════════════════════════════════════
#  CLASSIFICADOR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def classify():
    """
    Tenta cada detector em ordem de prioridade — mas só se o portão de
    movimento estiver liberado. Se a mão está praticamente parada,
    retorna None imediatamente sem gastar processamento nos detectores
    (e sem risco de falso positivo por tremor).

    Ordem de prioridade (do mais para o menos prioritário):
      0. Portão de movimento — corta cedo se não houve deslocamento real
      1. Swipe rápido   — janela curta, detecta antes do buffer encher
      2. Zoom           — precisa de duas mãos
      3. Círculo        — movimento fechado e amplo
      4. Figura de 8    — variação do círculo
      5. Wave W         — sobe-desce-sobe
      6. Shake          — vai-e-vem horizontal
      7. Push/Pull      — profundidade Z
      8. Tilt           — inclinação
      9. Swipe normal   — deslocamento linear com buffer completo
    """
    # Zoom usa buffer separado (_hand_dist), então passa direto pelo portão —
    # ele já tem seu próprio threshold (MIN_ZOOM_DELTA) que cumpre o mesmo papel.
    zoom = _detect_zoom()
    if zoom:
        return zoom

    if not has_enough_motion():
        return None

    return (
        _detect_speed_swipe()   or
        _detect_circle()        or
        _detect_figure_eight()  or
        _detect_wave_w()        or
        _detect_shake()         or
        _detect_push_pull()     or
        _detect_tilt()          or
        _detect_swipe()
    )
