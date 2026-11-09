# Stage 4 Unit37 — 모델 호출 PROXY 진단 마감

Updated: **2026-11-09 (Asia/Seoul)**

## 수용 범위

**PROXY 진단과 NO_SAFE_CANDIDATE를 한정 수용한다. 제품 변경과 속도 개선은 없다.** 독립 검토 `review_claude_01`의 필수 보완은 0건이며 새 native 시험은 필요하지 않다. 원 11.8초 사건의 요청 DTO를 확보하지 못했으므로 그 사건의 정확한 재현이나 원인 확정으로 확대하지 않는다.

마감 출발 HEAD/main/local origin/main은 `cccfb7d8483fb91601cc3db4bdd4cb46494aae12`다. Unit36은 이 commit의 사용자 push와 Desktop destination 검증까지 완료됐다. 이번 Unit37 마감은 문서 6경로만 변경한다. source384는 유지하고 tracked474→475를 예상한다. 최종 Git commit·remote와 Desktop 완료는 별도 사용자 영수증 및 조율의 사후 검증으로 확정한다.

## 진단 결과

대표 C01은 30×16/99 보드에서 숫자1 하나만 드러난 공개 국면이다. 원 사건과 유사한 **PROXY**이며, 공개 정보 이외의 실제 배치나 미래 입력은 정책에 주지 않았다. 공개 국면은 7개 등록·6개 실행했고 C06은 후보 확인용 미실행 사례다.

현재 모델 호출 조건은 counted≥1, attempts<8, 첫 시도 또는 이전 시도부터 간격≥16, 남은 모델 시간>0이다. 국면 복잡도에 따른 호출 선별 조건은 없다. 시도 수와 last를 갱신하고 durable history를 발행한 뒤 모델에 진입한다.

| C01 상세 진단(run01) | 원시·독립 재집계 |
| --- | ---: |
| wall / CPU | 12.203 / 11.984초 |
| root 후보 평가 | 0.188초 |
| 모델 내부 가상 F | 11.659초, wall의 약95.5% |
| F 내부 kernel / plan / Q | 8.762 / 1.957 / 0.737초 |
| 예정 / 시작 / 완료 행 | 32 / 4 / 3 |
| F miss | 212 = kernel COMPLETE112 + WORK_LIMIT100 |
| F lookup / hit / 거절 | 214 / 1 / 1 |
| 모델 뒤 실제 fallback F | trace0.016초, perf_counter 약0.0204초 |

kernel/plan/Q는 F 안에 포함되고 실제 fallback 부분도 포함한다. 가상 F와 다시 가산하지 않는다. operation tag로 누적 trace를 분리했으며 exclusive 합은 최상위 inclusive와 일치한다.

F miss마다 kernel 허용 작업량을 미리 예약하며, 실행 중 남은 예약량이 부족해 KERNEL_BUDGET에 이른다. 모든 행이 끝나야 모델 선택을 발행하므로 C01/C05의 약12~13초 가상 작업은 최종 선택으로 이어지지 않았다. 실제 행동은 별도의 fresh F에서 나왔다. C01의 기본 경로는 `OPEN(2,0)`이다. 이는 해당 국면에서 관측한 구조와 결과이며 모든 모델 호출의 무용성을 뜻하지 않는다.

정확한 GUI형 C01 DTO의 run04 직접 요청은13.391초, 기존 run02 persistent worker의 후속 요청은13.078초다. RuntimeRequest ID·행동·history·결정적 작업량이 같다. worker bootstrap은0.578초/model0이며 프로세스 시작부터 첫 제안까지의 별도 구간이다.

단일 표본끼리의 시간 차이에서 개선율·전송 비용을 추론하지 않는다. primary의 세부 timer hook은 OFF지만 함수 진입 카운터와 작은 영수증 쓰기는 ON이다. `GetTickCount64` monotonic의 해상도는15.625ms이며 작은0/16ms 구간을 정밀 비교하지 않는다. 다른 프로세스 시계를 빼지 않았고 일부 전송·직렬화 잔여 비용은 UNMEASURED다.

