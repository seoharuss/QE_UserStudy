import streamlit as st
import os
import json
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from datetime import datetime

# === 실험용 텍스트 설정 ===
INTRO_INFO = """
        안녕하세요,
        
        저희는 **Quantum ESPRESSO (QE)** 를 활용한 **Density Functional Theory (DFT)** 시뮬레이션 과정에서 발생하는 오류를 해결하고, 관련 질문에 답해주는 **Large Language Model (LLM)** 기반 챗봇을 연구하는 박인기, 조영우, 유재각, 김지환입니다.

        QE 를 사용하다 보면 다양한 문제 상황 및 에러를 마주하게 되나, 해결 방안을 손쉽게 찾기 어려운 경우가 많습니다. 이러한 문제를 해결하고자, 저희는 DFT 및 관련 전공서적, QE 메뉴얼, 그리고 소스코드를 **RAG (Retrieval-Augmented Generation)** 시스템에 활용하여, 사용자가 제시한 계산 스크립트와 오류 메시지를 분석하고 그 원인과 해결책을 근거와 함께 제시하는 챗봇을 개발했습니다.

        본 챗봇은 단순한 문제 해결을 넘어, DFT 의 이론적 배경, 실무 활용 가이드, 그리고 이론 기반 DFT 소스 코드 설명 등 전반적인 지식을 제공할 수 있도록 설계되었습니다. 저희의 목표는 초보자부터 숙련된 사용자까지 실제 연구 현장에서 바로 활용 가능한 시스템을 구축하는 것입니다.

        이번 설문은 개발된 챗봇이 연구자에게 얼마나 유용하고 적절한 답변을 제공하는지 평가하기 위한 것으로, 응답해 주시는 내용은 챗봇 성능 분석 및 정성 평가에 활용되어 논문 작성에 사용될 예정입니다.

        ---
        **연구팀 정보:**
        * **박인기** (KAIST, inkey.park@kaist.ac.kr)
        * **조영우** (KAIST, cyw314@kaist.ac.kr)
        * **김지환** (KAIST, jihvvan.kim@kaist.ac.kr)
        * **유재각 박사** (UIUC, yoojk20@illinois.edu)
        * **주재걸 교수** (KAIST, jchoo@kaist.ac.kr)
"""

EVALUATION_INFO = """

        해당 User Study 는 사용자 질문에 답하기 위해 필요한 관련 외부 지식 (QE 사용 설명서, QE 소스 코드, 전공서적) 을 얼마나 정확하게 검색하고 반영했는지 평가합니다.

        외부 지식은 LLM 시스템이 직접 활용할 수 있도록 데이터베이스화 되어 있습니다. 사용자 질문이 들어오면 LLM 시스템은 데이터베이스에서 필요한 외부 지식을 활용하여 답변을 생성합니다.

        각 **시나리오**마다 질문 (Question) 과 외부 지식 (Context) 을 바탕으로, 챗봇의 답변 (Answer) 이 얼마나 정확하고 충실한지 평가 및 점수 부여 기준에 따라 0 점 ~ 5 점 사이로 평가해 주시면 됩니다.

        평가 및 점수 부여 기준은 각 시나리오 페이지 상단에 제시되어 있습니다.
"""

EVALUATION_METHOD_INFO = """

        1. 평가를 시작하기 전에, 평가 및 점수 부여 기준을 읽어 주세요.
        
        2. "Question" 은 사용자가 챗봇에게 질문한 내용입니다.

        3. "ChatBot Answer" 은 챗봇이 생성한 답변입니다.

        4. "Contexts" 은 챗봇이 답변을 생성하기 위해 활용한 외부 지식입니다.

        5. "ChatBot Answer" 의 각 문장 뒤에 붙어 있는 숫자와 괄호는 해당 "Contexts" 를 참조했다는 의미입니다. (예: [4] 는 Context 4 를 참조했다는 의미입니다.)

        6. 평가 및 점수 부여 기준에 근거하여, 페이지 최하단의 점수를 선택해 주세요.
"""

EVALUATION_CRITERIA = """**[평가 기준]**
1. **기술적 정확성**
    - Quantum ESPRESSO 의 Namelist, 파라미터가 실제로 존재하고 정확하게 사용되었는가?
2. **근거 기반 충실성**
    - 제공된 context 범위 내에서만 답변하고 있는가?
    - context 와 answer 사이에 논리적 괴리가 없는가?
3. **완결성 및 의도 파악**
    - 사용자의 질문 중 누락된 부분은 없는가?
4. **불확실성 처리**
    - context 에 정보가 없을 때 억지로 추측하지 않았는가?

**[점수 부여 기준]**
- **0점** : 질문과 무관하거나 답변을 완전히 거부함.
- **1점** : 환각 (존재하지 않는 파라미터 등) 개념 오류 발생
- **2점** : 사소한 기술적 부정확함이나 검증되지 않은 주장 포함. 질문에 일부만 답변
- **3점** : 기술적으로는 맞지만 통찰이 부족하거나, 너무 일반적이고 장황한 답변
- **4점** : 정확하고 유용함. 기술적 오류는 없으나 스타일이나 문구 표현이 약간 미흡함.
- **5점** : 결점 없음. 완벽한 기술적 전문성, 근거 기반 답변
"""

