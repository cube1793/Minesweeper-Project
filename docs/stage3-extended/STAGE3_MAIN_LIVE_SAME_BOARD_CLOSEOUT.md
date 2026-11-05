# Main/Live 같은 보드 재플레이·기록·Replay 종료 선택 closeout

기준일: **2026-11-05 (Asia/Seoul)**. `main` / 실행·작성 기준 HEAD 및 local `origin/main`은 **4c1021711e53e45a29450da9fa3bebee54e80887**이다. 이후 사용자 commit/push의 실제 SHA와 clean 상태는 후속 receipt/recovery/live Git을 따른다. 새 commit을 이전 테스트의 실행 HEAD로 소급하지 않는다.

## 1. 판정과 범위

| 구분 | 현재 판정 |
| --- | --- |
| A: 같은 보드 재플레이·그룹 기록·Replay 진입/종료 | 구현, 범위 한정 독립 검토, 최종 사용자 native 수용 완료 |
| 최종 종료 선택 검토 | **49 methods / 143 subtests**, 실제 owner 2, 독립 probe 28; REQUIRED_FIXES 0 / OPTIONAL 0 |
| B: 자연 진행·고정 속도·burst 측정 | 원시 결과 40행의 독립 산술 재현 PASS; **B1 NOT_SATISFIED** 유지 |
| C: 거리와 전이 간격 분석 | 30판·5,035전이·24 player 그룹의 독립 산술 재현 PASS; 제품 보정식 미적용 |
| 효과성 / Production | **effectiveness NOT ESTABLISHED / Production K·Gate P 미승인** |
| Git 마감 | source/tests 20 + 문서 6 = **26경로(M19/U7)** 사용자 일괄 commit/push 대기 |

전체 밤샘 묶음 PASS, 모든 부하의 고속 CPS 보장, 새 package, Stage-4 또는 연구 실행 승인이 아니다. 기존 [속도/CPS closeout](STAGE3_MAIN_LIVE_PACING_CLOSEOUT.md)은 `4c10217`까지의 이전 수용 기록이며 관람 속도·원 Model C 계약은 유지한다.

## 2. 현재 제품 계약

### 종료판 같은 보드 재플레이

Live WON/LOST 판에서 원 입력/worker 정리가 확인된 뒤 **같은 보드 다시 플레이**를 사용한다. 가로·세로·지뢰 수와 전체 mine 좌표를 유지하고 모든 칸을 닫는다. 진행 중인 Live를 그대로 이어가는 기능은 아니다.

`live_same_board.py`의 frozen `FixedLayout`/`FixedOrigin`/`CompletedLiveGame`은 GUI 전용이다. layout은 `frozenset`으로 분리되며 완료 기록에는 Replay와 직렬화한 입력/action/owner·정리/통계 근거가 남는다. 실제 완료 Live layout과 기록 layout이 같아야 캡처된다. 숨은 mine 좌표는 solver 입력으로 전달하지 않는다.

매 시도는 새 game_id·세대·시간 0·입력 0·빈 Replay/M/cursor로 시작하고 Auto/guess는 OFF다. 정책·관람 속도·표시 선호를 유지한다. 수동 첫 수 없이 Simple/V1/K-P0/K-LC0/K-LC1 Auto를 시작할 수 있다. V1/K는 기존 세 preset에 한정하며 custom 지원을 추가하지 않았다.

고정판 시작은 `FIXED_BOARD`와 공개 관측/entry provenance로 검증한다. all-HIDDEN이라도 canonical 안전 첫 수로 위장하지 않는다. 첫 제안부터 공개 상태의 정상 추론/선택을 사용하며 guess OFF에서는 기다린다. 첫 OPEN이 지뢰이면 정상 LOST다. 원 배치를 옮겨 첫 클릭을 안전하게 만들지 않는다.

공통 wire는 **v10**이다. V1 fixed_game_id와 K game_id/definition, entry·세대·revision·cursor·빈 시작 M 등 원 provenance를 끝까지 결속한다. 이전 v9/알 수 없는 wire는 거부한다. 기존 정책·Model C·최종 비교→token→step·정확 ACK·cleanup 한도는 유지한다. `live_policy_job.py`의 변경은 기록의 고정판 game_id/definition 표현이며 lifecycle/containment 재설계가 아니다.

