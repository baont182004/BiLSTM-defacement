import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, Bidirectional, LSTM, Dense, SpatialDropout1D
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping
from tensorflow.keras.metrics import Precision, Recall
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import os
import time
import math 

# --- CẤU HÌNH ---
INPUT_X = 'X_data.npy'
INPUT_Y = 'y_data.npy'

BEST_MODEL_FILE = 'bilstm_defacement_model.keras'
HISTORY_PLOT_FILE = 'training_history.png' 

VOCAB_SIZE = 20000
MAX_LENGTH = 128

EMBEDDING_DIM = 64
LSTM_UNITS = 64

# Thông số huấn luyện
TEST_SPLIT_SIZE = 0.2
VALID_SPLIT_SIZE = 0.25 # -> 60% Train, 20% Valid, 20% Test
BATCH_SIZE = 64
EPOCHS = 15
# ------------------------------------

print("--- BẮT ĐẦU BƯỚC 3: HUẤN LUYỆN MÔ HÌNH (NÂNG CAO) ---")
start_time = time.time()

# --- 1. Tải Dữ liệu Đã xử lý ---
if not os.path.exists(INPUT_X) or not os.path.exists(INPUT_Y):
    print(f"LỖI: Không tìm thấy tệp '{INPUT_X}' hoặc '{INPUT_Y}'.")
    exit()

print(f"Đang tải dữ liệu từ {INPUT_X} và {INPUT_Y}...")
X = np.load(INPUT_X)
y = np.load(INPUT_Y)
num_total_samples = X.shape[0]
print(f"Đã tải {num_total_samples} mẫu.")

# Chuyển đổi nhãn Y sang dạng one-hot
y_categorical = to_categorical(y, num_classes=2)
print(f"Đã chuyển đổi nhãn Y sang dạng one-hot.")

# --- 2. Chia Dữ liệu (Train / Validation / Test) ---
print(f"Đang chia dữ liệu (60% Train, 20% Valid, 20% Test)...")
X_temp, X_test, y_temp, y_test = train_test_split(
    X, y_categorical, test_size=TEST_SPLIT_SIZE, random_state=42, stratify=y_categorical
)
X_train, X_valid, y_train, y_valid = train_test_split(
    X_temp, y_temp, test_size=VALID_SPLIT_SIZE, random_state=42, stratify=y_temp
)
num_train_samples = len(X_train)
num_valid_samples = len(X_valid)
num_test_samples = len(X_test)

print(f"Kích thước tập Train: {num_train_samples} mẫu") 
print(f"Kích thước tập Valid: {num_valid_samples} mẫu")
print(f"Kích thước tập Test:  {num_test_samples} mẫu")

# --- TÍNH TOÁN VÀ IN RA SỐ BƯỚC DỰ KIẾN ---
expected_steps_per_epoch = math.ceil(num_train_samples / BATCH_SIZE)
print(f"Với {num_train_samples} mẫu Train và Batch Size = {BATCH_SIZE}, dự kiến sẽ có {expected_steps_per_epoch} bước mỗi epoch.") 
# --------------------------------------------------

# --- 3. Xây dựng Kiến trúc Mô hình BiLSTM ---
print("\nĐang xây dựng kiến trúc mô hình...")
model = Sequential([
    Embedding(input_dim=VOCAB_SIZE, output_dim=EMBEDDING_DIM, input_length=MAX_LENGTH, name='embedding_input'),
    SpatialDropout1D(0.2, name='spatial_dropout'),
    Bidirectional(LSTM(LSTM_UNITS, dropout=0.2, recurrent_dropout=0.2), name='bidirectional_lstm'),
    Dense(2, activation='softmax', name='classification_output')
])
model.summary()

# --- 4. Biên dịch Mô hình ---
print("\nĐang biên dịch mô hình...")
model.compile(
    loss='categorical_crossentropy',
    optimizer='adam',
    metrics=['accuracy', Precision(name='precision'), Recall(name='recall')]
)

# --- 5. Thiết lập Callbacks ---
early_stopping = EarlyStopping(
    monitor='val_loss',
    patience=3,
    verbose=1,
    restore_best_weights=True
)
model_checkpoint = ModelCheckpoint(
    BEST_MODEL_FILE,
    monitor='val_loss',
    save_best_only=True,
    verbose=1
)

