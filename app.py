import streamlit as st
import googleapiclient.discovery
from googleapiclient.errors import HttpError
import statistics
from datetime import datetime, timedelta, timezone
import dateutil.parser
import pandas as pd

# ==========================================
# 🎨 CẤU HÌNH GIAO DIỆN
# ==========================================
st.set_page_config(
    page_title="YouTube Market Reality Check",
    page_icon="🌏",
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
# 🔧 QUẢN LÝ KEY (MULTI-KEY)
# ==========================================
class YouTubeKeyManager:
    def __init__(self, key_list):
        self.keys = [k.strip() for k in key_list if k.strip()]
        self.current_index = 0
        self.service = None
        self._build_service()

    def _build_service(self):
        if not self.keys:
            self.service = None
            return
        current_key = self.keys[self.current_index]
        try:
            self.service = googleapiclient.discovery.build(
                "youtube", "v3", developerKey=current_key, cache_discovery=False
            )
        except Exception:
            self.rotate_key()

    def rotate_key(self):
        self.current_index += 1
        if self.current_index >= len(self.keys):
            return False
        self._build_service()
        return True

    def execute_safe(self, request_builder_func):
        while True:
            if not self.service:
                raise Exception("Hết sạch API Key!")
            try:
                request = request_builder_func(self.service)
                return request.execute()
            except HttpError as e:
                if e.resp.get('status') == '403' and 'quotaExceeded' in str(e):
                    st.toast(f"⚠️ Key #{self.current_index + 1} hết xăng! Đổi Key...", icon="🔄")
                    if not self.rotate_key():
                        st.error("❌ HẾT SẠCH KEY!")
                        raise e
                    continue
                else:
                    raise e

# ==========================================
# 🌍 DANH SÁCH QUỐC GIA ĐẦY ĐỦ (FULL LIST)
# ==========================================
FULL_REGIONS = {
    "VN": "Vietnam 🇻🇳", "US": "United States 🇺🇸", "KR": "South Korea 🇰🇷", "JP": "Japan 🇯🇵",
    "IN": "India 🇮🇳", "GB": "United Kingdom 🇬🇧", "BR": "Brazil 🇧🇷", "RU": "Russia 🇷🇺",
    "DE": "Germany 🇩🇪", "FR": "France 🇫🇷", "ID": "Indonesia 🇮🇩", "MX": "Mexico 🇲🇽",
    "TH": "Thailand 🇹🇭", "PH": "Philippines 🇵🇭", "TR": "Turkey 🇹🇷", "ES": "Spain 🇪🇸",
    "IT": "Italy 🇮🇹", "CA": "Canada 🇨🇦", "AU": "Australia 🇦🇺", "MY": "Malaysia 🇲🇾",
    "TW": "Taiwan 🇹🇼", "SA": "Saudi Arabia 🇸🇦", "AE": "UAE 🇦🇪", "SG": "Singapore 🇸🇬",
    "HK": "Hong Kong 🇭🇰", "AR": "Argentina 🇦🇷", "ZA": "South Africa 🇿🇦", "EG": "Egypt 🇪🇬",
    "PK": "Pakistan 🇵🇰", "NG": "Nigeria 🇳🇬", "BD": "Bangladesh 🇧🇩", "PL": "Poland 🇵🇱",
    "NL": "Netherlands 🇳🇱", "SE": "Sweden 🇸🇪", "CH": "Switzerland 🇨🇭", "BE": "Belgium 🇧🇪",
    "AT": "Austria 🇦🇹", "PT": "Portugal 🇵🇹", "NO": "Norway 🇳🇴", "DK": "Denmark 🇩🇰",
    "FI": "Finland 🇫🇮", "IE": "Ireland 🇮🇪", "NZ": "New Zealand 🇳🇿", "IL": "Israel 🇮🇱",
    "UA": "Ukraine 🇺🇦", "CO": "Colombia 🇨🇴", "CL": "Chile 🇨🇱", "PE": "Peru 🇵🇪",
    "CZ": "Czechia 🇨🇿", "HU": "Hungary 🇭🇺", "RO": "Romania 🇷🇴", "GR": "Greece 🇬🇷",
    "SK": "Slovakia 🇸🇰", "BG": "Bulgaria 🇧🇬", "HR": "Croatia 🇭🇷", "RS": "Serbia 🇷🇸",
    "SI": "Slovenia 🇸🇮", "LT": "Lithuania 🇱🇹", "LV": "Latvia 🇱🇻", "EE": "Estonia 🇪🇪",
    "DZ": "Algeria 🇩🇿", "MA": "Morocco 🇲🇦", "IQ": "Iraq 🇮🇶", "KE": "Kenya 🇰🇪",
    "GH": "Ghana 🇬🇭", "TZ": "Tanzania 🇹🇿", "UG": "Uganda 🇺🇬", "ZW": "Zimbabwe 🇿🇼",
    "LK": "Sri Lanka 🇱🇰", "NP": "Nepal 🇳🇵", "KZ": "Kazakhstan 🇰🇿", "BY": "Belarus 🇧🇾",
    "AZ": "Azerbaijan 🇦🇿", "GE": "Georgia 🇬🇪", "BO": "Bolivia 🇧🇴", "EC": "Ecuador 🇪🇨",
    "GT": "Guatemala 🇬🇹", "CR": "Costa Rica 🇨🇷", "DO": "Dominican Rep. 🇩🇴",
    "UY": "Uruguay 🇺🇾", "PY": "Paraguay 🇵🇾", "SV": "El Salvador 🇸🇻", "HN": "Honduras 🇭🇳",
    "NI": "Nicaragua 🇳🇮", "PA": "Panama 🇵🇦", "JM": "Jamaica 🇯🇲", "PR": "Puerto Rico 🇵🇷",
    "QA": "Qatar 🇶🇦", "KW": "Kuwait 🇰🇼", "OM": "Oman 🇴🇲", "BH": "Bahrain 🇧🇭",
    "LB": "Lebanon 🇱🇧", "JO": "Jordan 🇯🇴", "TN": "Tunisia 🇹🇳", "YE": "Yemen 🇾🇪"
}

# ==========================================
# 🧠 CORE LOGIC
# ==========================================

def analyze_reality(key_list, keyword, time_frame, duration, sort_by, filter_type, limit, region_codes):
    try:
        key_manager = YouTubeKeyManager(key_list)
        if not key_manager.keys:
            st.warning("Chưa nhập Key!")
            return None

        # 1. CẤU HÌNH THỜI GIAN
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
        # BƯỚC 1: QUÉT ĐA QUỐC GIA
        # ---------------------------------------------------------
        unique_video_pool = {} 
        region_stats = {} 
        
        total_regions = len(region_codes)
        
        for idx, region in enumerate(region_codes):
            # Lấy tên nước để hiển thị
            region_name = FULL_REGIONS.get(region, region)
            status_text.text(f"🔍 Đang quét tại {region_name} ({idx+1}/{total_regions})...")
            
            current_region_count = 0
            next_page_token = None
            
            while True:
                if current_region_count >= limit: 
                    break

                def build_search_request(service):
                    params = {
                        "q": keyword, "type": filter_type, "part": "id,snippet", 
                        "maxResults": 50, "order": sort_by, "pageToken": next_page_token,
                        "regionCode": region,
                        "safeSearch": "none"
                    }
                    if published_after: params["publishedAfter"] = published_after
                    if filter_type == 'video' and duration != 'any': params["videoDuration"] = duration
                    return service.search().list(**params)

                res = key_manager.execute_safe(build_search_request)
                items = res.get('items', [])
                
                if not items: break 
                
                for item in items:
                    v_id = ""
                    if filter_type == 'video': v_id = item['id']['videoId']
                    elif filter_type == 'channel': v_id = item['id']['channelId']
                    elif filter_type == 'playlist': v_id = item['id']['playlistId']
                    
                    if v_id:
                        # Nếu video chưa có trong pool, hoặc có rồi nhưng ở nước khác -> Lưu
                        if v_id not in unique_video_pool:
                            unique_video_pool[v_id] = region 
                            current_region_count += 1
                
                overall_progress = (idx + min(current_region_count/limit, 1.0)) / total_regions
                progress_bar.progress(min(overall_progress, 0.9))
                
                next_page_token = res.get('nextPageToken')
                if not next_page_token: break
            
            region_stats[region] = current_region_count

        final_video_ids = list(unique_video_pool.keys())
        real_count = len(final_video_ids)

        if real_count == 0:
            st.error(f"⚠️ KHÔNG TÌM THẤY KẾT QUẢ NÀO tại các quốc gia đã chọn!")
            return None

        if filter_type != 'video':
            return {
                "type": filter_type, "count": real_count, "region_stats": region_stats,
                "data": [{"ID": i} for i in final_video_ids], "key_idx": key_manager.current_index + 1
            }

        # ---------------------------------------------------------
        # BƯỚC 2: PHÂN TÍCH CHI TIẾT
        # ---------------------------------------------------------
        status_text.text("📈 Đang phân tích chi tiết tổng hợp...")
        
        ids_to_analyze = final_video_ids[:50]
        
        def build_videos_request(service):
            return service.videos().list(part="snippet,statistics", id=','.join(ids_to_analyze))
        res_vid = key_manager.execute_safe(build_videos_request)
        
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
                pub_obj = dateutil.parser.isoparse(snip['publishedAt'])
                diff = now_utc - pub_obj
                local_time = pub_obj.astimezone() 
                date_str = local_time.strftime("%d/%m %H:%M")
                
                days = diff.days
                seconds = diff.seconds
                hours = days * 24 + seconds // 3600
                if days >= 1: age_display = f"{days} ngày"
                else: age_display = f"{hours} giờ"
            except: 
                age_display = "?"
                date_str = "?"
            
            l_rate = (likes / views * 100) if views > 0 else 0
            c_rate = (cmts / views * 100) if views > 0 else 0
            
            all_views.append(views)
            all_like_rates.append(l_rate)
            if subs > 0: competitor_subs.append(subs)
            
            c_type = "🐟"
            if subs > 500000: c_type = "🦈"; sharks += 1
            elif subs < 10000 and subs > 0: c_type = "🦐"; guppies += 1
            elif subs > 100000: c_type = "🐳"
            
            origin_region = unique_video_pool.get(v_id, "UNK")
            
            video_data.append({
                'Rank': order_map.get(v_id, 999) + 1,
                'Q.Gia': origin_region, # Hiển thị mã nước
                'Loại': c_type,
                'Tiêu đề': snip['title'],
                'View': views,
                'Ngày đăng': date_str,
                'Tuổi': age_display,
                '% Like': round(l_rate, 2),
                '% Cmt': round(c_rate, 2),
                'Sub Kênh': subs,
                'Link Video': f"https://youtu.be/{v_id}",
                'Link Kênh': f"https://www.youtube.com/channel/{snip['channelId']}"
            })

        # Sort theo View nếu chọn ViewCount, ngược lại theo Rank
        if sort_by == 'viewCount':
            video_data.sort(key=lambda x: x['View'], reverse=True)
        else:
            video_data.sort(key=lambda x: x['Rank'])

        # ---------------------------------------------------------
        # BƯỚC 3: KẾT LUẬN
        # ---------------------------------------------------------
        progress_bar.progress(1.0)
        status_text.text("✅ Hoàn tất!")
        
        videos_per_unit = real_count / max(1, days_back)
        
        sat_score = 0; sat_msg = ""; 
        if videos_per_unit > 40 * len(region_codes): 
            sat_score = 60; sat_msg = "🔴 BÃO HÒA CAO"
        elif videos_per_unit > 10 * len(region_codes): 
            sat_score = 30; sat_msg = "🟠 CẠNH TRANH"
        elif videos_per_unit < 1: 
            sat_score = -10; sat_msg = "🟢 KHAN HIẾM"
        else: 
            sat_score = 10; sat_msg = "🟡 TRUNG BÌNH"

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
            "count": real_count, "region_stats": region_stats,
            "avg_sub": avg_subs, "sharks": sharks, "guppies": guppies, 
            "total_vol": total_market_volume, "avg_view": avg_views, "avg_like": avg_like_bm, 
            "data": video_data, "key_idx": key_manager.current_index + 1
        }
        
    except Exception as e:
        st.error(f"Lỗi: {e}")
        return None

