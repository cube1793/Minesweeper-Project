# Stage4 N1·FA1-K 반영과 S/M/R 평가 — Units69–74

기준일: **2026-11-15 (Asia/Seoul)**. 현재 제품 반영 커밋은
`8fc12f39a6dcfb8a5326943f089ab42bc7b2f84c`다. 이 문서는 기존 결과와 수용 기록을
연결한 문서 갱신이며, 새 실험·제품 변경·실행 승인을 뜻하지 않는다.

## 현재 결론

- N1의 입력 전후 검증 비용 절감과 FA1-K의 동률 선택 개선은 Unit73에서 제품에 반영됐고 커밋·푸시됐다.
- Unit72의 F_ONLY 새 100판에서는 공동 승리 46판의 평균 효율이 **104.196697% → 108.361795%**였다.
- Unit74는 UI 설정에 맞춘 S/M/R **54보드 × 6조건 = 324판**을 평가했다. S의 표본 내 입력 개선은 확인됐지만 M/R은 승패 변화도 함께 보고해야 한다.
- Stage4 관련 **14모듈·187시험**은 사본(Unit73)과 설치본(Unit74)에서 각각 통과했다. **전체 소스 회귀는 `FAILED_UNRESOLVED`**다.
- 다음 우선순위는 현재 앱으로 녹화본 확보다. 평균 120%는 중간 이정표이며 평균·고점 개선의 상한이 아니다.

## 1. 버전과 용어

Unit37 문서 마감 기준은 `34eabd17d576d61262d782d7362a40157a0267a0`다.
그 이후의 조사·사본 실험·하네스 보완을 모두 제품 변경으로 세지 않는다.
현재 반영 커밋 `8fc12f3`의 부모가 이 Unit37 커밋이며, 변경은 제품 5파일,
시험의 식별자 단언 2파일, `ARCHITECTURE.md`의 기록 1파일이다.
Units38–68의 모든 실험을 이 문서에서 새로 수용하거나 종료했다고 선언하지 않는다.
당시의 실패·미채택·미확인 상태는 각 봉인 기록에 남는다.

| 이름 | 의미 | 현재 제품과의 관계 |
|---|---|---|
| N1 | `consistent()`에서 한 호출 동안 이웃 관계표를 재사용하는 변경 | 반영됨 |
| FA1-K | 공개 정보로 계산한 깃발 재사용 항을 안전 후보의 동률 정렬에 추가 | 반영됨 |
| N0 / K1 | Units71–74의 비교 소스: N1만 포함 / N1과 FA1-K 포함 | 현재 제품은 K1의 평가된 바이트를 사용 |
| F_ONLY | 모델 시도 없이 F 기본 풀이 경로만 사용하는 평가 설정 | UI에 별도 선택 항목으로 노출하지 않음 |
| S / M / R | 공통 후보 생성 뒤 허용 조건·목적 점수를 달리 적용하는 제품 모드 | 기존 UI 선택과 기본값 유지 |

FA1-K는 S/M/R과 나란히 고르는 네 번째 모드가 아니다. 공통 F 계열의 개선이며,
S/M/R 실행에서도 이 경로를 사용한다. N0/K1은 비교군 이름이다.
Unit65의 I0/I1/I2 계측 프로필이나 Unit58 등의 B0/D1을 이 이름들과 혼동하지 않는다.
S도 추측 허용 상태에서 무조건 안전한 승리를 보장하지 않는다.

## 2. 필요한 변경 이력

| Unit | 확인된 결과 | 적용 범위 |
|---|---|---|
| 69 | 기존 12판을 두 번 실행해 Unit52 수순·입력·결과를 재현 | E-MIN 평가 경로 검증, 새 효율 개선 아님 |
| 70 | N1의 12판 수순·반환 작업량 동등, wall 합 432.33 → 28.07초 | 해당 보드·실행의 비용 개선 관측 |
| 71 | FA1-K 의미 시험 보완 후 79/79, 개발 12판 비교 | 공동 승리 5판 평균 106.233 → 110.076%; B01은 악화 |
| 72 | 새 100판의 N0/K1 F_ONLY 비교와 독립 파일 검토 | 표본 내 효율 개선 수용 |
| 73 | 제품 5파일·시험 2파일·문서 1파일 반영, 사본 회귀 187 PASS | 소스 반영과 기능 호환; 빌드·배포 완료 아님 |
| 74 | 설치 Stage4 회귀 187 PASS, S/M/R 평가 및 독립 검토 수용 | 54보드의 제한 결과; 전체 회귀 실패는 별도 유지 |

