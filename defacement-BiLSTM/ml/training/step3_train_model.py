import json
import math
import os
import random
import time
from pathlib import Path

os.environ.setdefault("TF_DETERMINISTIC_OPS", "1")

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.utils.class_weight import compute_class_weight
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
from tensorflow.keras.layers import Bidirectional, Dense, Embedding, LSTM, SpatialDropout1D
from tensorflow.keras.metrics import AUC, Precision, Recall
from tensorflow.keras.models import Sequential
from tensorflow.keras.optimizers import Adam

ROOT_DIR = Path(__file__).resolve().parents[2]

# --- CONFIG ---
INPUT_X_TRAIN = ROOT_DIR / "ml" / "data" / "processed" / "X_train.npy"
INPUT_Y_TRAIN = ROOT_DIR / "ml" / "data" / "processed" / "y_train.npy"
INPUT_X_VALID = ROOT_DIR / "ml" / "data" / "processed" / "X_valid.npy"
INPUT_Y_VALID = ROOT_DIR / "ml" / "data" / "processed" / "y_valid.npy"
INPUT_X_TEST = ROOT_DIR / "ml" / "data" / "processed" / "X_test.npy"
INPUT_Y_TEST = ROOT_DIR / "ml" / "data" / "processed" / "y_test.npy"

BEST_MODEL_FILE = ROOT_DIR / "ml" / "artifacts" / "bilstm_defacement_model.keras"
HISTORY_PLOT_FILE = ROOT_DIR / "ml" / "artifacts" / "training_history.png"
METRICS_REPORT_FILE = ROOT_DIR / "ml" / "artifacts" / "metrics_report.json"
CALIBRATION_FILE = ROOT_DIR / "ml" / "artifacts" / "calibration.json"
DECISION_FILE = ROOT_DIR / "ml" / "artifacts" / "decision.json"
ROC_PLOT_FILE = ROOT_DIR / "ml" / "artifacts" / "roc_curve.png"
PR_PLOT_FILE = ROOT_DIR / "ml" / "artifacts" / "pr_curve.png"

VOCAB_SIZE = 20000
MAX_LENGTH = 128

EMBEDDING_DIM = 64
LSTM_UNITS = 64

BATCH_SIZE = 64
EPOCHS = 15
SEED = 42
P_MIN = float(os.getenv("P_MIN", "0.80"))
# ----------------


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def temperature_scale(prob, temperature):
    prob = np.clip(prob, 1e-6, 1 - 1e-6)
    logit = np.log(prob / (1 - prob))
    return sigmoid(logit / temperature)


def fit_temperature(probs, y_true):
    temps = np.arange(0.5, 5.01, 0.05)
    best_t = 1.0
    best_nll = float("inf")
    for t in temps:
        calibrated = temperature_scale(probs, t)
        calibrated = np.clip(calibrated, 1e-6, 1 - 1e-6)
        nll = -np.mean(y_true * np.log(calibrated) + (1 - y_true) * np.log(1 - calibrated))
        if nll < best_nll:
            best_nll = nll
            best_t = t
    return best_t, best_nll


def ece_score(probs, y_true, bins=10):
    probs = np.clip(probs, 1e-6, 1 - 1e-6)
    bin_edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for i in range(bins):
        mask = (probs >= bin_edges[i]) & (probs < bin_edges[i + 1])
        if not np.any(mask):
            continue
        bin_conf = np.mean(probs[mask])
        bin_acc = np.mean(y_true[mask])
        ece += np.abs(bin_acc - bin_conf) * (np.sum(mask) / len(probs))
    return float(ece)


def scan_thresholds(probs, y_true):
    thresholds = np.arange(0.05, 0.96, 0.01)
    best_f1 = {"threshold": 0.5, "f1": 0.0}
    best_recall = None
    for t in thresholds:
        preds = (probs >= t).astype(int)
        precision = precision_score(y_true, preds, zero_division=0)
        recall = recall_score(y_true, preds, zero_division=0)
        f1 = f1_score(y_true, preds, zero_division=0)
        if f1 > best_f1["f1"]:
            best_f1 = {"threshold": float(t), "f1": float(f1)}
        if precision >= P_MIN:
            if best_recall is None or recall > best_recall["recall"]:
                best_recall = {"threshold": float(t), "precision": float(precision), "recall": float(recall)}
    return best_f1, best_recall


