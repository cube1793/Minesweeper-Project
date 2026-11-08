# Stage 4 Units28–29 — 고정 K100K F와 신규 상급판 제한 평가

작성일은 2026-11-08이며 문서 마감 출발 HEAD/origin은 `5d4b64dbd94f51fecd99a94df920cf051d654e27`이다. Unit27은 이 commit과 Desktop destination 검증까지 마쳤다. 이번 실행의 source는 375개, tracked는 460개다. 검토된 source/tests 4경로와 문서 6경로를 함께 마감하며 최종 tracked는 461개를 예상한다. 이후 commit을 과거 실행 HEAD로 소급하지 않는다.

## 판정과 적용 범위

| 축 | 판정 |
| --- | --- |
| K100K source 계약 | 명시적으로 선택하는 F 종류로 한정 수용 |
| Unit28 C36 가용성 | 등록된 개발 집합의 gate 충족 |
| Unit29 관측된 전달·회계·미완료 처리 | 등록 경로에서 한정 수용 |
| Unit29 기술 완결 | PARTIAL 유지, 정상 종단 6/8 |
| R 모델 정보·실전 목적 차이·일반 효과성 | NOT_ESTABLISHED |
| Main/worker/Replay 연결 | 아직 미연결, 다음 구현 범위 |
| Stage4 전체 | NOT_MERGED 유지 |

제품 필수 수정과 helper/evidence 필수 수정은 0건이다. 검토된 네 파일을 현재 bytes 그대로 보존한다. `indexed`와 모델 기본 samples 8 / shortlist 4는 유지하며 `indexed_k100k`는 명시적 API 선택이다. 이번 수용은 기본 정책 전환이나 전체 Stage4 기능 수용을 뜻하지 않는다.

## source와 고정 F 계약

변경 경로는 `stage4_runtime_model.py`, `stage4_runtime_policy.py`, `tests/test_stage4_runtime_model.py`, `tests/test_stage4_runtime_policy.py`다. Unit29는 제품 source를 추가로 수정하지 않았다.

K100K는 기존 indexed kernel/proof 경로에 kernel work 100,000 한도를 고정한다. 다른 F 한도와 5초 계약은 유지한다. model row와 RuntimePolicy fallback은 `fixed_followup_limits`를 공유하며 모순된 kind/cap은 거절한다. F ID는 다음과 같다.

```text
PUBLIC_F_INDEXED_K100K_COVER_UNIT10_V1:prepaid_indexed_immutable_relations_v1
```

request, logical/cache key, score pilot_id와 runtime 반환은 이 F ID에 묶인다. miss에는 등록 자원 전체를 예약하며 잔여 자원에 맞춰 F의 의미를 축소하지 않는다. 미완료 kernel은 사실을 발행하지 않고 같은 공개 입력을 Q에 보낸다. 미완료 모델의 일부 행으로 평균·선택을 만들지 않는다. F1의 과거 결함과 `F1_FIXED_BOUNDED` 이력은 별도로 보존한다.

## Unit28 가용성과 비용

A의 기존 25 + 신규 12 = 고유 37시험과 B의 직접 F 16회를 구분한다. A의 실제 model 45/F 226은 mock·spy·의도적 UNKNOWN 과금과 별개다. C는 P01–P06 × S/M/R × BASELINE/K100K의 36요청이다. 원 31요청과 R1의 새 5요청을 한 번씩 결합했다.

| 항목 | BASELINE | K100K |
| --- | ---: | ---: |
| COMPLETE | 9/18 | 15/18 |
| mode별 nonzero | 2/2/2 | 4/4/4 |
| F miss | 2,737 | 6,640 |
| F hit | 151 | 1,798 |
| kernel work | 649,097,867 | 509,785,037 |
| Q local work | 4,039,592 | 16,086,845 |
| Unit10 units | 2,608,833 | 6,919,700 |
| evaluate 합계 | 127.204초 | 161.060초 |
| end-to-end 기록값 | 154.627초 | 211.614초 |

완료 12/18 이상, +3 이상, 완료 퇴행 0, mode별 nonzero 1 이상이라는 동결 기준을 충족했다. 완료 퇴행은 0이다. R의 엄격한 hit 차이는 0으로 모델 정보 수용과 분리한다.

독립 검토는 C36의 gzip 구조·행렬 결합, F 기록 11,326개, COMPLETE score 48개와 terminal 192개를 재계산했다. 모든 miss의 전량 예약·고정 한도·F ID·cache 분리도 확인했다. 동시 COMPLETE 9쌍의 선택과 첫 수순은 같지만 P02의 후속 row는 달랐다. mean X 차이 13/9130과 13/9352를 전체 행동 보존으로 확대하지 않는다.

