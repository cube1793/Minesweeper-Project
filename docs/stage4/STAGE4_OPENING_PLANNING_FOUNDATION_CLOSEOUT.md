# Stage 4 오프닝·계획 기반 한정 수용

작성: 2026-11-06, Asia/Seoul. 이 문서는 Unit 1과 Unit 2의 구현·독립 검토 범위를 마감한다. 전체 Stage 4 완료, 일반 효율 개선, 세계기록, Main/UI/native 수용은 선언하지 않는다.

## 권위와 구현 범위

실행 출발 HEAD는 **dc740e222c2b913fa1697fba0f4785cfffc37c2c**다. Unit 1은 source 335개를 보존하며 2개를 추가했고, Unit 2는 그 337개를 보존하며 3개를 추가했다. 현재 source는 340개다. 이후 문서/commit을 해당 실행 HEAD로 소급하지 않는다.

| 단위 | 신규 경로 | 판정 |
| --- | --- | --- |
| Unit 1 | `stage4_opening.py`, `tests/test_stage4_opening.py` | ACCEPT_BOUNDED |
| Unit 2 | `stage4_planning.py`, `tests/test_stage4_planning.py`, `tests/stage4_planning_oracle.py` | A/B ACCEPT_BOUNDED, D ACCEPT_BOUNDED_WITH_C01_RETAINED |

Unit 2 구현자의 **PARTIAL**은 최초 Git 조회 전 샘플과 개별 원본 stream 누락(C01)을 포함한 역사다. 이후 독립 수용은 제품/근거의 범위를 따로 판단한 것으로, 과거 PARTIAL을 PASS로 고쳐 쓰지 않는다.

## 사용자 목적과 공개 정보

목적은 제한된 공개 정보에서 최종 Efficiency/IOE를 높이는 것이다. 현재 UI의 Efficiency와 IOE는 completed 3BV / 총 입력 C의 백분율·소수 표현이다. 속도·이동 거리·Model C 비용은 Stage 4 선택 점수에 넣지 않는다.

정책 C는 공개 입력 원장의 counted 합이다. 원장 항목은 action·좌표·counted·공개 관측 ID만 포함한다. 실제 배치·seed·BoardSnapshot·active/wasted 분리값·진행 3BV/ops·ZiNi·숨은 칸 분류는 정책 인자/키/trace에 주지 않는다. 가상 세계는 공개 숫자와 전체 지뢰 수를 만족하는 배치에서 균등하게 생성한다.

물리 FLAGGED는 추론 사본에서 HIDDEN으로 취급하며, 실제 깃발의 입력 비용은 별도로 보존한다. Unit 1의 D/M/Z는 정확한 정수이고, Z는 후보와 보드 안 이웃이 모두 안전한 공동 사건이다. 높은 Pzero를 전체 최적 행동이라고 부르지 않는다.

## 세 방식과 수순 값

- S: 안전 진행이 있으면 위험을 늘리지 않고 E[X]를 최대화한다. 불가피한 추측에서는 HIDDEN+FLAGGED 전체의 최소 위험 OPEN을 비교하고 깃발 해제 비용도 센다.
- M: 추측 설정 안에서 완주 성과 E[X]를 최대화한다.
- R: 명시적 목표 τ에 대해 P(WON이고 IOE ≥ τ)를 최대화한다. 목표를 임의로 기본 설정하지 않는다.

X는 WON의 전체 3BV / 최종 C다. LOST와 추측 OFF의 GUESS_BLOCKED는 X=0이며 별도 집계한다. 이 효용식은 사용자 목표를 구체화한 조율 계약으로, 사용자가 수식까지 직접 지정했다고 쓰지 않는다. 추측 OFF에서 안전 칸이 남으면 계속 진행하고, 없음을 정확히 확인한 뒤 DEFER/GUESS_DISABLED로 멈춘다. 자원 부족은 INSUFFICIENT/UNRESOLVED이며 막힘이나 패배로 위장하지 않는다.

후보군 `progress_preparations_v1`은 직접 OPEN/깃발 해제 OPEN, 기존 유효 CHORD, 2칸 이상을 여는 CHORD의 정준 순서 FLAG 준비를 비교한다. 각 원자 입력은 비용/깊이 1이다. 공유 깃발과 자동 오프닝 확장을 반영한다. 편집이 필요한 1대상 CHORD·비정준 준비 순열 등은 제외한다. exact는 이 선언 후보군 안의 의미다.