def evaluate_at_threshold(probs, y_true, threshold):
    preds = (probs >= threshold).astype(int)
    cm = confusion_matrix(y_true, preds, labels=[0, 1])
    f1 = f1_score(y_true, preds, zero_division=0)
    mcc = matthews_corrcoef(y_true, preds)
    precision = precision_score(y_true, preds, zero_division=0)
    recall = recall_score(y_true, preds, zero_division=0)
    return {
        "threshold": float(threshold),
        "confusion_matrix": cm.tolist(),
        "f1": float(f1),
        "mcc": float(mcc),
        "precision": float(precision),
        "recall": float(recall),
    }


class F1Callback(tf.keras.callbacks.Callback):
    def __init__(self, x_val, y_val):
        super().__init__()
        self.x_val = x_val
        self.y_val = y_val
        self.best_f1 = 0.0

    def on_epoch_end(self, epoch, logs=None):
        probs = self.model.predict(self.x_val, verbose=0)[:, 1]
        preds = (probs >= 0.5).astype(int)
        f1 = f1_score(self.y_val, preds, zero_division=0)
        self.best_f1 = max(self.best_f1, float(f1))
        if logs is not None:
            logs["val_f1"] = f1
        print(f" - val_f1: {f1:.4f}")


def split_distribution(labels):
    unique, counts = np.unique(labels, return_counts=True)
    return {int(k): int(v) for k, v in zip(unique, counts)}


print("--- STEP 3: TRAINING WITH ADVANCED METRICS ---")
start_time = time.time()
set_seed(SEED)

required = [
    INPUT_X_TRAIN,
    INPUT_Y_TRAIN,
    INPUT_X_VALID,
    INPUT_Y_VALID,
    INPUT_X_TEST,
    INPUT_Y_TEST,
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    print(f"ERROR: Missing files: {missing}")
    raise SystemExit(1)

X_train = np.load(str(INPUT_X_TRAIN))
y_train = np.load(str(INPUT_Y_TRAIN))
X_valid = np.load(str(INPUT_X_VALID))
y_valid = np.load(str(INPUT_Y_VALID))
X_test = np.load(str(INPUT_X_TEST))
y_test = np.load(str(INPUT_Y_TEST))

print(f"Train: {X_train.shape} | Valid: {X_valid.shape} | Test: {X_test.shape}")

classes = np.unique(y_train)
weights = compute_class_weight(class_weight="balanced", classes=classes, y=y_train)
class_weights = {int(cls): float(wt) for cls, wt in zip(classes, weights)}
print(f"Class weights: {class_weights}")

model = Sequential(
    [
        Embedding(input_dim=VOCAB_SIZE, output_dim=EMBEDDING_DIM, input_length=MAX_LENGTH, name="embedding_input"),
        SpatialDropout1D(0.2, name="spatial_dropout"),
        Bidirectional(LSTM(LSTM_UNITS, dropout=0.2, recurrent_dropout=0.2), name="bidirectional_lstm"),
        Dense(2, activation="softmax", name="classification_output"),
    ]
)
model.summary()

metrics = [
    "accuracy",
    Precision(name="precision"),
    Recall(name="recall"),
    AUC(name="roc_auc", curve="ROC"),
    AUC(name="pr_auc", curve="PR"),
]

optimizer = Adam(clipnorm=1.0)
model.compile(
    loss="sparse_categorical_crossentropy",
    optimizer=optimizer,
    metrics=metrics,
)

BEST_MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
f1_callback = F1Callback(X_valid, y_valid)
callbacks = [
    f1_callback,
    EarlyStopping(monitor="val_pr_auc", patience=4, mode="max", restore_best_weights=True, verbose=1),
    ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, verbose=1),
    ModelCheckpoint(
        str(BEST_MODEL_FILE),
        monitor="val_pr_auc",
        mode="max",
        save_best_only=True,
        verbose=1,
    ),
]

history = model.fit(
    X_train,
    y_train,
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    validation_data=(X_valid, y_valid),
    callbacks=callbacks,
    class_weight=class_weights,
    verbose=1,
)

training_time = time.time() - start_time
print(f"Training finished in {training_time:.2f} seconds.")

def get_probs(x):
    return model.predict(x, verbose=0)[:, 1]


valid_probs = get_probs(X_valid)
test_probs = get_probs(X_test)

best_f1_threshold, best_recall_threshold = scan_thresholds(valid_probs, y_valid)

calibration = {"enabled": False}
calibrated_valid = valid_probs
calibrated_test = test_probs

temp, nll = fit_temperature(valid_probs, y_valid)
calibrated_valid = temperature_scale(valid_probs, temp)
calibrated_test = temperature_scale(test_probs, temp)
calibration = {
    "enabled": True,
    "method": "temperature_scaling",
    "temperature": float(temp),
    "nll": float(nll),
}

