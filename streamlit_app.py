import streamlit as st
import json
import os
import requests

SAVE_FILE = "secrets.json"

# 로그인 안 하고 억지로 설정창 들어온 경우 차단
if "logged_in_user" not in st.session_state or st.session_state["logged_in_user"] is None:
    st.warning("⚠️ 먼저 메인 화면에서 로그인을 진행해주세요.")
    st.stop()

current_user = st.session_state["logged_in_user"]

def load_all_users():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def get_long_lived_token(short_token, client_secret):
    url = "https://graph.threads.net/access_token"
    params = {"grant_type": "th_exchange_token", "client_secret": client_secret, "access_token": short_token}
    res = requests.get(url, params=params)
    return (True, res.json().get("access_token")) if res.status_code == 200 else (False, res.text)

all_data = load_all_users()
# 현재 접속자의 데이터만 가져옴
user_config = all_data.get(current_user, {})

st.title("⚙️ 내 환경 설정")
st.write(f"현재 접속 중인 **[{current_user}]** 계정의 전용 공간입니다.")
st.divider()

with st.form("settings_form"):
    st.subheader("기본 정보 입력")
    # 비밀번호 변경 기능 추가
    my_pw = st.text_input("🔑 내 계정 비밀번호 (변경 시 입력)", value=user_config.get("password", ""), type="password")
    gemini_key = st.text_input("1. Gemini API 키", value=user_config.get("gemini_api_key", ""), type="password")
    threads_secret = st.text_input("2. 스레드 앱 시크릿 코드", value=user_config.get("threads_secret", ""), type="password")
    threads_token = st.text_input("3. 스레드 액세스 토큰 (현재)", value=user_config.get("threads_token", ""), type="password")
    
    if st.form_submit_button("내 정보 저장하기"):
        all_data[current_user]["password"] = my_pw
        all_data[current_user]["gemini_api_key"] = gemini_key
        all_data[current_user]["threads_secret"] = threads_secret
        all_data[current_user]["threads_token"] = threads_token
        
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4)
        st.success("✅ 내 설정이 성공적으로 저장되었습니다!")

st.divider()
st.subheader("🔄 60일 장기 토큰 변환")
if st.button("✨ 60일 장기 토큰으로 변환하기", type="primary"):
    if not user_config.get("threads_secret") or not user_config.get("threads_token"):
        st.error("⚠️ 먼저 위에서 정보를 입력하고 저장해주세요.")
    else:
        with st.spinner("장기 토큰으로 교환 중..."):
            success, result = get_long_lived_token(user_config["threads_token"], user_config["threads_secret"])
            if success:
                all_data[current_user]["threads_token"] = result
                with open(SAVE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, indent=4)
                st.success("🎉 60일짜리 장기 토큰으로 교체되어 자동 저장되었습니다!")
            else:
                st.error(f"⚠️ 변환 실패: {result}")