import streamlit as st
import googleapiclient.discovery
from googleapiclient.errors import HttpError # Thêm thư viện bắt lỗi
import statistics
from datetime import datetime, timedelta, timezone
import dateutil.parser
import pandas as pd

# ==========================================
# 🎨 CẤU HÌNH GIAO DIỆN
# ==========================================
st.set_page_config(
    page_title="YouTube Market Reality Check",
    page_icon="🛡️", # Icon khiên bảo vệ (Multi-Key)
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
    .stProgress > div > div > div > div {background-color: #ff4b4b;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔧 CLASS QUẢN LÝ KEY (KEY MANAGER)
# ==========================================
class YouTubeKeyManager:
    def __init__(self, key_list):
        # Lọc bỏ dòng trống và khoảng trắng thừa
        self.keys = [k.strip() for k in key_list if k.strip()]
        self.current_index = 0
        self.service = None
        self._build_service()

    def _build_service(self):
        """Tạo đối tượng YouTube service với key hiện tại"""
        if not self.keys:
            self.service = None
            return
        
        current_key = self.keys[self.current_index]
        try:
            self.service = googleapiclient.discovery.build(
                "youtube", "v3", developerKey=current_key, cache_discovery=False
            )
            # print(f"-> Đang dùng Key #{self.current_index + 1}: {current_key[:5]}...")
        except Exception as e:
            # Nếu build thất bại (key sai format), thử key tiếp theo ngay
            self.rotate_key()

    def rotate_key(self):
        """Chuyển sang key tiếp theo. Trả về False nếu hết key."""
        self.current_index += 1
        if self.current_index >= len(self.keys):
            return False # Hết sạch key
        
        self._build_service()
        return True

    def execute_safe(self, request_builder_func):
        """
        Hàm bao bọc (Wrapper) để thực thi request.
        Nếu gặp lỗi Quota -> Tự động đổi key và thử lại.
        request_builder_func: Là hàm nhận vào 'service' và trả về 'request object'.
        """
        while True:
            if not self.service:
                raise Exception("Không có API Key nào hợp lệ hoặc đã hết sạch Key!")

            try:
                # Tạo request từ service hiện tại
                request = request_builder_func(self.service)
                # Thực thi
                return request.execute()
            
            except HttpError as e:
                # Kiểm tra xem có phải lỗi Hết Quota (403) không
                error_reason = e.resp.get('status')
                if error_reason == '403' and 'quotaExceeded' in str(e):
                    st.toast(f"⚠️ Key #{self.current_index + 1} hết xăng! Đang đổi Key...", icon="🔄")
                    print("Quota Exceeded. Rotating key...")
                    
                    if not self.rotate_key():
                        st.error("❌ TẤT CẢ KEY ĐỀU ĐÃ HẾT HẠN MỨC! Vui lòng thêm Key mới.")
                        raise e # Hết key cứu rồi, throw lỗi ra ngoài
                    
                    # Nếu đổi key thành công, vòng lặp while sẽ chạy lại từ đầu với service mới
                    continue
                else:
                    # Lỗi khác (không phải quota) thì throw luôn
                    raise e

# ==========================================
# 🧠 CORE LOGIC (v23.0 - MULTI-KEY SUPPORT)
# ==========================================

def analyze_reality(key_list, keyword, time_frame, duration, sort_by, filter_type, limit):
    try:
        # Khởi tạo Quản lý Key
        key_manager = YouTubeKeyManager(key_list)
        if not key_manager.keys:
            st.warning("Danh sách Key trống!")
            return None

        # 1. Cấu hình thời gian
        time_map = {'hour': 1/24, 'today': 1, 'week': 7, 'month': 30, 'year': 365, 'any': 3650}
        days_back = time_map.get(time_frame, 7)
        now_utc = datetime.now(timezone.utc)
        
        published_after = None
        if time_frame != 'any':
            date_limit = now_utc - timedelta(days=days_back)
            published_after = date_limit.isoformat().replace("+00:00", "Z")

        status_text = st.empty()
        progress_bar = st.progress(0)

        # ---------------------------------------------------------
        # BƯỚC 1: QUÉT THỰC TẾ (MULTI-KEY SAFE)
        # ---------------------------------------------------------
        status_text.text(f"🔍 Đang lật từng trang (Max: {limit})...")
        
        video_pool = []
        next_page_token = None
        hit_limit = False 
        
        while True:
            if len(video_pool) >= limit: 
                hit_limit = True
                break

            # Định nghĩa hàm tạo request (để key manager có thể tái tạo khi đổi key)
            def build_search_request(service):
                params = {
                    "q": keyword, "type": filter_type, "part": "id,snippet", 
                    "maxResults": 50, "order": sort_by, "pageToken": next_page_token
                }
                if published_after: params["publishedAfter"] = published_after
                if filter_type == 'video' and duration != 'any': params["videoDuration"] = duration
                return service.search().list(**params)

            # GỌI QUA HÀM AN TOÀN
            res = key_manager.execute_safe(build_search_request)
            
            items = res.get('items', [])
            if not items: break 
            
            for item in items:
                if filter_type == 'video': video_pool.append(item['id']['videoId'])
                elif filter_type == 'channel': video_pool.append(item['id']['channelId'])
                elif filter_type == 'playlist': video_pool.append(item['id']['playlistId'])
            
            progress_bar.progress(min(len(video_pool) / limit, 0.9))
            
            next_page_token = res.get('nextPageToken')
            if not next_page_token: break

        real_count = len(video_pool)

        if real_count == 0:
            st.error(f"⚠️ KHÔNG TÌM THẤY KẾT QUẢ NÀO!")
            return None

        if filter_type != 'video':
            return {"type": filter_type, "count": real_count, "hit_limit": hit_limit, "data": [{"ID": i} for i in video_pool]}

        # ---------------------------------------------------------
        # BƯỚC 2: PHÂN TÍCH CHI TIẾT (MULTI-KEY SAFE)
        # ---------------------------------------------------------
        status_text.text("📈 Đang phân tích chỉ số chi tiết...")
        
        ids_to_analyze = video_pool[:50]
        
        # Hàm lấy video
        def build_videos_request(service):
            return service.videos().list(part="snippet,statistics", id=','.join(ids_to_analyze))
        
        res_vid = key_manager.execute_safe(build_videos_request)
        
        # Hàm lấy channel
        ch_ids = [i['snippet']['channelId'] for i in res_vid['items']]
        def build_channels_request(service):
            return service.channels().list(part="statistics", id=','.join(ch_ids))
            
        res_ch = key_manager.execute_safe(build_channels_request)
        
        ch_map = {i['id']: (int(i['statistics']['subscriberCount']) if not i['statistics']['hiddenSubscriberCount'] else 0) for i in res_ch['items']}

        video_data = []
        all_views = []
        all_like_rates = []
        competitor_subs = []
        sharks = 0; guppies = 0

        order_map = {vid_id: i for i, vid_id in enumerate(ids_to_analyze)}

        for item in res_vid['items']:
            stat = item['statistics']
            snip = item['snippet']
            v_id = item['id']
            
            views = int(stat.get('viewCount', 0))
            likes = int(stat.get('likeCount', 0))
            cmts = int(stat.get('commentCount', 0))
            subs = ch_map.get(snip['channelId'], 0)
            
            try:
                pub = dateutil.parser.isoparse(snip['publishedAt'])
                diff = now_utc - pub
                if diff.days > 0: age = f"{diff.days}d"
                else: age = f"{diff.seconds//3600}h"
            except: age = "?"
            
            l_rate = (likes / views * 100) if views > 0 else 0
            c_rate = (cmts / views * 100) if views > 0 else 0
            
            all_views.append(views)
            all_like_rates.append(l_rate)
            if subs > 0: competitor_subs.append(subs)
            
            c_type = "🐟 Cá"
            if subs > 500000: c_type = "🦈 Cá Mập"; sharks += 1
            elif subs < 10000 and subs > 0: c_type = "🦐 Tôm"; guppies += 1
            elif subs > 100000: c_type = "🐳 Cá Voi"
            
            video_data.append({
                'Rank': order_map.get(v_id, 999) + 1,
                'Loại': c_type,
                'Tiêu đề': snip['title'],
                'View': views,
                'Tuổi': age,
                '% Like': round(l_rate, 2),
                '% Cmt': round(c_rate, 2),
                'Sub Kênh': subs,
                'Link Video': f"https://youtu.be/{v_id}",
                'Link Kênh': f"https://www.youtube.com/channel/{snip['channelId']}"
            })

        video_data.sort(key=lambda x: x['Rank'])

        # ---------------------------------------------------------
        # BƯỚC 3: KẾT LUẬN
        # ---------------------------------------------------------
        progress_bar.progress(1.0)
        status_text.text("✅ Hoàn tất!")
        
        # Metrics Calculation (Giữ nguyên logic v22)
        videos_per_unit = real_count / max(1, days_back)
        
        sat_score = 0; sat_msg = ""; 
        if hit_limit or videos_per_unit > 40: sat_score = 60; sat_msg = "🔴 BÃO HÒA"
        elif videos_per_unit > 10: sat_score = 30; sat_msg = "🟠 CẠNH TRANH"
        elif videos_per_unit < 1: sat_score = -10; sat_msg = "🟢 KHAN HIẾM"
        else: sat_score = 10; sat_msg = "🟡 TRUNG BÌNH"

        avg_subs = statistics.median(competitor_subs) if competitor_subs else 0
        comp_score = 0
        if avg_subs > 500000: comp_score = 40
        elif avg_subs > 100000: comp_score = 30
        elif avg_subs > 10000: comp_score = 10
        comp_score += (sharks * 2) - (guppies * 2)
        
        final_diff = max(0, min(100, comp_score + sat_score))
        total_market_volume = sum(all_views)
        avg_views = statistics.median(all_views) if all_views else 0
        avg_like_bm = statistics.median(all_like_rates) if all_like_rates else 0
        
        return {
            "type": "video", "score": final_diff, "supply": videos_per_unit, "supply_msg": sat_msg,
            "count": real_count, "hit_limit": hit_limit, "avg_sub": avg_subs,
            "sharks": sharks, "guppies": guppies, "total_vol": total_market_volume,
            "avg_view": avg_views, "avg_like": avg_like_bm, "data": video_data,
            "active_key_idx": key_manager.current_index + 1 # Báo xem đang dùng key nào
        }
        
    except Exception as e:
        st.error(f"Lỗi không xác định: {e}")
        return None

# ==========================================
# UI SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ CẤU HÌNH")
    
    # THAY ĐỔI: Text Area để nhập nhiều Key
    api_keys_input = st.text_area(
        "🔑 Danh sách API Key", 
        height=100,
        placeholder="Dán mỗi Key một dòng:\nAIzaSy...\nAIzaSy...",
        help="Nhập nhiều Key. Nếu Key 1 hết hạn mức, Tool sẽ tự động dùng Key 2."
    )
    
    keyword = st.text_input("🔎 Keyword", value="Bóng đá")
    st.divider()
    
    time_labels = {"hour": "1 giờ qua", "today": "Hôm nay", "week": "Tuần này", "month": "Tháng này", "year": "Năm nay", "any": "Mọi lúc"}
    time_frame = st.selectbox("🗓️ Thời gian", options=list(time_labels.keys()), format_func=lambda x: time_labels[x], index=1)
    
    filter_type_labels = {"video": "Video", "channel": "Kênh", "playlist": "Playlist"}
    filter_type = st.selectbox("📂 Loại", options=list(filter_type_labels.keys()), format_func=lambda x: filter_type_labels[x], index=0)

    if filter_type == 'video':
        dur_labels = {"short": "< 4 phút", "medium": "4 - 20 phút", "long": "> 20 phút", "any": "Bất kỳ"}
        duration = st.selectbox("⏳ Độ dài", options=list(dur_labels.keys()), format_func=lambda x: dur_labels[x], index=2)
    else:
        duration = 'any'
        
    sort_labels = {"viewCount": "Lượt xem (View)", "relevance": "Liên quan", "date": "Ngày tải lên", "rating": "Đánh giá"}
    sort_by = st.selectbox("📶 Xếp theo", options=list(sort_labels.keys()), format_func=lambda x: sort_labels[x], index=0)
    
    limit = st.slider("🚧 Giới hạn quét", 50, 1000, 200, step=50)
    
    btn_run = st.button("🚀 PHÂN TÍCH", type="primary", use_container_width=True)

# ==========================================
# UI MAIN
# ==========================================
st.title("🛡️ Market Reality Check (Multi-Key)")
st.markdown("---")

if btn_run:
    if not api_keys_input.strip():
        st.warning("Vui lòng nhập ít nhất 1 API Key!")
    else:
        # Tách chuỗi thành list key
        key_list = api_keys_input.strip().split('\n')
        
        result = analyze_reality(key_list, keyword, time_frame, duration, sort_by, filter_type, limit)
        
        if result:
            if result['type'] != 'video':
                st.info(f"Tìm thấy {result['count']} kết quả.")
            else:
                # --- METRICS ---
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.metric("🔥 ĐỘ KHÓ", f"{result['score']}/100")
                    st.progress(result['score']/100)
                    st.caption(f"Đang dùng Key #{result['active_key_idx']}") # Hiện key đang dùng

                with c2:
                    count_display = f"{result['count']}"
                    if result['hit_limit']:
                        count_display += "+"
                        msg = f"Chạm trần {limit}"
                    else:
                        msg = "Tổng thực tế hiển thị"
                    st.metric("📦 Video Hiển Thị", count_display, delta=result['supply_msg'], delta_color="inverse")
                    st.caption(msg)

                with c3:
                    st.metric("💰 Volume (Top List)", f"{result['total_vol']:,.0f}")
                    st.caption(f"View TB: {result['avg_view']:,.0f}")
                
                st.divider()

                # --- COMPETITORS ---
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("🦈 Cá Mập", result['sharks'])
                col2.metric("🦐 Tôm Tép", result['guppies'])
                col3.metric("Sub TB", f"{result['avg_sub']:,.0f}")
                col4.metric("👍 % Like", f"{result['avg_like']:.2f}%")
                
                # --- DATAFRAME ---
                st.subheader(f"🏆 Danh sách hiển thị ({time_labels[time_frame]} | {sort_labels[sort_by]})")
                
                df = pd.DataFrame(result['data'])
                def highlight_viral(row):
                    color = ''
                    if row['Sub Kênh'] > 0 and row['View'] > row['Sub Kênh'] * 2:
                        color = 'background-color: #d4edda' 
                    return [color] * len(row)

                st.dataframe(
                    df.style.apply(highlight_viral, axis=1),
                    column_config={
                        "Link Video": st.column_config.LinkColumn("Xem"),
                        "Link Kênh": st.column_config.LinkColumn("Kênh"),
                        "View": st.column_config.NumberColumn(format="%d"),
                        "Sub Kênh": st.column_config.NumberColumn(format="%d"),
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=600
                )
