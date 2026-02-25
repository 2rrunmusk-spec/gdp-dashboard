import streamlit as st
import json
import os
import requests

SAVE_FILE = "secrets.json"

def load_all_settings():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"admin": {}, "admin2": {}}

# 장기 토큰 발급 API 통신 함수
def get_long_lived_token(short_token, client_secret):
    url = "https://graph.threads.net/access_token"
    params = {
        "grant_type": "th_exchange_token",
        "client_secret": client_secret,
        "access_token": short_token
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return True, response.json().get("access_token")
    else:
        return False, response.text

st.title("⚙️ 계정별 환경 설정")
st.write("본인의 계정(admin 또는 admin2)을 선택하고 정보를 저장하세요.")

all_data = load_all_settings()
user_id = st.radio("어떤 계정의 설정을 수정하시겠습니까?", ["admin", "admin2"])

current_gemini = all_data[user_id].get("gemini_api_key", "")
current_threads = all_data[user_id].get("threads_token", "")
current_secret = all_data[user_id].get("threads_secret", "")

st.divider()

with st.form("settings_form"):
    st.subheader(f"[{user_id}] 기본 설정")
    gemini_key = st.text_input("1. Gemini API 키", value=current_gemini, type="password")
    threads_secret = st.text_input("2. 스레드 앱 시크릿 코드 (App Secret)", value=current_secret, type="password")
    threads_token = st.text_input("3. 스레드 액세스 토큰 (현재)", value=current_threads, type="password")
    
    submit = st.form_submit_button("저장하기")
    
    if submit:
        all_data[user_id]["gemini_api_key"] = gemini_key
        all_data[user_id]["threads_secret"] = threads_secret
        all_data[user_id]["threads_token"] = threads_token
        
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4)
            
        st.success(f"✅ {user_id} 계정의 설정이 성공적으로 저장되었습니다!")

st.divider()
st.subheader("🔄 60일 장기 토큰으로 업그레이드")
st.info("💡 1시간짜리 단기 토큰을 위 입력칸에 저장한 상태라면, 아래 버튼을 눌러 60일 장기 토큰으로 교체하세요.")

if st.button("✨ 60일 장기 토큰으로 변환하기", type="primary"):
    if not current_secret or not current_threads:
        st.error("⚠️ 먼저 위에서 '앱 시크릿 코드'와 방금 발급받은 '1시간짜리 단기 토큰'을 입력하고 [저장하기]를 눌러주세요.")
    else:
        with st.spinner("장기 토큰으로 교환 중..."):
            success, result = get_long_lived_token(current_threads, current_secret)
            if success:
                all_data[user_id]["threads_token"] = result
                with open(SAVE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, indent=4)
                st.success("🎉 성공! 60일짜리 장기 토큰으로 교체되어 자동 저장되었습니다. 이제 두 달 동안은 토큰 신경 안 쓰셔도 됩니다!")
            else:
                st.error(f"⚠️ 변환 실패: {result}")