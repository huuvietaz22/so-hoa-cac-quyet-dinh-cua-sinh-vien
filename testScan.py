import customtkinter
from tkinter import filedialog, messagebox
import google.generativeai as genai
from PIL import Image
import os
import threading
import json
import re
import pyodbc 
from typing import Dict

# --- Cấu hình API và Database ---
# Vui lòng thay thế các thông tin bên dưới bằng thông tin của bạn
API_KEY = "AIzaSyAYgvAsQCU2zmRGo4xTYz_-2rxSzlHDIF4"
SQL_SERVER = 'WILLIAMS22-01\\DHV'
SQL_DATABASE = 'TextExtractorDB'
SQL_USER = 'Admin' 
SQL_PASSWORD = '123456' 

# Chuỗi kết nối đến SQL Server
CONNECTION_STRING = (
    f'DRIVER={{ODBC Driver 17 for SQL Server}};'
    f'SERVER={SQL_SERVER};'
    f'DATABASE={SQL_DATABASE};'
    f'UID={SQL_USER};'
    f'PWD={SQL_PASSWORD};'
)


# --- Hàm xử lý API đã được cải thiện (Đã cập nhật) ---
def get_image_text(image_path):
    """
    Sử dụng Google Gemini API để trích xuất văn bản từ hình ảnh.
    Trả về một đối tượng JSON string chứa các thông tin cụ thể.
    """
    try:
        if not API_KEY or "AIzaSy" not in API_KEY:
            raise ValueError("API Key không hợp lệ. Vui lòng kiểm tra lại.")

        genai.configure(api_key=API_KEY)
        # Sử dụng mô hình Gemini 1.5 Flash vì nó hiệu quả cho các tác vụ trích xuất.
        model = genai.GenerativeModel("gemini-1.5-flash")
        img = Image.open(image_path)

        # Cập nhật prompt để chỉ yêu cầu các thông tin cụ thể
        prompt = """Trích xuất các thông tin sau từ văn bản trong hình ảnh:
- Họ tên của sinh viên.
- Tên đầy đủ của quyết định (ví dụ: "QUYẾT ĐỊNH VỀ VIỆC CHUYỂN NGÀNH HỌC").
- Tên của người ký quyết định.
- Một danh sách các điều, khoản hoặc quyết định cụ thể được liệt kê trong văn bản.

Chỉ trả về một đối tượng JSON duy nhất với các khóa sau:
1. "ho_ten_sinh_vien": Họ tên của sinh viên, không dấu, không khoảng trắng, ví dụ: "Nguyen_Van_A".
2. "ten_quyet_dinh": Tên đầy đủ của quyết định, không dấu, không khoảng trắng, ví dụ: "QUYET_DINH_CHUYEN_NGANH_HOC".
3. "nguoi_ki": Tên của người ký quyết định, không dấu, không khoảng trắng, ví dụ: "Tran_Van_B".
4. "cac_quyet_dinh": Một mảng các chuỗi, mỗi chuỗi là một điều, khoản hoặc quyết định cụ thể (ví dụ: ["Điều 1: ...", "Điều 2: ..."]).

Ví dụ:
{
  "ho_ten_sinh_vien": "Nguyen_Van_A",
  "ten_quyet_dinh": "QUYET_DINH_TOT_NGHIEP",
  "nguoi_ki": "Tran_Van_B",
  "cac_quyet_dinh": ["Điều 1: ...", "Điều 2: ..."]
}"""

        response = model.generate_content([prompt, img])
        full_text = response.text.strip()
        
        # Cải thiện việc trích xuất JSON bằng regex
        match = re.search(r'\{.*\}', full_text, re.DOTALL)
        if match:
            json_string = match.group(0)
            return json_string
        else:
            # Nếu không tìm thấy JSON, có thể trả về một đối tượng rỗng hoặc lỗi
            raise ValueError("Phản hồi của API không chứa đối tượng JSON hợp lệ.")

    except Exception as e:
        print(f"Lỗi khi xử lý ảnh qua API: {e}")
        return None

