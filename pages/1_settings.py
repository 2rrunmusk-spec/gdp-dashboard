import streamlit as st
import json
import os

# 설정 파일이 저장될 경로 (최상단 폴더에 secrets.json으로 저장)
SAVE_FILE = "secrets.json"

st.title("⚙️ 환경 설정")
st.write("봇 실행에 필요한 API 키와 계정 정보를 입력해주세요.")

# 입력 폼 만들기
with st.form("settings_form"):
    gemini_key = st.text_input("1. Gemini API 키", type="password")
    threads_id = st.text_input("2. 스레드 아이디")
    threads_pw = st.text_input("3. 스레드 비밀번호", type="password")
    
    # 저장 버튼
    submit = st.form_submit_button("저장하기")
    
    if submit:
        data = {
            "gemini_api_key": gemini_key,
            "threads_username": threads_id,
            "threads_password": threads_pw
        }
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        st.success("✅ 설정 정보가 성공적으로 저장되었습니다!")