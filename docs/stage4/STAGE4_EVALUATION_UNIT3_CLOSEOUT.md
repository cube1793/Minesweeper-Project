# Stage 4 Unit 3 — 공개 정보 평가기 한정 수용

작성: **2026-11-07 (Asia/Seoul)**. 신규 평가기와 작은 비교 묶음의 독립 검토를 마감한다. 일반 상급판 효율, Main/UI/native 통합 또는 전체 Stage 4 완료를 선언하지 않는다.

## 권위와 변경 범위

실행 출발 HEAD는 **a0c503dd9bf6e106e132fa5a70cb8d5cd8bb0c81**이다. Unit 1·2 기반의 source 340개를 보존하고 `stage4_evaluation.py`, `tests/test_stage4_evaluation.py` 두 개를 추가했다. 현재 source는 342개다. 이후 문서 commit을 실행 HEAD로 소급하지 않는다.

| 신규 파일 | SHA256 |
| --- | --- |
| `stage4_evaluation.py` | `28cf940e8848105f4bb9aba0947f0e37c6f530b71b050916e66b2f629e055395` |
| `tests/test_stage4_evaluation.py` | `c81eb46e291b35c188f9ed11387bfdb52f99ecf86934e3db977a8202d446940e` |

독립 판정은 제품 **ACCEPT_BOUNDED**, evidence/helper **ACCEPT_BOUNDED_WITH_NONBLOCKING_DEFECTS**, 실제 시작한 Job 6개의 실행계약 **ACCEPT**다. 필수 수정은 0건이다. 구현자 전체 **PARTIAL**과 최초 controller 공백 **U3-H01 UNCONFIRMED**는 그대로다. 완료 원시 10건의 재사용도 주장 범위를 제한한 한정 수용이다.

[Unit 1·2 closeout](STAGE4_OPENING_PLANNING_FOUNDATION_CLOSEOUT.md)의 수용, Unit 2 C01 최초 Git 전 기록 공백, Unit 2 H01 마감 집계 오류는 이번 U3-H01과 서로 다른 역사다.

## 평가기 계약

`PublicCase`와 `prepare_case`는 현재 공개 숫자와 전체 지뢰 수에 맞는 배치를 열거한다. 각 배치를 새 engine에서 `reset_with_mines`와 `step`으로 재생해 공개 prefix의 중간·최종 관측을 대조한다. 일부 배치만 맞으면 POSTERIOR_MISMATCH로 거부한다. transcript가 없는 사례는 첫 유효 재생의 관측열을 기준으로 모든 배치의 동일성을 확인하며, 외부 중간 관측 기록이 있다는 뜻은 아니다.

`public_request`는 공개 관측·지뢰 수·공개 원장·mode·추측 설정·목표·Limits·prior만 받는다. 실제 배치, 실제 3BV, active/wasted 분리값은 평가기 영역에만 있다. `plan_trials`, `Budget`, `run_attempt`, `aggregate`가 실행과 집계를 담당한다. OK마다 입력 하나를 적용하고 FLAG 준비 중에도 새 관측과 원장으로 다시 계획한다. 기존 `stage4_planning`의 후보군·수식·한도·동률은 바꾸지 않았다.

결과는 WON / LOST / GUESS_BLOCKED / UNRESOLVED와 NOT_STARTED를 구분한다. 입력 비용 C는 prefix를 포함한 counted 합이다. WON의 X는 실제 전체 3BV/C, LOST와 GUESS_BLOCKED는 X=0, 미완료·미시작은 X=null이다. 미확정 질량을 분모에서 버리지 않으며 완전 평균은 null, coverage와 보수적 구간을 별도로 낸다. `observed_wins_only`는 관측된 승리만의 평균이다.

S/M의 E[X]는 **실패를 0으로 둔 무조건부 효용**이다. G009에서 M의 E[X]=1/2는 승리 확률 1/2 × 승리 시 X=1이며, 승리판 효율이 50%라는 뜻이 아니다. R은 명시 목표 τ의 도달 확률을 우선한다. τ=1, 6/5, 3/2는 비교용 값이며 추천 설정이 아니다.

처음 score는 준비 수순을 마친 뒤 재계획하는 선언 후보군의 값이다. 모든 배치와 후속 호출이 exact일 때만 실제 매 입력 재계획 주 목적과 비교한다. 부차 성분은 차이를 기록한다. 이번 MATCH를 일반적인 score 동등성이나 전역 최적성 증명으로 확대하지 않는다.

## 검증과 실제 결과

