# BIND ZERO-X v4.3 | BIND-WITNESS
## 95点超を目指す、実装・観測証明・先行技術・実物評価の改訂仕様

- 日付：2026-10-12（JST）
- 状態：**実装済みのローカルコード検証**と**未実証の物理・クラウド成果**を分離した研究プロトタイプ
- 優先順位：この文書の仕様 > 同梱 v4.2設計書の同じ対象に関する古い記述。v4.2原文は HISTORY/REFERENCE であり、競技提出時の実装事実ではない。
- 本書の目標：OpenCV 5 + AWS 必須要件の実動、独創的な最小証拠意思決定、人間との公平な性能比較を揃える。**「95点獲得済」「他に競合がない」「安全保証」は主張不可。**

---

## A. 独創性の核：BIND-WITNESS / Evidence Before Intervention

**問い：** 段ボール束の見た目が同じでも、(a)層だけが滑る、(b)ひも経路だけがずれる、(c)結び目端が滑る、(d)複合故障という複数の機構があり得る。対策が「層を揃える」「ひも位置を直す」「結び直す」「二束へ分割」で異なる場合、最短のカメラ追加観察は何か。追加画像を撮る価値がなければ、何もしない根拠を示せるか。

提案する3層の仕組み：

1. **Failure Interaction Graph（FIG）**: 段ボール層間の接触辺、ひも経路の固定点、結び目端部をタイプ付き観測ノードとして管理する。各値に `observed / unknown / uncertain` と「画角・スケール・材料点ID」を付ける。物体剛体運動と層間の真の動きをSE(2)で区別する。
2. **Contradiction Witness Certificate（CWC）**: 現在の証拠に矛盾しない２つの世界が異なる適切な修正行動を要求するなら、その２世界を反例として記録する。モデル内部で全世界の許容行動が同じ場合は観測を増やさない。数値が空欄でも安全認証を捏造しない。
3. **Zero-Added-Force View Selection（ZAF-VS）**: まず非接触の上面・側面・ひも経路・結び目接写だけを候補にし、視点の変更が最大後悔量を減らす場合にのみ要求する。振動・引張・傾斜は材料状態を変化させるので、**別の研究治具モードでのみ人間承認後**。追加荷重ゼロの視点選択と、状態を変える物理診断を同じスコアに混ぜない。

### 評価可能な方法上の差別化

- 既存の画像検査：異常ラベルを返す。 → **本方式**：異常ラベルに加え、未観測故障との**行動衝突の証人**を返す。
- 固定追加撮影：常に側面（または上面）。 → **本方式**：`side` / `rope path` / `knot closeup` / `no view` を観測内容と仮定モデルで切り替える。
- 失敗検出に偏った手法：診断accuracyで評価。 → **本方式**：実際の修正後の残留変位、誤修正率、ユーザー作業時間、追加観測コストを評価する。
- 不確かでも対策を出す手法：単一最良候補。 → **本方式**：反例が消えず、追加観測の価値もない場合はABSTAIN。

**厳密な注意：** 能動知覚、ミニマックス後悔、説明可能な反例提示は一般概念として既知であり、この組み合わせだけで研究史上初とは断定できない。新規性を訴える対象は、**多層紙・ひも・結び目の異種故障グラフにおける「意思決定を変える観測の証明」を、非破壊な人間作業支援として実装・比較する固有の統合**である。既存の結束紐検査特許（JP3325709B2等）が存在するため、FTOや独占可能性についても主張しない。

### ミニマックス・後悔量（BIND-WITNESS）

世界集合 `W`、許された修正候補 `U`、仮説ごとの損失 `L(u,w)` について：

`Regret(u,w) = L(u,w) - min_v L(v,w)`

`R0 = min_u max_(w in W) Regret(u,w)`

追加非接触視点 `v` が生じる観測区分 `partition_v(W)` に対し、

`Rv = C(v) + max_(S in partition_v(W)) min_u max_(w in S) Regret(u,w)`

`Rv < R0` が確認された場合のみ非接触視点を要求。満たさなければ、後悔量が事前許容値以下の行動のみ提示し、その他はABSTAIN。`W`・`L`・観測シグネチャは現在**人工の離散例であり、実物から推定済みではない**。確率やCIを宣言せず、あくまでも有限モデル内部の保証としてログへ残す。

必要なログ：`case_id, observation_id, layer_pose, layer_max_mm, theta_deg, quality_reason, hypothesis_worlds, counterexample_pair, candidate_views, view_cost, measured_decision, certificate_sha256, approval_event_id, physical_outcome_id`。

