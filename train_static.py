#!/usr/bin/env python3
"""
train_static.py
----------------
Treina o classificador de gestos ESTÁTICOS (Random Forest, ou MLP se
preferir) a partir dos dados coletados com collect_data.py.

Uso:
  python train_static.py
  (lê todos os CSVs em gestures/data/static/*.csv)

Salva:
  gestures/models/static_model.joblib
  gestures/models/static_labels.joblib

Para trocar o algoritmo, edite a constante CLASSIFIER abaixo.
"""

from pathlib import Path
import numpy as np
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

BASE      = Path(__file__).parent
DATA_DIR  = BASE / "gestures" / "data" / "static"
MODEL_DIR = BASE / "gestures" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Troque para "mlp" se preferir uma rede neural pequena em vez de Random Forest
CLASSIFIER = "random_forest"   # ou "mlp"


def load_data():
    X, y = [], []
    csvs = list(DATA_DIR.glob("*.csv"))
    if not csvs:
        raise SystemExit(
            f"Nenhum CSV encontrado em {DATA_DIR}.\n"
            "Colete dados primeiro: python collect_data.py static NOME_DO_GESTO"
        )
    for csv_path in csvs:
        data = np.loadtxt(csv_path, delimiter=",", dtype=str)
        if data.ndim == 1:
            data = data.reshape(1, -1)
        feats  = data[:, :-1].astype(np.float32)
        labels = data[:, -1]
        X.append(feats)
        y.extend(labels)
        print(f"  {csv_path.name}: {len(labels)} amostras")
    return np.vstack(X), np.array(y)


def main():
    print("=== Treinamento — gestos estáticos ===\n")
    X, y = load_data()
    print(f"\nTotal: {len(y)} amostras, {len(set(y))} classes\n")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    if CLASSIFIER == "mlp":
        model = MLPClassifier(
            hidden_layer_sizes=(32, 16),
            max_iter=1000,
            random_state=42,
        )
    else:
        model = RandomForestClassifier(
            n_estimators=150,
            max_depth=12,
            random_state=42,
        )

    print(f"Treinando {CLASSIFIER}...")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n=== Relatório de avaliação ===")
    print(classification_report(y_test, y_pred))

    # model.classes_ garante a mesma ordem usada internamente pelo
    # predict_proba(), essencial para bater com o índice retornado
    labels = list(model.classes_)

    joblib.dump(model,  MODEL_DIR / "static_model.joblib")
    joblib.dump(labels, MODEL_DIR / "static_labels.joblib")

    print(f"\nModelo salvo em {MODEL_DIR / 'static_model.joblib'}")
    print("Reinicie o gesture_control.py para usar o novo modelo.")


if __name__ == "__main__":
    main()