| 축 | 독립 확인 범위 |
| --- | --- |
| 신규 시험 | 등록·수집 17개, 실패·오류·skip 0. 기존 Unit 1 27개 및 Unit 2 18개와 별도 실행 |
| 준비 연속성 | 낮은 depth 3/5의 8개 사례, 28배치 모두 FLAG 1입력 후 DEPTH 미완료, 이후 추가 입력 0 |
| 기본 depth 12 대조 | 동일 28배치가 8 WON / 20 LOST로 종결, 8개 집계 MATCH |
| 유한 생성 | 550행: VALID 64 / DUPLICATE 191 / PREFIX_TERMINAL 193 / NO_PUBLIC_CHANGE 102. 독립 처분 대조 불일치 0 |
| 탐색 | 64개 공개 case × 3τ × 3mode = 576호출. OK 553, 2초 TIME 미완료 23 |
| 탐색 분류 | case·τ 192행: 엄격 차이 32 / 공통 선택 150 / 판단 불충분 10 / 단순 동률 차이 0 |
| 최종 비교 | 신규 case 27설정 + 연결 대조 9설정 = 36설정, 모두 MATCH |
| 최종 집계 | 계획 시도 123건: WON 64 / LOST 53 / GUESS_BLOCKED 6 / UNRESOLVED 0 / NOT_STARTED 0 |
| 독립 재생 | 고유 실제 정책 시도 174건 전부 재생. 관측·C·3BV·종단 일치, 전이 1,704회, 정책 트리 전개 0 |
| 공개 identity | 요청 ID 970건(시도 394 + 탐색 576), 요청 키 9개·원장 키 5개 확인 |
| 독립 주장 대조 | CROSSCHECK 58개 모두 MATCH |

최종 세 case는 등록 순서에 따라 G009 → G001 → G010으로 선택됐다. D는 2, 5, 5다. 탐색 후보는 작은 보드에서 목적에 맞게 고른 witness이며 대표 표본이 아니다. 2초 제한의 미완료 행은 보존했다. D≤8 적격의 앞선 선택에 해당 미완료가 없다는 독립 확인도 이 묶음에 한정된다.

| case·목표 | S E[X] | M E[X] | R E[X] | M의 목표 확률 | R의 목표 확률 |
| --- | --- | --- | --- | --- | --- |
| G009·1 | 2/5 | 1/2 | 1/2 | 1/2 | 1/2 |
| G001·1 | 12/35 | 12/35 | 1/5 | 0 | 1/5 |
| G010·6/5 | 7/15 | 7/15 | 23/60 | 0 | 1/5 |
| G010·3/2 | 7/15 | 7/15 | 1/3 | 0 | 1/5 |

G009의 S는 확정 안전 OPEN(3,0), M은 공동 생존 확률 1/2의 CHORD(3,1)를 선택한다. 최종 승률은 양쪽 1/2이고, 승리 시 X는 각각 4/5와 1이다. G001의 R은 첫 FLAG 생존 1과 뒤 CHORD 생존 1/5를 구분한다. G010·6/5에서는 최초 OPEN이 같지만 후속 공개 관측에서 R의 경로가 갈라진다. 탐색의 첫 수순 분류와 최종 실제 경로 분류는 별개다.

## 동결 전 완료 원시 재사용

**최종 123건 = 동결 후 신규 113건 + 동결 전 완료 원시 재사용 10건**이다. 다음 4설정은 동결 후 새 실행이 없고 전량 재사용이다.

- G001_R_tau1: 5/5, 연속성 기본 depth 12의 원시.
- two_ends_M_guessTrue: 2/2, 신규 평가기 실제 planner 시험의 원시.
- two_ends_M_guessFalse: 2/2, 같은 시험의 추측 OFF 원시.
- shared_flag_M_guessTrue: 1/1, 같은 시험의 원시.

10건 모두 source gzip hash·sequence, 전체 Trial·설정·배치·비용·공개 identity와 events를 제외한 Attempt가 일치한다. 제품/시험 bytes는 v01–v04에서 같으며, 독립 엔진 재생도 맞았다. fake·미완료·탐색 점수는 재사용하지 않았다.

원 지시의 완료 시도 재실행 금지를 A/B→D 단계까지 넓힌 해석은 batch 문맥보다 넓었으나, 동결과 표기·결속·결정성 근거로 한정 수용됐다. “신규 123건”, “36설정 모두 동결 후 실행”이라고 쓰지 않는다. 새 10회 재실행은 요구되지 않았다.

## 실행·보호와 보존할 결함

실제 호출 955 = A 7 + B 140 + C 576 + D 232다. 실제 정책 시도 174 = 신규 시험 5 + 연속성 56 + 최종 신규 113이다. 생성 550회의 엔진 prefix 재생과 원시 재사용 10건은 이 정책 시도 수에 더하지 않는다.

논리 시작 7회(실패 controller 포함), Python image 12개, 실제 시작 Job 6개다. 각 Job은 Python 2개와 conhost 1개, total=observed=3, active/member 0이며 reap·EOF·thread·handle 종료를 확인했다. run02·03은 자체 Job의 TerminateJobObject 분기를 탔고 관측 구성원 3개의 exitcode는 모두 0이었다. 독립 검토는 종료된 관측 구성원이 없음을 확인하고 실행계약 수용을 유지했다. 이 분기 발생은 기록에서 생략하지 않는다.

