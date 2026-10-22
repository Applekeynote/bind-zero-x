# BIND ZERO-X v4.9 / 95点超を目指す保守運用強化版

現段階は **研究用ソースコード・ローカル検証版**。OpenCV 5、AWS、独立GT、実物比較の完成実証を示す成果物ではない。

主要変更: `capture_lifecycle.py`で初回セッション予約と画像保存のユースケースを分離。`research_loop_store.py`でサーバ受領PNGの存続とSHA256を読み込み/更新前に再検証。`capture_archive.audit_archive`と`operations_audit.py`で孤立候補・欠損を読み取り専用監査。物理試験には`E2-ablated`群と証拠欠落件数を追加。運用/SLO/障害復旧/セキュリティ/モジュール分割の設計は`operations/保守運用・ソース構成_設計書_v49.md`を参照。

## テスト

```bash
PYTHONPATH=code python -m unittest discover -s code -p 'test_*.py' -q
```

## 運用監査（研究環境、読取専用）

```bash
PYTHONPATH=code python code/operations_audit.py --db ./research.db --archive ./captures --output ./audit.json
```

## 既知の重大な未達

初回CVからPCIGの故障世界へ、独立GTを介した観測反映が未完成。OpenCV 5の実環境、AWS稼働、独立GT、実物の人間比較、S3/DynamoDB永続化、監視ダッシュボードも未実施。AWS向けの運用設計は提案でありデプロイ実績ではない。
