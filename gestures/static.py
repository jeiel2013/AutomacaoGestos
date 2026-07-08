#!/usr/bin/env python3
"""
gestures/static.py
------------------
Classificação de gestos ESTÁTICOS.

Modo ML (preferencial): usa um modelo treinado (Random Forest ou MLP via
scikit-learn) sobre features robustas — ângulos, distâncias e orientação
da palma (veja gestures/features.py). É mais preciso e menos sensível a
posição/ângulo da mão do que comparar apenas "dedo levantado ou não".

Modo fallback (regras fixas): se nenhum modelo treinado for encontrado,
usa a tabela original baseada em dedos levantados — funciona
imediatamente, sem precisar coletar dados nem instalar scikit-learn.

Como treinar seu próprio modelo:
  1. python collect_data.py static NOME_DO_GESTO
     (repita para cada gesto — recomenda-se 60-100 amostras por gesto,
     variando levemente ângulo e distância da mão)
  2. python train_static.py
  3. Reinicie o gesture_control.py — o modelo treinado passa a ser
     usado automaticamente se existir em gestures/models/static_model.joblib
"""

import logging
from pathlib import Path

from .features import extract_static_features

log = logging.getLogger(__name__)

MODEL_DIR   = Path(__file__).parent / "models"
MODEL_PATH  = MODEL_DIR / "static_model.joblib"
LABELS_PATH = MODEL_DIR / "static_labels.joblib"

MIN_CONFIDENCE = 0.65   # confiança mínima do modelo para aceitar a predição

_model    = None
_labels   = None
_ml_ready = False

try:
    import joblib
    if MODEL_PATH.exists() and LABELS_PATH.exists():
        _model    = joblib.load(MODEL_PATH)
        _labels   = joblib.load(LABELS_PATH)
        _ml_ready = True
        log.info("Modelo ML de gestos estáticos carregado (%s).", MODEL_PATH.name)
    else:
        log.info("Nenhum modelo estático treinado encontrado — usando regras fixas.")
except ImportError:
    log.warning("scikit-learn/joblib não instalados — usando regras fixas. "
                "Instale com: pip install scikit-learn joblib")


# ══════════════════════════════════════════════════════════════════════════════
#  MODO FALLBACK — dedo levantado ou não (regras fixas)
# ══════════════════════════════════════════════════════════════════════════════

def fingers_up(lm):
    """
    Recebe hand_landmarks.landmark e retorna lista de 5 inteiros (0 ou 1).
    Índice 0 = polegar, 1..4 = indicador ao mínimo.

    Mantido mesmo no modo ML porque o gesture_control.py chama esta
    função diretamente para detectar o duplo-V da trava mestra de
    gestos dinâmicos (_is_double_v).
    """
    tips = [4, 8, 12, 16, 20]
    pips = [3, 6, 10, 14, 18]
    result = []
    result.append(1 if lm[tips[0]].x < lm[pips[0]].x else 0)
    for tip, pip in zip(tips[1:], pips[1:]):
        result.append(1 if lm[tip].y < lm[pip].y else 0)
    return result


TABLE = {
    (0, 0, 0, 0, 0): "FECHAR_JANELA",
    (0, 1, 0, 0, 0): "SCROLL_CIMA",
    (0, 0, 1, 1, 1): "SCROLL_BAIXO",
    (0, 1, 1, 0, 0): "SELECIONAR_TUDO",
    (1, 1, 1, 1, 1): "DELETAR",
    (1, 0, 0, 0, 0): "CONFIRMAR",
    (0, 0, 0, 0, 1): "VOLTAR",
    (0, 1, 0, 0, 1): "TROCAR_JANELA",
    (1, 1, 0, 0, 1): "CAPTURA_TELA",
    (1, 0, 0, 0, 1): "WORKSPACE_DIR",
    (1, 1, 1, 0, 0): "NOVA_ABA",
    (0, 1, 1, 1, 0): "FECHAR_ABA",
    (0, 1, 1, 1, 1): "MAXIMIZAR",
    (1, 1, 1, 1, 0): "MINIMIZAR",
    (1, 1, 0, 0, 0): "DESFAZER",
    (0, 0, 1, 0, 0): "REFAZER",
}


def _classify_rules(lm):
    f = fingers_up(lm)
    return TABLE.get(tuple(f))


# ══════════════════════════════════════════════════════════════════════════════
#  MODO ML — Random Forest / MLP
# ══════════════════════════════════════════════════════════════════════════════

def _classify_ml(lm):
    features = extract_static_features(lm).reshape(1, -1)
    proba    = _model.predict_proba(features)[0]
    idx      = int(proba.argmax())
    conf     = float(proba[idx])

    if conf < MIN_CONFIDENCE:
        return None
    return _labels[idx]


# ══════════════════════════════════════════════════════════════════════════════
#  CLASSIFICADOR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def classify(hand_landmarks):
    """
    Recebe um objeto com .landmark (lista de 21 pontos do MediaPipe).
    Retorna o nome do gesto (str) ou None.

    Usa o modelo ML se disponível e treinado; caso contrário, cai
    automaticamente para as regras fixas baseadas em dedos levantados.
    """
    lm = hand_landmarks.landmark

    if _ml_ready:
        try:
            return _classify_ml(lm)
        except Exception as ex:
            log.warning("Erro na predição ML, usando fallback: %s", ex)

    return _classify_rules(lm)
