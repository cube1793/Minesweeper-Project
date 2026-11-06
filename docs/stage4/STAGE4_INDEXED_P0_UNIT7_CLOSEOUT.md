# Stage 4 Unit 7 — 색인 P0와 제한 모델 평가 마감

기록일: **2026-11-07 (Asia/Seoul)**. 구현자 `COMPLETE_BOUNDED_INDEXED_P0 / DEFAULT_LIMITED_EXPANDED_COMPLETE`는 독립 검토에서 등록 범위 안에 성립했다. 제품 필수 수정 0건, helper/evidence 필수 보완 0건이다. **계산 완료 범위의 개선이며, 실행 속도·실제 승률·효율 개선은 확립되지 않았다.**

작성 시 HEAD = local origin/main = `3670542ded239be34a1ef7f9de03a2d5a86d0950`, main, ahead/behind 0/0, staged 0이다. index SHA256은 `fc36efefc64c2cb645c2b191e554b1ecb9f742a0291ec6dc2d7fb76fb0505388`이다. Unit 6는 commit과 Desktop 검증까지 마쳤다. 이 문서는 Unit 7 source/tests 4 + 문서 6 = 10경로의 사용자 commit/push 준비 snapshot이며, 실제 마감은 영수증과 다음 Desktop destination 검증을 따른다. 실행 HEAD를 미래 commit으로 소급하지 않는다.

## 1. 변경과 수용 범위

| 축 | 독립 판정 |
| --- | --- |
| 결속·변경 범위 | ACCEPT |
| 색인 P0 의미·work | ACCEPT |
| 시험·버전·U7-P01 | ACCEPT_WITH_NOTES |
| Phase B 비용 | 산술 일치 / NO_SPEEDUP_ESTABLISHED |
| 큰 공개 관측의 모델 평가 | ACCEPT_BOUNDED |
| 실제 소보드 경로 | ACCEPT |
| 실행·보호 | ACCEPT_WITH_RETAINED_GAP |

변경된 기존 source는 `stage4_rollout.py`, `stage4_policy.py`이고, 신규 파일은 `tests/stage4_rollout_reference.py`, `tests/test_stage4_rollout_indexed.py`다. source 수는 355→357이다. 기존 355개 중 허용된 두 파일 외에는 변경되지 않았다. UI/Live/worker/Replay는 바뀌지 않았고 추가 사용자 native는 이 단위에 필요하지 않다. 일반 상급판 완주, Main 통합, 전시 노트북 수용은 후속이다.

P0 ID는 `PUBLIC_LOCAL_COST_P0_V2_INDEXED_HINT`, work ID는 `P0_WORK_V2_RESIDUAL_CONSTRAINT_EDGES`다. 추측 hint의 전역 밀도와 숫자 제약별 잔여 밀도를 한 번 계산해 해당 미지수 칸에 전달한다. 추론·5,000 subcap·안전 후보·동률·가상 전이·보상은 byte 동일하다. `pilot_work` 허용 상한은 30M으로 넓혔지만 **제품 기본값은 10M 그대로**다. 개별 P0의 20,000 work 상한도 유지했다.

추측 구간에 도달하면 안전 칸 집합이 비어 있으므로, 기존의 '칸이 숫자 제약에 포함'과 새 방식의 '칸이 그 제약의 잔여 미지수에 포함'은 같다. 따라서 동일한 Fraction 집합의 max와 동일한 최종 선택을 얻는다. 호출 사이에 hint cache를 공유하지 않는다. 이 밀도 힌트는 정확한 지뢰 확률이 아니다.

## 2. 독립 재현과 시험

API_PLAN을 읽고 검토자가 별도 작성한 기존/색인 P0가 **354/354**에서 status·reason·sequence·hint·증명된 안전/지뢰·추론 완료 여부와 각 버전의 work를 재현했다. 고유 공개 입력은 150개이며 중복 204개다. 구성은 cap 6 + 기존 정상 6 + 명시 진단 6 + 생성 진단 336이다. 생성 336개의 실제 플레이 도달 가능성은 미증명이다.

Unit 6 원시의 배치·행동에서 cap 상태 6개를 재구성했고 원 pilot ID 18/18, 입력 261이 일치했다. 실제 배치는 평가자의 상태 재생에만 사용했다. 기존 칸×제약 방문 179,457, 새 관련 edge 316, 새 제약 방문 1,106, local Fraction 316→108, 전역 Fraction 1,528→6도 재현했다. **서로 다른 work 정의의 비를 실행 속도비로 쓰지 않는다.**