# --- 6. Huấn luyện Mô hình ---
print(f"\nBắt đầu quá trình huấn luyện {EPOCHS} epochs (có thể dừng sớm)...")
history = model.fit(
    X_train, y_train,
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    validation_data=(X_valid, y_valid),
    callbacks=[early_stopping, model_checkpoint],
    verbose=1
)
training_time = time.time() - start_time
print(f"\nHuấn luyện hoàn tất sau {training_time:.2f} giây.")

# --- 7. Đánh giá Mô hình trên tập Test ---
print("\nĐang đánh giá mô hình trên tập Test (dữ liệu chưa từng thấy)...")
results = model.evaluate(X_test, y_test, verbose=0)
loss = results[0]
accuracy = results[1]
precision = results[2]
recall = results[3]

print(f"\n================== KẾT QUẢ ĐÁNH GIÁ TRÊN TẬP TEST ==================")
print(f"Loss (Mất mát):     {loss:.4f}")
print(f"Accuracy (Độ chính xác): {accuracy * 100:.2f}%")
print(f"Precision:           {precision:.4f}")
print(f"Recall (Độ nhạy):    {recall:.4f}")
print(f"======================================================================")

# --- 8. Tạo Báo cáo Chi tiết và Ma trận Nhầm lẫn ---
print("\nĐang tạo báo cáo chi tiết và ma trận nhầm lẫn...")
y_pred_probs = model.predict(X_test)
y_pred_classes = np.argmax(y_pred_probs, axis=1)
y_test_classes = np.argmax(y_test, axis=1)

print("\nBáo cáo Phân loại (Classification Report):")
print(classification_report(y_test_classes, y_pred_classes, labels=[0, 1], target_names=['Bình thường (0)', 'Deface (1)']))

print("\nMa trận Nhầm lẫn (Confusion Matrix):")
cm = confusion_matrix(y_test_classes, y_pred_classes, labels=[0, 1])
print("                 Dự đoán: Bình thường(0) | Dự đoán: Deface(1)")
print("Thực tế: Bình thường(0) | {:<22} | {:<18}".format(cm[0][0], cm[0][1]))
print("Thực tế: Deface(1)      | {:<22} | {:<18}".format(cm[1][0], cm[1][1]))
print("-" * 65)
print(f"TN (True Negative) : {cm[0][0]} (Dự đoán đúng 'Bình thường')")
print(f"FP (False Positive): {cm[0][1]} ('Bình thường' dự đoán nhầm thành 'Deface' - Báo động giả)")
print(f"FN (False Negative): {cm[1][0]} ('Deface' dự đoán nhầm thành 'Bình thường' - Bỏ lọt!)")
print(f"TP (True Positive) : {cm[1][1]} (Dự đoán đúng 'Deface')")
print("=" * 65)

# --- 9. Vẽ Biểu đồ Lịch sử Huấn luyện ---
try:
    print(f"\nĐang vẽ và lưu biểu đồ lịch sử huấn luyện vào '{HISTORY_PLOT_FILE}'...")
    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1)
    plt.plot(history.history['accuracy'], label='Độ chính xác (Train)')
    plt.plot(history.history['val_accuracy'], label='Độ chính xác (Valid)')
    plt.title('Độ chính xác qua các Epoch')
    plt.xlabel('Epoch')
    plt.ylabel('Accuracy')
    plt.legend()
    plt.grid(True)
    plt.subplot(1, 2, 2)
    plt.plot(history.history['loss'], label='Mất mát (Train)')
    plt.plot(history.history['val_loss'], label='Mất mát (Valid)')
    plt.title('Mất mát qua các Epoch')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(HISTORY_PLOT_FILE)
    print(f" -> Đã lưu biểu đồ thành công.")
except ImportError:
     print("\nLƯU Ý: Không thể vẽ biểu đồ. Vui lòng cài đặt matplotlib: pip install matplotlib")
except Exception as e:
    print(f"\nLỗi khi vẽ biểu đồ: {e}.")

end_time = time.time()
total_time = end_time - start_time
print(f"\n--- HOÀN TẤT BƯỚC 3 SAU {total_time:.2f} GIÂY ---")
print(f"Mô hình TỐT NHẤT đã được lưu vào '{BEST_MODEL_FILE}'.")