### 같은 배치의 기록 묶음

**재플레이 전 기록**은 처음에는 비활성이다. Live 종료판의 첫 같은 보드 재플레이로 활성화한 묶음만 관리하며, dimensions/지뢰 수/전체 mine 좌표가 같은 완료판을 보관한다. game_id로 중복을 제거하고 원 Replay/source_type/evidence를 바꾸지 않는다.

활성 묶음에서 메뉴를 열거나 Replay로 전환하기 전에 현재 완료판을 한 번 캡처한다. 진행 중·이력 미증명·정리 미확정 판은 완료 기록으로 넣지 않는다. 캡처할 수 없으면 구체적인 이유와 함께 전환을 거부하며 무관한 파일을 열려는 경우에도 원 완료판을 조용히 버리지 않는다.

새 게임·난이도 재구성과 다른 배치 Replay의 성공한 진입은 묶음/활성화/메뉴를 비운다. 불러오기 취소·잘못된 파일·같은 배치 왕복은 보존한다. 지운 메뉴 QAction/옛 closure는 같은 모양의 다음 판에서도 되살아나지 않는다. 외부·미완료 Replay를 완료 Live 기록으로 위장하지 않는다.

### Replay 진입과 두 종료 선택

Auto 중 Replay를 요청하면 Auto/guess와 입력 예약을 회수하고 **Live에서** 원 ACK 검증 및 worker 정리를 기다린다. V1은 검증에 필요한 owner/세대를 ACK까지 유지하고, K는 기존 봉인 receipt drain을 쓴다. 정상 정리 후 queued commit으로 한 번만 진입한다. ACK 미확인/worker 오류/cleanup 실패는 Live와 최초 구체 사유를 유지한다. 실패 잠금을 지우고 강제로 전환하지 않는다.

예약은 원 game/세대/정책/이력·상태/owner와 불변 ReplayData에 결속한다. reset·난이도·정책·수동 첫 press·close에서 폐기하며 늦은 ACK/finished/permit이 새 판을 바꾸지 않는다. 동일 요청·중복 signal은 중복 drain/commit을 만들지 않는다. 즉시 진입은 원 ReplayPlayer, 비동기 진입은 frozen 데이터의 새 player를 쓴다.

| 종료 선택 | 새 Live 판 | 기존 재플레이 전 기록 |
| --- | --- | --- |
| **Replay 종료** — 기본 API/버튼 | 보고 있던 Replay의 가로·세로·지뢰 수로 일반 canonical 새 게임. 초기 지뢰 미배치, fixed origin 없음 | 묶음·활성화·메뉴 초기화 |
| **같은 보드 다시 플레이** — 명시적 버튼 | 보고 있던 Replay의 전체 원 배치를 닫은 새 FIXED_BOARD/v10 판 | 기존 동일 배치 묶음과 evidence/출처/순서 유지 |

Replay의 시작/중간/끝 위치 및 이번 판/기록/파일 진입 출처와 무관하다. 이전 Live position을 재개하지 않는다. 두 경로 모두 새 identity/통계/이력/M, Auto/guess OFF와 정책·정확 CPS/Model C 배속·표시 선호를 유지한다. 외부 저장 파일은 삭제하지 않는다.

두 종료는 가드를 먼저 검사한다. 거부 시 mode·player·재생 위치/autoplay·그룹·현재 판을 바꾸지 않는다. 기본 `_exit_replay_mode()`는 canonical이고 `same_board=True`는 keyword-only 명시 선택이다. clicked(bool)는 mode 인자로 전달되지 않는다. 기존 NoFocus 재플레이 버튼을 Replay에서도 활성화하며 Live 종료판의 기존 역할도 유지한다. Replay Space/Return, Live 키 규칙과 좁은 창 레이아웃을 보존한다.

## 3. 버전별 검증·사용자 수용

