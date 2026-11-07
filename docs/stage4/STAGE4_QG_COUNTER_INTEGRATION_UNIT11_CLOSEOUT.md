# Stage 4 Unit 11 — Q/G 합산 계수기 연결 마감

2026-11-07 (Asia/Seoul). Unit 11의 연결·회계는 등록 범위에서 **ACCEPT_IN_REGISTERED_SCOPE**다. 제품 필수 수정과 근거·헬퍼 필수 보완은 각각 0건이다. 검토된 네 파일을 반영하고 **REVIEWED_OPT_IN_APPLIED_A48_PASS**를 확인했다. 큰 요청 가용성은 **UNCHANGED**, 실전 효율은 **NOT_ESTABLISHED**다.

## 반영 범위

[Q 공개 정밀 후속](../../stage4_exact_pilot.py)과 [G 목적별 평가](../../stage4_objective_pilot.py)의 `base_backend` 기본값은 `UNIT4_LEGACY`다. `UNIT10_SUMMED`는 API에서 명시적으로 지정한다. 연결은 Unit 10 계수기의 공개 관측 base D/M 경로에 한정된다. 해당 계수기는 관측, 전체 지뢰 수, prior, 한도만 받는다. 정책 S/M/R의 목적과 Main/Live의 사용자 인터페이스는 별도 범위다.

- opt-in 요청은 480칸을 먼저 검사한다. 선택한 backend의 작업 한도가 0이면 그 경로를 비활성으로 처리한다.
- Q가 하위 호출에 넘기는 합산 한도는 최대 200,000 units이고 시간은 최대 2초다. G는 남은 `counter_units`에서 Q 호출분을 예약하고, 유효한 실제 소비량을 실패·취소까지 포함해 차감한다. 소비량 정산은 호출 identity와 부모 시간 한도 검사보다 앞선다. Unit 4 exact work, 지역 작업, sampler work는 각 정의로 집계한다.
- 확인할 수 없는 지출은 `UNKNOWN_SPEND`로 남긴다. 지출이나 결과 검증이 불완전하면 평가를 중단한다. 캐시의 원래 소비 기록과 현재 호출의 소비를 구분하며, 후보와 표본의 행렬이 모두 끝났을 때만 모델 점수와 선택을 발행한다.

제품 변경은 Q·G와 [Q 시험](../../tests/test_stage4_exact_pilot.py)·[G 시험](../../tests/test_stage4_objective_pilot.py) 네 경로다. 반영 시점의 네 바이트열은 검토 대상 스냅샷과 일치한다.

## 등록 검증과 실제 반영 확인

| 단계 | 확인 범위 | 결과 |
| --- | --- | --- |
| P3 | 실행 격리 사전 확인 | 원 PASS 영수증 재사용 |
| A | 후보 단위 시험 | 기존 29 + 추가 19, 48 PASS |
| B | base 계수와 hard 어댑터 | Q 16건과 첫 179칸은 원시 재사용, 둘째 142칸은 새 계수 1회. 총 321칸의 D·M·기약분수 일치 |
| C | 작은 엔진 경로 | 24 trial, G 48 READY, 13 WON / 11 LOST. Unit 8 원 경로·결과와 일치 |
| D | 두 큰 요청 프로필 | 36건 반환 및 기존 입력·표본·후보군 결속 확인. 완전 모델 결과 3건 |
| 반영 뒤 A | 검토 바이트 그대로 적용한 상태 | 별도 실행 1회, 등록 메서드의 START 48 / PASS 48 / 실패·오류·skip 0 |

B의 두 hard 상태는 D가 각각 978,313,118,206,356과 7,941,240이다. 단위 시험의 앞선 PASS와 반영 후 PASS는 같은 메서드 집합의 별도 실행이다. C의 Claude 독립 엔진 모형은 22/24가 전 경로·입력·3BV·X·승패까지 일치했다. 나머지 두 경로는 안전칸에 잘못 꽂은 깃발을 연쇄 개방에서 여는 기존 엔진 규칙과 관련된다. G001/M/2는 손 추적으로 원시와 일치했고 G001/R/2의 별도 손 추적은 미확인이다. 작은 witness의 승패 집계는 등록된 사례에 한정된다.

독립 검토는 D의 36개 G 모두에서 예약·정산 사슬, Q 한도, 사용량 합계와 `counter_settle`·`counter_raw` 참조를 원시로 대조했다. B의 321칸과 A의 48개 START→PASS도 확인했다. 반영 확인은 이 검토가 수용한 파일을 적용한 뒤 A만 실행한 기록이다.

## 큰 요청의 완료와 한도

| 프로필 | 반환 / 등록 | Unit 8 READY | Unit 11 READY | Unit 11 미완료 원인 |
| --- | ---: | ---: | ---: | --- |
| DEFAULT | 18/18 | 0/18 | 0/18 | Q 지역 작업 한도 18 |
| EXPANDED | 18/18 | 3/18 | 3/18 | Q 호출 한도 9, G 시간 한도 6 |

