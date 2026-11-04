# Main/Live K-LC0 Unit1 closeout

> **현재 상태 안내 (2026-11-04):** 아래 LC0 단위의 29경로 commit/push 및 recovery 교체는 **4f34a9690fd913f8702404a3c1c6122c078bd4d0**에서 완료됐다. 이후 Main LC1과 표시 개선도 사용자 수용했으며 현재 계약/Git 절차는 [LC1 및 표시 개선 closeout](STAGE3_MAIN_LIVE_K_LC1_DISPLAY_CLOSEOUT.md)과 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md)를 따른다. 아래 wire v8·Main LC1 미지원·Git/NEXT 표기는 당시 snapshot이다. 원 검증 수치·실패·한계는 보존하며 이전 Git script를 다시 실행하지 않는다.

기준일: **2026-11-04 (Asia/Seoul)**. 상태: **구현·범위 한정 독립 검토·사용자 native 수용 완료 / 문서 마감·사용자 Git 준비**.

기준 commit은 `7f15355a1d17a3fab1b4b11d85897b02a6bda5d5`다. 이 문서는 그 위에 추가된 Main/Live LC0 연결을 기록한다. 이전 [K 인수·Simple 준비·Replay UI closeout](STAGE3_MAIN_LIVE_K_ADOPTION_UI_CLOSEOUT.md)과 [별도 LC0 정책 closeout](STAGE3_K_LC0_DISTANCE_BAND_V1_CLOSEOUT.md)은 당시의 계약·검증·수용 이력이다. 현재 복구는 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md)를 함께 읽는다.

## 1. 사용자 수용

사용자는 LC0 native 안내 뒤 주요 동작이 괜찮다고 확인하고, `(실험적)` 표기와 비활성 마우스 경로 옵션을 질문했다. 마우스 경로는 **기록을 켠 수동 판이 끝난 뒤에만 표시 가능하고, 실제 Auto 입력이 한 번이라도 있으면 그 판의 기록을 무효화**한다는 기존 동작을 설명했다. 정책 선택/분석/Auto ON만으로는 자동 입력이 되지 않는다. 이후 사용자는 **“내가 잘못 판단한것 같네, 다시 확인해보니 전부 정상같아.”**라고 확인했다.

이를 현재 사용자 환경의 LC0 native 안내 수용으로 기록한다. 구체적인 DPI 수치·모든 OS·각 preset 완주 횟수·모든 희귀 오류 경로까지 확인됐다고 추정하지 않는다. 수동 경로 질문은 새 결함 판정이나 제품 수정으로 이어지지 않았다. 기존 검토 파일의 PENDING은 작성 당시 상태로 보존한다.

K-P0와 K-LC0의 **(실험적)** 표시는 이번에 유지한다. LC1 연결·native 수용 이후 UI 정리에서 함께 검토할 수 있다. 이 라벨 자체가 Production 승인 gate는 아니며, 순수 문구 변경 때문에 전체 worker 검증을 자동 반복하지 않는다. 삭제하더라도 effectiveness나 Production K/Gate P 승인이 되는 것은 아니다.

## 2. Main 사용과 정책

- K-LC0 (실험적)을 선택해 초급·중급·상급의 새 게임 또는 현재 판을 진행한다. 기본 Stage2 Simple, K-P0와 V1의 기존 의미는 유지한다. Main LC1은 disabled이며 V1/K/LC0 custom은 미지원이다.
- LC0는 CANONICAL_NEW, FLAG-free ADOPT_CURRENT, 기존 FLAG를 확인·정리하는 FLAG_ADOPT, 정상 수동 인계 뒤 재인수를 지원한다. 기존 깃발을 사용자가 모두 해제할 필요는 없다. 미확인은 오답/안전 판정이 아니며 실제 지뢰의 깃발도 해제될 수 있다.
- Auto OFF는 같은 owner/pending을 보관하는 pause다. Simple/V1/K-P0/K-LC0 모두 수동 첫 press에서 Auto/guess를 끄고 원 gesture를 처리한다. 옛 owner 정리 뒤 명시 Auto ON으로 재인수한다.
- 확정색·이미 계산된 확률·가상 원형은 실제 LC0 첫 입력에 맞춘다. 표시용 추가 추론은 없고 확률 OFF에도 확정색은 남는다. 원형은 승인 대기 중 실제 입력보다 먼저 도착할 수 있다.
- 첫 실제 Auto 입력(준비 UNFLAG 포함)부터 Replay source_type은 algorithm이고, 이후 수동 전환으로 human으로 되돌리지 않는다. Replay JSON schema와 정책 이름 이력은 추가하지 않았다.

## 3. 선택·세션·입력 계약

Live ID `K_LC0`는 원 native wrapper의 `K-LC0` / `DISTANCE_BAND_V1`에 대응한다. **control=False**이며 native g/P0를 대신 실행하고 LC0라고 표시하지 않는다.

