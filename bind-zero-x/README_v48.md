# BIND ZERO-X v4.8｜Evidence Integrity & Completion-Safe Evaluation

**現在の正式最新版：** `BIND_ZERO_X_v4.8_正式改訂仕様_証拠真正性と完了安全評価.md`。以前のv4.2〜v4.7文書は履歴。95点超は目標であって達成済みではない。

## v4.8で動作する機能

- 完了試行のみの条件付き時間差、元枚数の完了率、中止率、間違った介入率、完了かつ誤介入なしの複合指標を同時出力。未完了であるほど速く見える指標の使用を禁止。
- 初回画像をサーバへ送信する`POST /api/research/loop/start-captured`と、4 PNGの原本・ROI/校正記録・内容ハッシュを結ぶ不変アーカイブ参照実装。既存の`/loop/start`は**未確認クライアントハッシュ**として出力で区別。
- GTエンベロープV2：30行ではなく30個以上のユニーク束ID/動画ハッシュと故障モード別内訳が必要。**V1承認は受理しない**。外部承認レシートのハッシュが必要で、サーバ側 allowlist SHA256 を別途設定する。
- 動画原本バイト・事前登録・学習束との非重複のオフライン監査。物理的真正性そのものや盲検性の独立監査は人間の責務。
- 追加36件のローカル異常系、研究用OpenCV4と模擬バージョン使用。本物のOpenCV5・AWS・物理試験ではない。

## ローカル再現

```bash
python -m unittest discover -s code -p 'test_*.py' -q
python -m unittest discover -s code -p 'test_v48_release_gates.py' -v
python comparisons/finite_model_ablation.py
```

## 物理試験CSVの分析（データなしでは実行しない）

```bash
python experiments/analyze_physical_comparison.py \
  /path/to/trials.csv --output /path/to/summary.json
```

`group_summaries`には完了率、中止率、完了枚数、全試行時間（速度比較不可）を出す。`comparisons`はペア一致条件で比較し、**両群の完了したペアだけ**時間の記述的比較を示す。完了条件で絞った時間は選択バイアスがあり、無条件の時間短縮には使えない。正式な主要項目は外部で事前登録を凍結する。

## GT原本監査とDRAFT

```bash
python experiments/audit_gt_source_media.py \
  --holdout-csv /path/to/holdout.csv \
  --media-root /path/to/videos \
  --preregistration /path/to/FROZEN_prereg.json \
  --training-bundles /path/to/training_bundle_ids.txt \
  --output /path/to/media_audit.json

python experiments/prepare_gt_envelope.py \
  --calibration /path/to/calibration.json \
  --holdout-csv /path/to/holdout.csv \
  --threshold-mm 5 --max-p95-mm 0.5 \
  --height 1080 --width 1920 --output /path/to/GT_DRAFT.json
```

動画には`video_file`列とコンテンツSHA256が必要。トレーニング集合との重複と、束単位の分離を確認する。原本監査は**GTを自動承認しない**。別担当者による装置校正、物理測定、盲検、事前登録の検証が必要。

## サーバ受領済みの初回画像

`BZX_RESEARCH_TOKEN`（長さ32以上）、`BZX_RESEARCH_INTEGRITY_KEY`（別鍵）、`BZX_RESEARCH_LOOP_DB`、`BZX_CAPTURE_ARCHIVE_DIR`をサーバが設定する。アーカイブは永続化された暗号化ストレージへ配置すること。ローカルのSQLite・ファイルはAWSのS3/DynamoDBに相当しない。

`/api/research/loop/start-captured`に、初回・次フレーム・上下層ROIのPNG、ROI帰属確認、校正パラメータ、仮説モデルを送信する。真のOpenCV5を必須とし、サーバで解析した後、4つの元PNGを内容アドレスで書き込み、原本の受領レシートをセッションに拘束する。**クライアント撮影日時や被写体の真正性の証明ではない。**

CLIデモ：

```bash
python demos/v48_captured_session_client.py \
  --config /path/to/model_and_roi.json \
  --frame0 /path/to/t0.png --frame1 /path/to/t1.png \
  --upper-mask /path/to/upper.png --lower-mask /path/to/lower.png \
  --output /path/to/session_receipt.json
```

## 未実装・未実証

- 実EC2/OpenCV 5での稼働、S3オブジェクト固定保存、DynamoDB CAS、人間承認Web UI。
- 実段ボールの元動画/GT、ケーブル/結び目の自動知覚、代表サンプルの独立試験、熟練者比較。
- 人工比較結果はあくまでモデル演習であり、競技スコア・優勝確率を示さない。

**未実施をPASSに繰り上げない。** 詳しくは正式仕様、`v4.8_提出ゲート_厳格再優先.csv`、`deploy/v48_private_EC2_evidence_runbook.md`を参照。

## 中止1秒の反例（合成・説明専用）

`demos/v48_SYNTHETIC_incomplete_vs_complete.csv`はE2が未完了0/10枚・1秒で中止する完全人工データ。`demos/v48_SYNTHETIC_incomplete_vs_complete_result.json`ではE2完了率が低く、速度の優越性を示すペア時間は`null`となる。実物試験には算入しない。
