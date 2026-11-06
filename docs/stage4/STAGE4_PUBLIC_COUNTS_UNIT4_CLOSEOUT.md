# Stage 4 Unit 4 — 공개 관측 계수기의 한정 수용

작성: **2026-11-07 (Asia/Seoul)**. 공개 정보에서 정확한 배치 수와 공동 사건 확률을 계산하는 기반을 마감한다. 독립 판정은 **ACCEPT_BOUNDED, 필수 수정 0건**이다. 일반 상급판 전체의 실용성·안정적인 계산 시간·효율 향상 또는 전체 Stage 4 완료를 뜻하지 않는다.

## 권위와 변경 범위

실행 출발 HEAD는 **1cf5ea9af95e69c069d3137b733801a43819333e**다. 기존 source 342개를 보존하고 아래 3개를 추가해 현재 source는 345개다. 이후 문서 commit을 실행 HEAD로 소급하지 않는다.

| 신규 파일 | SHA256 |
| --- | --- |
| `stage4_belief.py` | `4a4f1c74ed5a314f95ca53bdd254ea7c31537ff0131ef7a8ea211142f33daac8` |
| `tests/test_stage4_belief.py` | `9daa8bb8eade8ecf0a4d4b74ecced4e28c8febabaa8297456ba22c87a5278a68` |
| `tests/stage4_belief_oracle.py` | `de6360c1774a5978e92dabf0cb778cadff3fbb9146341b68485cd5047d85a07b` |

구현자 **COMPLETE_BOUNDED_PUBLIC_COUNTS**를 등록된 범위에서 수용한다. 제품/API·정확 산술·등록된 실제 6관측·evidence/helper는 ACCEPT, 한도·취소·원자성은 ACCEPT_BOUNDED, 실행계약은 비차단 기록 1건을 둔 ACCEPT다. 비차단 5건과 미확인 5건은 아래에 별도로 보존한다. [Unit 1·2 기반](STAGE4_OPENING_PLANNING_FOUNDATION_CLOSEOUT.md) 및 [Unit 3 평가기](STAGE4_EVALUATION_UNIT3_CLOSEOUT.md)의 판정·PARTIAL·공백을 바꾸지 않는다.

## 공개 입력과 정확한 계수

`count_public(BeliefRequest, cancelled=...)`는 공개 숫자·물리 깃발·전체 지뢰 수·공동 사건·자원 한도·prior ID만 받는다. 실제 배치, seed, 실제 3BV, active/wasted 분리 카운터, 미래 Replay 입력과 시각은 받지 않는다. 물리 FLAG는 요청 identity에는 남지만 추론에서는 미지수다. 지뢰 수에서 깃발 개수를 빼지 않는다.

- **D**: 현재 공개 관측과 일치하는 전체 배치 수.
- **M(x)**: 그중 닫힌 칸 x가 지뢰인 배치 수. 물리 깃발도 대상이다.
- **W(S,T)**: S의 모든 칸이 안전하고 T의 모든 칸이 지뢰인 공동 사건의 배치 수. 확률은 W/D이며 주변확률을 곱해 만들지 않는다.

숫자 제약으로 연결된 component의 정수 histogram을 만들고, prefix/suffix 합성곱과 비제약 칸의 조합 수로 전역 지뢰 수를 반영한다. 전체 보드 배치나 component 배치의 곱집합을 만들지 않는다. 표본 추정·전역 캐시·이전 요청의 상태 재사용은 없다. 정수와 Fraction은 손실 없는 십진 문자열로 기록한다.

`zero_event`는 중심과 이웃의 공동 안전 사건이다. `existing_chord_event`는 실제 물리 깃발 수가 양수 clue와 같고 HIDDEN 대상이 있는 CHORD만 반환한다. 비활성 CHORD는 빈 사건 대신 **None**이므로 후속 소비자는 이를 구분해야 한다. 칸·사건은 중복을 없애고 정준 순서로 정렬한다. 열린 칸의 safe 조건은 계수에 영향을 주지 않지만 identity에는 남는다.

D=0인 모순 입력과, D>0에서 W=0인 불가능 사건을 구분한다. 빈 사건은 W=D다. S/T 겹침 또는 열린 칸을 지뢰로 요구한 사건은 유효한 base에서 W=0이다. 이 모듈에는 action·경로·E[X]·목표 도달 확률이 없으며 기존 계획기·Main/Live에 연결하지 않았다.

## 한도·취소·미완료

상한은 **480칸, 정준 사건 16개, work 200,000, 협력 시간 2초**다. 사용자는 0을 포함해 한도를 낮출 수 있다. 변수값 시도 1회와 DP 정수항 곱셈 1회가 각각 work 1이며, 하나의 요청 예산을 base와 모든 사건이 공유한다. 열거·DP 안과 단계 경계에서 시간·취소를 확인한다.

