# Stage 4 Unit 10 — 독립 정확 계수기와 합산 작업 예산

기준일: 2026-11-07 (Asia/Seoul). 구현자 **COMPLETE_BOUNDED_STANDALONE_COUNTS**가 등록 범위의 source와 원시에서 성립한다는 독립 판정이다. 필수 제품 수정 0, 필수 helper/evidence 보완 0이다. 비차단 관찰 5건과 정보 1건은 아래 처분대로 보존한다. 전체 Stage 4, 실전 효율, 일반 안정 시간은 판정 대상이 아니다.

## 1. 수용 범위와 현재 소스

| 축 | 독립 판정 |
|---|---|
| 제품/API·수학 | ACCEPT_BOUNDED |
| 과금·중단·메모 | ACCEPT_BOUNDED |
| 측정 주장 | 이 기계의 bounded 관측으로 수용 |
| 실행/보호 | ACCEPT |

출발 HEAD와 local origin/main은 `f10c4346641e7d200e83573e9cbc35554e2b09a8`, index SHA256은 `e996faa8892c933f774bb84773039eaca9430fe0318500734e5162db7991b03d`다. 신규 파일은 `stage4_belief_counter.py`, `tests/test_stage4_belief_counter.py`, `tests/stage4_counter_oracle.py` 세 개이며 current=v01=v02가 같다. 기존 source 362개는 불변이고 현재 source는 365개다. 이 마감은 source/tests 3개와 문서 6개의 총 9경로(A4/M5)를 한 번에 묶는다. tracked는 439개에서 443개가 될 예정이다. 실제 Git receipt·현재 Git·postcommit recovery가 이 준비 시점 문구보다 우선한다. 시험 실행 HEAD를 새 commit으로 소급하지 않는다.

현재 Q/G는 **Unit 8 기준 그대로**이며 새 계수기를 호출하지 않는다. Unit 9 결합 후보도 미채택·원복 상태다. 이번 모듈은 독립 base D/M 계산이며 Main/Live·worker·UI·Replay·정책 선택 경로를 바꾸지 않았다. 이번 수용에 추가 native는 해당하지 않고 전시 노트북 수용은 별도 PENDING이다.

## 2. 공개 API와 계산 계약

`CountRequest`는 공개 observation, num_mines, prior_id, `CountLimits`만 받는다. 물리 FLAG(-3)는 identity에 남지만 계수에서는 HIDDEN과 같은 미지수다. 실제 배치·미래 입력·C·mode·target·rank·3BV·비공개 분리 카운터를 받지 않는다. 행동·수순·E[X]·목표 확률·공동 사건 W를 반환하지 않는다.

기본 겸 최대 한도는 480칸, 합산 작업 200,000, 협력 시간 2초, component 메모 16,384 entry/1,000,000 scalar다. `units_total = primary + auxiliary`이며 primary는 강제 배정·분기 시도·DP 곱셈, auxiliary는 준비·제약·제약칸·메모·histogram·발행 6계열이다. 각 방문 전 또는 길이를 아는 bounded loop 전에 과금한다. 정렬·bit 연산·comb·Fraction gcd·정준 JSON/hash 등 builtin을 CPU 명령별로 세는 것은 아니다. 협력 한도이며 hard real-time 보장이 아니다. oversized DTO의 identity 비용은 O02를 따른다.

내부 메모 key는 전파 후 free와 정준 잔여 제약이며 ways/marginal histogram을 저장한다. scalar는 free 1+잔여 제약당 2+ways term당 2+marginal cell당 1+각 marginal term당 2다. 공간이 부족하면 store만 생략한다. 한도 0에서는 lookup/store와 메모 전용 직렬화를 하지 않는다. component 종료/중단 뒤 메모 수명이 끝나며 호출 간·READY·전역 결과 캐시는 없다. 내부 dict alias가 저장값을 변조하는 경로가 없음을 정적으로 확인했다. 같은 문제 재호출은 새 예산을 쓴다.

