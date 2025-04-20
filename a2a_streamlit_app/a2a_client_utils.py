
import asyncio
import httpx
import logging
from typing import Optional, Dict, Any, List
# import sys # sys.path 操作は不要になったので削除
# import os # os モジュールも不要になったので削除

# --- google_a2a_common ライブラリのインポート ---
# lib ディレクトリから直接インポート
try:
    from lib.google_a2a_common.client.card_resolver import A2ACardResolver
    from lib.google_a2a_common.client.client import A2AClient
    # types モジュールを別名でインポートして衝突回避
    from lib.google_a2a_common import types as a2a_types
    # A2AClientJSONError も types からインポート
    from lib.google_a2a_common.types import A2AClientJSONError
except ImportError as e:
    logging.error(f"Failed to import google_a2a_common library from lib/: {e}")
    # ここでエラーが発生する場合、コピーが正しく行われていないか、
    # google_a2a_common 内部の依存関係に問題がある可能性がある
    # フォールバック用のダミー定義は削除 (インポート成功を前提とする)
    raise # エラーを再送出して問題を明確にする


logging.basicConfig(level=logging.INFO)
def get_agent_card(url: str) -> Optional[Dict[str, Any]]:
    """
    指定されたURLからAgent Cardを取得する同期関数。

    Args:
        url: Agent Cardを取得するA2AサーバーのURL。

    Returns:
        取得したAgent Cardの辞書表現。取得失敗時はNone。
    """
    try:
        # A2ACardResolver は base_url を必須引数として取る
        resolver = A2ACardResolver(base_url=url)
        logging.info(f"Attempting to get Agent Card from: {url}")
        # get_agent_card メソッドを呼び出す (同期)
        card: Optional[a2a_types.AgentCard] = resolver.get_agent_card()
        if card:
            logging.info(f"Successfully got Agent Card from: {url}")
            # pydanticモデルを辞書に変換して返す
            return card.model_dump(mode='json')
        else:
            logging.warning(f"Could not get Agent Card from: {url}")
            return None
    # httpx.RequestError は get_agent_card 内部で処理される可能性があるが、念のため捕捉
    except httpx.RequestError as e:
        logging.error(f"HTTP request error while getting Agent Card from {url}: {e}")
        return None
    except A2AClientJSONError as e: # types からインポートしたエラーを使用
         logging.error(f"JSON decode error while getting Agent Card from {url}: {e}")
         return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while getting Agent Card from {url}: {e}")
        return None