### U7RV-W4 — 시험 수와 버전

고유 PASS **34 = run02/v01 PASS 5 + run03/v02 PASS 29**다. run02의 FAIL 1은 보존한다. run03은 남은 신규 9 + 기존 policy 15 + 기존 rollout 5다. **v02에서 34개를 한 번에 실행한 기록은 없다.** 기존 실제 engine 전이 시험 1개는 이 단위에서 재실행하지 않았다.

U7-P01의 원 fixture는 정확 posterior로는 배치가 하나지만 P0의 단일 제약 규칙으로는 풀리지 않는다. 두 P0는 같은 OPEN(0,1)을 골랐다. 보정 fixture는 단일 규칙으로 FLAG(0,1)→CHORD(1,1)이 증명되며 정확한 수순을 요구한다. 기대를 약화한 것이 아니다. 제품과 reference는 v01/v02가 같고 새 시험의 fixture만 바뀌었다. reference는 Unit 6 코드의 사본이며 독립 oracle이 아니다. 독립성은 검토자의 재구현이 제공한다.

## 3. U7RV-W1 — Phase B는 속도 향상 근거가 아니다

12입력 × (warm-up 1쌍 + 측정 3쌍) × 2버전 = 96묶음, 묶음당 10호출, 합계 P0 960호출이다. 보고서의 wall 중앙값과 쌍별 비 산술은 일치했다.

그러나 **8입력은 변경된 hint 구간에 닿지 않아 같은 코드를 실행**했고, 그 쌍별 비 중앙값도 **0.7684~1.0245**로 흩어졌다. 실제 hint 경로 4개의 **0.7815~0.9167**은 그 산포 안에 있다. 따라서 속도 개선은 **NOT_ESTABLISHED**다. 측정 순서도 baseline 먼저 2/3로 균형이 아니다. 절대 중앙값의 비와 쌍별 비 중앙값을 혼동하지 않는다.

`flag_preparation`이라는 timing 입력은 실제로 OPEN(0,1)을 선택한다. FLAG 준비는 별도 보정 시험과 G001_3 경로로 확인했다. wall 최소 양의 차이는 100ns, CPU 양의 최소/GCD는 15,625,000ns이고 **CPU 0은 46/96**이다. empty-call wall 중앙값 1,800ns는 차감 전 원시 기준이다. 단일 호출 CPU 개선, 안정 계산 시간, CPS와 노트북 성능은 미확인이다. 오래된 cap 상태와 새 완주의 시간을 직접 비교하지 않는다.

## 4. U7RV-W2 — 기본값과 확대 profile을 구분한다

동일한 6개 공개 snapshot × S/M/R, N=16, shortlist=6, 추측 ON, R 목표 1을 사용했다. 여섯 관측은 같은 Replay에서 나왔으며 독립 실전 보드 6개가 아니다. R 목표 1은 검증 설정이며 추천값이 아니다.

| profile | 모델 비교 완료 | fallback | 모든 후보 점수 0인 완료 요청 | 가상 WON / LOST / 미완료 / 미시작 |
| --- | ---: | ---: | ---: | --- |
| DEFAULT 10M | 6/18 | 12 | 6/6 (snapshot 000·032 × 3모드) | 226 / 1,280 / 12 / 210 |
| EXPANDED 30M | 18/18 | 0 | 9/18 (000·001·032 × 3모드) | 272 / 1,456 / 0 / 0 |

**기본값에서 완료된 여섯 요청은 모두 후보 간 후속 모델 점수 차이가 없다.** 현재 입력의 exact 생존 확률과 동률 규칙으로는 선택할 수 있지만, 비영 모델 점수를 이용한 비교 근거는 이 기본 profile에서 한 건도 얻지 못했다. 확대 profile의 12요청이 10M을 초과했고 최대는 16,754,262 work였다. 확대 18/18을 기본값의 결과로 쓰지 않는다.

점수 0은 해당 표본에서 후보 뒤 고정 P0가 모두 패배했다는 뜻이다. 실제 승리 확률 0, 실제 S 반복 정책의 전멸, 목표 기록 불가능의 증거가 아니다. S/M/R은 현재 후보의 exact eligibility와 목적을 달리 적용하지만, 가상 미래 진행에는 같은 P0를 쓴다. P0는 기본 규칙 뒤 밀도 추측을 하며 기존 Simple/Stage 4의 정밀 확률을 매 수 사용하지 않는다. **계산 완료와 선택의 유용성, 실제 성과를 구분한다.**

