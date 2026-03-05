import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import altair as alt
import os

st.set_page_config(page_title="Quản Lý Duti's Home", layout="wide")

# ================= ĐỔI MÀU & IN ĐẬM TOÀN BỘ NÚT BẤM =================
st.markdown("""
<style>
/* 1. IN ĐẬM TẤT CẢ CHỮ TRONG NÚT BẤM */
div.stButton > button p, div.stFormSubmitButton > button p {
    font-weight: bold !important;
}

/* 2. Ẩn hoàn toàn các mộc đánh dấu để không làm lệch giao diện */
div.element-container:has(.btn-green), 
div.element-container:has(.btn-red), 
div.element-container:has(.btn-blue) {
    display: none !important;
}

/* 3. TÔ MÀU XANH LÁ (Thêm dữ liệu, Lưu, Thanh toán...) */
div.element-container:has(.btn-green) + div.element-container button {
    background-color: #2ecc71 !important;
    border-color: #2ecc71 !important;
    color: white !important;
}
div.element-container:has(.btn-green) + div.element-container button:hover {
    background-color: #27ae60 !important;
    border-color: #27ae60 !important;
}

/* 4. TÔ MÀU ĐỎ (Xóa dữ liệu) */
div.element-container:has(.btn-red) + div.element-container button {
    background-color: #e74c3c !important;
    border-color: #e74c3c !important;
    color: white !important;
}
div.element-container:has(.btn-red) + div.element-container button:hover {
    background-color: #c0392b !important;
    border-color: #c0392b !important;
}

/* 5. TÔ MÀU XANH DƯƠNG (Tìm kiếm, Tạo mới, Cập nhật...) */
div.element-container:has(.btn-blue) + div.element-container button {
    background-color: #3498db !important;
    border-color: #3498db !important;
    color: white !important;
}
div.element-container:has(.btn-blue) + div.element-container button:hover {
    background-color: #2980b9 !important;
    border-color: #2980b9 !important;
}
</style>
""", unsafe_allow_html=True)

# ================= 1. CẤU HÌNH API & BỘ NHỚ TẠM (CACHE) =================
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    except Exception:
        creds = ServiceAccountCredentials.from_json_keyfile_name('chia_khoa.json', scope)
    return gspread.authorize(creds)

client = get_gspread_client()
db = client.open("DuTi Homestay")
sheet = db.worksheet("Mật khẩu cổng")

try:
    sheet_cp = db.worksheet("Chi phí")
except:
    sheet_cp = None

try:
    sheet_tt = db.worksheet("Thanh toán hàng tháng")
except:
    sheet_tt = None

try:
    sheet_ln = db.worksheet("Lợi nhuận")
except:
    sheet_ln = None

@st.cache_data(ttl=120, show_spinner=False)
def get_raw_main():
    return sheet.get_all_values()

@st.cache_data(ttl=120, show_spinner=False)
def get_raw_cp():
    if sheet_cp is None: return []
    return sheet_cp.get_all_values()

@st.cache_data(ttl=120, show_spinner=False)
def get_raw_tt():
    if sheet_tt is None: return []
    return sheet_tt.get_all_values()

@st.cache_data(ttl=120, show_spinner=False)
def get_raw_ln():
    if sheet_ln is None: return []
    return sheet_ln.get_all_values()

def load_data():
    data = get_raw_main()
    if not data: return pd.DataFrame()
    headers = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=headers)
    df = df.loc[:, df.columns != '']
    df = df.loc[:, ~df.columns.duplicated()]
    df['Date_In'] = pd.to_datetime(df['Ngày check in'], format='%d/%m/%Y', errors='coerce')
    df['Date_Out'] = pd.to_datetime(df['Ngày check out'], format='%d/%m/%Y', errors='coerce')
    return df

df = load_data()
df_valid_dates = df.dropna(subset=['Date_In', 'Date_Out'])

data_cp = get_raw_cp()
df_cp = pd.DataFrame(data_cp[1:], columns=data_cp[0]) if len(data_cp) > 1 else pd.DataFrame()
if not df_cp.empty: 
    df_cp.columns = df_cp.columns.str.strip()
    df_cp = df_cp.loc[:, ~df_cp.columns.duplicated()]

data_tt = get_raw_tt()
if len(data_tt) > 1:
    cols_tt = [str(c).strip() for c in data_tt[0]]
    if len(cols_tt) > 4:
        cols_tt[4] = "Số tiền E"
    
    final_cols_tt = []
    for c in cols_tt:
        if c in final_cols_tt:
            final_cols_tt.append(c + "_dup")
        else:
            final_cols_tt.append(c)
            
    df_tt = pd.DataFrame(data_tt[1:], columns=final_cols_tt)
else:
    df_tt = pd.DataFrame()

today = pd.to_datetime(date.today())
ngay_toi_5 = today + timedelta(days=5)

def get_col_letter(col_name, default_letter):
    try:
        n = df.columns.get_loc(col_name) + 1
        string = ""
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            string = chr(65 + remainder) + string
        return string
    except:
        return default_letter

def parse_tien(chuoi_tien):
    if pd.isna(chuoi_tien) or chuoi_tien is None or str(chuoi_tien).strip() == "": return None
    chuoi_sach = re.sub(r'[^\d-]', '', str(chuoi_tien))
    try:
        return int(chuoi_sach)
    except:
        return 0

def format_tien_ui(so_tien):
    if so_tien is None: return ""
    return f"{int(so_tien):,.0f} đ".replace(",", ".")

# Hàm phụ trợ tạo chuỗi Tăng/Giảm theo PHẦN TRĂM (%)
def get_delta_html(curr, prev):
    if prev == 0 or pd.isna(prev): return ""
    d = ((curr - prev) / prev) * 100
    if d > 0: return f"<span style='color:#2ecc71; font-weight:bold; font-size:0.9em;'> (⬆ {d:.1f}%)</span>"
    elif d < 0: return f"<span style='color:#e74c3c; font-weight:bold; font-size:0.9em;'> (⬇ {abs(d):.1f}%)</span>"
    return "<span style='color:gray; font-weight:bold; font-size:0.9em;'> (0%)</span>"

def get_delta_val(curr, prev):
    if prev == 0 or pd.isna(prev): return 0
    return ((curr - prev) / prev) * 100

# Hàm phụ trợ tạo chuỗi Tăng/Giảm theo SỐ TIỀN (VNĐ) dành riêng cho ADR
def get_delta_money_html(curr, prev):
    if prev == 0 or pd.isna(prev): return ""
    d = curr - prev
    if d > 0: return f"<span style='color:#2ecc71; font-weight:bold; font-size:0.9em;'> (⬆ {format_tien_ui(d)})</span>"
    elif d < 0: return f"<span style='color:#e74c3c; font-weight:bold; font-size:0.9em;'> (⬇ {format_tien_ui(abs(d))})</span>"
    return "<span style='color:gray; font-weight:bold; font-size:0.9em;'> (0 đ)</span>"

