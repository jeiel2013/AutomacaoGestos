# Gesture Control

Controle o Pop!_OS com gestos das mãos via webcam. Roda completamente em
segundo plano, sem janela, com ícone na bandeja do sistema.

---

## Estrutura do projeto

```
gesture-control/
│
├── gesture_control.py       # Daemon principal — câmera, MediaPipe, loop de detecção
├── tray_icon.py             # Ícone na bandeja — iniciar, pausar, retomar, sair
├── debug_landmarks.py       # Ferramenta para descobrir vetores de gestos novos
├── install.sh               # Instalação automática de dependências
│
├── gestures/
│   ├── __init__.py          # Exporta as funções dos módulos para uso externo
│   ├── static.py            # Gestos por posição dos dedos (num único frame)
│   ├── dynamic.py           # Gestos por trajetória/movimento (buffer de frames)
│   └── custom.json          # Mapeamento gesto → comando (edite aqui!)
│
└── gesture.log              # Log gerado automaticamente em tempo de execução
```

---

## Instalação

```bash
# Clone ou copie a pasta para o seu home
cd ~/gesture-control

# Execute o instalador (só precisa rodar uma vez)
bash install.sh

# OBRIGATÓRIO: faça logout e login para entrar no grupo 'input'
# Sem isso o ydotool não funciona no Wayland
```

---

## Como usar

### Iniciar

Clique duas vezes no ícone **Gesture Control** no launcher de aplicativos,
ou execute diretamente:

```bash
python3 ~/gesture-control/tray_icon.py
```

O ícone aparece na bandeja:

| Cor    | Significado                        |
|--------|------------------------------------|
| Verde  | Reconhecimento ativo               |
| Cinza  | Pausado (clique para retomar)      |
| Laranja| Daemon com erro (tente reiniciar)  |

### Menu da bandeja

| Opção            | Ação                                        |
|------------------|---------------------------------------------|
| Pausar / Retomar | Suspende ou retoma o reconhecimento         |
| Ver log          | Abre gesture.log no editor de texto         |
| Editar gestos    | Abre custom.json para configurar ações      |
| Reiniciar daemon | Para e reinicia o processo de detecção      |
| Sair             | Encerra tudo                                |

---

## Gestos disponíveis

### Estáticos (posição dos dedos)

> Vetor: `[polegar, indicador, médio, anelar, mínimo]` — 1=aberto, 0=fechado

| Gesto              | Vetor           | Ação padrão          |
|--------------------|-----------------|----------------------|
| Punho fechado      | `[0,0,0,0,0]`  | Fechar janela        |
| Só indicador       | `[0,1,0,0,0]`  | Scroll cima          |
| Três dedos baixos  | `[0,0,1,1,1]`  | Scroll baixo         |
| V / paz            | `[0,1,1,0,0]`  | Selecionar tudo      |
| Mão aberta         | `[1,1,1,1,1]`  | Deletar              |
| Joinha             | `[1,0,0,0,0]`  | Confirmar (Enter)    |
| Mindinho           | `[0,0,0,0,1]`  | Voltar               |
| Rock / chifres     | `[0,1,0,0,1]`  | Trocar janela        |
| I love you         | `[1,1,0,0,1]`  | Captura de tela      |
| Hang loose         | `[1,0,0,0,1]`  | Workspace direita    |
| Polegar+2 dedos    | `[1,1,1,0,0]`  | Nova aba             |
| Três do meio       | `[0,1,1,1,0]`  | Fechar aba           |
| Quatro sem polegar | `[0,1,1,1,1]`  | Maximizar            |
| Quatro sem mínimo  | `[1,1,1,1,0]`  | Minimizar            |
| Pistola            | `[1,1,0,0,0]`  | Desfazer             |
| Só dedo médio      | `[0,0,1,0,0]`  | Refazer              |

### Dinâmicos (movimento)

| Gesto              | Movimento                         | Ação padrão              |
|--------------------|-----------------------------------|--------------------------|
| Swipe direita      | Mão move para direita (lento)     | Navegar → frente         |
| Swipe esquerda     | Mão move para esquerda (lento)    | Navegar → voltar         |
| Swipe cima         | Mão move para cima (lento)        | Workspace cima           |
| Swipe baixo        | Mão move para baixo (lento)       | Workspace baixo          |
| Swipe rápido →     | Movimento brusco para direita     | Próxima aba              |
| Swipe rápido ←     | Movimento brusco para esquerda    | Aba anterior             |
| Swipe rápido ↑     | Movimento brusco para cima        | Maximizar janela         |
| Swipe rápido ↓     | Movimento brusco para baixo       | Restaurar janela         |
| Shake              | Balançar a mão horizontalmente    | Desfazer                 |
| Círculo horário    | Movimento circular clockwise      | Refazer                  |
| Círculo anti-hor.  | Movimento circular anti-clockwise | Desfazer                 |
| Figura de 8        | Movimento em 8 / infinito         | Abrir Activities (Super) |
| Wave W             | Sobe-desce-sobe (forma de W)      | Abrir gerenciador        |
| Zoom in            | Duas mãos se afastando            | Ctrl++                   |
| Zoom out           | Duas mãos se aproximando          | Ctrl+-                   |
| Push frente        | Mão avança em direção à câmera    | Enter                    |
| Pull atrás         | Mão recua da câmera               | Escape                   |
| Tilt direita       | Mão inclina para direita          | Workspace direita        |
| Tilt esquerda      | Mão inclina para esquerda         | Workspace esquerda       |