### 具体的な違いが見えるデモ

- 同じ画像取得フローで「上層が9px動いた」ケースと「束全体の回転のみ」のケースを撮る。
- 前者は層間観測の異常と未観測のrope状態を保持し `ROPE_PATH`視点を候補にする。後者は層が動かないため仮説集合が変わり、別の視点または保留を選択する（研究用の人工モデルで実行済み、**実物では未実証**）。
- 「2つの説明が同じ画像に整合するが、対策が異なる」を**二枚の対照図**で示し、BIND-WITNESSが次の観測をどちらへ向けるかを理由と共に表示する。
- `CWC hash` を次の観測、承認、再計測結果に連結する。証拠がない推測やLLMの創作を測定値として扱わない。

---

## B. コードの修正（監査指摘との1対1対応）

| 前回の不具合 | v4.3の具体的修正 | 再現テスト |
|---|---|---|
| 上下層へ同一ROIを渡すと9px滑りを0とする | `validate_distinct_layer_rois`、マスク同一/過大重なり/画像形式拒否 | ROI_001, ROI_002, ROI_003, ROI_004, ROI_005 |
| 正しい層IDか確認できない | `verify_roi_provenance` が入力画像ハッシュ、ROIマスクハッシュ、２層の異なるsource ID、オペレーター確認を結合 | ROI_012〜016, SAFE_001〜003 |
| 8度の相対回転を無視 | ROIの実占有領域の角4点と中心で最大変位を計測し、`layer_max_drift_mm`＋`relative_angle_deg`をプランナに渡す | ROI_007/009/010, D_006〜010 |
| 不明のひも状態で層試験を要求 | ひも未観測→`RECAPTURE`、再撮影終了後`ABSTAIN`、層/結び目未観測とは別処理 | D_001〜005 |
| NaN/負の不確実性で確定判断 | Pixel/Calib/mm dataclass生成時にfinite・非負・ID検査。中心と最大変位の誤差境界のいずれかが閾値を跨ぐと保留 | M_001〜010 |
| 過大な物理試験許容差・無効な時刻 | タイムゾーン付きUTC必須、相対許容差の**開発用上限25%**、ゼロ変化率/ゼロ振幅の拒否 | P_001〜007 |
| 推奨行動しか返さず根拠が不明 | BIND-WITNESSの反例世界/追加視点/証拠ハッシュ | WIT_001〜014, BRIDGE_001〜005 |
| 計測値が正しくてもROIの帰属不明のまま勧める | 帰属が未確認なら物理修正は**ABSTAIN**、ルール評価候補のみ `research_candidate_only` | SAFE_001〜003 |

**残余リスク：** 入力マスクが異なることとハッシュが一致することは、それらが実際に別々の段ボール層を指す**物理的な正解証明ではない**。一貫した誤ラベルや悪意ある入力を完全に検出できない。研究用のオペレーターが各ROIと層IDを視覚確認し、別のカメラと校正治具を独立GTとして利用する必要がある。

`estimateAffinePartial2D` は相似変換を返すため、スケール逸脱・インライア不足・大きな再投影残差は拒否する。評価される幅のある段ボールに対し、単一ホモグラフィや単一 `mm/px` スケールを無条件に適用しない。

**最大変位の注意：** 現行の5点は可視ROIの占有領域を近似する評価点であり、実際の接触界面上の相対滑りを直接測った値ではない。`max_footprint_drift_mm` は "可視ROI内の相対剛体運動による最大推定変位" であって、摩擦強度や抜け落ち保証値ではない。真の接触領域を標識したGTを別途必要とする。

## C. ローカルソフトウェアが到達した範囲

- `code/vision_motion_core.py`: OpenCV由来のLK光学フロー、RANSAC、SE(2)、ROI分離、可視占有領域での相対変位。
- `code/measurement_contract.py`: 単位・校正ID・平面・有限な不確実性の契約。
- `code/cape_rule_core.py`: 3故障モードの分離、回転と最大変位、許可された行動、承認境界、診断回数上限。
- `code/witness_planner.py`: 反例付きミニマックス後悔量と非接触追加撮影の選択（人工モデル）。
- `code/decision_bridge.py`: 実画像計測の出力差によって人工WITNESS例の候補視点が異なることを確認する研究用接続。**このビュー選択はローカルの仮定モデルであり、現実の対策を自動承認しない。**
- `code/research_pipeline.py`: 2フレーム、専門家ROI、校正値からmm値と推奨候補へ接続、OpenCV5 version guard。
- `code/session_repository.py`: SQLiteの参照実装。DynamoDB/APIのアクセス制御・障害復旧についての証拠にはならない。