ds_don_phong = ["", "Duti", "Bé NA", "C. Xuân"]
ds_hang_muc_cp = ["Tiền nhà TQĐ", "Tiền mạng TQĐ", "Tiền điện TQĐ", "Tiền rác TQĐ", "Nước chai TQĐ", "Nước bình TQĐ", "Vệ sinh máy lạnh TQĐ", "Công an TQĐ", "Tiền nhà HBC", "Tiền mạng HBC", "Tiền điện HBC", "Tiền rác HBC", "Nước chai HBC", "Nước bình HBC", "Vệ sinh máy lạnh HBC", "Công an HBC", "Lương chị Xuân", "Bé cháu dọn phòng", "Seeding", "Chạy QC", "Netflix", "Kẹo + cf", "Nước tẩy bồn cầu", "Nước giặt", "Sữa tắm", "Dầu gội", "Bàn chải đánh răng", "Giấy rút", "Giấy vệ sinh", "Túi rác", "Xịt côn trùng", "Bộ drap nệm mới", "Khăn tắm bổ sung", "Khác (Nhập tay)"]

if "dp_search_key" not in st.session_state: st.session_state.dp_search_key = ""
if "cp_search_key" not in st.session_state: st.session_state.cp_search_key = ""

# ================= GIAO DIỆN HEADER =================
if os.path.exists("Logo.png"):
    st.image("Logo.png", width=250)
else:
    st.markdown("<h1 style='margin-bottom: -15px;'>🏡</h1>", unsafe_allow_html=True)

st.title("Hệ Thống Quản Lý Duti's Home")

tab1, tab2, tab3 = st.tabs(["📊 Tổng quan", "🛏️ Đặt phòng", "🧾 Chi phí"])

# Hàm tính mốc tháng kinh doanh (Ngày 12)
def get_biz_month(target_date):
    if target_date.day >= 12:
        s_date = date(target_date.year, target_date.month, 12)
        if target_date.month == 12:
            e_date = date(target_date.year + 1, 1, 11)
        else:
            e_date = date(target_date.year, target_date.month + 1, 11)
    else:
        e_date = date(target_date.year, target_date.month, 11)
        if target_date.month == 1:
            s_date = date(target_date.year - 1, 12, 12)
        else:
            s_date = date(target_date.year, target_date.month - 1, 12)
    return s_date, e_date

