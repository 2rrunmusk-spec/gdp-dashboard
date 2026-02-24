import streamlit as st
import requests
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import pandas as pd

# --- [1] 기본 설정 및 데이터베이스(다중 사용자용) ---
st.set_page_config(page_title="Threads Manager V18", page_icon="👑", layout="wide")

DATA_FILE = "threads_local_data.json"

# 기본 데이터베이스 구조 (admin, admin2 방 생성)
DEFAULT_DB = {
    "users": {
        "admin": {"password": "admin", "groq_api": "", "imgbb_api": "", "accounts": {}},
        "admin2": {"password": "admin2", "groq_api": "", "imgbb_api": "", "accounts": {}}
    }
}

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 구버전 데이터가 있다면 덮어쓰거나 초기화 방어
                if "users" not in data:
                    return DEFAULT_DB
                return data
        except:
            pass
    return DEFAULT_DB

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 전체 데이터 로드
db_data = load_data()

# --- [2] 세션 상태 (로그인 관리) 초기화 ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'username' not in st.session_state: st.session_state.username = ""
if 'draft_text' not in st.session_state: st.session_state.draft_text = ""
if 'trend_result_text' not in st.session_state: st.session_state.trend_result_text = ""
if 'draft_image_path' not in st.session_state: st.session_state.draft_image_path = None
if 'use_image' not in st.session_state: st.session_state.use_image = False

# ==========================================
# 🔐 [3] 로그인 화면 (로그인 안 된 경우 여기서 멈춤)
# ==========================================
if not st.session_state.logged_in:
    st.title("🔒 스레드 자동화 시스템 로그인")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("아이디와 비밀번호를 입력해주세요. (기본: admin / admin2)")
        login_id = st.text_input("아이디")
        login_pw = st.text_input("비밀번호", type="password")
        
        if st.button("로그인", type="primary", use_container_width=True):
            if login_id in db_data["users"] and db_data["users"][login_id]["password"] == login_pw:
                st.session_state.logged_in = True
                st.session_state.username = login_id
                st.success(f"{login_id}님 환영합니다!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 일치하지 않습니다.")
    
    # 로그인이 안 되었으므로 아래 코드는 실행하지 않고 여기서 정지합니다.
    st.stop()

# ==========================================
# 🔓 로그인 성공 후: 현재 사용자의 데이터만 추출
# ==========================================
current_user = st.session_state.username
# user_data를 수정하면 db_data 안의 내용이 함께 수정됩니다.
user_data = db_data["users"][current_user]

