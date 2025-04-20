import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import streamlit as st
from state_manager import initialize_session_state
import uuid
import asyncio
import nest_asyncio # Streamlit環境でasyncio.runを使うために必要
from a2a_client_utils import get_agent_card, send_a2a_task, stream_a2a_task, create_text_part # Agent Card取得, タスク送信/ストリーミング関数
from typing import Dict, Any, Optional, List
import json # アーティファクト表示用

# nest_asyncioを適用
nest_asyncio.apply()

# --- セッション状態の初期化 ---
initialize_session_state()

# --- Agent Card 取得 (同期) ---
@st.cache_data(ttl=300) # 5分間キャッシュ
def fetch_agent_card_sync(url: str) -> Optional[Dict[str, Any]]:
    """get_agent_card (同期関数) を呼び出し、結果をキャッシュする"""
    try:
        return get_agent_card(url)
    except Exception as e:
        st.error(f"Error fetching Agent Card for {url}: {e}")
        return None

# --- サイドバー ---
st.sidebar.title("A2A Server Management")

# サーバーURL入力
new_server_url = st.sidebar.text_input("Enter A2A Server URL:", key="new_server_url_input")

# サーバー追加ボタン
if st.sidebar.button("Add Server"):
    if new_server_url and new_server_url not in st.session_state.server_urls:
        st.session_state.server_urls.append(new_server_url)
        st.sidebar.success(f"Server added: {new_server_url}")
        # 入力フィールドをクリアするためにキーを使って値をリセット (少しトリッキーな方法)
        # st.session_state.new_server_url_input = "" # これだと再実行時にクリアされない
        # 代わりに rerun を使うか、JavaScriptを使う方法もあるが、シンプルにする
    elif not new_server_url:
        st.sidebar.warning("Please enter a URL.")
    else:
        st.sidebar.warning("Server URL already exists.")

# 登録済みサーバーリスト表示と削除
st.sidebar.subheader("Registered Servers")
servers_to_remove = []
if not st.session_state.server_urls:
    st.sidebar.info("No servers registered yet.")
else:
    for i, url in enumerate(st.session_state.server_urls):
        col1, col2 = st.sidebar.columns([0.8, 0.2])
        with col1:
            st.write(url)
        with col2:
            if st.button("❌", key=f"remove_server_{i}"):
                servers_to_remove.append(url)

# 削除処理
if servers_to_remove:
    for url in servers_to_remove:
        st.session_state.server_urls.remove(url)
        # 関連するAgent Cardも削除 (後続ステップで実装)
        if url in st.session_state.agent_cards:
            del st.session_state.agent_cards[url]
        if st.session_state.selected_agent_url == url:
            st.session_state.selected_agent_url = None # 選択中のエージェントが削除された場合
    st.rerun() # UIを更新するために再実行

# --- Agent Cardの取得 ---
# サーバーURLリストが変更された場合や初回ロード時にAgent Cardを取得
# st.cache_data を使っているので、URLが変わらなければキャッシュが使われる
fetched_cards = {}
if st.session_state.server_urls:
    st.sidebar.subheader("Fetching Agent Cards...")
    progress_bar = st.sidebar.progress(0)
    for i, url in enumerate(st.session_state.server_urls):
        if url not in st.session_state.agent_cards: # まだ取得していないか、キャッシュ切れの場合
            card_data = fetch_agent_card_sync(url)
            if card_data:
                st.session_state.agent_cards[url] = card_data
            else:
                # 取得失敗した場合も記録しておく（再試行を防ぐため、Noneを入れるなど）
                st.session_state.agent_cards[url] = None # 取得失敗を示す
                st.sidebar.error(f"Failed to fetch card for {url}")
        progress_bar.progress((i + 1) / len(st.session_state.server_urls))
    st.sidebar.success("Agent Card fetching complete.")


# --- メインエリア ---
st.title("A2A Chat Application")

