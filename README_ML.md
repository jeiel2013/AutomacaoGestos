# Reconhecimento de Gestos com Machine Learning

O projeto agora suporta dois modos de reconhecimento, **lado a lado**:

| Modo         | Gestos estáticos          | Gestos dinâmicos       |
|--------------|---------------------------|-------------------------|
| **ML** (preferencial) | Random Forest / MLP (scikit-learn) | GRU (PyTorch) |
| **Fallback** (automático) | Regras de dedo levantado/abaixado | Detectores geométricos (swipe, tilt, círculo...) |

Se você não treinar nenhum modelo, o sistema **continua funcionando normalmente** com o modo fallback — nada quebra. Assim que você treinar um modelo, ele passa a ser usado automaticamente no próximo início do `gesture_control.py`.

---

## Passo 1 — Instalar dependências de ML

```bat
install.bat
```

Isso já instala `scikit-learn`, `joblib` e `torch` (CPU) além das dependências que já existiam.

---

## Passo 2 — Coletar dados

### Gestos estáticos (uma pose)

```bat
py collect_data.py static PUNHO_FECHADO
```

- Uma janela abre com a câmera
- Pressione **ESPAÇO** para capturar uma amostra da pose atual
- Recomenda-se **60 a 100 amostras** por gesto, variando levemente o ângulo, a distância da câmera e a posição da mão na tela
- Pressione **ESC** para sair
- Repita para cada gesto (troque `PUNHO_FECHADO` pelo nome do gesto)

Os dados vão para `gestures/data/static/NOME_DO_GESTO.csv`.

### Gestos dinâmicos (sequência de movimento)

```bat
py collect_data.py dynamic SWIPE_DIREITA
```

- Pressione **ESPAÇO** para começar a gravar uma sequência de 30 frames
- Faça o movimento completo enquanto a tela mostra "GRAVANDO"
- Recomenda-se **30 a 50 sequências** por gesto, variando um pouco velocidade e amplitude
- Pressione **ESC** para sair

Os dados vão para `gestures/data/dynamic/NOME_DO_GESTO/000.npy, 001.npy, ...`.

**Dica:** use os mesmos nomes de gesto já existentes no `custom.json` (ex: `FECHAR_JANELA`, `SWIPE_DIREITA`, `CIRCLE_CW`) para que as ações continuem mapeadas corretamente. Se quiser criar um gesto novo, lembre de adicioná-lo também no `custom.json` depois.

---

## Passo 3 — Treinar os modelos

```bat
py train_static.py
py train_dynamic.py
```

Cada script imprime um relatório de acurácia. Se a acurácia estiver baixa (~<80%), geralmente significa que:
- Faltam amostras (colete mais)
- Os gestos são parecidos demais entre si (revise quais features os diferenciam)
- Há variação excessiva entre suas próprias execuções do mesmo gesto (tente ser mais consistente)

Os modelos treinados são salvos em `gestures/models/`:
```
gestures/models/
├── static_model.joblib
├── static_labels.joblib
├── dynamic_gru.pt
└── dynamic_labels.json
```

---

## Passo 4 — Usar

Basta reiniciar o `gesture_control.py` (ou pelo menu **Reiniciar daemon** no ícone da bandeja). Se os arquivos de modelo existirem, o log vai mostrar:

```
Modelo ML de gestos estáticos carregado (static_model.joblib).
Modelo GRU de gestos dinâmicos carregado (N classes).
```

Se não existirem, mostra:

```
Nenhum modelo estático treinado encontrado — usando regras fixas.
Nenhum modelo dinâmico (GRU) treinado — usando detectores geométricos.
```

---

## Ajustando a confiança mínima

Se o modelo estiver reconhecendo gestos com muita ou pouca facilidade, ajuste:

```python
# gestures/static.py
MIN_CONFIDENCE = 0.65   # aumente para exigir mais certeza

# gestures/dynamic.py
MIN_CONFIDENCE = 0.70
```

---

## Re-treinar depois de adicionar mais dados

Você pode rodar `collect_data.py` várias vezes para o mesmo gesto — as amostras se acumulam (estático) ou continuam a numeração (dinâmico). Depois é só rodar `train_static.py` / `train_dynamic.py` de novo para gerar um modelo atualizado.

---

## Arquitetura das features (por que não usar coordenadas cruas)

**Estático** (`gestures/features.py::extract_static_features`) — 23 números:
- 5 ângulos de flexão (um por dedo, MCP→PIP→TIP)
- 10 distâncias normalizadas entre pares de pontas de dedos
- 5 distâncias normalizadas ponta→pulso (abertura de cada dedo)
- 1 abertura geral da mão (média das anteriores)
- 2 componentes de orientação da palma (seno/cosseno)

**Dinâmico** (`gestures/features.py::extract_frame_vector`) — 63 números:
- Os 21 landmarks normalizados (translação pelo pulso + escala pelo tamanho da mão), achatados em sequência, alimentando a GRU frame a frame

Essa normalização é o que torna o reconhecimento robusto a mudanças de posição, distância da câmera e pequenas variações de ângulo — ao contrário de comparar coordenadas `(x, y, z)` cruas.