Unit70의 EQ는 함수 결과 68/68 일치와 별개로 후보 적재 목록의 기록 공백이 있다.
원 판정 `pass=false`와 한정 수용 처분을 유지한다. T1/T2 적재 확인을 EQ에 소급하지 않는다.
Unit71의 첫 의미 시험 78 PASS / 1 FAIL도 보존하며, 보완 시험의 79 PASS로 덮어쓰지 않는다.

## 3. N1 — 무엇이 빨라졌는가

`stage4_live_delivery.py`의 `consistent()`가 열린 칸마다 전체 이웃 표를 만들던
중복을 없애고, 한 검증 호출 안에서 한 번 만든 표를 사용한다. 상태 검증을 생략하거나
안전 조건을 완화한 변경이 아니다. 호출을 넘는 전역 캐시도 아니다.

| 기존 12판 합계 | A0 | N1 |
|---|---:|---:|
| 판 wall | 432.33초 | 28.07초 |
| 선택 계산 `choose` | 20.09초 | 20.02초 |
| `consistent()` | 406.57초 | 2.52초 |

wall 합의 비는 약 15.4다. **모든 모드·새 보드·GUI가 15.4배 빨라졌다는 뜻은 아니다.**
입력과 승패는 같은 관측이므로 클릭 효율 개선과도 구분한다.
Stage3는 이 검증 함수를 쓰는 경로가 아니며 같은 배율을 이식할 수 있다고 보지 않는다.

## 4. FA1-K — Unit72의 F_ONLY 확인 결과

새 보드 100개에 N0/K1을 한 번씩 실행했다. 두 군 모두 46승·54패이며 승리 집합도 같다.
효율은 승리판의 `3BV / 입력 수 × 100`을 판별로 구한 뒤 평균한 값이다.
승리 순간의 자동 깃발은 입력으로 세지 않는다.

| 공동 승리 46판 | N0 | K1 |
|---|---:|---:|
| 평균 효율 | 104.196697% | 108.361795% |
| 입력 합 | 7,710 | 7,414 |
| 120% 이상 | 1판 | 1판 |
| 130% 이상 | 0판 | 1판 |

44판 개선·1판 동일·1판 악화(N090, 입력 1 증가)다. K1 최고는 N046의
132.335329%이며, 한 판의 최고와 평균을 섞지 않는다. 이 결과는
**F_ONLY + indexed_k100k**에 한정된다. 보드당 군별 1회 관측이며 일반 승률 보존을
보증하지 않는다. 첫 분기에서 K1의 작업량 증가도 기록돼 있고, 작업량 동일을
FA1-K의 필수 조건으로 삼지 않는다.

## 5. Unit74 — 실제 UI 설정에 맞춘 S/M/R 결과

N0/K1 × S/M/R, R 목표 130%(13/10), 모델 시도 최대 8회, 등록된 35초/30초 한도를
사용했다. 두 군의 설정과 UI 요청 경로의 일치를 확인했다. 준비한 1,000개 본평가 보드를
모두 실행한 것이 아니다. 별도 pilot 6보드의 종단간 시간으로 N=54를 한 번 확정했다.

- smoke 8 + pilot 36 + 본평가 324 = **368판**. 새 표본 성적의 분모는 본평가 54보드다.
- 모든 판 유효 종료, 미확정·기술 오류·재시도 0. 저장 입력 **39,309개**를 독립 규칙으로 재현했다.
- 모델 한도로 F에 넘어간 결정은 있었으며, 판 단위 기술 오류 0과 구분한다.

| 본평가 조건 | 승 / 패 | 승리판 평균 효율 | 최고 효율 |
|---|---:|---:|---:|
| N0 / S | 22 / 32 | 104.9421% | 115.6977% |
| K1 / S | 22 / 32 | 109.6483% | 123.5294% |
| N0 / M | 22 / 32 | 105.5443% | 116.3743% |
| K1 / M | 18 / 36 | 110.0961% | 125.1748% |
| N0 / R | 22 / 32 | 105.5443% | 116.3743% |
| K1 / R | 18 / 36 | 110.0961% | 125.1748% |