K100K 보조 요청은18.906초, 8/8행 COMPLETE, 가상 입력751/miss616이며 `OPEN(0,15)`을 골랐다. 기본 경로의 자원 소진 및 `OPEN(2,0)`과 완료 조건·행동이 다르므로 속도 개선이나 후보 PASS가 아니다.

## 후보 미채택

`NO_SAFE_CANDIDATE / CANDIDATE_NONE`은 이번 허용 범위에서 유용한 의미 보존 후보를 확보하지 못했다는 결론이다. 원 지시가 허용한 진단 종료이며 모든 최적화가 불가능하다는 증명이 아니다.

- root 비용은 주 병목보다 작다. C01의 요청 내부 F cache는 hit1/miss212이고 cache는 모델 호출마다 새로 만들어진다.
- 단일 후보 C04도 R target/행 정보를 계산하며 약16ms여서 긴 지연의 대표 사례가 아니다.
- 초기 입력에서 모델을 생략하거나 F를 우선하면 attempt/last/model_status/usage와 이후 스케줄 또는 행동이 달라질 수 있다.
- 변형·제품 채택은0이다. 후보 비교·역순·후보용 C06·로컬 비용 gate는 미실행/해당 없음이며 PASS로 세지 않는다.

immutable kernel/proof 재사용과 admission 정책 실험은 별도 등록할 수 있는 후속 제안이다. 모델/F 한도, samples/shortlist/rows, 목적 함수, GUI 기본값과 quota를 이번 마감에서 바꾸지 않는다.

## 요청 결속과 회계 보완

**U37_TYPED_LIMIT_BINDING_001 원 FAIL 유지.** 원 직접 요청의 정수30/35는 제품 DTO에서 문자열 `"30"`/`"35"`로 인코딩되고 GUI의 실수30.0/35.0은 숫자로 남는다. 원 runner의 dataclass `==`는 이 차이를 놓쳤다. 수치 동등성과 요청 identity 동등성은 다르다.

- 원 C01 직접 RuntimeRequest ID: `9c91245d303f76db0919f0ac2c9df41c94ebaf070b943ae037d6b102a7384805`
- GUI형/worker ID: `bb6655e735ceca6c3bd231308f4a76213331b969f5be9ea7fb373a9e5bafb3bd`
- PUBLIC_CASES_TYPED의9행은 원 입력 대비 두 시간 토큰씩18개만 다르다. 독립 검토는 요청 ID10건을 손실 없는 파싱으로 재계산했다.
- run04 한 번의 직접 요청으로 기존 worker의 정확한 C01 identity·행동·history와 결속했다. worker 재실행은 없다. GUI 동일 identity 확인 범위는 C01이다. 동적으로 정해지는 남은 model 시간 때문에 내부 ModelRequest ID까지 동일하다고 주장하지 않는다.
- 원 FAIL은 유지하고 effective 보완 PASS를 별도로 기록한다. 검토 `work/primary_audit.json.typed_diffs`는 JSON 파싱 손실로 잘못된 필드이므로 사용하지 않는다. 올바른 근거는 `work/fixture_audit.json.typed_token_diffs`와 REVIEW_LEDGER다.

**U37_HISTORY_SUM_LABEL_002 원 label ERROR 유지.** `worker_model_attempts`는 새 시도가 아닌 최종 history 합이었다. 전체 최종합7, 새 시도6, worker 함수 진입6이다. run05 원5에는 인계받은1이 포함되어 새 시도는4다. 실제 model 총48은 별도 함수 진입 영수증에서 산출되어 이 label 오류의 영향을 받지 않는다.

run01/run02 history는 wire와 canonical operation log로 대조했다. run05 초기 history는 제품 operation log 수준이며 raw wire 수준은 NOT_VERIFIED다(RV37-N3). C01 worker 제안 자체에는 VALIDATE/ADMITTED/ACK/claim을 수행하지 않았다. bootstrap ACK는 공개 fixture 전이이며 engine.step은0이다. 실제 engine을 쓰는 허가·ACK·재시작은 run05 회귀 범위다.

