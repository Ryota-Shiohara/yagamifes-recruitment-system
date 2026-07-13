# 委員会新規局員採用システム

データモデリング最終課題用の、Flask + SQLite3 Webアプリケーションです。課題3の create_table.sql / insert_data.sql / hw3.db を基に、応募者の複数希望面接枠、面接確定、評価入力、評価者補正、局別ランキング、採否を管理します。登録されている氏名・メールアドレスはすべて架空データです。

## 使用技術

- Python 3.13.9（本番想定）
- Flask 3.1.2（本番想定）
- Python標準 sqlite3
- SQLite
- Jinja2 / HTML / CSS

ORMは使用せず、すべてのDB操作をSQLで記述しています。

## 主なファイル

- app.py: Flaskアプリケーション
- database.db: 実行用データベース
- database.initial.db: 初期状態の復元用データベース
- schema.sql: テーブル、制約、トリガー、VIEW
- seed.sql: 架空の初期データ
- templates/: Jinja2テンプレート
- static/style.css: 共通スタイル
- test_app.py: 正常系・異常系の自動テスト
- docs/design.md: ER、候補キー、画面とSQLの対応
- docs/requirements-draft.md: 要件定義

.htaccess と index.cgi は講義サンプルのWebサーバ設定を変更せず使用しています。

## ローカル起動

Anaconda用ターミナルで、このディレクトリへ移動して実行します。

~~~console
flask --debug run
~~~

表示された http://127.0.0.1:5000/ をブラウザで開きます。ポートが使用中の場合は次のように変更します。

~~~console
flask --debug run --port 5001
~~~

## DBを初期状態へ戻す

最も簡単な方法は、database.initial.db を複製して database.db を置き換えることです。SQLから再構築する場合は次を実行します。

~~~console
sqlite3 database.db < schema.sql
sqlite3 database.db < seed.sql
~~~

schema.sql は既存のアプリ用テーブルを削除して再作成するため、必要なデータがあるDBには実行しないでください。

## テスト

~~~console
python -m unittest -v
~~~

テスト用の一時DBを毎回作成するため、実行用 database.db は変更しません。

## 本番配置

- ~/public_html/dm_app/ 以下へ配置します。
- .htaccess と index.cgi は変更・上書きしません。
- ディレクトリ、index.cgi、app.py は755、その他のファイルは644にします。
- 本番では app.py の app.run(debug=True) は実行されません。Webサーバが index.cgi から app を読み込みます。
- 提出後は、ZIPと本番配置ファイルに差分がない状態を保ちます。