# --- LỚP GIAO DIỆN ỨNG DỤNG ---
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # Cấu hình cửa sổ chính
        self.title("📑 Trình trích xuất & tìm kiếm văn bản từ ảnh")
        self.geometry("1200x800")
        customtkinter.set_appearance_mode("Dark")
        customtkinter.set_default_color_theme("green")

        # Khởi tạo kết nối CSDL và đảm bảo bảng tồn tại
        self.conn = self.get_db_connection()
        if self.conn:
            self.create_documents_table()
        else:
            messagebox.showerror("Lỗi khởi tạo", "Không thể kết nối CSDL khi khởi động. Ứng dụng sẽ bị hạn chế chức năng.")

        # --- CONTAINER CHÍNH CHO TOÀN BỘ GIAO DIỆN ---
        main_frame = customtkinter.CTkFrame(self, corner_radius=20, fg_color="#1a1a1a")
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(2, weight=1)
        
        # Tiêu đề và phụ đề
        title_label = customtkinter.CTkLabel(
            main_frame,
            text="TRÌNH TRÍCH XUẤT VĂN BẢN VÀ TÌM KIẾM",
            font=("Arial", 32, "bold"),
            text_color="#4CAF50" # xanh lá cây
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

        # Nút bắt đầu và thanh tiến trình
        self.start_button = customtkinter.CTkButton(
            left_frame,
            text="🚀 BẮT ĐẦU TRÍCH XUẤT",
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
        
        self.results_listbox_frame = customtkinter.CTkScrollableFrame(right_frame, corner_radius=10, fg_color="#2b2b2b")
        self.results_listbox_frame.grid(row=1, column=0, padx=10, pady=0, sticky="nsew")
        self.results_listbox_frame.grid_columnconfigure(0, weight=1)
        self.result_labels: Dict[int, customtkinter.CTkLabel] = {}
        self.selected_item_id = None
        self.result_labels_data: Dict[int, Dict] = {}

        # Hộp hiển thị nội dung
        content_label = customtkinter.CTkLabel(
            right_frame, text="📝 NỘI DUNG TÀI LIỆU:", font=("Arial", 14, "bold")
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
        
        # Tải danh sách file ban đầu từ DB
        if self.conn:
            self.load_initial_data()


    # --- Các hàm xử lý ---
    def get_db_connection(self):
        """Tạo và trả về kết nối đến cơ sở dữ liệu."""
        try:
            conn = pyodbc.connect(CONNECTION_STRING)
            return conn
        except pyodbc.Error as e:
            sql_state = e.args[0]
            if sql_state == '28000':
                messagebox.showerror("Lỗi kết nối", "Tên người dùng hoặc mật khẩu SQL Server không đúng.")
            elif sql_state == '08001':
                messagebox.showerror("Lỗi kết nối", "Không thể kết nối đến SQL Server. Vui lòng kiểm tra địa chỉ máy chủ.")
            else:
                messagebox.showerror("Lỗi kết nối", f"Đã xảy ra lỗi khi kết nối SQL Server:\n{e}")
            return None

    def create_documents_table(self):
        """Tạo bảng Documents nếu nó chưa tồn tại (Đã cập nhật)."""
        create_table_query = """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Documents]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[Documents](
                [id] [int] IDENTITY(1,1) NOT NULL,
                [ho_ten_sinh_vien] [nvarchar](255) NULL,
                [ten_quyet_dinh] [nvarchar](255) NULL,
                [nguoi_ki] [nvarchar](255) NULL,
                [cac_quyet_dinh] [nvarchar](max) NULL,
            PRIMARY KEY CLUSTERED 
            (
                [id] ASC
            )WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
            ) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
        END
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(create_table_query)
            self.conn.commit()
            print("Đã kiểm tra và tạo bảng Documents (nếu chưa tồn tại).")
        except pyodbc.Error as e:
            messagebox.showerror("Lỗi CSDL", f"Không thể tạo bảng Documents. Lỗi: {e}")


    def select_image_file(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file ảnh scan",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
        )
        if file_path:
            self.image_path_entry.delete(0, "end")
            self.image_path_entry.insert(0, file_path)
            self.status_label.configure(text=f"✅ Đã chọn file: {os.path.basename(file_path)}")

    def start_processing_thread(self):
        image_path = self.image_path_entry.get()

        if not image_path:
            messagebox.showerror("Lỗi", "Vui lòng chọn một file ảnh.")
            return

        self.status_label.configure(text="⏳ Đang xử lý, vui lòng đợi...")
        self.start_button.configure(state="disabled")
        self.progress_bar.start()

        def worker():
            result = get_image_text(image_path)
            if result:
                try:
                    data = json.loads(result)
                    
                    ho_ten_sinh_vien = data.get("ho_ten_sinh_vien", "Không xác định")
                    ten_quyet_dinh = data.get("ten_quyet_dinh", "Không xác định")
                    nguoi_ki = data.get("nguoi_ki", "Không xác định")
                    # Chuyển đổi mảng cac_quyet_dinh thành JSON string
                    cac_quyet_dinh_json = json.dumps(data.get("cac_quyet_dinh", []))
                    
                    # Tạo nội dung hiển thị tóm tắt cho UI
                    summary_content = f"Họ tên sinh viên: {ho_ten_sinh_vien}\n" \
                                      f"Tên quyết định: {ten_quyet_dinh}\n" \
                                      f"Người ký: {nguoi_ki}\n\n" \
                                      f"Các quyết định:\n" + "\n".join(data.get("cac_quyet_dinh", []))

                    # LƯU DỮ LIỆU VÀO CƠ SỞ DỮ LIỆU (Đã cập nhật)
                    conn = self.get_db_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            insert_query = """
                                INSERT INTO Documents (ho_ten_sinh_vien, ten_quyet_dinh, nguoi_ki, cac_quyet_dinh)
                                VALUES (?, ?, ?, ?)
                            """
                            cursor.execute(insert_query, (ho_ten_sinh_vien, ten_quyet_dinh, nguoi_ki, cac_quyet_dinh_json))
                            conn.commit()
                            self.after(0, lambda: self.finish_processing("Đã lưu vào CSDL", summary_content))
                        except pyodbc.Error as e:
                            self.after(0, lambda: self.handle_error(f"Lỗi khi lưu vào CSDL: {e}"))
                        finally:
                            conn.close()
                    else:
                        self.after(0, lambda: self.handle_error("Lỗi: Không thể kết nối cơ sở dữ liệu."))
                except json.JSONDecodeError as e:
                    self.after(0, lambda: self.handle_error(f"Lỗi: Phản hồi API không phải là JSON hợp lệ. Chi tiết: {e}"))
            else:
                self.after(0, lambda: self.handle_error("Lỗi: Không thể trích xuất văn bản từ ảnh. Phản hồi API không chứa JSON."))

        threading.Thread(target=worker).start()

    def finish_processing(self, save_message, content):
        self.progress_bar.stop()
        self.output_textbox.delete("1.0", "end")
        self.output_textbox.insert("1.0", content)
        self.status_label.configure(text=f"✅ Trích xuất thành công! {save_message}")
        self.start_button.configure(state="normal")
        messagebox.showinfo("Thành công", f"Đã trích xuất và lưu văn bản thành công!")
        self.load_initial_data() # Tải lại danh sách file từ DB

    def handle_error(self, message):
        self.progress_bar.stop()
        self.status_label.configure(text=f"❌ {message}")
        self.start_button.configure(state="normal")
        messagebox.showerror("Lỗi", message)

    def load_initial_data(self):
        """Tải toàn bộ danh sách các file đã lưu trong CSDL."""
        for widget in self.results_listbox_frame.winfo_children():
            widget.destroy()

        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, ten_quyet_dinh, ho_ten_sinh_vien FROM Documents ORDER BY id DESC")
            rows = cursor.fetchall()
            row_count = 0
            for row in rows:
                doc_id, ten_quyet_dinh, ho_ten_sinh_vien = row
                display_name = f"{ten_quyet_dinh} - {ho_ten_sinh_vien} (ID: {doc_id})"
                
                label = customtkinter.CTkLabel(
                    self.results_listbox_frame,
                    text=display_name,
                    fg_color="#343638", 
                    corner_radius=6,
                    pady=5,
                    anchor="w",
                    font=("Arial", 12)
                )
                label.bind("<Button-1>", lambda event, doc_id=doc_id: self.show_file_content(doc_id))
                label.pack(fill="x", padx=5, pady=2)
                row_count += 1
                
            self.status_label.configure(text=f"Đã tải {row_count} tài liệu từ CSDL.")
        except pyodbc.Error as e:
            print(f"Lỗi khi tải dữ liệu từ CSDL: {e}")
            self.status_label.configure(text=f"❌ Lỗi khi tải dữ liệu từ CSDL.")


    def dynamic_search_files(self, event=None):
        """Lọc danh sách hiển thị khi người dùng gõ phím (Đã cập nhật)."""
        search_term = self.search_entry.get().strip().lower()
        
        for widget in self.results_listbox_frame.winfo_children():
            widget.destroy()
            
        found_files_count = 0

        try:
            cursor = self.conn.cursor()
            # Tìm kiếm theo tên quyết định, tên sinh viên hoặc ID
            search_query = """
                SELECT id, ten_quyet_dinh, ho_ten_sinh_vien FROM Documents
                WHERE LOWER(ten_quyet_dinh) LIKE ? OR LOWER(ho_ten_sinh_vien) LIKE ? OR CAST(id AS NVARCHAR) LIKE ?
            """
            cursor.execute(search_query, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            rows = cursor.fetchall()
            for row in rows:
                doc_id, ten_quyet_dinh, ho_ten_sinh_vien = row
                display_name = f"{ten_quyet_dinh} - {ho_ten_sinh_vien} (ID: {doc_id})"
                
                label = customtkinter.CTkLabel(
                    self.results_listbox_frame,
                    text=display_name,
                    fg_color="#343638",
                    corner_radius=6,
                    pady=5,
                    anchor="w",
                    font=("Arial", 12)
                )
                label.bind("<Button-1>", lambda event, doc_id=doc_id: self.show_file_content(doc_id))
                label.pack(fill="x", padx=5, pady=2)
                found_files_count += 1
            self.status_label.configure(text=f"✅ Tìm thấy {found_files_count} kết quả.")
        except pyodbc.Error as e:
            print(f"Lỗi khi tìm kiếm dữ liệu: {e}")
            self.status_label.configure(text=f"❌ Lỗi khi tìm kiếm dữ liệu từ CSDL.")

    def search_files(self):
        """Chức năng tìm kiếm nội dung đã bị loại bỏ vì cột 'content' không còn tồn tại."""
        self.dynamic_search_files()
    
    def show_file_content(self, doc_id):
        """Hiển thị nội dung của tài liệu được chọn từ CSDL (Đã cập nhật)."""
        try:
            cursor = self.conn.cursor()
            # Truy vấn 4 trường dữ liệu mới
            query = "SELECT ho_ten_sinh_vien, ten_quyet_dinh, nguoi_ki, cac_quyet_dinh FROM Documents WHERE id = ?"
            cursor.execute(query, (doc_id,))
            row = cursor.fetchone()
            if row:
                ho_ten_sinh_vien, ten_quyet_dinh, nguoi_ki, cac_quyet_dinh_json = row
                # Chuyển đổi JSON string thành mảng Python
                cac_quyet_dinh = json.loads(cac_quyet_dinh_json)
                
                # Tạo nội dung hiển thị tóm tắt
                summary_content = f"Họ tên sinh viên: {ho_ten_sinh_vien}\n" \
                                  f"Tên quyết định: {ten_quyet_dinh}\n" \
                                  f"Người ký: {nguoi_ki}\n\n" \
                                  f"Các quyết định:\n" + "\n".join(cac_quyet_dinh)
                
                self.output_textbox.delete("1.0", "end")
                self.output_textbox.insert("1.0", summary_content)
            else:
                messagebox.showerror("Lỗi", "Không tìm thấy tài liệu trong CSDL.")
        except pyodbc.Error as e:
            messagebox.showerror("Lỗi", f"Không thể đọc nội dung tài liệu:\n{e}")
        except json.JSONDecodeError:
            messagebox.showerror("Lỗi", "Không thể phân tích dữ liệu 'cac_quyet_dinh'. Dữ liệu có thể bị hỏng.")


if __name__ == "__main__":
    app = App()
    app.mainloop()
