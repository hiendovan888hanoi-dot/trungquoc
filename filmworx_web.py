import streamlit as st
import requests
import hashlib
import time
import re
import os
import zipfile
from urllib.parse import urljoin
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError:
    pass

st.set_page_config(page_title="Filmworx Downloader Web", page_icon="🎬", layout="wide")

st.markdown("""

<style>
    /* Hiệu ứng Fade-in nhanh (0.3s) để không gây cảm giác đơ */
    @keyframes fadeInFast {
        0% { opacity: 0; transform: translateY(5px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    .block-container {
        animation: fadeInFast 0.3s ease-out;
    }
    
    /* Hover effects for Movie Images */
    div[data-testid="stImage"] img {
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        border-radius: 8px;
    }
    div[data-testid="stImage"] img:hover {
        transform: scale(1.03);
        box-shadow: 0 10px 20px rgba(0, 242, 254, 0.2);
    }
    
    /* Progress Bar Animation & Styling */
    div[data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, #00f2fe, #4facfe, #00f2fe);
        background-size: 200% 100%;
        animation: gradientMove 2s linear infinite;
        border-radius: 10px;
    }
    @keyframes gradientMove {
        0% { background-position: 100% 0; }
        100% { background-position: -100% 0; }
    }
    
    /* Button styling (Subtle glow) */
    button[kind="primary"] {
        transition: all 0.3s ease;
    }
    button[kind="primary"]:hover {
        box-shadow: 0 0 15px rgba(0, 242, 254, 0.4);
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

VOD_BASE_URL = "https://video-file.filmworx.cn"
IMG_BASE_URL = "https://gnmj-file.filmworx.cn"
BASE_API = "https://app.filmworx.cn/api/app"

# ================= CẤU HÌNH CỦA BẠN =================
# Cứ mỗi khi token hết hạn, ông sửa trực tiếp trên file này nhé!
DEFAULT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMjcwNDY5NSIsImV4cCI6MTc4MjQ0Mjk1MX0.En2gnqW5M4NIOdx59fzZ3qgxKLrdigQcDFC9AKfIH34"
def get_user_id(token):
    try:
        import base64, json
        payload = token.split('.')[1]
        payload += '=' * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return int(data.get('sub') or data.get('uid') or 22704695)
    except: return 22704695

USER_ID = get_user_id(DEFAULT_TOKEN)
# ====================================================

if "view_mode" not in st.session_state:
    st.session_state.view_mode = "home"
if "selected_movie_id" not in st.session_state:
    st.session_state.selected_movie_id = None
if "selected_movie_title" not in st.session_state:
    st.session_state.selected_movie_title = ""

def generate_sign(params, user_id):
    user_id_str = str(user_id)
    raw_str = user_id_str
    for key in sorted(params.keys()):
        val = params[key]
        if key and val is not None and str(val) != "" and key != "sign":
            raw_str += f"{key}{val}"
    raw_str += user_id_str
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

def get_auth_headers(token=DEFAULT_TOKEN):
    return {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 TMA/2.1.0",
        "Referer": "https://tmaservice.developer.toutiao.com/?appid=tt0abe7c0395b0a48101&version=0.0.10",
        "Authorization": f"Bearer {token.strip()}" if token else "",
        "Host": "app.filmworx.cn"
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_cached_api(url, params, _headers, proxy_url):
    import requests
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    return requests.get(url, params=params, headers=_headers, proxies=proxies, timeout=30, verify=False).json()

def get_guest_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 TMA/2.1.0",
        "Referer": "https://tmaservice.developer.toutiao.com/?appid=tt0abe7c0395b0a48101&version=0.0.10",
        "Host": "app.filmworx.cn"
    }

st.sidebar.title("⚙️ Cấu Hình")
proxy = st.sidebar.text_input("Proxy Trung Quốc", placeholder="http://ip:port", help="Bắt buộc dùng để lách luật!")
token = DEFAULT_TOKEN

if "api_session" not in st.session_state:
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.trust_env = False  # Bỏ qua system proxy để tránh lag
    st.session_state.api_session = s

session = st.session_state.api_session
if proxy:
    session.proxies = {"http": proxy, "https": proxy}

if st.session_state.view_mode == "home":
    st.title("🎬 Danh Sách Phim Mới Nhất")
    
    with st.spinner("Đang lấy danh sách phim..."):
        try:
            url = f"{BASE_API}/series/list"
            params = {"page": 1, "size": 20, "timestamp": int(time.time()), "user_id": USER_ID}
            params["sign"] = generate_sign(params, USER_ID)
            res = session.get(url, params=params, headers=get_auth_headers(token), timeout=15, verify=False)
            if res.status_code == 200:
                data = res.json()
                if data.get("code") in [0, 200]:
                    movies = data.get("data", {}).get("list", [])
                    
                    if not movies:
                        st.warning("Không lấy được danh sách phim, hãy kiểm tra lại Proxy!")
                    
                    # Create grid 4 columns
                    cols = st.columns(4)
                    for i, movie in enumerate(movies):
                        col = cols[i % 4]
                        with col:
                            with st.container(border=True):
                                title = movie.get('title', 'Unknown')
                                img_path = movie.get('cover_url', '')
                                full_img = img_path if img_path.startswith("http") else f"{IMG_BASE_URL}/{img_path}"
                                m_id = str(movie.get('id', ''))
                                
                                st.image(full_img, use_column_width=True)
                                st.markdown(f"**{title}**")
                                st.caption(f"ID: {m_id}")
                                
                                if st.button(f"Tải phim này", key=f"btn_{m_id}", use_container_width=True):
                                    st.session_state.selected_movie_id = m_id
                                    st.session_state.selected_movie_title = title
                                    st.session_state.view_mode = "detail"
                                    st.rerun()
                else:
                    err_msg = data.get("msg") or data.get("message") or str(data)
                    st.error(f"Lỗi API: {err_msg}")
            else:
                st.error("Không thể kết nối đến máy chủ Filmworx. Vui lòng bật Proxy.")
        except Exception as e:
            st.error(f"Lỗi mạng: {e}")

elif st.session_state.view_mode == "detail":
    if st.button("⬅ Quay lại danh sách"):
        st.session_state.view_mode = "home"
        st.rerun()
        
    m_id = st.session_state.selected_movie_id
    m_title = st.session_state.selected_movie_title
    st.title(f"📺 Đang chọn: {m_title}")
    
    with st.spinner("Đang lấy dữ liệu phim..."):
        headers = get_auth_headers(token)
        try:
            # 1. Lấy tổng số tập phim
            total_eps_params = {"series_id": int(m_id)}
            total_eps_params["sign"] = generate_sign(total_eps_params, USER_ID)
            r_total = fetch_cached_api(f"{BASE_API}/video/total_episodes", total_eps_params, headers, proxy)
            
            if r_total.get("code") == 200:
                total_episodes = r_total.get("data", {}).get("total_episodes", 0)
                
                # Lấy thêm thông tin giờ cập nhật
                detail_params = {"timestamp": int(time.time()), "user_id": USER_ID}
                detail_params["sign"] = generate_sign(detail_params, USER_ID)
                r_detail = fetch_cached_api(f"{BASE_API}/series/detail/{m_id}", detail_params, headers, proxy)
                update_time = r_detail.get("data", {}).get("daily_update_time", "N/A") if r_detail.get("code") == 200 else "N/A"
                
                st.info(f"Tổng cộng: {total_episodes} tập | Giờ cập nhật: {update_time}")
                
                batch_eps = []
                if total_episodes > 0:
                    # Chia thành các batch (mỗi batch 30 tập giống bản Python GUI)
                    batch_size = 30
                    total_batches = (total_episodes + batch_size - 1) // batch_size
                    
                    batch_options = [f"Tập {i*batch_size + 1} - {min((i+1)*batch_size, total_episodes)}" for i in range(total_batches)]
                    
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        selected_batch = st.selectbox("Hiển thị danh sách:", batch_options)
                    
                    batch_idx = batch_options.index(selected_batch)
                    start_episode = batch_idx * batch_size + 1
                    end_episode = min((batch_idx + 1) * batch_size, total_episodes)
                    
                    # 2. Gọi API lấy đúng danh sách tập của trang hiện tại
                    list_params = {"series_id": int(m_id), "start_episode": start_episode, "end_episode": end_episode}
                    list_params["sign"] = generate_sign(list_params, USER_ID)
                    r_list = fetch_cached_api(f"{BASE_API}/video/v2/list", list_params, headers, proxy)
                    
                    if r_list.get("code") in [0, 200] and "data" in r_list:
                        batch_eps = r_list["data"].get("list", [])
                        
                        if batch_eps:
                            # Sắp xếp lại danh sách từ tập 1 -> N (vì API đôi khi trả về ngược)
                            batch_eps = sorted(batch_eps, key=lambda x: x.get("episode", 0))
                            
                            # Tạo bảng danh sách tập
                            import pandas as pd
                            df = pd.DataFrame([
                                {
                                    "Tập": ep.get("episode"), 
                                    "Link M3U8": f"{VOD_BASE_URL}{ep.get('video_url', '')}" if ep.get("video_url") else "N/A"
                                } 
                                for ep in batch_eps
                            ])
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.warning("Trang này không có tập phim nào. Hãy thử chọn trang khác.")
                    else:
                        st.error(f"Lỗi tải danh sách tập: {r_list.get('msg') or str(r_list)}")
            else:
                st.error(f"Lỗi tải tổng số tập: {r_total.get('msg') or str(r_total)}")
                
            st.markdown("---")
            ep_range = st.text_input("📥 Chọn tập tải (vd: 1-5, hoặc để trống sẽ tải toàn bộ batch đang hiển thị ở trên)", placeholder="Ví dụ: 1-5")
            
            if st.button("Bắt đầu Tải & Nén ZIP", type="primary"):
                selected_eps = batch_eps
                if ep_range and "-" in ep_range:
                    s, e = map(int, ep_range.split("-"))
                    selected_eps = [ep for ep in batch_eps if s <= ep.get("episode", 0) <= e]
                    
                st.write(f"Đang tải {len(selected_eps)} tập...")
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                out_dir = f"Downloads_Phim_{m_id}"
                os.makedirs(out_dir, exist_ok=True)
                
                for idx, ep in enumerate(selected_eps):
                    ep_num = ep.get("episode")
                    raw_url = ep.get("video_url")
                    if not raw_url: continue
                    
                    m3u8_url = f"{VOD_BASE_URL}{raw_url if raw_url.startswith('/') else '/'+raw_url}"
                    out_file = os.path.join(out_dir, f"Tap_{ep_num:03d}.mp4")
                    
                    status_text.text(f"Đang tải Tập {ep_num}...")
                    
                    try:
                        r_ts = session.get(m3u8_url, headers=headers, timeout=30, verify=False)
                        if r_ts.status_code != 200: continue
                        text = r_ts.text
                        
                        if "#EXT-X-STREAM-INF" in text:
                            lines = text.splitlines()
                            best = None; max_bw = -1
                            for i, l in enumerate(lines):
                                if l.startswith("#EXT-X-STREAM-INF"):
                                    bw = int(re.search(r'BANDWIDTH=(\d+)', l).group(1)) if 'BANDWIDTH' in l else 0
                                    if i+1 < len(lines) and bw > max_bw:
                                        max_bw = bw; best = lines[i+1].strip()
                            if best:
                                m3u8_url = urljoin(m3u8_url, best)
                                text = session.get(m3u8_url, headers=headers, timeout=30, verify=False).text

                        aes_key = None; aes_iv = None
                        for line in text.splitlines():
                            if line.startswith("#EXT-X-KEY:"):
                                if "METHOD=AES-128" in line:
                                    uri_match = re.search(r'URI="([^"]+)"', line)
                                    if uri_match:
                                        key_url = uri_match.group(1)
                                        if not key_url.startswith("http"): key_url = urljoin(m3u8_url, key_url)
                                        key_res = session.get(key_url, headers=headers, timeout=30, verify=False)
                                        if key_res.status_code == 200: aes_key = key_res.content
                                    iv_match = re.search(r'IV=0x([0-9a-fA-F]+)', line)
                                    if iv_match: aes_iv = bytes.fromhex(iv_match.group(1))

                        ts_links = [urljoin(m3u8_url, l.strip()) for l in text.splitlines() if l.strip() and not l.startswith('#')]
                        if not ts_links: continue
                        
                        def download_ts(i, ts_url, aes_key, aes_iv):
                            try:
                                ts_res = session.get(ts_url, headers=headers, timeout=30, verify=False)
                                if ts_res.status_code == 200:
                                    data_ts = ts_res.content
                                    if aes_key:
                                        try:
                                            iv = aes_iv if aes_iv else i.to_bytes(16, 'big')
                                            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
                                            data_ts = cipher.decryptor().update(data_ts)
                                        except: pass
                                    return data_ts
                            except: pass
                            return None

                        import concurrent.futures
                        with open(out_file, "wb") as f_out:
                            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                                futures = [executor.submit(download_ts, i, url, aes_key, aes_iv) for i, url in enumerate(ts_links)]
                                for fut in futures:
                                    data = fut.result()
                                    if data:
                                        f_out.write(data)
                        
                    except Exception as e:
                        st.error(f"Lỗi Tập {ep_num}: {e}")
                    
                    progress_bar.progress((idx + 1) / len(selected_eps))
                    
                if len(selected_eps) == 1:
                    status_text.text("Đang chuẩn bị file video...")
                    ep_num = selected_eps[0].get("episode")
                    single_file_path = os.path.join(out_dir, f"Tap_{ep_num:03d}.mp4")
                    st.success("Tải hoàn tất!")
                    with open(single_file_path, "rb") as f:
                        st.download_button(f"Tải Tập {ep_num} về máy", f, file_name=f"Phim_{m_id}_Tap_{ep_num:03d}.mp4", mime="video/mp4")
                else:
                    status_text.text("Đang nén file ZIP...")
                    zip_path = f"Phim_{m_id}.zip"
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, _, files in os.walk(out_dir):
                            for file in files:
                                zipf.write(os.path.join(root, file), arcname=file)
                                
                    st.success("Tải hoàn tất!")
                    with open(zip_path, "rb") as f:
                        st.download_button("Tải File ZIP về máy", f, file_name=zip_path, mime="application/zip")
        except Exception as e:
            st.error(f"Lỗi mạng: {e}")