S는 같은 22판 승리 중 21판 입력 감소·1판 증가이며 합계 3,708 → 3,547이다.
M/R은 승리 집합이 다르다. 공동 승리 16판에서는 입력 2,668 → 2,556으로 감소했지만
N0만 승리 6판, K1만 승리 2판을 함께 기록한다. 위 승리판 평균만으로 M/R 전체 개선을
선언하지 않는다. 불일치 6:2의 정확 양측 확률은 0.2890625이며 일반 승률 감소나
차이 없음의 증명으로 쓰지 않는다.

M/R은 pilot·본평가 120쌍 및 smoke 2쌍에서 입력열과 결정이 같았다.
본평가 R의 완료 모델 판정 410건 중 409건은 도달 증거가 없었고, 1건도 M과 같은 수를 골랐다.
목표 값이 전달되지 않은 오류로 판정한 것은 아니다. 같은 후보·표본을 사용하는 현재 구조에서
R의 추가 정렬 기준이 선택을 바꾸지 않은 관측이다. 후보별 원 점수는 저장되지 않아 독립 재계산은
미확인이다. R 재실험 전에는 구별할 가설과 후보별 점수 기록을 정해야 한다.

## 6. 반영·시험·남은 제한

제품 변경: `stage4_live_delivery.py`, `stage4_rollout.py`, `stage4_exact_pilot.py`,
`stage4_efficiency_plan.py`, `stage4_runtime_model.py`.
시험 변경은 `tests/test_stage4_rollout_indexed.py`와 `tests/test_stage4_runtime_model.py`의
식별자 리터럴뿐이다. `:FA1K_U71`은 평가본 그대로 유지했다. UI, 기본값, 예산은 바꾸지 않았다.
`request_id`만으로 반영 전후를 구분하지 않고 소스 바이트·식별자·설정을 함께 확인한다.

- Unit73 사본: 14모듈·187 PASS, FAIL/ERROR/skip 0.
- Unit74 설치본: 모듈별 새 프로세스의 Stage4 한정 14모듈·187 PASS.
- 전체 소스 관문: 최초 중복 시험 ID로 실행 전 중단. 보완 관문은 중복 29개를 정리했지만
  제거 불가능한 감사 훅의 시험 간 누수와 다른 실패로 종료됐다. **`FAILED_UNRESOLVED` 유지.**
  모든 실패를 FA1-K 결함이나 환경 문제로 단정하지 않는다.
- Unit74의 한정 평가 허용은 전체 관문 PASS를 대체하지 않는다. 기능 시험과 효율 평가는 별도 근거다.
- 평가·회수 기록 수용은 시스템 전체 프로세스 부재, 모든 환경의 UI, 전시 노트북 또는 배포물 인증이 아니다.
- Unit74 실행 manifest는 자기 자신과 명시된 실행기 콘솔 로그 2개를 제외한다. 모든 산출물이 봉인됐다고 표현하지 않는다.

## 7. 다음 작업과 유지할 경계

우선순위는 **현재 앱의 Stage3 실제 플레이 → Stage4 실제 플레이 녹화**다.
Stage4에서 만족스러운 약 120% 사례를 얻지 못하면 실제 알고리즘 저장 입력의 기존 Replay를 사용한다.
특정 보드를 새 무작위 판처럼 실행하는 기능이나 촬영 전용 UI를 추가하지 않는다.

검증된 후보는 Unit74 K1/M/N0005(179/143 = 125.1748%)와 K1/S/N0025
(210/170 = 123.5294%)다. 둘 다 추측을 통과한 승리다. 평가 JSONL의 앱 Replay JSON 호환·변환과
GUI 재현은 아직 미확인이다. 변환이 필요하면 원 배치·입력·순서·출처를 보존하고, 재생 속도를
원 측정 시간으로 꾸미지 않는다. 영상에서 실제 플레이와 기록 재생을 구분한다.

촬영 뒤 검토할 항목:

1. Stage3의 행동별 확정정보/표시 갱신, 가까운 확정 오프닝 우선, 불가피한 추측 조기 처리.
   계산·통신·화면·설정된 입력 간격의 비용을 분리한 뒤 최적화한다. Stage4의 배율을 적용하지 않는다.
