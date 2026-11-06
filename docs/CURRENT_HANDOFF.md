# Current Project Handoff

Updated: **2026-11-07 (Asia/Seoul)** — Stage 4 Unit 6 rollout 선택기가 독립 **ACCEPT_BOUNDED**, 제품/helper 필수 수정 0으로 수용됐다. 구현자 전체 **PARTIAL**과 첫 Git 4건의 원시 공백 U6-R02는 보존한다. 현재 source 355개이며 신규 source/tests 7개와 문서 6개, 총 13경로 마감을 준비한다. 큰 공개 관측 18회는 모두 fallback이고 큰 보드 모델 선택·일반 효율·Main/UI는 미확인이다.

Unit 5는 commit **fa6e33aa9a02a6facff447b81862727ca4f6e216**와 Desktop destination 검증까지 완료됐다. Unit 4 **9545f6368898d1f0679d178cd1dea5cdf8164ab9**, Unit 3 **1cf5ea9af95e69c069d3137b733801a43819333e**, Unit 1·2 **a0c503dd9bf6e106e132fa5a70cb8d5cd8bb0c81**, 거리 관람·고정 6 **dc740e222c2b913fa1697fba0f4785cfffc37c2c**의 수용·실패 이력은 유지한다. 전시 노트북은 PENDING이다. 과거 source 수/마감 준비 문구는 당시 snapshot이다.

## Stage 4 현재 상태와 다음 범위

- [Unit 6 rollout 선택 정책 closeout](stage4/STAGE4_ROLLOUT_POLICY_UNIT6_CLOSEOUT.md): 정확 posterior 표본·공개 P0·S/M/R·원자 입력과 같은 인스턴스의 continuation을 한정 수용했다. 기존 source 348개는 불변이다.
- **W1:** READY 104 = MODEL_SELECTED 69 + 실제 fallback 29 + continuation 6. 비READY 35 중 3개의 잔존 fallback basis를 선택으로 세지 않는다.
- **W2:** MODEL_SELECTED 69 = 합성 주입 4 + 실제 가상 rollout 65, 그중 실제 소보드 폐루프 43. **W3:** A 13/B 11(v01)과 추가 B 4(v02)는 별도 실행이며 v02 28개 일괄 PASS가 아니다.
- 작은 실제 25시도는 WON 13 / LOST 10 / GUESS_BLOCKED 1 / UNRESOLVED 1. 전체 평균 null, G001 세 모드 12/35, G009 S 2/5·M/R 1/2. 실제 M/R 차이는 확보하지 못했고 target 변경 차이는 합성 시험이다.
- 큰 18호출은 root/sampler COMPLETE이지만 모두 fallback. 예정 1,728행 중 미완료 18/가상 WON 3/미시작 1,707을 보존한다. P0 추측의 칸별 전체 제약 순회가 20,000 work cap에 닿았으며 다음 계산량 개선 범위다.
- N1~N9와 U1~U8, U6-R02의 복구 불가능한 과거 기록 공백은 closeout 처분을 따른다. 현재 모듈에는 추가 native가 필요 없으며 UI/worker·큰 보드 모델 선택·전시 노트북은 후속이다.

- [Unit 5 후보 수순 근거 closeout](stage4/STAGE4_CANDIDATE_EVIDENCE_UNIT5_CLOSEOUT.md): OPEN·해제·FLAG 준비 CHORD의 전체 비용, 공동 생존 Ws와 0 사건 Zt, S/M/R 위험 eligibility를 계산한다. 최종 선택이나 전체 효율 점수는 반환하지 않는다.
- A 25/B 1은 별도 시험이다. 24관측/2,761 mask/168후보/3,038 profile, 339 engine macro/1,403입력, 큰 6 snapshot의 4,699 고유 사건(새 조회 1,749 포함)을 독립 재현했다.
- C의 후보 2,373·0 대상 2,976, backend 118/work 236,097이 일치했다. 국소 비율이나 0 대상 수를 최종 IOE·오프닝 개수로 부르지 않는다.
- U5RV-N1~N5는 생존 가능한 최소 위험 OPEN 해석, 7종 방어의 코드 검토/미관측 구분, helper 변경 전체, 시각 표기, exit code에 근거한 종료 판정으로 기록한다. U5RV-U1 최초 tool controller 부재 원시 없음, U2 backend 내부 취소/시간 미시험, U3 잘린 표시 미보존, U4 설정/성능 일반화 미확인은 유지한다.
- 논리 시작 3/Python 6/Job 3 정리와 별개로 최초 tool controller의 과거 부재를 소급 증명하지 않는다. Unit 5와 과거 Unit 2 C01/H01·Unit 3 U3-H01 이력은 구분한다.