# === Google Sheets 연동 설정 ===
def save_all_scores_to_gsheet(scores_dict, total_items):
    try:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        spreadsheet_url = st.secrets["gsheets"]["spreadsheet_url"]

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_url(spreadsheet_url).sheet1
        
        # 헤더 준비: 1행 (time, scenario 1, scenario 2, ...)
        headers = ["time"] + [f"scenario {i+1}" for i in range(total_items)]
        
        # 1행이 비어있거나 올바른 구조가 아니면 한 번 덮어씌웁니다.
        first_row = sheet.row_values(1)
        if not first_row or first_row[0] != "time":
            sheet.insert_row(headers, index=1)
            
        # 제출할 데이터 로우 구성
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [now_str]
        
        # 각 시나리오별로 저장되어 있는 점수를 가져옵니다. 미평가시 빈 문자열.
        for i in range(total_items):
            row_data.append(str(scores_dict.get(i, "")))
            
        # 새 행으로 한 번에 추가합니다.
        sheet.append_row(row_data)
        
        return True
    except KeyError as k:
        st.error(f"⚠️ `.streamlit/secrets.toml` 설정이 누락되었습니다: {k}")
        return False
    except FileNotFoundError:
        st.error("⚠️ `.streamlit/secrets.toml` 파일을 찾을 수 없습니다.")
        return False
    except Exception as e:
        st.error(f"Google Sheet 연동 오류: {e}")
        return False

# === 페이지 설정 ===
st.set_page_config(layout="wide", page_title="User study")

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
    
    # input_description.json인 경우 텍스트의 첫 ':' 이전 부분을 토글 제목으로 설정
    if short_source == "input_description.json" and ":" in content:
        short_source = content.split(":", 1)[0].strip()
        
    # 1. 문서 출처나 내용으로 보아 아예 전체가 소스코드 파일인 경우, 전체를 코드 블록으로 씌웁니다.
    is_code_file = any(source.endswith(ext) for ext in [".f90", ".f", ".py", ".c", ".cpp", ".sh"]) or "Code Entity:" in content
    
    if is_code_file and "```" not in content:
        lang = "fortran" if source.endswith((".f90", ".f")) else "python" if source.endswith(".py") else ""
        safe_content = f"```{lang}\n{content}\n```"
    else:
        # 2. 텍스트 문서인 경우, 수식 블록($$)과 이미 존재하는 코드블록(```)이 망가지는 것을 스마트하게 방지
        temp_content = content.replace('$$', '\n\n$$\n\n')
        temp_content = re.sub(r'\n{3,}', '\n\n', temp_content)
        
        lines = temp_content.split('\n')
        processed_lines = []
        in_code_block = False
        
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                processed_lines.append(line)
                continue
                
            if in_code_block:
                # 코드 블록 내부 코드는 공백/띄어쓰기 등 원본 형태를 절대 건드리지 않고 그대로 보존합니다.
                processed_lines.append(line)
            else:
                if line.strip() != "":
                    # 일반 텍스트 줄은 마크다운 연속성을 돕기 위해 끝에 스페이스 2개 삽입 (강제 줄바꿈)
                    processed_lines.append(line.rstrip() + "  ")
                else:
                    processed_lines.append("")
        
        safe_content = "\n".join(processed_lines)

    # st.expander 대신 HTML <details>를 사용하여 토글 제목에 색상 배지를 직관적으로 복원합니다.
    # 마크다운 파서가 들여쓰기된 HTML 태그를 '코드 블록' 텍스트로 오인하는 것을 방지하기 위해 들여쓰기를 제거합니다.
    html_block = f"""<details style="margin-bottom: 12px; border: 1px solid rgba(128,128,128,0.2); border-radius: 6px; box-shadow: 1px 1px 4px rgba(0,0,0,0.1); overflow: hidden;">
<summary style="padding: 12px; cursor: pointer; display: flex; align-items: center; background-color: rgba(128,128,128,0.03); outline: none; font-weight: bold;">
<span style="background-color: {color}; color: #333; padding: 2px 8px; border-radius: 12px; margin-right: 8px; font-size: 0.9em;">Context {idx}</span>
<span style="font-size: 0.95em; color: #666;">📝 {short_source}</span>
</summary>
<div style="border-top: 1px solid rgba(128,128,128,0.1); border-left: 6px solid {color}; padding: 16px; background-color: rgba(128,128,128,0.05);">
<div style="font-size: 0.95em; color: #888; margin-bottom: 10px;">전체 경로: {source}</div>
<div style="font-size: 1.05em; line-height: 1.6; color: inherit;">

{safe_content}

</div>
</div>
</details>"""
    st.markdown(html_block, unsafe_allow_html=True)

