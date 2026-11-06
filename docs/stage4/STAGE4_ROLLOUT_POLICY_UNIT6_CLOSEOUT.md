# Stage 4 Unit 6 — 공개 posterior rollout 선택 정책

작성: 2026-11-07 (Asia/Seoul). 구현자 전체 판정 **PARTIAL**을 보존한다. 독립 검토의 제품 판정은 **ACCEPT_BOUNDED**이며 제품 필수 수정 0, helper/evidence 필수 보완 0이다. 마감 표현 W1~W3는 아래에 반영했다. 일반 상급판 효율·안정 시간·Main/UI·전시 노트북 수용은 아니다.

## 범위와 버전

출발 HEAD와 local origin/main은 `fa6e33aa9a02a6facff447b81862727ca4f6e216`이다. 출발 index SHA256은 `37e76e6eec79d2fb3dfe7e349533e90f6ab19c38cf46f41d8141c78d84e75983`이다. 기존 source 348개·tracked 421개는 불변이고, 신규 7파일을 포함한 source는 355개다. 본 마감은 신규 source/tests 7개와 문서 6개, 총 13경로다. commit 이후 권위는 실제 Git/영수증/recovery를 따르며 실행 HEAD를 새 commit으로 소급하지 않는다.

| 신규 경로 | 역할 |
| --- | --- |
| `stage4_posterior.py` | 공개 일관 배치의 정확한 정수 rank 표본 추출 |
| `stage4_rollout.py` | 가상 전이와 평가자, 공개 정보만 받는 고정 P0 |
| `stage4_policy.py` | S/M/R 선택·fallback·원자 입력·인스턴스 내 continuation |
| `tests/test_stage4_posterior.py` | 전수 rank·가중치·큰 정수·한도/취소 |
| `tests/test_stage4_rollout.py` | engine 대조·3BV·공개 경계·보상/null |
| `tests/test_stage4_policy.py` | 목적·위험·표본·오류·continuation |
| `tests/stage4_policy_oracle.py` | 제품 import 없는 작은 raw-bitmask/3BV oracle |

최종 소스는 v02다. **W3:** A 13개는 run02/v01, B 11개는 run03/v01, 추가 B 4개는 run04/v02에서 각각 PASS했다. 합계 신규 시험은 28개지만 v02에서 28개를 한 번에 실행하지 않았다. v01→v02의 제품 변경은 `stage4_policy.py`의 검증 +14/−2줄이며, 기존 B 11개 시험은 byte 동일하고 4개가 추가됐다. 정상 경로는 v02의 run05/run06에서도 실행됐다. 검토는 이 범위에서 기존 성공 시험 재실행을 요구하지 않았다. run01의 사용자 코드 전 exit 101은 별도 실패로 보존한다.

## 공개 정보와 계산 계약

`RolloutPolicy().select_next(PolicyRequest(...))`가 다음 원자 입력 한 개를 반환한다. 입력은 공개 observation, 전체 지뢰 수, 공개 counted 합 C, S/M/R, guess 설정, 양의 target, 공개 planning_seed, episode_key, limits, continuation이다. 실제 지뢰 배치·board seed·분리 active/wasted·진행 3BV·미래 Replay를 정책에 주지 않는다.

posterior는 `uniform_consistent_placements_v1`이다. 물리 FLAG는 미지수다. component의 mine-count histogram, suffix DP와 floating binomial을 정확한 정수로 결합한다. [0,D)의 균등 정수 rank를 component k/leaf index와 floating 조합으로 unrank한다. 전역 배치 곱집합을 저장하지 않고 필요한 leaf만 두 번째 제한 DFS로 회수한다. D≤N이면 모든 D개, 그 외에는 복원추출이며 중복 slot을 제거하지 않는다. mode/target/episode는 표본 seed에 들어가지 않고 각 후보는 같은 ordered bank를 사용한다.