# ================= 2. TAB 1: TỔNG QUAN =================
with tab1:
    st.header("🛏️ Đặt phòng")
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
            
        cols_to_show = ['Phòng', 'Ngày check in', 'Ngày check out', 'Khách', 'Doanh thu', 'Mã khóa cửa', 'Ghi chú']
        styled_df = df_hien_thi[cols_to_show].style.apply(highlight_today_tomorrow, subset=['Ngày check in', 'Ngày check out'])
        
        st.dataframe(styled_df)
    else:
        st.info("Hiện không có khách nào đang ở hoặc sắp đến.")
        
    col_cb1, col_cb2 = st.columns(2)
    
    with col_cb1:
        st.markdown("### 🔑 Chưa gửi mã")
        chua_gui_ma = df[mask_5_ngay & (df['Tạo/Gửi mã'] != '✔') & (df['Khách'] != '')]
        
        if chua_gui_ma.empty:
            st.success("Tuyệt vời! Đã gửi mã cho tất cả các khách sắp đến.")
        else:
            for index, row in chua_gui_ma.iterrows():
                ghi_chu = str(row.get('Ghi chú', '')).strip()
                txt_ghi_chu = f"\n\n**Ghi chú:** *{ghi_chu}*" if ghi_chu else ""
                
                st.error(f"**Phòng {row.get('Phòng', '')}** - Khách: **{row.get('Khách', '')}**\n\n"
                         f"Ngày: **{row.get('Ngày check in', '')}** đến **{row.get('Ngày check out', '')}**{txt_ghi_chu}")
                
                st.markdown("🔑 **Mã khóa:** (Nhấn vào góc phải ô bên dưới để copy)")
                ma_khoa = str(row.get('Mã khóa cửa', '')).strip()
                st.code(ma_khoa if ma_khoa else 'Chưa có', language="plaintext")
                         
                st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
                if st.button(f"Đã tạo và gửi mã cho {row.get('Khách', '')}", key=f"gui_ma_{index}"):
                    col_index = df.columns.get_loc('Tạo/Gửi mã') + 1
                    sheet.update_cell(index + 2, col_index, '✔') 
                    get_raw_main.clear()
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
                               f"Đã cọc: **{format_tien_ui(parse_tien(row.get('Cọc', '')))}** | Cần thu nốt: **{format_tien_ui(parse_tien(row.get('Cần tt', '')))}**")
                    
                    st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
                    if st.button(f"{row.get('Khách', '')} đã thanh toán đủ.", key=f"tt_{index}"):
                        col_coc = df.columns.get_loc('Cọc') + 1
                        col_cantt = df.columns.get_loc('Cần tt') + 1
                        sheet.update_cell(index + 2, col_coc, '') 
                        sheet.update_cell(index + 2, col_cantt, '') 
                        get_raw_main.clear()
                        st.rerun()

    col_cb3, col_cb4 = st.columns(2)
    
    with col_cb3:
        st.markdown("### 💸 Chưa nhập doanh thu")
        chua_dt = df[(df['Khách'] != '') & (df['Doanh thu'] == '')]
        if chua_dt.empty:
            st.success("Tất cả lượt đặt phòng đều đã nhập doanh thu.")
        else:
            for index, row in chua_dt.iterrows():
                with st.container(border=True):
                    st.write(f"Phòng **{row.get('Phòng', '')}** - Khách: **{row.get('Khách', '')}** ({row.get('Ngày check in', '')} -> {row.get('Ngày check out', '')})")
                    with st.form(f"form_dt_{index}"):
                        c_dt1, c_dt2 = st.columns([3, 1])
                        with c_dt1:
                            nhap_nhanh_dt_str = st.text_input("Doanh thu (VNĐ):", label_visibility="collapsed")
                        with c_dt2:
                            st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
                            if st.form_submit_button("Lưu", use_container_width=True):
                                nhap_nhanh_dt = parse_tien(nhap_nhanh_dt_str)
                                tien_coc = parse_tien(row.get('Cọc', ''))
                                can_tt = None
                                if tien_coc is not None:
                                    dt_val = nhap_nhanh_dt if nhap_nhanh_dt is not None else 0
                                    can_tt = max(0, dt_val - tien_coc)
                                col_dt = df.columns.get_loc('Doanh thu') + 1
                                col_cantt = df.columns.get_loc('Cần tt') + 1
                                val_dt_save = nhap_nhanh_dt if nhap_nhanh_dt is not None else ""
                                can_tt_save = can_tt if can_tt is not None else ""
                                sheet.update_cell(index + 2, col_dt, val_dt_save)
                                sheet.update_cell(index + 2, col_cantt, can_tt_save)
                                get_raw_main.clear()
                                st.rerun()

    with col_cb4:
        st.markdown("### 🧹 Chưa nhập người dọn dẹp")
        chua_don = df[(df['Khách'] != '') & (df['Dọn phòng'] == '') & (df['Date_Out'] <= today)]
        if chua_don.empty:
            st.success("Tất cả phòng checkout đều đã phân công dọn dẹp.")
        else:
            for index, row in chua_don.iterrows():
                with st.container(border=True):
                    st.write(f"Phòng **{row.get('Phòng', '')}** - Khách: **{row.get('Khách', '')}** ({row.get('Ngày check in', '')} -> {row.get('Ngày check out', '')})")
                    with st.form(f"form_don_{index}"):
                        c_don1, c_don2 = st.columns([3, 1])
                        with c_don1:
                            nhap_nhanh_don = st.selectbox("Người dọn:", ds_don_phong, label_visibility="collapsed")
                        with c_don2:
                            st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
                            if st.form_submit_button("Lưu", use_container_width=True):
                                col_don = df.columns.get_loc('Dọn phòng') + 1
                                sheet.update_cell(index + 2, col_don, nhap_nhanh_don)
                                get_raw_main.clear()
                                st.rerun()

    st.markdown("---")
    
    # ------------------ PHẦN CHI PHÍ ------------------
    st.header("🧾 Chi phí")
    
    today_date = date.today()
    curr_start, curr_end_full = get_biz_month(today_date)

    st.markdown(f"#### Chi phí trong tháng kinh doanh (Từ {curr_start.strftime('%d/%m/%Y')} đến {curr_end_full.strftime('%d/%m/%Y')})")
    
    if not df_cp.empty:
        df_cp['Ngày_parsed'] = pd.to_datetime(df_cp['Ngày'], format='%d/%m/%Y', errors='coerce').dt.date
        mask_thang = (df_cp['Ngày_parsed'] >= curr_start) & (df_cp['Ngày_parsed'] <= curr_end_full)
        df_cp_thang = df_cp[mask_thang].copy()
        
        if not df_cp_thang.empty:
            df_cp_thang['Số tiền gốc'] = df_cp_thang['Số tiền'].apply(parse_tien)
            total_cp = df_cp_thang['Số tiền gốc'].sum()
            st.success(f"**Tổng chi phí tháng hiện tại:** {format_tien_ui(total_cp)}")
            st.dataframe(df_cp_thang[['Ngày', 'Hạng mục', 'Số tiền']], use_container_width=True)
        else:
            st.info("Chưa có khoản chi nào được ghi nhận trong tháng kinh doanh hiện tại.")
            
    if not df_tt.empty and 'Ngày đến hạn' in df_tt.columns and 'Tên khoản thanh toán' in df_tt.columns and 'Trạng thái' in df_tt.columns:
        st.markdown("#### 🔔 Khoản chi sắp đến hạn")
        has_nhac_nho = False
        
        for idx, row in df_tt.iterrows():
            trang_thai = str(row.get('Trạng thái', '')).strip().lower()
            if trang_thai == 'đã thanh toán': continue
                
            ngay_str = str(row.get('Ngày đến hạn', '')).strip()
            if not ngay_str: continue
            
            try:
                if ngay_str.isdigit():
                    day_han = int(ngay_str)
                    ngay_han = date(today_date.year, today_date.month, day_han)
                    if ngay_han < today_date:
                        if today_date.month == 12: ngay_han = date(today_date.year + 1, 1, day_han)
                        else: ngay_han = date(today_date.year, today_date.month + 1, day_han)
                else:
                    ngay_han = pd.to_datetime(ngay_str, format="%d/%m/%Y").date()
                    
                delta = (ngay_han - today_date).days
                if 0 <= delta <= 3:
                    has_nhac_nho = True
                    with st.form(f"form_tt_{idx}"):
                        c_tt1, c_tt2, c_tt3 = st.columns([3, 2, 2])
                        with c_tt1:
                            st.markdown(f"⏳ **{row['Tên khoản thanh toán']}**<br>Hạn: **{ngay_han.strftime('%d/%m/%Y')}** (Còn {delta} ngày)", unsafe_allow_html=True)
                        with c_tt2:
                            tien_md = format_tien_ui(parse_tien(row.get('Số tiền E', '')))
                            nhap_tien_tt = st.text_input("Số tiền (VNĐ):", value=tien_md, key=f"tien_tt_{idx}", label_visibility="collapsed")
                        with c_tt3:
                            st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
                            if st.form_submit_button("Đã thanh toán", use_container_width=True):
                                so_tien_luu = parse_tien(nhap_tien_tt)
                                data_update_tt = [{'range': f'C{idx + 2}', 'values': [['Đã thanh toán']]}]
                                try:
                                    sheet_tt.batch_update(data_update_tt, value_input_option='USER_ENTERED')
                                    if sheet_cp is not None:
                                        col_c = sheet_cp.col_values(3)
                                        dong_moi_cp = len(col_c) + 1
                                        data_luu_cp = [{'range': f'C{dong_moi_cp}:F{dong_moi_cp}', 'values': [[today_date.strftime("%d/%m/%Y"), row['Tên khoản thanh toán'], so_tien_luu if so_tien_luu is not None else "", "OCB"]]}]
                                        sheet_cp.batch_update(data_luu_cp, value_input_option='USER_ENTERED')

                                    get_raw_tt.clear()
                                    get_raw_cp.clear()
                                    st.success("Ghi nhận thành công!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Lỗi: {e}")
            except: pass
            
        if not has_nhac_nho:
            st.success("Tất cả các khoản chi tiêu hàng tháng đều đã được thanh toán hoặc chưa tới hạn.")

    if not df_cp.empty:
        if 'Số tiền gốc' not in df_cp.columns:
            df_cp['Số tiền gốc'] = df_cp['Số tiền'].apply(parse_tien)
        tien_na = df_cp[df_cp['Nguồn tiền'].str.contains('Bé NA', case=False, na=False)]['Số tiền gốc'].sum()
        tien_duti = df_cp[df_cp['Nguồn tiền'].str.contains('Duti', case=False, na=False)]['Số tiền gốc'].sum()
        
        st.markdown("#### 💳 Tổng tiền đang tạm chi")
        c_tc1, c_tc2, _ = st.columns([1, 1, 2])
        c_tc1.info(f"**Bé NA tạm chi:** {format_tien_ui(tien_na)}")
        c_tc2.info(f"**Duti tạm chi:** {format_tien_ui(tien_duti)}")

    st.markdown("---")

    # ------------------ PHẦN HIỆU SUẤT ------------------
    st.header(f"📊 Hiệu suất (Tháng {curr_start.month})")
    
    # 1. LẤY DOANH THU TỪ SHEET LỢI NHUẬN ĐỂ CHUẨN XÁC 100%
    data_ln = get_raw_ln()
    rev_curr = 0
    rev_prev = 0
    avg_rev_6m = 0
    
    if data_ln and len(data_ln) > 1:
        df_ln_perf = pd.DataFrame(data_ln[1:], columns=data_ln[0])
        if 'Tháng' in df_ln_perf.columns and 'Tổng doanh thu' in df_ln_perf.columns:
            df_ln_perf = df_ln_perf[df_ln_perf['Tháng'] != '']
            df_ln_perf['DT_Goc'] = df_ln_perf['Tổng doanh thu'].apply(parse_tien)
            df_ln_perf['Thang_Date'] = pd.to_datetime(df_ln_perf['Tháng'], format='%m/%Y', errors='coerce')
            
            thang_nay_str = curr_start.strftime("%m/%Y")
            prev_start_biz, prev_end_biz = get_biz_month(curr_start - timedelta(days=1))
            thang_truoc_str = prev_start_biz.strftime("%m/%Y")
            
            try: rev_curr = df_ln_perf[df_ln_perf['Tháng'] == thang_nay_str]['DT_Goc'].iloc[0]
            except: rev_curr = 0
            
            try: rev_prev = df_ln_perf[df_ln_perf['Tháng'] == thang_truoc_str]['DT_Goc'].iloc[0]
            except: rev_prev = 0
            
            curr_month_datetime = datetime(curr_start.year, curr_start.month, 1)
            df_6m = df_ln_perf[df_ln_perf['Thang_Date'] <= curr_month_datetime].sort_values('Thang_Date').tail(6)
            if not df_6m.empty:
                avg_rev_6m = df_6m['DT_Goc'].mean()

    # 2. TÍNH TỶ LỆ LẤP PHÒNG & TÁCH DOANH THU CHO TỪNG PHÒNG
    try:
        df_perf = df_valid_dates.copy()
        df_perf['Date_In_d'] = df_perf['Date_In'].dt.date
        df_perf['Date_Out_d'] = df_perf['Date_Out'].dt.date
        df_perf['DT_num'] = df_perf['Doanh thu'].apply(parse_tien)

        curr_end_occ = min(today_date, curr_end_full)
        days_passed_occ = (curr_end_occ - curr_start).days + 1
        if days_passed_occ <= 0: days_passed_occ = 1
        
        prev_days_occ = (prev_end_biz - prev_start_biz).days + 1

        room_stats = []
        phong_list = ["101 Moon", "102 Noir", "103 Cine", "201 Sun", "202 Haven", "203 Garden"]
        
        total_paid_nights_occ_curr = 0
        total_avail_nights_occ_curr = 0
        total_paid_nights_full_curr = 0
        
        total_paid_nights_occ_prev = 0
        total_avail_nights_occ_prev = 0
        total_paid_nights_full_prev = 0

        for p in phong_list:
            df_p = df_perf[df_perf['Phòng'] == p]
            
            p_paid_nights_occ_curr = 0
            p_0vnd_nights_occ_curr = 0
            p_paid_nights_full_curr = 0
            p_rev_full_curr = 0
            
            p_paid_nights_occ_prev = 0
            p_0vnd_nights_occ_prev = 0
            p_paid_nights_full_prev = 0
            p_rev_full_prev = 0
            
            for _, r in df_p.iterrows():
                in_d = r['Date_In_d']
                out_d = r['Date_Out_d']
                dt = r['DT_num'] if not pd.isna(r['DT_num']) else 0
                
                total_nights_booking = (out_d - in_d).days
                if total_nights_booking <= 0: continue
                
                # THÁNG NÀY
                overlap_s_occ_curr = max(in_d, curr_start)
                overlap_e_occ_curr = min(out_d, curr_end_occ + timedelta(days=1))
                n_occ_curr = (overlap_e_occ_curr - overlap_s_occ_curr).days if overlap_s_occ_curr < overlap_e_occ_curr else 0
                
                overlap_s_full_curr = max(in_d, curr_start)
                overlap_e_full_curr = min(out_d, curr_end_full + timedelta(days=1))
                n_full_curr = (overlap_e_full_curr - overlap_s_full_curr).days if overlap_s_full_curr < overlap_e_full_curr else 0
                
                if dt <= 0:
                    p_0vnd_nights_occ_curr += max(0, n_occ_curr)
                else:
                    p_paid_nights_occ_curr += max(0, n_occ_curr)
                    p_paid_nights_full_curr += max(0, n_full_curr)
                    p_rev_full_curr += (dt / total_nights_booking) * max(0, n_full_curr)
                    
                # THÁNG TRƯỚC
                overlap_s_occ_prev = max(in_d, prev_start_biz)
                overlap_e_occ_prev = min(out_d, prev_end_biz + timedelta(days=1))
                n_occ_prev = (overlap_e_occ_prev - overlap_s_occ_prev).days if overlap_s_occ_prev < overlap_e_occ_prev else 0
                
                overlap_s_full_prev = max(in_d, prev_start_biz)
                overlap_e_full_prev = min(out_d, prev_end_biz + timedelta(days=1))
                n_full_prev = (overlap_e_full_prev - overlap_s_full_prev).days if overlap_s_full_prev < overlap_e_full_prev else 0
                
                if dt <= 0:
                    p_0vnd_nights_occ_prev += max(0, n_occ_prev)
                else:
                    p_paid_nights_occ_prev += max(0, n_occ_prev)
                    p_paid_nights_full_prev += max(0, n_full_prev)
                    p_rev_full_prev += (dt / total_nights_booking) * max(0, n_full_prev)
                    
            # TÍNH TOÁN HIỆU SUẤT TỪNG PHÒNG
            p_avail_nights_occ_curr = days_passed_occ - p_0vnd_nights_occ_curr
            if p_avail_nights_occ_curr > 0:
                p_occ_rate_curr = (p_paid_nights_occ_curr / p_avail_nights_occ_curr) * 100
                p_occ_str = f"{p_occ_rate_curr:.1f}%"
            else:
                p_occ_rate_curr = 0
                p_occ_str = "Ngưng KD"
                
            p_adr_curr = p_rev_full_curr / p_paid_nights_full_curr if p_paid_nights_full_curr > 0 else 0
            
            p_avail_nights_occ_prev = prev_days_occ - p_0vnd_nights_occ_prev
            p_occ_rate_prev = (p_paid_nights_occ_prev / p_avail_nights_occ_prev) * 100 if p_avail_nights_occ_prev > 0 else 0
            p_adr_prev = p_rev_full_prev / p_paid_nights_full_prev if p_paid_nights_full_prev > 0 else 0
            
            # FORMAT HTML CHO BẢNG (ADR dùng delta_money, Occ dùng delta_html)
            if p_occ_str != "Ngưng KD":
                html_occ = f"{p_occ_str}{get_delta_html(p_occ_rate_curr, p_occ_rate_prev)}"
            else:
                html_occ = p_occ_str
                
            html_adr = f"{format_tien_ui(p_adr_curr)}{get_delta_money_html(p_adr_curr, p_adr_prev)}"
            html_rev = f"{format_tien_ui(p_rev_full_curr)}{get_delta_html(p_rev_full_curr, p_rev_full_prev)}"
            
            room_stats.append({
                "Phòng": p,
                "Doanh thu": html_rev,
                "Lấp phòng": html_occ,
                "Giá TB 1 đêm": html_adr
            })
            
            total_paid_nights_occ_curr += p_paid_nights_occ_curr
            total_avail_nights_occ_curr += p_avail_nights_occ_curr
            total_paid_nights_full_curr += p_paid_nights_full_curr
            
            total_paid_nights_occ_prev += p_paid_nights_occ_prev
            total_avail_nights_occ_prev += p_avail_nights_occ_prev
            total_paid_nights_full_prev += p_paid_nights_full_prev

        # TÍNH TOÁN HIỆU SUẤT TỔNG TOÀN HOME
        if total_avail_nights_occ_curr > 0:
            home_occ_rate_curr = (total_paid_nights_occ_curr / total_avail_nights_occ_curr) * 100
            home_occ_str = f"{home_occ_rate_curr:.1f}%"
        else:
            home_occ_rate_curr = 0
            home_occ_str = "Ngưng KD"
            
        home_occ_rate_prev = (total_paid_nights_occ_prev / total_avail_nights_occ_prev) * 100 if total_avail_nights_occ_prev > 0 else 0
            
        home_adr_curr = rev_curr / total_paid_nights_full_curr if total_paid_nights_full_curr > 0 else 0
        home_adr_prev = rev_prev / total_paid_nights_full_prev if total_paid_nights_full_prev > 0 else 0

        # HIỂN THỊ UI KHỐI METRIC TRÊN CÙNG
        col_pf1, col_pf2, col_pf3, col_pf4 = st.columns(4)
        d_rev = get_delta_val(rev_curr, rev_prev)
        col_pf1.metric("Doanh thu tháng này", format_tien_ui(rev_curr), f"{d_rev:.1f}%" if rev_prev else None)
        col_pf2.metric("Doanh thu tháng trước", format_tien_ui(rev_prev))
        col_pf3.metric("Bình quân 6 tháng", format_tien_ui(avg_rev_6m))
        
        d_occ = get_delta_val(home_occ_rate_curr, home_occ_rate_prev)
        
        home_occ_str = f"{home_occ_rate_curr:.1f}%" if total_avail_nights_occ_curr > 0 else "Ngưng KD"
        col_pf4.metric("Tỷ lệ lấp phòng chung", home_occ_str, f"{d_occ:.1f}%" if home_occ_rate_prev and total_avail_nights_occ_curr > 0 else None)

        html_adr_chung = f"Giá trị trung bình 1 đêm (ADR chung): {format_tien_ui(home_adr_curr)}{get_delta_money_html(home_adr_curr, home_adr_prev)}"
        
        # In thẳng HTML không lùi lề để tránh lỗi Code Block của Markdown
        st.markdown("<div style='padding: 1rem; border-radius: 0.5rem; background-color: #1e293b; border: 1px solid #334155; color: #e2e8f0; margin-bottom: 1rem;'>ℹ️ <strong>" + html_adr_chung + "</strong></div>", unsafe_allow_html=True)

        st.markdown("##### Chi tiết tỷ lệ lấp phòng từng phòng")
        
        html_table = "<table style='width:100%; border-collapse: collapse; text-align: left; margin-bottom: 20px; font-size: 0.95em;'>"
        html_table += "<tr style='border-bottom: 1px solid #334155; background-color: #0f172a; color: #94a3b8;'>"
        html_table += "<th style='padding: 12px;'>Phòng</th>"
        html_table += "<th style='padding: 12px;'>Doanh thu</th>"
        html_table += "<th style='padding: 12px;'>Lấp phòng</th>"
        html_table += "<th style='padding: 12px;'>Giá TB 1 đêm</th>"
        html_table += "</tr>"
        
        for stat in room_stats:
            html_table += "<tr style='border-bottom: 1px solid #1e293b; background-color: #0f172a;'>"
            html_table += f"<td style='padding: 12px; font-weight: bold; color: #f8fafc;'>{stat['Phòng']}</td>"
            html_table += f"<td style='padding: 12px; color: #f8fafc;'>{stat['Doanh thu']}</td>"
            html_table += f"<td style='padding: 12px; color: #f8fafc;'>{stat['Lấp phòng']}</td>"
            html_table += f"<td style='padding: 12px; color: #f8fafc;'>{stat['Giá TB 1 đêm']}</td>"
            html_table += "</tr>"
            
        html_table += "</table>"
        
        st.markdown(html_table, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Lỗi khi tính toán hiệu suất: {e}")

    st.markdown("---")
    
    # ------------------ PHẦN LỢI NHUẬN ------------------
    st.header("📈 Lợi nhuận")
    col_ln1, col_ln2 = st.columns([3, 1])
    with col_ln2:
        st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
        if st.button("🔄 Cập nhật biểu đồ", use_container_width=True):
            get_raw_ln.clear()
            st.rerun()
            
    if data_ln and len(data_ln) > 1:
        df_ln = pd.DataFrame(data_ln[1:], columns=data_ln[0])
        if 'Tháng' in df_ln.columns and 'Tổng doanh thu' in df_ln.columns and 'Tổng chi phí' in df_ln.columns and 'Lợi nhuận' in df_ln.columns:
            df_ln_clean = pd.DataFrame()
            df_ln_clean['Tháng_Gốc'] = df_ln['Tháng']
            df_ln_clean['Doanh thu'] = df_ln['Tổng doanh thu'].apply(parse_tien)
            df_ln_clean['Chi phí'] = df_ln['Tổng chi phí'].apply(parse_tien)
            df_ln_clean['Lợi nhuận'] = df_ln['Lợi nhuận'].apply(parse_tien)
            df_ln_clean = df_ln_clean[df_ln_clean['Tháng_Gốc'] != '']
            
            if not df_ln_clean.empty:
                df_ln_clean['Tháng_Date'] = pd.to_datetime(df_ln_clean['Tháng_Gốc'], format='%m/%Y', errors='coerce')
                
                curr_month_datetime = datetime(curr_start.year, curr_start.month, 1)
                if curr_start.month == 12 and today_date.day < 12:
                    pass
                df_ln_clean = df_ln_clean[df_ln_clean['Tháng_Date'] <= curr_month_datetime]
                df_ln_clean = df_ln_clean.sort_values('Tháng_Date').tail(6)
                
                thang_order = df_ln_clean['Tháng_Gốc'].tolist()

                df_long = df_ln_clean.melt(id_vars=['Tháng_Gốc', 'Tháng_Date'], value_vars=['Doanh thu', 'Chi phí', 'Lợi nhuận'], var_name='Chỉ số', value_name='Số tiền')
                
                color_scale = alt.Scale(domain=['Doanh thu', 'Chi phí', 'Lợi nhuận'],
                                        range=['#2ecc71', '#dc3545', '#007bff'])
                
                line_chart = alt.Chart(df_long).mark_line(point=True, strokeWidth=3).encode(
                    x=alt.X('Tháng_Gốc:N', sort=thang_order, title="Tháng kinh doanh"),
                    y=alt.Y('Số tiền:Q', title="Số tiền (VNĐ)"),
                    color=alt.Color('Chỉ số:N', scale=color_scale),
                    tooltip=[
                        alt.Tooltip('Tháng_Gốc:N', title='Tháng'),
                        alt.Tooltip('Chỉ số:N', title='Hạng mục'),
                        alt.Tooltip('Số tiền:Q', format=',.0f', title='Số tiền (VNĐ)')
                    ]
                )
                
                zero_rule = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y')
                
                final_chart = (zero_rule + line_chart).interactive()
                st.altair_chart(final_chart, use_container_width=True)
            else:
                st.info("Chưa có dữ liệu lợi nhuận hợp lệ trong quá khứ.")
        else:
            st.warning("Sheet 'Lợi nhuận' không đúng định dạng cột yêu cầu.")
    else:
        st.info("Không tìm thấy dữ liệu trong sheet Lợi nhuận.")


# ================= 3. TAB 2: QUẢN LÝ ĐẶT PHÒNG =================
with tab2:
    st.subheader("🏡 Quản lý thông tin đặt phòng")
    
    with st.form("search_dp_form"):
        col_s1, col_s2, col_s3 = st.columns([4, 1, 1])
        with col_s1:
            tu_khoa = st.text_input("Tìm theo tên khách, phòng, ngày tháng...", value=st.session_state.dp_search_key)
        with col_s2:
            st.write("")
            st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
            btn_search_dp = st.form_submit_button("🔍 Tìm kiếm", use_container_width=True)
        with col_s3:
            st.write("")
            st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
            btn_clear_dp = st.form_submit_button("✨ Tạo mới", use_container_width=True)
            
    if btn_clear_dp:
        st.session_state.dp_search_key = ""
        st.rerun()
    if btn_search_dp:
        st.session_state.dp_search_key = tu_khoa
        
    chon_idx = None
    row_cu = None
    
    if st.session_state.dp_search_key:
        search_keys = st.session_state.dp_search_key.lower().split()
        mask = df.apply(lambda row: all(kw in ' '.join(row.astype(str)).lower() for kw in search_keys), axis=1)
        df_kq = df[mask]
        if df_kq.empty:
            st.warning("Không tìm thấy dữ liệu!")
        else:
            options = ["--- Chọn một lượt đặt phòng để sửa ---"] + [f"[{idx}] Phòng {row.get('Phòng', '')} - {row.get('Khách', '')} ({row.get('Ngày check in', '')})" for idx, row in df_kq.iterrows()]
            lua_chon = st.selectbox("Kết quả:", options)
            if lua_chon and lua_chon.startswith("["):
                chon_idx = int(lua_chon.split("]")[0].replace("[", ""))
                row_cu = df.loc[chon_idx]

    st.markdown(f"### ✏️ Sửa thông tin: {row_cu['Khách']}" if chon_idx is not None else "### 📝 Nhập đặt phòng mới")
    
    with st.form("form_dat_phong"):
        phong_ds = ["101 Moon", "102 Noir", "103 Cine", "201 Sun", "202 Haven", "203 Garden"]
        idx_phong = phong_ds.index(row_cu['Phòng']) if row_cu is not None and row_cu['Phòng'] in phong_ds else 0
        
        c1, c2 = st.columns(2)
        with c1:
            e_phong = st.selectbox("Phòng:", phong_ds, index=idx_phong)
            e_khach = st.text_input("Tên khách:", value=row_cu['Khách'] if row_cu is not None else "")
            
            try: def_in = pd.to_datetime(row_cu['Ngày check in'], format="%d/%m/%Y").date() if row_cu is not None else date.today()
            except: def_in = date.today()
            e_ngay_in = st.date_input("Ngày check-in:", value=def_in)
            
            try: def_out = pd.to_datetime(row_cu['Ngày check out'], format="%d/%m/%Y").date() if row_cu is not None else date.today() + timedelta(days=1)
            except: def_out = date.today() + timedelta(days=1)
            e_ngay_out = st.date_input("Ngày check-out:", value=def_out)

        with c2:
            e_dt_str = st.text_input("Doanh thu (VNĐ):", value=format_tien_ui(parse_tien(row_cu.get('Doanh thu', ''))) if row_cu is not None else "")
            e_coc_str = st.text_input("Cọc (VNĐ):", value=format_tien_ui(parse_tien(row_cu.get('Cọc', ''))) if row_cu is not None else "")
            
            try: idx_don = ds_don_phong.index(row_cu.get('Dọn phòng', '')) if row_cu is not None else 0
            except: idx_don = 0
            e_don = st.selectbox("Người dọn phòng:", ds_don_phong, index=idx_don)
            
            e_ghi = st.text_area("Ghi chú:", value=row_cu.get('Ghi chú', '') if row_cu is not None else "")
            
        e_bo_qua = st.checkbox("⚠️ Bỏ qua cảnh báo trùng lịch và tiếp tục lưu")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if chon_idx is None:
            st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
            btn_luu_dp = st.form_submit_button("Lưu")
            btn_xoa_dp = False
            xac_nhan_xoa = False
        else:
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1.5])
            with col_btn1:
                st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
                btn_luu_dp = st.form_submit_button("Lưu")
            with col_btn2:
                st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
                btn_xoa_dp = st.form_submit_button("🗑️ Xóa")
            xac_nhan_xoa = col_btn3.checkbox("⚠️ Xác nhận muốn xóa lượt đặt này")

    if btn_luu_dp:
        e_dt = parse_tien(e_dt_str)
        e_coc = parse_tien(e_coc_str)
        e_can_tt = None
        if e_coc is not None:
            dt_val = e_dt if e_dt is not None else 0
            e_can_tt = max(0, dt_val - e_coc)
            
        ngay_in_pd_e = pd.to_datetime(e_ngay_in)
        ngay_out_pd_e = pd.to_datetime(e_ngay_out)
        mask_trung_e = (df_valid_dates['Phòng'] == e_phong) & (ngay_in_pd_e < df_valid_dates['Date_Out']) & (ngay_out_pd_e > df_valid_dates['Date_In'])
        if chon_idx is not None: mask_trung_e = mask_trung_e & (df_valid_dates.index != chon_idx)
        df_trung_e = df_valid_dates[mask_trung_e]
        
        if not e_khach: 
            st.error("❌ Vui lòng nhập tên khách!")
        elif e_ngay_out <= e_ngay_in: 
            st.error("❌ Ngày check-out phải lớn hơn ngày check-in!")
        elif not df_trung_e.empty and not e_bo_qua: 
            st.error("🚨 PHÁT HIỆN TRÙNG LỊCH! Đánh dấu 'Bỏ qua cảnh báo' và bấm Lưu nếu vẫn muốn tạo.")
            st.dataframe(df_trung_e[['Phòng', 'Khách', 'Ngày check in', 'Ngày check out']])
        else:
            c_phong = get_col_letter('Phòng', 'B')
            c_in = get_col_letter('Ngày check in', 'C')
            c_out = get_col_letter('Ngày check out', 'D')
            c_khach = get_col_letter('Khách', 'F')
            c_don = get_col_letter('Dọn phòng', 'G')
            c_dt_col = get_col_letter('Doanh thu', 'I')
            c_coc_col = get_col_letter('Cọc', 'J')
            c_cantt_col = get_col_letter('Cần tt', 'L') 
            c_ghi = get_col_letter('Ghi chú', 'M')
            
            if chon_idx is None: 
                col_c = sheet.col_values(3) 
                dong_moi = len(col_c) + 1
                du_lieu_luu = [
                    {'range': f'A{dong_moi}', 'values': [[dong_moi - 1]]},
                    {'range': f'{c_phong}{dong_moi}', 'values': [[e_phong]]},
                    {'range': f'{c_in}{dong_moi}', 'values': [[e_ngay_in.strftime("%d/%m/%Y")]]},
                    {'range': f'{c_out}{dong_moi}', 'values': [[e_ngay_out.strftime("%d/%m/%Y")]]},
                    {'range': f'{c_khach}{dong_moi}', 'values': [[e_khach]]},
                    {'range': f'{c_don}{dong_moi}', 'values': [[e_don]]},
                    {'range': f'{c_dt_col}{dong_moi}', 'values': [[e_dt if e_dt is not None else ""]]},
                    {'range': f'{c_coc_col}{dong_moi}', 'values': [[e_coc if e_coc is not None else ""]]},
                    {'range': f'{c_cantt_col}{dong_moi}', 'values': [[e_can_tt if e_can_tt is not None else ""]]},
                    {'range': f'{c_ghi}{dong_moi}', 'values': [[e_ghi]]},
                ]
                try:
                    sheet.batch_update(du_lieu_luu, value_input_option='USER_ENTERED')
                    st.session_state.dp_search_key = ""
                    get_raw_main.clear()
                    st.success("✅ Đã tạo lượt đặt phòng thành công!")
                    st.rerun()
                except Exception as e: st.error(f"❌ Lỗi: {e}")
            else:
                row_sheet_idx = chon_idx + 2
                data_sua = [
                    {'range': f'{c_phong}{row_sheet_idx}', 'values': [[e_phong]]},
                    {'range': f'{c_in}{row_sheet_idx}', 'values': [[e_ngay_in.strftime("%d/%m/%Y")]]},
                    {'range': f'{c_out}{row_sheet_idx}', 'values': [[e_ngay_out.strftime("%d/%m/%Y")]]},
                    {'range': f'{c_khach}{row_sheet_idx}', 'values': [[e_khach]]},
                    {'range': f'{c_don}{row_sheet_idx}', 'values': [[e_don]]},
                    {'range': f'{c_dt_col}{row_sheet_idx}', 'values': [[e_dt if e_dt is not None else ""]]},
                    {'range': f'{c_coc_col}{row_sheet_idx}', 'values': [[e_coc if e_coc is not None else ""]]},
                    {'range': f'{c_cantt_col}{row_sheet_idx}', 'values': [[e_can_tt if e_can_tt is not None else ""]]},
                    {'range': f'{c_ghi}{row_sheet_idx}', 'values': [[e_ghi]]},
                ]
                try:
                    sheet.batch_update(data_sua, value_input_option='USER_ENTERED')
                    st.session_state.dp_search_key = ""
                    get_raw_main.clear()
                    st.success("✅ Cập nhật thành công!")
                    st.rerun()
                except Exception as e: st.error(f"❌ Lỗi: {e}")

    if btn_xoa_dp:
        if not xac_nhan_xoa: 
            st.error("❌ Đánh dấu vào ô 'Xác nhận muốn xóa' để tránh thao tác nhầm!")
        else:
            row_sheet_idx = chon_idx + 2
            c_phong = get_col_letter('Phòng', 'B')
            c_in = get_col_letter('Ngày check in', 'C')
            c_out = get_col_letter('Ngày check out', 'D')
            c_khach = get_col_letter('Khách', 'F')
            c_don = get_col_letter('Dọn phòng', 'G')
            c_dt_col = get_col_letter('Doanh thu', 'I')
            c_coc_col = get_col_letter('Cọc', 'J')
            c_cantt_col = get_col_letter('Cần tt', 'L') 
            c_ghi = get_col_letter('Ghi chú', 'M')
            data_xoa = [
                {'range': f'{c_phong}{row_sheet_idx}', 'values': [['']]},
                {'range': f'{c_in}{row_sheet_idx}', 'values': [['']]},
                {'range': f'{c_out}{row_sheet_idx}', 'values': [['']]},
                {'range': f'{c_khach}{row_sheet_idx}', 'values': [['']]},
                {'range': f'{c_don}{row_sheet_idx}', 'values': [['']]},
                {'range': f'{c_dt_col}{row_sheet_idx}', 'values': [['']]},
                {'range': f'{c_coc_col}{row_sheet_idx}', 'values': [['']]},
                {'range': f'{c_cantt_col}{row_sheet_idx}', 'values': [['']]},
                {'range': f'{c_ghi}{row_sheet_idx}', 'values': [['']]},
            ]
            try:
                sheet.batch_update(data_xoa, value_input_option='USER_ENTERED')
                st.session_state.dp_search_key = ""
                get_raw_main.clear()
                st.success("✅ Đã xóa an toàn!")
                st.rerun()
            except Exception as e: st.error(f"❌ Lỗi: {e}")

