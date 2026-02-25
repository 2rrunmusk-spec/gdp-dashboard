import streamlit as st
import json
import os
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
import threading
import time

SAVE_FILE = "secrets.json"
SCHEDULE_FILE = "scheduled.json"

# ---------------------------------------------
# 💾 데이터 처리 및 자동 마이그레이션
# ---------------------------------------------
def save_all_users(data):
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def load_all_users():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            changed = False
            # 구버전 데이터를 다중 계정 버전으로 자동 변환
            for uid, udata in data.items():
                if "threads_accounts" not in udata:
                    udata["threads_accounts"] = {}
                    if udata.get("threads_token"):
                        udata["threads_accounts"]["기본 계정"] = {
                            "secret": udata.get("threads_secret", ""),
                            "token": udata.get("threads_token", "")
                        }
                    changed = True
            if changed:
                save_all_users(data)
            return data
    return {}

def load_schedules():
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
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
# ⏰ 백그라운드 스케줄러 (한국 시간 패치)
# ---------------------------------------------
def job_checker():
    while True:
        schedules = load_schedules()
        if schedules:
            now_kst = datetime.utcnow() + timedelta(hours=9)
            now_str = now_kst.strftime("%Y-%m-%d %H:%M")
            pending = []
            for item in schedules:
                if item["post_time"] <= now_str:
                    post_to_threads(item["text"], item["token"])
                else:
                    pending.append(item)
            if len(schedules) != len(pending):
                save_schedules(pending)
        time.sleep(30)

def start_scheduler():
    for t in threading.enumerate():
        if t.name == "Thread_JobChecker":
            return
    t = threading.Thread(target=job_checker, name="Thread_JobChecker", daemon=True)
    t.start()

start_scheduler()

# ---------------------------------------------
# 🔒 로그인 화면
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
                else:
                    st.error("⚠️ 비밀번호가 틀렸습니다.")
            else:
                st.error("⚠️ 등록되지 않은 아이디입니다.")
                
    with tab2:
        st.subheader("신규 계정 생성")
        new_id = st.text_input("새로 만들 아이디")
        new_pw = st.text_input("새 비밀번호", type="password")
        if st.button("사용자 생성"):
            if new_id in users_data:
                st.error("⚠️ 이미 존재하는 아이디입니다.")
            elif not new_id or not new_pw:
                st.warning("⚠️ 아이디와 비밀번호를 모두 입력해주세요.")
            else:
                users_data[new_id] = {"password": new_pw, "gemini_api_key": "", "threads_accounts": {}}
                save_all_users(users_data)
                st.success(f"🎉 '{new_id}' 생성 완료! 로그인 탭에서 로그인해주세요.")
    st.stop()

# ---------------------------------------------
# 🚀 메인 대시보드 & 설정 통합 화면
# ---------------------------------------------
current_user = st.session_state["logged_in_user"]
user_config = users_data.get(current_user, {})

with st.sidebar:
    st.success(f"👤 **{current_user}**님 접속 중")
    if st.button("🚪 로그아웃"):
        st.session_state["logged_in_user"] = None
        st.rerun()

st.title("🤖 스레드 다중 계정 봇")

# ✨ 탭으로 화면 분리 (대시보드 / 설정)
tab_main, tab_settings = st.tabs(["🚀 자동 업로드 대시보드", "⚙️ 계정 및 API 설정"])