- [Unit 4 공개 계수기 closeout](stage4/STAGE4_PUBLIC_COUNTS_UNIT4_CLOSEOUT.md): 공개 D/M/공동 사건 W를 정수로 계산한다. 물리 FLAG는 미지수이고 실제 배치·비공개 카운터·미래 입력을 받지 않는다. 행동·E[X]·목표 확률을 반환하지 않는다.
- 상한은 480칸/사건 16/work 200,000/협력 시간 2초다. base 원자적 확정, 사건 PARTIAL과 미완료 null을 구분한다. 기존 작은 계획기와 Main/Live에는 연결하지 않았다.
- A 17개와 B 4개의 새 시험이 별도 실행으로 통과했다. 독립 재계산은 작은 32관측/13,627 bitmask, 분석해 7요청, Replay 6관측의 D·M 1,956개·W 37개 모두 일치했다. component M 346개는 두 번째 방법으로도 확인했다.
- EXACT 37의 구성은 W=0 19 / W=D 7 / 중간값 11이며 입력 32 이후 정보성 사건은 관측당 1개다. 일반 큰 frontier 비용이나 안정 시간의 근거로 확대하지 않는다.
- RV4-N1: 동결 RUN_PLAN 예상 UTC가 07:33/09:33Z로 잘못 기록됐다. 실제 시작+1/+3시간은 16:33/18:33Z다. 보고서에 원시 오류가 빠졌으므로 closeout에서 병기하고 원본은 유지한다. 다른 기한은 정확하다. RV4-N2/N5: 약 15.6 ms monotonic, elapsed 0의 의미와 비중단 구간을 기록해 실시간 보장과 구분한다. N3~N5·미확인 5건은 개별 처분을 따른다.
- Unit 4 논리 시작 5/Python image 7/Job 4, 구현자 incident 3/9(bootstrap와 launcher 실패 포함), 검토자 별도 incident 1/4를 보존한다. run04의 TerminateJobObject 호출 사유는 미확인이며 종료된 process 0·exit 0/0/0이다.

