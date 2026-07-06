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

VOD_BASE_URL = "https://video-file.filmworx.cn"
IMG_BASE_URL = "https://gnmj-file.filmworx.cn"
BASE_API = "https://app.filmworx.cn/api/app"

# ================= CẤU HÌNH CỦA BẠN =================
DEFAULT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMjcwNDY5NSIsImV4cCI6MTc4MjQ0Mjk1MX0.En2gnqW5M4NIOdx59fzZ3qgxKLrdigQcDFC9AKfIH34"
USER_ID = 22704695
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

def get_guest_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 TMA/2.1.0",
        "Referer": "https://tmaservice.developer.toutiao.com/?appid=tt0abe7c0395b0a48101&version=0.0.10",
        "Host": "app.filmworx.cn"
    }

st.sidebar.title("⚙️ Cấu Hình")
proxy = st.sidebar.text_input("Proxy Trung Quốc", placeholder="http://ip:port", help="Bắt buộc dùng để lách luật!")
token = DEFAULT_TOKEN

session = requests.Session()
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
                            title = movie.get('title', 'Unknown')
                            img_path = movie.get('cover_url', '')
                            full_img = img_path if img_path.startswith("http") else f"{IMG_BASE_URL}/{img_path}"
                            m_id = str(movie.get('id', ''))
                            
                            st.image(full_img, use_column_width=True)
                            st.markdown(f"**{title}**")
                            st.caption(f"Trạng thái: {movie.get('status', 'N/A')} | Tập: {movie.get('total', 0)}")
                            
                            if st.button(f"Tải phim này", key=f"btn_{m_id}"):
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
    
    with st.spinner("Đang lấy danh sách tập..."):
        headers = get_auth_headers(token)
        try:
            params = {"series_id": int(m_id), "page": 1, "size": 200, "timestamp": int(time.time()), "user_id": USER_ID}
            params["sign"] = generate_sign(params, USER_ID)
            r = session.get(f"{BASE_API}/video/v2/list", params=params, headers=headers, timeout=30, verify=False).json()
            
            if r.get("code") == 0 and "data" in r:
                eps = r["data"].get("list", [])
                st.info(f"Tìm thấy {len(eps)} tập.")
                
                ep_range = st.text_input("Chọn tập tải (vd: 1-5, hoặc để trống tải hết)", placeholder="1-5")
                
                if st.button("Bắt đầu Tải & Nén ZIP", type="primary"):
                    selected_eps = eps
                    if ep_range and "-" in ep_range:
                        s, e = map(int, ep_range.split("-"))
                        selected_eps = [ep for ep in eps if s <= ep.get("episode", 0) <= e]
                        
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
                            
                            with open(out_file, "wb") as f_out:
                                for i, ts_url in enumerate(ts_links):
                                    ts_res = session.get(ts_url, headers=headers, timeout=30, verify=False)
                                    if ts_res.status_code == 200:
                                        data_ts = ts_res.content
                                        if aes_key:
                                            try:
                                                iv = aes_iv if aes_iv else i.to_bytes(16, 'big')
                                                cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
                                                data_ts = cipher.decryptor().update(data_ts)
                                            except: pass
                                        f_out.write(data_ts)
                            
                        except Exception as e:
                            st.error(f"Lỗi Tập {ep_num}: {e}")
                        
                        progress_bar.progress((idx + 1) / len(selected_eps))
                        
                    status_text.text("Đang nén file ZIP...")
                    zip_path = f"Phim_{m_id}.zip"
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, _, files in os.walk(out_dir):
                            for file in files:
                                zipf.write(os.path.join(root, file), arcname=file)
                                
                    st.success("Tải hoàn tất!")
                    with open(zip_path, "rb") as f:
                        st.download_button("Tải File ZIP về máy", f, file_name=zip_path, mime="application/zip")
            else:
                st.error(f"Lỗi: {r.get('message', r)}")
        except Exception as e:
            st.error(f"Lỗi mạng: {e}")
