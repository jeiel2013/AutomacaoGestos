#!/usr/bin/env python3
"""
gestures/dynamic.py
-------------------
Detecção de gestos DINÂMICOS.

Modo ML (preferencial): usa uma rede GRU treinada sobre sequências de
30 frames de landmarks normalizados (veja gestures/features.py e
gestures/gru_model.py). Reconhece gestos como acenar, deslizar, círculo,
pinça, zoom, apontar — com muito mais robustez do que thresholds fixos.

Modo fallback (regras geométricas): se nenhum modelo GRU treinado for
encontrado, usa os detectores originais (swipe, shake, círculo, tilt,
zoom por distância, etc.) baseados em thresholds — funciona
imediatamente, sem precisar coletar dados nem instalar PyTorch.

Como treinar seu próprio modelo:
  1. python collect_data.py dynamic NOME_DO_GESTO
     (repita o movimento completo 30-50 vezes por gesto)
  2. python train_dynamic.py
  3. Reinicie o gesture_control.py — o modelo treinado passa a ser
     usado automaticamente se existir em gestures/models/dynamic_gru.pt
"""

import json
import math
import logging
from pathlib import Path
from collections import deque

import numpy as np

from .features import extract_frame_vector, DYNAMIC_FEATURE_SIZE

log = logging.getLogger(__name__)

MODEL_DIR   = Path(__file__).parent / "models"
MODEL_PATH  = MODEL_DIR / "dynamic_gru.pt"
LABELS_PATH = MODEL_DIR / "dynamic_labels.json"

SEQ_LEN        = 30    # frames por sequência analisada pela GRU
MIN_CONFIDENCE = 0.70  # confiança mínima do modelo para aceitar a predição

_ml_ready = False
_model    = None
_labels   = None
_torch    = None

try:
    import torch as _torch_module
    _torch = _torch_module

    if MODEL_PATH.exists() and LABELS_PATH.exists():
        from .gru_model import GestureGRU

        with open(LABELS_PATH, encoding="utf-8") as f:
            _labels = json.load(f)

        _model = GestureGRU(
            input_size=DYNAMIC_FEATURE_SIZE,
            hidden_size=64,
            num_layers=1,
            num_classes=len(_labels),
        )
        _model.load_state_dict(_torch.load(MODEL_PATH, map_location="cpu"))
        _model.eval()
        _ml_ready = True
        log.info("Modelo GRU de gestos dinâmicos carregado (%d classes).", len(_labels))
    else:
        log.info("Nenhum modelo dinâmico (GRU) treinado — usando detectores geométricos.")
except ImportError:
    log.warning("PyTorch não instalado — usando detectores geométricos (sem ML). "
                "Instale com: pip install torch --index-url https://download.pytorch.org/whl/cpu")


# ── Buffer para o modelo ML (sequência de vetores normalizados) ──────────────
_seq_buffer = deque(maxlen=SEQ_LEN)

# ── Buffers para os detectores geométricos (fallback) ────────────────────────
HISTORY_SIZE = 25
_palm      = deque(maxlen=HISTORY_SIZE)
_wrist     = deque(maxlen=HISTORY_SIZE)
_tip       = deque(maxlen=HISTORY_SIZE)
_hand_dist = deque(maxlen=HISTORY_SIZE)

MIN_SWIPE_DIST  = 0.18
MIN_SHAKE_FLIPS = 3
MIN_CIRCLE_DEG  = 280
MIN_ZOOM_DELTA  = 0.12
MIN_Z_DELTA     = 0.08
MIN_TILT_DEG    = 25
MIN_MOTION_GATE = 0.045


# ══════════════════════════════════════════════════════════════════════════════
#  ALIMENTAÇÃO DOS BUFFERS (ML + geométrico, sempre em paralelo)
# ══════════════════════════════════════════════════════════════════════════════