- [Unit 3 평가기 closeout](stage4/STAGE4_EVALUATION_UNIT3_CLOSEOUT.md): 제품 ACCEPT_BOUNDED, 근거 ACCEPT_BOUNDED_WITH_NONBLOCKING_DEFECTS, 실제 시작 Job 6개 ACCEPT. 원 전체 PARTIAL과 U3-H01 UNCONFIRMED를 보존한다.
- `stage4_evaluation.py`와 신규 시험은 공개 prefix 전수 재생, 실제 한 입력 후 재계획, 네 결과·미시작·미완료 분모와 정확 집계를 다룬다. 시험 17개는 기존 Unit 1 27개·Unit 2 18개와 별도다.
- 최종 36설정 MATCH, 123건=동결 후 신규 113 + 동결 전 완료 재사용 10. G001_R_tau1와 두 two_ends_M 추측 설정 및 shared_flag_M의 4설정은 전량 재사용이다. 최종 결과는 WON 64 / LOST 53 / GUESS_BLOCKED 6 / UNRESOLVED 0이다.
- 독립 모델이 고유 실제 정책 174시도와 생성 전이(총 1,704전이)를 재생했다. 낮은 depth 3/5의 8사례/28배치에서 FLAG 뒤 미완료를 재현했고, 기본 depth 12는 28배치 모두 종결·8 MATCH다. 일반 연속성 증명은 아니다.
- S/M 및 M/R의 엄격한 목적값 차이가 작은 witness에서 확인됐다. E[X]는 실패 0을 포함한 무조건부 효용이며 승리판 평균과 다르다. 일반 효율 우위·세계기록·추천 τ로 확대하지 않는다.
- [Unit 1·2 기반 closeout](stage4/STAGE4_OPENING_PLANNING_FOUNDATION_CLOSEOUT.md)의 수용·실패 이력을 유지한다. Unit 2 C01 최초 Git 전 기록 공백, Unit 2 H01 집계 오류, Unit 3 U3-H01은 서로 다르다. 이후 성공으로 과거 PASS를 만들지 않는다.
- 계획기는 전체 64칸/닫힘·깃발 8칸 이하의 선언 후보군이다. 처음 score와 재계획 결과의 일반 동등성은 미증명이다. Unit 4의 480칸 상한은 이 계획기의 지원 확대가 아니다. Unit 5가 후보 비교 근거를 추가했고 Unit 6가 제한 rollout 선택기를 구현했다. 다음은 P0 계산량 개선과 큰 관측의 모델 선택 경로 확인이다. 근사 점수를 정확한 최종 E[X]/목표 확률로 부르지 않으며 화면 연결은 별도다.
- 이번 평가는 UI/Live 입력 경로를 바꾸지 않아 추가 사용자 native 확인은 해당하지 않는다. 향후 화면/입력 연결과 전시 노트북 수용은 별도다.

## 현재 authority와 기능

기존 같은 보드 기능·실패 이력·당시 B/C 근거는 [같은 보드/Replay closeout](stage3-extended/STAGE3_MAIN_LIVE_SAME_BOARD_CLOSEOUT.md)을 따른다. [관람 속도/CPS closeout](stage3-extended/STAGE3_MAIN_LIVE_PACING_CLOSEOUT.md)은 완료 commit **4c10217**까지의 이전 checkpoint이며 원 속도 계약은 유지한다.

2026-11-05의 진단 근거는 [고속 CPS 제한 진단 closeout](stage3-extended/STAGE3_MAIN_LIVE_HIGH_CPS_DIAGNOSTIC_CLOSEOUT.md)이다. 실제 실행 HEAD는 **cd8ee2ef23a2753f858f8945d7a9bff1580369fb/source333**이며 이후 문서 commit을 그 실행 HEAD로 소급하지 않는다.

현재 추가 기능은 [거리 관람 closeout](stage3-extended/STAGE3_MAIN_LIVE_DISTANCE_VIEW_CLOSEOUT.md), 최신 최적화·native·검토는 [고정 6 CPS closeout](stage3-extended/STAGE3_MAIN_LIVE_FIXED6_OPTIMIZATION_CLOSEOUT.md)을 따른다. 출발 HEAD는 **dc711a7917edf3f00bbad26f710b5240c08d7f13**이고 source 335개다. 현재 변경 source/tests는 `ui_manager.py`, `live_distance_pacing.py`, `tests/test_live_distance_pacing.py`, `live_policy_job.py`, `live_policy_transport.py`, `tests/test_live_policy_job.py`의 6경로다. 거리 테스트 hash는 **3a1c2be377f552b6af4792954bb5c0641af84716c41b773f1c91275f134d434a**로 유지되며 현재 전체 source는 고정 6 CPS `codex_02/SOURCE_COMBINED.json`과 같다. 이전 333개 목록을 현재 335개 목록으로 오인하지 않는다.

