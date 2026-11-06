# Stage 4 Unit 5 — 후보 수순 근거의 한정 수용

작성: **2026-11-07 (Asia/Seoul)**. 공개 확률로 OPEN·깃발 준비·CHORD 수순의 비용, 생존, 직접 대상의 0 사건을 계산하는 공통 기반을 마감한다. 독립 판정은 **ACCEPT_BOUNDED_CANDIDATE_EVIDENCE**이며 필수 제품 수정 0, 필수 helper/evidence 보완 0이다. 최종 행동 선택이나 일반 효율·승률은 판정하지 않았다.

## 권위와 범위

실행 출발 HEAD는 **9545f6368898d1f0679d178cd1dea5cdf8164ab9**다. 기존 source 345개를 보존하고 아래 3파일을 추가해 현재 source는 348개다. 이후 문서 commit을 실행 HEAD로 소급하지 않는다.

| 신규 파일 | SHA256 |
| --- | --- |
| `stage4_candidates.py` | `bb598011f2753911a6425a53f3654d16c534a38e05539ff5eb64232661920abc` |
| `tests/test_stage4_candidates.py` | `9b62709e712be7ab86d12cbdf8cb58dc99d2e4ab0872f68e9f986c643baad2ac` |
| `tests/stage4_candidates_oracle.py` | `43aa79baf4e40675aa9d8196dea671c18371620c808573e74450957ebaaf038d` |

실제 실행된 제품 source는 v01뿐이다. draft01은 미실행이며, v01과의 차이는 batch의 Z≤Ws를 반영 전에 확인하는 10줄이다. 제품/API와 후보/산술은 ACCEPT, 예산/실패/실행계약은 ACCEPT_WITH_NOTES, 독립 A/B/C 재현은 PASS다. 구현자의 COMPLETE_BOUNDED_CANDIDATE_EVIDENCE를 이 범위에서 수용한다.

## 공개 API와 후보의 의미

`analyze_candidates(CandidateRequest, cancelled=...)`는 공개 관측·전체 지뢰 수·한도·prior만 받는다. 실제 배치, seed, 3BV, active/wasted, clock, mode, target은 받지 않는다. 물리 FLAG는 identity에 남고 추론에서는 미지수다. 불변 DTO와 정확한 정수/Fraction으로 결과를 기록한다.

후보군 `progress_preparations_evidence_v1`은 다음을 열거한다.

- HIDDEN의 OPEN은 1입력, FLAGGED의 해제 FLAG→OPEN은 2입력이다.
- 양수 공개 숫자 주변에서 숫자와 같은 개수의 최종 FLAG 집합 F를 고른다. 현재 FLAG와 다른 칸을 행 순서로 toggle한 뒤 마지막에 CHORD를 수행하는 수순이며, 비용은 변경 칸 수+1이다.
- 대상 T가 없는 CHORD와 편집이 필요한 1대상 CHORD는 제외한다. 기존 1대상 CHORD와 생존 0 후보는 기록에 남긴다.

미래에 준비를 공유할 것이라 가정해 비용을 할인하지 않는다. 다음 실제 관측에서 다시 계산한다. 같은 sequence가 아닌 후보를 국소 비율만으로 병합·제거하지 않으며 정렬 순서를 추천 순위로 부르지 않는다.

Ws는 직접 대상 T가 모두 안전한 공동 사건의 배치 수, Zt는 T와 각 대상 t의 이웃이 동시에 안전한 배치 수다. Ws/D, Zt/D, Ws>0일 때 Zt/Ws를 반환한다. **0≤Zt≤Ws≤D**이며 Ws=0의 조건부 확률은 null이다.

target_count는 생존 시 새로 열리는 안전 칸 수의 하한이다. `|T|*Ws/(D*cost)`는 생존을 가중한 직접 대상 하한의 국소 비율이며 최종 Efficiency/IOE가 아니다. 0 대상이 5칸이어도 같은 오프닝 하나일 수 있다. ZERO_OVERLAP_WITNESS는 cost 1/T 7칸/0 대상 5칸/8이웃 연결 영역 1개로 이 중복을 확인한다.

