#!/usr/bin/env python3
"""
gesture_control.py
------------------
Daemon principal — detecta gestos via câmera e executa ações no Windows.
Usa mediapipe.tasks (0.10.13+) e pyautogui para envio de teclas.
Comunica com tray_icon.py via arquivo IPC em %TEMP%.
"""

import cv2
import time
import logging
import sys
import json
import os
import threading
import tempfile
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import HandLandmarkerOptions, HandLandmarker

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE    = Path(__file__).parent
CONFIG  = BASE / "gestures" / "custom.json"
LOGFILE = BASE / "gesture.log"
MODEL   = BASE / "hand_landmarker.task"

# Arquivos IPC em %TEMP% (equivalente ao /tmp do Linux)
_TEMP          = Path(tempfile.gettempdir())
PIDFILE        = _TEMP / "gesture-control.pid"
PAUSE          = _TEMP / "gesture-control.pause"
QUIT           = _TEMP / "gesture-control.quit"
GESTURE_SIGNAL = _TEMP / "gesture-control.gesture"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=str(LOGFILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger()

# ── Verificações iniciais ─────────────────────────────────────────────────────
if not MODEL.exists():
    log.error("Modelo não encontrado: %s", MODEL)
    log.error("Baixe em: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task")
    sys.exit(1)

try:
    with open(CONFIG, encoding="utf-8") as f:
        ACTION_MAP = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as ex:
    log.error("Erro ao carregar custom.json: %s", ex)
    sys.exit(1)

# ── PID ───────────────────────────────────────────────────────────────────────
PIDFILE.write_text(str(os.getpid()))
QUIT.unlink(missing_ok=True)

# ── Módulos de gestos ─────────────────────────────────────────────────────────
from gestures import static, dynamic, keyboard
import confirm_dialog

# ── Emojis dos gestos (IPC com o tray) ───────────────────────────────────────
GESTURE_EMOJI = {
    "FECHAR_JANELA":"🪟","SCROLL_CIMA":"⬆️","SCROLL_BAIXO":"⬇️",
    "SELECIONAR_TUDO":"📋","DELETAR":"🗑️","CONFIRMAR":"👍","VOLTAR":"↩️",
    "TROCAR_JANELA":"🔄","CAPTURA_TELA":"📸","WORKSPACE_DIR":"➡️",
    "NOVA_ABA":"➕","FECHAR_ABA":"✖️","MAXIMIZAR":"⬛","MINIMIZAR":"▬",
    "DESFAZER":"↪️","REFAZER":"↩️","SWIPE_DIREITA":"👉","SWIPE_ESQUERDA":"👈",
    "SWIPE_CIMA":"👆","SWIPE_BAIXO":"👇","SWIPE_RAPIDO_DIREITA":"⚡",
    "SWIPE_RAPIDO_ESQUERDA":"⚡","SWIPE_RAPIDO_CIMA":"⚡","SWIPE_RAPIDO_BAIXO":"⚡",
    "SHAKE":"🤝","CIRCLE_CW":"🔃","CIRCLE_CCW":"🔄","FIGURE_EIGHT":"♾️",
    "WAVE_W":"〰️","ZOOM_IN":"🔍","ZOOM_OUT":"🔎","PUSH_FRENTE":"🫸",
    "PULL_ATRAS":"🫷","TILT_DIREITA":"↗️","TILT_ESQUERDA":"↖️",
    "TOGGLE_DYNAMIC":"🔀",
}

def _signal_tray(gesture_name: str):
    """Escreve emoji no arquivo IPC — tray_icon.py lê e atualiza o ícone."""
    emoji = GESTURE_EMOJI.get(gesture_name, "✋")
    try:
        GESTURE_SIGNAL.write_text(emoji, encoding="utf-8")
    except Exception:
        pass

# ── Encerramento gracioso ─────────────────────────────────────────────────────
cap = None
_running = True

def shutdown():
    global _running
    log.info("Encerrando.")
    _running = False
    keyboard.close()
    if cap is not None:
        cap.release()
    PIDFILE.unlink(missing_ok=True)
    QUIT.unlink(missing_ok=True)
    sys.exit(0)

# ── Executar ação ─────────────────────────────────────────────────────────────
def run_action(cmd: list):
    keyboard.dispatch(cmd)

# ── Modo de gestos dinâmicos (trava mestra) ──────────────────────────────────
# Por padrão os gestos DINÂMICOS ficam DESATIVADOS. Só os ESTÁTICOS funcionam.
# Para ativar: faça "V" com AS DUAS MÃOS ao mesmo tempo e confirme com Joinha
# (ou cancele com Punho). O mesmo gesto novamente desativa.
# Isso evita que tremores da mão durante um gesto estático disparem um
# gesto dinâmico por engano — dinâmico só roda quando você pediu explicitamente.
dynamic_mode_enabled = False
TOGGLE_COOLDOWN      = 2.0   # segundos mínimos entre duas tentativas de alternância

def _is_double_v(hands_list) -> bool:
    """Retorna True se AS DUAS mãos detectadas estão fazendo o sinal de V."""
    if len(hands_list) != 2:
        return False
    try:
        f1 = static.fingers_up(hands_list[0])
        f2 = static.fingers_up(hands_list[1])
    except Exception:
        return False
    V = [0, 1, 1, 0, 0]
    return f1 == V and f2 == V

def _request_toggle_dynamic():
    """Pede confirmação (Joinha/Punho) para ligar ou desligar o modo dinâmico."""
    global dynamic_mode_enabled

    _signal_tray("TOGGLE_DYNAMIC")
    novo_estado = not dynamic_mode_enabled
    acao        = "ATIVAR" if novo_estado else "DESATIVAR"
    log.info("Aguardando confirmação para %s gestos dinâmicos", acao)

    def on_result(confirmed: bool):
        global dynamic_mode_enabled
        if confirmed:
            dynamic_mode_enabled = novo_estado
            if dynamic_mode_enabled:
                dynamic.reset()   # começa o buffer limpo ao ativar
            log.info("Gestos dinâmicos: %s",
                     "ATIVADOS" if dynamic_mode_enabled else "DESATIVADOS")
        else:
            log.info("Alternância cancelada — gestos dinâmicos continuam %s",
                     "ATIVADOS" if dynamic_mode_enabled else "DESATIVADOS")

    threading.Thread(
        target=confirm_dialog.show,
        args=("TOGGLE_DYNAMIC", on_result),
        daemon=True,
    ).start()

# ── Processar gesto ───────────────────────────────────────────────────────────
def handle_gesture(gesture_name: str, gesture_type: str) -> bool:
    """Processa gesto — com confirmação se necessário."""

    # Diálogo pendente: Joinha confirma, punho cancela
    if confirm_dialog.has_pending():
        if gesture_name == "CONFIRMAR":
            confirm_dialog.confirm_current()
            log.info("Confirmação: ACEITA via Joinha")
            return True
        elif gesture_name == "FECHAR_JANELA":
            confirm_dialog.cancel_current()
            log.info("Confirmação: CANCELADA via Punho")
            return True
        return False

    cmd = ACTION_MAP[gesture_type].get(gesture_name)
    if not cmd:
        return False

    # Sinaliza tray
    _signal_tray(gesture_name)

    # Gesto destrutivo → confirmação
    if confirm_dialog.needs_confirmation(gesture_name):
        log.info("Aguardando confirmação: %s", gesture_name)

        def on_result(confirmed: bool):
            if confirmed:
                run_action(cmd)
                log.info("Executado após confirmação: %s → %s", gesture_name, cmd)
            else:
                log.info("Cancelado: %s", gesture_name)

        threading.Thread(
            target=confirm_dialog.show,
            args=(gesture_name, on_result),
            daemon=True,
        ).start()
        return True

    # Gesto normal → executar direto
    threading.Thread(target=run_action, args=(cmd,), daemon=True).start()
    log.info("%s: %-25s → %s",
             "Dinâmico" if gesture_type == "dynamic" else "Estático",
             gesture_name, cmd)
    return True

# ── Wrapper de landmarks ──────────────────────────────────────────────────────
class _LandmarkWrapper:
    def __init__(self, landmarks):
        self.landmark = landmarks

def _wrap(lms):
    return _LandmarkWrapper(lms)

# ── Configurações de CPU ──────────────────────────────────────────────────────
SKIP_FRAMES = 2
TARGET_FPS  = 15
FRAME_DELAY = 1.0 / TARGET_FPS
COOLDOWN    = 1.2
PROC_WIDTH  = 320
PROC_HEIGHT = 240

# ── HandLandmarker ────────────────────────────────────────────────────────────
options = HandLandmarkerOptions(
    base_options=mp_tasks.BaseOptions(model_asset_path=str(MODEL)),
    num_hands=2,
    min_hand_detection_confidence=0.7,
    min_hand_presence_confidence=0.7,
    min_tracking_confidence=0.7,
    running_mode=mp_vision.RunningMode.IMAGE,
)

log.info("Iniciado (PID %s). Gestos dinâmicos: DESATIVADOS — faça duas mãos em V + confirme para ativar.", os.getpid())

cap         = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # CAP_DSHOW = backend Windows
last_action = 0.0
last_toggle = 0.0
frame_count = 0

if not cap.isOpened():
    log.error("Câmera não encontrada. Verifique as permissões no Windows.")
    PIDFILE.unlink(missing_ok=True)
    sys.exit(1)

with HandLandmarker.create_from_options(options) as landmarker:
    while _running:
        loop_start = time.monotonic()

        if QUIT.exists():
            shutdown()

        if PAUSE.exists():
            time.sleep(0.5)
            continue

        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        frame_count += 1
        if frame_count % SKIP_FRAMES != 0:
            elapsed = time.monotonic() - loop_start
            sleep_t = FRAME_DELAY - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)
            continue

        small    = cv2.resize(frame, (PROC_WIDTH, PROC_HEIGHT))
        small    = cv2.flip(small, 1)
        rgb      = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result   = landmarker.detect(mp_image)

        now = time.monotonic()

        if result.hand_landmarks:
            hands_list = result.hand_landmarks
            hand       = _wrap(hands_list[0])

            # 1) Confirmação pendente (Joinha/Punho) tem prioridade máxima —
            #    ignora tudo o mais até o usuário confirmar ou cancelar.
            if confirm_dialog.has_pending():
                if now - last_action > COOLDOWN:
                    sta = static.classify(hand)
                    if sta in ("CONFIRMAR", "FECHAR_JANELA"):
                        if handle_gesture(sta, "static"):
                            last_action = now
                            dynamic.reset()

            # 2) Trava mestra — duas mãos em V liga/desliga o modo dinâmico
            elif (_is_double_v(hands_list)
                  and now - last_toggle > TOGGLE_COOLDOWN):
                _request_toggle_dynamic()
                last_toggle = now

            # 3) Fluxo normal — dinâmico só é avaliado se o modo estiver ativo
            else:
                if dynamic_mode_enabled:
                    if len(hands_list) == 2:
                        dynamic.update_two_hands(
                            _wrap(hands_list[0]),
                            _wrap(hands_list[1]),
                        )
                    dynamic.update(hand)

                if now - last_action > COOLDOWN:
                    dyn = dynamic.classify() if dynamic_mode_enabled else None
                    if dyn:
                        if handle_gesture(dyn, "dynamic"):
                            last_action = now
                            dynamic.reset()
                    else:
                        sta = static.classify(hand)
                        if sta:
                            if handle_gesture(sta, "static"):
                                last_action = now
                                dynamic.reset()

        elapsed = time.monotonic() - loop_start
        sleep_t = FRAME_DELAY - elapsed
        if sleep_t > 0:
            time.sleep(sleep_t)