가상 layout과 전체 B=3BV는 평가자만 사용한다. 고정 `PUBLIC_LOCAL_COST_P0_V1`의 의미 입력은 공개 grid/지뢰 수/C/guess다. P0는 확정 규칙과 안전 수순 비용을 사용하고 추측 시 공개 local-density hint를 쓴다. hint는 정확 확률이 아니다. 추측 OFF에서 로컬 규칙이 막히면 `PILOT_UNRESOLVED`다. 가상 WON은 X=B/(C+추가 입력), LOST는 0, 미완료는 null이다.

root의 위험 제한은 Unit 5 exact eligibility를 따른다. 기본 shortlist 6개·표본 16개이고 상한은 각각 12/64다. 모든 후보×같은 N개 표본이 종결돼야 모델 mean/win/hit를 비교한다. S/M은 모델 평균 X를, R은 명시 목표 달성률을 먼저 비교한다. 이 값은 해당 shortlist 뒤에 고정 P0를 따르는 모델의 값이며 실제 매 입력 재계획 정책의 정확한 기대값이나 전역 최적성은 아니다.

모델 한도/미완료에는 완전한 root와 최종 검사 뒤 `HEURISTIC_FALLBACK`을 허용한다. R은 `TARGET_NOT_EVALUATED`다. global timeout/cancel, root incomplete, model error는 action=null이다. hit 0을 목표 불가능의 증명으로 쓰지 않는다. 기본 한 호출 상한은 480칸·sampler work 2,000,000·virtual 입력 50,000·pilot work 10,000,000·협력 wall 30초다. P0 한 호출은 20,000 work, 추론 subcap은 5,000이다. 실시간 보장은 아니다.

## 입력과 continuation

한 번에 원자 입력 하나만 반환한다. FLAG 준비는 같은 `RolloutPolicy` 인스턴스가 공개 발행/소비 상태를 소유한다. episode·설정·원 grid/C·sequence·prefix·예상 다음 grid/C를 확인하고, 실제 입력이 반영된 다음 호출에서 현재 exact 후보의 남은 수순과 허용 조건을 다시 대조한다. OPEN/CHORD 뒤에는 새 root 계획이다.

같은 인스턴스 안의 단일 소비 범위로 수용됐다. 다른 인스턴스의 token은 STALE이며 인스턴스 간 소비 이력 공유는 없다. 반환했지만 적용하지 않은 위치는 같은 인스턴스에서 계속 STALE이므로 새 인스턴스로 새 계획을 해야 한다(N3). UI/worker 인스턴스 수명·미적용 입력 복구와 BUSY 동시성은 후속이다. 현재는 UI/ACK/owner 통합이 없다.

## 선택 수의 정확한 집계 — W1/W2

139개 정책 응답 중 READY는 104개다.

| 응답 구분 | 수 |
| --- | ---: |
| READY / MODEL_SELECTED | 69 |
| READY / HEURISTIC_FALLBACK | 29 |
| READY / EXACT_REVALIDATED_CONTINUATION | 6 |
| 비READY | 35 |

**W1:** basis 필드만 세면 HEURISTIC_FALLBACK이 32개다. 이 중 run03#31 취소, run04#4·#5 오류의 3개는 action=null인데 basis만 남았다. 실제 fallback 입력 반환은 **29개**다. 오류를 입력으로 실행한 것은 아니며, 이후 소비자는 READY와 basis를 함께 봐야 한다(N1).

**W2:** MODEL_SELECTED 69개는 **합성 점수 주입 4 + 실제 가상 rollout 선택 65**다. 65개는 run03 시험 fixture 20, run04 시험 fixture 2(그중 1개는 RNG bank 패치), run05 실제 소보드 폐루프 43이다. 69개 실제 게임이나 독립 보드를 뜻하지 않는다.

## 실제 작은 보드와 큰 공개 관측