DTO/type/비호출 callback 오류는 계산 전 예외다. 지원 판정은 cell→prior, 지원된 요청의 checkpoint는 callback 오류/비bool·True→시간, 과금 직전에는 작업 한도 순이다. publish 마지막 검사까지 끝난 경우에만 모든 D/M을 한 번에 발행한다. 증명된 모순만 D=0/M=null이고, 나머지 미완료는 D/M=null이다. API `problem_id`와 `request_id`, backend/work 버전은 분리하며 정규화 float 2.0을 유지한다. 기존 reference identity와 같다고 주장하지 않는다.

## 3. 독립 계수와 제한 검증

API 시험 **10/10**은 run01/v01이며 B/C/D는 v02다. 제품·시험·oracle·driver·core는 byte 동일하고 부모 콘솔 표시 투영 한 줄만 바뀌었다. 과거 Unit 8/9 시험과 합산하지 않는다.

등록 작은 문제는 28개·918 mask(26 COMPLETE/2 모순)다. 검토자가 생성 규칙/seed를 따로 구현하고 제품 import 없는 bitmask로 D/M/Fraction을 전부 다시 셌다. 큰 8문제는 Unit 9 독립 frontier-DP의 바이트 동일 사본을 이번에 새 실행해 D와 모든 M을 확인했다. 큰 문제 FDP work 합계는 431,330이고, 작은 문제의 추가 FDP 대조 405까지 합치면 총 431,735다. 다시 세지 못한 문제는 0이다.

| hard 공개 상태 | D | 닫힌 칸 | 새 측정 완료 | primary | auxiliary | 합산 work |
|---|---:|---:|---:|---:|---:|---:|
| a14e1857 | 978,313,118,206,356 | 179 | 3/3 | 1,104 | 48,800 | 49,904 |
| 0e08c76d | 7,941,240 | 142 | 3/3 | 811 | 44,166 | 44,977 |

hard 기대표 321행은 과거 Unit 9 구현자 B_1/B_6에서 추출한 값의 결속이다. 당시 독립 전 행 일치 요약과 이번 **새 FDP 재계수**를 구별한다. 기대표 추출 자체를 새 독립 oracle 성과로 세지 않는다. 기존 여섯 snapshot은 reference와 새 계수기 모두 측정 18/18 COMPLETE다.

독립 검토는 COMPLETE 112건(B82/A30), 반복 포함 M 21,428행(B11,648/A9,780)의 좌표 유일성·전체 coverage·범위·기약분수·ΣM=N×D를 확인했고 위반은 0이다. identity는 새 B 결과 232건을 Python JSON의 float 표기까지 재현해 전부 일치했다. reference identity는 정의가 달라 재계산하지 않았으며 대응 관계로 남긴다.

## 4. 과금·중단·메모 검증

| 단계 | 새 호출 / reference 호출 | 새 합산 work / reference legacy work |
|---|---:|---:|
| A API 시험 | 166 / 0 | 9,500 / 0 |
| B 작은 oracle | 28 / 0 | 2,505 / 0 |
| C 고정 8문제 | 8 / 6 | 131,911 / 5,520 |
| D warm-up·측정 | 32 / 32 | 527,644 / 1,622,080 |
| 합계 | 234 / 38 | 671,560 / 1,627,600 |

실제 API 시도는 총 272다. 새 합계 671,560=primary18,124+auxiliary653,436이며 비완료 지출 7,520도 포함한다. reference WORK_LIMIT 8회의 1,600,000을 포함한 legacy work 합계는 1,627,600이다. 원시 gzip member 각각과 reserve/settle을 조인해 전수 합산했다. 사전 예외 2건은 결과 객체와 지출이 없고, 시험 내부 `_Budget.spend(-1/True)` 두 거절은 API 시도가 아니며 지출 0이다.

spend 지점 49곳의 선과금을 정적으로 확인했다. source의 작업 순서를 옮긴 독립 검토 재생은 200호출의 모든 진단 필드와 D/M이 일치했다(57,248 checkpoint/143,916 units). 이는 source와 원시의 일치 확인이지 독립 계수가 아니다. run04는 같은 문제의 반복으로 행·진단 동일성을 확인했다.