| 단위 | 당시 source | 독립 focused | 새 실제 owner | 독립 probe |
| --- | --- | --- | --- | --- |
| overnight bundle A | 330 | 119 / 299, 최종 단일 실행 | 14: 5×1 seam 10 + production preset 4 | A 118; B 산술/C 21은 별개 |
| same-board history flow | 331 | 33 / 52, 최종 단일 실행 | 9×9 V1/K-LC1 2 | fixture 실패 보존 뒤 67 PASS |
| Replay entry guard | 332 | 45 / 86, 최종 단일 실행 | 9×9 V1/K-LC1 2 | 30 PASS |
| **Replay exit choice — 최종** | **333** | **49 / 143, 최종 단일 실행** | **V1 canonical / K-LC1 fixed 2** | **28 PASS** |

표의 숫자를 합쳐 최종 전체 suite나 같은 실행의 총계로 표현하지 않는다. 구현자의 초기 119 합성 및 history 33 합성은 당시 기록으로 남고, 각 독립 최종 단일 실행이 해당 bytes만 확인한다.

최종 49개는 이전 40 ID 유지 + 이름/기대가 바뀐 기존 2 + 새 7이다. generic 종료 검사는 canonical로 1:1 교체하고 same-board 의도만 명시적 handler로 옮겼다. 무관한 모델 불변식 2/단독 Live 반복 1 제외는 검토에서 타당하다고 판단했다. 기본 경로를 지우거나 assertion을 약화하지 않았다.

최종 실제 worker는 V1 기본 종료 뒤 revision 0/initial/non-guess/안전 첫 OPEN, K-LC1 fixed 뒤 revision 0/guess 대기→허용/원 배치·기록 보존을 확인했다. 입력/Replay/ACK 각 1, NEXT 0, wire v10, 원시 QPC와 wire의 ACK 확인→정리→Replay commit, 두 번째 종료와 늦은 메시지 거부가 검토됐다. 모든 owner의 reap/tree0/channel/Job·process handle 정리를 확인했다. canonical 배치는 RNG 그대로이며 결과를 맞추는 반복은 없었다.

사용자는 source332의 기존 기능에 **“다 통과했는데 한 가지만.”**이라고 수용하고 기본 종료와 명시 재플레이를 분리하도록 요구했다. 최종 source333/표적 검토 뒤 두 선택의 native 확인을 안내했고 **“이제 통과야.”**라고 수용했다. 현재 사용자 환경과 안내 항목에 한정하며 모든 OS/DPI·preset 완주·전체 suite·일반 처리량을 승인하지 않는다.

## 4. B 측정 — 산술 확인과 미충족 조건

자연 진행 15판과 저부하 고정 속도/burst 결과 **40행**은 독립 검토가 원시 QPC에서 재계산해 일치했다. 주 CPS는 `(N−1)/(마지막−첫 Auto 입력 시각)`이다. steady/warmup/P95/최대 gap, 완전 0.5초·1초 window와 목표/최소 간격 검사도 구분했다. 목표보다 이른 입력과 0.9P 위반은 0이었다.

**B1 동일 owner·설정별 60입력은 NOT_SATISFIED다.** 60입력은 설정마다 별도 owner/게임이며 동일 owner 전환은 설정당 12입력뿐이었다. 유한 fixture의 근거 범위 한계로, 제품 결함이나 완료 근거로 쓰지 않는다. 함수별 시간은 NOT_MEASURED, 최적화는 NOT_TRIGGERED다.

특정 자연 상급 0ms 관측은 Simple 29.585 / V1 9.828 / K-P0 6.619 / LC0 6.558 / LC1 6.415 CPS였고 V1 target 8→7.914, 10→9.183 steady였다. 일반 안정 상한·모든 보드의 burst 보장이나 병목 원인 확정이 아니다. window peak는 이산 개수 경계로 정상 5 CPS를 6.0으로 보일 수 있어 주 CPS와 동일시하지 않는다.

