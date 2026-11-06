# Stage 4 Unit 8 — 공개 정밀 확률 후속과 목적별 평가 프로토타입

기준일: 2026-11-07 (Asia/Seoul). 제품 축 **ACCEPT_BOUNDED**, 제품 필수 수정 0이다. 구현자 전체 **PARTIAL**, U8-H05, 원 OUTPUT_MANIFEST 부재와 U8-R02/R03 시점 원시 공백은 유지한다. 일반 상급판의 실용 정책, 효율 향상, 전체 Stage 4 완료를 수용한 문서가 아니다. **effectiveness NOT ESTABLISHED**다.

## 1. 현재 수용과 마감 범위

출발 HEAD와 local origin/main은 `92270322bb1d99653ce753ddb17e9bc32a1128de`, index SHA256은 `59805e796a4515778b37dce0ea24e098477407060b530add10db9937f1738aa6`이다. Unit 7의 사용자 commit/push 및 Desktop 교체 검증은 완료됐다. 이 문서는 Unit 8의 신규 source/tests 5 + 문서 6 = 11경로 마감을 준비한 snapshot이다. 실제 commit/push 이후의 receipt·현재 Git·recovery가 이 준비 문구보다 우선하며, 테스트 실행 HEAD를 미래 commit으로 소급하지 않는다.

| 축 | 처분 |
|---|---|
| 제품 Q/G | ACCEPT_BOUNDED, 제품 필수 0 |
| 원 helper/evidence | 필수 1: RV8-H1. 원 finalizer 재사용 금지 |
| H1 후속 보정 | 조율의 별도 보정 템플릿과 합산 함수 작성, PowerShell 5.1/7.6.9 각각 5사례 확인. 전체 manifest 발행 흐름 재실행 없음 |
| 원 전체 상태 | PARTIAL, U8-H05 및 원 OUTPUT_MANIFEST 부재 유지 |
| 문구 / 선택 / 미확인 | 5 / 4 / 6. 아래 개별 처분 유지 |
| Main/UI/native | 변경·새 검증 없음. 이번 계산 모듈 마감에 추가 native는 해당하지 않음 |

신규 파일은 `stage4_exact_pilot.py`, `stage4_objective_pilot.py`, `tests/test_stage4_exact_pilot.py`, `tests/test_stage4_objective_pilot.py`, `tests/stage4_pilot_oracle.py`다. 기존 source 357개는 그대로이며 전체 source는 362개다. 신규 5파일은 현재 = v01 = v02다. v02 변경은 외부 driver의 좌표 decoder 한 줄과 REGISTRATION뿐이다. 기존 정책·UI·Model C를 수정하지 않았다.

## 2. 구현 의미와 공개 정보 경계

Q(`PUBLIC_EXACT_COST_Q_V1`)는 먼저 P0 V2를 guess=False로 호출한다. 지역 규칙의 안전 수가 있으면 BASIC_RULES로 반환하고, 막히면 Unit 4의 정확한 공개 D/M으로 안전 수 또는 최소 위험 OPEN을 판단한다. 물리 FLAG는 미지수다. 공개 관측·총 지뢰 수·counted 입력 합 C·guess·prior·한도만 받으며 실제 배치, B/3BV, mode/target을 받지 않는다.

Q는 정확 안전/지뢰 집합으로 OPEN·깃발 해제·FLAG 준비 CHORD의 전체 입력 비용을 비교한다. 안전 수 부재가 정확히 확인된 경우에만 불가피한 추측 또는 GUESS_BLOCKED를 낸다. 시간/작업 중단·취소·오류는 빈 수순과 null을 반환한다. COMPLETE base만 인스턴스의 최대 256개 캐시에 보관하며, 캐시 key는 공개 grid/총 지뢰 수/prior/counter version이다. 새 요청의 0한도·취소·시간·지원 검사는 캐시보다 먼저 한다.

