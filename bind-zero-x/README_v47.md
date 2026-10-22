# BIND ZERO-X v4.7｜監査修正済み研究プロトタイプ

## 最重要

本フォルダの正式最新版は `BIND_ZERO_X_v4.7_正式改訂仕様_95点超の実証ゲート.md`。旧版の資料は履歴として残した。現状は**研究用・未実物検証・安全認定なし**。実環境でのOpenCV 5/AWS稼働の証拠は含まれない。

## ローカル再現

```bash
cd code
python -m unittest discover -v -p 'test_*.py'
```

ローカルCV4.13での試験およびモックが混じる。OpenCV5の本物の実行とは区別する。

```bash
python comparisons/finite_model_ablation.py
# 純粋に人工的な仮説モデル。実物試験や独創性の効果の証明ではない。
```

### 画像研究API

`deploy/Dockerfile` はOpenCV 5.0.0.93を指定する。EC2でのビルドは実際に利用者側で行う必要がある。APIはワークフローの**観測・判断保留**を扱う研究用で、遠隔操作権限なし。

研究用APIの視覚から仮説を縮約するゲートは既定で**閉じている**。独立GTの元動画・読取者・事前登録・校正IDと閾値の整合性を別途監査し、`BZX_APPROVED_GT_ENVELOPE_PATH` と `BZX_APPROVED_GT_ENVELOPE_SHA256` にサーバが審査済み記録を設定するまで、数値が変わってもPCIGの世界を確定しない。

### GT記録のDRAFT作成

空の `experiments/holdout_gt_record_template.csv`を実物の正しい記録で埋め、下記を実行：

```bash
python experiments/prepare_gt_envelope.py \
  --calibration /path/to/calibration.json \
  --holdout-csv /path/to/independent_gt.csv \
  --threshold-mm 5 --max-p95-mm 0.5 \
  --height 1080 --width 1920 --output /path/to/gt_DRAFT.json
```

このDRAFTは `approved=false`、`independent_real_gt=false`、`pre_registered=false`。実物検証なしにこれらを真にして稼働させてはいけない。下記の比較実験スクリプトもCSVが空ならエラーにする。

```bash
python experiments/analyze_physical_comparison.py \
  /path/to/filled_trials.csv --output /path/to/effect_summary.json
```

## 主な変更

- `measurement_contract.py`: 真偽値型・奥行き範囲の検証。
- `vision_motion_core.py`: 実ROIの凸包頂点上で最大移動量算出。
- `active_evidence_loop.py`: 親子観測IDを履歴とMACに結合。
- `api_research.py`: セッション版・観測親ID・視点・校正入力を画像デコード前に照合。
- `witness_planner.py`と`independent_witness_checker.py`: 絶対損失を考慮した非接触視点の選択。
- `cv_evidence_gate.py`: サーバ事前登録GTエンベロープに基づく研究用の視覚観測トークン化。偽データのテストはGTの現実性を示さない。
- `experiments/`: 独立GTと対照実験のテンプレート、DRAFT作成と厳格入力チェック。
- `test_v47_regressions.py`, `test_v47_experiment_tools.py`: 新規異常系。

## 注意

テスト名に `_mock_` が含まれる画像解析は、**OpenCV4を用い、cv2バージョン表示のみOpenCV5に差し替えたソフトウェア結合試験**である。AWS/実物/OpenCV5の達成を報告してはならない。正式採点の予測も含まない。