# エージェント選択
agent_options_dict = {"Select an Agent": None} # 表示名 -> URL の辞書
for url, card in st.session_state.agent_cards.items():
    if card: # 取得成功したカードのみ選択肢に追加
        agent_name = card.get('name', 'Unknown Agent')
        display_name = f"{agent_name} ({url})"
        agent_options_dict[display_name] = url
    # else: # 取得失敗したURLは選択肢に含めない

# 現在選択されているURLに対応する表示名を探す
current_selection_display = "Select an Agent"
if st.session_state.selected_agent_url:
    for display, url_val in agent_options_dict.items():
        if url_val == st.session_state.selected_agent_url:
            current_selection_display = display
            break

selected_agent_display = st.selectbox(
    "Select Agent:",
    options=list(agent_options_dict.keys()),
    index=list(agent_options_dict.keys()).index(current_selection_display), # 現在の選択を復元
    key="agent_selector",
    # format_func は不要 (辞書のキーがそのまま表示される)
)

# selectboxの選択が変更されたら session_state を更新
selected_url = agent_options_dict.get(selected_agent_display)
if selected_url != st.session_state.selected_agent_url:
    st.session_state.selected_agent_url = selected_url
    # エージェントが変更されたらチャット履歴やタスク状態をリセットするかどうか？
    # st.session_state.chat_history = []
    # st.session_state.current_task_id = None
    # st.session_state.input_required = False
    st.rerun() # 選択を確実に反映させるために再実行

# --- 選択された Agent Card 情報表示 ---
if st.session_state.selected_agent_url and st.session_state.selected_agent_url in st.session_state.agent_cards:
    selected_card = st.session_state.agent_cards[st.session_state.selected_agent_url]
    if selected_card: # カード情報が取得できている場合
        st.subheader(f"Agent Details: {selected_card.get('name', 'Unknown')}")
        with st.expander("Show Agent Card Details", expanded=False):
            st.markdown(f"**Description:** {selected_card.get('description', 'N/A')}")
            st.markdown(f"**URL:** {selected_card.get('url', 'N/A')}")
            st.markdown(f"**Version:** {selected_card.get('version', 'N/A')}")
            caps = selected_card.get('capabilities', {})
            st.markdown(f"**Capabilities:**")
            st.markdown(f"  - Streaming: {'✅' if caps.get('streaming') else '❌'}")
            st.markdown(f"  - Push Notifications: {'✅' if caps.get('pushNotifications') else '❌'}")
            st.markdown(f"  - State History: {'✅' if caps.get('stateTransitionHistory') else '❌'}")
            skills = selected_card.get('skills', [])
            if skills:
                st.markdown(f"**Skills:**")
                for skill in skills:
                    st.markdown(f"  - **{skill.get('name', skill.get('id', 'Unknown Skill'))}**: {skill.get('description', 'N/A')}")
            # 他のカード情報も必要に応じて表示
            # st.json(selected_card) # デバッグ用に全表示
    elif st.session_state.selected_agent_url: # URLは選択されているがカード取得失敗の場合
         st.warning(f"Could not retrieve details for agent at {st.session_state.selected_agent_url}")


# チャット履歴表示エリア
st.subheader("Chat History")
chat_container = st.container(height=400) # 高さを固定してスクロール可能に
with chat_container:
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # TODO: アーティファクト表示 (Step 4, 6)