---

## Configurar ações personalizadas

Edite `gestures/custom.json`. Não é necessário mexer em Python.

```json
{
  "static": {
    "FECHAR_JANELA": ["ydotool", "key", "alt+F4"]
  },
  "dynamic": {
    "SWIPE_DIREITA": ["ydotool", "key", "alt+Right"],
    "WAVE_W":        ["nautilus"]
  }
}
```

Qualquer comando de terminal funciona como valor do array.

---

## Adicionar um gesto estático novo

1. Descubra o vetor do gesto com a ferramenta de debug:

```bash
python3 debug_landmarks.py
```

2. Adicione o vetor em `gestures/static.py`:

```python
TABLE[(1, 0, 1, 0, 0)] = "MEU_GESTO"
```

3. Adicione a ação em `gestures/custom.json`:

```json
"static": {
  "MEU_GESTO": ["ydotool", "key", "ctrl+shift+t"]
}
```

---

## Adicionar um gesto dinâmico novo

1. Escreva a função de detecção em `gestures/dynamic.py`:

```python
def _detect_meu_gesto():
    if len(_palm) < HISTORY_SIZE:
        return None
    # analise _palm, _wrist, _tip conforme necessário
    # retorne o nome do gesto ou None
    return "MEU_GESTO_DIN" if condicao else None
```

2. Registre em `classify()` na ordem de prioridade desejada:

```python
def classify():
    return (
        _detect_speed_swipe()   or
        _detect_meu_gesto()     or   # <- aqui
        _detect_zoom()          or
        # ...
    )
```

3. Adicione a ação em `gestures/custom.json`:

```json
"dynamic": {
  "MEU_GESTO_DIN": ["ydotool", "key", "super+e"]
}
```

---

## Ajustar sensibilidade

Edite os thresholds no topo de `gestures/dynamic.py`:

```python
MIN_SWIPE_DIST  = 0.18   # distância mínima para swipe (maior = menos sensível)
MIN_SHAKE_FLIPS = 3      # inversões para shake (maior = precisa agitar mais)
MIN_CIRCLE_DEG  = 280    # graus para círculo (menor = aceita círculos parciais)
MIN_ZOOM_DELTA  = 0.12   # variação para zoom entre duas mãos
MIN_Z_DELTA     = 0.08   # variação no eixo Z para push/pull
MIN_TILT_DEG    = 25     # graus de inclinação para tilt
```

Para reduzir falsos positivos: aumente os valores.
Para gestos mais fáceis de ativar: diminua os valores.

---

## Reduzir uso de CPU

Edite em `gesture_control.py`:

```python
SKIP_FRAMES = 2    # processa 1 em cada N frames (aumente para economizar mais)
TARGET_FPS  = 15   # iterações por segundo do loop (diminua para economizar mais)
PROC_WIDTH  = 320  # resolução do frame enviado ao MediaPipe
PROC_HEIGHT = 240
```

Combinação recomendada para máquinas mais lentas:

```python
SKIP_FRAMES = 3
TARGET_FPS  = 10
PROC_WIDTH  = 240
PROC_HEIGHT = 180
```

---

## Verificar se está funcionando

```bash
# Ver se o daemon está rodando
pgrep -a python3 | grep gesture_control

# Acompanhar log em tempo real
tail -f ~/gesture-control/gesture.log

# Verificar uso de CPU/RAM
top -p $(pgrep -f gesture_control)

# Testar se ydotool está OK
ydotool key ctrl+t
```

---

## Solução de problemas

**ydotool não funciona:**
```bash
# Verificar se o daemon está rodando
sudo systemctl status ydotoold

# Verificar se está no grupo input (precisa de logout/login após install.sh)
groups | grep input
```

**Câmera não abre:**
```bash
# Listar câmeras disponíveis
v4l2-ctl --list-devices

# Testar câmera
python3 -c "import cv2; c=cv2.VideoCapture(0); print('OK' if c.isOpened() else 'FALHOU')"
```

**Gestos não detectados / muitos falsos positivos:**
- Ajuste os thresholds em `dynamic.py` (veja seção acima)
- Aumente `COOLDOWN` em `gesture_control.py` para espaçar mais as detecções
- Use `debug_landmarks.py` para ver os valores em tempo real

**Sessão Wayland vs X11:**
```bash
# Ver qual sessão está usando
echo $XDG_SESSION_TYPE

# Se for X11, ydotool não é necessário — troque por xdotool nos comandos
```
