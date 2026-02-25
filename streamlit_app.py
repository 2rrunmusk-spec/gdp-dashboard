import streamlit as st
import json
import os
import requests
import google.generativeai as genai

SAVE_FILE = "secrets.json"

# 데이터 불러오기/저장 함수
def load_all_users():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_all_users(data):
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
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

# 로그인 세션 초기화
if "logged_in_user" not in st.session_state:
    st.session_state["logged_in_user"] = None

users_data = load_all_users()

# ---------------------------------------------
# 🔒 로그인 및 사용자 추가 화면 (로그인 안 된 경우)
# ---------------------------------------------
if st.session_state["logged_in_user"] is None:
    st.title("🔒 스레드 봇 로그인")
    
    tab1, tab2 = st.tabs(["로그인", "새 사용자 추가"])
    
    with tab1:
        st.subheader("계정 접속")
        login_id = st.text_input("아이디")
        login_pw = st.text_input("비밀번호", type="password")
        
        if st.button("로그인", type="primary"):
            if login_id in users_data:
                # 기존에 쓰던 admin은 비밀번호가 없으므로 그냥 통과
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
                users_data[new_id] = {
                    "password": new_pw,
                    "gemini_api_key": "",
                    "threads_secret": "",
                    "threads_token": ""
                }
                save_all_users(users_data)
                st.success(f"🎉 '{new_id}' 계정 생성 완료! 옆의 로그인 탭에서 로그인해주세요.")
                
    st.stop() # 로그인 전에는 아래 코드(대시보드) 실행 안 함

# ---------------------------------------------
# 🚀 메인 대시보드 화면 (로그인 성공 후)
# ---------------------------------------------
current_user = st.session_state["logged_in_user"]
user_config = users_data.get(current_user, {})

# 사이드바: 내 정보 및 로그아웃
with st.sidebar:
    st.success(f"👤 **{current_user}**님 접속 중")
    if st.button("🚪 로그아웃"):
        st.session_state["logged_in_user"] = None
        st.rerun()

st.title("🤖 스레드 자동화 봇 대시보드")

if not user_config.get("gemini_api_key") or not user_config.get("threads_token"):
    st.warning("⚠️ 현재 계정의 API 설정 정보가 없습니다. 왼쪽 [1_settings] 메뉴에서 내 설정을 완료해주세요.")
else:
    st.subheader("📝 1단계: 게시글 자동 작성")
    
    genai.configure(api_key=user_config["gemini_api_key"])
    model = genai.GenerativeModel('gemini-2.5-flash') 
    
    sample_prompt = "유튜브에 새로 업로드한 BeamNG.drive 플레이 영상을 홍보하는 스레드 게시글을 써줘."
    user_prompt = st.text_area("Gemini에게 지시할 내용을 적어보세요:", value=sample_prompt, height=100)

    if st.button("✨ 게시글 초안 생성하기", type="primary"):
        with st.spinner("Gemini가 글을 작성하고 있습니다..."):
            try:
                response = model.generate_content(user_prompt)
                st.session_state["draft_text"] = response.text
            except Exception as e:
                st.error("⚠️ 텍스트 생성 오류! API 키를 확인해주세요.")
    
    if "draft_text" in st.session_state:
        st.divider()
        st.subheader("🚀 2단계: 스레드 업로드")
        
        final_text = st.text_area("수정 후 업로드할 최종 내용:", value=st.session_state["draft_text"], height=200)
        
        if st.button("📤 내 스레드에 업로드하기"):
            with st.spinner("스레드에 게시물을 전송하고 있습니다..."):
                success, message = post_to_threads(final_text, user_config["threads_token"])
                if success:
                    st.balloons()
                    st.success("🎉 성공적으로 스레드에 업로드되었습니다!")
                    del st.session_state["draft_text"]
                    st.rerun()
                else:
                    st.error(f"⚠️ 업로드 실패: {message}")