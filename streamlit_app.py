import streamlit as st
import json
import os
import requests
import google.generativeai as genai

SAVE_FILE = "secrets.json"

def load_user_settings(user_id):
    """저장된 설정 정보를 불러오는 함수"""
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get(user_id, {})
    return {}

def post_to_threads(text, access_token):
    """스레드 API를 이용해 글을 업로드하는 함수 (2단계 과정)"""
    # 1단계: 스레드 컨테이너(임시 저장소) 생성
    create_url = "https://graph.threads.net/v1.0/me/threads"
    create_payload = {
        "media_type": "TEXT",
        "text": text,
        "access_token": access_token
    }
    create_res = requests.post(create_url, data=create_payload)
    
    if create_res.status_code != 200:
        return False, f"컨테이너 생성 오류: {create_res.text}"
        
    creation_id = create_res.json().get("id")
    
    # 2단계: 생성된 컨테이너를 스레드 타임라인에 발행
    publish_url = "https://graph.threads.net/v1.0/me/threads_publish"
    publish_payload = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    publish_res = requests.post(publish_url, data=publish_payload)
    
    if publish_res.status_code != 200:
        return False, f"발행 오류: {publish_res.text}"
        
    return True, "성공"

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
        
        # --- [1단계: Gemini 텍스트 생성] ---
        st.subheader("📝 1단계: 게시글 자동 작성")
        
        genai.configure(api_key=user_config["gemini_api_key"])
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        sample_prompt = "유튜브에 새로 업로드한 BeamNG.drive 플레이 및 모드 리뷰 영상을 홍보하는 스레드 게시글을 시선을 끌 수 있게 작성해줘. 관련 해시태그도 3~4개 포함해줘."
        user_prompt = st.text_area("Gemini에게 지시할 내용을 적어보세요:", value=sample_prompt, height=100)

        if st.button("✨ 게시글 초안 생성하기", type="primary"):
            with st.spinner("Gemini가 글을 작성하고 있습니다..."):
                try:
                    response = model.generate_content(user_prompt)
                    # 생성된 텍스트를 세션에 저장하여 다음 단계로 넘김
                    st.session_state["draft_text"] = response.text
                except Exception as e:
                    st.error("⚠️ 텍스트 생성 중 오류가 발생했습니다. API 키를 확인해주세요!")
        
        # --- [2단계: 스레드 업로드] ---
        if "draft_text" in st.session_state:
            st.divider()
            st.subheader("🚀 2단계: 스레드 업로드")
            
            # 생성된 텍스트를 수정할 수 있도록 text_area에 띄워줌
            final_text = st.text_area("수정 후 업로드할 최종 내용을 확인하세요:", value=st.session_state["draft_text"], height=200)
            
            if st.button("📤 이 내용으로 스레드에 업로드하기"):
                with st.spinner("스레드에 게시물을 전송하고 있습니다..."):
                    success, message = post_to_threads(final_text, user_config["threads_token"])
                    
                    if success:
                        st.balloons()
                        st.success("🎉 성공적으로 스레드에 업로드되었습니다! 폰이나 웹에서 스레드를 확인해보세요.")
                        # 업로드 완료 후 세션 초기화 (중복 업로드 방지)
                        del st.session_state["draft_text"]
                        st.rerun()
                    else:
                        st.error(f"⚠️ 업로드 실패: {message}")