import streamlit as st
import googleapiclient.discovery
import statistics
from datetime import datetime, timedelta, timezone
import dateutil.parser
import pandas as pd

# ==========================================
# 🎨 CẤU HÌNH GIAO DIỆN
# ==========================================
st.set_page_config(
    page_title="YouTube Market Reality Check",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Tùy chỉnh
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
    .stProgress > div > div > div > div {background-color: #ff4b4b;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 CORE LOGIC (v22.0 - REALITY CHECK)
# ==========================================

def analyze_reality(api_key, keyword, time_frame, duration, sort_by, filter_type, limit):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
        
        # 1. Cấu hình thời gian
        time_map = {
            'hour': 1/24, 'today': 1, 'week': 7, 'month': 30, 'year': 365, 'any': 3650
        }
        days_back = time_map.get(time_frame, 7)
        now_utc = datetime.now(timezone.utc)
        
        published_after = None
        if time_frame != 'any':
            date_limit = now_utc - timedelta(days=days_back)
            published_after = date_limit.isoformat().replace("+00:00", "Z")

        status_text = st.empty()
        progress_bar = st.progress(0)

        # ---------------------------------------------------------
        # BƯỚC 1: QUÉT THỰC TẾ (LẬT TRANG ĐẾN KHI HẾT HOẶC CHẠM TRẦN)
        # ---------------------------------------------------------
        status_text.text(f"🔍 Đang lật từng trang kết quả (Max Limit: {limit})...")
        
        video_pool = []
        next_page_token = None
        hit_limit = False 
        
        while True:
            # Kiểm tra trần
            if len(video_pool) >= limit: 
                hit_limit = True
                break

            # Cấu hình search TUÂN THỦ TUYỆT ĐỐI USER
            search_params = {
                "q": keyword, 
                "type": filter_type, 
                "part": "id,snippet", 
                "maxResults": 50,
                "order": sort_by, # Sắp xếp y hệt bạn muốn (View/Relevance/Date)
                "pageToken": next_page_token
            }
            if published_after: search_params["publishedAfter"] = published_after
            if filter_type == 'video' and duration != 'any': search_params["videoDuration"] = duration

            req = youtube.search().list(**search_params)
            res = req.execute()
            
            items = res.get('items', [])
            
            # Nếu YouTube báo hết kết quả -> Dừng ngay
            if not items: 
                break 
            
            for item in items:
                if filter_type == 'video': video_pool.append(item['id']['videoId'])
                elif filter_type == 'channel': video_pool.append(item['id']['channelId'])
                elif filter_type == 'playlist': video_pool.append(item['id']['playlistId'])
            
            # Cập nhật thanh tiến trình
            progress_bar.progress(min(len(video_pool) / limit, 0.9))
            
            next_page_token = res.get('nextPageToken')
            if not next_page_token: 
                break

        real_count = len(video_pool)

        if real_count == 0:
            st.error(f"⚠️ KHÔNG TÌM THẤY KẾT QUẢ NÀO! (YouTube không trả về video nào cho bộ lọc này)")
            return None

        # Nếu không phải video thì trả về luôn
        if filter_type != 'video':
            return {
                "type": filter_type, "count": real_count, "hit_limit": hit_limit, 
                "data": [{"ID": i} for i in video_pool]
            }

        # ---------------------------------------------------------
        # BƯỚC 2: PHÂN TÍCH CHI TIẾT (LẤY MẪU TOP 50)
        # ---------------------------------------------------------
        status_text.text("📈 Đang phân tích chỉ số chi tiết...")
        
        ids_to_analyze = video_pool[:50]
        
        res_vid = youtube.videos().list(part="snippet,statistics", id=','.join(ids_to_analyze)).execute()
        
        ch_ids = [i['snippet']['channelId'] for i in res_vid['items']]
        res_ch = youtube.channels().list(part="statistics", id=','.join(ch_ids)).execute()
        ch_map = {i['id']: (int(i['statistics']['subscriberCount']) if not i['statistics']['hiddenSubscriberCount'] else 0) for i in res_ch['items']}

        video_data = []
        all_views = []
        all_like_rates = []
        competitor_subs = []
        sharks = 0; guppies = 0

        # Map thứ tự gốc
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

        # Sắp xếp hiển thị theo đúng thứ tự quét được
        video_data.sort(key=lambda x: x['Rank'])

        # ---------------------------------------------------------
        # BƯỚC 3: TÍNH TOÁN CHỈ SỐ
        # ---------------------------------------------------------
        progress_bar.progress(1.0)
        status_text.text("✅ Hoàn tất!")
        
        # A. Supply (Mật độ thực tế)
        videos_per_unit = real_count / max(1, days_back)
        
        sat_score = 0; sat_msg = ""; sat_color = "green"
        
        # Logic bão hòa dựa trên thực tế
        if hit_limit or videos_per_unit > 40: 
            sat_score = 60; sat_msg = "🔴 BÃO HÒA (Nhiều video)"; sat_color = "red"
        elif videos_per_unit > 10: 
            sat_score = 30; sat_msg = "🟠 CẠNH TRANH"; sat_color = "orange"
        elif videos_per_unit < 1: 
            sat_score = -10; sat_msg = "🟢 KHAN HIẾM"; sat_color = "green"
        else: 
            sat_score = 10; sat_msg = "🟡 TRUNG BÌNH"; sat_color = "gold"

        # B. Competitor
        avg_subs = statistics.median(competitor_subs) if competitor_subs else 0
        comp_score = 0
        if avg_subs > 500000: comp_score = 40
        elif avg_subs > 100000: comp_score = 30
        elif avg_subs > 10000: comp_score = 10
        comp_score += (sharks * 2) - (guppies * 2)
        
        # C. Difficulty
        final_diff = comp_score + sat_score
        final_diff = max(0, min(100, final_diff))

        # D. Volume
        total_market_volume = sum(all_views)
        avg_views = statistics.median(all_views) if all_views else 0
        avg_like_bm = statistics.median(all_like_rates) if all_like_rates else 0
        
        return {
            "type": "video",
            "score": final_diff,
            "supply": videos_per_unit,
            "supply_msg": sat_msg,
            "count": real_count,
            "hit_limit": hit_limit,
            "avg_sub": avg_subs,
            "sharks": sharks,
            "guppies": guppies,
            "total_vol": total_market_volume,
            "avg_view": avg_views,
            "avg_like": avg_like_bm,
            "data": video_data
        }
        
    except Exception as e:
        st.error(f"Lỗi: {e}")
        return None

# ==========================================
# UI SIDEBAR (GIAO DIỆN CẤU HÌNH)
# ==========================================
with st.sidebar:
    st.header("⚙️ CẤU HÌNH")
    api_key = st.text_input("🔑 API Key", type="password")
    keyword = st.text_input("🔎 Keyword", value="Bóng đá")
    st.divider()
    
    # 1. TIME
    time_labels = {"hour": "1 giờ qua", "today": "Hôm nay", "week": "Tuần này", "month": "Tháng này", "year": "Năm nay", "any": "Mọi lúc"}
    time_frame = st.selectbox("🗓️ Thời gian", options=list(time_labels.keys()), format_func=lambda x: time_labels[x], index=1)
    
    # 2. TYPE
    filter_type_labels = {"video": "Video", "channel": "Kênh", "playlist": "Playlist"}
    filter_type = st.selectbox("📂 Loại", options=list(filter_type_labels.keys()), format_func=lambda x: filter_type_labels[x], index=0)

    # 3. DURATION
    if filter_type == 'video':
        dur_labels = {"short": "< 4 phút", "medium": "4 - 20 phút", "long": "> 20 phút", "any": "Bất kỳ"}
        duration = st.selectbox("⏳ Độ dài", options=list(dur_labels.keys()), format_func=lambda x: dur_labels[x], index=2)
    else:
        duration = 'any'
        
    # 4. SORT (QUAN TRỌNG)
    sort_labels = {"viewCount": "Lượt xem (View)", "relevance": "Liên quan", "date": "Ngày tải lên", "rating": "Đánh giá"}
    sort_by = st.selectbox("📶 Xếp theo", options=list(sort_labels.keys()), format_func=lambda x: sort_labels[x], index=0, help="Bộ đếm sẽ đếm dựa trên danh sách sắp xếp này.")
    
    # 5. LIMIT (TRẦN NHÀ)
    st.divider()
    limit = st.slider("🚧 Giới hạn quét (Trần nhà)", 50, 1000, 200, step=50, 
                      help="Ví dụ: Đặt 500. Nếu quét được 20 video rồi hết -> Báo 20. Nếu quét đến 500 vẫn còn -> Báo 500+ (Bão hòa).")
    
    btn_run = st.button("🚀 PHÂN TÍCH THỰC TẾ", type="primary", use_container_width=True)

# ==========================================
# UI MAIN (MÀN HÌNH KẾT QUẢ)
# ==========================================
st.title("👁️ Market Reality Check")
st.markdown("---")

if btn_run:
    if not api_key:
        st.warning("Vui lòng nhập API Key!")
    else:
        result = analyze_reality(api_key, keyword, time_frame, duration, sort_by, filter_type, limit)
        
        if result:
            if result['type'] != 'video':
                st.info(f"Tìm thấy {result['count']} kết quả.")
            else:
                # --- METRICS ---
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.metric("🔥 ĐỘ KHÓ HIỂN THỊ", f"{result['score']}/100")
                    if result['score'] > 75: st.error("🔴 KHÓ (Cạnh tranh)")
                    elif result['score'] > 45: st.warning("🟠 TRUNG BÌNH")
                    else: st.success("🟢 DỄ (Ít đối thủ hiển thị)")
                    st.progress(result['score']/100)

                with c2:
                    # LOGIC SỐ LƯỢNG CHUẨN
                    count_display = f"{result['count']}"
                    if result['hit_limit']:
                        count_display += "+"
                        msg = f"Đã chạm trần {limit} (Còn nữa)"
                    else:
                        msg = "Tổng số video thực tế hiển thị"
                        
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
                st.subheader(f"🏆 Danh sách hiển thị thực tế ({time_labels[time_frame]} | {sort_labels[sort_by]})")
                
                df = pd.DataFrame(result['data'])
                
                # Tô màu viral
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