G(`PUBLIC_OBJECTIVE_PILOT_G_V1`)는 Unit 5의 정확 위험 eligibility와 공통 posterior bank를 사용한다. 후보 하나를 적용한 뒤 Q로 끝까지 진행한 결과를 비교한다. S는 안전 유지, M은 평균 X, R은 양의 target 달성률을 우선한다. WON이면 X=B/(C+추가입력), LOST와 정확 GUESS_BLOCKED는 0, 미완료는 null이다. 모든 후보×표본 행이 끝나야 점수/수순을 발행하며, 이번 G에는 미완료를 대신하는 fallback이 없다.

**모델 점수는 ‘후보 뒤 Q’의 값이다. 실제 한 입력 뒤 다시 G를 부르는 정책의 정확한 값이 아니다.** L2 평가는 매 실제 입력 후 G를 다시 호출하지만, G의 내부 가상 후속은 항상 Q다. mode/target은 실제 재계획 사이에 유지된다. G→G, Q 활성 중 G, Q→Q 재귀 guard가 있다. Q 활성 중 G 및 Q→Q 직접 주입 시험은 이번 범위에 없었다.

## 3. 작은 상태와 정확 안전 수 근거

- 신규 시험은 Q 15개(run03)와 G 14개(run04)의 별도 실행이다. 총 29개 PASS이며 기존 suite 전체 실행을 뜻하지 않는다.
- Unit 7 실패 trace에서 선택한 6개 직전 공개 상태를 독립 재생했다. 지역 규칙은 막혔지만 정확 안전 칸은 3~14개 남아 있었다. 구 선택 위험은 7/34, 94/451, 29/367, 17213897/77475762, 79409/348910, 2354479/10479543이고 최소 위험은 모두 0이다. 새 Q의 수순은 독립 key와 같고 모든 일관 세계에서 안전했다. 실패를 기준으로 고른 사례이므로 전체 패배의 원인 비율로 일반화하지 않는다.
- 작은 G 102건의 1,718행·점수 475개·선택 102개를 독립 재계산해 불일치 0이었다. mode/target이 달라도 공통 bank는 같다.
- 실제 engine 24 trial은 13 WON / 11 LOST, prefix 42 + 정책 52 = 94입력, G 48호출이다. 세 witness의 해당 mode별 전체 모집단이며 일반 상태의 무작위 24판 표본이 아니다.

| witness | 반복 G 성과 |
|---|---|
| G009 | S E[X]=2/5, M E[X]=1/2 |
| G001 | M/R 같은 경로, E[X]=12/35, target hit=0 |
| G010, target=6/5 | M E[X]=7/15·hit=0, R E[X]=23/60·hit=1/5 |

G010 root의 후보 뒤 Q 모델은 R hit가 전 후보 0이어서 M/R이 같은 첫 OPEN을 고른다. 이후 다시 G를 부르면 경로가 갈라진다. 이 차이는 모델 의미 차이이며 산술 오류가 아니다. E[X]는 실패를 0으로 포함한 무조건부 효용이다.

## 4. 큰 보드 완료율과 중단 원인

6개 공개 시점×S/M/R의 18요청이며, 18개의 실제 완주 게임이 아니다. 각 요청은 N16×K6=96개 가상 행을 요구한다.

| profile | 완료 | 중단 | WON / LOST / UNRESOLVED / NOT_STARTED |
|---|---:|---|---|
| 기본 exact20M/local10M/30초 | 0/18 | Q_LOCAL 12, Q_BASE_WORK 6 | 401 / 337 / 18 / 972 |
| 확대 exact60M/local30M/30초 | 3/18 | TIME 8, Q_BASE_WORK 6, Q_BASE_TIME 1 | 509 / 411 / 15 / 793 |

