import streamlit as st
import json
import os
import google.generativeai as genai

SAVE_FILE = "secrets.json"

def load_user_settings(user_id):
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get(user_id, {})
    return {}

st.title("🤖 스레드 자동화 봇 대시보드")

# 1. 로그인 (계정 선택)
login_id = st.selectbox("접속할 계정을 선택하세요:", ["선택안함", "admin", "admin2"])

if login_id != "선택안함":
    user_config = load_user_settings(login_id)
    
    # 2. 정보 확인
    if not user_config.get("gemini_api_key") or not user_config.get("threads_token"):
        st.warning(f"⚠️ {login_id} 계정의 설정 정보가 없습니다. 왼쪽 [1_settings]에서 먼저 등록해주세요.")
    else:
        st.success(f"✅ {login_id} 계정으로 접속되었습니다.")
        st.divider()
        
        st.subheader("🧪 1단계: Gemini 텍스트 생성 테스트")
        
        genai.configure(api_key=user_config["gemini_api_key"])
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        sample_prompt = "유튜브에 새로 업로드한 BeamNG.drive 플레이 및 모드 리뷰 영상을 홍보하는 스레드 게시글을 시선을 끌 수 있게 작성해줘. 관련 해시태그도 3~4개 포함해줘."
        user_prompt = st.text_area("Gemini에게 지시할 내용을 적어보세요:", value=sample_prompt, height=100)

        if st.button("✨ 게시글 초안 생성하기", type="primary"):
            with st.spinner("Gemini가 글을 작성하고 있습니다..."):
                try:
                    response = model.generate_content(user_prompt)
                    st.info("🎉 완성된 스레드 초안:")
                    st.write(response.text)
                except Exception as e:
                    st.error("⚠️ 오류가 발생했습니다. API 키를 다시 확인해주세요!")