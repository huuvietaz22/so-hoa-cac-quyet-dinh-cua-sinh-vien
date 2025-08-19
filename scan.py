import customtkinter
from tkinter import filedialog, messagebox
import google.generativeai as genai
from PIL import Image
import os
import threading
import json
import re
from CTkListbox import CTkListbox

API_KEY = "AIzaSyAYgvAsQCU2zmRGo4xTYz_-2rxSzlHDIF4"

# --- Hàm xử lý API (Đã cập nhật prompt) ---
def get_image_text(image_path):
    """
    Sử dụng Google Gemini API để trích xuất văn bản từ hình ảnh.
    Trả về một đối tượng JSON string chứa các thông tin cụ thể và nội dung văn bản.
    """
    try:
        if not API_KEY or "AIzaSy" not in API_KEY:
            messagebox.showerror(
                "Lỗi API Key",
                "API Key không hợp lệ. Vui lòng kiểm tra lại trong mã nguồn.",
            )
            return None

        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        img = Image.open(image_path)

        # Cập nhật prompt để yêu cầu trích xuất các thông tin chi tiết
        prompt = """Trích xuất toàn bộ văn bản có trong hình ảnh. Đồng thời, tìm và trích xuất các thông tin sau từ nội dung:
- Họ tên của sinh viên.
- Tên đầy đủ của quyết định (ví dụ: "QUYẾT ĐỊNH VỀ VIỆC CHUYỂN NGÀNH HỌC").
- Tên của người ký quyết định.
- Một danh sách các điều, khoản hoặc quyết định cụ thể được liệt kê trong văn bản.

Chỉ trả về một đối tượng JSON duy nhất với các khóa sau:
1. "ho_ten_sinh_vien": Họ tên của sinh viên, không dấu, không khoảng trắng, ví dụ: "Nguyen_Van_A".
2. "ten_quyet_dinh": Tên đầy đủ của quyết định, không dấu, không khoảng trắng, ví dụ: "QUYET_DINH_CHUYEN_NGANH_HOC".
3. "nguoi_ki": Tên của người ký quyết định, không dấu, không khoảng trắng, ví dụ: "Tran_Van_B".
4. "cac_quyet_dinh": Một mảng các chuỗi, mỗi chuỗi là một điều, khoản hoặc quyết định cụ thể (ví dụ: ["Điều 1: Nay cho phép sinh viên...", "Điều 2: Quyết định có hiệu lực..."]).
5. "content": Toàn bộ nội dung văn bản đã trích xuất, giữ nguyên định dạng ban đầu.

Ví dụ:
{
  "ho_ten_sinh_vien": "Nguyen_Van_A",
  "ten_quyet_dinh": "QUYET_DINH_TOT_NGHIEP",
  "nguoi_ki": "Tran_Van_B",
  "cac_quyet_dinh": ["Điều 1: ...", "Điều 2: ..."],
  "content": "Đây là toàn bộ nội dung văn bản..."
}"""

        response = model.generate_content([prompt, img])
        
        full_text = response.text.strip()
        
        match = re.search(r'\{.*\}', full_text, re.DOTALL)
        if match:
            json_string = match.group(0)
            return json_string
        else:
            return None

    except Exception as e:
        print(f"Lỗi khi xử lý ảnh qua API: {e}")
        messagebox.showerror("Lỗi API", f"Đã xảy ra lỗi khi gọi API của Google:\n\n{e}")
        return None