- 기본 Q_LOCAL 12건은 **G 합계 10M 소진**이다. 마지막 Q에 남은 local 작업량은 848~4,883이었다.
- Q_BASE_WORK 6+6건은 **개별 정확 계수 200,000 한도**다. 두 profile에서 같은 Q 호출 번호(1832/1093)가 막혔다. 이때 G exact 합계는 약 2.07M/3.15M이므로 합계 한도만 늘려서는 해결되지 않는다.
- 확대 TIME 8건은 **G 전체 30초**가 relay를 통해 Q를 중단한 경우다.
- 확대 Q_BASE_TIME 1건은 개별 2초를 쓴 것이 아니라 **부모의 남은 약 0.231초**가 base 한도가 된 경우다.
- 비교 가능한 3건은 snapshot_128 S/M/R이며, 기존에도 모델 점수가 비영이었다. 0→비영 0, 순위 변화 1, 선택·다음 입력 변화 0이다. 미완료 33건의 개선 여부는 판단하지 않는다.

root/bank/shortlist는 Unit 7 기준과 18/18 동일했다. 이는 기존 근거와의 결속 확인이며 큰 후보 구성을 새로 독립 재도출한 것은 아니다. Q 결과 92,545건은 각 행에 저장된 base 기준의 계약 정합성 issue 0이다. Phase A 6건 외 큰 base 자체는 **NOT_INDEPENDENTLY_RECOUNTED**다. 정확한 확률 사용과 실용적인 계산 완료율/효율 향상은 별개다.

## 5. 원시 집계와 문구 정정 W1~W5

원본은 수정하지 않고 이 문서와 별도 조율 처분에서 의미를 정정한다.

| ID | 마감 해석 |
|---|---|
| RV8-W1 | q_calls 92,551 = 실제 Q 92,545 + Phase A reference P0 6. local_work 340,635,671 = Q 340,613,800 + reference P0 21,871 |
| RV8-W2 | G CPU 0/양수 71/97은 바깥 call_cpu_ns, 내부 cpu_nanoseconds는 72/96. Q 내부는 61,603/30,942. 15.625ms는 process CPU 회계 tick이며 monotonic 해상도와 혼동하지 않음. 0은 비용 0이 아님 |
| RV8-W3 | 비교 불가 33행의 old_zero_to_nonzero=false는 의미상 null/미확인. 개선 없음의 증명이 아님 |
| RV8-W4 | FINAL_MANIFEST.json의 READY_FOR_LAST_WRITE_PUBLICATION은 갱신되지 않은 상태. 원 stdout은 발행 예정 문구이며 성공 receipt가 아님 |
| RV8-W5 | 개별 cap, 합계 cap, 부모 시간 잔여를 4절처럼 구분 |

그 밖의 실행 집계는 G 168, 실제 backend 12,628 + 의도적 실패 주입 1, posterior slot 976, model 행 5,640, 가상 입력 112,665, 작은 engine 24/94, oracle mask 41, 방문 witness 3/128이다. exact_work 64,575,079는 backend 64,173,492 + sampler 401,587이며 Q exact와 중복 합산하지 않는다. 8 Job / 15 Python / 23 멤버, resume 1회·정리 8/8, 실제 TerminateJobObject 0이다.

## 6. H1 보정과 원 실패 보존

원 `finalize_manifest.ps1`은 ordered 사전 목록에 `Measure-Object bytes -Sum`을 사용했다. pwsh 7.6.9에서 Sum=null이 되고 long 0으로 변환돼 최종 bytes 검사가 실패한 원인을 독립 탐침으로 확인했다.

조율은 원본을 건드리지 않고 `STAGE4_UNIT8_CLOSEOUT_2026-11-07/coordinator_01/helper_correction/`에 명시적 Int64 누적 함수와 해당 한 줄을 대체한 SOURCE_ONLY 템플릿을 만들었다. 빈 목록·ordered 사전·일반 객체·32bit 초과 합·0 혼합 5사례가 PowerShell 5.1과 7.6.9에서 각각 일치했다. **합산 보정 검증이며 전체 finalizer 발행 실행 검증이 아니다.** 원 finalizer 재사용은 금지하며 미래 단위는 새 root에 보정본을 결속하고 사전 확인해야 한다. 원 Unit 8을 재실행하거나 원 manifest를 복원하지 않았다.