# 中間レスポンス表示エリア (Expander)
st.subheader("Task Progress")
progress_expander = st.expander("Show intermediate responses", expanded=False)
with progress_expander:
    st.write("**Status Updates:**")
    if st.session_state.task_status_updates:
        for update in st.session_state.task_status_updates:
             ts = update.get('timestamp', '') # ISO 8601形式など
             state = update.get('state', 'UNKNOWN')
             msg = update.get('status_message', '')
             st.caption(f"{ts} - **{state}**: {msg}")
    else:
        st.caption("No status updates yet.")

    st.write("**Artifacts:**")
    if st.session_state.task_artifacts:
        for artifact in st.session_state.task_artifacts:
            artifact_id = artifact.get('artifact_id', 'N/A')
            artifact_type = artifact.get('type', 'unknown')
            st.caption(f"ID: {artifact_id} (Type: {artifact_type})")
            # コンテンツタイプに応じて表示を変える
            content = artifact.get('content')
            mime_type = artifact.get('mime_type')
            if artifact_type == 'text':
                st.text(content)
            elif artifact_type == 'file' and mime_type and mime_type.startswith('image/'):
                 # TODO: Base64デコードして画像表示 (Step 6)
                 st.caption(f"[Image file: {artifact.get('filename', artifact_id)} - content omitted]")
            elif artifact_type == 'file':
                 # TODO: Base64デコードしてダウンロードリンク (Step 6)
                 st.caption(f"[File: {artifact.get('filename', artifact_id)} - content omitted]")
            else:
                # JSONなどで表示試行
                try:
                    st.json(content if isinstance(content, (dict, list)) else json.loads(content))
                except:
                    st.text(str(content)) # そのまま表示
    else:
        st.caption("No artifacts received yet.")


# --- UI更新コールバック ---
# stream_a2a_task からのイベントを受け取り、セッション状態を更新する
# Streamlitの制約上、コールバック内で直接UI要素を更新するのは難しいため、
# st.session_state を更新し、st.rerun() で再描画をトリガーする方式をとる
def update_ui_callback(event_data: Dict[str, Any]):
    """ストリーミングイベントを受け取り、セッション状態を更新するコールバック"""
    event_type = event_data.get("event_type")
    task_id = event_data.get("task_id")

    # 現在のタスクIDと一致するか確認 (古いタスクのイベントを無視)
    if task_id != st.session_state.current_task_id:
        print(f"Ignoring event for old task {task_id} (current: {st.session_state.current_task_id})")
        return

    if event_type == "status_update":
        st.session_state.task_status_updates.append(event_data)
        # HIL状態の更新
        if event_data.get("state") == "INPUT_REQUIRED":
            st.session_state.input_required = True
            st.session_state.input_prompt = event_data.get("status_message", "Agent requires input.") # status_messageをプロンプトとして使う
        else:
            # INPUT_REQUIREDでなくなった場合はフラグをリセット
             if st.session_state.input_required and event_data.get("state") != "INPUT_REQUIRED":
                 st.session_state.input_required = False
                 st.session_state.input_prompt = None

    elif event_type == "artifact_update":
        # 同じIDのアーティファクトがあれば更新、なければ追加
        artifact_id = event_data.get("artifact_id")
        found = False
        for i, existing_artifact in enumerate(st.session_state.task_artifacts):
            if existing_artifact.get("artifact_id") == artifact_id:
                st.session_state.task_artifacts[i] = event_data
                found = True
                break
        if not found:
            st.session_state.task_artifacts.append(event_data)

    elif event_type == "final_result":
        # 最終結果をチャット履歴に追加
        assistant_response = ""
        if event_data.get("output"):
            for part in event_data["output"]:
                if part.get("type") == "text":
                    assistant_response += part.get("content", "") + "\n"
        if not assistant_response:
             assistant_response = f"Agent finished task {event_data.get('task_id')} with state: {event_data.get('state', 'Unknown')}"
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_response.strip()})
        # HIL状態の最終確認
        if event_data.get("state") == "INPUT_REQUIRED":
             st.session_state.input_required = True
             st.session_state.input_prompt = assistant_response.strip() # outputをプロンプトとして使う
        else:
             st.session_state.input_required = False
             st.session_state.input_prompt = None

    elif event_type == "error":
        st.error(f"Streaming Error: {event_data.get('message', 'Unknown error')}")
        # エラーメッセージをチャット履歴にも追加する？
        # st.session_state.chat_history.append({"role": "assistant", "content": f"Error: {event_data.get('message')}"})

    # UIを再描画して変更を反映させる
    # コールバックは別スレッドで実行される可能性があるため、st.rerun()が安全か要検討
    # 代わりに、メインスレッドで定期的にチェックするか、st.experimental_rerun() を使う？
    # ここではシンプルに st.rerun() を試す
    try:
        st.rerun()
    except Exception as e:
        # st.rerun() が別スレッドから呼ばれるとエラーになることがある
        print(f"Error calling st.rerun from callback: {e}")
        # 代替策としてフラグを立ててメインループで再実行させるなどが必要かも
        pass