가상 전이 후 동일한 공개 결과를 묶어 공통 다음 행동을 고른다. 실제 반환은 첫 원자 입력 하나이며 호출자는 다음 공개 관측에서 다시 계획한다. 수순 score는 준비 수순을 마친 뒤 재계획하는 후보군 값이다. **모든 후속 호출이 exact일 때**, 매 입력 재계획 정책의 주 목적값에 대한 하한이다. 일반적 동등성과 부차 성분의 일치는 미증명이다. 등록된 45시도 및 검토 모델의 FLAG 시작 180건에서는 다섯 성분이 같았다.

## 지원 한도와 미통합 상태

전체 64칸, 닫힘/깃발 8칸, 일관 배치 256개, 원자 입력 깊이 12, 전개 노드 50,000개, 호출 10초다. 현재 8칸 이하에서 배치 수는 최대 C(8,4)=70이므로 256 상한은 기본 조건에서 걸리지 않는다. 잘못된 타입/필드는 거부하고, 모순·추론 오류·지원 밖·자원 부족을 구분한다.

Main/Live 실행, worker/ACK/permit, 메뉴, Replay 및 native 화면은 연결하거나 변경하지 않았다. 이번 단위의 추가 사용자 native 수용은 해당하지 않는다. 일반 상급 보드는 현재 계획기의 지원 범위를 넘는다.

## 검증과 독립 재현

| 근거 | 확인 범위 |
| --- | --- |
| Unit 1 | 테스트 27개, 공개 관측 24개(정상 21/모순 3), D/M/Z 86행, 큰 정수 조합식 4개 |
| Unit 1 실제 엔진 예제 | 공통 prefix를 포함해 3입력 대 4입력, 양쪽 WON 및 3BV 2 |
| Unit 2 최종 run03 | 등록·수집·실행 18개, 실패/오류/skip 0 |
| Unit 2 독립 oracle | 7상태 × 3방식 = 21건, 첫 입력·점수 5성분·첫 후보 전체 점수/생존 일치 |
| Unit 2 주입 전이 | 1,017건: 결과 관측·종단·counted·active/wasted·완료 3BV/ops·전체 3BV·관측 ID 일치 |
| Unit 2 실제 경로 | 가능한 배치 15개 × 3방식 = 45시도: WON 27 / LOST 12 / GUESS_BLOCKED 6 / UNRESOLVED 0 |
| Unit 2 공개 실행 | 150건의 identity, 정상 137건의 선택/점수/후보/D/M/Z, 미완료·오류 13건의 null 반환 대조 |

Unit 1 27개, Unit 2 run02의 16개와 최종 run03의 18개를 단일 suite로 합산하지 않는다. 1,017 전이는 `_revealed/_flagged`를 주입한 단일 단계이며 도달 불가능한 상태도 포함한다. 실제 공개 prefix에서 이어 간 근거는 별도 45시도다. oracle과 검토 모델은 선언 후보군의 의미를 공유하므로 일치는 전체 정책 최적성의 증명이 아니다.

## 실패·실행·C01

Unit 1은 논리 Python 시작 2회/관측 image 3개, run01 bootstrap exit 101과 초기 preflight PID 미기록을 보존한다. helper 보정 2/2, 읽기/명령 2/2, 고유 incident 4/4, raw event 5다.

Unit 2는 논리 시작 3회/관측 image 5개(1+2+2)다. run01은 exit 101/user code 0, run02는 같은 v1 bytes의 승인 재시도, run03은 제품/오라클 bytes를 유지하고 테스트를 보강한 v2다. 각 Job total은 2/3/3, active/member 0, 정리 필드 19개가 모두 true이며 controller 종료를 확인했다. PowerShell/compiler는 Job 밖의 기록된 신뢰 경계다.

C01은 최초 `git status` 직전 index 샘플과 개별 stdout/stderr 원본이 없다는 **영구 기록 공백**이다. 대화 발췌와 이후 일치 hash를 보존하지만 누락된 과거 샘플로 대체하지 않는다. FIXED나 과거 PASS로 변경하지 않는다. 같은 bytes로 다시 쓰였는지도 미확인이다. 현재 bytes·index·보호 자료의 독립 대조를 근거로 다음 개발은 가능하다.

H01 마감 OrderedDictionary 집계 오류, P01 bootstrap 실패, W01 ignore 접근 경고를 보존한다. 경고는 guarded stderr 6줄+transcript 2줄이며 C01.raw_warning_count=0 표기는 원본의 불일치로 남긴다. 600.9580077초는 보수적인 21:44 KST 기준이고 실제 최초 tool 시작은 미확인이다.

