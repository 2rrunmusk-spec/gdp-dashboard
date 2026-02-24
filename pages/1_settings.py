import streamlit as st
import json
import os

# 데이터를 저장할 로컬 파일 이름 설정
DATA_FILE = "threads_data.json"

# 1. 로컬 파일에서 데이터 불러오기 함수
def load_data():
    # 파일이 존재하면 읽어오고, 없으면 빈 형태를 반환
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"gemini_api_key": "", "threads_user_id": "", "threads_token": ""}

# 2. 로컬 파일에 데이터 저장하기 함수
def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- 화면 UI 구성 ---
st.set_page_config(page_title="설정 및 계정 정보", page_icon="⚙️")
st.title("⚙️ API 및 스레드 정보 설정")
st.write("앞으로 버전이 수정되더라도 이 페이지에서 저장한 정보는 로컬 파일로 항상 유지돼.")

# 기존에 저장된 데이터 불러오기
saved_data = load_data()

# 입력 폼 만들기
with st.form("settings_form"):
    st.subheader("🔑 제미나이(Gemini) API 설정")
    gemini_key = st.text_input("Gemini API Key", value=saved_data.get("gemini_api_key", ""), type="password")
    
    st.subheader("🧵 스레드(Threads) 정보 설정")
    threads_id = st.text_input("Threads User ID", value=saved_data.get("threads_user_id", ""))
    threads_token = st.text_input("Threads Access Token", value=saved_data.get("threads_token", ""), type="password")
    
    # 저장 버튼
    submit = st.form_submit_button("로컬 파일에 저장하기")
    
    # 버튼을 눌렀을 때 실행될 로직
    if submit:
        new_data = {
            "gemini_api_key": gemini_key,
            "threads_user_id": threads_id,
            "threads_token": threads_token
        }
        save_data(new_data)
        st.success("✅ 정보가 `threads_data.json` 파일에 성공적으로 저장되었어!")