def update(hand_landmarks):
    """
    Alimenta os buffers com os dados da mão principal.
    Chame uma vez por frame — alimenta tanto o buffer do modelo ML
    quanto os buffers dos detectores geométricos (fallback).
    """
    lm = hand_landmarks.landmark

    # Buffer do modelo ML — vetor normalizado de 63 valores
    try:
        _seq_buffer.append(extract_frame_vector(lm))
    except Exception:
        pass

    # Buffers dos detectores geométricos (fallback)
    _palm.append( (lm[9].x,  lm[9].y,  lm[9].z)  )
    _wrist.append((lm[0].x,  lm[0].y)             )
    _tip.append(  (lm[12].x, lm[12].y)            )


def update_two_hands(hand1, hand2):
    """
    Alimenta o buffer de distância entre duas mãos, usado pelo
    detector geométrico de zoom (o modelo ML não usa isso).
    """
    lm1  = hand1.landmark
    lm2  = hand2.landmark
    dist = math.hypot(lm1[9].x - lm2[9].x, lm1[9].y - lm2[9].y)
    _hand_dist.append(dist)


def reset():
    """Limpa todos os buffers. Chame após detectar e executar um gesto."""
    _seq_buffer.clear()
    _palm.clear()
    _wrist.clear()
    _tip.clear()
    _hand_dist.clear()


# ══════════════════════════════════════════════════════════════════════════════
#  MODO ML — GRU
# ══════════════════════════════════════════════════════════════════════════════

def _classify_ml():
    """Roda a sequência acumulada pela GRU treinada, se o buffer estiver cheio."""
    if len(_seq_buffer) < SEQ_LEN:
        return None
    try:
        seq = np.stack(list(_seq_buffer), axis=0)                     # (30, 63)
        x   = _torch.tensor(seq, dtype=_torch.float32).unsqueeze(0)   # (1, 30, 63)
        with _torch.no_grad():
            logits = _model(x)
            probs  = _torch.softmax(logits, dim=1)[0]
            idx    = int(_torch.argmax(probs))
            conf   = float(probs[idx])
        if conf < MIN_CONFIDENCE:
            return None
        return _labels[idx]
    except Exception as ex:
        log.warning("Erro na predição GRU: %s", ex)
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  MODO FALLBACK — detectores geométricos (regras/thresholds)
# ══════════════════════════════════════════════════════════════════════════════

def _detect_swipe():
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
    if len(_palm) < 8:
        return None
    recent = list(_palm)[-8:]
    dx     = recent[-1][0] - recent[0][0]
    dy     = recent[-1][1] - recent[0][1]
    dist   = math.hypot(dx, dy)
    if dist < 0.20:
        return None
    angle = math.degrees(math.atan2(dy, dx))
    if  -40 < angle <  40:  return "SWIPE_RAPIDO_DIREITA"
    if   140 < abs(angle):  return "SWIPE_RAPIDO_ESQUERDA"
    if  -130 < angle < -50: return "SWIPE_RAPIDO_CIMA"
    if    50 < angle < 130: return "SWIPE_RAPIDO_BAIXO"
    return None


def _detect_shake():
    if len(_palm) < HISTORY_SIZE:
        return None
    xs       = [p[0] for p in _palm]
    flips    = 0
    prev_dir = None
    for i in range(1, len(xs)):
        d = xs[i] - xs[i - 1]
        if abs(d) < 0.005:
            continue
        cur_dir = 1 if d > 0 else -1
        if prev_dir is not None and cur_dir != prev_dir:
            flips += 1
        prev_dir = cur_dir
    return "SHAKE" if flips >= MIN_SHAKE_FLIPS else None


