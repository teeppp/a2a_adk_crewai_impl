# Streamlit A2A チャットアプリケーション 実装計画書

**1. 目的**

Streamlitフレームワークを使用し、Agent2Agent (A2A) プロトコルに対応したインタラクティブなチャットアプリケーションを開発する。ユーザーは複数のA2Aエージェントサーバーを登録し、選択したエージェントと対話できる。エージェントとのやり取りの中間プロセスも可視化し、Human-in-the-Loop機能も実装する。

**2. 要件**

1.  **Streamlitベース:** Streamlitを用いてWebアプリケーションとして実装する。
2.  **A2Aプロトコル通信:** アプリケーションがA2A Clientとして機能し、A2A Server (エージェント) と通信する。
3.  **サーバー/エージェント管理:**
    *   ユーザーがA2AサーバーのURLを複数登録・管理できる。
    *   登録されたサーバーからAgent Card情報を自動取得し、利用可能なエージェントを選択肢として表示する。
4.  **チャットインターフェース:**
    *   ユーザーがテキストメッセージを入力し、選択したエージェントに送信できる。
    *   エージェントからの最終応答をチャット履歴として表示する。
    *   (オプション) ファイルのアップロードと送信に対応する。
5.  **中間プロセス可視化 (要件3):** A2Aプロトコルのストリーミング機能を利用し、エージェントがタスクを処理する際の中間的なステータス更新や生成物 (Artifacts) をリアルタイムでUI上に表示する。
6.  **Human-in-the-Loop (要件4):** エージェントが追加の入力を要求した場合 (`INPUT_REQUIRED` 状態)、ユーザーが応答を入力できるインターフェースを提供し、タスクを継続できるようにする。

**3. 実装場所**

*   `/home/ubuntu/workspace/roobase/github/a2a_adk_crewai_impl`

**4. 技術スタック**

*   **UIフレームワーク:** Streamlit
*   **非同期処理:** `streamlit-async`
*   **A2Aプロトコル実装:** `google/A2A` リポジトリのPython共通ライブラリ (サブモジュールとして利用)
*   **HTTPクライアント:** `httpx` (A2A共通ライブラリが依存)
*   **データモデル:** `pydantic` (A2A共通ライブラリが依存)
*   **SSEクライアント:** `httpx-sse` または `sse-starlette` (A2Aストリーミングクライアントが依存)
*   **言語:** Python 3.12+

**5. プロジェクト構成 (案)**

```
github/a2a_adk_crewai_impl/
├── a2a_streamlit_app/         # Streamlitアプリケーションコード
│   ├── main.py                # アプリケーションエントリーポイント
│   ├── a2a_client_utils.py    # A2Aクライアント関連のラッパー/ユーティリティ関数
│   ├── ui_components.py       # Streamlit UIコンポーネント (チャット表示など)
│   └── state_manager.py       # セッション状態管理 (st.session_state)
├── google_a2a/                # google/A2Aリポジトリのサブモジュール
│   └── samples/
│       └── python/
│           └── common/        # 利用する共通ライブラリ (client.py, types.py, utils/)
│               ├── client.py
│               ├── types.py
│               └── utils/
├── requirements.txt           # Python依存ライブラリ
└── README.md                  # プロジェクト説明、実行方法など
```

**6. 実装ステップ**

*   **Step 0: 環境構築**
    1.  `github/a2a_adk_crewai_impl` ディレクトリに移動。
    2.  `google/A2A` をサブモジュールとして追加:
        ```bash
        git submodule add https://github.com/google/A2A.git google_a2a
        git submodule update --init --recursive
        ```
    3.  `requirements.txt` を作成し、必要なライブラリ (`streamlit`, `streamlit-async`, `httpx`, `pydantic`, `httpx-sse` 等) を記述。
    4.  仮想環境を作成し、`pip install -r requirements.txt` を実行。

*   **Step 1: UI骨格作成**
    1.  `a2a_streamlit_app/main.py` を作成し、基本的なStreamlitアプリの構造を定義。
    2.  サイドバーにサーバーURL管理UI (テキスト入力、追加/削除ボタン、登録済みURLリスト表示) を実装 (`st.session_state` にURLリストを保存)。
    3.  メインエリアにエージェント選択UI (空の `st.selectbox`) を配置。
    4.  チャットUI (`st.text_input`、送信ボタン、チャット履歴表示用のコンテナ) を配置。
    5.  中間レスポンス表示用のエリア (`st.expander` や `st.container`) を配置。
    6.  `st.session_state` に必要なキー (サーバーリスト、選択中エージェント、チャット履歴、現在のタスクID、セッションIDなど) を初期化する処理を追加 (`state_manager.py` に分離推奨)。

