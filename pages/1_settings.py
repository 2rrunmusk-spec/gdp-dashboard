import streamlit as st
import json
import os

SAVE_FILE = "secrets.json"

st.title("⚙️ 계정별 환경 설정")
st.write("본인의 계정(admin 또는 admin2)을 선택하고 정보를 저장하세요.")

# 파일 불러오기 함수
def load_all_settings():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"admin": {}, "admin2": {}}

# 기존 데이터 불러오기
all_data = load_all_settings()

# 1. 누구의 설정을 바꿀지 선택
user_id = st.radio("어떤 계정의 설정을 수정하시겠습니까?", ["admin", "admin2"])

# 선택한 사용자의 기존 데이터 가져오기
current_gemini = all_data[user_id].get("gemini_api_key", "")
current_threads = all_data[user_id].get("threads_token", "")

st.divider()

# 2. 정보 입력 및 저장 폼
with st.form("settings_form"):
    st.subheader(f"[{user_id}] 설정")
    gemini_key = st.text_input("1. Gemini API 키", value=current_gemini, type="password")
    threads_token = st.text_input("2. 스레드 액세스 토큰", value=current_threads, type="password")
    
    submit = st.form_submit_button("저장하기")
    
    if submit:
        # 선택한 사용자의 정보만 업데이트
        all_data[user_id]["gemini_api_key"] = gemini_key
        all_data[user_id]["threads_token"] = threads_token
        
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4)
            
        st.success(f"✅ {user_id} 계정의 설정이 성공적으로 저장되었습니다!")