- Live WON/LOST와 worker 정리 뒤 같은 배치의 새 판을 시작한다. 새 game_id/세대·시간/입력/Replay/M 초기화, Auto/guess OFF, 정책·속도·표시 선호 유지. V1/K는 세 preset, custom은 기존 Simple/수동 범위다.
- 고정판은 **FIXED_BOARD/wire v10**의 공개 관측 기반 정상 추론을 사용한다. all-HIDDEN이어도 canonical 안전 첫 수가 아니며 guess OFF 대기, ON에서 첫 지뢰면 LOST가 정상이다. 숨은 layout은 GUI의 배치 복원에만 쓰고 정책에 넘기지 않는다.
- 기록은 동일 dimensions/지뢰 수/전체 좌표 묶음이다. 첫 Live 재플레이 뒤 활성화, 현재 완료판은 메뉴/Replay 진입 전 game_id당 한 번 캡처한다. 진행 중/미증명/정리 미확정 판과 imported Replay를 완료 Live로 위장하지 않는다. 원 Replay/source/evidence는 불변이다.
- **기본 Replay 종료**: 보고 있던 Replay의 크기/지뢰 수로 미배치 canonical 새 게임, fixed origin 없음, 기록 묶음/활성화/메뉴 초기화. **명시적 같은 보드 다시 플레이**: Replay의 원 배치로 닫힌 fixed 새 판, 기존 같은 배치 기록 유지. 이전 Live position의 재개가 아니다. 저장 파일은 지우지 않는다.
- 새 게임/난이도 재구성과 다른 배치 Replay의 성공한 진입은 기록을 비운다. 취소/invalid load/같은 배치 왕복은 보존하고 옛 QAction/closure는 무효다.
- Replay 요청은 Auto/guess·입력 예약을 회수하고 Live에서 원 ACK·worker 정리를 기다린다. 정리 뒤 queued commit 1회, 실패 시 Live와 최초 구체 사유 유지. reset/정책/난이도/수동 첫 press/close는 예약을 폐기한다. 보관 불가 완료판이 있으면 구체 사유로 파일 진입도 거부한다.
- Simple/V1/K-P0/K-LC0/K-LC1의 인수/FLAG 준비·수동 인계, 원 session/M/decision identity, VALIDATE→ADMITTED→무yield token→step1→정확 ACK→NEXT는 유지한다. old owner 정리 전 새 owner는 시작하지 않는다.
- 기본 고정200ms/목표5 CPS, FixedPeriod.period_ns·정확 Fraction·QPC/PreciseTimer·bounded fixed-rate를 유지한다. 6 CPS=166,666,667ns, 작은 지연은 위상 유지, 큰 지연은 실제 입력+P, 최소0.9P다. Model C는 원 행동 비용/배속이며 frozen 표를 바꾸지 않는다.
- 새 **거리 기반** 모드는 이미 선택된 target까지의 public/actual cursor 거리를 관람 대기로 변환한다. 배속 0.05–8, 기본 1이며 고정값·Model C 배속과 독립 보존한다. 관람 대기는 target 선택 뒤 시작하고 K VALIDATE는 대기 완료 뒤 수행한다. 실제 간격에는 계산·통신도 포함되므로 배속과 실측 CPS는 비례하지 않는다.
- 확률·확정색·가상 원형/녹화입력·Simple 참고분석/키보드·human trace 경계는 이전 수용대로다. K 라벨에서 실험적 접미사를 뺀 것은 Production 승인이 아니다.

## 검증과 사용자 수용

이전 같은 보드 마감의 source333 manifest SHA256: **07feed55cdfd2979c4022efd3c90b5b6fe1a541de175df13f2965ced729676e5**. 현재 source335와 별도의 역사적 authority다.

- overnight A: 최종 독립119/299, owner14, probe118; B/C는 별도 산술 검토다.
- history flow: 최종 독립33/52, owner2, fixture 실패 수정 후 probe67.
- entry guard: 최종 독립45/86, owner2, probe30. RV2-O1의 실제 진입 실패 경로를 막고 O3/O4를 해소했다.
- **최종 exit choice: 독립49/143, owner2(V1 canonical/K-LC1 fixed), probe28, REQUIRED0/OPTIONAL0.** 입력/Replay/ACK 각1, NEXT0, ACK→정리→commit과 reap/tree0/channel/handle 정리를 확인했다.