2. R의 목표 점수가 선택에 영향을 주는 조건과 후보별 점수 기록, 필요한 추가 비교.
3. 전체 소스 시험의 격리와 남은 실패 원인 정리.
4. 사용자가 따로 정할 도움말·UI 정리, 전시 노트북·배포물 확인.

기존 Stage3 V1/Model C, D0–D5 수용, 과거 실험 원시·실패·미확인 기록은 보존한다.
Phase2/R0-B/ActualE2, Production K/Gate P, holdout 2,010,000..2,010,099 및 금지 formal evidence를
이 문서로 재개하지 않는다. 실제 배치/복원용 seed는 정책에 주지 않으며 공개 조건 모의 계획의
`planning_seed`와 구분한다. 읽기·문서 작업에 브라우저 종료는 필요 없고, 부하 앱 종료가 권장되는
실제 측정은 사용자에게 미리 알린다. 새로운 실행 범위는 현재 사용자 지시에서 확인한다.

## 8. 근거 경로

아래 절대 경로는 개발 PC의 보존 산출물이다. GitHub에는 경로가 가리키는 원시 파일이 포함되지 않는다.
과거 보고서의 '미반영'은 그 보고서 작성 시점의 상태다. 현재 반영 여부는 Unit73 및 Git 마감이 기준이다.

| 근거 | 파일 |
|---|---|
| Unit69 두 반복 경로 검증 | [R2_REPORT_KO.txt](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_MINIMAL_EVALUATION_PATH_UNIT69_2026-11-14/claude_01/R2_REPORT_KO.txt>) |
| Unit70 12판 비용 진단 | [T2_REPORT_KO.txt](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_DELIVERY_COST_DIAGNOSTIC_UNIT70_2026-11-14/claude_01/T2_REPORT_KO.txt>) |
| Unit71 보완 의미 시험과 pilot | [REPORT_KO.txt](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_FA1_MINIMUM_PILOT_UNIT71_2026-11-14/execution_02/REPORT_KO.txt>) |
| Unit72 새 100판 | [실행 보고](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_FA1_CONFIRMATION_UNIT72_2026-11-14/execution_02/REPORT_KO.txt>), [독립 검토](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_FA1_CONFIRMATION_UNIT72_2026-11-14/review_claude_01/REVIEW_REPORT_KO.txt>) |
| Unit73 사본 회귀·반영 | [사본 회귀](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_PRODUCT_INTEGRATION_PREPARATION_UNIT73_2026-11-15/execution_01/REPORT_KO.txt>), [소스 반영](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_PRODUCT_INTEGRATION_PREPARATION_UNIT73_2026-11-15/integration_01/REPORT_KO.txt>) |
| 제품 커밋·푸시 | [Git 마감](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_PRODUCT_INTEGRATION_PREPARATION_UNIT73_2026-11-15/git_closeout_01/REPORT_KO.txt>), [커밋 8fc12f3](https://github.com/cube1793/Minesweeper-Project/commit/8fc12f39a6dcfb8a5326943f089ab42bc7b2f84c) |
| Unit74 실행·독립 검토 | [실행 보고](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_SMR_OVERNIGHT_EVALUATION_UNIT74_2026-11-15/execution_03/REPORT_KO.txt>), [독립 검토](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_SMR_OVERNIGHT_EVALUATION_UNIT74_2026-11-15/review_claude_01/REVIEW_REPORT_KO.txt>) |
| Unit74 수용·촬영 우선 | [수용 기록](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_SMR_OVERNIGHT_EVALUATION_UNIT74_2026-11-15/coordinator_06/REVIEW_RECEPTION_KO.txt>), [촬영 계획](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_SMR_OVERNIGHT_EVALUATION_UNIT74_2026-11-15/coordinator_06/RECORDING_PLAN_KO.txt>) |
| Stage3 미구현 후속안 | [REQUESTED_ITEMS_KO.txt](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE3_FOLLOWUP_NOTES_2026-11-07/coordinator_01/REQUESTED_ITEMS_KO.txt>) |

현재 문서 출발점은 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md), 전체 문서 목록은 [문서 색인](../README.md)이다.
