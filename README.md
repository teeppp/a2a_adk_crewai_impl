# ADK と CrewAI を用いた A2A 通信サンプル

## 概要

このプロジェクトは、Google Agent Development Kit (ADK) で作成されたエージェントと、CrewAI フレームワークで作成されたエージェント間で、Agent2Agent (A2A) プロトコルを用いた基本的な双方向通信（テキストメッセージの送受信）を行うサンプル実装です。

異なるフレームワーク間のエージェント連携の基礎をデモンストレーションすることを目的としています。

## ディレクトリ構成

```
a2a_adk_crewai_impl/
├── A2A_repo/             # Google A2Aリポジトリのクローン (samples/python を利用)
├── adk_agent/            # ADKエージェント関連ファイル
│   ├── main.py           # ADKエージェントのメインスクリプト (A2Aサーバー含む)
│   ├── adk_config.yaml   # ADKエージェントの設定ファイル
│   ├── pyproject.toml    # Pythonプロジェクト設定 (uv)
│   └── .venv/            # 仮想環境 (uvにより自動生成)
├── crewai_agent/         # CrewAIエージェント関連ファイル
│   ├── main.py           # CrewAIエージェントのメインスクリプト (A2Aサーバー含む)
│   ├── crewai_config.yaml# CrewAIエージェントの設定ファイル
│   ├── pyproject.toml    # Pythonプロジェクト設定 (uv)
│   └── .venv/            # 仮想環境 (uvにより自動生成)
├── pyproject.toml        # ルートワークスペース設定 (uv)
└── README.md             # このファイル
```

## 環境構築

1.  **前提条件:**
    *   Python 3.12 以上
    *   [uv](https://github.com/astral-sh/uv) (Pythonパッケージインストーラー兼リゾルバー)
    *   Git

2.  **リポジトリのクローン:**
    ```bash
    git clone <このプロジェクトのリポジトリURL> a2a_adk_crewai_impl
    cd a2a_adk_crewai_impl
    ```

3.  **Google A2A リポジトリのクローン:**
    プロジェクトルート (`a2a_adk_crewai_impl`) 内に Google の A2A リポジトリを `A2A_repo` という名前でクローンします。
    ```bash
    git clone https://github.com/google/A2A.git A2A_repo
    ```

4.  **Python 環境の準備 (uv):**
    プロジェクトルートで `uv` を使用して Python 3.12 をインストールします (既に適切なバージョンがあればスキップ可)。
    ```bash
    # 必要に応じて実行
    # uv python install 3.12
    ```

5.  **依存関係のインストール (uv sync):**
    `uv` のワークスペース機能を利用して、各エージェントの依存関係をインストールします。プロジェクトルートで以下のコマンドを実行します。
    ```bash
    uv sync --all-members
    ```
    これにより、`adk_agent` と `crewai_agent` の両方の仮想環境に必要なパッケージがインストールされます。

## 設定ファイル

各エージェントの動作は、それぞれのディレクトリにある `.yaml` ファイルで設定します。

*   `adk_agent/adk_config.yaml`: ADKエージェントの設定 (自身のAgent ID、待ち受けポート、接続先CrewAIエージェント情報)
*   `crewai_agent/crewai_config.yaml`: CrewAIエージェントの設定 (自身のAgent ID、待ち受けポート、接続先ADKエージェント情報)

デフォルトでは、ADKエージェントはポート `8001`、CrewAIエージェントはポート `8002` で待ち受けます。

## 実行方法

1.  **ターミナル1: CrewAI エージェントの起動**
    ```bash
    cd /path/to/a2a_adk_crewai_impl/crewai_agent
    uv run python main.py
    ```
    サーバーが `http://0.0.0.0:8002` で起動します。

2.  **ターミナル2: ADK エージェントの起動**
    ```bash
    cd /path/to/a2a_adk_crewai_impl/adk_agent
    uv run python main.py
    ```
    サーバーが `http://0.0.0.0:8001` で起動します。

## 期待される動作

1.  両エージェントが起動すると、それぞれが設定ファイルに基づいて相手のエージェントにテストメッセージ (`tasks/send` リクエスト) を送信します。
2.  各エージェントのターミナルログに、相手へのメッセージ送信ログ (`Sending test message to ...`) と、相手からのレスポンス受信ログ (`Received response from target agent: ...`) が表示されます。
3.  各エージェントのターミナルログに、相手から送信されたテストメッセージの受信ログ (`Received SendTask request: ...`) が表示されます。

これにより、基本的な双方向通信が確立されていることを確認できます。

## 留意事項

*   この実装は基本的なメッセージ送受信のデモンストレーションです。実際の CrewAI や ADK のタスク実行ロジックは含まれていません (`TaskManager` はダミー実装です)。
*   エラーハンドリングやセキュリティ対策は最小限です。
*   A2Aプロトコルは開発中のため、仕様変更により動作しなくなる可能性があります。