kernel work는 약 21.46% 감소했지만 Q와 Unit10 비용이 늘었다. 완료량과 실행 시각이 다르므로 이 값은 속도 개선율이 아니다. end-to-end 시간은 구현자 기록값이며 이번 독립 검토에서 다시 계산하지 않았다. plan verification/visits가 기존 수치 model budget 밖이라는 한계도 유지한다.

## Unit29 실제 8회

새 상급 30×16/99 보드 두 개를 고정했다. G01 seed는 994773631, G02는 972070611이다. 최초 OPEN(0,0)을 실제 counted 1회로 포함했다. F_ONLY도 RuntimePolicy를 사용하며 모델 시도만 0으로 설정했다. S/M/R은 모델 최대 8회, counted 간격 16, samples 4 / shortlist 2 / rows 8, K100K, guess ON을 사용했다. R target은 6/5다.

G01은 F_ONLY→S→M→R, G02는 R→M→S→F_ONLY 순서로 한 번씩 실행했다. 같은 보드의 배치·첫 관측은 같고 policy 인스턴스는 분리했다. 정책에 실제 배치·seed·완성 3BV·active/wasted를 전달하지 않았다.

| 판 | 조건 | 결과 | C | 승리 IOE | 모델 시도/완료/선택 |
| --- | --- | --- | ---: | --- | --- |
| G01 | F_ONLY | LOST | 168 | — | 0/0/0 |
| G01 | S | LOST | 168 | — | 8/2/2 |
| G01 | M | UNRESOLVED | 105 | — | 7/4/4 |
| G01 | R | UNRESOLVED | 105 | — | 7/4/4 |
| G02 | R | WON | 190 | 41/38 | 8/5/5 |
| G02 | M | WON | 190 | 41/38 | 8/5/5 |
| G02 | S | WON | 196 | 205/196 | 8/3/3 |
| G02 | F_ONLY | WON | 194 | 205/194 | 0/0/0 |

8회 시작, WON 4 / LOST 2 / UNRESOLVED 2다. 실제 입력과 저장 로그 재생은 각각 1,316회이며 독립 엔진 재생의 불일치는 0이다. 정상 종단은 6/8이므로 Unit29의 기술 판정은 PARTIAL이다. LOST의 X는 0이며 두 UNRESOLVED의 X와 target hit는 null로 유지했다.

G01 M/R은 C105에서 `RESOURCE_LIMIT:F_BLOCKED:Q_BASE_WORK_LIMIT`로 멈췄다. Unit10은 199,998/200,000까지 사용했으며 제안 없이 종료했다. 추가 입력은 0이고 같은 요청을 반복해 quota를 다시 얻지 않았다. 이는 현 정책 계약에 맞는 미완료다.

M/R의 실제 수순은 두 판 모두 동일했다. R 완료 9건은 hit 동률에서 mean으로 순서를 정했으며 엄격한 hit 차이는 0이다. G02의 matched-win은 각 조건 한 판이다. M/R은 F_ONLY 대비 각 4입력을 줄였고 S는 2입력 늘었다. G01 F_ONLY와 S는 C·종단이 같지만 실제 수순은 달랐다. 두 판으로 일반 우월성이나 추천 설정을 정하지 않는다.

G02 M/R raw wall은 약 147초, F_ONLY는 약 9.66초이며 계측·직렬화·검증을 포함한다. 이 평가는 시간 성능 비교 실험이 아니다.

## 실제로 확인한 분기와 남은 연결 계약

독립 검토는 공개 요청, quota/간격, 완료 모델 23개, claim·stale·기존 F의 전달과 원장 15항목을 확인했다. S 모델 선택 5건은 안전/최소위험 규칙을 지켰다. G01의 두 패배는 각각 확률 1/9와 35/324로 제안된 추측이었다. 해당 시점의 Q 최소위험이 전역적으로 최적인지는 새 정확계수로 재검증하지 않았다.

실제 모델 CHORD 전달과 공유 FLAG skip은 각각 0이다. 취소/BUSY/만료, 모델 TIME_LIMIT, guess OFF, K100K의 F_TIME_RESERVATION도 이번 실전에서는 미관측이다. 기존 시험·통제 근거와 이번 실제 관측을 구분한다.

다음 화면 연결에서 적용할 조율 계약은 다음과 같다.

