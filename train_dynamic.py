#!/usr/bin/env python3
"""
train_dynamic.py
------------------
Treina o classificador de gestos DINÂMICOS (GRU, PyTorch) a partir das
sequências coletadas com collect_data.py.

Uso:
  python train_dynamic.py
  (lê gestures/data/dynamic/<gesto>/*.npy)

Salva:
  gestures/models/dynamic_gru.pt
  gestures/models/dynamic_labels.json
"""

import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split

from gestures.gru_model import GestureGRU
from gestures.features import DYNAMIC_FEATURE_SIZE

BASE      = Path(__file__).parent
DATA_DIR  = BASE / "gestures" / "data" / "dynamic"
MODEL_DIR = BASE / "gestures" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

SEQ_LEN     = 30
HIDDEN_SIZE = 64
NUM_LAYERS  = 1
EPOCHS      = 60
BATCH_SIZE  = 16
LR          = 1e-3


class GestureSequenceDataset(Dataset):
    def __init__(self, samples, labels):
        self.samples = samples
        self.labels  = labels

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        x = torch.tensor(self.samples[idx], dtype=torch.float32)
        y = torch.tensor(self.labels[idx],  dtype=torch.long)
        return x, y


def load_data():
    label_dirs = sorted([d for d in DATA_DIR.iterdir() if d.is_dir()])
    if not label_dirs:
        raise SystemExit(
            f"Nenhuma pasta de gesto encontrada em {DATA_DIR}.\n"
            "Colete dados primeiro: python collect_data.py dynamic NOME_DO_GESTO"
        )

    labels_list = [d.name for d in label_dirs]
    samples, targets = [], []

    for idx, d in enumerate(label_dirs):
        files = list(d.glob("*.npy"))
        print(f"  {d.name}: {len(files)} sequências")
        for f in files:
            arr = np.load(f)
            if arr.shape != (SEQ_LEN, DYNAMIC_FEATURE_SIZE):
                print(f"    aviso: {f.name} tem shape {arr.shape}, esperado "
                      f"({SEQ_LEN}, {DYNAMIC_FEATURE_SIZE}) — ignorado")
                continue
            samples.append(arr)
            targets.append(idx)

    return np.array(samples, dtype=np.float32), np.array(targets, dtype=np.int64), labels_list


def main():
    print("=== Treinamento — gestos dinâmicos (GRU) ===\n")
    X, y, labels_list = load_data()
    print(f"\nTotal: {len(y)} sequências, {len(labels_list)} classes: {labels_list}\n")

    dataset = GestureSequenceDataset(X, y)
    n_val   = max(1, int(len(dataset) * 0.2))
    n_train = len(dataset) - n_val
    train_ds, val_ds = random_split(dataset, [n_train, n_val])

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE)

    model = GestureGRU(
        input_size=DYNAMIC_FEATURE_SIZE,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        num_classes=len(labels_list),
    )

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    print("Treinando GRU...")
    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            logits = model(xb)
            loss   = criterion(logits, yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        if epoch % 10 == 0 or epoch == EPOCHS:
            model.eval()
            correct, total = 0, 0
            with torch.no_grad():
                for xb, yb in val_loader:
                    logits = model(xb)
                    preds  = logits.argmax(dim=1)
                    correct += (preds == yb).sum().item()
                    total   += yb.size(0)
            acc = correct / total if total else 0.0
            print(f"  Época {epoch:3d}/{EPOCHS} — loss: {total_loss:.4f} — acurácia val: {acc:.2%}")

    torch.save(model.state_dict(), MODEL_DIR / "dynamic_gru.pt")
    with open(MODEL_DIR / "dynamic_labels.json", "w", encoding="utf-8") as f:
        json.dump(labels_list, f, ensure_ascii=False, indent=2)

    print(f"\nModelo salvo em {MODEL_DIR / 'dynamic_gru.pt'}")
    print("Reinicie o gesture_control.py para usar o novo modelo.")


if __name__ == "__main__":
    main()
