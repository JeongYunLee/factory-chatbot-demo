"""
이 파일은 예전 monolithic 구현을 위해 사용되던 엔트리 포인트입니다.
현재 로직은 모두 개별 모듈로 분리되었고, 이 파일은 더 이상 사용하지 않습니다.

prompt-test.ipynb 등에서 사용할 때는 아래 모듈들을 직접 import 해서 사용하세요.
- config          : LLM 모델 & 데이터프레임 로드
- state           : GraphState, 세션 관리
- routing         : Router 노드
- tools_module    : code_generator / code_executor tool
- agent_module    : agent 노드
- workflow        : langgraph StateGraph (graph, memory)
"""

from workflow import graph, memory  # re-export (필요시 사용)