## Unit 2 비차단 권고의 disposition

| ID | 이번 처리와 이후 범위 |
| --- | --- |
| U2R-NB-01 | 이 문서에 score의 후보군 의미/조건부 하한/일반 동등성 미증명을 반영. 알고리즘 변경 없음 |
| U2R-NB-02 | 다음 평가 harness에서 준비 도중 미완료를 UNRESOLVED로 집계. 낮춘 깊이 3/5의 검토 모델 8건이며 제품/기본 12에서는 미확인. 수순 유지·다음 상태 사전 점검은 선택 설계로 남김 |
| U2R-NB-03 | 생존 동률은 첫 원자 입력 기준이라고 명시. FLAG 준비는 1을 받을 수 있음. 계약 변경 없음 |
| U2R-NB-04 | 부분 trace는 진단용이며 INSUFFICIENT의 행동/전체 점수 근거로 사용하지 않음 |
| U2R-NB-05 | 제외 CHORD의 노드별 개별 기록은 없음. 후보군 선언을 유지하고 추가 추적은 필요 시 후속 |
| U2R-NB-06 | 배치 상한의 비활성 범위와 C=0인 이미 WON 입력의 ERROR를 기록. 실제 플레이 도달 불가, 코드 변경 없음 |
| U2R-EV-01 | C01 경고 수 불일치를 위 역사에 기록. 원 파일을 덮어쓰지 않음 |
| U2R-EV-02 | 공유 가정과 주입 전이/실제 경로를 분리해 서술 |
| U2R-EV-03 | registration 신규 3항목의 relative_path 부재를 보존. path/hash는 일치, 필수 수정 아님 |

6개 미확인은 별도로 유지한다: 검토 Fast 설정, 구현자 실제 첫 tool 시각, exit 101의 OS 원인, 노드/경과 및 일부 테스트-only 단정의 독립 미재계산, 일반적 재계획 동등성·기본 한도 연속성, C01 동일 bytes 재작성 여부. Unit 1의 이전 비차단·미확인과 더 오래된 실패도 이 수용으로 일괄 CLOSED하지 않는다.

## 원시 자료와 해시

로컬 evidence는 `C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs` 아래에 있다. 제품 repository로 복사하지 않는다.

- Unit 1 구현: `STAGE4_OPENING_FOUNDATION_UNIT1_2026-11-06/codex_01`, manifest `5930f0423960aeb3b3bb4ddab6893208db29662f6f5c6002606ed67573219944`.
- Unit 1/설계 검토: `STAGE4_UNIT1_REVIEW_UNIT2_CONTRACT_2026-11-06/review_claude_01`, manifest `16004e0d42ca43e4752d73955108e64fa6f70d7a34a50c74e974986a0727a5e5`.
- v0.2 변경분 검토: 같은 root의 `review_claude_02`, manifest `afe60d69232e50cd7c5a9ffeed36788d721776a571fc41b9819cb07d3d2fef8f`.
- Unit 2 구현: `STAGE4_PLANNING_UNIT2_2026-11-06/codex_01`, manifest `c311a627c4f72f8209dce1e606d6cc7475062d14e5603ca90e3834a308e7ffc9`.
- Unit 2 독립 검토: 같은 root의 `review_claude_01`, manifest `ea7bd050d729ff250ada153e22a598acd5dd6be9ceda8abd58afebb9317036eb`, 자기 제외 15파일/255,999 bytes.

## 마감과 다음 범위

신규 source/tests 5개와 문서 6개, 총 11경로를 묶어 사용자 commit/push를 준비한다. 이 문서의 실행 HEAD는 위의 dc740e2이며 최종 Git/recovery 권위는 실제 receipt와 live 상태다. postcommit 문구만을 위한 추가 commit은 만들지 않는다.

다음 구현은 Main 연결 전 평가 harness를 우선한다. 비교 상태/시도 수를 사전 고정하고 WON/LOST/GUESS_BLOCKED/UNRESOLVED, 후보 수순 score/실제 재계획 결과를 분리한다. 아직 일반 상급판 지원, Main 메뉴 또는 고점 기록을 약속하지 않는다.

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, V1 CLOSED/FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인이다. F02 NOT_VERIFIED, 과거 Qt shared FileDialog FAIL, 이전 TEMP NOT_VERIFIED를 유지한다. Phase2/R0-B/ActualE2, frozen 정책·Model C·holdout 2,010,000..2,010,099 및 금지 formal evidence는 열지 않는다.