B_FIXED01 V1 8의 228입력/227ACK 구간은 제외되고 B_FIXED02 228/228로 교체됐다. B_LOW01 V1_5와 B_FIXED01 Simple 8/10/12는 exit 1 run의 정상 구간으로 수용된 기록이며 원 실패/정리 근거를 보존한다. B 재측정은 이번 기능 마감의 재검증으로 실행하지 않았다.

## 5. C 거리 분석 — 제품과 분리

기존 canonical 30판/5,065 events에서 **5,035전이**, 이름 정규화 후 **24 player 그룹**을 사용했다. U+00AD 제거로 26 이름 중 두 쌍이 합쳐졌다. 사전 FIT_PLAN, player별 leave-one-group-out 24-fold, 게임 동일 가중치·계수·OOF·민감도/bin은 독립 산술에서 재현됐다. 전체 적합 in-sample 값과 OOF를 혼동하지 않는다.

| 후보 | 게임 동일 OOF RMSE |
| --- | --- |
| constant | 152.440ms |
| bounded_log | 129.389ms |
| model_c_bands | 128.597ms |

constant 대비 bands 개선은 약 15.641%이나 log와의 차이는 약 0.792ms다. 0.5초 이상 gap을 뺀 NO_LONG_GAP/COMBINED에서 **log와 bands 순위가 뒤집힌다**. 일반 최적 모델·인간 운동 법칙·자연스러운 관람 효과를 확정하지 않는다.

`0<d≤1` 평균 간격 156.873ms의 역수는 6.375 CPS, `8<d≤16`의 534.589ms는 1.871 CPS다. 전이별 역수 평균 7.677/2.453과 다른 통계다. `d>16`은 3표본뿐이고 17.9칸/50ms 전이가 있어 해석하지 않는다. action은 UNKNOWN, 직선 target 거리는 연속 마우스 궤적이 아니며 판단 시간과 운동 시간을 분리하지 못한다. 그래프 색/가려진 선 권고는 보존한다.

**frozen Model C/profile/table은 불변**이다. 새 거리 보정식/프로필은 제품에 들어가지 않았다. 필요하면 별도 관람 프로필 설계를 승인하고 현재 자료의 민감도와 부하를 고려하며 기존 30판 분석을 자동 반복하지 않는다.

## 6. 실패·절차·잔여 판정

- overnight 구현 helper **5/3 한도 위반**은 유지한다. 최종 git status 미확인은 당시 기록이며 사후 읽기 확인으로 원 기록을 PASS로 덮지 않는다. `D_SYSTEM01` aggregate SUCCEEDED보다 개별 git exit128/ledger가 우선한다.
- history 구현 helper **2/2**, 독립 probe fixture 첫 guess 즉시 WON의 실패와 한 줄 수정/67 PASS를 보존한다. R01 V1 완료와 R01 LC1 부분 결과/R02 LC1 완료를 구분한다.
- entry guard F01 제품 player 호환성 assertion/ACK fixture error → F02 중간 → F03 45/86 최종과 helper 0/2를 보존한다.
- exit choice H01 rg glob/H02 원자적 patch 거부는 각 1회 복구 **2/2**다. 제품/테스트 실행 실패는 0, 독립 검토 사고/복구/이탈도 0이다.
- RV2-O1 진입 전 ACK·정리로 실제 도달 경로를 막았고 O3 테스트/O4 audit는 해소했다. O2의 보관 불가 시 파일 진입도 거부하는 정책은 의도된 잔여다. RV3-O1 화면 갱신/Close hook의 예약 폐기 유지보수 권고와 도달 경로가 발견되지 않은 이론상 Replay 내 실패는 기록으로 남긴다. 최종 종료 선택 OPTIONAL 0이 과거 모든 권고의 일괄 CLOSED를 뜻하지 않는다.
- PID 재사용은 생성 identity로 구분했다. 전역 TEMP 검색/삭제나 전역 Python kill은 하지 않았다. coordinator는 제품/Python/Qt/worker 및 실제 Git 쓰기를 실행하지 않았다.

