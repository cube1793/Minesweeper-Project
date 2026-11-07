# Stage 4 효율 실험 Units 12–17 마감

## 현재 판정

Unit15 기준선, Unit16 공개 진단과 Unit17 후보의 묶음 독립 검토를 2026-11-08에 마쳤다. 후보 수학은 PASS, 실행·보호는 PASS이며 최종 driver 요약의 PARTIAL을 유지한다. 제한 성과는 MIXED이며 후보는 미채택이다. 필수 제품 수정은0, 향후 driver 재사용 전 helper 보완 H1은1건이다.

제품 source는 Unit11의 ae88e5e8c6c13cff735a2cf9a55d33c9c17746fc와 같은365개다. 이번 기록 마감은 문서만 변경한다. 기본 UNIT4_LEGACY와 명시적 UNIT10_SUMMED, 기존 화면과 실행 경계를 유지한다. 실전 효율과 Stage4 전체 완료는 미확립이다.

## 이전 제한 실험 계보

- Unit12는 Q/G 비용 진단의 PARTIAL이다. 기록 work 선과금 누락을 포함한 원 사건과 후보 미반영을 유지한다.
- Unit13은 같은 보드128입력 이후 Q와 S/M/R의 제한 연속 실행이다. 전체 C는 Q157/S158/M157/R157이며 모두 승리했다. 원 PARTIAL과 후보 미채택을 유지한다.
- Unit14는32입력 이후 Q와 안전 FLAG→CHORD 대안을 비교했다. 두 경로 모두 WON/C156이며 절약 입력0이다. 이들 기록은 Unit15–17 독립 검토의 별도 수용 대상으로 합치지 않는다.

## Unit15 전체 판 기준선

해시 규칙으로 먼저 등록한 상급30×16·99지뢰 개발판 E01–E04를 일반 첫 OPEN(0,0)부터 Q로 진행했다. 첫 입력을 C에 포함했다. 결과는 E01 WON/C163/3BV167, E02 WON/C174/3BV177, E03 LOST/C3, E04 LOST/C2다. 전체342입력·Q288회·counter33회이며 기준선의 반복 실행은 없다.

## Unit16 확정0 진단

완주판에서 나중에 열린 오프닝 경계의 이전 OPEN20개를 사후 선택했다. D01은 첫 실행의 저장 결과를 재사용했고19개를 새로 계수했다.20개 모두 COMPLETE이며 확정0은 없다. 누적20회·239235 units이고 후보 구현/네 판 비교는 NOT_TRIGGERED다. 해당20곳에서0을 먼저 확정할 근거가 없었다는 제한 진단이며, 모든 이전 입력이 필수였다는 판정은 아니다.

원 codex_01의 Git global ignore 접근 거절과 codex_02의 evaluator 실패를 PARTIAL로 보존한다. 후속 실행에서는 비입력 행 필터와 outer COMPLETE/inner EXACT, FLAG 토글 처리를 offline gate에서 확인했다. 호출 전후 회계와 기존 결과 재사용을 구분한다.

## Unit17 후보 수학

후보 SAFE_FIRST_LAYER_BOUND_PER_INPUT_V1은 안전 표적 t의0확률 하한을 L(t)=max(0,D−Σ이웃M)/D로 계산한다. 직접 표적 T와 그 밖의 미개방 이웃 U에 대해 gain=|T|+Σ_U max인접L을 계산하고 준비 FLAG·해제를 포함한 원자 입력 수로 나눈다. U의 중복은 한 번만 센다. 후보군은 원 Q 수순과 안전한 단일 OPEN이며 동점에서 원 Q가 우선이다.

독립 검토는 A의17개 안전 상태/204 catalogue 항목과 나머지3개 추측 유지, D333결정/4736항목을 BigInt로 재현했다. 자체 oracle87419수순에서 하한 위반0이다. 이 보장은 계획한 수순 전체를 실행할 때의 즉시 공개 칸 기대값 하한이다. 최종 E[X], IOE, 실제 입력 절약량으로 확대하지 않는다. D01의(0,9)에서39/62–101/124는 주변확률에서 얻은 범위다.

## 실제 성과와 비용

| 판 | 기준선 C | 후보 C | 결과 | 후보 IOE |
| --- | ---: | ---: | --- | --- |
| E01 | 163 | 157 | WON | 167/157 |
| E02 | 174 | 175 | WON | 177/175 |
| E03 | 3 | 3 | LOST | — |
| E04 | 2 | 2 | LOST | — |

전체 C는342→337, 합계5 감소다. 그러나 기존 승리판 각각의 C 비증가 조건에서 E02가1 증가하므로 동결 기준은 미충족이며 MIXED/미채택이다. 후보 수학의 정확성과 채택 판단을 분리한다.

기준선은 macro 완료 후, 후보는 원자 입력마다 Q를 호출했다. 독립 검토에서37개의 다중 입력 제안은44개 중간 결정 모두 원래 꼬리로 이어졌다. 이번 기록의 행동 차이는 override28회와 이후 경로 분기에서 발생했다. 이 수순 지속은 일반 보장이 아니다.

counter는33회/377125 units에서333회/3882284 units로 늘었다. 순수 wall은 약3배이며 기준선과 후보는 서로 다른 실행 시점이다. 쌍 타이밍 측정으로 표기하지 않는다. 추가 비용을 채택 판단과 함께 보존한다.

## 실행과 남은 보완

두 Job은 suspended 생성, 할당/소속 확인,1회 resume와 release 이후 실행을 거쳤고 최종 member/active0과 handle 종료를 확인했다. host binary는 승인 controller가 각 START 직전에 검증한 과거 기록이다. 검토 시점의 host 파일 해시를 새로 읽은 값은 없다.

최종 run02에서 Fraction을 plain json.dump로 저장하다 실패했다. 그 전에 CD_RESULTS.json과 네 판 원시가 저장됐고 독립 엔진679입력과 조율 수치42개가 모두 일치했다. 성공 phase_result와 exit0을 소급 생성하지 않는다.

H1은 driver 재사용 전에 Fraction-safe 변환을 적용하고 Fraction·중첩 dataclass·2^53 초과 정수를 작은 시험으로 확인하는 것이다. 이 보완은 아직 PENDING이다. 완료된 네 판과20개 계수의 재실행은 필요 없다. N1–N6, U1–U7은 원 FINDINGS와 함께 보존한다. Fast OFF와 프로세스 수준 새 세션 여부는 UNCONFIRMED다.

## 근거 위치

- Unit15: C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_EXPERT_Q_BASELINE_UNIT15_2026-11-08
- Unit16: C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_OPENING_POLICY_BUNDLE_UNIT16_2026-11-08
- Unit17 구현·검토: C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_SAFE_OPENING_VALUE_UNIT17_2026-11-08
- 독립 보고서: review_claude_01/REVIEW_REPORT_KO.md, FINDINGS.json, CROSSCHECK.json, OUTPUT_MANIFEST.json
- 독립 manifest SHA256: 1a6b70cea9bc8b181570f1f7b28e67d5a40dea5c0202f9dd4071b25ca464fd07

## 다음 범위

H1을 다음 실행 준비에 묶어 보완한 뒤, 공유 FLAG·겹치는 CHORD를 포함하는 복합 수순의 총비용을 검토한다. 새 후보의 실제 전체 입력 개선은 별도 등록 비교로 확인한다. S/M/R 일반 상급판 평가, 메인 UI/worker 통합, 사용자/전시 노트북 수용은 후속이다. 모든 기존 frozen 정책·Model C·holdout·연구 승인 경계를 유지한다.