base 전체가 완료되기 전에는 D/M을 공개하지 않는다. base 완료 뒤 사건이 중단되면 **PARTIAL**로 exact base와 이미 완료된 사건만 보존한다. 중단된 W/확률은 null, 이후 사건은 NOT_EVALUATED다. 미완료를 0이나 불가능 사건으로 바꾸지 않는다. callback 예외·비-bool 반환은 ERROR다. cells/events 한도 0은 UNSUPPORTED, work/time 한도 0은 INSUFFICIENT로 처리한다.

이 시간 한도는 **실시간 응답 상한이 아니다**. 현재 실행 환경 CPython 3.12.10/Windows의 `time.monotonic`은 약 15.6 ms 단위다. checkpoint elapsed 0.0은 계산 시간 0이 아니다. 요청 생성·정준화와 결과 직렬화는 호출 밖이며, identity 계산·UNSUPPORTED 반환·일부 Fraction/조합 수 계산에는 중간 checkpoint가 없다. publish 단계 종료 검사는 원자성을 지키지만 그 단계 내부를 즉시 중단하지는 않는다. 이후 더 세밀한 지연이나 실시간 상한을 주장하려면 별도 설계·측정이 필요하다.

## 등록 검증과 독립 재계산

새 시험은 **A 17개(run02) + B 4개(run04) = 고유 21개**다. 같은 source bytes에서 별도 실행했으며 단일 21개 실행이나 기존 Unit 1~3 suite와 합친 결과로 쓰지 않는다. 실패·오류·skip은 0이다.

| 근거 | 독립 확인 |
| --- | --- |
| 작은 oracle | 공개 관측 32개, 전체 bitmask 13,627개, 사건 354개. 정상 28/모순 4, D/M/W 모두 일치 |
| 분석해 | 7요청·사건 22개. 세 크기 all-HIDDEN, 70개의 두 칸 component, 가변 component와 비제약 칸, 물리 FLAG 변형, CHORD 공동 안전 1/8을 정확한 정수·다항식으로 재계산 |
| 실제 Replay 공개 관측 | 첫 128입력만 재구성한 0/1/32/64/96/128 시점 6개, D 6개·닫힌 칸 M 1,956개·사건 W 37개 모두 일치 |
| 두 번째 M 경로 | component 칸 346개의 M을 강제 재열거로 다시 계산, 불일치 0 |
| 공개 identity | 정상 DTO 요청 75/75를 공개 필드만으로 재계산해 일치 |
| 전체 요청 처분 | 77요청: COMPLETE 52 / INCONSISTENT_INPUT 4 / INSUFFICIENT 4 / PARTIAL 4 / CANCELLED 3 / ERROR 3 / UNSUPPORTED 5 / 형식 예외 2 |

독립 검토는 제품·구현자·조율 helper를 실행하지 않고 별도 Node의 engine 의미·union-find component·BFS 변수 순서·생성다항식·재열거를 사용했다. 전체 2^480 열거는 하지 않았다. 6관측에 NOT_INDEPENDENTLY_RECOUNTED로 남은 항목은 없다.

원 Replay는 `replay_20261106_121528.json`, SHA256 `c58beda2f53e38709ea596afa3c7c07478ad6482a48bcf324bf6d4a1bc6131c1`다. 총 158입력 중 128개만 적용했고 이후 30개는 사용하지 않았다. 관측 재구성에만 평가자가 실제 배치를 썼으며, 계수기에는 공개 관측만 전달했다. 128입력 뒤 상태는 PLAYING이다. 이는 새 정책의 완주나 효율 평가가 아니다.

**EXACT 37개는 W=0 19개 / W=D 7개 / 중간 확률 11개**다. 입력 32 이후에는 관측마다 중간 확률 사건이 1개뿐이다. 등록된 계수의 정확성 근거이며, 큰 frontier에서 어려운 공동 사건의 계산 비용이나 일반 상급판 전체 지원의 근거로 확대하지 않는다.

## 비차단·미확인 disposition

| 발견 | 마감 처리 |
| --- | --- |
| RV4-N1 예상 UTC 오류 | 동결 RUN_PLAN의 예상 종료는 2026-11-06 **07:33:42Z / 09:33:42Z**로, 실제 시작 15:33:42.3899819Z보다 앞선다. 시작+1/+3시간의 올바른 값은 **16:33:42.3899819Z / 18:33:42.3899819Z**다. 보고서는 올바른 값만 적고 원시 오류를 밝히지 않았다. 이 기록 불일치를 여기 명시하며 원본은 수정하지 않는다. soft/hard/새 Python 금지/마감 예비 시각은 정확하고 결과에는 영향이 없다. 원인이 현지시각 중복 변환인지는 UNCONFIRMED이며, 다음 계획은 명시적인 UTC 시작값에서 산술 계산한다 |
| RV4-N2 시계 해상도 | 위의 약 15.6 ms 단위와 elapsed 0의 의미를 명시. sub-20 ms 정밀도나 안정 시간은 주장하지 않으며 v0.1 source는 유지 |
| RV4-N3 사건 구성 | 위의 19/7/11 분포와 비초기 정보성 사건 수를 함께 기록. 어려운 큰 frontier 비용 근거로 쓰지 않음 |
| RV4-N4 oracle 구성 의존 | A oracle은 생산 모듈이 만든 정준 사건에서 계수만 독립 비교. 독립 검토가 32개 사건 목록과 Replay 질의를 따로 재도출해 일치를 확인했으므로 이번 범위의 필수 보완 없음 |
| RV4-N5 비중단 구간 | 요청 생성·identity·일부 publish·직렬화의 범위를 위에 명시. 현재 계약 내이며 실시간 보장 없음. 이후 필요할 때 별도 보완 |