S/M/R의 위험 허용만 표시한다. 추측 OFF와 안전 칸이 있는 S는 생존 1만, M/R 추측 ON은 생존>0을 허용한다. S에 안전 칸이 없으면 HIDDEN+FLAGGED 전체에서 최소 M인 생존 가능한 직접 OPEN만 허용한다. 최선 후보, 행동 실행, 종단, E[X], 목표 도달 확률은 반환하지 않는다.

## 한도·중단·미완료

상한은 480칸, 생성 시도 4,096, 후보 2,048, 별도 조회 사건 512, backend 호출 33, 합산 work 500,000, 협력 시간 10초다. 개별 Unit 4 호출은 480/16/200,000/2초와 남은 전체 예산 이하를 유지한다. base D/M을 먼저 확정하고 알려진 0/1·단일 marginal 증명을 재사용하며 필요한 사건만 16개씩 요청한다.

후보 목록, 사건 수집, 근거 전체의 완료를 구분한다. base 이후 자원/취소 중단은 PARTIAL, callback/backend 오류는 ERROR로 정확한 근거만 보존한다. Ws만 확정됐다면 그 값과 eligibility는 유지하고 미확정 Z는 null로 둔다. 모르는 값을 0이나 false로 바꾸지 않는다. 후보 부재를 WON/LOST/GUESS_BLOCKED로 해석하지 않는다.

중단 뒤 materialize는 추가 backend/callback 없이 기존 결과를 구성한다. 기계적 상한이 있지만 협력 시간 바깥의 처리이므로 hard real-time이 아니다. consumer는 QPC perf_counter, Unit 4는 약 15.625 ms 단위의 monotonic을 쓴다. 단일 wrapper 포함 elapsed를 일반 성능 근거로 쓰지 않는다.

## 독립 검증

새 시험은 **A 25개(run01)와 B 1개(run02)의 별도 실행**이며 각각 failure/error/skip 0이다. 기존 Unit 1~4 suite와 합산하지 않는다.

| 축 | 독립 확인 |
| --- | --- |
| A 작은 공개 관측 | 24관측(일관 21, D=0 3), bitmask 2,761, 구조 후보 168, 후보×배치 3,038. 후보·사건을 raw grid에서 별도로 생성하고 모든 값 일치 |
| 공개 identity | request_id 27개, candidate_id 2,541개를 공개 필드로 재현해 일치 |
| A 전체 응답 | ERROR/PARTIAL 포함 83응답. null이 아닌 수 3,349개는 정확하고 미확정 1,169개의 0/false 치환은 없음. 후보 접두 목록과 완료 flag도 일관 |
| B 실제 엔진 의미 | 339 macro, 원자 입력 1,403(prefix 828+후보 575)을 별도 Node 엔진으로 행 단위 재생. 비용·생존·안전 공개 하한 모두 일치. 후보 48개의 Ws/Zt 집계도 일치 |
| C 큰 공개 관측 | 6 snapshot의 후보 2,373, 0 대상 2,976. 고유 사건 4,699(새 조회 1,749와 base 증명 2,950)를 전부 독립 재계수. 미재계수 0 |

B의 기록은 패배 CHORD의 안전 칸 부분 공개 112 macro, flood의 안전 FLAG 공개 172칸, 승리 자동 FLAG 40칸, 생존 다중 0 대상 16 macro, 후보 FLAG 해제 116입력/준비 120입력이다. 서로 다른 단위를 구분해 일치했다. B는 A의 보존된 후보를 사용했고 새 consumer 호출은 0이다.

C는 Unit 4에서 독립 재구성된 공개 snapshot을 재사용했다. 원 Replay128을 다시 실행하지 않았다. 별도 component counter로 정확히 계산했으며 전체 2^480 열거나 표본 근사로 대신하지 않았다. Unit 4 Claude counter는 원본과 같은 hash로 C에 재사용됐고, A bitmask와 B 엔진은 별도 구현이다.

