# Agent2Agent (A2A) プロトコル調査レポート

## 1. はじめに

本レポートは、Agent2Agent (A2A) プロトコルにおける最初のインプット方法、およびアプリケーションレイヤーからの具体的な実装方法について調査した結果をまとめたものである。特に、StreamlitアプリケーションからA2Aエージェントを呼び出す際の参考となる情報を提供することを目的とする。

## 2. A2Aプロトコルの概要と初期インプット方法

### 2.1. コアコンセプト

`google/A2A` リポジトリの調査に基づき、A2Aプロトコルの主要な概念は以下の通りである。

*   **Agent Card:** エージェントの能力、スキル、エンドポイントURL、認証要件などを記述した公開メタデータファイル (通常 `/.well-known/agent.json`)。クライアントはこれを発見に利用する。
*   **A2A Server:** A2Aプロトコルメソッドを実装したHTTPエンドポイントを公開するエージェント。リクエストを受け取り、タスク実行を管理する。
*   **A2A Client:** A2Aサービスを利用するアプリケーションまたは他のエージェント。A2A ServerのURLにリクエスト (`tasks/send` など) を送信する。
*   **Task:** 作業の中心単位。クライアントがメッセージ (`tasks/send` または `tasks/sendSubscribe`) を送信して開始する。ユニークなIDを持ち、状態 (`submitted`, `working`, `input-required`, `completed` など) が遷移する。
*   **Message:** クライアント (`role: "user"`) とエージェント (`role: "agent"`) 間の通信ターンを表す。`Parts` を含む。
*   **Part:** `Message` または `Artifact` 内の基本的なコンテンツ単位。`TextPart` (テキスト)、`FilePart` (ファイル、インラインバイトまたはURI)、`DataPart` (構造化JSON、例: フォーム) がある。
*   **Artifact:** タスク中にエージェントが生成した出力 (生成ファイル、最終的な構造化データなど)。`Parts` を含む。
*   **Streaming:** 長時間実行タスク向け。サーバーが `streaming` 能力をサポートする場合、クライアントは `tasks/sendSubscribe` を使用できる。クライアントはServer-Sent Events (SSE) でリアルタイムな進捗 (`TaskStatusUpdateEvent`, `TaskArtifactUpdateEvent`) を受信する。
*   **Push Notifications:** サーバーが `pushNotifications` をサポートする場合、クライアントが提供したWebhook URLにタスク更新をプッシュ通知できる。

### 2.2. タスク開始フロー (初期インプット)

A2Aプロトコルにおけるタスクの開始、すなわち最初のインプットは、以下の流れで行われる。

1.  **Discovery (任意):** A2A Client (アプリケーション) は、対象エージェントの Agent Card を取得し、エンドポイントURLや能力を確認する。
2.  **Initiation:** A2A Client は、A2A Server のエンドポイントURLに対し、HTTP POSTリクエストとして `tasks/send` または `tasks/sendSubscribe` メソッドを呼び出す。
3.  **リクエスト内容:** このリクエストのペイロードには、少なくとも以下の情報が含まれる。
    *   `id`: ユニークなタスクID (クライアントが生成)。
    *   `message`: 最初のインプットとなるメッセージオブジェクト。
        *   `role`: `"user"`
        *   `parts`: 実際のコンテンツを含む `Part` オブジェクトのリスト (例: `TextPart`, `FilePart`)。

これにより、**アプリケーションレイヤーは、A2A Server のAPIエンドポイントを直接呼び出す形で、A2Aプロトコルを利用してエージェントにタスクと初期インプットを与えることができる。**

## 3. `google/A2A` Pythonクライアント実装調査

Streamlitアプリケーションでの実装の参考とするため、`google/A2A` リポジトリに含まれるPythonのCLIクライアントサンプル (`samples/python/hosts/cli/__main__.py`) の実装を調査した。

### 3.1. 主要な機能と実装方法

*   **Agent Card 取得:**
    *   `common.client.A2ACardResolver(agent_url).get_agent_card()` を使用してAgent Cardを取得。
*   **A2Aクライアント初期化:**
    *   取得したAgent Cardを `common.client.A2AClient(agent_card=card)` に渡してクライアントを初期化。
*   **タスク送信:**
    *   ユーザー入力 (テキスト、ファイルパス) から `message` オブジェクト (辞書形式) を作成。ファイルはBase64エンコードして `FilePart` に含める。
    *   `payload` (タスクID, セッションID, メッセージ等を含む辞書) を作成。
    *   非ストリーミングの場合: `await client.send_task(payload)` を呼び出し、最終的な `Task` オブジェクトを受け取る。
    *   ストリーミングの場合: `client.send_task_streaming(payload)` を呼び出し、非同期イテレータを取得。
*   **ストリーミング処理:**
    *   `async for result in response_stream:` ループで、SSE経由で送られてくる中間イベント (`TaskStatusUpdateEvent`, `TaskArtifactUpdateEvent`) を非同期に受信・処理。
*   **Human-in-the-Loop (HIL):**
    *   受信したタスク結果の `state` が `TaskState.INPUT_REQUIRED` かどうかを確認。
    *   `INPUT_REQUIRED` の場合、再度ユーザーに入力を促し、その入力を含めて同じタスクIDで `send_task` または `send_task_streaming` を再帰的に呼び出す。
*   **状態管理:**
    *   `sessionId` と `taskId` を変数で管理し、リクエストペイロードに含めることで、会話の継続性やタスクの追跡を行っている。

### 3.2. Streamlit実装への応用ポイント

*   **非同期処理:** Streamlitは基本的に同期的だが、A2Aクライアントの操作 (特にストリーミング) は非同期であるため、`streamlit-async` ライブラリなどを利用して非同期関数を実行する必要がある。
*   **状態管理:** 会話履歴、サーバーリスト、選択中のエージェント、現在のタスクID/セッションID、タスクの状態などを `st.session_state` で適切に管理する必要がある。
*   **UI更新:** ストリーミングイベント受信時やHILでの応答時に、`st.empty()` やコンテナの更新を利用してUIを動的に更新する。
*   **コードの再利用:** `google/A2A` の `samples/python/common` 内の `client.py`, `types.py` をサブモジュール経由で利用することで、A2Aプロトコルの詳細な実装を意識せずにクライアント機能を実装できる。

## 4. まとめ

A2Aプロトコルは、アプリケーションレイヤーからHTTPリクエストを通じて直接利用可能であり、テキスト、ファイル、構造化データなど多様な形式で初期インプットを与えることができる。ストリーミングやHuman-in-the-Loopといった高度な機能も提供されている。

`google/A2A` リポジトリのPythonサンプルコードは、これらの機能を実装する上で重要な参照情報となる。StreamlitでA2Aクライアントアプリケーションを実装する際は、非同期処理と状態管理が鍵となる。