## 회귀와 실행 종료

42 고유 ID가 등록·수집·실행 목록에 일치하고 모두 PASS다. 기능 FAIL/ERROR/SKIP은0이다. 시험 파일은 결속 bytes 그대로이며 기존 기대를 바꾸지 않았다. 의도된 model ERROR 응답2는 시험 ERROR0과 구분한다.

| 회계 축 | 값 |
| --- | ---: |
| 실제 START / supervisor | 4 |
| 보수 Python image / 실제 worker owner | 11 / 7 |
| 실제 engine.step / model 함수 진입 | 13 / 48 |
| memory policy instance | 59 |
| model 진입의 진단·primary / 회귀 | 18 / 30 |
| 진단·primary 가상 입력 / 시작 행 | 2,565 / 92 |
| 진단·primary F lookup | 2,039 = miss1,988 + hit44 + 거절7 |

실행은 run01/run02/run04/run05이며 run03은 등록 후 미시작 취소다. 필수 owner7개 모두 요청→PID·정확한 생성시각·이미지·Job→보유 handle 종료·회수가 이어진다. duplicate birth handle은 신원 병합 때 닫힌 별도 handle이고, 같은 PID+creation의 retained 관측에서 종료를 확인한다.

각 실행의 빈 Job 조회2회가 성공했으며 census는4/4,4/4,2/2,12/12 COMPLETE다. census22는 Python11+conhost11이고 Python image 수와 다르다. 현재 OS 프로세스를 새로 조회한 결과는 아니다. 실행 결속1,564건은 helper/snapshot1,503 + product16 + loaded45의 검사 건수이며 고유 파일 수가 아니다.

RV37-N4는 TEST_MATRIX 분류의 누락으로, 원6분류의41참조가 고유33개만 포함한다. 나머지9개도 등록·실행·PASS다. 원 TEST_MATRIX는 보존하고 아래에 보충 분류한다. 분류 중복을 별도 시험으로 세지 않는다.

| 보충 분류 | 원래 미분류였던 시험 ID(모듈 접두어 생략) |
| --- | --- |
| 목표/identity | RuntimePolicyTests.test_target_required_and_zero_parent |
| 시간·자원 한도 | IndexedK100KPolicyTests.test_runtime_K100K_requires_all_five_seconds |
| 정확 eligibility | RuntimeModelTests.test_common_exhaustive_bank_and_exact_eligibility |
| permit 시계 | PermitClockTests.test_common_integer_clock_different_perf_origin_and_exact_boundaries |
| owner 정리 | OwnedCleanupRetryTests.test_retry_releases_only_confirmed_original_handles_and_preserves_failure |
| owner fail-closed | OwnedCleanupRetryTests.test_live_unknown_reused_pid_foreign_scope_and_permission_fail_closed |
| DTO/입력 계약 | ContractTests.test_forbidden_fields_invalid_cells_integers_and_large_dtos |
| ACK identity | ContractTests.test_ack_target_and_generation_are_bound |
| transport | TransportRecoveryTests.test_ordered_publication_between_absence_and_glob |

## 보호 판정과 절차상 공백

**보호 PASS는 결속한 HEAD/main/local origin/main/index/source384/tracked474/Desktop에 한정한다. `.git` 전체 무변경을 뜻하지 않는다.** 구현자가 요청한 Git 쓰기 명령0과 `.git` 내부에 어떤 쓰기도 없었다는 주장은 구분한다.

RV37-N1에서 `.git/packed-refs`의 생성·수정 시각05:58:45.538Z와 `refs/codex/turn-diffs/checkpoints/...`의 생성 시각06:12:24.631Z를 관측했다. 후자는 구현 manifest 봉인 약7초 뒤다. host turn checkpoint 형태와 맞지만 **실제 쓰기 주체는 NOT_VERIFIED**다. 현재 main/origin/main의 loose ref가 우선하므로 packed-refs 안의 오래된 main 값으로 기준 commit을 바꾸지 않는다.

