#!/usr/bin/env python3
"""
gesture_control.py
------------------
Processo principal do sistema de controle por gestos.
Roda em segundo plano (sem janela), consome o mínimo de CPU possível
e se comunica com o tray_icon.py via arquivos de sinalização em /tmp.

Sinalização:
  /tmp/gesture-control.pid   — PID do processo (criado ao iniciar)
  /tmp/gesture-control.pause — se existir, o loop entra em modo pausa
  /tmp/gesture-control.quit  — se existir, o processo encerra limpo
"""

import cv2
import mediapipe as mp
import time
import logging
import signal
import sys
import json
import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE     = Path(__file__).parent
CONFIG   = BASE / "gestures" / "custom.json"
LOGFILE  = BASE / "gesture.log"
PIDFILE  = Path("/tmp/gesture-control.pid")
PAUSE    = Path("/tmp/gesture-control.pause")
QUIT     = Path("/tmp/gesture-control.quit")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=str(LOGFILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger()

# ── Carregar mapeamento de ações ──────────────────────────────────────────────
try:
    with open(CONFIG, encoding="utf-8") as f:
        ACTION_MAP = json.load(f)
except FileNotFoundError:
    log.error("custom.json não encontrado em %s", CONFIG)
    sys.exit(1)
except json.JSONDecodeError as ex:
    log.error("Erro de sintaxe no custom.json: %s", ex)
    sys.exit(1)

# ── Salvar PID ────────────────────────────────────────────────────────────────
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

# ── Executar ação via evdev (sem ydotool, sem daemon) ─────────────────────────
from gestures import keyboard

def run_action(cmd: list):
    keyboard.dispatch(cmd)

# ── Importar módulos de gestos ────────────────────────────────────────────────
from gestures import static, dynamic

# ── Configuração MediaPipe ────────────────────────────────────────────────────
mp_hands   = mp.solutions.hands
CONFIDENCE = 0.75

# ── Configurações de CPU ──────────────────────────────────────────────────────
SKIP_FRAMES  = 2
TARGET_FPS   = 15
FRAME_DELAY  = 1.0 / TARGET_FPS
COOLDOWN     = 1.2
PROC_WIDTH   = 320
PROC_HEIGHT  = 240

log.info("Iniciado (PID %s).", os.getpid())

cap         = cv2.VideoCapture(0)
last_action = 0.0
frame_count = 0

if not cap.isOpened():
    log.error("Câmera não encontrada. Verifique /dev/video*")
    PIDFILE.unlink(missing_ok=True)
    sys.exit(1)

with mp_hands.Hands(
    static_image_mode        = False,
    max_num_hands            = 2,
    model_complexity         = 0,
    min_detection_confidence = CONFIDENCE,
    min_tracking_confidence  = CONFIDENCE,
) as hands:

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

        small = cv2.resize(frame, (PROC_WIDTH, PROC_HEIGHT))
        small = cv2.flip(small, 1)
        rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result              = hands.process(rgb)
        rgb.flags.writeable = True

        now = time.monotonic()

        if result.multi_hand_landmarks:
            hands_list = result.multi_hand_landmarks

            if len(hands_list) == 2:
                dynamic.update_two_hands(hands_list[0], hands_list[1])

            hand = hands_list[0]
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