# --- LỚP GIAO DIỆN ỨNG DỤNG (Đã cập nhật hoàn toàn bố cục) ---
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # Cấu hình cửa sổ chính
        self.title("📑 Trình trích xuất & tìm kiếm văn bản từ ảnh")
        self.geometry("1200x800")
        customtkinter.set_appearance_mode("Dark")
        customtkinter.set_default_color_theme("green")

        # --- CONTAINER CHÍNH CHO TOÀN BỘ GIAO DIỆN ---
        main_frame = customtkinter.CTkFrame(self, corner_radius=20, fg_color="#1a1a1a")
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(2, weight=1)
        
        # Tiêu đề và phụ đề, nằm ở trên cùng và trải dài hai cột
        title_label = customtkinter.CTkLabel(
            main_frame,
            text="TRÌNH TRÍCH XUẤT VĂN BẢN VÀ TÌM KIẾM",
            font=("Arial", 32, "bold"),
            text_color="#4CAF50"
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(20, 5), sticky="n")

        subtitle_label = customtkinter.CTkLabel(
            main_frame,
            text="Sử dụng AI để nhận diện và tìm kiếm nội dung trong hình ảnh",
            font=("Arial", 16),
            text_color="#a0a0a0"
        )
        subtitle_label.grid(row=1, column=0, columnspan=2, pady=(0, 20), sticky="n")
        
        # --- KHUNG BÊN TRÁI: NHẬP LIỆU & TÌM KIẾM ---
        left_frame = customtkinter.CTkFrame(main_frame, corner_radius=15)
        left_frame.grid(row=2, column=0, padx=15, pady=15, sticky="nsew")
        left_frame.grid_columnconfigure(0, weight=1)
        
        # Khung nhỏ hơn cho chức năng trích xuất
        extraction_frame = customtkinter.CTkFrame(left_frame, corner_radius=10)
        extraction_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        extraction_frame.grid_columnconfigure(1, weight=1)

        image_label = customtkinter.CTkLabel(extraction_frame, text="🖼️ Ảnh cần trích xuất:", font=("Arial", 14, "bold"))
        image_label.grid(row=0, column=0, padx=15, pady=10, sticky="w")
        self.image_path_entry = customtkinter.CTkEntry(extraction_frame, placeholder_text="Chưa chọn file ảnh...")
        self.image_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        browse_image_button = customtkinter.CTkButton(extraction_frame, text="Duyệt...", command=self.select_image_file, width=80)
        browse_image_button.grid(row=0, column=2, padx=15, pady=10)

        folder_label = customtkinter.CTkLabel(extraction_frame, text="📁 Thư mục lưu trữ:", font=("Arial", 14, "bold"))
        folder_label.grid(row=1, column=0, padx=15, pady=10, sticky="w")
        self.output_folder_entry = customtkinter.CTkEntry(extraction_frame, placeholder_text="Chưa chọn thư mục...")
        self.output_folder_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        browse_folder_button = customtkinter.CTkButton(extraction_frame, text="Duyệt...", command=self.select_output_folder, width=80)
        browse_folder_button.grid(row=1, column=2, padx=15, pady=10)

        # Nút bắt đầu và thanh tiến trình
        self.start_button = customtkinter.CTkButton(
            left_frame,
            text="� BẮT ĐẦU TRÍCH XUẤT",
            font=("Arial", 18, "bold"),
            height=55,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            command=self.start_processing_thread,
            corner_radius=12
        )
        self.start_button.grid(row=1, column=0, padx=10, pady=(10, 5), sticky="ew")
        
        self.progress_bar = customtkinter.CTkProgressBar(left_frame, mode="indeterminate", height=10)
        self.progress_bar.grid(row=2, column=0, padx=10, pady=(0, 20), sticky="ew")
        self.progress_bar.stop()
        self.progress_bar.set(0)

        # Khung tìm kiếm
        search_frame = customtkinter.CTkFrame(left_frame, corner_radius=10)
        search_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = customtkinter.CTkEntry(search_frame, placeholder_text="🔍 Nhập từ khóa để tìm kiếm...", font=("Arial", 14))
        self.search_entry.grid(row=0, column=0, padx=(15, 5), pady=15, sticky="ew")
        # Gắn sự kiện nhấn phím vào ô nhập liệu
        self.search_entry.bind("<KeyRelease>", self.dynamic_search_files)
        
        search_button = customtkinter.CTkButton(search_frame, text="Tìm kiếm", command=self.search_files, width=100)
        search_button.grid(row=0, column=1, padx=(5, 15), pady=15)
        
        # --- KHUNG BÊN PHẢI: KẾT QUẢ & NỘI DUNG ---
        right_frame = customtkinter.CTkFrame(main_frame, corner_radius=15)
        right_frame.grid(row=2, column=1, padx=15, pady=15, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_rowconfigure(3, weight=3)

        # Danh sách kết quả
        results_label = customtkinter.CTkLabel(
            right_frame, text="📑 KẾT QUẢ TÌM KIẾM:", font=("Arial", 14, "bold")
        )
        results_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.results_listbox = CTkListbox(right_frame, command=self.show_file_content)
        self.results_listbox.grid(row=1, column=0, padx=10, pady=0, sticky="nsew")

        # Hộp hiển thị nội dung
        content_label = customtkinter.CTkLabel(
            right_frame, text="📝 NỘI DUNG FILE:", font=("Arial", 14, "bold")
        )
        content_label.grid(row=2, column=0, padx=10, pady=(15, 5), sticky="w")
        self.output_textbox = customtkinter.CTkTextbox(
            right_frame, font=("Consolas", 12), wrap="word"
        )
        self.output_textbox.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # Thanh trạng thái
        self.status_label = customtkinter.CTkLabel(
            self, text="✅ Sẵn sàng", fg_color="transparent", anchor="w", font=("Arial", 12)
        )
        self.status_label.pack(side="bottom", fill="x", padx=40, pady=10)


    # --- Các hàm xử lý ---
    def select_image_file(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file ảnh scan",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
        )
        if file_path:
            self.image_path_entry.delete(0, "end")
            self.image_path_entry.insert(0, file_path)
            self.status_label.configure(text=f"✅ Đã chọn file: {os.path.basename(file_path)}")

    def select_output_folder(self):
        folder_path = filedialog.askdirectory(title="Chọn thư mục để lưu và tìm kiếm file")
        if folder_path:
            self.output_folder_entry.delete(0, "end")
            self.output_folder_entry.insert(0, folder_path)
            self.status_label.configure(text=f"✅ Thư mục lưu: {folder_path}")
            # Sau khi chọn thư mục, tự động tải danh sách file
            self.load_initial_files()

    def start_processing_thread(self):
        image_path = self.image_path_entry.get()
        output_folder = self.output_folder_entry.get()

        if not image_path:
            messagebox.showerror("Lỗi", "Vui lòng chọn một file ảnh.")
            return

        if not output_folder:
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục để lưu.")
            return

        self.status_label.configure(text="⏳ Đang xử lý, vui lòng đợi...")
        self.start_button.configure(state="disabled")
        self.progress_bar.start()

        def worker():
            result = get_image_text(image_path)
            if result:
                try:
                    data = json.loads(result)
                    
                    # Lấy các thông tin mới từ phản hồi JSON
                    ten_quyet_dinh = data.get("ten_quyet_dinh", "khong_xac_dinh")
                    ho_ten_sinh_vien = data.get("ho_ten_sinh_vien", "khong_xac_dinh")
                    cac_quyet_dinh = data.get("cac_quyet_dinh", [])
                    nguoi_ki = data.get("nguoi_ki", "khong_xac_dinh")
                    content = data.get("content", "")

                    # Tạo tên file mới từ hai thông tin đã trích xuất
                    safe_ten_quyet_dinh = "".join(c for c in ten_quyet_dinh if c.isalnum() or c in ("_",)).strip().replace(" ", "_")
                    safe_ho_ten_sinh_vien = "".join(c for c in ho_ten_sinh_vien if c.isalnum() or c in ("_",)).strip().replace(" ", "_")

                    # Kết hợp hai tên lại, sử dụng một tên mặc định nếu không tìm thấy
                    if safe_ten_quyet_dinh == "khong_xac_dinh" and safe_ho_ten_sinh_vien == "khong_xac_dinh":
                        final_filename = "extracted_text"
                    else:
                        final_filename = f"{safe_ten_quyet_dinh}_{safe_ho_ten_sinh_vien}"
                        if final_filename.startswith("_"):
                            final_filename = final_filename[1:]
                        if final_filename.endswith("_"):
                            final_filename = final_filename[:-1]

                    file_path = os.path.join(output_folder, f"{final_filename}.txt")
                    
                    # Tạo nội dung hiển thị chi tiết cho người dùng
                    display_content = f"--- THÔNG TIN TRÍCH XUẤT ---\n"
                    display_content += f"Họ Tên Sinh Viên: {ho_ten_sinh_vien}\n"
                    display_content += f"Tên Quyết Định: {ten_quyet_dinh}\n"
                    display_content += f"Người Ký: {nguoi_ki}\n"
                    display_content += "Các Quyết Định:\n"
                    for qd in cac_quyet_dinh:
                        display_content += f"  - {qd}\n"
                    display_content += "\n--- TOÀN BỘ NỘI DUNG ---\n"
                    display_content += content

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(display_content)

                    self.after(0, lambda: self.finish_processing(file_path, display_content))
                except json.JSONDecodeError as e:
                    self.after(0, lambda: self.handle_error(f"Lỗi: Phản hồi API không phải là JSON hợp lệ. Chi tiết: {e}"))
            else:
                self.after(0, lambda: self.handle_error("Lỗi: Không thể trích xuất văn bản từ ảnh. Có thể phản hồi API không chứa JSON."))

        threading.Thread(target=worker).start()

    def finish_processing(self, file_path, content):
        self.progress_bar.stop()
        self.output_textbox.delete("1.0", "end")
        self.output_textbox.insert("1.0", content)
        self.status_label.configure(text=f"✅ Trích xuất thành công! Đã lưu tại: {file_path}")
        self.start_button.configure(state="normal")
        messagebox.showinfo("Thành công", f"Đã trích xuất và lưu văn bản vào:\n{file_path}")
        self.load_initial_files() # Tải lại danh sách file sau khi trích xuất thành công

    def handle_error(self, message):
        self.progress_bar.stop()
        self.status_label.configure(text=f"❌ {message}")
        self.start_button.configure(state="normal")
        messagebox.showerror("Lỗi", message)

    def load_initial_files(self):
        """Tải toàn bộ danh sách các file .txt có trong thư mục đã chọn."""
        output_folder = self.output_folder_entry.get()
        if not output_folder or not os.path.isdir(output_folder):
            return

        self.results_listbox.delete(0, "end")
        try:
            for filename in os.listdir(output_folder):
                if filename.endswith(".txt"):
                    self.results_listbox.insert("end", filename)
            self.status_label.configure(text=f"Đã tải {self.results_listbox.size()} file.")
        except Exception as e:
            print(f"Lỗi khi tải danh sách file: {e}")

    def dynamic_search_files(self, event=None):
        """Lọc danh sách file hiển thị khi người dùng gõ phím."""
        search_term = self.search_entry.get().strip().lower()
        output_folder = self.output_folder_entry.get()
        
        if not output_folder or not os.path.isdir(output_folder):
            return

        self.results_listbox.delete(0, "end")
        
        found_files_count = 0
        for filename in os.listdir(output_folder):
            if filename.endswith(".txt") and search_term in filename.lower():
                self.results_listbox.insert("end", filename)
                found_files_count += 1
        
        self.status_label.configure(text=f"✅ Tìm thấy {found_files_count} kết quả.")


    def search_files(self):
        """Tìm kiếm nội dung file khi nhấn nút."""
        search_term = self.search_entry.get().strip()
        output_folder = self.output_folder_entry.get()

        if not search_term:
            messagebox.showerror("Lỗi", "Vui lòng nhập từ khóa để tìm kiếm.")
            return
        
        if not output_folder or not os.path.isdir(output_folder):
            messagebox.showerror("Lỗi", "Thư mục không hợp lệ. Vui lòng chọn một thư mục có sẵn.")
            self.status_label.configure(text="❌ Lỗi: Thư mục không hợp lệ.")
            return

        self.results_listbox.delete(0, "end")
        self.status_label.configure(text="⏳ Đang tìm kiếm nội dung...")

        found_files = []
        try:
            for filename in os.listdir(output_folder):
                if filename.endswith(".txt"):
                    file_path = os.path.join(output_folder, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            if search_term.lower() in content.lower():
                                found_files.append(filename)
                    except Exception as e:
                        print(f"Lỗi khi đọc file {filename}: {e}")

            if found_files:
                for file in found_files:
                    self.results_listbox.insert("end", file)
                self.status_label.configure(text=f"✅ Tìm thấy {len(found_files)} kết quả trong nội dung file.")
            else:
                self.status_label.configure(text="❌ Không tìm thấy kết quả nào trong nội dung file.")

        except FileNotFoundError:
            messagebox.showerror("Lỗi", "Thư mục đã chọn không tồn tại.")
            self.status_label.configure(text="❌ Lỗi: Thư mục không tồn tại.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Đã xảy ra lỗi không xác định khi tìm kiếm:\n{e}")
            self.status_label.configure(text=f"❌ Lỗi: {e}")
    
    def show_file_content(self, selected_filename):
        output_folder = self.output_folder_entry.get()
        if not output_folder or not selected_filename:
            return

        file_path = os.path.join(output_folder, selected_filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.output_textbox.delete("1.0", "end")
            self.output_textbox.insert("1.0", content)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể đọc nội dung file:\n{e}")

if __name__ == "__main__":
    app = App()
    app.mainloop()