**存在しない成果**：ローカルのOpenCV5実行、画像からの自動層セグメンテーション、AWS Webサービス、Bedrock連携、DynamoDB競合検査、実物での因果推論、強度保証、人間比較での有意な成果。

## D. 95点超のための実証トラックと判定

### D0：大会資格（非交渉）

1. EC2等AWS上にPython OpenCV 5.0.0.93を搭載したコンテナを立て、`cv2.__version__` とDockerイメージdigestを記録する。OpenCV 5による実動画解析の request_id と解析結果を保存。**Dockerfileがあるだけでは合格しない。**
2. ユーザー認証、所有者照合、承認、結果再計測、DynamoDB条件付き更新、S3のprivate assetを最低限のE2Eで接続。可能ならBedrockに計測済みのJSONだけを渡し、検証済みallowlist以外は不採用。
3. Webで「何が見え、何が見えないか」を表示。人間の確認なしで物理行動を自動化しない。

### D1：測定精度（現物GT）

- 少なくとも3種類の実段ボール構成、校正済み長さ基準による既知0/2/5/10mm相対移動、共通回転とカメラ移動、照明と視点を変える。
- 主要：`MAE_mm`, `P95_absolute_error_mm`, `false_clear_rate`, `rejection_rate`, `layer_id_swap_rate`。`UNKNOWN`をゼロとして足さず、Coverageを併記。
- 当初の挑戦目標：MAE≤1mm、P95≤2mm。実測結果を見て都合良く変更しない。目標未達の場合対象・解像度・校正へ戻る。

### D2：独創性主張の確証実験（M-TRACK）

**Primary contrast**：新方式 E-WITNESS vs 同じ撮影・時間制約下の固定追加観測 D-FIXED。両群で撮影回数・累積非接触時間の同じ上限を設定。

- 単位：独立 `configuration_id`（素材組合せと難条件を事前固定）。同じ束の反復を別の独立データとして数えない。
- 主要指標（前登録で**1個**選択）：`wrong_repair_rate`（独立GTに照らして不要または不適切な修正を選ぶ率）。不適切かどうかは「単一正解」ではなく、標準チャレンジ後の実測損失に基づく許容行動集合で判定。
- 副指標：`selective_coverage`, `false_clear_rate`, `average_extra_views`, `average_view_seconds`, `decision_regret`, `abstention_rate`, 統計的な区間。常時保留で誤修正率0に見せかけることを禁止。
- 独創性の仮説が支持される条件：比較可能なカバレッジで `wrong_repair_rate(E) < wrong_repair_rate(D)`、ユーザーに追加負担を押しつけず、事前定義した効果幅と不確実性を報告できること。サンプル不足なら「探索的」「不確定」。
- **必須アブレーション**：A1 単純OpenCV閾値、A2 常時側面、A3 常時結び目接写、A4 不確実性なし、A5 反例証明なし、A6 WITNESS full。LLMあり/なしも同じholdoutで別比較。

### D3：利用価値の実証（U-TRACK）

**Primary contrast**：E-WITNESS vs 熟練者B（自由な再配置・合法な結び方・分割可）。双方に同一個数・材料・環境・独立GT・Qを提供。

- Job単位は元の全段ボール枚数をすべて搬出すること。分割した束の最悪 `D_res`、ひもの `K_res`、合計の作業時間・往復・紐総長、完了率を別々に出す。
- 失敗・中止は除外せず、作業完了率と完了者のみの時間を明示的に区別。
- 利便性の主要仮説は**実用改善**（時短・失敗の減少・誤修正の減少のうち事前固定したもの）、単なる中間指標の改善ではない。
- 物理評価が安全・再現可能でない時は、無理に強いチャレンジを実施せず研究用途に縮小。

### D4：統計・信頼性

- パイロットとholdoutは configuration_id / material_set_id で完全分離。
- 主比較と除外基準、最低意味のある差、stopルール、観測不能処理、検定単位を物理試験より前に凍結。
- 可能なら独立構成≥12を探索上の希望値として設定するが、それだけで90%超の成功確率や一般化は言えない。GTを付けた者と評価者を分離。
- 3要件はA/B/C個別表示。いずれか未達なら「3要件すべて改善」と書かない。

