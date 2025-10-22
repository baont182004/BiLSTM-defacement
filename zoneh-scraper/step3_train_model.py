import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, Bidirectional, LSTM, Dense, SpatialDropout1D
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
import os

# --- CẤU HÌNH  ---
INPUT_X = 'X_data.npy'
INPUT_Y = 'y_data.npy'
MODEL_OUTPUT_FILE = 'bilstm_defacement_model.keras'

# Thông số từ Bước 2
VOCAB_SIZE = 20000  # Giữ nguyên từ script Tokenizer
MAX_LENGTH = 128    # "lựa chọn 128 từ đầu tiên"

# Thông số mô hình (Dựa trên Hình 4 và Bước 3, 4, 5)
EMBEDDING_DIM = 64  # Bước 3 (Theo Hình 4, output là (None, 128, 64))
LSTM_UNITS = 64     # Bước 5 (Để BiLSTM cho ra 64 + 64 = 128 đặc trưng)

# Thông số huấn luyện
TEST_SPLIT_SIZE = 0.2   # 20% cho Kiểm tra
VALID_SPLIT_SIZE = 0.25 # 25% của 80% = 20% cho Xác thực (60/20/20)
BATCH_SIZE = 64
EPOCHS = 10
# ------------------------------------

print("--- BẮT ĐẦU BƯỚC 3: HUẤN LUYỆN MÔ HÌNH (THEO TÀI LIỆU) ---")

# --- 1. Tải dữ liệu đã xử lý ---
if not os.path.exists(INPUT_X) or not os.path.exists(INPUT_Y):
    print(f"LỖI: Không tìm thấy tệp '{INPUT_X}' hoặc '{INPUT_Y}'.")
    exit()

print(f"Đang tải dữ liệu từ {INPUT_X} và {INPUT_Y}...")
X = np.load(INPUT_X)
y = np.load(INPUT_Y)
print(f"Đã tải {X.shape[0]} mẫu.")

# *** THAY ĐỔI QUAN TRỌNG (cho Bước 6 - Softmax) ***
# Chuyển đổi nhãn Y sang dạng categorical (one-hot encoding)
# 0 -> [1, 0] (Bình thường)
# 1 -> [0, 1] (Deface)
y_categorical = to_categorical(y, num_classes=2)
print(f"Đã chuyển đổi nhãn Y sang dạng one-hot (ví dụ: 1 -> {y_categorical[np.argmax(y)]})")

# --- 2. Chia dữ liệu (Train / Validation / Test) ---
print(f"Đang chia dữ liệu (60% Train, 20% Valid, 20% Test)...")
X_temp, X_test, y_temp, y_test = train_test_split(
    X, y_categorical, test_size=TEST_SPLIT_SIZE, random_state=42, stratify=y_categorical
)
X_train, X_valid, y_train, y_valid = train_test_split(
    X_temp, y_temp, test_size=VALID_SPLIT_SIZE, random_state=42, stratify=y_temp
)
print(f"Kích thước tập Train: {len(X_train)} mẫu")
print(f"Kích thước tập Valid: {len(X_valid)} mẫu")
print(f"Kích thước tập Test:  {len(X_test)} mẫu")

# --- 3. Xây dựng kiến trúc mô hình (Theo Bước 3, 4, 5, 6) ---
print("Đang xây dựng kiến trúc mô hình (theo Hình 4)...")

model = Sequential([
    # Bước 3: Lớp Embedding
    Embedding(input_dim=VOCAB_SIZE, 
              output_dim=EMBEDDING_DIM, 
              input_length=MAX_LENGTH,
              name='embedding_input'),

    # Bước 4: Lớp SpatialDropout1D
    SpatialDropout1D(0.2, name='spatial_dropout'), 

    # Bước 5: Lớp BiLSTM (cho ra 128 đặc trưng)
    Bidirectional(LSTM(LSTM_UNITS, dropout=0.2, recurrent_dropout=0.2), name='bidirectional_lstm'),
    
    # Bước 6: Lớp kết nối đầy đủ (Fully Connected) và Phân loại
    # (Bài báo không đề cập lớp Dense(64) trung gian,
    # nhưng Hình 4 (dense_Dense) lại ngụ ý có một lớp Fully Connected
    # trước lớp phân loại 2-node. Chúng ta sẽ theo Hình 4)
    # CẬP NHẬT: Hình 4 cho thấy BiLSTM -> Dense(2). 
    # Chúng ta sẽ bỏ lớp 64-node trung gian để bám sát Hình 4
    
    # Lớp Phân loại cuối cùng (theo Bước 6 và Hình 4)
    Dense(2, activation='softmax', name='classification_output') 
])

# In cấu trúc mô hình ra terminal
model.summary()

# --- 4. Biên dịch mô hình ---
print("Đang biên dịch mô hình...")
model.compile(
    # Sử dụng 'categorical_crossentropy' vì chúng ta dùng softmax (Bước 6)
    loss='categorical_crossentropy', 
    optimizer='adam',
    metrics=['accuracy']
)

# --- 5. Huấn luyện mô hình ---
print(f"\nBắt đầu quá trình huấn luyện {EPOCHS} epochs...")
early_stopping = EarlyStopping(monitor='val_loss', patience=3, restore_best_weights=True)

history = model.fit(
    X_train, y_train,
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    validation_data=(X_valid, y_valid),
    callbacks=[early_stopping],
    verbose=1
)
print("Huấn luyện hoàn tất.")

# --- 6. Đánh giá mô hình trên tập Test ---
print("\nĐang đánh giá mô hình trên tập Test...")
loss, accuracy = model.evaluate(X_test, y_test)
print(f"\n======================================")
print(f"Độ chính xác trên tập Test: {accuracy * 100:.2f}%")
print(f"Loss trên tập Test: {loss:.4f}")
print(f"======================================")

# --- 7. Lưu mô hình ---
print(f"Đang lưu mô hình đã huấn luyện vào {MODEL_OUTPUT_FILE}...")
model.save(MODEL_OUTPUT_FILE)

print("\n--- HOÀN TẤT BƯỚC 3 ---")
print(f"Mô hình đã được lưu thành công vào '{MODEL_OUTPUT_FILE}'.")