run05/v02는 등록 25시도를 모두 시작했다. WON 13 / LOST 10 / GUESS_BLOCKED 1 / UNRESOLVED 1이다. 미완료 1개는 의도한 root cap 0 fixture이고, 전체 평균 X는 null로 남겼다. G001 S/M/R은 각각 12/35, G009는 S 2/5·M/R 1/2다. 실패를 0으로 포함한 평균이지 승리판 평균 효율이 아니다. 실제 M/R 차이는 이 fixture에서 확보하지 못했고 R의 target 변경 차이는 합성 행렬에서만 확인했다(N5). 이 실제 폐루프에는 fallback 선택이 없었으며 작은 fixture의 fallback 시험과 구분한다(N4).

run06/v02는 기존 상급 크기 공개 snapshot 6개×3모드의 첫 선택 18회다. 모두 root/sampler COMPLETE, bank 16·shortlist 6, READY fallback이다. 예정 가상 1,728행은 **PILOT_UNRESOLVED 18 / WON 3 / NOT_STARTED 1,707**이다. 부분 WON 3개로 선택하지 않았고 모델 집계는 null, R 6회는 TARGET_NOT_EVALUATED다. 큰 보드 MODEL_SELECTED는 **UNVERIFIED**다. 128입력이 모두 counted라는 입력 결속은 Unit 4 독립 기록에 의존한다.

독립 P0가 모든 큰 batch의 work를 재현했다. 중단된 18개 호출은 확정 추론이 끝났고 안전 칸이 0인 추측 단계였다. 닫힌 칸마다 모든 숫자 제약을 다시 순회하는 hint 루프가 호출당 16,961~17,972 work를 써서 20,000 cap에 도달했다. 계수·중단 처리는 계약에 맞으며 정확성 결함이 아니라 후속 계산량 개선 대상이다(N2). 다음은 칸별 제약 index·빈 제약 생략의 동등성, work 정의와 상한을 별도 계약으로 검토하는 일이다. 이번에 상한 인상·튜닝·큰 보드 재실행은 하지 않았다.

## 독립 검토와 실행 근거

검토는 제품/시험/helper/Python/Qt/owner/Git 명령을 실행하지 않고 자체 Node 도구로 수행했다.

- 작은 raw-bitmask 10관측/169 mask의 rank 전단사. 기록 1,010 slot 중 정상 1,009개 독립 unrank 일치, 1개는 의도한 rank −1 주입이다.
- 복원추출 bank 41개 중 38개를 자체 MT19937로 rank 열까지 재현했다. 나머지 3개는 RNG 패치 시험이다. 큰 288 slot은 공개 일관성·D·공통 bank가 일치했다.
- 실제 engine 15 step와 소보드 94 step, 정책 수준 rollout 89/95 batch를 재현했다. 나머지 6개는 rollout/P0 패치 시험이다. run02 직접 evaluator 시험의 11결과는 표본 layout 원시 부재로 별도 미재생(U4)이다.
- eligibility 오류 0, shortlist 112/112, READY 선택 104/104, 부분 표본 성공 평균 선택 0이다. CROSSCHECK는 40행이며 설명되지 않은 불일치 0이다.
- 실행은 논리 시작 6, Python image 11, Job 6, policy 139, backend 502, posterior slot 530, model rollout 759, sampler work 202,246, raw mask 169, 실제 tiny engine trial 28/step 109다. 가상 step 2,129 = rollout 2,110 + engine 시험의 가상 15 + 직접 적용 시험 4다.
- Job은 suspended 생성→할당·소속 확인→resume 1회, total=observed, active/member 0과 reap/EOF/thread/handle 종료를 확인했다. run01은 사용자 코드 전 exit 101/0, 이후 5개 Job은 0/0/0이다.
- TerminateJobObject는 run02/04/05에서 정상 top 종료 뒤 active 관측으로 호출됐다. 관측 멤버 종료 코드는 모두 0이다. 종료 코드 필드는 run02에만 있으며 run04/05는 helper 상수와 event로 확인했다(N6). accounting만으로 실제 종료 부재를 단정하지 않는다.

## 비차단·미확인 처분과 보존 이력

