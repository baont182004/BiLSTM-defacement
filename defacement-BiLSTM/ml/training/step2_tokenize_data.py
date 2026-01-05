import json
import random
import re
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.preprocessing.text import Tokenizer
import unicodedata

ROOT_DIR = Path(__file__).resolve().parents[2]

# --- CONFIG ---
INPUT_FILE = ROOT_DIR / "ml" / "data" / "raw" / "rawData.json"

OUTPUT_X_TRAIN = ROOT_DIR / "ml" / "data" / "processed" / "X_train.npy"
OUTPUT_Y_TRAIN = ROOT_DIR / "ml" / "data" / "processed" / "y_train.npy"
OUTPUT_X_VALID = ROOT_DIR / "ml" / "data" / "processed" / "X_valid.npy"
OUTPUT_Y_VALID = ROOT_DIR / "ml" / "data" / "processed" / "y_valid.npy"
OUTPUT_X_TEST = ROOT_DIR / "ml" / "data" / "processed" / "X_test.npy"
OUTPUT_Y_TEST = ROOT_DIR / "ml" / "data" / "processed" / "y_test.npy"
OUTPUT_TOKENIZER = ROOT_DIR / "ml" / "artifacts" / "tokenizer.json"

MAX_LENGTH = 128
VOCAB_SIZE = 20000
OOV_TOKEN = "<OOV>"

TEST_SPLIT_SIZE = 0.2
VALID_SPLIT_SIZE = 0.25
SEED = 42
# ----------------


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def basic_clean(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = cleaned.replace("\u00a0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"(.)\1{3,}", r"\1\1", cleaned)
    return cleaned.strip()


def report_distribution(name: str, labels: np.ndarray) -> dict:
    unique, counts = np.unique(labels, return_counts=True)
    dist = {int(k): int(v) for k, v in zip(unique, counts)}
    total = int(labels.shape[0])
    print(f"{name} samples: {total} | distribution: {dist}")
    return {"total": total, "distribution": dist}


print("--- STEP 2: TOKENIZE + SPLIT (NO LEAKAGE) ---")
set_seed(SEED)

if not INPUT_FILE.exists():
    print(f"ERROR: Missing input file {INPUT_FILE}")
    raise SystemExit(1)

with INPUT_FILE.open("r", encoding="utf-8") as handle:
    data = json.load(handle)

if not data:
    print("ERROR: rawData.json is empty.")
    raise SystemExit(1)

valid = [item for item in data if item.get("text") and item.get("label") is not None]
texts = [basic_clean(item["text"]) for item in valid]
labels = np.array([int(item["label"]) for item in valid], dtype=np.int64)

if not texts:
    print("ERROR: No valid samples after filtering.")
    raise SystemExit(1)

print(f"Loaded samples: {len(texts)}")

texts_temp, texts_test, y_temp, y_test = train_test_split(
    texts,
    labels,
    test_size=TEST_SPLIT_SIZE,
    random_state=SEED,
    stratify=labels,
)
texts_train, texts_valid, y_train, y_valid = train_test_split(
    texts_temp,
    y_temp,
    test_size=VALID_SPLIT_SIZE,
    random_state=SEED,
    stratify=y_temp,
)

report_distribution("Train", y_train)
report_distribution("Valid", y_valid)
report_distribution("Test", y_test)

print(f"Fitting tokenizer on train split only (vocab={VOCAB_SIZE})...")
tokenizer = Tokenizer(num_words=VOCAB_SIZE, oov_token=OOV_TOKEN)
tokenizer.fit_on_texts(texts_train)

def to_padded(text_list):
    sequences = tokenizer.texts_to_sequences(text_list)
    return pad_sequences(
        sequences,
        maxlen=MAX_LENGTH,
        padding="post",
        truncating="post",
    )

X_train = to_padded(texts_train)
X_valid = to_padded(texts_valid)
X_test = to_padded(texts_test)

OUTPUT_TOKENIZER.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_X_TRAIN.parent.mkdir(parents=True, exist_ok=True)

np.save(str(OUTPUT_X_TRAIN), X_train)
np.save(str(OUTPUT_Y_TRAIN), y_train)
np.save(str(OUTPUT_X_VALID), X_valid)
np.save(str(OUTPUT_Y_VALID), y_valid)
np.save(str(OUTPUT_X_TEST), X_test)
np.save(str(OUTPUT_Y_TEST), y_test)

tokenizer_json_string = tokenizer.to_json()
try:
    tokenizer_dict = json.loads(tokenizer_json_string)
    with OUTPUT_TOKENIZER.open("w", encoding="utf-8") as handle:
        json.dump(tokenizer_dict, handle, ensure_ascii=False, indent=4)
except json.JSONDecodeError:
    with OUTPUT_TOKENIZER.open("w", encoding="utf-8") as handle:
        handle.write(tokenizer_json_string)

print("Saved splits:")
print(f"  X_train: {X_train.shape} -> {OUTPUT_X_TRAIN}")
print(f"  y_train: {y_train.shape} -> {OUTPUT_Y_TRAIN}")
print(f"  X_valid: {X_valid.shape} -> {OUTPUT_X_VALID}")
print(f"  y_valid: {y_valid.shape} -> {OUTPUT_Y_VALID}")
print(f"  X_test:  {X_test.shape} -> {OUTPUT_X_TEST}")
print(f"  y_test:  {y_test.shape} -> {OUTPUT_Y_TEST}")
print(f"Tokenizer: {OUTPUT_TOKENIZER}")
print("--- STEP 2 COMPLETE ---")