valid_brier = float(np.mean((calibrated_valid - y_valid) ** 2))
test_brier = float(np.mean((calibrated_test - y_test) ** 2))
valid_ece = ece_score(calibrated_valid, y_valid, bins=10)
test_ece = ece_score(calibrated_test, y_test, bins=10)

report = {
    "config": {
        "vocab_size": VOCAB_SIZE,
        "max_length": MAX_LENGTH,
        "embedding_dim": EMBEDDING_DIM,
        "lstm_units": LSTM_UNITS,
        "batch_size": BATCH_SIZE,
        "epochs": EPOCHS,
        "seed": SEED,
        "precision_min": P_MIN,
    },
    "split_distribution": {
        "train": split_distribution(y_train),
        "valid": split_distribution(y_valid),
        "test": split_distribution(y_test),
    },
    "class_weights": class_weights,
    "thresholds": {
        "best_f1": best_f1_threshold,
        "best_recall": best_recall_threshold,
    },
    "calibration": calibration,
    "metrics": {},
    "training": {
        "time_seconds": float(training_time),
        "best_val_f1": float(f1_callback.best_f1),
    },
}

def add_curve_plots(probs, y_true):
    try:
        from sklearn.metrics import RocCurveDisplay, PrecisionRecallDisplay

        RocCurveDisplay.from_predictions(y_true, probs)
        plt.title("ROC Curve")
        plt.savefig(str(ROC_PLOT_FILE))
        plt.close()

        PrecisionRecallDisplay.from_predictions(y_true, probs)
        plt.title("PR Curve")
        plt.savefig(str(PR_PLOT_FILE))
        plt.close()
    except Exception as exc:
        print(f"Plot warning: {exc}")


def add_metrics(prefix, probs, y_true):
    roc = roc_auc_score(y_true, probs)
    pr = average_precision_score(y_true, probs)
    report["metrics"][prefix] = {
        "roc_auc": float(roc),
        "pr_auc": float(pr),
    }


add_metrics("valid_raw", valid_probs, y_valid)
add_metrics("test_raw", test_probs, y_test)
add_metrics("valid_calibrated", calibrated_valid, y_valid)
add_metrics("test_calibrated", calibrated_test, y_test)

report["metrics"]["valid_calibrated"]["brier"] = valid_brier
report["metrics"]["test_calibrated"]["brier"] = test_brier
report["metrics"]["valid_calibrated"]["ece"] = valid_ece
report["metrics"]["test_calibrated"]["ece"] = test_ece

report["metrics"]["test_thresholds"] = {
    "threshold_0.5": evaluate_at_threshold(calibrated_test, y_test, 0.5),
    "threshold_best_f1": evaluate_at_threshold(calibrated_test, y_test, best_f1_threshold["threshold"]),
}

if best_recall_threshold:
    report["metrics"]["test_thresholds"]["threshold_best_recall"] = evaluate_at_threshold(
        calibrated_test, y_test, best_recall_threshold["threshold"]
    )

precision, recall, f1, _ = precision_recall_fscore_support(
    y_test, (calibrated_test >= 0.5).astype(int), average="binary", zero_division=0
)
report["metrics"]["test_summary"] = {
    "precision": float(precision),
    "recall": float(recall),
    "f1": float(f1),
    "mcc": float(matthews_corrcoef(y_test, (calibrated_test >= 0.5).astype(int))),
}

add_curve_plots(calibrated_test, y_test)

try:
    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1)
    plt.plot(history.history.get("accuracy", []), label="train_accuracy")
    plt.plot(history.history.get("val_accuracy", []), label="val_accuracy")
    plt.title("Accuracy by Epoch")
    plt.xlabel("Epoch")
    plt.ylabel("Accuracy")
    plt.legend()
    plt.grid(True)
    plt.subplot(1, 2, 2)
    plt.plot(history.history.get("loss", []), label="train_loss")
    plt.plot(history.history.get("val_loss", []), label="val_loss")
    plt.title("Loss by Epoch")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(str(HISTORY_PLOT_FILE))
    plt.close()
except Exception as exc:
    print(f"Plot warning: {exc}")

METRICS_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
with METRICS_REPORT_FILE.open("w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2)

with CALIBRATION_FILE.open("w", encoding="utf-8") as handle:
    json.dump(calibration, handle, indent=2)

decision = {
    "thresholds": report["thresholds"],
    "calibration": calibration,
}
with DECISION_FILE.open("w", encoding="utf-8") as handle:
    json.dump(decision, handle, indent=2)

end_time = time.time()
print(f"Metrics saved to {METRICS_REPORT_FILE}")
print(f"Calibration saved to {CALIBRATION_FILE}")
print(f"Decision saved to {DECISION_FILE}")
print(f"Total time: {end_time - start_time:.2f} seconds.")