작은 pair `[[-2,1,-2]]`, N=1은 손 추적으로 115 units, 101 spend, 104 checkpoint, 메모 2 entry/14 scalar다. cap1..114의 막힌 계열 분포가 원시와 같고 9계열 모두 실제 cap 중단을 밟았다. 정확 임계115는 COMPLETE,114는 발행 중 WORK_LIMIT이다. 메모 0/작은 한도/default의 결과 동등성과 skip을 확인했다.

fake clock/callback의 prepare·publish.before·publish.rows·publish.final 및 모순 마지막 검사에서 중단할 때 원자성을 유지했다. 모든 행을 만든 뒤 마지막 검사에서 막혀도 D/M은 null이다. comb 고장 주입도 지출 8을 보존한 ERROR/null이었다. 이런 정상 시험 중단과 운영 incident는 구별한다.

## 5. 시간 관측과 실행 정리

warm-up16회 뒤 8문제×3쌍=측정48회이며 사전 AB/BA 순서를 지켰다. hard 새 API의 벽시계 중앙값은 각각 13.601/12.231ms다. reference는 200,000 legacy work에 막혀 완료하지 못했으므로 완료 시간의 속도 배율을 만들지 않는다. 기존6관측의 완료 비퇴행을 확인했지만 모든 쉬운 상태에서 더 빠르다는 주장은 없다.

API 시간에는 identity·과금·메모·발행이 포함되고 DTO 구성과 to_dict/JSON/gzip/write-fsync는 밖이다. CPU는 0과 15.625ms tick 표본이 있으며 0은 무비용이 아니다. 무계측 구현과 과금 overhead를 분리하지 않았다. 원장 `timing_totals_ns`는 A 전체(run03+04)와 B 전체(run01..04, 시험·warm-up 포함)의 합계이며 측정48회만의 합계가 아니다(O04). 이 기계의 작은 반복 관측을 일반 안정 시간·CPS·실전 효율로 확대하지 않는다.

4 Job×3멤버, Python image8개다. suspended 생성→Job 할당·신원 확인→resume1회→전체 graph→release→제품 import 순서를 확인했다. 종료는 active/member0, PID+생성시각·exit·EOF·스레드/handle·channel·controller 회수로 결속했다. run02 TJO 요청1회에서 conhost exit0(요청238과 다름)이 실제 종료 멤버0의 결정 근거다. Job accounting의 terminated0만으로 증명하지 않는다(O03).

구현의 원 시작은 2026-11-07 08:46:26 KST, 보충 재개는 09:11:09 KST다. 같은 절대 예산을 이월했으며 시작4/12, image8/24, count272/1500과 work 한도 안에서 마감했다. 독립 검토는 10:03:54 KST 시작, 약10:33 KST 종료로 soft 안에 끝났다. 새 Node 도구6개 exit0, 보정/incident0이며 제품·시험·helper·Git·Python·원본/메모리 쓰기는0이다.

## 6. 실패·정정과 비차단 처분

원 codex_01 PARTIAL/PREIMPLEMENTATION_CONTRACT_STOP은 유지한다. 조율 v1.0 §7C가 칸별 표 대신 요약 JSON을 지정했고, U10-I01 두 발생을 남긴 뒤 버전 표기·출처만 v1.1로 정정했다. 후속 RESOLVED_IN_SPEC_FOR_RESUME_ONLY는 원 중단의 소급 PASS가 아니다. U10-I02는 base Python 메타데이터 읽기 EPERM 보정1이며 Python bootstrap 재시도가 아니다.

U10-I03은 run01의 부모 콘솔 표시 투영이 null이던 사건이다. durable external_exit.json이 먼저 올바른 값을 보존했고 `[pscustomobject]` 투영 한 줄만 고쳤다. A를 재실행하지 않고 B 이후의 표시로 보정했다. 누적 읽기보정1/helper1/제품0, 고유incident3/raw4, venv bootstrap재시도0을 보존한다.

