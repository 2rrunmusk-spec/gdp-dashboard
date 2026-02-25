import streamlit as st
import json
import os
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import time

SAVE_FILE = "secrets.json"
SCHEDULE_FILE = "scheduled.json"

# ---------------------------------------------
# 💾 데이터 처리
# ---------------------------------------------
def save_all_users(data):
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def load_all_users():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                changed = False
                for uid, udata in data.items():
                    if "threads_accounts" not in udata:
                        udata["threads_accounts"] = {}
                        if udata.get("threads_token"):
                            udata["threads_accounts"]["기본 계정"] = {"secret": udata.get("threads_secret", ""), "token": udata.get("threads_token", "")}
                        changed = True
                if changed: save_all_users(data)
                return data
        except: return {}
    return {}

def load_schedules():
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f: 
                schedules = json.load(f)
                # 혹시 예전에 'processing' 상태로 고장난 자물쇠가 있다면 강제로 해제!
                for s in schedules:
                    if s.get("status") == "processing":
                        s.pop("status", None)
                return schedules
        except: return []
    return []

def save_schedules(data):
    with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def post_to_threads(text, access_token):
    create_url = "https://graph.threads.net/v1.0/me/threads"
    create_res = requests.post(create_url, data={"media_type": "TEXT", "text": text, "access_token": access_token})
    if create_res.status_code != 200:
        return False, f"컨테이너 생성 오류: {create_res.text}"
    
    creation_id = create_res.json().get("id")
    time.sleep(3) # 메타 서버 준비 대기
    
    publish_url = "https://graph.threads.net/v1.0/me/threads_publish"
    publish_res = requests.post(publish_url, data={"creation_id": creation_id, "access_token": access_token})
    if publish_res.status_code != 200:
        return False, f"발행 오류: {publish_res.text}"
    return True, "성공"

def get_long_lived_token(short_token, client_secret):
    url = "https://graph.threads.net/access_token"
    params = {"grant_type": "th_exchange_token", "client_secret": client_secret, "access_token": short_token}
    res = requests.get(url, params=params)
    return (True, res.json().get("access_token")) if res.status_code == 200 else (False, res.text)

# ---------------------------------------------
# ⏰ [핵심 개선] 페이지 접속 시 자동 예약 처리 (자물쇠 제거)
# ---------------------------------------------
def process_due_schedules():
    schedules = load_schedules()
    if not schedules: return

    now_kst = datetime.utcnow() + timedelta(hours=9)
    now_str = now_kst.strftime("%Y-%m-%d %H:%M")

    # '실패'가 아닌 것 중에서 시간이 지난 것들을 싹 모음
    due_items = [item for item in schedules if item["post_time"] <= now_str and item.get("status") != "failed"]
    if not due_items: return

    for item in due_items:
        success, msg = post_to_threads(item["text"], item["token"])

        # 업로드 시도 후 목록 갱신
        current_schedules = load_schedules()
        updated_schedules = []
        for s in current_schedules:
            if s["post_time"] == item["post_time"] and s["text"] == item["text"]:
                if not success:
                    s["status"] = "failed"
                    s["error_msg"] = msg
                    updated_schedules.append(s)
                # 성공 시에는 추가하지 않으므로 자연스럽게 목록에서 삭제!
            else:
                updated_schedules.append(s)
        save_schedules(updated_schedules)

# 스크립트가 실행(새로고침)될 때마다 무조건 예약 검사
process_due_schedules()

# ---------------------------------------------
# 🔒 로그인 및 메인 화면 구성
# ---------------------------------------------
if "logged_in_user" not in st.session_state:
    st.session_state["logged_in_user"] = None

users_data = load_all_users()

if st.session_state["logged_in_user"] is None:
    st.title("🔒 스레드 봇 로그인")
    tab1, tab2 = st.tabs(["로그인", "새 사용자 추가"])
    with tab1:
        st.subheader("계정 접속")
        login_id = st.text_input("아이디")
        login_pw = st.text_input("비밀번호", type="password")
        if st.button("로그인", type="primary"):
            if login_id in users_data:
                stored_pw = users_data[login_id].get("password", "")
                if stored_pw == "" or stored_pw == login_pw:
                    st.session_state["logged_in_user"] = login_id
                    st.rerun()
                else: st.error("⚠️ 비밀번호가 틀렸습니다.")
            else: st.error("⚠️ 등록되지 않은 아이디입니다.")
    with tab2:
        st.subheader("신규 계정 생성")
        new_id = st.text_input("새로 만들 아이디")
        new_pw = st.text_input("새 비밀번호", type="password")
        if st.button("사용자 생성"):
            if new_id in users_data: st.error("⚠️ 이미 존재하는 아이디입니다.")
            elif not new_id or not new_pw: st.warning("⚠️ 아이디와 비밀번호를 모두 입력해주세요.")
            else:
                users_data[new_id] = {"password": new_pw, "gemini_api_key": "", "threads_accounts": {}}
                save_all_users(users_data)
                st.success(f"🎉 '{new_id}' 생성 완료! 로그인 탭에서 로그인해주세요.")
    st.stop()