## E. 評価証拠の採取（審査員向け）

必須1件分のトレース：

```
VIDEO_SHA256
  -> S3 key (private) -> EC2/OpenCV5 request id
  -> ROI label + background compensation + SE(2) matrix + units/quality
  -> FIG observation nodes + CWC conflicting world pair
  -> next view (NONCONTACT) or ABSTAIN, explanation, model version
  -> human approval event (DynamoDB condition version)
  -> next video SHA256 -> followup decision -> action confirmation
  -> common Q independent GT outcome -> E vs D/B report
```

`CWC hash` は内的整合の証跡であり、予測仮説の正しさを証明するハッシュではない。UIに生の隠れたGTを表示しない。Bedrockには候補の文面整形のみを許し、発明した測定値を行動理由に使わない。

## F. 実装優先順位（提出まで約14日）

1. **DAY 1-2**: OpenCV5実起動、今版のROI不正・角度・NaN回帰をAWSと同一DockerでPASS。最初の独立GT動画3本取得。
2. **DAY 3-5**: 研究ROIで連続フレーム解析、境界近くで不確実性を保留、写真の2視点撮影を実物で確認。物理試験は安全承認まで待つ。
3. **DAY 6-8**: 最小API＋EC2＋S3＋DynamoDB + 任意Bedrock、動画→判断証明→人間承認→再撮影を完走。
4. **DAY 9-11**: 固定追加視点DとBIND-WITNESS Eを同じ予算で盲検比較。B熟練者対照の小規模実験も別に実施。
5. **DAY 12-13**: 勝てなかった条件を含め効果表・CloudWatch・失敗例・5分以内のデモ。
6. **DAY 14**: 機能凍結・第三者再実行・提出。内部提出目標は2026-10-26 23:00 JST。公式締切表示の不一致があるため、締切直前提出は避ける。

**削除するより厳しいスコープ判断**：OpenCV5のAWS稼働・実物の独立GT・BIND-WITNESS E-vs-Dを残し、画像ベースの自動層分離、確率遷移学習、複数ひも材質、COOL、VR/AR、高品質の一般家庭向け商用UIは未検証なら明示して延期する。

## G. 先行研究と競合境界

- 2024 Weng et al., *Interactive Perception for Deformable Object Manipulation*（能動知覚と変形物操作は既に研究されている）: https://doi.org/10.1109/LRA.2024.3431943
- 2026 Caporali et al., *Robotic perception and manipulation of deformable linear objects: A survey*（ロープ・ケーブル視覚操作の豊富な既往研究）: https://doi.org/10.1177/02783649261432253
- JP3325709B2 *Method and apparatus for inspecting binding straps*（板紙・段ボールを含む結束紐の検査で直接隣接する先行事例）: https://patents.google.com/patent/JP3325709B2/en
- JP6895227B2, JP6038627B2, EP3501995B1, US9051071B2（v4.2参照資料に記載の結束補助/移動/産業視覚制御）
- OpenCV 5.0.0.93 wheel: https://pypi.org/project/opencv-python/5.0.0.93/
- 公式rules: https://opencv26.devpost.com/rules

上記は**機能重複リスクの探索例**であり、全特許の網羅・法的な自由実施・「競合ゼロ」の証明ではない。特許クレームと学術研究の本質的重複は別に比較表で監査する。

## H. 審査得点の現実性

「95点を超える」と書くために必要な独立審査相当の証拠例：技術29/30、独創性19/20、社会影響19/20、UX10/10、文書10/10、AWS10/10 =97点。**これは希望配点であり、現在の達成点ではない。** 単独開発・2週間でOpenCV5/AWS/実物データ/熟練者比較の全条件を完成させ、ほぼ満点を取るのは非常に難しい。評価の信頼性は、実測されていない比較結果を示唆しないことによって守る。

---

### v4.3成果のラベル体系（厳守）

`LOCAL_PURE_CODE_PASS`・`LOCAL_SYNTHETIC_OPENCV4_PASS`・`LOCAL_HYPOTHETICAL_DECISION_PASS`・`REAL_GT_NOT_RUN`・`AWS_OPENCV5_NOT_RUN`・`PHYSICAL_BENCHMARK_NOT_RUN`・`THIRD_PARTY_NOVELTY_NOT_PROVEN`。同じPASS表記で実物と合成を混ぜない。