normal 결정마다 같은 KLocalSession에서 analyze_decision 1회, native select_policy 1회, 그 결과의 apply_distance_band 1회다. 원 survivors 중 정수식 `20*L(p)*R(g) <= 21*L(g)*R(p)`를 만족하는 후보에 **전체 exact_route 거리 D → 정확한 Fraction E → L → frozen final tie** 순위를 적용한다. 원 setup FLAG 순서·hypot/fsum·float 동률을 바꾸지 않는다. EXACT_GUESS의 위험/target/no-setup과 SETUP_OPEN 무결성 오류는 기존대로다.

worker가 원 DecisionAnalysis·native selection·DistanceSelection·selected selection을 보관한다. VALIDATE에서 원 객체/graph 결속, validate_distance_selection, 기존 K 물리 검증과 원 pending 비교를 함께 적용한다. 첫 입력만 실행하고 나머지 suffix는 실행하지 않는다.

```text
공개 현재 판/실제 이력 → 같은 owner의 K 분석1/native 선택1/LC0 적용1
→ 원 pending 보관 → VALIDATE → ADMITTED
→ GUI 최종 상태·이력·정책 확인 → token 소비 → 실제 입력1
→ 정확한 원 입력 ACK → 다음 공개 상태에서 새 결정
```

최종 비교→token→step 사이에는 yield가 없다. ACK 중 수동 입력은 원 receipt만 drain하고 새 수동 판을 덮어쓰거나 NEXT를 보내지 않는다. exit/reap/tree0/private cleanup이 끝나기 전에 새 owner를 시작하지 않는다. 실제 ACK/이력/정리 실패의 최초 원인 latch는 유지한다.

FLAG 준비는 변경하지 않은 KFlagPreparation과 fresh native session의 공개 masked local proof다. 준비 UNFLAG 후 같은 session의 실제 observation 검증으로 normal LC0에 들어간다. masked graph/요약을 normal 입력 승인에 쓰거나 M을 외부 주입·이전 owner에서 복원하지 않는다.

## 4. identity와 한도

| 항목 | 값 |
| --- | --- |
| Canonical 정의 | K_LC0_DISTANCE_BAND_FIRST_INPUT_V1 |
| FLAG-free ADOPT 정의 | K_LC0_PUBLIC_ADOPT_DISTANCE_BAND_FIRST_INPUT_V1 |
| FLAG_ADOPT 정의 | K_LC0_PUBLIC_FLAG_ADOPT_LOCAL_BOOTSTRAP_V1 |
| Normal phase | LC0는 K_LC0, P0는 K_P0 |
| 공유 준비 phase | K_BOOTSTRAP / K_PREPARATION |
| 공통 wire | v8, 구버전 거부 |

필수 game_id를 KSnapshot에 추가했다. policy/definition/entry/start revision/game/run/generation/token/nonce/M revision이 proposal→VALIDATE→permit→ACK→원장에 이어진다. normal480+준비480, pending VALIDATE64, V1seq1921/K31681/FLAG63362, 2MiB, compute/ACK/exit/drain30/5/5/0.75초는 유지한다. `MAX_INPUTS`는 준비 포함 480+480=960이며 normal 상한480과 다르다.

LivePolicyJob poll/_cleanup/shutdown/_request_stop 본문은 기준선과 같다. core, native Simple/K/LC0/LC1 정책·runner·capability, Model C/profile/table, containment, Simple 준비, K bootstrap은 변경하지 않았다. Main 기본 import에 native LC runtime을 올리지 않았다.

## 5. 구현과 독립 검토 근거

공통 root: `C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\MAIN_LIVE_K_LC0_UNIT1_2026-11-04`.

| 구분 | 최종 결과와 한계 |
| --- | --- |
| Codex focused | 536/788 + 보완19/6 = 555 고유 method / 794 subtest, 교집합0·동일 최종 bytes의 합성 |
| Claude focused | 555 method / 794 subtest 한 번 실행, 실패·오류·skip·child0 |
| Codex 실제 worker | 6사례 / 8owner / Popen8 / Auto10, 정리 확인 |
| Claude 실제 worker | 최초 환경 실패 시도1/Popen0 보존, 복구1회에서 6사례 / 8owner / Popen8 / Auto10, 누적시도9 |
| Claude 독립 probe | 49 check 중48 PASS, 1개는 검토자의 MAX_INPUTS 기대값 오류. 원 FAIL 보존, 재실행 없음 |

