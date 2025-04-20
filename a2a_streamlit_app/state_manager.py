import streamlit as st
from typing import List, Dict, Any, Optional

def initialize_session_state():
    """Streamlitのセッション状態を初期化する"""
    if "server_urls" not in st.session_state:
        st.session_state.server_urls: List[str] = [] # 登録済みサーバーURL
    if "agent_cards" not in st.session_state:
        st.session_state.agent_cards: Dict[str, Any] = {} # 取得したAgent Card (URL -> Card)
    if "selected_agent_url" not in st.session_state:
        st.session_state.selected_agent_url: Optional[str] = None # 選択中のエージェントURL
    if "chat_history" not in st.session_state:
        st.session_state.chat_history: List[Dict[str, Any]] = [] # チャット履歴 [{"role": "user/assistant", "content": "...", "artifacts": [...]}]
    if "current_task_id" not in st.session_state:
        st.session_state.current_task_id: Optional[str] = None # 現在実行中のタスクID
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id: Optional[str] = None # 現在のセッションID
    if "task_status_updates" not in st.session_state:
        st.session_state.task_status_updates: List[Dict[str, Any]] = [] # タスクステータス更新履歴
    if "task_artifacts" not in st.session_state:
        st.session_state.task_artifacts: List[Dict[str, Any]] = [] # タスクアーティファクト更新履歴
    if "input_required" not in st.session_state:
        st.session_state.input_required: bool = False # HIL入力が必要か
    if "input_prompt" not in st.session_state:
        st.session_state.input_prompt: Optional[str] = None # HIL入力プロンプト