def _detect_circle():
    if len(_palm) < HISTORY_SIZE:
        return None
    pts = [(p[0], p[1]) for p in _palm]
    cx  = sum(p[0] for p in pts) / len(pts)
    cy  = sum(p[1] for p in pts) / len(pts)
    angles    = [math.atan2(p[1] - cy, p[0] - cx) for p in pts]
    total_rot = 0.0
    for i in range(len(angles) - 1):
        diff       = angles[i + 1] - angles[i]
        diff       = (diff + math.pi) % (2 * math.pi) - math.pi
        total_rot += diff
    deg = abs(math.degrees(total_rot))
    if deg >= MIN_CIRCLE_DEG:
        return "CIRCLE_CW" if total_rot < 0 else "CIRCLE_CCW"
    return None


def _detect_zoom():
    if len(_hand_dist) < HISTORY_SIZE:
        return None
    delta = _hand_dist[-1] - _hand_dist[0]
    if  delta >  MIN_ZOOM_DELTA: return "ZOOM_IN"
    if  delta < -MIN_ZOOM_DELTA: return "ZOOM_OUT"
    return None


def _detect_push_pull():
    if len(_palm) < HISTORY_SIZE:
        return None
    zs = [p[2] for p in _palm]
    dz = zs[-1] - zs[0]
    if dz < -MIN_Z_DELTA: return "PUSH_FRENTE"
    if dz >  MIN_Z_DELTA: return "PULL_ATRAS"
    return None


def _detect_tilt():
    if len(_wrist) < 5 or len(_palm) < 5:
        return None
    wx = sum(p[0] for p in list(_wrist)[-5:]) / 5
    wy = sum(p[1] for p in list(_wrist)[-5:]) / 5
    px = sum(p[0] for p in list(_palm) [-5:]) / 5
    py = sum(p[1] for p in list(_palm) [-5:]) / 5
    angle     = math.degrees(math.atan2(py - wy, px - wx))
    deviation = abs(abs(angle) - 90)
    if deviation > MIN_TILT_DEG:
        return "TILT_DIREITA" if angle > 0 else "TILT_ESQUERDA"
    return None


def _detect_wave_w():
    if len(_palm) < HISTORY_SIZE:
        return None
    ys       = [p[1] for p in _palm]
    flips_y  = 0
    prev_dir = None
    segment  = 0.0
    for i in range(1, len(ys)):
        d = ys[i] - ys[i - 1]
        if abs(d) < 0.008:
            continue
        cur_dir  = 1 if d > 0 else -1
        segment += abs(d)
        if prev_dir is not None and cur_dir != prev_dir:
            if segment > 0.06:
                flips_y += 1
            segment = 0.0
        prev_dir = cur_dir
    return "WAVE_W" if flips_y >= 2 else None


def _detect_figure_eight():
    if len(_palm) < HISTORY_SIZE:
        return None
    pts    = [(p[0], p[1]) for p in _palm]
    cx     = sum(p[0] for p in pts) / len(pts)
    cy     = sum(p[1] for p in pts) / len(pts)
    angles = [math.atan2(p[1] - cy, p[0] - cx) for p in pts]
    acc          = 0.0
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


def _movement_amount() -> float:
    if len(_palm) < 4:
        return 0.0
    xs = [p[0] for p in _palm]
    ys = [p[1] for p in _palm]
    amp_x = max(xs) - min(xs)
    amp_y = max(ys) - min(ys)
    return math.hypot(amp_x, amp_y)


def has_enough_motion() -> bool:
    return _movement_amount() >= MIN_MOTION_GATE


def _classify_rules():
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


# ══════════════════════════════════════════════════════════════════════════════
#  CLASSIFICADOR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def classify():
    """
    Usa o modelo GRU se disponível e o buffer estiver cheio; caso
    contrário, cai automaticamente para os detectores geométricos.

    Os dois modos NÃO são misturados no mesmo ciclo: se o modelo ML
    está carregado mas o buffer ainda não encheu (ou a confiança foi
    baixa), retorna None em vez de tentar as regras geométricas —
    isso evita resultados inconsistentes entre os dois sistemas.
    """
    if _ml_ready:
        return _classify_ml()
    return _classify_rules()
