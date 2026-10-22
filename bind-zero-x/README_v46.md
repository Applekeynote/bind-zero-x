# BIND ZERO-X v4.6 — 検証可能な研究用改訂版

v4.6を最新版とする。v4.2〜v4.5の文書とCSVは履歴。現在の正本は`BIND_ZERO_X_v4.6_正式改訂仕様_PCIG証拠連鎖と視覚再観測.md`とv4.6の試験台帳。

## ローカルテスト

```bash
python -m pip install -r requirements-dev-v45.txt
PYTHONPATH=code python -m unittest discover -s code -p 'test_*.py' -v
PYTHONPATH=code python comparisons/finite_model_ablation.py
```

- `code/test_v46_integrity.py`: 固定モデル指紋、履歴検証、SQLite MAC、撮影予算、OpenCV失敗。
- `code/test_v46_image_api.py`: 研究用画像再観測API。**OpenCV 5の文字列をモックした一部のテストはOpenCV 4実行**であり、OpenCV 5検証とは区別。
- `code/test_v46_ablation.py`: 人工モデルの負の対照・比較の数理検算。実物性能ではない。
- `reports/v46_unittest_verbose.log`: 実行ログ。`reports/v46_execution_summary.json`に環境情報と件数。

## API

- `POST /api/research/loop/start` — 研究用の仮説モデルと撮影予算からセッションを作成。
- `POST /api/research/loop/reobserve` — **人手観測**から次の世界集合を更新。CVの出力だと偽らない。
- `POST /api/research/loop/reobserve-image` — OpenCV 5必須。画像/ROI/校正をサーバで計測し、観測証跡を追加する。**未校正では世界集合を絞らない**。
- `POST /api/research/analyze` — 単発の研究用2フレーム解析。
- `/health`, `/ready` — 実行条件を報告。物理操作許可なし。

研究用APIは単一トークン、ローカルSQLite、手動ROI前提。インターネット公開・本番運用・安全保証には使用しない。

## SQLite MAC鍵

`BZX_RESEARCH_INTEGRITY_KEY` に32文字以上の別管理秘密文字列を設定する。本番ではSecrets Manager等から設定すること。未設定のローカル実行ではDB横に`.hmac_key`を作成する開発用フォールバックを使い、DBと鍵を同時に変更できる攻撃者には耐えない。

## デプロイと大会要件

`deploy/Dockerfile` はOpenCV 5で研究APIを起動する想定だが、**この成果物をAWSで実行・検証した証拠はない**。実際のEC2/OpenCV5/S3/DynamoDB/認可/Bedrock/本番Web UI/実物GT/比較試験は未完了。

## 負の結果も保持

仮説モデル内のアブレーション結果は`comparisons/finite_model_ablation_result.json`。実測改善は示していない。旧資料の「95点超」は実証目標を意味する。

## 配布ファイル

`SHA256SUMS_v46.txt`にZIP内全コンテンツ（SHAファイル自体は除く）のハッシュを収録。v4.5以前のSHA一覧は履歴でありv4.6の検証正本ではない。
