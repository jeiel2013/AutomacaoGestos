#!/usr/bin/env python3
"""
gestures/static.py
------------------
Gestos baseados na posição dos dedos num único frame.

Como adicionar um gesto novo:
  1. Descubra o padrão de dedos levantados: execute o script
     de debug (python3 debug_landmarks.py) e anote o vetor.
  2. Adicione a linha no dicionário TABLE abaixo.
  3. Mapeie o nome no custom.json.

Padrão do vetor: [polegar, indicador, médio, anelar, mínimo]
  1 = dedo levantado / aberto
  0 = dedo abaixado / fechado

Exemplos rápidos:
  [0,0,0,0,0] = punho fechado
  [1,1,1,1,1] = mão aberta
  [0,1,0,0,0] = só indicador (apontar)
  [0,1,1,0,0] = V / paz
  [1,0,0,0,0] = joinha / polegar para cima
  [0,0,0,0,1] = mindinho
  [0,1,0,0,1] = "rock" / chifres
  [1,1,0,0,1] = "I love you"
  [1,0,0,0,1] = "hang loose"
"""


# ── Detecta quais dedos estão levantados ──────────────────────────────────────
def fingers_up(lm):
    """
    Recebe hand_landmarks.landmark e retorna lista de 5 inteiros (0 ou 1).
    Índice 0 = polegar, 1..4 = indicador ao mínimo.
    """
    tips  = [4,  8, 12, 16, 20]   # pontas dos dedos
    pips  = [3,  6, 10, 14, 18]   # segunda articulação
    result = []

    # Polegar: compara X (horizontal) — difere dos outros pois dobra lateralmente
    # Para mão direita espelhada: ponta à esquerda do pip = aberto
    result.append(1 if lm[tips[0]].x < lm[pips[0]].x else 0)

    # Demais dedos: ponta acima (y menor) do pip = levantado
    for tip, pip in zip(tips[1:], pips[1:]):
        result.append(1 if lm[tip].y < lm[pip].y else 0)

    return result


# ── Tabela de gestos estáticos ────────────────────────────────────────────────
# Chave: tupla do vetor de dedos
# Valor: nome do gesto (usado para buscar a ação no custom.json)
TABLE = {
    (0, 0, 0, 0, 0): "FECHAR_JANELA",      # punho fechado
    (0, 1, 0, 0, 0): "SCROLL_CIMA",        # só indicador
    (0, 0, 1, 1, 1): "SCROLL_BAIXO",       # três dedos (sem polegar/indicador)
    (0, 1, 1, 0, 0): "SELECIONAR_TUDO",    # V / paz
    (1, 1, 1, 1, 1): "DELETAR",            # mão aberta
    (1, 0, 0, 0, 0): "CONFIRMAR",          # joinha
    (0, 0, 0, 0, 1): "VOLTAR",             # mindinho
    (0, 1, 0, 0, 1): "TROCAR_JANELA",      # chifres / rock
    (1, 1, 0, 0, 1): "CAPTURA_TELA",       # "I love you"
    (1, 0, 0, 0, 1): "WORKSPACE_DIR",      # hang loose
    (1, 1, 1, 0, 0): "NOVA_ABA",           # três dedos com polegar
    (0, 1, 1, 1, 0): "FECHAR_ABA",         # três do meio
    (0, 1, 1, 1, 1): "MAXIMIZAR",          # quatro dedos sem polegar
    (1, 1, 1, 1, 0): "MINIMIZAR",          # quatro dedos sem mínimo
    (1, 1, 0, 0, 0): "DESFAZER",           # polegar + indicador (pistola)
    (0, 0, 1, 0, 0): "REFAZER",            # só dedo médio
}


def classify(hand_landmarks):
    """
    Recebe um objeto hand_landmarks do MediaPipe.
    Retorna o nome do gesto (str) ou None.
    """
    lm = hand_landmarks.landmark
    f  = fingers_up(lm)
    return TABLE.get(tuple(f))