| ID | 현재 처분 |
| --- | --- |
| N1 | 비READY basis 잔존. W1을 반영했고 원본은 불변. 이후 READY gate 또는 표기 정리를 고려 |
| N2 | P0 추측의 전체 제약 재순회. 별도 성능/동등성 개선 범위로 이관 |
| N3 | 미적용 입력 후 같은 인스턴스 STALE. 이후 UI/worker 수명 계약에 반영 |
| N4 | 실제 작은 폐루프 fallback 0. 시험 fixture와 분리 기재 |
| N5 | 실제 M/R 차이 미확보. 합성 target 시험과 분리 기재 |
| N6 | TJO 코드 필드 일부 누락. 다음 launcher에서 모든 호출에 기록 |
| N7 | 후속 Git 7기록 중 처음 2개 UTC 없음. 다음 helper에서 명령별 시작/종료 시각 기록 |
| N8 | 정수/문자열 seed의 같은 digest. 공개 값 정규화이며 영향 없음 |
| N9 | run01 stderr의 한글 경로가 ?. OS 원인은 미확인으로 보존 |

미확인 U1 BUSY 동시성, U2 인스턴스 간 소비·UI/worker 수명, U3 큰 model 경로, U4 직접 evaluator 시험행, U5 시간 한도·실시간 취소 시점, U6 Unit 5 root 개별 계수의 재검토 생략, U7 run01 OS 원인, U8 실제 미노출 설정을 유지한다. FINDINGS의 unconfirmed 배열은 이 8개와 별도 범위 밖 설명 1개로 9행이다.

**U6-R02:** 첫 Git 4건의 개별 전후 index/stream 원시는 없다. 구현자의 hash 계산 설명과 실제 보존 원시를 구분한다. FIRST_INDEX, 이후 7기록과 현재 index가 같아도 당시 4건을 PASS로 소급하지 않는다. 구현자 PARTIAL은 복구 불가능한 기록 공백을 포함해 그대로다.

U6-R01/R03 표시 원시, H01 무효 시각 초안, H02 bootstrap, P01 사전 검토 보완을 보존한다. 조율 U6-COORD-H01~H03과 독립 검토 RVI-01/RVI-02도 별도다. 이번 문서 마감의 스키마 해석 보정은 closeout root 원장에 남기며 과거와 합산하거나 제품 결함으로 바꾸지 않는다.

## 산출물과 다음 순서

외부 root는 `outputs/STAGE4_ROLLOUT_POLICY_UNIT6_2026-11-07`이다.

- 구현 `codex_01`: manifest 자기 제외 234파일 / 3,846,174 bytes, SHA256 `e6db0212b68fa33513025b92847fdb679a196d3ca75fc939d1650bcacaf6f9b2`.
- 독립 `review_claude_01`: manifest 자기 제외 42파일 / 66,672,326 bytes, SHA256 `c3860607b800488fe6c77d64431055a68bcd507b347ca58989b2ebd4c4e40839`.
- 조율 `coordinator_02`: 구현 전수 결속과 보충 산술. 최종 수용은 위 독립 판정을 따른다.
- 문서·Git 준비: `outputs/STAGE4_UNIT6_CLOSEOUT_2026-11-07/coordinator_01`. 사용자 commit/push 영수증 확인 뒤 Desktop recovery 두 파일을 별도로 교체한다.

다음 개발은 P0 계산량 개선과 큰 공개 관측의 모델 선택 경로 확인이다. 실제 일반 상급판 전체 평가, Main/Live·worker·Replay 통합, 사용자 native·전시 노트북·새 패키지는 후속 별도 범위다. 현재 순수 모듈에는 추가 native가 필요하지 않다.

Unit 2 C01/H01, Unit 3 U3-H01, Unit 4/5 비차단·미확인과 과거 실패는 유지한다. D0–D5 CLOSED/FINAL ACCEPTANCE PASS, V1 CLOSED/FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인이다. Phase2/R0-B/ActualE2, frozen 정책·Model C·holdout **2,010,000..2,010,099**와 금지 formal evidence는 미승인/미실행이다. F02 NOT_VERIFIED·과거 Qt shared FileDialog FAIL·이전 TEMP NOT_VERIFIED와 전시 노트북 PENDING도 유지한다.