| after_inputs | 후보 | 새 조회 사건 | base 증명 | 중복 참조 | backend 호출 | work |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 480 | 480 | 480 | 0 | 31 | 542 |
| 1 | 482 | 457 | 511 | 33 | 30 | 3,783 |
| 32 | 466 | 296 | 625 | 211 | 20 | 89,438 |
| 64 | 371 | 211 | 512 | 162 | 15 | 71,690 |
| 96 | 323 | 172 | 454 | 136 | 12 | 33,990 |
| 128 | 251 | 133 | 368 | 108 | 10 | 36,654 |
| 합계 | 2,373 | 1,749 | 2,950 | 650 | 118 | 236,097 |

참조 5,349 = 생존 2,373+0 대상 2,976 = 새 조회 1,749+base 증명 2,950+중복 650이다. 생존 Ws=0/D/중간 분포는 537/94/1,742, 0 사건 Z=0/D/중간 분포는 1,433/0/1,543으로 일치했다. 6개 모두 COMPLETE지만 일반 상급판의 최종 정책·효율·승률을 증명하지 않는다.

## 비차단·미확인 처분

| ID | 마감 disposition |
| --- | --- |
| U5RV-N1 | S의 안전 칸 부재 규칙은 “생존 가능한 최소 M의 직접 OPEN”으로 해석한다. 모든 칸이 지뢰인 ALL_MINES 2후보는 허용하지 않는다. API_PLAN 사전 등록 및 Unit 2 routes와 같고, 일반 6 snapshot의 차이는 0이다. 제품 변경 없음 |
| U5RV-N2 | Z>Ws, Fraction만 불일치, 잘못된 batch 상태, 수치가 있는 비EXACT 행, 잘못된 work, base marginal 검증, exact base 상실의 7종은 **코드 검토·원시 미관측**이다. 실제 주입한 재정렬/중복/누락/범위 밖/request_id·base 불일치 등과 구분하며 추가 시험을 요구하지 않음 |
| U5RV-N3 | helper core의 전체 변경을 기록한다. termination_reason/termination_active_before 필드, finally/fallback 사유 기록 추가, QT_QPA_PLATFORM=offscreen 설정 제거, Job 이름 접두 MinesweeperSupplement_→MinesweeperUnit5_. 조건·호출 지점과 Account(job) 횟수는 동일하며 제어 흐름 변경 없음이라는 독립 판정을 유지 |
| U5RV-N4 | FINAL_STATE.start_utc 값은 +09:00 표기지만 TIMING의 +00:00과 같은 시점이다. 필드명 주의로 기록하고 원본 보존. 이전 9시간 오류의 재발이 아님 |
| U5RV-N5 | run02에서 “실제 종료된 멤버 0”의 결정적 근거는 관측 exit code 0/0/0(지정 종료 code 0xEE=238이 아님)이다. Job accounting terminated=0만을 근거로 하지 않음 |

미확인 4건도 유지한다. **U5RV-U1**은 최초 tool controller(pid 38540)의 당시 정확한 identity 부재를 증명할 원시가 없고 boolean만 있다. 나중 부재 조회로 과거를 메우지 않는다. **U2**는 backend 내부 취소 True/시간 만료 pending_stop 경로 미시험(코드 읽기는 일치), **U3**는 최초 잘린 표시 stream 미보존, **U4**는 실제 runtime 설정과 단일 elapsed의 일반화다. U2가 후속 실행 계층에 필요하면 별도 신규 검증에 포함하며 이번 관측으로 소급하지 않는다.

## 실행·보호·이력

consumer 89 = run01 83+run03 6이다. backend 시도 248 중 실제 Unit 4 진입은 246이며 무응답/예외 2건은 work 미확정으로 표시했다. 알려진 work는 256,954다. 전체 처분은 COMPLETE 39 / PARTIAL 22 / INCONSISTENT_INPUT 3 / UNSUPPORTED 2 / CANCELLED 1 / ERROR 16 / INSUFFICIENT 6이다. 의도한 음성 시험과 incident를 혼동하지 않는다.