검토자는 가상 3,456행 전체의 action·pilot ID·B/C/X/hit와 36개 batch·점수·선택을 재현했다. DEFAULT 종결 1,506행, 시작 1,518행의 prefix, Unit 6 종결 3행, DEFAULT 완료 6요청의 점수도 EXPANDED와 같다. DEFAULT/EXPANDED의 pilot work는 각각 155,723,449 / 185,558,973이다. wall 합계 182.0186875 / 212.848374초와 CPU 177.90625 / 209.484375초는 해당 계측 조건의 기록이며 속도비가 아니다.

## 5. U7RV-W3 — 수치 동등성과 identity는 다르다

Unit 6의 `max_seconds`는 float `30.0`, Unit 7은 int 30의 exact_json 문자열 `"30"`이다. 수치 제한은 같지만 **policy request_id는 36/36 다르다**. settings_id도 같은 이유로 달라지는 코드 경로지만 원시에 기록되지 않았다. DEFAULT 구조 차이는 이 필드뿐이며 EXPANDED는 등록한 `pilot_work` 차이가 추가된다.

seed ID, root ID/근거(elapsed 제외), bank, shortlist와 선택 의미는 36/36 같다. 다른 필드를 임의로 정규화하지 않았다. 과거 요청 ID를 같은 것으로 고치거나 실패 원시를 덮어쓰지 않는다. 다음 decoder는 원래 수치 타입을 보존한다.

## 6. 실제 소보드와 실행 보호

10시도, prefix 24 + 정책 입력 23 = **47입력**, 결과는 **WON 6 / LOST 3 / GUESS_BLOCKED 1 / UNRESOLVED 0**이다. Unit 6의 동일 10경로와 행동·C·결과·X가 같다. G001_3은 FLAG 해제→OPEN을 포함하며 세 모드 C=7, X=5/7이다. G009 성공 배치는 S C=5/X=4/5, M/R C=4/X=1이다. 이 결과를 10승이나 일반 상급판 효율 개선으로 쓰지 않는다.

논리 시작 8, Python image 15, Job 8, 멤버 23(15 Python + 8 conhost)이다. suspended 생성→Job 할당·확인→resume 1회, total=observed, active/member 0, reap/EOF/thread/handle 및 controller 부재를 확인했다. run01은 사용자 코드 전 exit101, run02는 시험 실패, 후속 6run은 정상 종료다. **TerminateJobObject 실제 호출은 0**이며 새 기록 래퍼는 코드 검토만 받았다.

policy 133 / backend 810 / posterior slot 695 / model rollout 3,568 / 가상 입력 111,066 / P0+reference 93,715호출 / reference work 2,011,520 / indexed work 342,241,471 / semantic 354가 원시와 맞는다. Git 읽기 13건의 개별 전후 index는 동일하며 UI/owner/Computer Use/제품 Git 쓰기/Desktop 쓰기는 0이다.

## 7. 비차단·미확인 및 실패 이력

| ID | 처분 |
| --- | --- |
| U7RV-N1 | 비READY P0 원시에 sequence/hint 필드가 없다. 행동 미반환은 코드와 통과한 단언의 근거로 한정한다. 다음 진단은 전체 PilotResult를 기록한다. |
| U7RV-N2 | timing 순서 비균형. 원시를 보존하고 새 성능 측정이 필요할 때 순서를 균형화한다. 이번 재측정은 불필요하다. |
| U7RV-N3 | 기본 aggregate 10M으로 큰 12/18이 미완료다. 기본값 변경은 새 계약과 평가로 다룬다. |
| U7RV-N4 | TJO 래퍼의 실제 실행은 0. 과거 U6RV-N6을 실행 검증 완료로 바꾸지 않는다. |
| U7RV-N5 | reference 사본과 독립 oracle을 구분한다. 이번 등록 입력의 독립 재현은 검토자가 제공한다. |

미확인은 **U1** Unit 6 root 계수 재사용, **U2** TJO 래퍼 실행, **U3** 실제 성능·효율·M/R 우위·안정 시간·노트북, **U4** 생성 336관측의 도달 가능성, **U5** run01 OS 원인, **U6** BUSY/인스턴스 수명, **U7** 미노출 실제 설정, **U8** 단일 호출 CPU 개선이다. 개별 항목을 자동 CLOSED로 바꾸지 않는다.