원 OUTPUT_REGISTRATION은 613경로, 실패 뒤 추가된 9경로를 포함한 현재 자료는 622파일/125,293,213 bytes다. 조율의 외부 `coordinator_02/CODEX_INPUT_MANIFEST.json`을 검토 입력 결속에 사용했다. 원 OUTPUT_MANIFEST는 계속 부재이며 PARTIAL은 유지한다. U8-R02/R03 시점 원시 공백, 최초 Python 101의 OS 원인 미확인, U8-H01~H05와 읽기/명령 4/4·helper 4/4·고유 incident 9/12 이력은 보존한다. 후속 조율 합산 확인을 원 실행 실적으로 합치지 않는다.

검토 자체의 RV8-I01 관찰용 PowerShell 5.1 비정상 종료와 RV8-I02 witness_pool.size 키 오류도 보존한다. 올바른 pool 크기는 128이며 CROSSCHECK에 기록돼 있다.

## 7. 선택·미확인과 다음 범위

- O1: Q 활성 중 G, Q→Q 직접 주입 시험 부재. guard 코드 확인과 구분한다.
- O2: COMPLETE base 캐시 재사용으로 완료 여부가 G 내부 평가 순서/캐시 상태에 의존한다. 결정적이고 계약에 명시돼 있으며 성능 변경 시 보존·기록해야 한다.
- O3: 종단 직후 시간 초과 시 종결 행과 중단 reason이 공존할 수 있다. 원시 발생 0이며 G는 점수를 발행하지 않는다.
- O4: BASIC_RULES 빠른 경로는 전역 정합성을 확인하지 않는다. 계약상 허용되며 실제 배치에서 만든 평가 상태와 구분한다.
- U1~U6: 실제 미노출 설정, run01 OS 원인, 큰 base 자체 재계수, 큰 후보 구성 재도출, 미완료 요청의 개선, 이번 독립 검토에서의 시험 재실행은 미확인/미실행이다.

다음 후보는 기존 근거에서 확인된 **개별 Q cap·반복 계산·캐시 재사용과 전체 시간 예산을 분리해** 완료율을 개선할 수 있는지 설계하는 것이다. 총 한도 자동 인상, 실제 상급판 효율 평가, Main/Live 연결은 자동 시작하지 않는다. Stage 3의 50/50·고립 추측·확정 오프닝·확정색 갱신 메모는 별도 후속이며 Unit 8 수용에 섞지 않는다. 전시회 패키지·대규모 리팩토링·저장 자료 삭제/정리는 이번 범위가 아니다.

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, V1 CLOSED/FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인, Phase2/R0-B/ActualE2 미승인·미실행, frozen 정책·Model C·holdout 2,010,000..2,010,099와 금지 formal evidence 경계를 유지한다. Unit 2 C01/H01, Unit 3 U3-H01, Unit 6 PARTIAL/U6-R02, Unit 7 U7-R01 및 모든 이전 실패/제한은 소급하지 않는다.

## 8. 근거 위치

공통 root: `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_PUBLIC_EXACT_OBJECTIVE_PILOT_UNIT8_2026-11-07`.

- 구현: `codex_01/REPORT_KO.md`, 원시 runs 및 실패 원장. 원 OUTPUT_MANIFEST 없음.
- 외부 결속: `coordinator_02/CODEX_INPUT_MANIFEST.json` (622파일/125,293,213 bytes).
- 중단 원인 조율 대조: `coordinator_03/STOP_CAUSE_DERIVATION.json`.
- 독립 검토: `review_claude_01/REVIEW_REPORT_KO.md`, `FINDINGS.json`, `CROSSCHECK.json`.
- 독립 검토 OUTPUT_MANIFEST: 자기 제외 27파일/456,131 bytes, SHA256 `aa12e039736d71f02494b853f5b6f6b0ff768cf76d10abb8f92ab2da6045c1da`.
- 이번 문서·Git 준비와 H1 후속: `STAGE4_UNIT8_CLOSEOUT_2026-11-07/coordinator_01`.

전시 노트북 수용은 PENDING이다. 계산 모듈 수용만으로 native·패키지·일반 효율을 PASS로 만들지 않는다.
