# 実物画像・独立GTの取得と保守

利用者から受領した段ボールの静止画5枚は、app/static/photos/にデモ専用として保存しています。時系列の対画像、ROIマスク、校正、独立実測CSVはまだ揃っていません。デモ画像から独立測定者の記録やGTを生成していません。

保存先はプロジェクト直下の`data/physical/`です。Gitおよびソース配布から除外します。

| フォルダ | 内容 |
| --- | --- |
| `raw/BUNDLE-ID/` | 撮影した原動画・PNG。編集せず保持 |
| `calibration/` | 測定器・カメラ校正記録と`calibration.json` |
| `holdout/independent_measurements.csv` | 独立測定者の実測値、CV値、動画SHA256、束ID |
| `training/bundle_ids.txt` | 学習・調整に使用した束ID。holdoutとの重複を禁止 |
| `preregistration/` | 取得前の事前登録。DRAFTと凍結済みFROZENを区別 |
| `reviews/` | 別担当者の校正・原本・盲検・手順の承認記録 |
| `derived/` | 再実行可能な監査・集計・未承認エンベロープ |

1. 撮影前に独立測定者と評価方法・閾値・除外基準を合意し、事前登録を凍結します。後から撮影前の日付を作りません。
2. カメラを固定し、同一寸法の`t0`と`t1`、専門家が指定する上層・下層ROIマスクを取得します。画像だけからmm尺度を推測せず、実際の平面校正を記録します。
3. 最低30個の物理的に異なる束を評価し、30本以上の異なる原動画を保存します。故障モードは2種類以上、各5件以上を必要とします。同じ束の再撮影を独立標本に数えません。
4. 測定担当者がCVの出力を見ずに測定し、`gt_mm`を記録します。CV担当者の自己申告を独立GTとしません。
5. `video_file`は`raw/`からの相対パス、`video_sha256`は実際の原動画バイトのSHA256です。CSVには実際の観測だけを記録します。
6. データが揃ったら次の監査を実行します。寸法は取得した画像に合わせます。

```powershell
.\.venv5\Scripts\python.exe scripts\validate_physical_gt.py --height 1080 --width 1920
```

不足は`BLOCKED_PHYSICAL_DATA_REQUIRED`、原本や事前登録の不整合は`REJECTED_INPUT`になります。成功しても`approved=false`のDRAFTしか生成しません。独立監査の承認票とそのハッシュを取得した後に、サーバー側のallowlistへ承認済みファイルのSHA256を登録する必要があります。

画像解析の再現は、1つの取得フォルダに`frame0.png`、`frame1.png`、`upper_mask.png`、`lower_mask.png`、`config.json`を置き、次を実行します。

```powershell
.\.venv5\Scripts\python.exe scripts\verify_opencv5.py --capture-directory data\physical\raw\BUNDLE-ID --output data\physical\derived\BUNDLE-ID
```

この操作は受領バイト・計測・保存の検査であり、撮影内容の真正性や独立GTの承認ではありません。上層の画像運動が計測できても、ひも・結び目の状態は別の観測が必要です。
