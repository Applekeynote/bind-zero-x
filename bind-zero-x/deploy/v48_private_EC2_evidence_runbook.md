# v4.8 OpenCV 5 / AWS 実働ゲート（未実施）

**本資料は手順であり、EC2・OpenCV 5・S3・DynamoDBの実行証拠ではない。**

## 1. 最優先のビルドと証明

1. 自分のAWSアカウント内のEC2にSSHまたはSSMでアクセス。Security Groupでは研究ポート8080を公開しない。
2. `docker build --pull --no-cache -f deploy/Dockerfile -t bind-zero-x:v4.8 .`。依存するOpenCV 5.0.0.93ホイールの公開・互換性は環境依存なので失敗もログへ残す。
3. `docker image inspect bind-zero-x:v4.8 --format '{{.Id}}'`、および `docker run --rm --entrypoint python bind-zero-x:v4.8 -c 'import cv2; print(cv2.__version__);print(cv2.getBuildInformation())'` を保存する。
4. 研究用トークンとMAC鍵は別々の強い秘密値。トークンを動画やログに記録しない。最小IAM/HTTPS/プライベート接続を別途設定する。
5. `BZX_CAPTURE_ARCHIVE_DIR` は永続化された暗号化EBS上のディレクトリを指すこと。`/tmp`だけでは再起動で画像証拠を失う。サーバの実効UIDが書けるよう権限設定し、マウントを確認する。S3への真正なアップロードは**未実装**。
6. `POST /api/research/loop/start-captured` に実画像PNG4枚と専門家が帰属確認したROI、校正、研究モデルを投入し、返されたreceiptから画像4件のハッシュが保存されていることを独立照合する。
7. セッションの続きは再撮影を実行し、`/api/research/loop/reobserve-image` で画像の違いが実際の行動候補/視点に影響するかを記録する。ただし独立GT承認なしは保留が正しい。許可フラグのモック結果は正式エビデンスにしない。
8. S3、DynamoDB、IAM、アクセス監査、ユーザー認証/セッション分離、UI、本物のV5での負荷とセキュリティ試験は追加実装と証拠が必要。

## 2. 保存が必要な生証拠

- `cv2.__version__` と `cv2.getBuildInformation()`、コンテナimage ID、EC2 instance metadataの機密情報を除いた環境バージョン。
- 入力原画像の内容SHA256、初回capture manifest SHA256、観測ID、ROI manifest、校正マニフェスト、セッションの判断前後。
- GTの独立測定者、測定器校正、原動画、物理束ID、事前登録の承認文書。
- 比較各群の元枚数と完了枚数、途中中止の理由、誤介入、再撮影数、全作業時間。失敗例も保存。

## 3. 合格定義

OpenCV 5の実稼働とAWSが実際に動いているログ、実画像由来の判断差、独立GT、E2-D1/E1/B実物比較、秘密値を含まない再現手順がそろうまで **G1〜G5はNOT_RUN**。