미확인 5건은 별도로 유지한다: **RV4-U1** run01의 정확한 OS 거절 원인, **U2** run04 TerminateJobObject 호출 사유, **U3** 구현자의 실제 모델·강도·속도, **U4** U4-R01 표시 잘림의 원시 부재, **U5** 일반 상급판 지원·안정 시간·효율/승률·전시 노트북 성능(판정 범위 밖). 비차단 항목 전체를 FIXED/CLOSED로 바꾸지 않는다.

## 실패·실행·보호 기록

논리 시작은 **5/6**, Python image는 **7/12**, 실제 Job은 4개다. run01 bootstrap은 image 1에서 exit 101, run02는 image 2/A, run03은 Python 시작 전 launcher 실패/image 0, run04는 image 2/B, run05는 image 2/C다. 신규 3파일은 v01/v02/v03에서 동일하며 launch.ps1만 보정됐다.

각 Job의 suspended 생성→할당·소속 확인→resume 1회, total=observed, active/member 0, reap·EOF·thread·handle 종료가 확인됐다. run01은 ready-parent map이 없지만 native PID·생성 시각·소속·종료 기록은 있다. run04는 TerminateJobObject를 호출했으며 종료된 process 수는 0, 관측 exitcode는 0/0/0이다. 호출 사유와 OS 전체의 정리를 추정하지 않는다.

U4-R01 표시 잘림, U4-H01 bootstrap, U4-H02 없는 summary 참조의 **고유 incident 3/9**, 읽기 보정 1/3·helper 보정 2/2·제품 보정 0/4를 보존한다. 독립 검토의 별도 RVI-01은 run05에 없는 tests.jsonl을 읽은 도구 오류이며 실패본을 남기고 한 번 보정했다(보정 1/2, incident 1/4). 두 원장을 합치지 않는다.

START6/END6 Git 읽기 전후 index SHA256 `857679b09d300b1521c48fa2c030a7ad66c86f827eba018cd65f353b29eee4ef`가 같았다. source342·현재345·tracked413·문서48·Desktop 등 보호 대상이 일치했다. 조율의 문서 마감에서도 제품 source/tests·원시 evidence는 바꾸지 않고 source345와 전체 tracked를 다시 결속했다.

## 근거와 다음 순서

외부 evidence root: `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_GENERAL_BOARD_BELIEF_UNIT4_2026-11-07`.

- `coordinator_01`: 계약·분석해·실행 예산. 자동 실행 지시가 아니다.
- `codex_01`: REPORT, API_PLAN, RUN_PLAN, 원시 요청·결과·실행 원장. manifest **241파일 / 4,597,957 bytes**, SHA256 `1696bbddbd5900c2b04ec29726dd5c4c9b3a3be5ad0c7784e933115d2afa7b6b`.
- `coordinator_02`: 작은/분석해 재계산과 검토 입력 결속. 큰 6관측의 독립 재계산은 후속 Claude 근거와 구분한다.
- `review_claude_01`: REVIEW_REPORT, FINDINGS, CROSSCHECK, 독립 원시. manifest **24파일 / 279,068 bytes**, SHA256 `a27cbe9db78843af1aa55aef069b8b7595f6ad371db62ae87444bdf074932d10`.
- 문서·사용자 Git 준비: `STAGE4_UNIT4_CLOSEOUT_2026-11-07/coordinator_01`. **신규 source/tests 3 + 문서 6 = 9경로**를 묶는다. 사용자 commit/push receipt 검증 뒤 Desktop recovery 2개를 별도 교체·검증한다.

UI/Live 입력 변경이 없는 독립 계수기 단위이므로 추가 사용자 native는 해당하지 않는다. 다음은 이 계수를 사용하는 후보의 안전성·오프닝·CHORD 전체 입력 비용 비교와 계산 부족 반환, 검증 범위를 먼저 정하는 일이다. 국소 순위 점수를 Unit 2의 정확한 최종 E[X]나 R의 목표 도달 확률로 부르지 않는다. 근사 정책·UI/worker 통합·일반 효율 평가는 후속 계약과 별도 실행 범위다.

Unit 2 C01/H01, Unit 3 U3-H01과 과거 실패를 소급 변경하지 않는다. D0–D5 CLOSED/FINAL ACCEPTANCE PASS, V1 CLOSED/FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인을 유지한다. Phase2/R0-B/ActualE2, frozen 정책·Model C·holdout 2,010,000..2,010,099 및 금지 formal evidence는 미승인/미실행이다. F02 NOT_VERIFIED·과거 Qt shared FileDialog FAIL·이전 TEMP NOT_VERIFIED와 전시 노트북 PENDING도 그대로다.