# ================= 4. TAB 3: CHI PHÍ =================
with tab3:
    st.subheader("💸 Quản lý chi phí")
    
    with st.form("search_cp_form"):
        col_cp1, col_cp2, col_cp3 = st.columns([4, 1, 1])
        with col_cp1:
            cp_tu_khoa = st.text_input("Tìm theo hạng mục, ngày...", value=st.session_state.cp_search_key)
        with col_cp2:
            st.write("")
            st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
            btn_search_cp = st.form_submit_button("🔍 Tìm kiếm", use_container_width=True)
        with col_cp3:
            st.write("")
            st.markdown('<span class="btn-blue"></span>', unsafe_allow_html=True)
            btn_clear_cp = st.form_submit_button("✨ Tạo mới", use_container_width=True)
            
    if btn_clear_cp:
        st.session_state.cp_search_key = ""
        st.rerun()
    if btn_search_cp:
        st.session_state.cp_search_key = cp_tu_khoa

    cp_idx = None
    row_cp_cu = None
    
    if st.session_state.cp_search_key and not df_cp.empty:
        search_keys_cp = st.session_state.cp_search_key.lower().split()
        mask_cp = df_cp.apply(lambda row: all(kw in ' '.join(row.astype(str)).lower() for kw in search_keys_cp), axis=1)
        df_cp_kq = df_cp[mask_cp]
        if df_cp_kq.empty:
            st.warning("Không tìm thấy dữ liệu!")
        else:
            cp_options = ["--- Chọn khoản chi để sửa ---"] + [f"[{idx}] Ngày {row.get('Ngày', '')} - {row.get('Hạng mục', '')} - {format_tien_ui(parse_tien(row.get('Số tiền', '')))}" for idx, row in df_cp_kq.iterrows()]
            cp_lua_chon = st.selectbox("Kết quả:", cp_options)
            if cp_lua_chon and cp_lua_chon.startswith("["):
                cp_idx = int(cp_lua_chon.split("]")[0].replace("[", ""))
                row_cp_cu = df_cp.loc[cp_idx]

    st.markdown("---")
    st.markdown("### ✏️ Sửa chi phí" if cp_idx is not None else "### 📝 Nhập khoản chi mới")

    with st.form("form_chi_phi"):
        c_cp1, c_cp2 = st.columns(2)
        with c_cp1:
            try: e_cp_ngay_def = pd.to_datetime(row_cp_cu['Ngày'], format="%d/%m/%Y").date() if row_cp_cu is not None else date.today()
            except: e_cp_ngay_def = date.today()
            e_cp_ngay = st.date_input("Ngày chi:", value=e_cp_ngay_def)
            
            hm_val = row_cp_cu.get('Hạng mục', '') if row_cp_cu is not None else ""
            if hm_val and hm_val not in ds_hang_muc_cp:
                idx_hm = len(ds_hang_muc_cp) - 1
            else:
                idx_hm = ds_hang_muc_cp.index(hm_val) if hm_val in ds_hang_muc_cp else 0
                
            e_cp_hm_chon = st.selectbox("Hạng mục:", ds_hang_muc_cp, index=idx_hm)
            
            if e_cp_hm_chon == "Khác (Nhập tay)":
                e_cp_hm = st.text_input("Nhập hạng mục khác (bắt buộc):", value=hm_val if hm_val not in ds_hang_muc_cp else "")
            else:
                e_cp_hm = e_cp_hm_chon

        with c_cp2:
            e_cp_tien_str = st.text_input("Số tiền chi (VNĐ):", value=format_tien_ui(parse_tien(row_cp_cu.get('Số tiền', ''))) if row_cp_cu is not None else "")
            
            cp_nguon_ds = ["OCB", "Để riêng", "Bé NA tạm chi", "Duti tạm chi"]
            def_cp_nguon = cp_nguon_ds.index(row_cp_cu.get('Nguồn tiền', '')) if row_cp_cu is not None and row_cp_cu.get('Nguồn tiền', '') in cp_nguon_ds else 0
            e_cp_nguon = st.selectbox("Nguồn tiền:", cp_nguon_ds, index=def_cp_nguon)

        st.markdown("<br>", unsafe_allow_html=True)
        
        if cp_idx is None:
            st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
            btn_luu_cp = st.form_submit_button("Lưu")
            btn_xoa_cp = False
            xac_nhan_cp_xoa = False
        else:
            c_btn_cp1, c_btn_cp2, c_btn_cp3 = st.columns([1, 1, 1.5])
            with c_btn_cp1:
                st.markdown('<span class="btn-green"></span>', unsafe_allow_html=True)
                btn_luu_cp = st.form_submit_button("Lưu")
            with c_btn_cp2:
                st.markdown('<span class="btn-red"></span>', unsafe_allow_html=True)
                btn_xoa_cp = st.form_submit_button("🗑️ Xóa")
            xac_nhan_cp_xoa = c_btn_cp3.checkbox("⚠️ Xác nhận muốn xóa khoản này")
            
    if sheet_cp is None and (btn_luu_cp or btn_xoa_cp):
        st.error("🚨 Không tìm thấy dữ liệu sheet 'Chi phí'.")
    else:
        if btn_luu_cp:
            if not e_cp_hm: 
                st.error("❌ Vui lòng điền hạng mục chi phí!")
            else:
                e_cp_tien = parse_tien(e_cp_tien_str)
                if cp_idx is None: 
                    col_c = sheet_cp.col_values(3) 
                    dong_moi_cp = len(col_c) + 1
                    data_luu_cp = [{'range': f'C{dong_moi_cp}:F{dong_moi_cp}', 'values': [[e_cp_ngay.strftime("%d/%m/%Y"), e_cp_hm, e_cp_tien if e_cp_tien is not None else "", e_cp_nguon]]}]
                    try:
                        sheet_cp.batch_update(data_luu_cp, value_input_option='USER_ENTERED')
                        st.session_state.cp_search_key = ""
                        get_raw_cp.clear()
                        st.success("✅ Đã ghi nhận chi phí thành công!")
                        st.rerun()
                    except Exception as e: st.error(f"❌ Lỗi: {e}")
                else: 
                    row_cp_sheet_idx = cp_idx + 2
                    data_sua_cp = [{'range': f'C{row_cp_sheet_idx}:F{row_cp_sheet_idx}', 'values': [[e_cp_ngay.strftime("%d/%m/%Y"), e_cp_hm, e_cp_tien if e_cp_tien is not None else "", e_cp_nguon]]}]
                    try:
                        sheet_cp.batch_update(data_sua_cp, value_input_option='USER_ENTERED')
                        st.session_state.cp_search_key = ""
                        get_raw_cp.clear()
                        st.success("✅ Sửa xong chi phí!")
                        st.rerun()
                    except Exception as e: st.error(f"❌ Lỗi: {e}")

        if btn_xoa_cp:
            if not xac_nhan_cp_xoa: 
                st.error("❌ Vui lòng tick xác nhận xóa!")
            else:
                row_cp_sheet_idx = cp_idx + 2
                data_xoa_cp = [{'range': f'C{row_cp_sheet_idx}:F{row_cp_sheet_idx}', 'values': [['', '', '', '']]}]
                try:
                    sheet_cp.batch_update(data_xoa_cp, value_input_option='USER_ENTERED')
                    st.session_state.cp_search_key = ""
                    get_raw_cp.clear()
                    st.success("✅ Đã xóa!")
                    st.rerun()
                except Exception as e: st.error(f"❌ Lỗi: {e}")