U7-R01 최초 bootstrap의 개별 종료·index·stream 공백은 복구 불가로 남긴다. U7-R02 표시 잘림, U7-H01 시작 실패, U7-P01 fixture 실패, U7-H02 표현 차이를 보존한다. 구현자 고유 incident 5/12와 조율 U7-COORD-R01/H01/H02, 검토자 RVI7-01(usage 증분·키 가정 오류/보정 1회)을 구분한다. 독립 검토는 제품/기존 helper/Git를 실행하지 않았고 P0 work 73,913,444, 전이 재생 110,321의 자체 모델을 사용했다.

**Unit 6 전체 PARTIAL/U6-R02, Unit 2 C01/H01, Unit 3 U3-H01와 Unit 4~6의 한계는 소급 변경하지 않는다.**

## 8. 근거 위치와 마감

evidence root: `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_P0_INDEXED_HINT_UNIT7_2026-11-07`.

- 구현 `codex_01/OUTPUT_MANIFEST.json`: **496파일 / 11,522,350 bytes**, SHA256 `f472ac4fa0fb34ef03c8603bc7445a95bbe5104226d06e6f89c2f9974fe3cf6b`.
- 독립 `review_claude_01/OUTPUT_MANIFEST.json`: **38파일 / 628,839 bytes**, SHA256 `2777431829643c5f5a4a8b24695c08bba7758dd0c1990fa27014a5eab2be5607`.
- 조율 `coordinator_02`: review 준비의 INPUT_BINDING과 산술. 독립 검토와 구분한다.
- 문서/사용자 Git 준비: `outputs/STAGE4_UNIT7_CLOSEOUT_2026-11-07/coordinator_01`.

검토된 reference는 LF 세 개로 끝나 끝의 빈 줄 두 개가 있다(SHA256 `55544e9cc4b766b2fc725672a7da7b503d215f874955b7a4f12a1e62d8d2e1d8`). source bytes를 보존한다. 사용자 Git 검사는 **이 정확한 한 파일에만 command-local `core.whitespace=-blank-at-eof`**를 적용하고 다른 공백 검사는 유지한다. 다른 9경로는 기본 공백 검사를 받으며 전역 Git 설정은 바꾸지 않는다.

## 9. 다음 범위

다음 조율 방향은 **P0의 정밀 확률 보완과 S/M/R 목적에 맞는 후속 선택 설계**다. 확률 정확도와 선택 목적의 변경을 별도 축으로 검증한다. 공개 숫자·총 지뢰 수에서 계산한 확률은 허용되지만, 실제 배치·미공개 숫자·실제 3BV·분리 카운터는 정책에 주지 않는다.

S는 기본 추론 뒤 놓친 안전 칸과 최소 위험 판단이 중요하다. M/R은 안전한 수가 있어도 효율 경쟁 후보를 비교해야 하므로 '안전 수가 없을 때만 확률 계산'으로 충분하지 않다. 현재 후보 뒤 공통 P0라는 모델을 모드별 후속 정책으로 바꾸는 것은 새 모델 버전/계약이다. 확률·생존·국소 이득만으로 정확한 최종 E[X]/목표 확률이라고 쓰지 않는다.

기존 실패 trace에서 불가피한 추측과 증명 가능한 안전 수 누락을 구분하고, 공개 상태·모델별 재사용과 전체 예산을 정한다. 원래 요청 타입, 전체 PilotResult와 미완료를 기록한다. 무제한 재귀 rollout, 기본값/표본 수의 자동 인상, 실전 전체 평가나 UI 추가를 이번 마감으로 시작하지 않는다. 실제 구현·측정은 별도 Codex, 독립 검토는 의미 있는 묶음 단위의 Claude가 맡는다.

**D0–D5 CLOSED/FINAL ACCEPTANCE PASS, V1 CLOSED/FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인**을 유지한다. Phase2/R0-B/ActualE2, frozen 정책·Model C·holdout **2,010,000..2,010,099**와 금지 formal evidence는 열지 않는다. F02 NOT_VERIFIED, 과거 Qt shared FileDialog FAIL, 이전 TEMP NOT_VERIFIED와 전시 노트북 PENDING도 유지한다.