확대 READY 세 건은 양쪽 모두 `snapshot_128`의 S/M/R이다. 세 건의 점수·순위·선택·다음 수순이 일치한다. 나머지 33건의 완료 점수와 순위는 null이다. 전환한 합산 계수기 한도에서 중단된 사례는 0건이었다. 이 비교는 등록된 요청에서의 완료율이다. 단위가 다른 작업량을 합하거나 속도 배율로 환산하지 않는다. 안정 계산시간, 실제 효율과 전시 노트북 성능은 별도 근거가 필요하다.

## 실행 수와 과거 판정

- 구현·검증은 논리 시작 8, Python 이미지 14, Job 8과 멤버 21이었다. 종료 요청 2건 중 지정 종료 코드가 관측된 것은 P3 1건이고, run08의 종료 요청으로 실제 종료된 멤버는 exit code 기준 0개였다.
- 반영 확인은 시작 1, Python 이미지 2, Job 1과 멤버 3을 추가했다. 반영 Job의 멤버는 모두 exit 0, 최종 active/member는 0, 컨트롤러와 핸들 회수까지 확인했다. 합계는 시작 9 / 이미지 16 / Job 9 / 멤버 24다. P3는 원시 영수증을 참조했다.
- 반영 전 Q 130,315, 계수기 실제 호출 16,387 / 시도 16,388, 합산 246,415,978 = primary 7,253,017 + auxiliary 239,162,961이다. 반영 A의 추가 Q 476, 계수기 실제 86 / 시도 87, 합산 12,527 = primary 999 + auxiliary 11,528을 별도 기록한다. 반영 뒤 누계는 Q 130,791, 실제 16,473 / 시도 16,475, 합산 246,428,505다.
- 잘못된 응답을 주입한 A의 예약 1,200,000 units는 실제 소비 합계와 구분한다. 반영 A에서 같은 시험을 실행해 예약 누계는 2,400,000이다.
- `codex_01`~`codex_03`의 읽기 출력·보정 중단과 PARTIAL, U11-R02/R03/R04/H01, `codex_04`의 EEXIST와 최초 A exit 101, `codex_06`의 좌표 자료형 비교 실패와 소비 기록을 당시 결과로 보존한다. `codex_05` A와 `codex_07` B tail/C/D, `codex_08` 반영 확인은 각각 별도 실행이다. 최초 exit 101의 OS 원인은 UNCONFIRMED다.

## 비차단 발견과 미확인 처분

| ID | 기록 |
| --- | --- |
| N01 | `QCounterSettlement.SETTLED`는 유효한 counter 소비량의 정산을 뜻한다. 다른 usage 검증에 실패하면 불완전 회계와 오류·중단을 함께 해석한다. |
| N02 | 새 계수기를 써도 이 자료에서는 지역 작업, Q 호출, 시간 한도에서 멈췄다. |
| N03 | D의 `max_seconds`가 현재 float 30.0, Unit 8 int 30으로 직렬화된다. 요청 대응의 공개 내용과 수치 한도는 일치한다. |
| N04 | 기본 backend의 버전·요청 ID는 Unit 11 표현을 쓴다. |
| N05 | C의 깃발 칸 연쇄 개방은 기존 엔진 규칙이다. |
| U01 | Claude의 줄 해시 0/36은 검토 당시 NOT_VERIFIED다. 조율은 gzip을 해제해 1부터 센 UTF-8 줄의 CR/LF를 제외하고 해시하여 36/36을 확인했다. 두 기록은 서로 구분한다. |
| U02–U03 | 최초 A exit 101의 OS 원인과 G001/R/2의 별도 손 추적은 미확인이다. |
| U04–U07 | 독립 검토의 untracked/staged는 index 바이트에 결속했다. Job은 원시 기록으로 확인했다. 제품 시험·시간 측정과 요청 identity digest 재계산은 해당 검토 범위 밖이다. 조율의 현재 Git 확인과 반영 A를 별도 증거로 둔다. |

## 근거와 마감 권한

근거 root는 `outputs/STAGE4_QG_COUNTER_INTEGRATION_UNIT11_2026-11-07`이다. `codex_01`~`codex_07` manifest 797파일, `review_claude_01` manifest 42파일, `codex_08` 반영 manifest 72파일을 각 범위로 결속한다. 독립 검토는 `REVIEW_REPORT_KO.md`·`FINDINGS.json`·`CROSSCHECK.json`, 추가 확인은 `coordinator_09/UNIT8_LINE_HASH_COORDINATOR_CHECK.json`, 반영 확인은 `codex_08/APPLICATION_RECEIPT.json`과 `runs/run01` 원시를 따른다.

검증과 반영 확인의 기준 HEAD는 Unit 10의 `fe41a93353edf0b9e865a0acbd8f7eff98a9fed1`이다. 문서 작성 시점의 마감 계획은 source 365개, 기존 tracked 443개, 반영된 네 경로와 문서 여섯 경로를 묶는 commit/push다. 이후 권한 있는 Git 영수증, 현재 Git과 Desktop destination 검증을 우선한다. 시험 실행 HEAD는 실행 원장에 기록된 값을 따른다.

후속 판단은 남은 지역 작업·Q 호출·시간 비용과 등록 사례의 한계를 근거로 한다. 실제 효율, Stage 4 전체, Main/Live 통합과 전시 노트북은 별도 수용 범위다. 상위 authority와 보호 경계는 [현재 인계](../CURRENT_HANDOFF.md)와 [Stage 4 인덱스](README.md)를 따른다.