# send_a2a_task と stream_a2a_task は非同期のまま (A2AClient のメソッドが非同期のため)
async def send_a2a_task(agent_card_dict: Dict[str, Any], message_parts_dicts: List[Dict[str, Any]], task_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    """
    A2Aタスクを送信する (非ストリーミング)。

    Args:
        agent_card_dict: Agent Card の辞書表現。
        message_parts_dicts: 送信するメッセージパートの辞書表現のリスト。
        task_id: タスクID。
        session_id: セッションID。

    Returns:
        取得した Task オブジェクトの辞書表現。取得失敗時はNone。
    """
    try:
        # AgentCard辞書をPydanticモデルにパース (a2a_types を使用)
        agent_card = a2a_types.AgentCard.model_validate(agent_card_dict)

        # MessagePart辞書をPydanticモデルにパース (a2a_types を使用)
        message_parts: List[a2a_types.MessagePart] = []
        for part_dict in message_parts_dicts:
            if part_dict.get("type") == "text":
                message_parts.append(a2a_types.TextPart.model_validate(part_dict))
            # TODO: FilePartの処理 (Step 6)
            # elif part_dict.get("type") == "file":
            #     message_parts.append(a2a_types.FilePart.model_validate(part_dict))
            else:
                logging.warning(f"Unsupported message part type: {part_dict.get('type')}")

        if not message_parts:
            logging.error("No valid message parts to send.")
            return None

        # A2AClient は agent_card または url で初期化 (client 引数は不要)
        # httpx.AsyncClient のコンテキストマネージャも不要 (内部で管理されるため)
        client = A2AClient(agent_card=agent_card)
        logging.info(f"Sending task {task_id} (session: {session_id}) to {agent_card.url}")

        # send_task メソッドは payload 辞書を引数に取る
        payload = {
            "id": task_id,
            "sessionId": session_id,
            "message": a2a_types.Message(role="user", parts=message_parts).model_dump(mode='json')
            # acceptedOutputModes など、他のパラメータも必要に応じて追加
        }

        # a2a_types.Task を使用 (send_task の戻り値は SendTaskResponse だが、中身は Task 相当のはず)
        # client.py を見ると send_task は SendTaskResponse を返す。中身は Task ではない。
        # send_task の戻り値は JSONRPCResponse 形式の辞書のはず。
        # response_dict = await client.send_task(payload) # client.py の send_task は SendTaskResponse を返す
        # SendTaskResponse は result フィールドに Task を持つはず
        # response = await client.send_task(payload)
        # task_result: Optional[a2a_types.Task] = response.result if response else None

        # client.py の send_task は JSONRPCRequest を作成し、_send_request を呼ぶ。
        # _send_request は辞書を返す。SendTaskResponse でラップして返す。
        # なので、戻り値は SendTaskResponse オブジェクト。
        response = await client.send_task(payload)

        if response and response.result:
            task_result: a2a_types.Task = response.result
            logging.info(f"Received task result for {task_id}: State={task_result.status.state}")
            return task_result.model_dump(mode='json')
        else:
            logging.warning(f"No valid task result received for {task_id}. Response: {response}")
            return None
    except httpx.RequestError as e:
        logging.error(f"HTTP request error while sending task {task_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending task {task_id}: {e}")
        return None


async def stream_a2a_task(agent_card_dict: Dict[str, Any], message_parts_dicts: List[Dict[str, Any]], task_id: str, session_id: str, update_callback: callable):
    """
    A2Aタスクを送信し、ストリーミングでイベントを受け取る非同期ジェネレータ。

    Args:
        agent_card_dict: Agent Card の辞書表現。
        message_parts_dicts: 送信するメッセージパートの辞書表現のリスト。
        task_id: タスクID。
        session_id: セッションID。
        update_callback: イベント受信時に呼び出されるコールバック関数。
                         イベントデータ (辞書) を引数として受け取る。
    """
    final_task_result: Optional[a2a_types.Task] = None # a2a_types を使用
    try:
        # AgentCard辞書をPydanticモデルにパース (a2a_types を使用)
        agent_card = a2a_types.AgentCard.model_validate(agent_card_dict)

        # MessagePart辞書をPydanticモデルにパース (a2a_types を使用)
        message_parts: List[a2a_types.MessagePart] = []
        for part_dict in message_parts_dicts:
            if part_dict.get("type") == "text":
                message_parts.append(a2a_types.TextPart.model_validate(part_dict))
            # TODO: FilePartの処理 (Step 6)
            else:
                logging.warning(f"Unsupported message part type: {part_dict.get('type')}")

        if not message_parts:
            logging.error("No valid message parts to send.")
            await update_callback({"event_type": "error", "message": "No valid message parts."})
            return

        # A2AClient は agent_card または url で初期化 (client 引数は不要)
        # httpx.AsyncClient のコンテキストマネージャも不要
        client = A2AClient(agent_card=agent_card)
        logging.info(f"Streaming task {task_id} (session: {session_id}) to {agent_card.url}")

        # send_task_streaming メソッドは payload 辞書を引数に取る
        payload = {
            "id": task_id,
            "sessionId": session_id,
            "message": a2a_types.Message(role="user", parts=message_parts).model_dump(mode='json')
            # acceptedOutputModes など、他のパラメータも必要に応じて追加
        }

        # send_task_streaming は AsyncIterable[SendTaskStreamingResponse] を返す
        async for response in client.send_task_streaming(payload):
            # response は SendTaskStreamingResponse オブジェクト
            # 中身は TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task のいずれかのはず
            # client.py を見ると、SSE の data を SendTaskStreamingResponse でラップしている
            # SendTaskStreamingResponse は result フィールドを持つ
            if response and response.result:
                event = response.result # result が実際のイベントデータ (Task, TaskStatusUpdateEvent など)
                event_dict = event.model_dump(mode='json') # イベントデータを辞書化

                # a2a_types を使用して型チェック
                if isinstance(event, a2a_types.TaskStatusUpdateEvent):
                    logging.info(f"Task {task_id} Status Update: {event.status.state} - {event.status.message}") # status オブジェクト経由でアクセス
                    await update_callback({"event_type": "status_update", **event_dict})
                elif isinstance(event, a2a_types.TaskArtifactUpdateEvent):
                    logging.info(f"Task {task_id} Artifact Update: {event.artifact.name if event.artifact else 'N/A'}") # artifact オブジェクト経由
                    await update_callback({"event_type": "artifact_update", **event_dict})
                elif isinstance(event, a2a_types.Task): # ストリームの最後はTaskオブジェクト
                    logging.info(f"Task {task_id} Final Result Received: State={event.status.state}") # status オブジェクト経由
                    final_task_result = event
                    # コールバックにも最終結果を送る (一貫性のため)
                    await update_callback({"event_type": "final_result", **event_dict})
                else:
                     logging.warning(f"Received unknown event type in stream: {type(event)}")
                     await update_callback({"event_type": "unknown", **event_dict})
            else:
                logging.warning(f"Received empty or invalid response in stream for task {task_id}: {response}")

    except httpx.RequestError as e:
        logging.error(f"HTTP request error during streaming task {task_id}: {e}")
        await update_callback({"event_type": "error", "message": f"HTTP request error: {e}"})
    except Exception as e:
        logging.error(f"An unexpected error occurred during streaming task {task_id}: {e}")
        await update_callback({"event_type": "error", "message": f"An unexpected error occurred: {e}"})

    # ストリームが終了しても final_task_result がない場合 (エラーなど)
    if final_task_result is None:
         logging.warning(f"Streaming finished for task {task_id} but no final Task object was received.")
         # 必要であれば、エラー状態を示す最終イベントをコールバックに送る
         # await update_callback({"event_type": "error", "message": "Streaming finished without final result."})


# --- ヘルパー関数 ---
def create_text_part(content: str) -> Dict[str, Any]:
    """TextPartの辞書表現を作成する"""
    try:
        # Pydanticモデルを作成して辞書に変換 (フィールド名を 'text' に修正)
        return a2a_types.TextPart(text=content).model_dump(mode='json')
    except AttributeError: # a2a_types が DummyA2ATypes の場合など
         logging.warning("a2a_types.TextPart class not found or invalid, returning basic dict.")
         # ダミー辞書も 'text' フィールドを使うように修正 (一貫性のため)
         return {"type": "text", "text": content}

# def create_file_part(content: bytes, mime_type: str, filename: Optional[str] = None) -> Dict[str, Any]:
#     """FilePartを作成する (Step 6)"""
#     import base64
#     encoded_content = base64.b64encode(content).decode('utf-8')
#     # return FilePart(content=encoded_content, mime_type=mime_type, filename=filename).model_dump(mode='json') # google_a2aインポート成功時
#     return {"type": "file", "content": encoded_content, "mime_type": mime_type, "filename": filename}