U3-H01은 첫 controller의 CIM 조회가 자체 신원 기록보다 먼저 실패한 공백이다. 코드상 Add-Type/Python/Job 생성 전이지만 PID·생성 시각은 기록되지 않았다. run01의 cleanup_verified/controller_absent는 **TOOL_REPORTED_EXIT_NOT_OS_VERIFIED**로 읽는다. 후속 성공으로 과거를 FIXED/PASS로 바꾸지 않는다. 원 R01 출력 잘림과 U3-H01의 고유 incident 2/9를 유지한다.

| 발견 | 마감 disposition |
| --- | --- |
| U3R-NB-01 | dict가 아닌 응답·status 누락·emit 실패 등은 UNRESOLVED 기록 대신 예외로 나갈 수 있음. 추가 입력/0점 치환은 없고 실제 경로에서 관측되지 않음. 코드 근거의 선택 보완으로 유지. fsync 없는 gzip flush를 OS 비정상 종료 내구성 보장으로 쓰지 않음 |
| U3R-NB-02 | aggregate는 전달받은 등록·Attempt를 신뢰함. 이번 52그룹은 독립 전수 열거와 원시 재생으로 완전성을 확인. 임의 외부 입력에 대한 일반 방어로 확대하지 않음 |
| U3R-NB-03 | CONTRADICTION은 배치 간 최초 score 불일치까지 포함하며 실제 발생 0. 키 집합 검사는 동어반복이고 실제 경계는 signature/DTO 검증. 의미를 명시하고 코드 유지 |
| U3R-NB-04 | 위의 재사용 10건·전량 재사용 4설정에 대한 주장 제한을 적용 |
| U3R-EV-01 / COORD-EV-01 | 원 구현자 manifest total_bytes=null 보존. 279파일 hash/bytes 일치, 조율·독립 합계 26,497,365 bytes를 별도 결속. 이후 manifest는 정수 합계 사용 |
| U3R-EV-02 | 예상 종료 UTC 두 값이 첫 tool보다 8·6시간 앞섰음. 실제 soft/hard/새 Python 금지/마감 예비 deadline은 정확했고 잘못된 예상값을 실행 결정에 쓰지 않았음. 원본 보존 |
| U3R-EV-03 | U3-H01의 tool 종료 주장과 OS 신원 검증을 구분. 영구 미확인 유지 |
| U3R-EV-04 | run02·03의 자체 Job 종료 호출과 관측 exitcode 0을 위에 기록. 재실행 없음 |
| U3R-EV-05 | tracked `results/stage3_replay_validation/final/REPLACEMENT_SELECTION.md`는 원 source340·보호 트리 밖. 당시/검토 Git 상태로 변경 없음이 확인됐으나 hash 보호로 소급하지 않음. 이번 문서 마감부터 전체 tracked 목록으로 별도 결속 |

독립 검토는 약 27분, 제품·helper 실행 및 Git/Desktop 쓰기 0이다. 원시 174시도와 생성 전이를 별도 Node 모델로 재생했으며 기존 정책 트리 검증은 반복하지 않았다. 검토자 종료 시각 한 항목은 정정 후 manifest를 다시 검증했다. 미노출 설정과 첫 시각 이전 전송 지연은 미확인이다.

## 근거와 다음 단계

evidence root는 `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_EVALUATION_UNIT3_2026-11-06`이다.

- `codex_01`: REPORT, 원시 gzip/실행 원장/동결 corpus. manifest SHA256 `7cfae73988bb56df0addac9d1954a36cb8184682d392dcf874696c2724f39ad0`, 279파일, 재계산 26,497,365 bytes(원 total_bytes=null).
- `coordinator_02`: 조율 산술·재사용 결속·MANIFEST_CHECK 및 검토 인계. 독립 검토를 대체하지 않는다.
- `review_claude_01`: REVIEW_REPORT, FINDINGS, CROSSCHECK, 보호·독립 원시. manifest SHA256 `a8632036aa4e19b4ad15b9235ab8cabc1dafc91128dc16890a707b55f54bdd86`, 자기 제외 32파일/378,491 bytes.
- 이번 문서·사용자 Git 준비: `STAGE4_UNIT3_CLOSEOUT_2026-11-07/coordinator_01`. source/tests 2 + 문서 6 = 8경로를 묶는다. 사용자 receipt 뒤 Desktop recovery는 별도 교체·검증한다.

추가 사용자 native 확인은 이번 순수 평가기 단위에 해당하지 않는다. Main/Live 화면·입력 통합이나 전시 노트북 동작 수용은 별도다. 다음은 일반 보드 지원에 필요한 계산 범위·근사 정책·검증 방법을 정한 뒤 화면 연결 순서를 설계하는 일이다. 현재 64칸/닫힘 8칸 제한을 조용히 넓히거나 Unit 4를 자동 실행하지 않는다.

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, V1 CLOSED/FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인을 유지한다. Phase2/R0-B/ActualE2, frozen 정책·Model C·holdout 2,010,000..2,010,099 및 금지 formal evidence는 미승인/미실행이다. F02 NOT_VERIFIED, 과거 Qt shared FileDialog FAIL, 이전 TEMP NOT_VERIFIED와 전시 노트북 PENDING도 그대로다.