버전별 숫자를 합쳐 전체 suite로 쓰지 않는다. 사용자는 source332 기능을 수용한 뒤 기본 종료를 새 판으로 바꾸도록 요구했고, 최종 source333의 두 종료 선택을 안내한 뒤 **“이제 통과야.”**라고 수용했다. 현재 사용자 환경/항목에 한정하며 모든 OS/DPI·부하·전체 suite를 뜻하지 않는다.

## 거리 모드와 보완분 — 독립 수용, 이번 PC native 수용

로컬 묶음 root는 `outputs/MAIN_LIVE_PERFORMANCE_DISTANCE_IMPLEMENTATION_2026-11-06`이다.

- `codex_01`: 22회 timing, 실제 policy 입력 1369 + Simple 1, 거리 모드 구현. 원 outer launcher의 suspended 생성과 helper 소유 Job은 **NOT_APPLIED**, ambient Job은 **NOT_SAMPLED**, outer conhost는 **NOT_IDENTIFIED**다. 원 전체 **PARTIAL**은 유지하지만 기능·산술은 `review_claude_01`에서 ACCEPT_BOUNDED, 제품 필수 수정 0으로 수용했다.
- `codex_02`: 새 outer helper의 P1 정상/P2 timeout/P3 resume 전 중단. `codex_03`: 동일 helper로 T1/T2의 새 메서드 3개, 하위 사례 10개. 기존 테스트 줄 삭제는 없고 제품 두 파일은 그대로다.
- `review_claude_02`: 새 helper/T1/T2는 **ACCEPT_BOUNDED**, CR01-F03 라벨 정정은 **ACCEPT**. 필수 보완 0, 선택 6. CROSSCHECK 38 = MATCH 34 / MISMATCH 0 / NOT_VERIFIED 3 / NOT_SAMPLED 1이다. 원 검토의 incident 6/6과 새 검토의 incident 0/3을 구분한다.
- 렌더 후보는 V1 16.19% 개선, LC1 9.57%로 사전 기준 미달해 미채택·복원했다. TRACE 영향과 drift의 인과 분리는 INSUFFICIENT이고 안정 CPS 상한을 확정하지 않았다. LC1 fixed6의 약 5.724 CPS는 해당 조건의 관측이다.
- 이 거리 단위 당시 새 controller는 owner 없는 graph와 offscreen test driver에 한정됐다. 후속 고정 6 CPS의 G01에서 **CR02-F04의 실제 owner 사례**를 확인했고 이후 같은 controller의 정리 근거를 독립 대조했다. 과거 기록을 실제 owner 검증으로 소급하지 않는다.

이후 검토된 최적화 반영 상태에서 사용자가 세 모드 진행·중단과 두 Replay 종료 후 선호 보존을 “모두 통과”로 수용했다. 전시 노트북은 별도로 PENDING이다. 선택 6건과 이전 선택 권고는 closeout의 개별 disposition을 유지한다.

## 고정 6 CPS 최적화 — 정확 반영 및 사용자 수용

외부 root는 `outputs/MAIN_LIVE_NATIVE_FIXED6_OPTIMIZATION_2026-11-06`이다. 원 `codex_01`의 C1은 원본 대비 8.796620% 개선했으나 목표 미달, C2의 C1 대비 추가 효과 4.820778%는 5% 기준 미달이었다. 두 미채택 판정과 focused FAIL, incident 9/8은 그대로다.

새 `codex_02`의 원본 대 결합본 직접 3쌍은 5.788274/5.765701/5.796701 CPS, gap 개선 중앙값 12.484226%, CPU/입력 +3.856749% 및 +6.966561 ms로 사전 기준을 충족했다. 실제 Auto 157 / Replay 158(수동 prefix 1) / ACK 157, 동일 행동·좌표·M·원 Model C 누계와 WON·정리를 독립 재계산했다. 최소0.9P와 자기 deadline, 고정/관람 모드 계약은 유지한다. 이 수치는 해당 기계·보드·세션에 한정한다.