current_user = st.session_state["logged_in_user"]
user_config = users_data.get(current_user, {})

# 현재 봇 시간 계산
bot_now = datetime.utcnow() + timedelta(hours=9)
bot_now_str = bot_now.strftime("%Y-%m-%d %H:%M")

with st.sidebar:
    st.success(f"👤 **{current_user}**님 접속 중")
    
    # ✨ 봇 시계 표시! (이 시간 기준으로 예약이 돌아갑니다)
    st.info(f"⏰ 봇 기준 현재 시간:\n\n**{bot_now_str}**")
    
    if st.button("🚪 로그아웃"):
        st.session_state["logged_in_user"] = None
        st.rerun()

st.title("🤖 스레드 다중 계정 봇")

tab_main, tab_settings = st.tabs(["🚀 자동 업로드 대시보드", "⚙️ 계정 및 API 설정"])

# ==========================================
# ⚙️ 탭 2: 환경 설정
# ==========================================
with tab_settings:
    st.header("1. Gemini API 설정")
    new_gemini = st.text_input("🔑 Gemini API 키", value=user_config.get("gemini_api_key", ""), type="password")
    if st.button("Gemini 키 저장"):
        users_data[current_user]["gemini_api_key"] = new_gemini
        save_all_users(users_data)
        st.success("✅ Gemini API 키가 저장되었습니다.")
        time.sleep(1)
        st.rerun()

    st.divider()
    st.header("2. 스레드 다중 계정 관리")
    accounts = user_config.get("threads_accounts", {})
    if accounts:
        st.write("📋 **현재 등록된 계정 목록**")
        for acc_name, acc_info in accounts.items():
            with st.expander(f"📌 {acc_name}"):
                st.caption(f"앱 시크릿: {acc_info['secret'][:5]}... / 토큰: {acc_info['token'][:10]}...")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button(f"✨ 60일 토큰 갱신", key=f"renew_{acc_name}", type="primary"):
                        with st.spinner("갱신 중..."):
                            suc, res = get_long_lived_token(acc_info["token"], acc_info["secret"])
                            if suc:
                                users_data[current_user]["threads_accounts"][acc_name]["token"] = res
                                save_all_users(users_data)
                                st.success("🎉 장기 토큰으로 갱신 완료!")
                            else: st.error(f"⚠️ 실패: {res}")
                with col_btn2:
                    if st.button(f"🗑️ 계정 삭제", key=f"del_{acc_name}"):
                        del users_data[current_user]["threads_accounts"][acc_name]
                        save_all_users(users_data)
                        st.warning(f"'{acc_name}' 계정이 삭제되었습니다.")
                        time.sleep(1)
                        st.rerun()
    else:
        st.info("아직 등록된 스레드 계정이 없습니다. 아래에서 추가해주세요.")

    with st.form("add_account_form"):
        st.subheader("➕ 새 스레드 계정 추가")
        new_acc_name = st.text_input("1. 계정 별명 (예: 맛집 리뷰용, 일상용)")
        new_secret = st.text_input("2. 스레드 앱 시크릿 코드", type="password")
        new_token = st.text_input("3. 스레드 액세스 토큰 (현재)", type="password")
        if st.form_submit_button("이 계정 추가하기"):
            if not new_acc_name or not new_secret or not new_token: st.error("⚠️ 모든 항목을 입력해주세요.")
            elif new_acc_name in accounts: st.error("⚠️ 이미 같은 별명의 계정이 존재합니다.")
            else:
                users_data[current_user]["threads_accounts"][new_acc_name] = {"secret": new_secret, "token": new_token}
                save_all_users(users_data)
                st.success(f"🎉 '{new_acc_name}' 추가 완료!")
                time.sleep(1)
                st.rerun()

# ==========================================
# 🚀 탭 1: 대시보드 (업로드 및 예약)
# ==========================================
with tab_main:
    accounts = user_config.get("threads_accounts", {})
    if not user_config.get("gemini_api_key") or not accounts:
        st.warning("⚠️ 옆의 [⚙️ 계정 및 API 설정] 탭으로 가서 Gemini 키와 스레드 계정을 먼저 등록해주세요.")
    else:
        selected_account = st.selectbox("📤 어느 계정에 업로드하시겠습니까?", list(accounts.keys()))
        selected_token = accounts[selected_account]["token"]

        st.divider()
        st.subheader("📝 1단계: 게시글 자동 작성")
        genai.configure(api_key=user_config["gemini_api_key"])
        model = genai.GenerativeModel('gemini-2.5-flash') 
        topic = st.text_input("💡 오늘 스레드에 올릴 주제를 짧게 적어주세요:", value="오늘 점심 메뉴 추천 좀")

        if st.button("✨ 게시글 초안 생성하기", type="primary"):