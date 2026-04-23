#!/usr/bin/env python3
"""
gesture_control.py
------------------
Processo principal — usa a nova API mediapipe.tasks (0.10.13+).
"""

import cv2
import time
import logging
import signal
import sys
import json
import os
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import HandLandmarkerOptions, HandLandmarker

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE      = Path(__file__).parent
CONFIG    = BASE / "gestures" / "custom.json"
LOGFILE   = BASE / "gesture.log"
MODEL     = BASE / "hand_landmarker.task"
PIDFILE   = Path("/tmp/gesture-control.pid")
PAUSE     = Path("/tmp/gesture-control.pause")
QUIT      = Path("/tmp/gesture-control.quit")

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
    log.error("Execute: wget -q https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task -O hand_landmarker.task")
    sys.exit(1)

try:
    with open(CONFIG, encoding="utf-8") as f:
        ACTION_MAP = json.load(f)
except FileNotFoundError:
    log.error("custom.json não encontrado em %s", CONFIG)
    sys.exit(1)
except json.JSONDecodeError as ex:
    log.error("Erro de sintaxe no custom.json: %s", ex)
    sys.exit(1)

# ── PID ───────────────────────────────────────────────────────────────────────
PIDFILE.write_text(str(os.getpid()))
QUIT.unlink(missing_ok=True)

# ── Encerramento gracioso ─────────────────────────────────────────────────────
cap = None

def shutdown(sig=None, frame=None):
    log.info("Encerrando (sinal %s).", sig)
    from gestures import keyboard
    keyboard.close()
    if cap is not None:
        cap.release()
    PIDFILE.unlink(missing_ok=True)
    QUIT.unlink(missing_ok=True)
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT,  shutdown)

# ── Módulos de gestos ─────────────────────────────────────────────────────────
from gestures import static, dynamic, keyboard

def run_action(cmd: list):
    keyboard.dispatch(cmd)

# ── Configurações de CPU ──────────────────────────────────────────────────────
SKIP_FRAMES = 2
TARGET_FPS  = 15
FRAME_DELAY = 1.0 / TARGET_FPS
COOLDOWN    = 1.2
PROC_WIDTH  = 320
PROC_HEIGHT = 240

# ── Converter resultado da nova API para formato compatível ───────────────────
class _LandmarkWrapper:
    """Adapta o NormalizedLandmark da nova API para o formato antigo (lm[i].x/y/z)."""
    def __init__(self, landmarks):
        self.landmark = landmarks

def _build_wrapper(hand_landmarks_list):
    """Recebe lista de NormalizedLandmark e retorna wrapper compatível."""
    return _LandmarkWrapper(hand_landmarks_list)

# ── Inicializar HandLandmarker ────────────────────────────────────────────────
options = HandLandmarkerOptions(
    base_options=mp_tasks.BaseOptions(model_asset_path=str(MODEL)),
    num_hands=2,
    min_hand_detection_confidence=0.7,
    min_hand_presence_confidence=0.7,
    min_tracking_confidence=0.7,
    running_mode=mp_vision.RunningMode.IMAGE,
)

log.info("Iniciado (PID %s).", os.getpid())

cap         = cv2.VideoCapture(0)
last_action = 0.0
frame_count = 0

if not cap.isOpened():
    log.error("Câmera não encontrada. Verifique /dev/video*")
    PIDFILE.unlink(missing_ok=True)
    sys.exit(1)

with HandLandmarker.create_from_options(options) as landmarker:
    while True:
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
            continue

        # Pré-processar
        small = cv2.resize(frame, (PROC_WIDTH, PROC_HEIGHT))
        small = cv2.flip(small, 1)
        rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        # Detectar com nova API
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result   = landmarker.detect(mp_image)

        now = time.monotonic()

        if result.hand_landmarks:
            hands_list = result.hand_landmarks  # lista de listas de NormalizedLandmark

            # Alimentar zoom se duas mãos
            if len(hands_list) == 2:
                dynamic.update_two_hands(
                    _build_wrapper(hands_list[0]),
                    _build_wrapper(hands_list[1]),
                )

            hand = _build_wrapper(hands_list[0])
            dynamic.update(hand)

            if now - last_action > COOLDOWN:
                dyn = dynamic.classify()
                if dyn:
                    cmd = ACTION_MAP["dynamic"].get(dyn)
                    if cmd:
                        run_action(cmd)
                        log.info("Dinâmico: %-25s → %s", dyn, cmd)
                        last_action = now
                        dynamic.reset()
                else:
                    sta = static.classify(hand)
                    if sta:
                        cmd = ACTION_MAP["static"].get(sta)
                        if cmd:
                            run_action(cmd)
                            log.info("Estático:  %-25s → %s", sta, cmd)
                            last_action = now
                            dynamic.reset()

        elapsed = time.monotonic() - loop_start
        sleep_t = FRAME_DELAY - elapsed
        if sleep_t > 0:
            time.sleep(sleep_t)
