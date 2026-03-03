import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

st.set_page_config(page_title="Quản Lý Duti's Home", layout="wide")

# ================= 1. CẤU HÌNH API THÔNG MINH (CHẠY CẢ PC & CLOUD) =================
@st.cache_resource
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # Cách 1: Thử tìm trong Két sắt (khi chạy trên Streamlit Cloud / Điện thoại)
        key_dict = json.loads(st.secrets["GCP_KEY"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    except Exception:
        # Cách 2: Nếu không có Két sắt, tự động tìm file json (khi chạy trên Máy tính)
        creds = ServiceAccountCredentials.from_json_keyfile_name('chia_khoa.json', scope)
        
    client = gspread.authorize(creds)
    sheet = client.open("DuTi Homestay").worksheet("Mật khẩu cổng")
    return sheet

sheet = get_google_sheet()

def load_data():
    data = sheet.get_all_values()
    headers = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=headers)
    df = df.loc[:, df.columns != '']
    
    df['Date_In'] = pd.to_datetime(df['Ngày check in'], format='%d/%m/%Y', errors='coerce')
    df['Date_Out'] = pd.to_datetime(df['Ngày check out'], format='%d/%m/%Y', errors='coerce')
    return df

df = load_data()
df_valid_dates = df.dropna(subset=['Date_In', 'Date_Out'])

today = pd.to_datetime(date.today())
ngay_toi_5 = today + timedelta(days=5)

def format_tien(so_tien):
    if so_tien == 0: return "0 đ"
    return f"{so_tien:,.0f} đ".replace(",", ".")

def parse_tien(chuoi_tien):
    if not chuoi_tien or chuoi_tien == "": return 0
    so = str(chuoi_tien).replace(" đ", "").replace(".", "").replace(",", "")
    if so.isdigit(): return int(so)
    return 0

ds_don_phong = ["", "Duti", "Bé NA", "C. Xuân"]

# ================= XỬ LÝ LÀM SẠCH FORM AN TOÀN =================
if "do_clear_search" not in st.session_state: st.session_state.do_clear_search = False
if "do_clear_new" not in st.session_state: st.session_state.do_clear_new = False

if st.session_state.do_clear_search:
    if "edit_search" in st.session_state: st.session_state.edit_search = ""
    st.session_state.do_clear_search = False

if st.session_state.do_clear_new:
    st.session_state.new_khach = ""
    st.session_state.new_dt = 0
    st.session_state.new_coc = 0
    st.session_state.new_don = ""
    st.session_state.new_ghi = ""
    st.session_state.new_phong = "101 Moon"
    st.session_state.new_in = date.today()
    st.session_state.new_out = date.today() + timedelta(days=1)
    st.session_state.do_clear_new = False

st.title("🏡 Hệ Thống Quản Lý Duti's Home")
tab1, tab2, tab3 = st.tabs(["📊 Tổng quan", "📝 Nhập Đặt Phòng Mới", "🔍 Tra Cứu & Sửa"])

# ================= 2. TAB 1: TỔNG QUAN =================
with tab1:
    st.subheader("Lượt đặt phòng hiện tại và 5 ngày tới")
    
    mask_hien_tai = (df['Date_In'] <= today) & (df['Date_Out'] >= today)
    mask_5_ngay = (df['Date_In'] > today) & (df['Date_In'] <= ngay_toi_5)
    df_hien_thi = df[mask_hien_tai | mask_5_ngay].copy()
    
    if not df_hien_thi.empty:
        def format_ngay_thu(d):
            if pd.isna(d): return ""
            thu = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
            return f"{thu[d.weekday()]}, {d.strftime('%d/%m/%Y')}"
            
        df_hien_thi['Ngày check in'] = df_hien_thi['Date_In'].apply(format_ngay_thu)
        df_hien_thi['Ngày check out'] = df_hien_thi['Date_Out'].apply(format_ngay_thu)
        
        def highlight_today_tomorrow(s):
            today_str = today.strftime('%d/%m/%Y')
            tomorrow_str = (today + timedelta(days=1)).strftime('%d/%m/%Y')
            styles = []
            for val in s:
                if isinstance(val, str):
                    if today_str in val:
                        styles.append('background-color: #ffcccc; color: black;')
                    elif tomorrow_str in val:
                        styles.append('background-color: #fff2cc; color: black;')
                    else:
                        styles.append('')
                else:
                    styles.append('')
            return styles
            
        cols_to_show = ['Phòng', 'Ngày check in', 'Ngày check out', 'Khách', 'Doanh thu', 'Mã khóa cửa', 'Tạo/Gửi mã', 'Cọc', 'Cần tt', 'Ghi chú']
        styled_df = df_hien_thi[cols_to_show].style.apply(highlight_today_tomorrow, subset=['Ngày check in', 'Ngày check out'])
        
        st.dataframe(styled_df)
    else:
        st.info("Hiện không có lượt đặt phòng nào đang diễn ra hoặc sắp đến.")
    
    st.markdown("---")
    col_cb1, col_cb2 = st.columns(2)
    
    with col_cb1:
        st.markdown("### 🔑 Chưa gửi mã")
        chua_gui_ma = df[mask_5_ngay & (df['Tạo/Gửi mã'] != '✔') & (df['Khách'] != '')]
        
        if chua_gui_ma.empty:
            st.success("Tuyệt vời! Đã gửi mã cho tất cả các khách sắp đến.")
        else:
            for index, row in chua_gui_ma.iterrows():
                ghi_chu = row.get('Ghi chú', '')
                txt_ghi_chu = f" | Ghi chú: *{ghi_chu}*" if ghi_chu else ""
                
                st.error(f"**Phòng {row.get('Phòng', '')}** - Khách: **{row.get('Khách', '')}**\n\n"
                         f"Ngày: **{row.get('Ngày check in', '')}** đến **{row.get('Ngày check out', '')}** {txt_ghi_chu}")
                
                st.markdown("🔑 **Mã khóa:** (Rê chuột vào góc phải ô bên dưới để Copy)")
                st.code(row.get('Mã khóa cửa', 'Chưa có'), language="plaintext")
                         
                if st.button(f"Đã tạo và gửi mã cho {row.get('Khách', '')}", key=f"gui_ma_{index}"):
                    col_index = df.columns.get_loc('Tạo/Gửi mã') + 1
                    sheet.update_cell(index + 2, col_index, '✔') 
                    st.rerun()

    with col_cb2:
        st.markdown("### 💰 Chưa thanh toán đủ")
        if 'Cần tt' in df.columns:
            chua_thanh_toan = df[(df['Cần tt'] != '') & (df['Cần tt'] != '0') & (df['Cần tt'] != '0 đ') & (df['Khách'] != '')]
            
            if chua_thanh_toan.empty:
                st.success("Hiện tại không có khách nào chưa thanh toán đủ.")
            else:
                for index, row in chua_thanh_toan.iterrows():
                    st.warning(f"**Phòng {row.get('Phòng', '')}** - Khách: **{row.get('Khách', '')}**\n\n"
                               f"Ngày: **{row.get('Ngày check in', '')}** đến **{row.get('Ngày check out', '')}**\n\n"
                               f"Đã cọc: **{row.get('Cọc', '')}** | Cần thu nốt: **{row.get('Cần tt', '')}**")
                    if st.button(f"Đã thanh toán đủ ({row.get('Khách', '')})", key=f"tt_{index}"):
                        col_coc = df.columns.get_loc('Cọc') + 1
                        col_cantt = df.columns.get_loc('Cần tt') + 1
                        sheet.update_cell(index + 2, col_coc, '') 
                        sheet.update_cell(index + 2, col_cantt, '') 
                        st.rerun()

    st.markdown("---")
    col_cb3, col_cb4 = st.columns(2)
    
    with col_cb3:
        st.markdown("### 💸 Chưa nhập doanh thu")
        chua_dt = df[(df['Khách'] != '') & (df['Doanh thu'] == '')]
        if chua_dt.empty:
            st.success("Tất cả lượt đặt đều đã nhập doanh thu.")
        else:
            for index, row in chua_dt.iterrows():
                with st.container(border=True):
                    st.write(f"Phòng **{row.get('Phòng', '')}** - Khách: **{row.get('Khách', '')}** ({row.get('Ngày check in', '')} -> {row.get('Ngày check out', '')})")
                    c_dt1, c_dt2 = st.columns([3, 1])
                    with c_dt1:
                        nhap_nhanh_dt = st.number_input("Doanh thu (VNĐ)", min_value=0, step=10000, key=f"nhanh_dt_{index}", label_visibility="collapsed")
                    with c_dt2:
                        if st.button("Lưu", key=f"btn_dt_{index}", use_container_width=True):
                            tien_coc = parse_tien(row.get('Cọc', ''))
                            can_tt = 0
                            if tien_coc > 0:
                                can_tt = max(0, nhap_nhanh_dt - tien_coc)
                                
                            col_dt = df.columns.get_loc('Doanh thu') + 1
                            col_cantt = df.columns.get_loc('Cần tt') + 1
                            sheet.update_cell(index + 2, col_dt, format_tien(nhap_nhanh_dt))
                            sheet.update_cell(index + 2, col_cantt, format_tien(can_tt))
                            st.rerun()

    with col_cb4:
        st.markdown("### 🧹 Chưa nhập người dọn dẹp")
        chua_don = df[(df['Khách'] != '') & (df['Dọn phòng'] == '') & (df['Date_Out'] <= today)]
        if chua_don.empty:
            st.success("Tất cả lượt đặt hiện tại/quá khứ đều đã phân công dọn dẹp.")
        else:
            for index, row in chua_don.iterrows():
                with st.container(border=True):
                    st.write(f"Phòng **{row.get('Phòng', '')}** - Khách: **{row.get('Khách', '')}** ({row.get('Ngày check in', '')} -> {row.get('Ngày check out', '')})")
                    c_don1, c_don2 = st.columns([3, 1])
                    with c_don1:
                        nhap_nhanh_don = st.selectbox("Người dọn:", ds_don_phong, key=f"nhanh_don_{index}", label_visibility="collapsed")
                    with c_don2:
                        if st.button("Lưu", key=f"btn_don_{index}", use_container_width=True):
                            col_don = df.columns.get_loc('Dọn phòng') + 1
                            sheet.update_cell(index + 2, col_don, nhap_nhanh_don)
                            st.rerun()


# ================= 3. TAB 2: NHẬP LIỆU MỚI =================
if "new_phong" not in st.session_state: st.session_state.new_phong = "101 Moon"
if "new_in" not in st.session_state: st.session_state.new_in = date.today()
if "new_out" not in st.session_state: st.session_state.new_out = date.today() + timedelta(days=1)

with tab2:
    st.subheader("Nhập Đặt Phòng Mới")
    c1, c2 = st.columns(2)
    
    with c1:
        phong_moi = st.selectbox("Chọn phòng:", ["101 Moon", "102 Noir", "103 Cine", "201 Sun", "202 Haven", "203 Garden"], key="new_phong")
        khach_moi = st.text_input("Tên khách hàng:", key="new_khach")
        ngay_in_moi = st.date_input("Ngày Check-in:", key="new_in")
        ngay_out_moi = st.date_input("Ngày Check-out:", key="new_out")

    with c2:
        doanh_thu = st.number_input("Doanh thu (VNĐ):", min_value=0, step=10000, key="new_dt")
        tien_coc = st.number_input("Tiền cọc (VNĐ):", min_value=0, step=10000, key="new_coc")
        
        can_tt = 0
        if tien_coc > 0:
            can_tt = max(0, doanh_thu - tien_coc)
            
        st.info(f"**Số tiền chưa thanh toán:** {can_tt:,.0f} VNĐ".replace(",", "."))
            
        don_phong = st.selectbox("Người dọn phòng:", ds_don_phong, key="new_don")
        ghi_chu = st.text_area("Ghi chú:", key="new_ghi")

    st.markdown("---")
    
    ngay_in_pd = pd.to_datetime(ngay_in_moi)
    ngay_out_pd = pd.to_datetime(ngay_out_moi)
    mask_trung = (df_valid_dates['Phòng'] == phong_moi) & (ngay_in_pd < df_valid_dates['Date_Out']) & (ngay_out_pd > df_valid_dates['Date_In'])
    df_trung = df_valid_dates[mask_trung]
    
    cho_phep_luu = True
    xac_nhan_bo_qua = False
    
    if not df_trung.empty and khach_moi != "":
        st.error("🚨 PHÁT HIỆN TRÙNG LỊCH! Phòng này đã có khách đặt đè lên khoảng thời gian trên:")
        st.dataframe(df_trung[['Phòng', 'Khách', 'Ngày check in', 'Ngày check out']])
        xac_nhan_bo_qua = st.checkbox("⚠️ Bỏ qua cảnh báo và vẫn tiếp tục tạo lượt đặt phòng này")
        if not xac_nhan_bo_qua:
            cho_phep_luu = False

    if st.button("💾 Lưu dữ liệu mới", type="primary"):
        if not khach_moi: st.error("❌ Vui lòng nhập tên khách hàng!")
        elif ngay_out_moi <= ngay_in_moi: st.error("❌ Ngày check-out phải lớn hơn ngày check-in!")
        elif not cho_phep_luu: st.error("❌ Bị trùng lịch! Vui lòng tick vào ô xác nhận bỏ qua cảnh báo ở trên nếu muốn lưu!")
        else:
            col_c = sheet.col_values(3) 
            dong_moi_index = len(col_c) + 1
            
            du_lieu_nhay_coc = [
                {'range': f'A{dong_moi_index}:D{dong_moi_index}', 'values': [[dong_moi_index - 1, phong_moi, ngay_in_moi.strftime("%d/%m/%Y"), ngay_out_moi.strftime("%d/%m/%Y")]]},
                {'range': f'F{dong_moi_index}:G{dong_moi_index}', 'values': [[khach_moi, don_phong]]},
                {'range': f'I{dong_moi_index}:L{dong_moi_index}', 'values': [[format_tien(doanh_thu), format_tien(tien_coc), format_tien(can_tt), ghi_chu]]}
            ]
            
            luu_thanh_cong = False
            try:
                sheet.batch_update(du_lieu_nhay_coc, value_input_option='USER_ENTERED')
                luu_thanh_cong = True
            except Exception as e:
                st.error(f"❌ Lỗi khi lưu: {e}")

            if luu_thanh_cong:
                st.session_state.do_clear_new = True 
                st.success(f"✅ Đã tạo lượt đặt phòng thành công!")
                st.rerun()

# ================= 4. TAB 3: TÌM KIẾM & SỬA / XÓA =================
with tab3:
    st.subheader("Tra cứu, Sửa & Xóa thông tin")
    tu_khoa = st.text_input("Nhập tên khách, phòng, hoặc ngày tháng để tìm kiếm:", key="edit_search")
    
    if tu_khoa:
        mask = df.apply(lambda row: row.astype(str).str.contains(tu_khoa, case=False).any(), axis=1)
        df_kq = df[mask]
        
        if df_kq.empty:
            st.warning("Không tìm thấy dữ liệu phù hợp.")
        else:
            st.write(f"Tìm thấy {len(df_kq)} kết quả:")
            options = []
            for idx, row in df_kq.iterrows():
                options.append(f"[{idx}] {row.get('Phòng', '')} - Khách: {row.get('Khách', '')} ({row.get('Ngày check in', '')} -> {row.get('Ngày check out', '')})")
                
            lua_chon = st.selectbox("Chọn một lượt đặt phòng để thao tác:", options)
            
            if lua_chon:
                chon_idx = int(lua_chon.split("]")[0].replace("[", ""))
                row_cu = df.loc[chon_idx]
                
                st.markdown("### Thông tin chi tiết")
                with st.form("form_sua_xoa"):
                    s1, s2 = st.columns(2)
                    with s1:
                        phong_ds = ["101 Moon", "102 Noir", "103 Cine", "201 Sun", "202 Haven", "203 Garden"]
                        idx_phong = phong_ds.index(row_cu['Phòng']) if row_cu['Phòng'] in phong_ds else 0
                        
                        e_phong = st.selectbox("Phòng:", phong_ds, index=idx_phong)
                        e_khach = st.text_input("Khách:", row_cu['Khách'])
                        
                        try: e_in = pd.to_datetime(row_cu['Ngày check in'], format="%d/%m/%Y").date()
                        except: e_in = date.today()
                        e_ngay_in = st.date_input("Check-in:", e_in)
                        
                        try: e_out = pd.to_datetime(row_cu['Ngày check out'], format="%d/%m/%Y").date()
                        except: e_out = date.today() + timedelta(days=1)
                        e_ngay_out = st.date_input("Check-out:", e_out)
                    
                    with s2:
                        e_dt = st.number_input("Doanh thu:", value=parse_tien(row_cu['Doanh thu']), step=10000)
                        e_coc = st.number_input("Cọc:", value=parse_tien(row_cu['Cọc']), step=10000)
                        
                        try: idx_don = ds_don_phong.index(row_cu.get('Dọn phòng', ''))
                        except: idx_don = 0
                        e_don = st.selectbox("Người dọn phòng:", ds_don_phong, index=idx_don)
                        
                        e_ghi = st.text_area("Ghi chú:", row_cu.get('Ghi chú', ''))
                    
                    e_can_tt = 0
                    if e_coc > 0:
                        e_can_tt = max(0, e_dt - e_coc)
                        
                    st.write(f"**Số tiền chưa thanh toán:** {e_can_tt:,.0f} VNĐ".replace(",", "."))
                    
                    ngay_in_pd_e = pd.to_datetime(e_ngay_in)
                    ngay_out_pd_e = pd.to_datetime(e_ngay_out)
                    mask_trung_e = (df_valid_dates['Phòng'] == e_phong) & (ngay_in_pd_e < df_valid_dates['Date_Out']) & (ngay_out_pd_e > df_valid_dates['Date_In']) & (df_valid_dates.index != chon_idx)
                    df_trung_e = df_valid_dates[mask_trung_e]
                    
                    if not df_trung_e.empty:
                        st.error("🚨 Trùng lịch với lượt đặt khác!")
                        st.dataframe(df_trung_e[['Phòng', 'Khách', 'Ngày check in', 'Ngày check out']])
                        e_bo_qua = st.checkbox("⚠️ Bỏ qua trùng lịch và vẫn cập nhật")
                    else:
                        e_bo_qua = True
                        
                    st.markdown("---")
                    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1.5])
                    with col_btn1:
                        btn_luu_sua = st.form_submit_button("💾 Cập nhật", type="primary")
                    with col_btn2:
                        btn_xoa = st.form_submit_button("🗑️ Xóa dữ liệu")
                    with col_btn3:
                        xac_nhan_xoa = st.checkbox("⚠️ Xác nhận muốn xóa lượt đặt này")
                    
                row_sheet_idx = chon_idx + 2 
                
                # XỬ LÝ NÚT CẬP NHẬT
                if btn_luu_sua:
                    if not e_khach: st.error("❌ Vui lòng nhập tên!")
                    elif e_ngay_out <= e_ngay_in: st.error("❌ Ngày check-out phải lớn hơn!")
                    elif not df_trung_e.empty and not e_bo_qua: st.error("❌ Vui lòng tick ô bỏ qua cảnh báo trùng lịch!")
                    else:
                        data_sua_nhay_coc = [
                            {'range': f'A{row_sheet_idx}:D{row_sheet_idx}', 'values': [[row_cu['STT'], e_phong, e_ngay_in.strftime("%d/%m/%Y"), e_ngay_out.strftime("%d/%m/%Y")]]},
                            {'range': f'F{row_sheet_idx}:G{row_sheet_idx}', 'values': [[e_khach, e_don]]},
                            {'range': f'I{row_sheet_idx}:L{row_sheet_idx}', 'values': [[format_tien(e_dt), format_tien(e_coc), format_tien(e_can_tt), e_ghi]]}
                        ]
                        
                        sua_thanh_cong = False
                        try:
                            sheet.batch_update(data_sua_nhay_coc, value_input_option='USER_ENTERED')
                            sua_thanh_cong = True
                        except Exception as e:
                            st.error(f"❌ Lỗi: {e}")
                            
                        if sua_thanh_cong:
                            st.session_state.do_clear_search = True 
                            st.success("✅ Cập nhật thành công!")
                            st.rerun()
                            
                # XỬ LÝ NÚT XÓA 
                if btn_xoa:
                    if not xac_nhan_xoa:
                        st.error("❌ Vui lòng tick vào ô 'Xác nhận muốn xóa' để tránh xóa nhầm!")
                    else:
                        data_xoa_nhay_coc = [
                            {'range': f'B{row_sheet_idx}:D{row_sheet_idx}', 'values': [['', '', '']]},
                            {'range': f'F{row_sheet_idx}:H{row_sheet_idx}', 'values': [['', '', '']]},
                            {'range': f'I{row_sheet_idx}:L{row_sheet_idx}', 'values': [['', '', '', '']]}
                        ]
                        xoa_thanh_cong = False
                        try:
                            sheet.batch_update(data_xoa_nhay_coc, value_input_option='USER_ENTERED')
                            xoa_thanh_cong = True
                        except Exception as e:
                            st.error(f"❌ Lỗi khi xóa: {e}")
                            
                        if xoa_thanh_cong:
                            st.session_state.do_clear_search = True 
                            st.success("✅ Đã xóa lượt đặt phòng an toàn, giữ nguyên công thức cột STT và Mã khóa!")
                            st.rerun()