**F02 NOT_VERIFIED / 과거 Qt shared FileDialog 보존 FAIL / 이전 TEMP NOT_VERIFIED**는 유지한다. 현 정상 파일 UI 확인은 사용자 전체 Qt 설정 보존 PASS가 아니다. 과거 검증 루프를 재개하지 않는다.

## 7. 외부 근거와 마감 authority

외부 root는 `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs`다. 각 폴더의 보고서와 manifest는 원 bytes에 결속되며 기존 evidence를 수정하지 않았다.

| 폴더 / 파일 | SHA256 |
| --- | --- |
| MAIN_LIVE_OVERNIGHT_BUNDLE_2026-11-05/codex_01/OUTPUT_MANIFEST.json (189) | 5a291ba083dfab3964adf55a88e63066f9854c337589914cbb6c50f2167a3b32 |
| 같은 root review_claude_01/OUTPUT_MANIFEST.json (57) | dea6714d59a2d487dba5ccd914954c3ecf447c7aa50ef383f8f8274ac8ab8259 |
| MAIN_LIVE_SAME_BOARD_HISTORY_FLOW_2026-11-05/codex_01/OUTPUT_MANIFEST.json (120) | 79d3c8f2d254be72d682c62257e880a3f9c3bd1a74c145dae551bd59cd8a0b08 |
| 같은 root review_claude_01/OUTPUT_MANIFEST.json (48) | 76259731cb2957d215626b4c7ab48d13de0d0a43fae2a2ff1c1ebee69d3c68d8 |
| MAIN_LIVE_REPLAY_ENTRY_GUARD_2026-11-05/codex_01/OUTPUT_MANIFEST.json (92) | 0199c92ccdd8b480d14178a8eaa9b16b614f4f0101347175ab2d2b9539ca294f |
| 같은 root review_claude_01/OUTPUT_MANIFEST.json (28) | 5760a1c531b0845b6177791312387a87d2b88873b060d879b38b60d38c02c285 |
| MAIN_LIVE_REPLAY_EXIT_CHOICE_2026-11-05/codex_01/SOURCE_MANIFEST_FINAL.json (333) | 07feed55cdfd2979c4022efd3c90b5b6fe1a541de175df13f2965ced729676e5 |
| 같은 root codex_01/OUTPUT_MANIFEST.json (85) | 7c84ba6fa603d9adf729b9f246ee82c5fbd28acdcfaf9559e8dfdc9df42aafeb |
| 같은 root review_claude_01/OUTPUT_MANIFEST.json (30) | ccdfe19854e3b6b5d980ebb4e0738d8c7742a9fca005e5d63ae497a2438637e7 |

문서/Git 준비 root는 **MAIN_LIVE_SAME_BOARD_DOC_CLOSEOUT_2026-11-05/coordinator_01**이다. 작성 시점 **4c10217 / ahead·behind 0/0 / staged 0 / 26경로(M19/U7)**이며 source/tests 20 + 문서 6이다. 사용자는 새 `USER_GIT_STEPS_KO.ps1` 한 번으로 exact stage/commit/push를 수행한다. 실제 receipt/parent/경로/blob/push/clean 확인 뒤 새 commit에 결속한 recovery 두 파일을 사용자 Desktop에서 교체한다. postcommit 문구만을 위한 추가 문서 commit은 만들지 않는다.

이후 후보는 B1 근거 보완의 필요성 판단, 필요 시 함수 단위 병목 측정, frozen Model C와 분리된 거리 기반 관람 프로필 설계다. 최적화/프로필/새 연구를 여기서 자동 시작하지 않는다. Codex 속도 선호는 사용자의 최신 지시에 따라 **Standard**, Claude는 Opus 5.5 / Max / Auto / Fast OFF다.

## 8. 영구 경계

**D0–D5 CLOSED / FINAL ACCEPTANCE PASS**, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE를 유지한다. Phase2/R0-B/ActualE2 미승인/미실행, frozen 정책·Model C 및 holdout **2,010,000..2,010,099**·금지 연구 formal evidence 경계를 유지한다. Main source 수용은 Stage-4/Extended 전체 마감이나 새 package 승인과 다르다.