`review_claude_01`은 A ACCEPT_BOUNDED, B ACCEPT/제품 필수0, C CONDITIONS_REMAIN으로 수용했다. `codex_03`이 동일 스타일시트 재설정 생략·worker 응답 알림과 테스트의 네 파일을 정확히 반영했고, source335 전체가 COMBINED와 같다. 별도 R2 mock 56개 PASS, owner 0이며 과거 28개/표시 126개/S01 1개와 단일 suite로 합산하지 않는다.

H1은 Git 읽기에 `diff.autoRefreshIndex=false`와 optional-locks0을 적용하고 모든 읽기 뒤 최종 index 해시를 기록해 완료했다. 과거6a59→f0ff→bf95의 stat-cache 변화와 raw-byte FAIL/작성 PID 미확정은 유지한다. R1/R2 완료, R3/R5 보류, R4 전시 노트북 PENDING이다. 원 S03의 CUA 승인 시간 초과·외부 click0·보완 PARTIAL/incident5/3도 유지한다.

사용자는 후보 반영 확인 뒤 **“좋아, 모두 통과야.”**라고 이번 PC native를 수용했다. 별도로 목표 10 CPS에서 약 8–9 CPS를 보았다고 보고했으나 원시 기록·관측 구간·metric 종류는 미확인이다. 안정 상한이나 별도 측정 PASS로 쓰지 않는다.

## 이전 고속 CPS 제한 진단 — 묶음 독립 수용

**COMPLETE_BOUNDED_DIAGNOSTIC / 독립 수용**, 필수 증거 수정0·제품 결함0이다. V1/K-LC1, 기존 30×16/99 합성 공개 저부하 fixture, fixed0ms의 MIN1/TRACE/MIN2 여섯 run이다. 각 actual/Replay/ACK62/62/62, 총 Auto372, steady60/59gap이다.

- RESUME 약44.060분, Python10/12, owner7/8, C보정2/2. C01은 actual0의 bootstrap 실패 뒤 한 번 대체했고 성공6개 timed signature가 같다. C02는 마감 PowerShell 집계 보정으로 새 Python/owner0이다. P01의 실제 startup 순서 검증 공백과 이전 Unit1 PARTIAL/4·상한2/당시 NOT_VERIFIED는 보존한다.
- V1 drift0.678704%/관측 TRACE 변화+1.938511%, LC1 drift1.759086%/+0.740295%. 잠정5%는 사용자·제품 수용치가 아니며 순차 관측의 drift와 인과 overhead를 완전히 분리하지 못한다.
- 부모 anchor만 gap을 비중첩 분할한다. 성공 read_next 약6.5–7ms와 render_board 약22ms는 중첩된 후속 후보이며 순수 IPC/poll·단독 원인·자연 판 상한은 미확정이다. MIN은 공통 seam을 포함한 하네스 기준이다. native paint/실제 표시 지연은 미측정이며 최적화는 **NOT_PERFORMED**다.
- Claude 약27.915분, 새 제품 Python/Qt/worker/owner0, 도구 오류2/2. CROSSCHECK205=정확201+참고2+문자열 주석 문제2, review manifest는 자기 제외16/포함17파일이다. E1 setup timerType1·E2 UI 구간 잘라냄·M3 하네스 기준 문구를 closeout에 명확히 했고 M1/M2 helper 유지보수는 선택 권고로 남긴다. 원 evidence는 수정하지 않았다.
- 조율은 기존 TRACE만으로 poll 구간을 추가 재구성했다. parent 진입 간격 median30.3407/30.83585ms, worker 부재 read 반환→다음 read mean10.194602/10.235673ms다. 새 실행0이고 순수 timer/scheduler 비용으로 귀속하지 않으며 이 보충 자체를 Claude 독립 수용으로 부르지 않는다.

## 기존 B/C 측정·분석의 남은 한계

**B1 NOT_SATISFIED**: 기존40행 속도/burst 산술은 재현됐지만 동일 owner·설정별60입력 조건은 미충족이다. 설정별 별도 owner60과 동일 owner12를 혼동하지 않는다. 당시 함수별 NOT_MEASURED/최적화 NOT_TRIGGERED를 후속 진단으로 소급 변경하지 않는다. B1은 이번 진단의 선행 조건이 아니며 OUT_OF_SCOPE다. V1 target8→7.914/10→9.183 및 특정 상급0ms 값은 관측일 뿐 일반 상한이 아니다. window peak의 이산 경계 편향도 보존한다.

