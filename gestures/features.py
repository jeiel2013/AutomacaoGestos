#!/usr/bin/env python3
"""
gestures/features.py
---------------------
Extração de características (features) a partir dos 21 landmarks da mão,
usadas pelos classificadores de Machine Learning (estático e dinâmico).

Em vez de alimentar coordenadas cruas (x, y, z), calculamos:
  - Distâncias normalizadas entre pontos-chave (abertura da mão, entre pontas)
  - Ângulos das articulações de cada dedo
  - Orientação da palma (ângulo do vetor pulso→dedo médio)

Isso reduz a sensibilidade à posição da mão na tela e à distância da
câmera, tornando o reconhecimento mais robusto do que comparar apenas
coordenadas cruas.
"""

import numpy as np

# Índices dos 21 landmarks do MediaPipe Hands
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP      = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP     = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP         = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP     = 17, 18, 19, 20

FINGER_TIPS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
FINGER_MCPS = [THUMB_MCP, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
FINGER_PIPS = [THUMB_IP,  INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]


def _to_array(lm) -> np.ndarray:
    """Converte lista de landmarks do MediaPipe em array (21, 3)."""
    return np.array([[p.x, p.y, p.z] for p in lm], dtype=np.float32)


def normalize_landmarks(lm) -> np.ndarray:
    """
    Normaliza os landmarks para serem invariantes a posição e escala:
      1. Translada tudo para o pulso (landmark 0) ficar na origem
      2. Escala pela distância pulso → base do dedo médio (tamanho da mão)

    Retorna array (21, 3) normalizado.
    """
    pts    = _to_array(lm)
    origin = pts[WRIST].copy()
    pts   -= origin

    scale = np.linalg.norm(pts[MIDDLE_MCP])
    if scale < 1e-6:
        scale = 1e-6
    pts /= scale

    return pts


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Ângulo em graus no vértice b, formado pelos pontos a-b-c."""
    v1 = a - b
    v2 = c - b
    denom = (np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom < 1e-6:
        denom = 1e-6
    cos_ang = np.clip(np.dot(v1, v2) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_ang)))


def extract_static_features(lm) -> np.ndarray:
    """
    Extrai um vetor de features robusto para classificação de gestos
    ESTÁTICOS.

    Features incluídas:
      - 5 ângulos de flexão dos dedos (MCP-PIP-TIP)
      - 10 distâncias normalizadas entre pares de pontas de dedos
      - 5 distâncias normalizadas ponta→pulso (abertura de cada dedo)
      - 1 métrica de abertura geral da mão (média das 5 acima)
      - 2 componentes de orientação da palma (seno/cosseno do ângulo)

    Total: 5 + 10 + 5 + 1 + 2 = 23 features
    """
    pts = normalize_landmarks(lm)

    # Ângulos de flexão de cada dedo (MCP -> PIP -> TIP)
    angles = []
    for mcp, pip, tip in zip(FINGER_MCPS, FINGER_PIPS, FINGER_TIPS):
        angles.append(_angle(pts[mcp], pts[pip], pts[tip]))

    # Distâncias entre pontas de dedos — todas as 10 combinações possíveis
    tip_dists = []
    for i in range(len(FINGER_TIPS)):
        for j in range(i + 1, len(FINGER_TIPS)):
            d = float(np.linalg.norm(pts[FINGER_TIPS[i]] - pts[FINGER_TIPS[j]]))
            tip_dists.append(d)

    # Abertura de cada dedo: distância da ponta até o pulso (já normalizado)
    tip_to_wrist = [float(np.linalg.norm(pts[tip])) for tip in FINGER_TIPS]
    openness     = float(np.mean(tip_to_wrist))

    # Orientação da palma: ângulo do vetor pulso → base do médio, plano XY
    palm_vec    = pts[MIDDLE_MCP] - pts[WRIST]
    palm_angle  = float(np.arctan2(palm_vec[1], palm_vec[0]))
    orientation = [float(np.sin(palm_angle)), float(np.cos(palm_angle))]

    features = np.array(
        angles + tip_dists + tip_to_wrist + [openness] + orientation,
        dtype=np.float32,
    )
    return features


def extract_frame_vector(lm) -> np.ndarray:
    """
    Extrai o vetor "cru" normalizado de um frame, para uso em SEQUÊNCIAS
    no classificador dinâmico (GRU). Retorna os 21 landmarks normalizados
    achatados em um vetor de 63 números (21 × 3).
    """
    pts = normalize_landmarks(lm)
    return pts.flatten()   # shape (63,)


STATIC_FEATURE_SIZE  = 23
DYNAMIC_FEATURE_SIZE = 63