6개 실제 사례는 LC0/P0 차이, nonzero revision ADOPT, mixed FLAG 준비→normal, ACK 중 수동→새 owner, pause/guess, policy/late negative다. p01은 같은6×5 상태에서 실제 LC0 CHORD(0,3)와 P0/native g CHORD(4,1)을 실행한다. 일부 소형 Main은 preset gate만 seam으로 대체했다. 모든 preset 완주·native 창 검증·성능 pilot은 아니다. 각 실행의 24개 소유 PID 기록과 8owner의 reap/tree0/private 삭제/handle close가 있다. 정상 terminal exit0와 의도된 cancel exit1을 구분한다.

최종 source111 manifest SHA256:
`fd58110b2dba907560767ddab1d9e6d0899411cff534cb68a1ec0549df76b629`

Codex output manifest66 SHA256:
`184457358cc1ade4924f91d5a5011c4642cc916b5f1137cb8006fb982f628f27`

Claude output manifest33 SHA256:
`039da7c5221d34ad1005fd747667262d8e304f80b63b8d2620d7c110654bea47`

독립 보고서 SHA256:
`3568cee7b70a2898fc7d68ac55193dc6c985c45d7f98a56fe2d40359b4c15953`

위 수를 과거 버전의 345/479·443/731 등에 합산하거나 전체 suite PASS로 쓰지 않는다. 49개 probe 전체가 PASS했다고도 쓰지 않는다. 구현자의 모델·effort·속도는 미노출/미확인이다. Claude는 Opus5.5/effort max/Auto 관찰, Fast 미확인, Computer Use 미제공/미사용이다. 약46분/약28분은 실제 소요 기록이며 품질을 대신하는 지표가 아니다.

## 6. 실패·권고와 TEMP

Codex 초기 slotted instance patch 오류, wirev7 기대값 실패, 누락19개 보완과 fixture 탐색/편집 이력을 보존한다. 기존 mouse 검사2개는 HEAD에서도 실패한 옛 기대값이다. 첫press 뒤 guess/analysis 유지 기대와 현재 인계 계약의 차이를 독립 검토가 확인했고, 실제 Qt press/move/release로 현재 동작을 직접 검사했다. 이 테스트를 고치거나 baseline 전체 suite를 반복하지 않았다.

Claude 세션의 TMPDIR이 전역 TEMP를 가리켜 첫 process private 경로 검사가 Popen 전에 막혔다. 원 helper/원장/binding을 유지하고 TMPDIR만 고정한 wrapper와 이월 계수 driver로 복구했다. **최초 process 및 focused가 사용한 전역 TEMP 잔여물은 NOT_VERIFIED**다. 복구 campaign의 전용 tmp 정리와 구분하며 전역 TEMP 검색/삭제로 해결하지 않는다. 앞으로 재현 wrapper는 Python 시작 전에 TMP/TEMP/TMPDIR을 모두 전용 경로로 맞추고 실제 tempfile 경로를 확인한다. 이 교훈은 원 evidence의 수정이 아니다.

기존 mouse 기대2개 갱신, 개행 혼재, audit method byte 측정의 끝 개행 차이는 낮은 우선순위다. 별도 필수 제품 수정으로 승격하지 않는다. **과거 F02 NOT_VERIFIED, Qt shared FileDialog 보존 FAIL, 이전 중단 focused temp NOT_VERIFIED**와 모든 절차 정정도 유지한다.

## 7. 문서·Git·후속

문서 작성 기준: **main / HEAD = local origin/main = 7f15355a1d17a3fab1b4b11d85897b02a6bda5d5 / ahead·behind0·0 / staged0**. LC0 source/tests21(M18/U3) + 문서8(기존7·신규1) = **29경로(M25/U4)**의 미커밋 단위다. 외부 evidence/launcher/recovery는 commit 대상이 아니다.

조율 root: `MAIN_LIVE_K_LC0_DOC_CLOSEOUT_2026-11-04/coordinator_01`. source111·원 검토/구현 evidence·다른 문서·Desktop·index를 보존하고 문서8개만 갱신한다. 사용자용 단일 script로 정확한29경로 stage·commit·push와 receipt를 묶는다. 실제 실행 전 push 완료라고 쓰지 않으며 raw와 정규화 Git blob을 구분한다.

**NEXT: 사용자 일괄 Git → 실제 receipt/SHA 확인 → postcommit recovery 교체본 → 사용자 Desktop 교체 → LC1 Main/Live 연결 단위 준비.** 같은 단위의 postcommit 문구만을 위해 추가 문서 commit을 만들지 않는다. 이후 실제 SHA는 receipt/recovery/live Git을 따른다. LC0의 수용된 기능·마우스 경로 질문을 다시 미완료로 돌리지 않는다.

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE다. Phase2/R0-B/ActualE2는 미승인/미실행이며 frozen 정책·Model C·holdout2,010,000..2,010,099·공식/formal evidence 경계를 유지한다. 별도 LC1 저장 viewer와 아직 없는 Main LC1을 구분한다. 새 package·Stage4·연구를 자동 시작하지 않는다.
