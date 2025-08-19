import customtkinter
from tkinter import filedialog, messagebox, Toplevel, Label
import google.generativeai as genai
from PIL import Image, ImageTk, ImageDraw
import os
import threading
import json
import re
import pyodbc
from typing import Dict, Optional, Tuple

# --- Cấu hình API và Database ---
# Vui lòng thay thế các thông tin bên dưới bằng thông tin của bạn
API_KEY = "AIzaSyAYgvAsQCU2zmRGo4xTYz_-2rxSzlHDIF4"
SQL_SERVER = "WILLIAMS22-01\\DHV"
SQL_DATABASE = "TextExtractorDB"
SQL_USER = "Admin"
SQL_PASSWORD = "123456"

# Chuỗi kết nối đến SQL Server
CONNECTION_STRING = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DATABASE};"
    f"UID={SQL_USER};"
    f"PWD={SQL_PASSWORD};"
)

# Thư mục để lưu trữ các file ảnh chữ ký và ảnh gốc
ORIGINAL_IMAGES_DIR = "originals"
if not os.path.exists(ORIGINAL_IMAGES_DIR):
    os.makedirs(ORIGINAL_IMAGES_DIR)


# --- Hàm xử lý API ---
def get_image_data(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Sử dụng Google Gemini API để trích xuất văn bản, thông tin chữ ký và tọa độ.
    Trả về một đối tượng JSON string và đường dẫn ảnh gốc đã lưu.
    """
    try:
        if not API_KEY or "AIzaSy" not in API_KEY:
            raise ValueError("API Key không hợp lệ. Vui lòng kiểm tra lại.")

        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        img = Image.open(image_path)

        # Lưu ảnh gốc vào thư mục để sử dụng sau này
        original_file_path = os.path.join(
            ORIGINAL_IMAGES_DIR, os.path.basename(image_path)
        )
        img.save(original_file_path)

        prompt = """Trích xuất các thông tin sau từ văn bản trong hình ảnh:
- Họ tên của sinh viên.
- Tên đầy đủ của quyết định.
- Tên của người ký quyết định.
- Một danh sách các điều, khoản hoặc quyết định cụ thể.
- Tọa độ khung hình vuông của chữ ký, bắt buộc phải trả về một mảng 4 số nguyên. Nếu không tìm thấy, hãy trả về [0, 0, 0, 0].

**Quy tắc và định dạng đầu ra:**
1. Trả về một đối tượng JSON duy nhất.
2. Tất cả các khóa phải có giá trị. Nếu không tìm thấy, hãy trả về chuỗi "Không xác định".
3. Đặc biệt, khóa "toa_do_chu_ki" phải là một mảng 4 số nguyên [x_min, y_min, x_max, y_max]. Nếu không thể xác định, hãy trả về [0, 0, 0, 0].
4. Vị trí của chữ ký trong ảnh sẽ ở bên trên tên người ký.

Chỉ trả về một đối tượng JSON duy nhất với các khóa sau:
"ho_ten_sinh_vien"
"ten_quyet_dinh"
"nguoi_ki"
"cac_quyet_dinh"
"toa_do_chu_ki"

Ví dụ:
{
  "ho_ten_sinh_vien": "Nguyen_Van_A",
  "ten_quyet_dinh": "QUYET_DINH_TOT_NGHIEP",
  "nguoi_ki": "Tran_Van_B",
  "cac_quyet_dinh": ["Điều 1: ...", "Điều 2: ..."],
  "toa_do_chu_ki": [850, 600, 1000, 750]
}"""

        response = model.generate_content([prompt, img])
        full_text = response.text.strip()

        print(f"Phản hồi từ API Gemini:\n{full_text}")  # In phản hồi để gỡ lỗi

        match = re.search(r"\{.*\}", full_text, re.DOTALL)
        if match:
            json_string = match.group(0)
            return json_string, original_file_path
        else:
            raise ValueError("Phản hồi của API không chứa đối tượng JSON hợp lệ.")

    except Exception as e:
        print(f"Lỗi khi xử lý ảnh qua API: {e}")
        return None, None


# --- LỚP GIAO DIỆN ỨNG DỤNG ---
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # Cấu hình cửa sổ chính
        self.title("📑 Trình trích xuất & tìm kiếm văn bản từ ảnh")
        self.geometry("1200x800")
        customtkinter.set_appearance_mode("Dark")
        customtkinter.set_default_color_theme("green")

        self.conn = self.get_db_connection()
        if self.conn:
            self.create_documents_table()
        else:
            messagebox.showerror(
                "Lỗi khởi tạo",
                "Không thể kết nối CSDL khi khởi động. Ứng dụng sẽ bị hạn chế chức năng.",
            )

        # --- CONTAINER CHÍNH CHO TOÀN BỘ GIAO DIỆN ---
        main_frame = customtkinter.CTkFrame(self, corner_radius=20, fg_color="#1a1a1a")
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(2, weight=1)

        title_label = customtkinter.CTkLabel(
            main_frame,
            text="TRÌNH TRÍCH XUẤT VĂN BẢN VÀ TÌM KIẾM",
            font=("Arial", 32, "bold"),
            text_color="#4CAF50",
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(20, 5), sticky="n")

        subtitle_label = customtkinter.CTkLabel(
            main_frame,
            text="Sử dụng AI để nhận diện và tìm kiếm nội dung trong hình ảnh",
            font=("Arial", 16),
            text_color="#a0a0a0",
        )
        subtitle_label.grid(row=1, column=0, columnspan=2, pady=(0, 20), sticky="n")

        # --- KHUNG BÊN TRÁI: NHẬP LIỆU & TÌM KIẾM ---
        left_frame = customtkinter.CTkFrame(main_frame, corner_radius=15)
        left_frame.grid(row=2, column=0, padx=15, pady=15, sticky="nsew")
        left_frame.grid_columnconfigure(0, weight=1)

        extraction_frame = customtkinter.CTkFrame(left_frame, corner_radius=10)
        extraction_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        extraction_frame.grid_columnconfigure(1, weight=1)

        image_label = customtkinter.CTkLabel(
            extraction_frame, text="🖼️ Ảnh cần trích xuất:", font=("Arial", 14, "bold")
        )
        image_label.grid(row=0, column=0, padx=15, pady=10, sticky="w")
        self.image_path_entry = customtkinter.CTkEntry(
            extraction_frame, placeholder_text="Chưa chọn file ảnh..."
        )
        self.image_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        browse_image_button = customtkinter.CTkButton(
            extraction_frame, text="Duyệt...", command=self.select_image_file, width=80
        )
        browse_image_button.grid(row=0, column=2, padx=15, pady=10)

        self.start_button = customtkinter.CTkButton(
            left_frame,
            text="🚀 BẮT ĐẦU TRÍCH XUẤT",
            font=("Arial", 18, "bold"),
            height=55,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            command=self.start_processing_thread,
            corner_radius=12,
        )
        self.start_button.grid(row=1, column=0, padx=10, pady=(10, 5), sticky="ew")

        self.progress_bar = customtkinter.CTkProgressBar(
            left_frame, mode="indeterminate", height=10
        )
        self.progress_bar.grid(row=2, column=0, padx=10, pady=(0, 20), sticky="ew")
        self.progress_bar.stop()
        self.progress_bar.set(0)

        search_frame = customtkinter.CTkFrame(left_frame, corner_radius=10)
        search_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = customtkinter.CTkEntry(
            search_frame,
            placeholder_text="🔍 Nhập từ khóa để tìm kiếm...",
            font=("Arial", 14),
        )
        self.search_entry.grid(row=0, column=0, padx=(15, 5), pady=15, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self.dynamic_search_files)

        search_button = customtkinter.CTkButton(
            search_frame, text="Tìm kiếm", command=self.search_files, width=100
        )
        search_button.grid(row=0, column=1, padx=(5, 15), pady=15)

        # --- KHUNG BÊN PHẢI: KẾT QUẢ & NỘI DUNG ---
        right_frame = customtkinter.CTkFrame(main_frame, corner_radius=15)
        right_frame.grid(row=2, column=1, padx=15, pady=15, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_rowconfigure(2, weight=0)
        right_frame.grid_rowconfigure(3, weight=1)
        right_frame.grid_rowconfigure(4, weight=0)
        right_frame.grid_rowconfigure(5, weight=3)

        results_label = customtkinter.CTkLabel(
            right_frame, text="📑 KẾT QUẢ TÌM KIẾM:", font=("Arial", 14, "bold")
        )
        results_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.results_listbox_frame = customtkinter.CTkScrollableFrame(
            right_frame, corner_radius=10, fg_color="#2b2b2b"
        )
        self.results_listbox_frame.grid(row=1, column=0, padx=10, pady=0, sticky="nsew")
        self.results_listbox_frame.grid_columnconfigure(0, weight=1)

        self.open_image_button = customtkinter.CTkButton(
            right_frame,
            text="Xem ảnh gốc với chữ ký đã nhận dạng",
            font=("Arial", 14),
            command=self.show_original_image_window,
            state="disabled",
        )
        self.open_image_button.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="ew")

        content_label = customtkinter.CTkLabel(
            right_frame, text="📝 NỘI DUNG TÀI LIỆU:", font=("Arial", 14, "bold")
        )
        content_label.grid(row=3, column=0, padx=10, pady=(15, 5), sticky="w")

        self.output_textbox = customtkinter.CTkTextbox(
            right_frame, font=("Consolas", 12), wrap="word"
        )
        self.output_textbox.grid(
            row=4, column=0, rowspan=2, padx=10, pady=(0, 10), sticky="nsew"
        )

        # Thanh trạng thái
        self.status_label = customtkinter.CTkLabel(
            self,
            text="✅ Sẵn sàng",
            fg_color="transparent",
            anchor="w",
            font=("Arial", 12),
        )
        self.status_label.pack(side="bottom", fill="x", padx=40, pady=10)

        if self.conn:
            self.load_initial_data()
            self.current_selected_doc_id = None

    # --- Các hàm xử lý ---
    def get_db_connection(self):
        try:
            conn = pyodbc.connect(CONNECTION_STRING)
            return conn
        except pyodbc.Error as e:
            sql_state = e.args[0]
            if sql_state == "28000":
                messagebox.showerror(
                    "Lỗi kết nối", "Tên người dùng hoặc mật khẩu SQL Server không đúng."
                )
            elif sql_state == "08001":
                messagebox.showerror(
                    "Lỗi kết nối",
                    "Không thể kết nối đến SQL Server. Vui lòng kiểm tra địa chỉ máy chủ.",
                )
            else:
                messagebox.showerror(
                    "Lỗi kết nối", f"Đã xảy ra lỗi khi kết nối SQL Server:\n{e}"
                )
            return None

    def create_documents_table(self):
        create_table_query = """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[Documents]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[Documents](
                [id] [int] IDENTITY(1,1) NOT NULL,
                [ho_ten_sinh_vien] [nvarchar](255) NULL,
                [ten_quyet_dinh] [nvarchar](255) NULL,
                [nguoi_ki] [nvarchar](255) NULL,
                [cac_quyet_dinh] [nvarchar](max) NULL,
                [duong_dan_anh_goc] [nvarchar](max) NULL, 
                [toa_do_chu_ki] [nvarchar](max) NULL, 
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
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if file_path:
            self.image_path_entry.delete(0, "end")
            self.image_path_entry.insert(0, file_path)
            self.status_label.configure(
                text=f"✅ Đã chọn file: {os.path.basename(file_path)}"
            )

    def start_processing_thread(self):
        image_path = self.image_path_entry.get()
        if not image_path:
            messagebox.showerror("Lỗi", "Vui lòng chọn một file ảnh.")
            return

        self.status_label.configure(text="⏳ Đang xử lý, vui lòng đợi...")
        self.start_button.configure(state="disabled")
        self.progress_bar.start()

        def worker():
            result, original_file_path = get_image_data(image_path)
            if result:
                try:
                    data = json.loads(result)
                    ho_ten_sinh_vien = data.get("ho_ten_sinh_vien", "Không xác định")
                    ten_quyet_dinh = data.get("ten_quyet_dinh", "Không xác định")
                    nguoi_ki = data.get("nguoi_ki", "Không xác định")
                    cac_quyet_dinh_json = json.dumps(data.get("cac_quyet_dinh", []))

                    toa_do_chu_ki = data.get("toa_do_chu_ki")
                    toa_do_chu_ki_json = (
                        json.dumps(toa_do_chu_ki) if toa_do_chu_ki else None
                    )

                    summary_content = (
                        f"Họ tên sinh viên: {ho_ten_sinh_vien}\n"
                        f"Tên quyết định: {ten_quyet_dinh}\n"
                        f"Người ký: {nguoi_ki}\n\n"
                        f"Các quyết định:\n" + "\n".join(data.get("cac_quyet_dinh", []))
                    )

                    conn = self.get_db_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            insert_query = """
                                INSERT INTO Documents (ho_ten_sinh_vien, ten_quyet_dinh, nguoi_ki, cac_quyet_dinh, duong_dan_anh_goc, toa_do_chu_ki)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """
                            cursor.execute(
                                insert_query,
                                (
                                    ho_ten_sinh_vien,
                                    ten_quyet_dinh,
                                    nguoi_ki,
                                    cac_quyet_dinh_json,
                                    original_file_path,
                                    toa_do_chu_ki_json,
                                ),
                            )
                            conn.commit()
                            self.after(
                                0,
                                lambda: self.finish_processing(
                                    "Đã lưu vào CSDL", summary_content
                                ),
                            )
                        except pyodbc.Error as e:
                            self.after(
                                0,
                                lambda: self.handle_error(f"Lỗi khi lưu vào CSDL: {e}"),
                            )
                        finally:
                            conn.close()
                    else:
                        self.after(
                            0,
                            lambda: self.handle_error(
                                "Lỗi: Không thể kết nối cơ sở dữ liệu."
                            ),
                        )
                except (json.JSONDecodeError, KeyError) as e:
                    self.after(
                        0,
                        lambda: self.handle_error(
                            f"Lỗi: Phản hồi API không phải là JSON hợp lệ hoặc thiếu khóa. Chi tiết: {e}"
                        ),
                    )
            else:
                self.after(
                    0,
                    lambda: self.handle_error(
                        "Lỗi: Không thể trích xuất văn bản từ ảnh. Phản hồi API không chứa JSON."
                    ),
                )

        threading.Thread(target=worker).start()

    def finish_processing(self, save_message, content):
        self.progress_bar.stop()
        self.output_textbox.delete("1.0", "end")
        self.output_textbox.insert("1.0", content)
        self.status_label.configure(text=f"✅ Trích xuất thành công! {save_message}")
        self.start_button.configure(state="normal")
        messagebox.showinfo("Thành công", f"Đã trích xuất và lưu văn bản thành công!")
        self.load_initial_data()

    def handle_error(self, message):
        self.progress_bar.stop()
        self.status_label.configure(text=f"❌ {message}")
        self.start_button.configure(state="normal")
        messagebox.showerror("Lỗi", message)

    def load_initial_data(self):
        for widget in self.results_listbox_frame.winfo_children():
            widget.destroy()

        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id, ten_quyet_dinh, ho_ten_sinh_vien FROM Documents ORDER BY id DESC"
            )
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
                    font=("Arial", 12),
                )
                label.bind(
                    "<Button-1>",
                    lambda event, doc_id=doc_id: self.show_file_content(doc_id),
                )
                label.pack(fill="x", padx=5, pady=2)
                row_count += 1
            self.status_label.configure(text=f"Đã tải {row_count} tài liệu từ CSDL.")
        except pyodbc.Error as e:
            print(f"Lỗi khi tải dữ liệu từ CSDL: {e}")
            self.status_label.configure(text=f"❌ Lỗi khi tải dữ liệu từ CSDL.")

    def dynamic_search_files(self, event=None):
        search_term = self.search_entry.get().strip().lower()

        for widget in self.results_listbox_frame.winfo_children():
            widget.destroy()

        found_files_count = 0
        try:
            cursor = self.conn.cursor()
            search_query = """
                SELECT id, ten_quyet_dinh, ho_ten_sinh_vien FROM Documents
                WHERE LOWER(ten_quyet_dinh) LIKE ? OR LOWER(ho_ten_sinh_vien) LIKE ? OR CAST(id AS NVARCHAR) LIKE ?
            """
            cursor.execute(
                search_query,
                (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"),
            )
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
                    font=("Arial", 12),
                )
                label.bind(
                    "<Button-1>",
                    lambda event, doc_id=doc_id: self.show_file_content(doc_id),
                )
                label.pack(fill="x", padx=5, pady=2)
                found_files_count += 1
            self.status_label.configure(
                text=f"✅ Tìm thấy {found_files_count} kết quả."
            )
        except pyodbc.Error as e:
            print(f"Lỗi khi tìm kiếm dữ liệu: {e}")
            self.status_label.configure(text=f"❌ Lỗi khi tìm kiếm dữ liệu từ CSDL.")

    def search_files(self):
        self.dynamic_search_files()

    def show_file_content(self, doc_id):
        self.output_textbox.delete("1.0", "end")
        self.open_image_button.configure(state="disabled")
        self.current_selected_doc_id = None

        try:
            cursor = self.conn.cursor()
            query = "SELECT ho_ten_sinh_vien, ten_quyet_dinh, nguoi_ki, cac_quyet_dinh, duong_dan_anh_goc, toa_do_chu_ki FROM Documents WHERE id = ?"
            cursor.execute(query, (doc_id,))
            row = cursor.fetchone()
            if row:
                (
                    ho_ten_sinh_vien,
                    ten_quyet_dinh,
                    nguoi_ki,
                    cac_quyet_dinh_json,
                    duong_dan_anh_goc,
                    toa_do_chu_ki_json,
                ) = row
                cac_quyet_dinh = json.loads(cac_quyet_dinh_json)

                summary_content = (
                    f"Họ tên sinh viên: {ho_ten_sinh_vien}\n"
                    f"Tên quyết định: {ten_quyet_dinh}\n"
                    f"Người ký: {nguoi_ki}\n\n"
                    f"Các quyết định:\n" + "\n".join(cac_quyet_dinh)
                )

                self.output_textbox.insert("1.0", summary_content)
                self.current_selected_doc_id = doc_id
                self.open_image_button.configure(state="normal")
            else:
                messagebox.showerror("Lỗi", "Không tìm thấy tài liệu trong CSDL.")
        except pyodbc.Error as e:
            messagebox.showerror("Lỗi", f"Không thể đọc nội dung tài liệu:\n{e}")
        except json.JSONDecodeError:
            messagebox.showerror(
                "Lỗi", "Không thể phân tích dữ liệu. Dữ liệu có thể bị hỏng."
            )

    def show_original_image_window(self):
        if not self.current_selected_doc_id:
            return

        try:
            cursor = self.conn.cursor()
            query = (
                "SELECT duong_dan_anh_goc, toa_do_chu_ki FROM Documents WHERE id = ?"
            )
            cursor.execute(query, (self.current_selected_doc_id,))
            row = cursor.fetchone()

            if row:
                image_path, coords_json = row
                if not image_path or not os.path.exists(image_path):
                    messagebox.showerror("Lỗi", "Không tìm thấy file ảnh gốc.")
                    return

                original_image = Image.open(image_path)

                # Vẽ bounding box nếu có tọa độ
                coords = []
                if coords_json:
                    coords = json.loads(coords_json)
                    if (
                        coords
                        and len(coords) == 4
                        and all(isinstance(c, (int, float)) for c in coords)
                    ):
                        draw = ImageDraw.Draw(original_image)
                        draw.rectangle(coords, outline="red", width=5)

                # Hiển thị ảnh trong cửa sổ mới
                top_level = Toplevel(self)
                top_level.title("Ảnh gốc với chữ ký đã nhận dạng")

                original_width, original_height = original_image.size
                screen_width = top_level.winfo_screenwidth()
                screen_height = top_level.winfo_screenheight()

                resize_ratio = min(
                    screen_width / original_width, screen_height / original_height
                )
                new_size = (
                    int(original_width * resize_ratio * 0.9),
                    int(original_height * resize_ratio * 0.9),
                )

                resized_image = original_image.resize(new_size, Image.LANCZOS)

                ctk_image = ImageTk.PhotoImage(resized_image)

                image_label = Label(top_level, image=ctk_image)
                image_label.image = ctk_image
                image_label.pack(padx=10, pady=10)

        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể hiển thị ảnh gốc: {e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