C는30판/5,035전이/24 player OOF 산술 재현 PASS다. RMSE constant152.440/log129.389/bands128.597ms, log와 bands 차이는0.792ms이며 긴 gap 제외 시 순위가 뒤집힌다. d>16은3표본/비정상 장거리 전이가 있어 해석하지 않는다. action UNKNOWN·직선 target 거리로 판단/운동 시간을 분리할 수 없다. 당시 제품 미적용이던 descriptive fit을 2026-11-06 별도 관람 기본안으로 사용했으며, 원 Model C와 연구 판정은 불변이다.

과거 overnight helper5/3 위반, history2/2와 probe fixture 실패, entry F01 수정 이력, exit helper2/2를 보존한다. 최종 OPTIONAL0이 과거 유지보수/그래프/측정/harness 권고 전체의 CLOSED를 뜻하지 않는다. **F02 NOT_VERIFIED / 과거 Qt shared FileDialog FAIL / 이전 TEMP NOT_VERIFIED** 유지. 재검증 루프나 전역 TEMP 검색을 열지 않는다.

## Git / 다음 단계

작성 시 main/HEAD=local origin/main=**fa6e33aa9a02a6facff447b81862727ca4f6e216**, ahead/behind 0/0, staged 0, index **37e76e6eec79d2fb3dfe7e349533e90f6ab19c38cf46f41d8141c78d84e75983**다. Unit 5의 완료 권위는 `STAGE4_UNIT5_POSTCOMMIT_RECOVERY_2026-11-07/coordinator_01/DESKTOP_REPLACEMENT_VERIFICATION.json`의 PASS_ALL_CLOSEOUT_STEPS_COMPLETE다.

현재 Unit 6 신규 source/tests 7 + 문서 6 = 13경로는 `outputs/STAGE4_UNIT6_CLOSEOUT_2026-11-07/coordinator_01`의 계획과 사용자 스크립트로 묶는다. commit/push 영수증 확인 뒤 Desktop recovery 2개를 별도 교체한다. 완료된 과거 스크립트를 재실행하지 않고 문구만을 위한 추가 commit을 만들지 않는다.

다음 개발은 칸별 제약 index·빈 제약 생략 등 P0 계산량 개선을 별도 계약으로 정하고, 작은 동등성 및 큰 공개 관측의 모델 선택을 검증하는 일이다. 현재 상한만 높이거나 성공 단계를 반복하지 않는다. 일반 상급판 전체 평가·Main/UI·native·패키지는 그 뒤다.

Codex 모델은 사용자 지정 Astra/Max를 기준으로 하고 미노출 실제 설정은 UNCONFIRMED다. Claude는 큰 단위 뒤 묶어서 검토한다. 과거 오류/예산과 새 보완 예산은 분리한다.

## 역할과 영구 경계

구현·실제 측정은 별도 Codex, 독립 검토는 Claude Code, 현재 채팅은 조율·문서·Git/recovery 인계다. 작은 환경/helper 수정은 정해진 범위·복구 예산 안에서 Codex가 이어가고 결과가 모이거나 큰 단위가 끝나면 Claude에 묶어서 넘긴다. coordinator는 제품 source/tests·프로젝트 Python/Qt/worker·실제 Git 쓰기·Desktop 교체를 수행하지 않는다. 긴 프롬프트는 높이 제한 스크롤·전문 복사·TXT로 제공하고 큰 단위 후 문서와 사용자 Git을 일괄 마감한다.

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE. Phase2/R0-B/ActualE2 미승인/미실행. frozen 정책·Model C·holdout **2,010,000..2,010,099**·금지 연구 formal evidence 경계를 지킨다. Main source 수용은 새 package/Stage4/연구 자동 승인과 다르다.