- 제안 없는 RESOURCE_LIMIT나 F_TIME_RESERVATION은 Auto를 중지하고 입력 예약을 비운 뒤 구체적인 계산 중단 사유를 표시한다. engine의 PLAYING 상태와 완료·패배를 구분하고 현재 보드와 Replay 기록을 보존한다.
- 같은 공개 상태를 자동 재요청하는 루프를 만들지 않는다. 수동 입력·새 판·명시적 정책 전환 등 정상 상태 전이 뒤의 재개 규칙은 연결 구현에서 검증한다.
- K100K는 명시 설정으로만 제공한다. 기본 indexed와 기존 모델 기본값은 유지한다.
- 모델 CHORD·공유 FLAG skip·취소/BUSY/만료·시간 한도·guess OFF는 기존 근거를 연결 경로에 대응시키고, 대응이 없는 경로만 표적 시험한다. 성공한 C36이나 기존 8판을 숫자 보충 목적으로 반복하지 않는다.

위 항목은 다음 구현의 계약이며 아직 Main/worker/Replay에서 구현·검증한 결과가 아니다. 사용자 native와 전시 노트북 수용도 후속이다.

## 실패·정리·근거 한계

Unit28 원 실행은 PARTIAL_STOP_RESTORED, incident 7/6으로 보존한다. H04는 shortlist metadata 순서를 실제 chosen 순서로 오인한 helper 검사였다. C31·C32에서 순서가 달랐으며 R1은 공개 후보로 순서를 재도출했다. 원 C31 FAIL_RETAINED와 새 검증 PASS를 구분한다. 원 actual START 5/image 10, conservative 6/12와 R1 새 1/2를 합쳐 지우지 않는다.

Unit29 원 실행은 A의 모듈 import assertion 실패와 예비 A PASS, 원장 분기 보완을 포함한다. B1 전 U29-O03에서 최초 개별 PID 상태가 저장되지 않았다. 원 actual 2/4, conservative 3/6, helper 보정 2/2, incident 3/4를 유지한다. 이후 부재 관측으로 최초 원인 공백을 해소하지 않는다.

Unit29 R1은 조회 결과를 영속 저장한 뒤 같은 값으로 `original_absent AND NO_PID_MATCH`를 검사했다. 새 actual 2/4, 전체 actual 4/8, 보수 전체 5/10을 분리한다. 40/40·45/45 preflight와 최종 50/50 부재는 해당 시점의 기록이다. 기존 Python helper·containment core는 그대로였고 invoke만 바뀌었다. 출력의 Object[] 바인딩 오류는 String[]로 한 번 보정했으며 게임·모델을 재실행하지 않았다.

Job·개별 identity·exit·handle/channel 정리는 원시 기록으로 수용했다. 검토자가 현재 OS를 조회한 것은 아니다. result.json의 cache 공유 여부 등 일부 bool은 helper 선언값이며 독립 근거는 고유 session ID와 source의 수명주기다.

독립 검토는 새 Node 도구만 실행했다. 엔진 전이 27,090/50,000, 새 bitmask 0/20,000을 사용했다. 시각의 Z/+00:00 문자열 비교 오탐을 한 번 보정했다. 원장은 12:40:40Z에 닫혔고 manifest는 12:43:41Z에 생성됐으며 시작은 12:16:48Z다. 실제 Fast OFF와 화면 설정은 UNCONFIRMED다.

## 근거 위치와 결속

구현·복구 네 manifest는 총 1,218파일 / 81,329,154 bytes다. 독립 검토 manifest는 자기 제외 26파일 / 522,334 bytes이며 SHA256은 `17082e8737240d73fdef95dc263724cb5b70b4b4354eb9d7ca155c25967dfdf6`이다. Git 명령 없이 index와 HEAD 460개를 대조해 staged 0, 작업 트리의 후보 4개 변경을 독립 확인했다.

```text
C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\STAGE4_FIXED_F_KERNEL_BUDGET_UNIT28_2026-11-08\codex_01
C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\STAGE4_FIXED_F_KERNEL_BUDGET_UNIT28_2026-11-08\codex_02
C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\STAGE4_FRESH_SMR_PILOT_UNIT29_2026-11-08\codex_01
C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\STAGE4_FRESH_SMR_PILOT_UNIT29_2026-11-08\codex_02
C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\STAGE4_FRESH_SMR_PILOT_UNIT29_2026-11-08\review_claude_01
```

각 root의 REPORT_KO.md 또는 REVIEW_REPORT_KO.md, EXECUTION/REVIEW_LEDGER.json, FINDINGS.json, CROSSCHECK.json, OUTPUT_MANIFEST.json과 연결된 원시를 따른다. [이전 Unit27](STAGE4_FIXED_F_PROFILE_UNIT27_CLOSEOUT.md)의 NONE과 가용성 미달은 당시 결과로 보존한다. D0–D5 CLOSED/FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, V1 CLOSED/FROZEN, Extended ACTIVE, Production K/Gate P·Phase2/R0-B/ActualE2 미승인과 frozen 정책·Model C·holdout 경계는 유지한다.
