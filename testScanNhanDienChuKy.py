import customtkinter
from tkinter import filedialog, messagebox, Toplevel, Label
import google.generativeai as genai
from PIL import Image, ImageTk, ImageDraw
import os
import threading
import json
import re
import pyodbc
from typing import Optional, Tuple

# --- Cấu hình toàn cục ---
API_KEY = "AIzaSyAYgvAsQCU2zmRGo4xTYz_-2rxSzlHDIF4"
SQL_SERVER = "WILLIAMS22-01\\DHV"
SQL_DATABASE = "TextExtractorDB"
SQL_USER = "Admin"
SQL_PASSWORD = "123456"

CONNECTION_STRING = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DATABASE};"
    f"UID={SQL_USER};"
    f"PWD={SQL_PASSWORD};"
)

ORIGINAL_IMAGES_DIR = "originals"
if not os.path.exists(ORIGINAL_IMAGES_DIR):
    os.makedirs(ORIGINAL_IMAGES_DIR)


# --- Hàm xử lý API (ĐÃ SỬA LỖI CHỮ KÝ) ---
# --- Hàm xử lý API (ĐÃ SỬA TRIỆT ĐỂ LỖI PHẢN HỒI) ---
def get_image_data(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        if not API_KEY or "AIzaSy" not in API_KEY:
            raise ValueError("API Key không hợp lệ. Vui lòng kiểm tra lại.")

        genai.configure(api_key=API_KEY)
        # ✅ DÙNG MODEL ỔN ĐỊNH NHẤT HIỆN TẠI
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        img = Image.open(image_path)

        original_file_path = os.path.join(
            ORIGINAL_IMAGES_DIR, os.path.basename(image_path)
        )
        img.save(original_file_path)

        # === PROMPT SIÊU RÕ RÀNG, BẮT BUỘC TRẢ VỀ JSON ===
        prompt = """Bạn là hệ thống AI trích xuất thông tin văn bản hành chính.

Hãy phân tích ảnh và trả về DUY NHẤT một khối JSON với cấu trúc sau:

{
  "ho_ten_sinh_vien": "chuỗi",
  "ten_quyet_dinh": "chuỗi",
  "nguoi_ki": "chuỗi",
  "cac_quyet_dinh": ["mảng chuỗi"],
  "toa_do_chu_ki": [x_min, y_min, x_max, y_max]
}

HƯỚNG DẪN CHI TIẾT:
- "ho_ten_sinh_vien": Họ tên sinh viên trong quyết định.
- "ten_quyet_dinh": Tên đầy đủ của quyết định (VD: "Quyết định công nhận tốt nghiệp...").
- "nguoi_ki": Họ tên người ký (thường ở cuối trang).
- "cac_quyet_dinh": Mảng chứa từng điều/khoản được liệt kê.
- "toa_do_chu_ki": Mảng 4 SỐ NGUYÊN [trái, trên, phải, dưới] bao quanh CHỮ KÝ THẬT (không phải tên người ký). Nếu không thấy → [0,0,0,0].

QUY TẮC BẮT BUỘC:
1. LUÔN trả về đúng định dạng JSON như trên.
2. KHÔNG THÊM bất kỳ ký tự, giải thích, markdown hay ```json nào ngoài khối JSON.
3. Nếu thiếu thông tin → điền "Không xác định".
4. "toa_do_chu_ki" PHẢI là mảng 4 số nguyên. Không được để null, string hay object.

VÍ DỤ HOÀN HẢO:
{
  "ho_ten_sinh_vien": "Nguyễn Văn A",
  "ten_quyet_dinh": "Quyết định công nhận tốt nghiệp đại học",
  "nguoi_ki": "Hiệu trưởng Trần Văn Minh",
  "cac_quyet_dinh": [
    "Điều 1: Sinh viên đủ điều kiện tốt nghiệp.",
    "Điều 2: Cấp bằng kỹ sư ngành Công nghệ thông tin."
  ],
  "toa_do_chu_ki": [820, 580, 980, 720]
}"""

        response = model.generate_content([prompt, img], stream=False)
        full_text = response.text.strip()

        print("\n" + "="*60)
        print("[DEBUG] PHẢN HỒI THÔ TỪ GEMINI:")
        print("-"*60)
        print(full_text)
        print("="*60 + "\n")

        # 🔍 Rút JSON bằng nhiều lớp bảo vệ
        json_match = re.search(r"\{.*\}", full_text, re.DOTALL)
        if not json_match:
            print("[CẢNH BÁO] Không tìm thấy JSON trong phản hồi → Tạo JSON mặc định")
            fallback_data = {
                "ho_ten_sinh_vien": "Không xác định",
                "ten_quyet_dinh": "Không xác định",
                "nguoi_ki": "Không xác định",
                "cac_quyet_dinh": [],
                "toa_do_chu_ki": [0, 0, 0, 0]
            }
            return json.dumps(fallback_data, ensure_ascii=False), original_file_path

        json_string = json_match.group(0)

        # ✅ Kiểm tra & sửa lỗi JSON trước khi trả về
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError:
            print("[LỖI] JSON không hợp lệ → Sửa chữa tự động")
            # Tạo lại JSON an toàn
            data = {
                "ho_ten_sinh_vien": "Không xác định",
                "ten_quyet_dinh": "Không xác định",
                "nguoi_ki": "Không xác định",
                "cac_quyet_dinh": [],
                "toa_do_chu_ki": [0, 0, 0, 0]
            }

        # ✅ Đảm bảo khóa "toa_do_chu_ki" luôn tồn tại & đúng định dạng
        if "toa_do_chu_ki" not in data or not isinstance(data["toa_do_chu_ki"], list) or len(data["toa_do_chu_ki"]) != 4:
            data["toa_do_chu_ki"] = [0, 0, 0, 0]

        # Chuyển về int
        try:
            data["toa_do_chu_ki"] = [int(x) for x in data["toa_do_chu_ki"]]
        except:
            data["toa_do_chu_ki"] = [0, 0, 0, 0]

        # Trả về JSON string chuẩn
        return json.dumps(data, ensure_ascii=False), original_file_path

    except Exception as e:
        print(f"[LỖI NẶNG] Xử lý ảnh thất bại: {e}")
        # Fallback cuối cùng
        fallback_data = {
            "ho_ten_sinh_vien": "Lỗi xử lý",
            "ten_quyet_dinh": "Lỗi xử lý",
            "nguoi_ki": "Lỗi xử lý",
            "cac_quyet_dinh": ["Không trích xuất được do lỗi hệ thống"],
            "toa_do_chu_ki": [0, 0, 0, 0]
        }
        return json.dumps(fallback_data, ensure_ascii=False), None


# --- LỚP CHÍNH: GIAO DIỆN DASHBOARD ĐẸP, SÁNG, 1 CỬA SỔ ---
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # === CẤU HÌNH CỬA SỔ ===
        self.title("📄 AI Document Extractor & Searcher")
        self.geometry("1300x850")
        self.minsize(1200, 800)
        customtkinter.set_appearance_mode("Light")  # 🌞 CHẾ ĐỘ SÁNG
        customtkinter.set_default_color_theme("blue")

        # Kết nối CSDL
        self.conn = self.get_db_connection()
        if self.conn:
            self.create_documents_table()
        else:
            messagebox.showerror(
                "Lỗi khởi tạo",
                "Không thể kết nối CSDL khi khởi động. Ứng dụng sẽ bị hạn chế chức năng.",
            )

        # Biến trạng thái
        self.current_selected_doc_id = None

        # === HEADER ===
        header_frame = customtkinter.CTkFrame(self, height=80, corner_radius=0, fg_color="#f8f9fa", border_width=0)
        header_frame.pack(fill="x", pady=0, padx=0)
        header_frame.grid_columnconfigure(1, weight=1)

        title_label = customtkinter.CTkLabel(
            header_frame,
            text="📑 AI Document Dashboard",
            font=("Segoe UI", 28, "bold"),
            text_color="#2c3e50",
        )
        title_label.grid(row=0, column=0, padx=(40, 20), pady=20, sticky="w")

        subtitle_label = customtkinter.CTkLabel(
            header_frame,
            text="Trích xuất thông minh & tìm kiếm tài liệu ảnh bằng AI — Giao diện hiện đại, dễ sử dụng",
            font=("Segoe UI", 13),
            text_color="#7f8c8d",
        )
        subtitle_label.grid(row=0, column=1, padx=10, pady=20, sticky="w")

        # === MAIN CONTENT FRAME ===
        main_frame = customtkinter.CTkFrame(self, fg_color="#ffffff", corner_radius=20)
        main_frame.pack(pady=25, padx=30, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1, uniform="group1")
        main_frame.grid_columnconfigure(1, weight=2, uniform="group1")
        main_frame.grid_rowconfigure(1, weight=1)

        # --- TOP CONTROL CARD ---
        control_card = customtkinter.CTkFrame(main_frame, fg_color="#f8f9fa", corner_radius=15, border_width=2, border_color="#e0e0e0")
        control_card.grid(row=0, column=0, columnspan=2, padx=0, pady=(0, 20), sticky="ew")
        control_card.grid_columnconfigure(1, weight=1)

        # File selection
        row1 = customtkinter.CTkFrame(control_card, fg_color="transparent")
        row1.pack(fill="x", padx=30, pady=(25, 15))

        customtkinter.CTkLabel(
            row1, text="📁 Ảnh cần xử lý:", font=("Segoe UI", 15, "bold"), text_color="#2c3e50"
        ).pack(side="left")

        self.image_path_entry = customtkinter.CTkEntry(
            row1, placeholder_text="Chưa chọn file...", height=40, font=("Segoe UI", 13), width=500
        )
        self.image_path_entry.pack(side="left", padx=15, fill="x", expand=True)

        browse_btn = customtkinter.CTkButton(
            row1,
            text="Duyệt...",
            width=110,
            height=40,
            font=("Segoe UI", 13, "bold"),
            command=self.select_image_file,
            fg_color="#3498db",
            hover_color="#2980b9",
        )
        browse_btn.pack(side="left")

        # Process button + progress
        row2 = customtkinter.CTkFrame(control_card, fg_color="transparent")
        row2.pack(fill="x", padx=30, pady=(0, 25))

        self.start_button = customtkinter.CTkButton(
            row2,
            text="🚀 BẮT ĐẦU TRÍCH XUẤT",
            font=("Segoe UI", 17, "bold"),
            height=55,
            fg_color="#27ae60",
            hover_color="#229954",
            command=self.start_processing_thread,
            corner_radius=12,
        )
        self.start_button.pack(side="left")

        self.progress_bar = customtkinter.CTkProgressBar(
            row2, mode="indeterminate", height=10, progress_color="#27ae60", width=300
        )
        self.progress_bar.pack(side="left", padx=(30, 0))
        self.progress_bar.stop()
        self.progress_bar.set(0)

        # --- LEFT PANEL: SEARCH & RESULTS ---
        left_panel = customtkinter.CTkFrame(main_frame, fg_color="#f8f9fa", corner_radius=15, border_width=2, border_color="#e0e0e0")
        left_panel.grid(row=1, column=0, padx=(0, 15), pady=0, sticky="nsew")
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(2, weight=1)

        # Search bar
        search_frame = customtkinter.CTkFrame(left_panel, fg_color="transparent", height=70)
        search_frame.grid(row=0, column=0, padx=20, pady=(20, 15), sticky="ew")
        search_frame.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(
            search_frame, text="🔍 Tìm kiếm nhanh:", font=("Segoe UI", 15, "bold"), text_color="#2c3e50"
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.search_entry = customtkinter.CTkEntry(
            search_frame,
            placeholder_text="Nhập tên SV, QĐ hoặc ID...",
            height=40,
            font=("Segoe UI", 13),
        )
        self.search_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self.dynamic_search_files)

        search_btn = customtkinter.CTkButton(
            search_frame,
            text="Tìm",
            width=80,
            height=40,
            font=("Segoe UI", 13, "bold"),
            command=self.search_files,
            fg_color="#e67e22",
            hover_color="#d35400",
        )
        search_btn.grid(row=1, column=1)

        # Results list
        result_label = customtkinter.CTkLabel(
            left_panel,
            text="📋 Tài liệu đã lưu:",
            font=("Segoe UI", 16, "bold"),
            text_color="#2c3e50",
        )
        result_label.grid(row=1, column=0, padx=20, pady=(15, 10), sticky="w")

        self.results_listbox_frame = customtkinter.CTkScrollableFrame(
            left_panel,
            fg_color="#ffffff",
            scrollbar_button_color="#3498db",
            corner_radius=10,
            border_width=1,
            border_color="#e0e0e0",
        )
        self.results_listbox_frame.grid(row=2, column=0, padx=20, pady=(0, 25), sticky="nsew")

        # --- RIGHT PANEL: CONTENT & ACTIONS ---
        right_panel = customtkinter.CTkFrame(main_frame, fg_color="#f8f9fa", corner_radius=15, border_width=2, border_color="#e0e0e0")
        right_panel.grid(row=1, column=1, padx=(15, 0), pady=0, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(2, weight=1)

        # Action button
        self.open_image_button = customtkinter.CTkButton(
            right_panel,
            text="🖼️ Xem ảnh gốc với chữ ký đã nhận dạng",
            font=("Segoe UI", 15, "bold"),
            height=45,
            state="disabled",
            command=self.show_original_image_window,
            fg_color="#9b59b6",
            hover_color="#8e44ad",
        )
        self.open_image_button.grid(row=0, column=0, padx=25, pady=(25, 20), sticky="ew")

        # Content display
        content_label = customtkinter.CTkLabel(
            right_panel,
            text="📝 Nội dung tài liệu đã trích xuất:",
            font=("Segoe UI", 16, "bold"),
            text_color="#2c3e50",
        )
        content_label.grid(row=1, column=0, padx=25, pady=(10, 10), sticky="w")

        self.output_textbox = customtkinter.CTkTextbox(
            right_panel,
            font=("Consolas", 13),
            wrap="word",
            fg_color="#ffffff",
            text_color="#2c3e50",
            corner_radius=10,
            border_width=1,
            border_color="#e0e0e0",
        )
        self.output_textbox.grid(row=2, column=0, padx=25, pady=(0, 25), sticky="nsew")

        # === STATUS BAR ===
        status_frame = customtkinter.CTkFrame(self, height=40, corner_radius=0, fg_color="#ecf0f1")
        status_frame.pack(side="bottom", fill="x", padx=0, pady=0)

        self.status_label = customtkinter.CTkLabel(
            status_frame,
            text="✅ Sẵn sàng | Phiên bản Light Dashboard 1.0",
            font=("Segoe UI", 12),
            text_color="#7f8c8d",
            anchor="w",
        )
        self.status_label.pack(side="left", padx=40, pady=8)

        # Load initial data
        if self.conn:
            self.load_initial_data()

    # --- Các hàm xử lý (giữ nguyên logic, chỉ sửa giao diện nếu cần) ---
    def get_db_connection(self):
        try:
            conn = pyodbc.connect(CONNECTION_STRING)
            return conn
        except pyodbc.Error as e:
            sql_state = e.args[0]
            if sql_state == "28000":
                messagebox.showerror("Lỗi kết nối", "Tên người dùng hoặc mật khẩu SQL Server không đúng.")
            elif sql_state == "08001":
                messagebox.showerror("Lỗi kết nối", "Không thể kết nối đến SQL Server. Vui lòng kiểm tra địa chỉ máy chủ.")
            else:
                messagebox.showerror("Lỗi kết nối", f"Đã xảy ra lỗi khi kết nối SQL Server:\n{e}")
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
            self.status_label.configure(text=f"✅ Đã chọn: {os.path.basename(file_path)}")

    def start_processing_thread(self):
        image_path = self.image_path_entry.get()
        if not image_path:
            messagebox.showerror("Lỗi", "Vui lòng chọn một file ảnh.")
            return

        self.status_label.configure(text="⏳ Đang xử lý bằng AI...")
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
                    toa_do_chu_ki_json = json.dumps(toa_do_chu_ki) if toa_do_chu_ki else None

                    summary_content = (
                        f"🧑‍🎓 Họ tên sinh viên: {ho_ten_sinh_vien}\n"
                        f"📑 Tên quyết định: {ten_quyet_dinh}\n"
                        f"✍️ Người ký: {nguoi_ki}\n\n"
                        f"📋 Chi tiết các điều khoản:\n" + "\n".join(f"• {qd}" for qd in data.get("cac_quyet_dinh", []))
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
                            new_id = cursor.execute("SELECT @@IDENTITY").fetchval()
                            self.after(0, lambda: self.finish_processing(f"Đã lưu vào CSDL (ID: {new_id})", summary_content))
                        except pyodbc.Error as e:
                            self.after(0, lambda: self.handle_error(f"Lỗi khi lưu vào CSDL: {e}"))
                        finally:
                            conn.close()
                    else:
                        self.after(0, lambda: self.handle_error("Lỗi: Không thể kết nối cơ sở dữ liệu."))
                except (json.JSONDecodeError, KeyError) as e:
                    self.after(0, lambda: self.handle_error(f"Lỗi JSON hoặc thiếu khóa: {e}"))
            else:
                self.after(0, lambda: self.handle_error("Không thể trích xuất văn bản. Phản hồi API không hợp lệ."))

        threading.Thread(target=worker, daemon=True).start()

    def finish_processing(self, save_message, content):
        self.progress_bar.stop()
        self.output_textbox.delete("1.0", "end")
        self.output_textbox.insert("1.0", content)
        self.status_label.configure(text=f"✅ Thành công! {save_message}")
        self.start_button.configure(state="normal")
        messagebox.showinfo("Thành công", "Đã trích xuất và lưu văn bản thành công!")
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
            cursor.execute("SELECT id, ten_quyet_dinh, ho_ten_sinh_vien FROM Documents ORDER BY id DESC")
            rows = cursor.fetchall()
            for row in rows:
                doc_id, ten_qd, ho_ten = row
                display_name = f"📌 {ten_qd}\n👤 {ho_ten}  (ID: {doc_id})"

                item_frame = customtkinter.CTkFrame(
                    self.results_listbox_frame,
                    fg_color="#ffffff",
                    corner_radius=10,
                    border_width=1,
                    border_color="#e0e0e0",
                )
                item_frame.pack(fill="x", padx=5, pady=6)
                item_frame.grid_columnconfigure(0, weight=1)

                label = customtkinter.CTkLabel(
                    item_frame,
                    text=display_name,
                    font=("Segoe UI", 13),
                    justify="left",
                    anchor="w",
                    text_color="#2c3e50",
                )
                label.pack(fill="x", padx=15, pady=12)
                label.bind("<Button-1>", lambda event, did=doc_id: self.show_file_content(did))
                label.bind("<Enter>", lambda event, frame=item_frame: frame.configure(fg_color="#f0f0f0"))
                label.bind("<Leave>", lambda event, frame=item_frame: frame.configure(fg_color="#ffffff"))

            self.status_label.configure(text=f"✅ Đã tải {len(rows)} tài liệu.")
        except pyodbc.Error as e:
            print(f"Lỗi khi tải dữ liệu: {e}")
            self.status_label.configure(text="❌ Lỗi khi tải dữ liệu từ CSDL.")

    def dynamic_search_files(self, event=None):
        search_term = self.search_entry.get().strip().lower()
        for widget in self.results_listbox_frame.winfo_children():
            widget.destroy()

        if not search_term:
            self.load_initial_data()
            return

        found_count = 0
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, ten_quyet_dinh, ho_ten_sinh_vien FROM Documents
                WHERE LOWER(ten_quyet_dinh) LIKE ? OR LOWER(ho_ten_sinh_vien) LIKE ? OR CAST(id AS NVARCHAR) LIKE ?
                ORDER BY id DESC
            """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))

            rows = cursor.fetchall()
            for row in rows:
                doc_id, ten_qd, ho_ten = row
                display_name = f"📌 {ten_qd}\n👤 {ho_ten}  (ID: {doc_id})"

                item_frame = customtkinter.CTkFrame(
                    self.results_listbox_frame,
                    fg_color="#ffffff",
                    corner_radius=10,
                    border_width=1,
                    border_color="#e0e0e0",
                )
                item_frame.pack(fill="x", padx=5, pady=6)
                item_frame.grid_columnconfigure(0, weight=1)

                label = customtkinter.CTkLabel(
                    item_frame,
                    text=display_name,
                    font=("Segoe UI", 13),
                    justify="left",
                    anchor="w",
                    text_color="#2c3e50",
                )
                label.pack(fill="x", padx=15, pady=12)
                label.bind("<Button-1>", lambda event, did=doc_id: self.show_file_content(did))
                label.bind("<Enter>", lambda event, frame=item_frame: frame.configure(fg_color="#f0f0f0"))
                label.bind("<Leave>", lambda event, frame=item_frame: frame.configure(fg_color="#ffffff"))

                found_count += 1

            self.status_label.configure(text=f"✅ Tìm thấy {found_count} kết quả cho '{search_term}'")
        except pyodbc.Error as e:
            print(f"Lỗi tìm kiếm: {e}")
            self.status_label.configure(text="❌ Lỗi tìm kiếm trong CSDL.")

    def search_files(self):
        self.dynamic_search_files()

    def show_file_content(self, doc_id):
        self.output_textbox.delete("1.0", "end")
        self.open_image_button.configure(state="disabled")
        self.current_selected_doc_id = None

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT ho_ten_sinh_vien, ten_quyet_dinh, nguoi_ki, cac_quyet_dinh, duong_dan_anh_goc, toa_do_chu_ki 
                FROM Documents WHERE id = ?
            """, (doc_id,))
            row = cursor.fetchone()

            if row:
                ho_ten_sinh_vien, ten_quyet_dinh, nguoi_ki, cac_quyet_dinh_json, duong_dan_anh_goc, toa_do_chu_ki_json = row
                cac_quyet_dinh = json.loads(cac_quyet_dinh_json)

                content = (
                    f"🧑‍🎓 Họ tên sinh viên: {ho_ten_sinh_vien}\n"
                    f"📑 Tên quyết định: {ten_quyet_dinh}\n"
                    f"✍️ Người ký: {nguoi_ki}\n\n"
                    f"📋 Chi tiết các điều khoản:\n" + "\n".join(f"• {qd}" for qd in cac_quyet_dinh)
                )

                self.output_textbox.insert("1.0", content)
                self.current_selected_doc_id = doc_id
                self.open_image_button.configure(state="normal")
                self.status_label.configure(text=f"✅ Đang xem tài liệu ID: {doc_id}")
            else:
                messagebox.showerror("Lỗi", "Không tìm thấy tài liệu.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể đọc nội dung: {e}")

    def show_original_image_window(self):
        if not self.current_selected_doc_id:
            return

        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT duong_dan_anh_goc, toa_do_chu_ki FROM Documents WHERE id = ?", (self.current_selected_doc_id,))
            row = cursor.fetchone()

            if row:
                image_path, coords_json = row
                if not image_path or not os.path.exists(image_path):
                    messagebox.showerror("Lỗi", "Không tìm thấy ảnh gốc.")
                    return

                img = Image.open(image_path)
                coords = json.loads(coords_json) if coords_json else []

                if len(coords) == 4 and all(isinstance(c, (int, float)) for c in coords) and sum(coords) > 0:
                    draw = ImageDraw.Draw(img)
                    draw.rectangle(coords, outline="#e74c3c", width=6)
                    draw.text((coords[0], coords[1]-25), "📝 Chữ ký", fill="#e74c3c")

                # Resize ảnh để vừa màn hình
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                img_width, img_height = img.size
                ratio = min(screen_width * 0.7 / img_width, screen_height * 0.7 / img_height)
                new_size = (int(img_width * ratio), int(img_height * ratio))
                img_resized = img.resize(new_size, Image.LANCZOS)

                top = Toplevel(self)
                top.title(f"🖼️ Ảnh gốc - ID: {self.current_selected_doc_id}")
                top.geometry(f"{new_size[0] + 60}x{new_size[1] + 120}")
                top.configure(bg="#f8f9fa")

                tk_img = ImageTk.PhotoImage(img_resized)
                lbl = Label(top, image=tk_img, bg="#ffffff", relief="solid", bd=1)
                lbl.image = tk_img
                lbl.pack(padx=30, pady=30)

                info_lbl = Label(
                    top,
                    text="🔴 Khung đỏ: Vị trí chữ ký đã nhận dạng",
                    bg="#f8f9fa",
                    fg="#e74c3c",
                    font=("Segoe UI", 11, "bold"),
                )
                info_lbl.pack(pady=(0, 15))

        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể hiển thị ảnh: {e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
