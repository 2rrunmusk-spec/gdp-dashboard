import streamlit as st
import json
import os

SAVE_FILE = "secrets.json"

def load_settings():
    """저장된 설정 정보를 불러오는 함수"""
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

st.title("🤖 스레드 자동화 봇 대시보드")

# 1. 설정 정보 확인
config = load_settings()

# 2. 화면 분기 처리
if not config:
    st.warning("⚠️ 저장된 설정 정보가 없습니다. 왼쪽 사이드바에서 [1_settings] 메뉴를 눌러 설정을 먼저 진행해주세요.")
else:
    st.success(f"✅ [{config['threads_username']}] 계정 설정이 로드되었습니다.")
    st.info("준비가 완료되었습니다. 아래 버튼을 눌러 작업을 시작하세요.")
    
    # 봇 실행 버튼
    if st.button("▶️ 봇 실행 테스트", type="primary"):
        st.write("데이터 수집 및 포스팅 준비 중...")
        # TODO: 여기에 실제 스크래핑 및 스레드 업로드 연결