import streamlit as st
import os
import json
import re

# === 페이지 설정 ===
st.set_page_config(layout="wide", page_title="RAG Context Highlighter")

# === 하이라이트 색상 팔레트 ===
# 컨텍스트 인덱스별로 매칭할 색상
COLORS = [
    "#FFB3BA", # 파스텔 레드
    "#BAE1FF", # 파스텔 블루
    "#B5EAD7", # 파스텔 민트
    "#FFDFBA", # 파스텔 오렌지
    "#E2F0CB", # 연두색
    "#F1CBFF", # 연보라
    "#FFC4E1", # 핑크
    "#C4FAF8", # 시안
]

def load_data(folder_path):
    files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
    files.sort(reverse=True) # 최신 파일이 위로 오도록 정렬
    return files

def highlight_answer(text):
    """
    답변 텍스트 내의 [1], [2] 등의 참조 번호를 찾아 
    규칙에 맞는 색상으로 하이라이트 처리하는 HTML 반환
    """
    def repl(match):
        idx = int(match.group(1))
        # 색상 배열의 길이를 넘어가는 인덱스를 대비한 모듈러 연산
        color = COLORS[(idx - 1) % len(COLORS)]
        
        # [1] 부분에 색상 배지로 하이라이트
        return f'<span style="background-color: {color}; color: #333; padding: 2px 6px; border-radius: 4px; font-weight: bold; margin: 0 2px; box-shadow: 1px 1px 2px rgba(0,0,0,0.2);">[{idx}]</span>'
    
    # [1], [2] 와 같이 대괄호 안에 숫자가 있는 패턴을 찾습니다.
    highlighted_text = re.sub(r'\[(\d+)\]', repl, text)
    return highlighted_text

def display_context(context):
    """
    컨텍스트 박스를 시각적으로 예쁘게 표시 (토글 형태, HTML details 태그 사용)
    """
    idx = context.get('id', 1)
    source = context.get('source', 'Unknown Document')
    content = context.get('content', '')
    
    color = COLORS[(idx - 1) % len(COLORS)]
    short_source = source.split('/')[-1] if '/' in source else source
    
    # HTML <details>와 <summary> 태그를 이용하면 제목 부분에도 예쁜 색상 배지(HTML)를 넣을 수 있습니다.
    html = f"""
    <details style="margin-bottom: 12px; border: 1px solid rgba(128,128,128,0.2); border-radius: 6px; box-shadow: 1px 1px 4px rgba(0,0,0,0.1); overflow: hidden;">
        <summary style="padding: 12px; cursor: pointer; display: flex; align-items: center; background-color: rgba(128,128,128,0.03); outline: none; font-weight: bold;">
            <span style="background-color: {color}; color: #333; padding: 2px 8px; border-radius: 12px; margin-right: 8px; font-size: 0.9em; pointer-events: none;">Context {idx}</span>
            <span style="font-size: 0.95em; color: #666; pointer-events: none;">📝 {short_source}</span>
        </summary>
        <div style="border-top: 1px solid rgba(128,128,128,0.1); border-left: 6px solid {color}; padding: 16px; background-color: rgba(128,128,128,0.05);">
            <div style="font-size: 0.95em; color: #888; margin-bottom: 10px;">전체 경로: {source}</div>
            <div style="font-size: 0.95em; line-height: 1.5; color: #ddd;">
                {content.replace(chr(10), '<br>')}
            </div>
        </div>
    </details>
    """
    st.markdown(html, unsafe_allow_html=True)

def main():
    st.title("🔍 RAG Context Highlighter")
    st.markdown("LLM이 답변을 생성할 때 참고한 **문서(Context)와 답변의 출처([Index])를 같은 색상으로 매칭**하여 시각화합니다.")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(current_dir, "data")
    
    if not os.path.exists(data_folder):
        st.error(f"데이터 폴더를 찾을 수 없습니다: `{data_folder}`\n먼저 `make_rag_data.py`를 실행하여 데이터를 생성해주세요.")
        return

    json_files = load_data(data_folder)
    
    if not json_files:
        st.warning("저장된 데이터 파일이 없습니다.")
        return
        
    # 자동으로 가장 최근 파일 선택 (사이드바 선택 없이)
    selected_file = json_files[0]
    
    file_path = os.path.join(data_folder, selected_file)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    total_items = len(data)
    
    # Session State 초기화
    if "current_idx" not in st.session_state:
        st.session_state.current_idx = 0
        
    # 상단 네비게이션 버튼 (이전 / 다음)
    col_nav1, col_nav2, col_nav3 = st.columns([1, 8, 1])
    
    with col_nav1:
        if st.button("⬅️ Prev", disabled=(st.session_state.current_idx == 0)):
            st.session_state.current_idx -= 1
            st.rerun()
            
    with col_nav2:
        st.markdown(f"<h4 style='text-align: center; margin-top: 5px; color: #555;'>데이터 {st.session_state.current_idx + 1} / {total_items}</h4>", unsafe_allow_html=True)
        
    with col_nav3:
        if st.button("Next ➡️", disabled=(st.session_state.current_idx == total_items - 1)):
            st.session_state.current_idx += 1
            st.rerun()

    item = data[st.session_state.current_idx]
    
    st.write("---")
    
    # 질문 섹션
    st.subheader("Question")
    st.info(item.get("question", "질문 없음"))
    
    st.write("---")
    
    # 좌우 컬럼 레이아웃
    col1, col2 = st.columns([6, 4])
    
    with col1:
        st.subheader("ChatBot Answer")
        raw_answer = item.get("rag_answer", "")
        highlighted_answer = highlight_answer(raw_answer)
        st.markdown(f'<div style="font-size: 1.05em; line-height: 1.6;">{highlighted_answer}</div>', unsafe_allow_html=True)
        
    with col2:
        st.subheader("Contexts")
        contexts = item.get("contexts", [])
        
        if not contexts:
            st.warning("참고한 문서가 없습니다.")
        else:
            for ctx in contexts:
                display_context(ctx)

if __name__ == "__main__":
    main()