def main():
    st.title("Context user study")
    
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
        st.session_state.current_idx = -1
    if "eval_scores" not in st.session_state:
        st.session_state.eval_scores = {}
        
    # === 1. 인트로 페이지 ===
    if st.session_state.current_idx == -1:
        st.info(INTRO_INFO)
        st.write(EVALUATION_INFO)
        
        st.markdown("<br>", unsafe_allow_html=True)
        cols = st.columns([1, 2, 1])
        with cols[1]:
            if st.button("Start !", use_container_width=True):
                st.session_state.current_idx = 0
                st.rerun()
        return

    # === 3. 완료 페이지 ===
    if st.session_state.current_idx >= total_items:
        st.balloons()
        st.markdown("<h2 style='text-align: center;'>🎉 평가가 모두 완료되었습니다!</h2>", unsafe_allow_html=True)
        st.success("소중한 시간을 내어 모든 시나리오에 대한 평가를 마쳐주셔서 감사합니다.")
        st.info("이제 진행하시던 브라우저 창을 닫으셔도 됩니다.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        cols = st.columns([1, 2, 1])
        with cols[1]:
            if st.button("⏮️ 처음으로 돌아가기 (다시 하기)", use_container_width=True):
                st.session_state.current_idx = -1
                st.rerun()
        return

    # === 2. 평가 진행 페이지 ===
    # 상단 네비게이션 버튼 (이전 / 다음)
    col_nav1, col_nav2, col_nav3 = st.columns([1, 8, 1])
    
    with col_nav1:
        if st.button("⬅️ 이전", disabled=(st.session_state.current_idx == 0)):
            st.session_state.current_idx -= 1
            st.rerun()
            
    with col_nav2:
        st.markdown(f"<h4 style='text-align: center; margin-top: 5px; color: #555;'>시나리오 {st.session_state.current_idx + 1} / {total_items}</h4>", unsafe_allow_html=True)
        
    with col_nav3:
        btn_label = "완료 🏁" if st.session_state.current_idx == total_items - 1 else "다음 ➡️"
        if st.button(btn_label):
            st.session_state.current_idx += 1
            st.rerun()

    item = data[st.session_state.current_idx]
    
    st.write("---")
    
    # === 전문가 평가 섹션 ===
    st.warning(EVALUATION_METHOD_INFO)
    with st.expander("평가 및 점수 부여 기준", expanded=False):
        st.markdown(EVALUATION_CRITERIA)



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
        # HTML <div> 내부에 빈 줄(\n\n)을 추가하여 첫 줄의 마크다운(### 등)이 정상 파싱되도록 합니다.
        st.markdown(f'<div style="font-size: 1.05em; line-height: 1.6;">\n\n{highlighted_answer}\n\n</div>', unsafe_allow_html=True)
        
    with col2:
        st.subheader("Contexts")
        contexts = item.get("contexts", [])
        
        if not contexts:
            st.warning("참고한 문서가 없습니다.")
        else:
            for ctx in contexts:
                display_context(ctx)

    st.write("---")
    st.subheader("🎯 점수 부여")

    score_options = [0, 1, 2, 3, 4, 5]
    def format_score(x):
        desc = {
            0: "0점",
            1: "1점",
            2: "2점",
            3: "3점",
            4: "4점",
            5: "5점"
        }
        return desc.get(x, f"{x}점")
        
    # 현재 세션에 저장된 점수가 있으면 불러옵니다. 기본값은 5 (결점 없음)
    current_idx = st.session_state.current_idx
    saved_score = st.session_state.eval_scores.get(current_idx, 5)
    default_index = score_options.index(saved_score) if saved_score in score_options else 5
    
    col_score1, col_score2 = st.columns([8, 2])
    with col_score1:
        selected_score = st.radio(
            "이 답변에 대한 점수를 부여해주세요:",
            options=score_options,
            format_func=format_score,
            index=default_index,
            horizontal=True,
            key=f"radio_score_{current_idx}"
        )
        # 라디오 버튼을 선택하는 즉시 session_state에 해당 시나리오 번호로 점수 기록
        st.session_state.eval_scores[current_idx] = selected_score

    with col_score2:
        st.write("") # 스타일링용 여백
        # 마지막 시나리오에서만 최종 제출 버튼 표시
        if current_idx == total_items - 1:
            if st.button("💾 최종 데이터 제출", use_container_width=True):
                with st.spinner("Google Sheet에 모든 평가 데이터를 전송하는 중..."):
                    success = save_all_scores_to_gsheet(st.session_state.eval_scores, total_items)
                if success:
                    st.success("모든 평가 결과가 성공적으로 제출되었습니다! 🎉")
                    st.balloons()
                else:
                    st.error("Google Sheet 제출 및 연결 실패.")

if __name__ == "__main__":
    main()
