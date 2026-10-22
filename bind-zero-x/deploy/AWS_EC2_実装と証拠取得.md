# OpenCV 5 + AWS EC2 実装・証拠取得ランブック（未実行）

対象: 2026-10-12時点。実際のAWSへデプロイしていない。正式の応募要件は OpenCV5の実質的画像処理＋AWS上で意味ある処理。

## 1. 最小構成
- EC2 (保護されたinstance profile)、暗号化済みプライベートS3、期限付きオブジェクトのみ。公開HTTPでこの研究用CLIを直接実行しない。
- 開発用に固定の2フレーム＋専門家が作成した上下層ROIマスク＋独立したキャリブレーションをS3から取得。
- Dockerで OpenCV5.0.0.93 headless のビルドとテストを検証。`docker build -f deploy/Dockerfile -t bzx:v4.2 .`
- `docker run --rm bzx:v4.2` で本コンテナの回帰を実行。成功してもAWS稼働は別の証跡が必要。
- バケットへのGETのみを許すEC2 IAMロール、署名済みアップロードURL、削除手段。標準出力へ生画像・GPS・認証情報を記録しない。

## 2. 観測対象が実物の場合の最低条件
- 二時点の同視野グレースケール画像、および識別が追跡できる各層のROIマスク、背景マーカーでのカメラ運動補正。
- 別計測で得たmm/px、観測平面、キャリブレーション証明、独立GT。厚み差や視点差で単一スケールが成立しない場合は計測拒否。
- `code/research_pipeline.py` のCLIは maskが**外部から与えられる研究用**。層自動認識/本番機能の証拠と誤認しない。
- 結び目・ひもは未計測(NULL)。その他が正常に見えても「安全」や強度保証を表示しない。

## 3. AWSでの実行ログ（必ず実際に取得）
- EC2 instance idの末尾など匿名化したID、AWSリージョン、OpenCV `cv2.__version__`（先頭major=5）、Docker digest、実行時Git SHA。
- 同じS3動画を取得した記録（キーの生文字列は秘匿）、アップロード検証、CV workerのrequest_id、測定出力の検算値・品質フラグ。
- DynamoDBで`ConditionExpression`とトランザクションによるowner・version・冪等性・承認と実行完了の分離を実装すること（SQLiteはその代替でない）。
- Bedrockを使う場合は、allowlist内の提案だけを検証、fallbackなしで危険操作が進まないことを故障注入で示す。Bedrock単独で物理値を推測させない。
- S3の削除、CloudWatchのログ秘匿、IAM境界、異なるownerのIDORテストはAWSで試験。

## 4. Go/No-Go
- G2-PASS: OpenCV5を実際のEC2上で実行、任意の研究用画像を取り込み、CV出力とログを保存した。
- G3-PASS: 実HTTP認証/JWT、S3/DynamoDB永続性、人間による承認後の状態遷移・結果再計測がE2Eで動く。
- 上記を満たす証拠がない場合は `NOT_RUN_AWS` とし、大会必須要件クリアを宣言しない。

## 5. 最終提出期限
Devpost Rulesのヘッダーは2026-10-26 23:45 PDT（JST 10/27 15:45）。Overviewの23:59 Pacific表記との不一致があるため、内部期限を10/26 23:00 JSTに設定。