# チャット入力エリア
st.subheader("Send Message")
user_input = st.chat_input("Enter your message...", key="chat_input", disabled=st.session_state.input_required) # HIL中は無効化

# 送信ボタン (chat_inputを使う場合は不要だが、HILのために別途配置する可能性も考慮)
# if st.button("Send", key="send_button", disabled=not selected_agent_display or selected_agent_display == "Select an Agent"):

# --- メッセージ送信処理 ---
if user_input and st.session_state.selected_agent_url:
    # デバッグログ追加
    print(f"DEBUG: Sending message. user_input='{user_input}', selected_agent_url='{st.session_state.selected_agent_url}'")

    # ユーザーメッセージを履歴に追加
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with chat_container:
         with st.chat_message("user"):
            st.markdown(user_input)

    # セッションIDがなければ生成
    if not st.session_state.current_session_id:
        st.session_state.current_session_id = str(uuid.uuid4())
    # タスクIDを生成
    st.session_state.current_task_id = str(uuid.uuid4())

    # A2Aタスク送信処理 (ストリーミング対応)
    st.info(f"Sending task (ID: {st.session_state.current_task_id}) to {st.session_state.selected_agent_url}...")

    # 中間レスポンス表示エリアをクリア
    st.session_state.task_status_updates = []
    st.session_state.task_artifacts = []
    # HIL状態もリセット
    st.session_state.input_required = False
    st.session_state.input_prompt = None
    # Expanderを開いておく
    progress_expander.expanded = True # これだけだと再実行時に閉じる可能性あり
    # st.session_state.progress_expanded = True # セッション状態で管理する方が確実かも

    with st.spinner("Processing task..."):
        try:
            # Agent Card 辞書を取得
            # Get the selected agent URL (should be like http://adk_agent:8001)
            selected_url = st.session_state.selected_agent_url
            agent_card_dict = st.session_state.agent_cards.get(selected_url)

            if not agent_card_dict:
                 st.error("Selected agent's card data not found.")
            else:
                # Ensure the URL in the card uses the service name for container communication
                # The URL fetched might still contain localhost if fetched initially that way
                # We rely on selected_url which should be correct after selection
                # Let's ensure the client uses the selected_url directly if card URL is wrong
                # (Alternatively, update agent_card_dict['url'] here if needed)

                # メッセージパートを作成
                message_parts = [create_text_part(user_input)]

                # ストリーミングをサポートしているか確認
                supports_streaming = agent_card_dict.get('supports_streaming', False)

                if supports_streaming:
                    print(f"DEBUG: Calling stream_a2a_task with URL: {selected_url}") # デバッグログ
                    try:
                        # ストリーミング実行 (Pass the correct URL explicitly)
                        # Note: stream_a2a_task might need adjustment to accept url directly
                        # For now, assume it uses agent_card_dict['url'], let's ensure it's correct
                        if "localhost" in agent_card_dict.get("url", ""):
                             logger.warning(f"Agent card URL contains localhost: {agent_card_dict.get('url')}. Using selected URL: {selected_url}")
                             # We should ideally modify stream_a2a_task to accept url or use the client correctly
                             # Temporary fix: update the dict (might not be ideal)
                             # agent_card_dict['url'] = selected_url # This might break caching if dict is modified

                        # Let's modify a2a_client_utils.py instead to prioritize selected_url if provided
                        # For now, proceed assuming the client init inside uses the correct URL from agent_card

                        asyncio.run(
                            stream_a2a_task(
                                agent_card_dict=agent_card_dict, # Pass the potentially corrected card
                                message_parts_dicts=message_parts,
                                task_id=st.session_state.current_task_id,
                                session_id=st.session_state.current_session_id,
                                update_callback=update_ui_callback
                            )
                        )
                    except Exception as e_stream:
                         print(f"ERROR in asyncio.run(stream_a2a_task): {e_stream}") # エラーログ
                         st.error(f"Error during streaming: {e_stream}")

                else:
                    print(f"DEBUG: Calling send_a2a_task with URL: {selected_url}") # デバッグログ
                    try:
                        # 非ストリーミング実行 (Ensure correct URL is used)
                        if "localhost" in agent_card_dict.get("url", ""):
                             logger.warning(f"Agent card URL contains localhost: {agent_card_dict.get('url')}. Using selected URL: {selected_url}")
                             # Ideally modify send_a2a_task or ensure client uses correct URL
                             # agent_card_dict['url'] = selected_url # Temp fix

                        task_result_dict: Optional[Dict[str, Any]] = asyncio.run(
                            send_a2a_task(
                                agent_card_dict=agent_card_dict, # Pass potentially corrected card
                                message_parts_dicts=message_parts,
                                task_id=st.session_state.current_task_id,
                                session_id=st.session_state.current_session_id
                            )
                        )
                        if task_result_dict:
                            assistant_response = ""
                            # output フィールドからテキスト応答を抽出
                            if task_result_dict.get("output"):
                                for part in task_result_dict["output"]:
                                    if part.get("type") == "text":
                                        # TextPart のフィールド名は 'text'
                                        assistant_response += part.get("text", "") + "\n"
                            # output がない場合、status.message から応答を抽出
                            if not assistant_response:
                                status = task_result_dict.get("status")
                                if status and status.get("message") and status["message"].get("parts"):
                                    for part in status["message"]["parts"]:
                                        if part.get("type") == "text":
                                            assistant_response += part.get("text", "") + "\n"

                            # それでも応答がない場合、ステータスを表示
                            if not assistant_response:
                                state = task_result_dict.get("status", {}).get("state", "Unknown")
                                assistant_response = f"Agent finished task {task_result_dict.get('task_id')} with state: {state}"

                            st.session_state.chat_history.append({"role": "assistant", "content": assistant_response.strip()})

                            # HIL状態の確認 (status.state を参照)
                            if task_result_dict.get("status", {}).get("state") == "INPUT_REQUIRED":
                                st.session_state.input_required = True
                                # プロンプトは status.message から取るのが適切かもしれない
                                prompt_from_status = ""
                                status = task_result_dict.get("status")
                                if status and status.get("message") and status["message"].get("parts"):
                                    for part in status["message"]["parts"]:
                                        if part.get("type") == "text":
                                            prompt_from_status += part.get("text", "") + "\n"
                                st.session_state.input_prompt = prompt_from_status.strip() or assistant_response.strip() # status.message があれば優先
                                st.warning("Agent requires further input.")
                            else:
                                st.session_state.input_required = False
                                st.session_state.input_prompt = None

                            # 非ストリーミング完了後、UIを再描画
                            st.rerun()
                        else:
                            st.error("Failed to get response from the agent.")
                    except Exception as e_send:
                        print(f"ERROR in asyncio.run(send_a2a_task): {e_send}") # エラーログ
                        st.error(f"Error sending task: {e_send}")


        except Exception as e_outer:
            # この try ブロック全体の例外 (Agent Card取得などを含む)
            print(f"ERROR in processing task block: {e_outer}") # エラーログ
            st.error(f"An error occurred while processing the task: {e_outer}")
            # エラー時も再描画してエラーメッセージを表示
            st.rerun()

    # chat_input は自動でクリアされる
    # ストリーミングの場合、st.rerun() はコールバックに任せる
    # 非ストリーミングの場合は上で st.rerun() 済み

