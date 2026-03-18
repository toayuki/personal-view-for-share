
・環境構築手順：webサーバーapiサーバーともに必要
1. venv環境作成：python3 -m venv venv
2. venv環境起動：source venv/bin/activate
3. ライブラリインストール：pip install -r requirements.txt
4. venv環境離脱：deactivate

・webサーバー起動手順
1. venv環境起動：source venv/bin/activate
2. webサーバー起動：uvicorn src.main:app --reload --host 192.168.0.7 --port 3000

apiサーバー起動手順
1. venv環境起動：source venv/bin/activate
2. webサーバー起動：uvicorn src.main:app --reload --host 192.168.0.7 --port 8000

sqlite
データアクセス
apiディレクトリで以下を実行
sqlite3 main.db
