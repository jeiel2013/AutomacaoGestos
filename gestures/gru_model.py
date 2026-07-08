#!/usr/bin/env python3
"""
gestures/gru_model.py
----------------------
Definição da rede GRU usada para classificar gestos DINÂMICOS.

Compartilhada entre train_dynamic.py (treino) e gestures/dynamic.py
(inferência) para garantir que a arquitetura seja sempre idêntica entre
o modelo salvo e o modelo carregado.

Entrada:  sequência de 30 frames × 63 valores (21 landmarks normalizados)
Saída:    logits para cada classe de gesto (aplique softmax por fora)
"""

import torch
import torch.nn as nn


class GestureGRU(nn.Module):
    """
    30 frames → 63 landmarks → GRU → Softmax → gesto

    input_size:  tamanho do vetor de cada frame (63 = 21 landmarks × 3)
    hidden_size: dimensão do estado oculto da GRU
    num_layers:  camadas empilhadas da GRU
    num_classes: quantidade de gestos dinâmicos treinados
    """

    def __init__(self, input_size=63, hidden_size=64, num_layers=1, num_classes=10):
        super().__init__()
        self.gru = nn.GRU(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )
        self.dropout = nn.Dropout(0.2)
        self.fc      = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        # x: (batch, seq_len, input_size)
        out, _ = self.gru(x)
        out    = out[:, -1, :]      # usa apenas o último passo temporal
        out    = self.dropout(out)
        out    = self.fc(out)
        return out                  # logits — aplique softmax fora se precisar de probabilidades