*   **Step 2: Agent Card取得と表示 (要件2)**
    1.  `a2a_client_utils.py` に、`google_a2a/samples/python/common/client.py` の `A2ACardResolver` を利用してAgent Cardを取得する非同期関数 `get_agent_card(url)` を実装。
    2.  `main.py` で `streamlit_async.run_async()` を使用し、`st.session_state` に保存されたサーバーURLリストから各サーバーのAgent Cardを取得。
    3.  取得したAgent Card情報 (エージェント名、説明など) をエージェント選択 `st.selectbox` の選択肢として表示。

*   **Step 3: 基本タスク送信 (非ストリーミング)**
    1.  `a2a_client_utils.py` に、`A2AClient` を初期化し、`send_task` を呼び出す非同期関数 `send_a2a_task(agent_card, message_parts, task_id, session_id)` を実装。メッセージ形式 (`TextPart`, `FilePart`) の作成も含む。
    2.  `main.py` の送信ボタンが押されたら、`streamlit_async.run_async()` を使用して `send_a2a_task` を呼び出す。
    3.  タスクIDとセッションIDを生成・管理 (`st.session_state`)。
    4.  返却された最終結果 (`Task` オブジェクト) からエージェントの応答メッセージを抽出し、チャット履歴 (`st.session_state` 内) に追加して表示 (`ui_components.py` で表示部分を実装推奨)。

*   **Step 4: ストリーミング対応 (要件3)**
    1.  `a2a_client_utils.py` に、`send_task_streaming` を呼び出し、非同期イテレータからイベント (`TaskStatusUpdateEvent`, `TaskArtifactUpdateEvent`) を受け取る非同期関数 `stream_a2a_task(agent_card, message_parts, task_id, session_id, update_callback)` を実装。`update_callback` はUI更新用のコールバック関数。
    2.  `main.py` で、ストリーミングが有効なエージェントの場合、`streamlit_async.run_async()` を使用して `stream_a2a_task` を呼び出す。
    3.  `update_callback` 内で、受信したイベントの内容を整形し、中間レスポンス表示エリアに追記していく処理を実装 (`st.empty()` やコンテナの更新を利用)。

*   **Step 5: Human-in-the-Loop 対応 (要件4)**
    1.  タスクのレスポンス (ストリーミング中または最終結果) を監視し、`TaskState` が `INPUT_REQUIRED` になったことを検知するロジックを追加。
    2.  検知した場合、チャット入力欄を有効化し、プロンプト (エージェントからの質問) を表示。
    3.  ユーザーが応答を入力して送信ボタンを押したら、その応答メッセージを含めて、同じタスクIDで再度 `send_a2a_task` または `stream_a2a_task` を呼び出す。

*   **Step 6: ファイル送受信 (オプション)**
    1.  `st.file_uploader` をチャットUIに追加。
    2.  アップロードされたファイルを読み込み、Base64エンコードして `FilePart` を作成し、メッセージに追加する処理を実装。
    3.  エージェントからのレスポンスに `FilePart` を含むアーティファクトがある場合、それをデコードして表示またはダウンロードリンクを提供する処理を実装。

*   **Step 7: エラーハンドリングとテスト**
    1.  `try...except` ブロックを使用して、ネットワークエラー、A2Aプロトコルエラー、ファイルI/Oエラーなどを捕捉し、ユーザーに分かりやすいエラーメッセージを表示。
    2.  各機能 (Agent Card取得、タスク送信、ストリーミング、HIL、ファイル処理) が要件通りに動作するかテスト。

**7. 成果物**

*   Streamlitアプリケーションのソースコード一式 (`a2a_streamlit_app/` ディレクトリ)。
*   `google/A2A` サブモジュールを含むプロジェクト構造。
*   依存関係ファイル (`requirements.txt`)。
*   本実装計画書 (`streamlit_a2a_chat_plan_20250419011800.md`)。
*   アプリケーションの実行方法などを記載した `README.md`。