# ==========================================
# UI SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ CẤU HÌNH")
    api_keys_input = st.text_area("🔑 API Keys (Mỗi dòng 1 key)", height=100)
    keyword = st.text_input("🔎 Keyword", value="Kiếm tiền online")
    
    st.divider()
    
    # --- MULTI-REGION FULL LIST ---
    region_codes = st.multiselect(
        "🌏 Chọn Quốc gia (Đa vùng)", 
        options=list(FULL_REGIONS.keys()), 
        format_func=lambda x: FULL_REGIONS[x], 
        default=["VN"], 
        help="Chọn nhiều nước để quét và gộp kết quả."
    )
    
    st.divider()

    time_labels = {"hour": "1 giờ qua", "today": "Hôm nay", "week": "Tuần này", "month": "Tháng này", "year": "Năm nay", "any": "Mọi lúc"}
    time_frame = st.selectbox("🗓️ Thời gian", options=list(time_labels.keys()), format_func=lambda x: time_labels[x], index=1)
    
    filter_type_labels = {"video": "Video", "channel": "Kênh", "playlist": "Playlist"}
    filter_type = st.selectbox("📂 Loại", options=list(filter_type_labels.keys()), format_func=lambda x: filter_type_labels[x], index=0)

    if filter_type == 'video':
        dur_labels = {"short": "< 4 phút", "medium": "4 - 20 phút", "long": "> 20 phút", "any": "Bất kỳ"}
        duration = st.selectbox("⏳ Độ dài", options=list(dur_labels.keys()), format_func=lambda x: dur_labels[x], index=3)
    else:
        duration = 'any'
        
    sort_labels = {"viewCount": "Lượt xem", "relevance": "Liên quan", "date": "Ngày tải lên", "rating": "Đánh giá"}
    sort_by = st.selectbox("📶 Xếp theo", options=list(sort_labels.keys()), format_func=lambda x: sort_labels[x], index=1)
    
    limit = st.slider("🚧 Giới hạn quét (Mỗi quốc gia)", 50, 500, 100, step=50)
    
    btn_run = st.button("🚀 PHÂN TÍCH", type="primary", use_container_width=True)