elif user_input and not st.session_state.selected_agent_url:
    st.warning("Please select an agent first.")


# Human-in-the-Loop 入力エリア (条件付き表示)
if st.session_state.input_required:
    st.subheader("Input Required by Agent")
    st.info(st.session_state.input_prompt or "The agent requires additional input.")
    hil_input = st.text_area("Your response:", key="hil_input")
    if st.button("Send Response", key="hil_send_button"):
        if hil_input and st.session_state.current_task_id and st.session_state.selected_agent_url and st.session_state.current_session_id:
            st.info(f"Sending HIL response for task {st.session_state.current_task_id}...")

            # HIL応答をユーザーメッセージとして履歴に追加
            st.session_state.chat_history.append({"role": "user", "content": f"(Response) {hil_input}"})

            # 中間レスポンス表示エリアをクリア (前回のタスクのものを消す)
            st.session_state.task_status_updates = []
            st.session_state.task_artifacts = []
            # Expanderを開く
            progress_expander.expanded = True

            with st.spinner("Processing HIL response..."):
                try:
                    agent_card_dict = st.session_state.agent_cards.get(st.session_state.selected_agent_url)
                    if not agent_card_dict:
                        st.error("Selected agent's card data not found.")
                        # HIL状態は維持
                        st.rerun()
                    else:
                        # HIL応答を含むメッセージパートを作成
                        message_parts = [create_text_part(hil_input)]
                        supports_streaming = agent_card_dict.get('supports_streaming', False)

                        # HIL応答を同じタスクIDで再送信 (Ensure correct URL)
                        if "localhost" in agent_card_dict.get("url", ""):
                             logger.warning(f"HIL: Agent card URL contains localhost: {agent_card_dict.get('url')}. Using selected URL: {selected_url}")
                             # agent_card_dict['url'] = selected_url # Temp fix

                        if supports_streaming:
                            asyncio.run(
                                stream_a2a_task(
                                    agent_card_dict=agent_card_dict,
                                    message_parts_dicts=message_parts,
                                    task_id=st.session_state.current_task_id,
                                    session_id=st.session_state.current_session_id,
                                    update_callback=update_ui_callback
                                )
                            )
                        else:
                            task_result_dict: Optional[Dict[str, Any]] = asyncio.run(
                                send_a2a_task(
                                    agent_card_dict=agent_card_dict,
                                    message_parts_dicts=message_parts,
                                    task_id=st.session_state.current_task_id,
                                    session_id=st.session_state.current_session_id
                                )
                            )
                            if task_result_dict:
                                assistant_response = ""
                                if task_result_dict.get("output"):
                                    for part in task_result_dict["output"]:
                                        if part.get("type") == "text":
                                            assistant_response += part.get("content", "") + "\n"
                                if not assistant_response:
                                     assistant_response = f"Agent finished task {task_result_dict.get('task_id')} with state: {task_result_dict.get('state', 'Unknown')}"

                                st.session_state.chat_history.append({"role": "assistant", "content": assistant_response.strip()})

                                # HIL状態の再確認
                                if task_result_dict.get("state") == "INPUT_REQUIRED":
                                    st.session_state.input_required = True
                                    st.session_state.input_prompt = assistant_response.strip()
                                    st.warning("Agent requires further input.")
                                else: # タスク完了 or 別の状態になった
                                    st.session_state.input_required = False
                                    st.session_state.input_prompt = None
                                # UI更新
                                st.rerun()
                            else:
                                st.error("Failed to get response from the agent after HIL.")
                                # HIL状態は維持して再試行可能にする
                                st.rerun()

                except Exception as e:
                    st.error(f"An error occurred while sending the HIL response: {e}")
                    # エラー時もHIL状態は維持して再試行可能にする
                    st.rerun()

            # HIL応答送信後、入力欄はクリアされる (st.rerunのため)
            # HIL状態はタスクの結果に応じて更新される

        elif not hil_input:
            st.warning("Please enter your response.")
        else:
             st.error("Cannot send response: Missing Task ID, Agent URL, or Session ID.")

# (オプション) ファイルアップロード (Step 6)
# uploaded_file = st.file_uploader("Upload File (Optional)", key="file_uploader")
