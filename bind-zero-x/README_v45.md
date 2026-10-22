# BIND ZERO-X v4.5 — 95点超の実証を目指す研究用改訂版

**正式な追加仕様は `BIND_ZERO_X_v4.5_正式仕様_独創性と実証設計.md`。** 旧版v4.2〜v4.4の文書は変更履歴であり、矛盾する場合はv4.5が優先する。

## 実際に動く範囲
- 数学的SE(2)相対運動／合成画像へのOpenCV処理
- 限定的な仮説モデルのBIND-WITNESS/PCIG・**意味的な証明書検算（別実装の有限列挙チェッカーを併用）**・モデル/映像/校正の外部参照ピン
- 逆方向オプティカルフロー失敗などの安全な品質エラー
- 人工的モデルの複数ステップ（追加ビュー選択→人手の報告→可能世界更新→再計画）
- 研究用FastAPI（OpenCV5を要求する画像分析、別途人手観測を使う研究セッション）。ローカルSQLiteのみ

**できないこと**：実物の独立GTがない、自然画像の自動層検出なし、ひも・結び目の自動CV追跡なし、AWS接続なし、Bedrockなし、物理操作の許可なし、OpenCV5実行未検証。

## ローカル実行

```bash
python -m pip install -r requirements-dev-v45.txt
PYTHONPATH=code python -m unittest discover -s code -p 'test_*.py' -v
PYTHONPATH=code python demos/v45_multiturn_demo.py
```

OpenCV4は**開発テスト専用**。本大会の必須要件にはならない。

## コンテナでの研究API起動（未ビルド・未デプロイ）

`deploy/Dockerfile`はOpenCV5の配布版を要求し、未導入ならビルド失敗とする。

```bash
docker build --no-cache -f deploy/Dockerfile -t bzx-v45-research .
docker run --rm -p 127.0.0.1:8080:8080 \
  -e BZX_RESEARCH_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(24))')" \
  bzx-v45-research
```

トークンを別に保存しなければクライアントから使えない。デプロイ前に機密管理・TLS・VPCを整えること。

## APIの注意

`/api/research/loop/start`と`/api/research/loop/reobserve`は**クライアントからの有限仮説モデルと人手観測**で動作する。現時点では**画像を2回OpenCV5で計測したAgentic Vision E2Eの証拠ではない**。研究用APIは単一トークン運用で、公開・複数ユーザー運用は禁止。

## 第三者再現

- `reports/v45_unittest_verbose.log`：再実行した各テストと合否
- `reports/v45_adversarial_findings.json`：v4.4の3つの欠陥が再現されなくなったこと
- `v4.5_テスト台帳_491件.csv`：ローカルPASSと物理/AWS未実施を区別
- `v4.5_要求試験対応_650件.csv`：要求の多対多対応
- `SHA256SUMS_v45.txt`：配布ZIPに含むファイルのハッシュ

このZIPは**実施可能な研究用プロトタイプと開発・評価資料**であり、95点以上の達成証明ではない。
