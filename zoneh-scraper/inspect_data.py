import numpy as np
import os

# --- CẤU HÌNH ---
FILE_X = 'X_data.npy'
FILE_Y = 'y_data.npy'
NUM_SAMPLES_TO_VIEW = 5 # Số lượng mẫu ngẫu nhiên bạn muốn xem
# --------------------

def inspect_data():
    print(f"--- BẮT ĐẦU KIỂM TRA {NUM_SAMPLES_TO_VIEW} MẪU NGẪU NHIÊN ---")

    # --- 1. Kiểm tra tệp ---
    if not os.path.exists(FILE_X) or not os.path.exists(FILE_Y):
        print(f"LỖI: Không tìm thấy tệp '{FILE_X}' hoặc '{FILE_Y}'.")
        print("Vui lòng đảm bảo 2 tệp .npy nằm trong cùng thư mục với script này.")
        return # Thoát nếu không tìm thấy tệp

    # --- 2. Tải dữ liệu ---
    try:
        X = np.load(FILE_X)
        y = np.load(FILE_Y)
        
        num_total_samples = X.shape[0]
        print(f"Đã tải thành công {num_total_samples} mẫu từ các tệp .npy.")

        if num_total_samples == 0:
            print("LỖI: Tệp dữ liệu rỗng, không có mẫu nào để hiển thị.")
            return
        elif num_total_samples < NUM_SAMPLES_TO_VIEW:
            print(f"Cảnh báo: Chỉ có {num_total_samples} mẫu, sẽ hiển thị tất cả.")
            indices_to_show = np.arange(num_total_samples)
        else:
            # Lấy 5 chỉ số (index) ngẫu nhiên, không lặp lại
            indices_to_show = np.random.choice(num_total_samples, NUM_SAMPLES_TO_VIEW, replace=False)
            print(f"Đang hiển thị {NUM_SAMPLES_TO_VIEW} mẫu ngẫu nhiên (từ các chỉ số: {indices_to_show}):")

        # --- 3. In 5 mẫu ngẫu nhiên ---
        # Đặt tùy chọn in của NumPy để hiển thị toàn bộ mảng mà không bị cắt bớt
        np.set_printoptions(threshold=np.inf)
        
        for i, index in enumerate(indices_to_show):
            print(f"\n--- Mẫu ngẫu nhiên {i+1} (từ chỉ số {index}) ---")
            
            # Lấy dữ liệu X và Y tại chỉ số ngẫu nhiên
            sample_X = X[index]
            sample_y = y[index]
            
            print(f"  Nhãn (Y): {sample_y}  (0=Bình thường, 1=Deface)")
            print(f"  Chuỗi (X) đầy đủ (128 số):")
            # In mảng X. Vì đã set_printoptions, nó sẽ in toàn bộ 128 số.
            print(f"  {sample_X}") 

    except Exception as e:
        print(f"LỖI: Đã xảy ra sự cố khi tải hoặc xử lý tệp .npy: {e}")

    # Đặt lại tùy chọn in về mặc định
    np.set_printoptions(threshold=1000)
    print("\n--- KIỂM TRA HOÀN TẤT ---")

# Dòng này đảm bảo script sẽ chạy khi bạn gọi nó từ CMD
if __name__ == "__main__":
    inspect_data()