# --- [4] 통신 함수 (Groq 및 스크래핑) ---
def generate_draft_with_groq(prompt, api_key):
    try:
        api_key.encode('ascii')
    except UnicodeEncodeError:
        st.error("⚠️ [설정 오류] Groq API 키에 잘못된 문자가 포함되었습니다.")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1024
    }
    
    try:
        payload_bytes = json.dumps(payload).encode('ascii')
        req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        if e.code == 429: 
            st.warning("⚠️ 한도 도달! 우회 시도 중...")
            payload["model"] = "llama-3.1-8b-instant"
            try:
                fb_bytes = json.dumps(payload).encode('ascii')
                fb_req = urllib.request.Request(url, data=fb_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(fb_req) as fb_res:
                    return json.loads(fb_res.read().decode('utf-8'))["choices"][0]["message"]["content"]
            except:
                st.error("⏳ Groq API 무료 한도를 소진했습니다.")
                return None
        else:
            st.error(f"API 오류: {e.code}")
            return None
    except Exception as e:
        st.error(f"시스템 오류: {str(e)}")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_trend_cached(rss_url, category_name, style_instruction, api_key):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        rss_res = requests.get(rss_url, headers=headers)
        root = ET.fromstring(rss_res.content)
        raw_items = [item.find('title').text for item in root.findall('.//item')[:15]]
        prompt = f"주제 기획: {json.dumps(raw_items)}\n지시: {style_instruction}"
        return generate_draft_with_groq(prompt, api_key)
    except Exception as e:
        return f"수집 오류: {e}"

# --- [5] 사이드바 (로그아웃, 비번 변경, 개인 설정) ---
with st.sidebar:
    st.markdown(f"### 👤 안녕하세요, **{current_user}** 님!")
    
    col_out1, col_out2 = st.columns(2)
    with col_out1:
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()
            
    with st.expander("🔑 비밀번호 변경"):
        new_pw = st.text_input("새로운 비밀번호 입력", type="password")
        if st.button("변경 저장", use_container_width=True):
            if len(new_pw) >= 4:
                user_data["password"] = new_pw
                save_data(db_data)
                st.success("✅ 비밀번호가 변경되었습니다!")
            else:
                st.error("4자리 이상 입력해주세요.")

    st.divider()
    st.title("🧭 내비게이션")
    page = st.radio("메뉴 선택:", ["📝 기획 & 업로드", "📊 데이터 정보"])
    
    st.divider()
    st.header("⚙️ 개인 API 설정")
    new_api_key = st.text_input("Groq API Key", value=user_data.get("groq_api", ""), type="password")
    new_imgbb_key = st.text_input("ImgBB API Key", value=user_data.get("imgbb_api", ""), type="password")
    
    if new_api_key != user_data.get("groq_api", "") or new_imgbb_key != user_data.get("imgbb_api", ""):
        user_data["groq_api"] = new_api_key.strip()
        user_data["imgbb_api"] = new_imgbb_key.strip()
        save_data(db_data)

    with st.expander("➕ 내 계정 추가하기 (최대 10개)"):
        new_id = st.text_input("계정 아이디")
        new_token = st.text_input("Threads 토큰", type="password")
        if st.button("계정 저장"):
            if new_id and new_token:
                user_data.setdefault("accounts", {})[new_id] = new_token.strip()
                save_data(db_data)
                st.success(f"'{new_id}' 추가 완료!")
                st.rerun()

    if user_data.get("accounts"):
        st.divider()
        st.subheader("🗑️ 내 계정 관리")
        del_account = st.selectbox("삭제할 계정 선택", list(user_data["accounts"].keys()))
        if st.button("선택 계정 삭제"):
            del user_data["accounts"][del_account]
            save_data(db_data)
            st.rerun()

# --- [6] 메인 프레임 1: 기획 & 업로드 ---
if page == "📝 기획 & 업로드":
    st.title("🚀 스레드 자동 업로드")
    
    if not user_data.get("accounts"):
        st.info("👈 좌측 사이드바에서 계정을 먼저 추가해주세요.")
    else:
        selected_account = st.selectbox("내 계정 선택:", list(user_data["accounts"].keys()))
        active_token = user_data["accounts"][selected_account]
        
        t1, t2, t3 = st.tabs(["사회/이슈", "유머/썰", "IT/트렌드"])
        with t1:
            if st.button("📰 이슈 기획"):
                st.session_state.trend_result_text = fetch_trend_cached("https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko", "사회", "진지한 주제", user_data["groq_api"])
        with t2:
            if st.button("🔥 유머/썰 기획"):
                st.session_state.trend_result_text = fetch_trend_cached("https://news.google.com/rss/search?q=블라인드+OR+직장인썰+OR+커뮤니티&hl=ko&gl=KR&ceid=KR:ko", "유머", "도파민 팡팡 터지는 썰", user_data["groq_api"])
        with t3:
            if st.button("📱 IT 트렌드 기획"):
                st.session_state.trend_result_text = fetch_trend_cached("https://news.google.com/rss/search?q=애플+OR+삼성+OR+신제품&hl=ko&gl=KR&ceid=KR:ko", "IT", "얼리어답터 관심사", user_data["groq_api"])
                
        if st.session_state.trend_result_text: st.info(st.session_state.trend_result_text)
        
        st.divider()
        draft_topic = st.text_area("주제 입력", height=100)
        use_img = st.checkbox("🖼️ 사진 포함")
        uploaded_file = None
        img_mode = "🤖 AI 생성"
        
        if use_img:
            img_mode = st.radio("이미지 모드", ["🤖 AI 생성", "📁 직접 업로드"], horizontal=True)
            if img_mode == "📁 직접 업로드":
                uploaded_file = st.file_uploader("사진 선택", type=['png', 'jpg', 'jpeg'])

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🤖 AI 초안 생성", type="primary", use_container_width=True):
                if not draft_topic: st.warning("주제를 적어주세요.")
                else:
                    with st.spinner('작성 중...'):
                        res = generate_draft_with_groq(f"인플루언서 말투로 작성: {draft_topic}", user_data["groq_api"])
                        if res:
                            st.session_state.draft_text = res
                            st.session_state.use_image = use_img
                            if use_img:
                                path = "temp_img.jpg"
                                if img_mode == "🤖 AI 생성":
                                    prompt = urllib.parse.quote(draft_topic)
                                    img_res = requests.get(f"https://image.pollinations.ai/prompt/{prompt}")
                                    with open(path, "wb") as f: f.write(img_res.content)
                                elif uploaded_file:
                                    with open(path, "wb") as f: f.write(uploaded_file.getbuffer())
                                st.session_state.draft_image_path = path
                            st.success("생성 완료!")

        with col_b:
            if st.session_state.draft_text:
                final_text = st.text_area("최종 수정", value=st.session_state.draft_text, height=150)
                if st.session_state.use_image: st.image(st.session_state.draft_image_path, width=300)
                if st.button("🚀 스레드 업로드", type="primary", use_container_width=True):
                    with st.status("전송 중...") as s:
                        try:
                            img_url = None
                            if st.session_state.use_image:
                                with open(st.session_state.draft_image_path, "rb") as f:
                                    res = requests.post(f"https://api.imgbb.com/1/upload?key={user_data['imgbb_api']}", files={"image": f})
                                img_url = res.json()["data"]["url"]
                            
                            payload = {"media_type": "IMAGE" if img_url else "TEXT", "text": final_text, "access_token": active_token}
                            if img_url: payload["image_url"] = img_url
                            
                            c_res = requests.post("https://graph.threads.net/v1.0/me/threads", data=payload)
                            c_id = c_res.json().get("id")
                            time.sleep(10)
                            requests.post("https://graph.threads.net/v1.0/me/threads_publish", data={"creation_id": c_id, "access_token": active_token})
                            s.update(label="업로드 성공!", state="complete")
                            st.balloons()
                        except Exception as e:
                            st.error(f"실패: {e}")

# --- [7] 메인 프레임 2: 데이터 정보 ---
elif page == "📊 데이터 정보":
    st.title("📈 내 계정 데이터 조회")
    if not user_data.get("accounts"): st.info("사이드바에서 조회할 계정을 추가하세요.")
    else:
        acc = st.selectbox("계정 선택", list(user_data["accounts"].keys()))
        tok = user_data["accounts"][acc]
        if st.button("🔄 최신 데이터 불러오기", type="primary"):
            with st.spinner("가져오는 중..."):
                try:
                    res = requests.get(f"https://graph.threads.net/v1.0/me/threads?fields=id,text&limit=5&access_token={tok}").json()
                    st.markdown(f"### 📝 최근 게시물 (@{acc})")
                    for p in res.get("data", []):
                        st.write(f"- {p.get('text', '(사진/미디어)')}")
                    st.success("완료!")
                except: 
                    st.error("데이터를 불러오지 못했습니다. 토큰을 확인해주세요.")