| 발견 | 마감 처분 |
|---|---|
| U10R-O01 | 재귀 깊이 상한이 없어 극단적 분기/깊은 부모 stack에서 INSUFFICIENT 대신 원자적·과금 유지 ERROR가 날 수 있음. 원시 사례 없는 UNCONFIRMED. 부모 통합 전 문서화 또는 명시적 깊이 한도 검토. 이번 필수 수정 아님 |
| U10R-O02 | 지원 판정 전 전체 grid identity를 계산하므로 oversized DTO의 과금 밖 비용은 O(grid). 481칸 시험은 계약대로 UNSUPPORTED. 부모 입력 크기 제한/지원 후 identity 설계를 후속 검토하며 hard 시간 상한을 주장하지 않음 |
| U10R-O03 | TJO 실제 종료0은 exitcode0≠238에 근거한다고 명시. 원시/코드 재실행 없음 |
| U10R-O04 | timing_totals_ns의 전체 run 범위를 위에 명시. 원 원장 값/라벨은 수정하지 않음 |
| U10R-O05 | 기존 검토 core의 MinesweeperUnit9Resume_ Job 접두 유지. 실제 신원은 PID+생성시각이며 표시 문제로 기록. core hash를 바꾸지 않음 |
| U10R-I01 | Unit10 auxiliary48,800/44,166과 Unit9 auxiliary25,021/22,695는 정의가 달라 비교하지 않음. primary1,104/811의 일치와 구별 |

조율의 원 기대표 지정 오류와 메타데이터/표시 절단 보정도 원 root의 원장에 유지한다. 문서화가 모든 선택 권고의 FIXED/CLOSED를 뜻하지 않는다.

## 7. 다음 범위와 영구 경계

다음 후보는 새 계수기의 Q/G 연결 설계다. 실패·취소·오류를 포함한 `units_total`의 부모 차감, 기존 sampler/root/legacy work와의 별도 회계·비교 단위, oversized DTO·깊은 stack의 반환 계약을 먼저 정한다. 이번 단독 성공이 기존 G의 완주율이나 효율을 개선했다는 뜻은 아니다. Q5000/30초와 Unit9 채택 기준을 소급 변경하거나 READY 결합 후보를 다시 적용하지 않는다.

실전 S/M/R 평가, UI/Live·worker·Replay 연결, 전시 노트북, 패키지, Stage3 50/50·오프닝·표시, 저장 자료 정리는 별도다. 원 Unit8 PARTIAL/H05/manifest부재, Unit9 P01 공백/PARTIAL/미채택, Unit2 C01/H01·U3-H01·U6-R02·U7-R01을 유지한다. D0–D5 CLOSED, V1 FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT_ESTABLISHED, Production K/Gate P 미승인이다. Phase2/R0-B/ActualE2, frozen 정책/ModelC, holdout2,010,000..2,010,099와 금지 formal evidence는 열지 않았다.

## 8. 근거 위치

공통 root: `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_STANDALONE_EXACT_COUNTER_UNIT10_2026-11-07`.

- codex_01: 98파일/1,699,565bytes, manifest `96e088118b15bf9a323261e15ecea643a3e94a605fd26a9818afb9c3fc596ae5`.
- codex_02: 225파일/2,824,717bytes, manifest `58b98c3d91508de8c9138b64635dc887ab4ca928b1ea6c4ed608a4abd95ec01f`.
- review_claude_01: 22파일/555,196bytes, manifest `9816d37fad0bbf448623425b4073818f5e5b3844ce4dfc39c1f8425f9d19e64c`.
- coordinator_02: v1.1 계약·기대표·절대 예산 이월 권한. coordinator_03: 검토 입력 결속·원시 합계.
- 문서/Git 준비: `outputs/STAGE4_UNIT10_CLOSEOUT_2026-11-07/coordinator_01`. 실제 사용자 Git/교체 영수증과 destination 검증은 후속 별도 단계다.
