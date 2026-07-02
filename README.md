# Gesture Control — Windows 10/11

Controle o Windows com gestos das mãos via webcam.
Roda em segundo plano com ícone na bandeja do sistema.

---

## Estrutura do projeto

```
gesture-control/
│
├── gesture_control.py   # Daemon principal — câmera, MediaPipe, loop de detecção
├── tray_icon.py         # Ícone na bandeja — iniciar, pausar, retomar, sair
├── confirm_dialog.py    # Popup de confirmação para gestos destrutivos (tkinter)
├── debug_landmarks.py   # Ferramenta para descobrir vetores de gestos novos
├── install.bat          # Instalação automática de dependências
├── hand_landmarker.task # Modelo MediaPipe (baixado pelo install.bat)
│
├── gestures/
│   ├── __init__.py
│   ├── static.py        # Gestos por posição dos dedos
│   ├── dynamic.py       # Gestos por trajetória/movimento
│   ├── keyboard.py      # Envio de teclas via pyautogui (Windows)
│   └── custom.json      # Mapeamento gesto → ação (edite aqui!)
│
└── gesture.log          # Log gerado automaticamente
```

---

## Instalação

**Requisitos:** Python 3.10+ com "Add Python to PATH" marcado na instalação.

```bat
:: Execute como Administrador (ou clique duas vezes)
install.bat
```

O script instala as dependências, baixa o modelo MediaPipe e cria um atalho na Área de Trabalho.

**Dependências Python instaladas:**
- `opencv-python` — captura da câmera
- `mediapipe` — detecção de landmarks da mão
- `pyautogui` — envio de teclas/mouse no Windows
- `pystray` — ícone na bandeja do sistema
- `pillow` — geração dos ícones PNG

---

## Como usar

### Iniciar

Clique duas vezes em **Gesture Control** na Área de Trabalho, ou:

```bat
pythonw tray_icon.py
```

O ícone verde aparece na bandeja (canto inferior direito, perto do relógio).

### Menu da bandeja

| Opção            | Ação                                        |
|------------------|---------------------------------------------|
| Pausar / Retomar | Suspende ou retoma o reconhecimento         |
| Ver log          | Abre gesture.log no Bloco de Notas          |
| Editar gestos    | Abre custom.json para configurar ações      |
| Reiniciar daemon | Para e reinicia o processo de detecção      |
| Sair             | Encerra tudo                                |

---

## Gestos disponíveis

### Estáticos (posição dos dedos)

> Vetor: `[polegar, indicador, médio, anelar, mínimo]` — 1=aberto, 0=fechado

| Gesto              | Vetor           | Ação padrão          |
|--------------------|-----------------|----------------------|
| Punho fechado      | `[0,0,0,0,0]`  | Fechar janela (Alt+F4)|
| Só indicador       | `[0,1,0,0,0]`  | Scroll cima          |
| Três dedos baixos  | `[0,0,1,1,1]`  | Scroll baixo         |
| V / paz            | `[0,1,1,0,0]`  | Selecionar tudo      |
| Mão aberta         | `[1,1,1,1,1]`  | Delete               |
| Joinha             | `[1,0,0,0,0]`  | Enter                |
| Mindinho           | `[0,0,0,0,1]`  | Voltar               |
| Rock / chifres     | `[0,1,0,0,1]`  | Alt+Tab              |
| I love you         | `[1,1,0,0,1]`  | Win+Shift+S          |
| Hang loose         | `[1,0,0,0,1]`  | Workspace →          |
| Três + polegar     | `[1,1,1,0,0]`  | Nova aba (Ctrl+T)    |
| Três do meio       | `[0,1,1,1,0]`  | Fechar aba (Ctrl+W)  |
| Quatro sem polegar | `[0,1,1,1,1]`  | Maximizar (Win+↑)    |
| Quatro sem mínimo  | `[1,1,1,1,0]`  | Minimizar (Win+↓)    |
| Pistola            | `[1,1,0,0,0]`  | Desfazer (Ctrl+Z)    |
| Só dedo médio      | `[0,0,1,0,0]`  | Refazer (Ctrl+Y)     |

### Dinâmicos (movimento)

| Gesto              | Ação padrão                      |
|--------------------|----------------------------------|
| Swipe →            | Navegar → frente (Alt+→)         |
| Swipe ←            | Navegar → voltar (Alt+←)         |
| Swipe ↑            | Workspace cima (Ctrl+Win+↑)      |
| Swipe ↓            | Workspace baixo (Ctrl+Win+↓)     |
| Swipe rápido →     | Próxima aba (Ctrl+Tab)           |
| Swipe rápido ←     | Aba anterior (Ctrl+Shift+Tab)    |
| Swipe rápido ↑     | Maximizar (Win+↑)                |
| Swipe rápido ↓     | Restaurar (Win+↓)                |
| Shake              | Desfazer (Ctrl+Z)                |
| Círculo ↻          | Refazer (Ctrl+Y)                 |
| Círculo ↺          | Desfazer (Ctrl+Z)                |
| Figura 8           | Task View (Win+Tab)              |
| Wave W             | Abrir Explorer                   |
| Zoom in            | Ctrl++                           |
| Zoom out           | Ctrl+-                           |
| Push frente        | Enter                            |
| Pull atrás         | Escape                           |
| Tilt →             | Workspace direita                |
| Tilt ←             | Workspace esquerda               |

---

## Configurar ações personalizadas

Edite `gestures/custom.json` — sem precisar mexer em Python:

```json
{
  "static": {
    "FECHAR_JANELA": ["KEY", "alt+F4"]
  },
  "dynamic": {
    "SWIPE_DIREITA": ["KEY", "alt+right"],
    "WAVE_W":        ["CMD", "explorer"]
  }
}
```

Formatos de ação:
- `["KEY", "ctrl+t"]` — combinação de teclas
- `["SCROLL", "up"]` — scroll (up/down)
- `["CMD", "notepad"]` — executar programa

---

## Confirmação de gestos destrutivos

Os gestos **Fechar Janela, Selecionar Tudo, Deletar, Voltar, Fechar Aba, Desfazer e Refazer** exigem confirmação antes de executar.

Uma janela aparece no canto inferior direito da tela. Para confirmar:
- Faça o gesto **Joinha** 👍 na câmera
- Ou clique em **✅ Confirmar**
- Ou pressione **Enter**

Para cancelar: gesto de **punho fechado**, clique em **❌ Cancelar**, ou aguarde 5 segundos.

---

## Testar gestos (debug)

```bat
python debug_landmarks.py
```

Uma janela abre com a câmera. O vetor dos dedos aparece em tempo real — anote o padrão e adicione em `gestures/static.py` e `gestures/custom.json`.

---

## Solução de problemas

**Câmera não abre:**
- Verifique permissões em Configurações → Privacidade → Câmera
- Certifique-se que nenhum outro app está usando a câmera

**pyautogui não envia teclas:**
- Execute `tray_icon.py` com o Python padrão (não como admin)
- Algumas combinações com `Win` podem precisar de `pygetwindow`

**Ícone não aparece na bandeja:**
- Clique na seta "^" na bandeja para ver ícones ocultos
- Arraste o ícone para a área visível

**Dependências não instalam:**
```bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install opencv-python mediapipe pyautogui pystray pillow
```