논리 시작 3, Python image 6, Job 3개다. 각 Job의 3멤버는 suspended 생성→할당·소속 확인→resume 1회, total=observed=3, 최종 active/member 0, reap/EOF/thread/handle 종료가 기록됐다. run별 controller 부재는 원시가 있고, 최초 tool controller는 위의 U1과 별개다.

run02는 정상 top 종료 뒤 finally에서 active 1을 관측해 자기 Job에 TerminateJobObject(0xEE)를 호출했다. 멤버의 관측 exit는 0/0/0이다. OS 전체 정리나 모든 미시험 실패 경로를 보장하지 않는다.

시작 UTC는 2026-11-06T16:38:35.5305751Z, KST는 2026-11-07T01:38:35.5305751+09:00이다. +1/+3시간, soft/hard, 새 시작 금지와 마감 예비 산술은 독립 일치했고 이전 UTC 오류를 반복하지 않았다. 구현자 U5-R01 표시 잘림과 U5-R02 sandbox Git ignore 경고를 보존하며 제품/launcher 실패는 0이다.

독립 검토는 약 25분이고 고유 incident 3/5(한글 표시, 빈 reduce, CRLF 비교)를 별도로 보존했다. 검토 mask 6,202, 원자 전이 1,403, 큰 component work 702,730이다. 제품·제공 helper·Git 명령·원본/memory 쓰기는 0이었다.

현재 source 348, 기존 345/tracked 417, END 보호 762항목과 구현자 manifest 237파일이 일치했다. 시작·종료 index는 `4d70da79c35be5cab3e672f8b95fe312e7b04a8dc06b9004dac64f8e30eecb2d`다. 문서 마감은 새 제품 실행 판정이 아니다.

## 근거와 다음 단계

evidence root: `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_CANDIDATE_EVIDENCE_UNIT5_2026-11-07`.

- `codex_01`: manifest 237파일/23,793,280 bytes, SHA256 `e5167ea03a549b99b4cae262631a0b13bb39e60832de05d0a2ad840eca49146b`.
- `review_claude_01`: manifest 29파일/254,977 bytes, SHA256 `f2aa05c047da5c171543378c6afa54fd96eda59f2ae1a96fd719fbda3b6d410a`. REVIEW_REPORT, FINDINGS, CROSSCHECK, 독립 tools/raw_derived를 참조한다.
- `coordinator_02`: 산술과 결속. 독립 검토를 대체하지 않는다.
- 문서·사용자 Git 준비: `STAGE4_UNIT5_CLOSEOUT_2026-11-07/coordinator_01`. **신규 source/tests 3 + 문서 6 = 9경로**를 묶고 사용자 commit/push 검증 뒤 Desktop recovery 2개를 별도로 교체한다.

다음은 후보 근거로 일반 보드에서 실제 선택할 S/M/R 정책과 제한 선행 탐색·근사 목적·평가 방법을 설계하는 일이다. 기존 작은 exact 계획기를 비교 기준으로 두고, 국소 비율과 최종 IOE/목표 확률을 구분한다. Main/Live·worker 통합, 사용자 native와 전시 노트북은 후속이며 이번 독립 계산 모듈에는 추가 native가 필요하지 않다.

[Unit 4](STAGE4_PUBLIC_COUNTS_UNIT4_CLOSEOUT.md), [Unit 3](STAGE4_EVALUATION_UNIT3_CLOSEOUT.md), [Unit 1·2](STAGE4_OPENING_PLANNING_FOUNDATION_CLOSEOUT.md)의 수용·PARTIAL·C01/H01/U3-H01과 과거 실패는 보존한다. D0–D5 CLOSED/FINAL ACCEPTANCE PASS, V1 CLOSED/FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인을 유지한다. Phase2/R0-B/ActualE2, frozen 정책·Model C·holdout 2,010,000..2,010,099와 금지 formal evidence는 미승인/미실행이다. F02 NOT_VERIFIED·과거 Qt shared FileDialog FAIL·이전 TEMP NOT_VERIFIED·전시 노트북 PENDING도 그대로다.