# ==========================================
# ⚙️ 탭 2: 환경 설정 (다중 계정 관리)
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
    
    # 기존 등록된 계정 목록 보여주기
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
                                st.success("🎉 장기 토큰으로 갱신/저장 완료!")
                            else:
                                st.error(f"⚠️ 실패: {res}")
                with col_btn2:
                    if st.button(f"🗑️ 계정 삭제", key=f"del_{acc_name}"):
                        del users_data[current_user]["threads_accounts"][acc_name]
                        save_all_users(users_data)
                        st.warning(f"'{acc_name}' 계정이 삭제되었습니다.")
                        time.sleep(1)
                        st.rerun()
    else:
        st.info("아직 등록된 스레드 계정이 없습니다. 아래에서 추가해주세요.")

    # 새 계정 추가 폼
    with st.form("add_account_form"):
        st.subheader("➕ 새 스레드 계정 추가")
        new_acc_name = st.text_input("1. 계정 별명 (예: 맛집 리뷰용, 일상용)")
        new_secret = st.text_input("2. 스레드 앱 시크릿 코드", type="password")
        new_token = st.text_input("3. 스레드 액세스 토큰 (현재)", type="password")
        
        if st.form_submit_button("이 계정 추가하기"):
            if not new_acc_name or not new_secret or not new_token:
                st.error("⚠️ 모든 항목을 입력해주세요.")
            elif new_acc_name in accounts:
                st.error("⚠️ 이미 같은 별명의 계정이 존재합니다.")
            else:
                users_data[current_user]["threads_accounts"][new_acc_name] = {
                    "secret": new_secret,
                    "token": new_token
                }
                save_all_users(users_data)
                st.success(f"🎉 '{new_acc_name}' 계정이 성공적으로 추가되었습니다!")
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
        # ✨ 어떤 계정에 올릴지 선택하는 드롭다운
        selected_account = st.selectbox("📤 어느 계정에 업로드하시겠습니까?", list(accounts.keys()))
        selected_token = accounts[selected_account]["token"]

        st.divider()
        st.subheader("📝 1단계: 게시글 자동 작성")
        genai.configure(api_key=user_config["gemini_api_key"])
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        topic = st.text_input("💡 오늘 스레드에 올릴 주제를 짧게 적어주세요:", value="오늘 점심 메뉴 추천 좀")

        if st.button("✨ 게시글 초안 생성하기", type="primary"):
            with st.spinner("Gemini가 트렌디한 글을 작성하고 있습니다..."):
                try:
                    final_prompt = f"""
당신은 스레드(Threads)에서 활동하는 센스 있는 인플루언서입니다. 
다음 [주제]를 바탕으로 스레드에 업로드할 게시글을 작성해주세요.

[주제]: {topic}

[절대 지켜야 할 조건]
1. 인사말이나 부연 설명은 절대 하지 말고 '딱 게시글 본문만' 출력할 것.
2. 무조건 3줄 이내로 아주 짧고 간결하게 작성할 것.
3. 친근하고 자연스러운 인터넷 '반말(최신 밈 활용)'로 작성할 것.
4. 해시태그는 마지막 줄에 1~2개만 넣을 것.
"""
                    response = model.generate_content(final_prompt)
                    st.session_state["draft_text"] = response.text
                except Exception as e:
                    st.error("⚠️ 텍스트 생성 오류! API 키를 확인해주세요.")
        
        if "draft_text" in st.session_state:
            st.divider()
            st.subheader(f"🚀 2단계: [{selected_account}]에 스레드 업로드")
            final_text = st.text_area("수정 후 업로드할 최종 내용:", value=st.session_state["draft_text"], height=150)
            
            is_scheduled = st.checkbox("⏰ 이 게시물을 예약해서 올리기")
            
            if is_scheduled:
                col1, col2 = st.columns(2)
                with col1:
                    sched_date = st.date_input("예약 날짜")
                with col2:
                    sched_time = st.time_input("예약 시간", step=60)
                    
                sched_datetime_str = f"{sched_date} {sched_time.strftime('%H:%M')}"
                
                if st.button("📅 지정한 시간에 예약하기", type="primary"):
                    schedules = load_schedules()
                    schedules.append({
                        "user": current_user,
                        "account_name": selected_account, # 어떤 계정인지 저장
                        "text": final_text,
                        "token": selected_token,
                        "post_time": sched_datetime_str
                    })
                    schedules = sorted(schedules, key=lambda x: x["post_time"])
                    save_schedules(schedules)
                    
                    st.success(f"🎉 [{selected_account}] 계정에 {sched_datetime_str} 업로드 예약 완료!")
                    del st.session_state["draft_text"]
                    time.sleep(1)
                    st.rerun()
            else:
                if st.button("📤 지금 바로 업로드하기", type="primary"):
                    with st.spinner("스레드에 게시물을 전송하고 있습니다..."):
                        success, message = post_to_threads(final_text, selected_token)
                        if success:
                            st.balloons()
                            st.success(f"🎉 [{selected_account}] 계정에 성공적으로 업로드되었습니다!")
                            del st.session_state["draft_text"]
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"⚠️ 업로드 실패: {message}")

        # ---------------------------------------------
        # 📅 예약된 게시물 관리
        # ---------------------------------------------
        st.divider()
        st.subheader("📅 내 예약된 게시물 관리")
        
        my_schedules = [s for s in load_schedules() if s["user"] == current_user]
        
        if not my_schedules:
            st.info("현재 대기 중인 예약 게시물이 없습니다.")
        else:
            for idx, sched in enumerate(my_schedules):
                # 표시용 계정 이름 (구버전 데이터 호환 처리)
                disp_acc = sched.get('account_name', '기본 계정')
                
                with st.expander(f"⏰ {sched['post_time']} | 📌 [{disp_acc}] | (클릭해서 수정/삭제)"):
                    new_text = st.text_area("내용 수정:", value=sched['text'], height=100, key=f"text_{idx}")
                    
                    try:
                        exist_dt = datetime.strptime(sched['post_time'], "%Y-%m-%d %H:%M")
                        exist_date = exist_dt.date()
                        exist_time = exist_dt.time()
                    except:
                        exist_date = datetime.now().date()
                        exist_time = datetime.now().time()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        new_date = st.date_input("날짜 변경", value=exist_date, key=f"date_{idx}")
                    with col2:
                        new_time = st.time_input("시간 변경", value=exist_time, key=f"time_{idx}", step=60)
                    
                    new_datetime_str = f"{new_date} {new_time.strftime('%H:%M')}"
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("💾 수정 내용 저장", key=f"edit_{idx}", type="primary"):
                            all_schedules = load_schedules()
                            for s in all_schedules:
                                if s["user"] == current_user and s["post_time"] == sched["post_time"] and s["text"] == sched["text"]:
                                    s["text"] = new_text
                                    s["post_time"] = new_datetime_str
                                    break
                            save_schedules(sorted(all_schedules, key=lambda x: x["post_time"]))
                            st.success("✅ 예약이 성공적으로 수정되었습니다!")
                            time.sleep(1)
                            st.rerun()
                            
                    with col_btn2:
                        if st.button("🗑️ 예약 취소 (삭제)", key=f"del_{idx}"):
                            all_schedules = load_schedules()
                            all_schedules = [s for s in all_schedules if not (s["user"] == current_user and s["post_time"] == sched["post_time"] and s["text"] == sched["text"])]
                            save_schedules(all_schedules)
                            st.warning("🗑️ 예약이 삭제되었습니다.")
                            time.sleep(1)
                            st.rerun()