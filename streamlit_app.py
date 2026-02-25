import streamlit as st
import json
import os
import requests
import google.generativeai as genai
from datetime import datetime
import threading
import time

SAVE_FILE = "secrets.json"
SCHEDULE_FILE = "scheduled.json" # 예약 데이터를 저장할 새로운 파일

# ---------------------------------------------
# 💾 데이터 처리 및 스레드 업로드 함수
# ---------------------------------------------
def load_all_users():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_all_users(data):
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

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

# ---------------------------------------------
# ⏰ 백그라운드 스케줄러 (시간 되면 알아서 올림)
# ---------------------------------------------
def job_checker():
    while True:
        schedules = load_schedules()
        if schedules:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            pending = []
            for item in schedules:
                # 예약 시간이 현재 시간보다 과거이거나 같으면 업로드 실행
                if item["post_time"] <= now:
                    post_to_threads(item["text"], item["token"])
                    # 업로드 후 목록에서 제외됨
                else:
                    pending.append(item)
            
            # 변경사항이 있으면 파일 다시 저장
            if len(schedules) != len(pending):
                save_schedules(pending)
        
        time.sleep(30) # 30초마다 파일 확인

# 앱 실행 시 스케줄러를 백그라운드에서 한 번만 켬
if "scheduler_started" not in st.session_state:
    t = threading.Thread(target=job_checker, daemon=True)
    t.start()
    st.session_state["scheduler_started"] = True


# ---------------------------------------------
# 🔒 로그인 화면 처리
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
                users_data[new_id] = {"password": new_pw, "gemini_api_key": "", "threads_secret": "", "threads_token": ""}
                save_all_users(users_data)
                st.success(f"🎉 '{new_id}' 생성 완료! 로그인 탭에서 로그인해주세요.")
    st.stop()


# ---------------------------------------------
# 🚀 메인 대시보드 화면
# ---------------------------------------------
current_user = st.session_state["logged_in_user"]
user_config = users_data.get(current_user, {})

with st.sidebar:
    st.success(f"👤 **{current_user}**님 접속 중")
    if st.button("🚪 로그아웃"):
        st.session_state["logged_in_user"] = None
        st.rerun()

st.title("🤖 스레드 자동화 봇 대시보드")

if not user_config.get("gemini_api_key") or not user_config.get("threads_token"):
    st.warning("⚠️ 현재 계정의 API 설정 정보가 없습니다. 왼쪽 [1_settings] 메뉴에서 내 설정을 완료해주세요.")
else:
    # 1단계: 텍스트 생성
    st.subheader("📝 1단계: 게시글 자동 작성")
    genai.configure(api_key=user_config["gemini_api_key"])
    model = genai.GenerativeModel('gemini-2.5-flash') 
    
    sample_prompt = sample_prompt = """요즘 스레드나 인스타그램, 인터넷 등에서 사람들이 많이 이야기하는 최신 트렌드나 밈, 공감 가는 일상 주제를 하나 골라서 스레드 게시글을 작성해줘. 
    
[조건]
1. 무조건 3줄 이내로 아주 짧고 간결하게 작성할 것.
2. 친구한테 말하듯이 친근하고 자연스러운 '반말'로 작성할 것.
3. 해시태그는 마지막 줄에 1~2개만 넣을 것."""
    
    user_prompt = st.text_area("Gemini에게 지시할 내용을 적어보세요:", value=sample_prompt, height=150)
    user_prompt = st.text_area("Gemini에게 지시할 내용을 적어보세요:", value=sample_prompt, height=100)

    if st.button("✨ 게시글 초안 생성하기", type="primary"):
        with st.spinner("Gemini가 글을 작성하고 있습니다..."):
            try:
                response = model.generate_content(user_prompt)
                st.session_state["draft_text"] = response.text
            except Exception as e:
                st.error("⚠️ 텍스트 생성 오류! API 키를 확인해주세요.")
    
    # 2단계: 업로드 및 스케줄러
    if "draft_text" in st.session_state:
        st.divider()
        st.subheader("🚀 2단계: 스레드 업로드")
        final_text = st.text_area("수정 후 업로드할 최종 내용:", value=st.session_state["draft_text"], height=200)
        
        # --- 예약 업로드 기능 추가 ---
        is_scheduled = st.checkbox("⏰ 이 게시물을 예약해서 올리기")
        
        if is_scheduled:
            col1, col2 = st.columns(2)
            with col1:
                sched_date = st.date_input("예약 날짜")
            with col2:
                sched_time = st.time_input("예약 시간")
                
            sched_datetime_str = f"{sched_date} {sched_time.strftime('%H:%M')}"
            
            if st.button("📅 지정한 시간에 예약하기", type="primary"):
                schedules = load_schedules()
                schedules.append({
                    "user": current_user,
                    "text": final_text,
                    "token": user_config["threads_token"],
                    "post_time": sched_datetime_str
                })
                # 시간순으로 정렬해서 저장
                schedules = sorted(schedules, key=lambda x: x["post_time"])
                save_schedules(schedules)
                
                st.success(f"🎉 {sched_datetime_str}에 업로드되도록 예약되었습니다!")
                del st.session_state["draft_text"]
                st.rerun()
        else:
            if st.button("📤 지금 바로 업로드하기", type="primary"):
                with st.spinner("스레드에 게시물을 전송하고 있습니다..."):
                    success, message = post_to_threads(final_text, user_config["threads_token"])
                    if success:
                        st.balloons()
                        st.success("🎉 성공적으로 스레드에 업로드되었습니다!")
                        del st.session_state["draft_text"]
                        st.rerun()
                    else:
                        st.error(f"⚠️ 업로드 실패: {message}")

    # --- 예약 목록 보기 기능 추가 ---
    st.divider()
    st.subheader("📅 내 예약된 게시물 목록")
    
    my_schedules = [s for s in load_schedules() if s["user"] == current_user]
    
    if not my_schedules:
        st.info("현재 대기 중인 예약 게시물이 없습니다.")
    else:
        for idx, sched in enumerate(my_schedules):
            st.write(f"**{idx+1}. ⏰ {sched['post_time']}**")
            st.caption(f"내용: {sched['text'][:50]}...")