조율은 현재 packed-refs 원문·7,219 bytes·SHA256 `ac0809fd66dc10154ad5c9ba306c047d8673b5b23e6eea7cf3bced8974db4bd5`, packed/loose `refs/codex` 목록·OID·파일 hash를 `GIT_METADATA_BASELINE.json`에 새 기준으로 기록했다. 관측 시 packed codex35개와 loose15개다. 이후 Git/host 활동에 따라 달라질 수 있으므로 사용자 마감 스크립트는 전후 inventory도 기록한다. HEAD/main/origin/main/index/source/tracked/Desktop의 계획상 변화는 엄격히 검증하고, 그와 별개로 packed-refs/codex ref 변화와 행위자 미확인을 명시한다. 이 inventory는 `.git` 전체 감사가 아니다. ref 삭제·정리는 이번 마감에 포함되지 않으며 사용자 Git 결정이다.

RV37-N2: 구현 최초 도구 UTC/monotonic은 미기록이다. 첫 도구는 대략05:52:13Z~05:59:02.96Z로만 한정되며05:55Z가 실제 첫 도구보다 이른 기점이라는 것은 증명되지 않았다. 구현 전체 상한이 약20분이어서3시간 soft/5시간 hard 예산 판정에는 영향이 없다. 원 시간 공백과 첫 Git 명령의 보호 옵션·직전 index 기록 공백은 소급 PASS로 바꾸지 않는다.

독립 검토도 최초 Bash node 시각 probe가 실패했다. 첫 기록06:21:26.4667374Z를 첫 도구 시각으로 부르지 않는다. 검토의 약28분은 보고된 경과이며 이 공백을 보존한다. 조율/검토 도구의 경로·파싱·분류 오류 및 대체 필드는 해당 ledger에 남아 있다.

Unit36 D와 과거 B 비용 FAIL, 과거302 PASS+보호 FAIL1, INCOMPLETE_CENSUS·35/34 FAIL, Unit36 추가 진단 ERROR를 유지한다. 모든 환경의 UI, 전시 노트북, 일반 효율·승률·P95·Production 승인은 별도 범위다.

## 근거와 후속

구현·독립 검토·조율 대조는 다음 output root에 있다.

`C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\STAGE4_MODEL_CALL_ADMISSION_UNIT37_2026-11-09`

- `codex_01`: 구현 manifest1,536파일/68,284,301bytes, SHA256 `c419e031a97669c3c7cf0e1a20f6a32eba14da19ec491aadf96e164ad48cabca`.
- `review_claude_01`: 검토 manifest30파일/318,019bytes, SHA256 `ee219860fc926f40eff8c8f5a1ed50ff9c605f70f62e7044231095e6c211ed0a`. FINDINGS의 미확인11항목을 유지한다.
- `coordinator_02`: 조율 보호·실행·비용 대조와 독립 검토 인계. 효과적인 실행/비용 결과는 EXECUTION_RECHECK_V2와 COST_RECHECK_V3다.

이번 수용·메타데이터 관측·문서 마감 자료는 `STAGE4_UNIT37_CLOSEOUT_2026-11-09\coordinator_01`의 REVIEW_VERIFICATION, COORDINATOR_ACCEPTANCE, GIT_METADATA_BASELINE, DOCUMENT_REFRESH_RECEIPT, GIT_PLAN에 결속한다. 사용자 commit/push 이후 실제 commit에 맞춰 Desktop recovery를 별도 준비한다.

후속 우선순위는 제공된 고효율 Replay의 행동 직전 공개 정보 분석과, 얻은 전략 후보의 새 보드 S/M/R 비교다. 이번 병목의 kernel/proof 재사용이나 호출 선별은 의미·회계·반복 시간 표본을 갖춘 별도 실험으로 준비한다. R 목표 UX, 표시 D 비용, 전시 노트북/패키지는 별도 미완료 항목이다. 노트북 대여는11월10일18시 신청 시작이며 수령 시각은 미정이다.