# ==========================================
# UI MAIN
# ==========================================
st.title("🌏 Market Reality Check")
st.markdown("---")

if btn_run:
    if not api_keys_input.strip():
        st.warning("Vui lòng nhập Key!")
    elif not region_codes:
        st.warning("Vui lòng chọn ít nhất 1 quốc gia!")
    else:
        key_list = api_keys_input.strip().split('\n')
        result = analyze_reality(key_list, keyword, time_frame, duration, sort_by, filter_type, limit, region_codes)
        
        if result:
            if result['type'] != 'video':
                st.info(f"Tìm thấy {result['count']} kết quả.")
            else:
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("🔥 ĐỘ KHÓ", f"{result['score']}/100")
                    st.progress(result['score']/100)
                    st.caption(f"Dùng Key #{result['key_idx']}")

                with c2:
                    # Hiển thị chi tiết từng nước
                    # Format đẹp hơn cho list nước
                    top_regions = sorted(result['region_stats'].items(), key=lambda x: x[1], reverse=True)[:3]
                    stats_str = ", ".join([f"{k}: {v}" for k, v in top_regions])
                    if len(result['region_stats']) > 3: stats_str += "..."
                    
                    st.metric("📦 Tổng Video Hiển Thị", f"{result['count']}", delta=result['supply_msg'], delta_color="inverse")
                    st.caption(f"Chi tiết: {stats_str}")

                with c3:
                    st.metric("💰 Volume (Top List)", f"{result['total_vol']:,.0f}")
                    st.caption(f"View TB: {result['avg_view']:,.0f}")
                
                st.divider()

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("🦈 Cá Mập", result['sharks'])
                col2.metric("🦐 Tôm Tép", result['guppies'])
                col3.metric("Sub TB", f"{result['avg_sub']:,.0f}")
                col4.metric("👍 % Like", f"{result['avg_like']:.2f}%")
                
                region_display = ", ".join(region_codes[:5])
                if len(region_codes) > 5: region_display += "..."
                st.subheader(f"🏆 Danh sách hiển thị tại [{region_display}] ({time_labels[time_frame]})")
                
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
