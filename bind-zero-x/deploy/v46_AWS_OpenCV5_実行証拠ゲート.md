# BIND ZERO-X v4.6 AWS/OpenCV5 実機検証ランブック（未実施）

## セキュリティ・責任範囲

研究用APIは単一のBearerトークンのみで認証するため、**公開ネットワークに直接配置しない**。EC2のプライベートIP、VPN/SSHトンネル、厳格なSecurity Group、TLS終端、IAM最小権限を必須とする。Docker `USER 65534:65534` で動かし、書込み可能な作業領域/秘密の外部鍵と接続。`BZX_RESEARCH_INTEGRITY_KEY` はSecureString/Secrets Manager等で別管理しログに出さない。複数ユーザー対応、IDP認証、完全なDynamoDBデータ整合性は**未実装**。

## 必須G1：OpenCV 5コンテナを実機起動

`deploy/Dockerfile`は `opencv-python-headless==5.0.0.93` のインストールと`cv2.__version__`のメジャー5をビルド時に検証する想定。**Dockerビルド自体は今回実行していない。**

```bash
docker build --pull --no-cache --progress plain \
  -f deploy/Dockerfile -t bzx-v46-vision . 2>&1 | tee evidence/build.log
docker image inspect bzx-v46-vision --format '{{.Id}}' | tee evidence/image_digest.txt
docker run --rm --entrypoint python bzx-v46-vision -c \
  "import cv2,platform; print(cv2.__version__,cv2.getBuildInformation()[:800],platform.platform())" \
  | tee evidence/opencv5_build.txt
```

成功時だけ`OPENCV5_VERIFIED_RUNTIME`として記録。ネットワークや配布環境の制約で失敗した場合は、v4模擬検証と区別する。

## 必須G2：AWS EC2上のログ

- EC2インスタンスID/リージョン/CPUアーキテクチャ/AMI、Dockerイメージdigest、起動時刻、プログラムcommitをメタデータへ。
- 少なくとも1つの実動画ペアをOpenCV 5で処理したAPIレスポンス、校正ID、ROIマスクと実画像の内容ハッシュ、失敗/棄却理由を収集。
- `POST /api/research/loop/reobserve-image`で再観測し、`before_certificate_hash`・`after_certificate_hash`・状態versionを保存。未校正の場合は**世界集合を縮小せず、ABSTAINの理由を明記**。
- 「OpenCV 5出力が後続行動を変えた」証拠には、**実物の校正済みCVとモデル選択の関係を検証**して別途トレース取得が必要。現コードの未校正ストップだけでAgentic Visionの効果を達成したと主張しない。

## 必須G3：実AWSデータストア（未実装）

- S3: SSE-KMS、オブジェクトバージョニング、ハッシュ・期限とアクセスログ、匿名画像が混ざらない設定。
- DynamoDB: `session_id` + `version` 条件付き書込、観測と証明の原子的永続化、token owner属性とIAM境界、同じkey+同じ本文の冪等リプレイ、相違内容の拒否。
- Secrets Manager: MAC鍵、API認証秘密の保管とローテーション。コンテナ/リポジトリに直書きしない。
- CloudWatch: 未認証、再送、校正欠落、ROI証跡不正、異常例外、処理時間と費用のログ/アラート。
- Bedrockは実際に使用しない限り「Bedrock搭載」と記述しない。LLMの自然言語説明には工学的な安全承認権限を与えない。

## 必須G4：テスト行と提出証拠を連結

`v4.6_テスト台帳_550件.csv` の `V46-AWS-001/002`、`V46-AGENT-001/002` を実施前に`NOT_RUN`のままにし、実際のプロバイダログ・生画像ハッシュ・実行者・再現コマンドを取得してからPASSに変更すること。

大会公式： https://opencv26.devpost.com/rules と https://opencv26.devpost.com/ 。締切表示に11:45pm PDTと11:59pm PDTの不一致があるため、11:45pm PDTを安全側の予定とする。
