# K_LC0_RANDOM_EXPERT_COMPARE — source checkpoint closeout

작성: 2026-11-02 (Asia/Seoul). 새 비교 앱의 **구현·개발 검증 완료, Claude 독립 검토
PASS / REQUIRED_FIXES 없음, 사용자 native 수용**을 기록한다.
사용자 최신 발언은 **“확인했고 다 괜찮은 것 같아.”**다. 직전 안내한 새 index/추첨,
표시 identity/저장, 저장8191의 Model C0.5배·독립/공통 재생·seek, 저장 열기·취소 후
재실행·닫기에 대한 수용이다. 이는 안내 범위에 대한 사용자 판정이며, 구체적으로 보고하지
않은 실행 횟수/index/DPI/OS 또는 항목별 receipt를 새로 만들지 않는다.

실험적 K-LC0 및 비교 도구의 현재 source checkpoint이며 알고리즘 freeze나 일반 효과성,
production 승인, 새 package 수용이 아니다. 고정3보드 viewer의 당시 정상 동작/경로 체감과
별도 수용이다. 옛 viewer는 원 LAUNCH_IDENTITY316파일의 raw hash에 묶인 역사적 도구이며,
현재 문서5개 불일치로 새 로딩이 인증 실패로 거부된다. source 실행 없이 hash로 확인했다.
과거 보고서의 PENDING/실패와 수정 전 기록은 그대로 보존한다.

## 현재 source와 실행 경로

문서 작업 시작 Git은 main, HEAD == local origin/main ==
`3e9f3935f505ff36dd74b6fba668650ab5c1d41d`, ahead/behind 0/0, tracked 변경 없음,
index 비어 있음이다. **기존 K-LC0 4개 + 새 앱 9개 = 13개 untracked**이며 clean이 아니다.
기존 V1/K-P0 전시는 이 commit으로 이미 user commit/push 완료했다. 이번 13개 및 문서
7개의 새 commit은 아직 없고 Git 쓰기 작업도 하지 않았다.

[entry](../../experiments/k_lc0_exhibition.py) →
[CompareWindow](../../experiments/k_lc0_exhibition_ui.py) →
[CompareJob](../../experiments/k_lc0_exhibition_job.py) →
[전용 child](../../experiments/k_lc0_exhibition_worker.py) →
[run_pair](../../experiments/k_lc0_exhibition_execution.py) 순서다.
child에서 actual `run_k_p0(capture_effects=True)` 다음 active
`run_k_lc0(control=False, capture_effects=True)`를 각 한 번 순차 실행한다.
저장 CONTROL/V1/shadow CONTROL로 대체하지 않는다. solver는 UI thread에서 돌지 않는다.

기존 `EXPERT_GENERAL_V1 / V1 / game_index`, 공개 index **0..99999**, Expert30×16/99를
사용한다. 한 번 생성한 동일 layout을 두 fresh engine에 설치하고 fingerprint를 확인한다.
각 runner는 fresh session·빈 M·cursor(0,0)·첫 OPEN(0,0), 동일 인증 Model C table을 쓴다.
truth는 설치/fingerprint/terminal 대조에만 사용하며 policy에는 기존 공개 port만 전달한다.
기록 때문에 후보 생성·추론·native 선택을 추가 호출하지 않는다.
[DISTANCE_BAND_V1 정책](STAGE3_K_LC0_DISTANCE_BAND_V1_CLOSEOUT.md)의 survivors,
정확21/20 band, D→E→L→frozen tie, guess·추론·M·Model C는 변경하지 않았다.

## lifecycle·renderer 재사용

CompareJob은 기존 start의 작은 골격에 새 worker command, durable request, run/policy
identity를 추가했다. __init__/start/_read_progress/_read_result/_record만 adapter로 두고
elapsed/cancel/_request_stop/poll/_cleanup/_finish/shutdown은 기존 ExhibitionJob을 상속한다.
기존 job 자체와 정확한 ExhibitionPair/ExhibitionTrace 타입 제한은 바꾸지 않았다.
새 ComparePair/CompareTrace와 작은 ComparePlayer/panel 설치 adapter를 사용한다.
ExhibitionAction/Frame, PublicBoard/TracePanel/AbsoluteSeekSlider/ExhibitionPlayback은 재사용한다.
runtime global/class monkeypatch나 frozen 함수 교체는 없다.

WindowsWorkerScope의 suspended launch → 부모 소유 Job assign → resume를 유지한다.
실제 venv Python/자손 containment, pair 전체120초 cap, 비차단 poll, 고정0.75초 exit drain,
cancel/close/timeout 우선, reap 후 cleanup, cleanup 실패 시 다음 요청 거부도 상속한다.
progress OSError는 best-effort지만 final result는 strict다. token/index/run ID/policies/
request 시각·kind가 다른 결과는 거부한다. pre-token scope/transport 원인은 부모 stderr에 남는다.
소유 temp 절대 경로/PREFIX 검사를 유지한다. worker 정리와 JSON 저장 성공은 별개다.

## 화면·재생 의미

시작과 저장 열기는 solver를 자동 실행하지 않는다. index 지정 실행/새 추첨은 명시적
버튼 동작이다. 추첨은 `secrets.randbelow(100000)`이며 선택 index를 실행 전에 저장한다.
‘다음 요청 index’ 입력란과 현재 표시 pair의 index/seed/fingerprint/policy/run ID는 별도다.
새 요청은 이전 pair를 비우며 partial pair를 완료 결과로 설치하지 않는다.
실패/취소/timeout은 새 요청 미완료이고 이전 결과 성공으로 표시하지 않는다.

좌우 독립 play/pause/reset/전후 seek/slider와 함께 재생/일시정지/처음을 제공한다.
공통 명령은 같은 입력 번호나 진행률을 강제하지 않는다. 먼 track click 직접 seek,
drag·keyboard도 유지한다. 기존 수동20..10000ms /0.1..50CPS, 기본250ms,
200/500ms 및 Model C 배율을 그대로 사용한다. 새 기준CPS·거리별 관람 공식은 미구현이다.

완료 current frame의 M/physical flags/observation/누적 비용/완료 route만 표시한다.
pending 중에는 합성 cursor/target만 움직인다. ‘다음 선택의 기록’의 g/selected·L/R/D·
phase/reason과 실제 완료 경로는 다르며 계획 suffix를 완료 route로 그리지 않는다.
전체 입력·O/F/C·종료 비용·총 이동과 현재 위치 누적값도 별도다.
WIN 자동 flags는 실제 입력 수에 포함하지 않는다. 입력 번호/outcome이 같아도 같은 상태가 아니다.
LOST 종료 비용은 time-to-win이 아니며 승리 시간 차이는 양쪽 WON일 때만, 그 외 N/A다.
관람 CPS, 합성 커서, Model C, 실제 인간 시간은 서로 다르다.

## JSON 기록과 검증 한계

기본 사용자 root는 `C:\Projects\GraduationProject\K_LC0_RANDOM_EXPERT_COMPARE_RUNS`다.
같은 index도 UUID run ID의 새 폴더에 저장한다. request.json은 child 전에 index/kind/시각/
policy를 남기고, 유효 완료 pair.json과 lifecycle.json을 구분한다. exclusive publication과
저장 후 round-trip을 사용한다. 화면에서 저장 위치/성패를 알 수 있으며 쓰기 실패를 성공으로
표시하지 않는다. os.link가 필요한 방식이므로 hard link 미지원 `--runs-root`는 실패로 닫힌다.

[store](../../experiments/k_lc0_exhibition_store.py)와
[model](../../experiments/k_lc0_exhibition_model.py)은 schema
`K_LC0_RANDOM_EXPERT_COMPARE`, version1, complete=true를 요구한다.
실행 당시 HEAD/dirty Git/Python, 신규·기존 의존 source40개의 SHA-256, 정책 정의,
generator/index/seed/fingerprint, timezone 시각, table 전체를 저장한다. 각 actual
action/target/cursor/charged cost/status/M_before/preinput_M, N+1 public frames,
실제 choice의 g/selected plan·L/R/D·phase/reason/override를 보존한다.

profile SHA-256: `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`.
table SHA-256: `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b`.

사용자 선택 파일은 JSON만 허용한다. 크기/UTF-8/중복 key/비유한 수/추가 필드,
schema/version/완료, 정확한 타입·범위, action/frame/cursor/status/cost/M·flag 연결,
canonical start, choice/plan 산술, table hash/lookup, terminal layout/fingerprint/clue를 검사한다.
private child transport의 pickle과 구분하며 임의 사용자 pickle은 읽지 않는다.
**재독은 solver·보드 재생성·planner 호출 없이 저장값으로 재생**한다.
과거 source 실행을 historical identity로 표시하며 현재 source 실행으로 재라벨하지 않는다.

본문 SHA-256은 자체 일치 확인이며 외부 서명이나 독립 실행 인증이 아니다. 본문과 checksum을
함께 바꾸면 출처를 보장하지 않는다. reader는 generator를 실행하여 index→layout을 재인증하지
않고 과거 HEAD/source hash의 진실성도 독립 증명하지 않는다. 과거 외부 산출물과 고정 viewer의
review_data.py는 새 앱의 필수 실행 의존성이 아니다. user_runs는 고정 pilot manifest와 별개다.

JSON은 공개 상태/M/실제 경로와 당시 g/선택의 지역성 검토에 쓸 수 있지만 **전체 native
후보/survivors/score/proof/world counts는 미저장**이다. 전체 후보 최소성·pruning·추론의
독립 재인증은 할 수 없다. K-P0 reason과 plan D는 projection의 표시용 파생값이며
native가 출력한 추가 기록이 아니다. 나중 검산을 당시 native 기록으로 주장하지 않는다.

Claude의 optional reader 보강은 별도 후속이다: 저장 terminal layout 기반 정확한 효과 재생,
EXPLODED/입력 결속, override의 selected<g 순위, setup∈preinput_M/plan 종단 합법성,
열기 시 폴더·request 결속. 현재 reader가 이를 모두 인증한다고 주장하지 않는다.
M 획득 시점은 추론 없이 완전히 재인증할 수 없다. WON의 ‘물리 ⚑’ 표시는 자동 WIN flags도
포함하므로 explicit/automatic 수 분리 표시는 optional이다(입력 O/F/C는 정확).
선택 tooltip의 setup 좌표 숨김, cleanup blocked 안내, 게시 후 round-trip 실패 파일 처리도
optional이며 이번 문서 작업에서 구현하지 않았다.

## 검증 이력과 R-1 정정

| 주체 / 기록 | 결과 | 해석 |
| --- | --- | --- |
| Codex TEST_01 | 51 method: 48PASS / 3ERROR | 서로 다른 move 자료형 equality로 정상 projection 거부 |
| Codex TEST_02 | 104PASS = 새51 + 직접 의존53 | action/좌표/status/cursor/cost 필드 결속으로 수정 |
| Codex TEST_03 | 21PASS | phase/OPEN/M 경계와 취소 표시 보강; 새3 추가 |
| Codex TEST_04 | 3PASS | 저장 경로 표시 관련; 최종 직전 UI에서 실행 |
| Codex 합계 | **107 unique = 새54 + 직접 의존53; 179 method 실행** | 누적176PASS/3ERROR, 각 method 최신PASS; 최종107 전체1회 실행 없음 |
| Claude | **최종 source bytes의 새54개 1회 54PASS** | 직접 의존53 재실행 없음 |
| Claude 별도 검사 | offscreen47(36+11) PASS; 저장414입력/424frames 독립 엔진 효과 재생 PASS | pilot 새 실행/native 조작은 하지 않고 Codex 기록으로만 확인 |

직접 의존53은 기존 job28/worker7/playback14/slider4다. 작은 fixture/fake clock/offscreen,
소유한 작은 worker+자손으로 취소/close/timeout을 검증했다. 실제120초 대기나40회 stress,
전체 suite/기존152 전체를 실행했다는 주장은 없다. 이전 source snapshot/실패 로그는 보존한다.
원 K-LC0의152unique/182회 및 Claude30/30, 고정 viewer29unique/85회·새solver0은
[별도 원 구현 closeout](STAGE3_K_LC0_DISTANCE_BAND_V1_CLOSEOUT.md)에 기록한다.

**R-1 — Codex 검증 bytes에 대한 비차단 기록 정정:**

| UI SHA-256 prefix | 실행/검증 identity |
| --- | --- |
| `c03b7c75` | 5 pair pilot 당시 UI; 각 run의40-file map은 PILOT_PLAN과 동일 |
| `f770d4f0` | Codex TEST_04 관련3검사 당시 UI(16,575 bytes) |
| `5b04577c` | 최종 UI(16,611 bytes); TEST_04 뒤 `self.storage.setToolTip("")` 한 줄 추가 |

최종 UI 전체 SHA-256은 `5b04577c8825c95236f78610e3f5209f882285d1f145b0bd6c11bcf45f311a30`다.
TEST_04 snapshot/log 뒤 약23초 후 tooltip 해제 줄이 추가됐다. 따라서 과거 Codex REPORT의
‘관련3검사’ 및 검토 지시서 문구를 **최종9파일 전체 bytes로 Codex test가 실행됐다**는 뜻으로
읽으면 부정확하다. 최종 native 작은 창은 --open 재생으로 run_index를 호출하지 않았다.
최종 UI의 새 tests 전체 통과 근거는 **Claude54/54와 tooltip 해제 fake-job probe**다.
과거 Codex 보고서/WORK_LOG/검토 지시서를 고치지 않고 이 문서에서 정정한다.
이 정정은 source 수정 요구가 아니며 최종 NEW_FILES의9파일과 기존4파일 bytes를 유지한다.

## 사전 계획한 5 pair 전부

PILOT_PLAN은 focused 검증 뒤 pilot 전에 저장했다. 고정314/2718/8191/32768 각1회와
native 새 추첨 `secrets.randbelow(100000)` 1회(26284)다. request 기록은 결과보다 앞선다.
최대5 attempts/10 starts를 모두 사용했고 완료5, 실패/취소/timeout/retry0, 중복0이다.
중복이 나왔어도 replacement하지 않는 계획이었다. 새 앱의 일반 사용자 실행을5회로 제한하지 않는다.

| index | run ID | 실행 경로 |
| ---: | --- | --- |
| 314 | `0c1a30780a984fd8b5dbb8a8a8cef742` | native 지정 버튼 |
| 2718 | `c72501e4d03a4d61b271bcfe2c009b8f` | 같은 CompareJob |
| 8191 | `4ac38c20334f42af9f3e893640f5d73c` | 같은 CompareJob |
| 32768 | `fe1e7385fb854948bf76978b0712cba9` | 같은 CompareJob |
| 26284 | `83bbff5d2bd3443380fc8fdeb41c82be` | native 새 추첨 버튼 |

| index | policy | outcome | 입력 | O/F/C | 종료 Model C µs | 실제 이동 칸 | ≥8칸 이동 |
| ---: | --- | --- | ---: | --- | ---: | ---: | ---: |
| 314 | K-P0 / K-LC0 각각 | LOST | 2 | 2/0/0 | 306,609 | 2.000000 | 0 |
| 2718 | K-P0 / K-LC0 각각 | LOST | 4 | 4/0/0 | 720,354 | 7.064495 | 0 |
| 8191 | K-P0 | WON | 193 | 74/49/70 | 34,838,014 | 491.020103 | 11 |
| 8191 | K-LC0 | WON | 195 | 76/50/69 | 34,822,276 | 476.077105 | 11 |
| 32768 | K-P0 / K-LC0 각각 | LOST | 4 | 4/0/0 | 613,218 | 5.000000 | 0 |
| 26284 | K-P0 / K-LC0 각각 | LOST | 3 | 3/0/0 | 499,665 | 4.236068 | 0 |

8191의 K-LC0−K-P0는 **입력+2, O/F/C +2/+1/−1, 거리−14.942997칸,
Model C−15,738µs**, 긴 이동 차이0이다. active override는 input29/37/79다.
나머지 네 보드는 양쪽 동일한2~4입력 조기LOST이며 승리 시간 차이는 N/A다.
총 거리는 실제 각 입력 cursor→target 합이며 계획 D_route 합이 아니다. 긴 이동≥8칸은
plan에서 미리 고정했다. 개선 사례만 골라 일반 효과성을 주장하지 않는다.

저장414 actions/424 frames의 identity/terminal/cost/M 연결과 round-trip이 확인됐고
모든 lifecycle은 reaped=true/tree_active_count=0/cleanup_complete=true/exit0다.
Claude는 repository import 없는 독립 stdlib 효과 재생으로 저장 기록을 검산했다.
generator 재실행이나 미저장 native 후보 재인증은 하지 않았다.
원3보드6회와 합쳐 독립 표본 수/효과성 통계를 만들지 않는다.

## 개발 native 확인과 사용자 수용의 분리

Codex 개발 기록은 최대화1920×1032, 작은 client900×760(캡처902×792),
314 지정 및26284 추첨의 실제 runner 도달/저장, 같은 pilot8191의 JSON 열기다.
8191 Model C0.5배 독립 재생, 먼 track0→144/drag144→109/keyboard109→110,
독립 위치를 유지한 공통 조작/처음, 작은 창 scroll/seek/저장 위치/닫기를 확인했다.
개발자가 연 창만 닫고 기존 사용자 viewer는 보존했다. 최대화 PNG는 pilot UI,
FINAL_SMALL은 최종 UI의 저장 재생이다. offscreen47검사는 native 증거와 구분한다.

사용자 수용은 이 문서 첫 문단의 최신 발언으로 별도 기록한다. 개발 확인이나 Claude PASS가
사용자 수용을 대신한 것이 아니다. 다른 DPI/OS·새 EXE/package를 수용한 것으로 확대하지 않는다.

## 사용자 실행 / 저장 열기

```powershell
Set-Location -LiteralPath 'C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:QT_QPA_PLATFORM='windows'
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m experiments.k_lc0_exhibition
```

`--index 314`는 입력란만 채우며 버튼을 눌러야 새 실행한다. 저장8191 열기는 다음과 같다.
기본 최대화이며 끝에 `--small`을 붙이면 작은 창이다. 이 명령은 새 계산을 하지 않는다.

```powershell
Set-Location -LiteralPath 'C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:QT_QPA_PLATFORM='windows'
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m experiments.k_lc0_exhibition --open 'C:\Projects\GraduationProject\K_LC0_RANDOM_EXPERT_COMPARE_2026-11-02\codex_20261102_01\pilot_runs\4ac38c20334f42af9f3e893640f5d73c\pair.json'
```

저장 재생의 표시 identity와 다음 요청 입력란을 먼저 구분하고, 독립 재생/seek 및
Model C0.5배·공통 조작을 살펴볼 수 있다. 새 실행은 원하는 공개 index/추첨 버튼으로
별도 요청하고 저장 성공/경로를 확인한다. 현재 사용은 이 새 앱을 중심으로 한다.
옛 고정3보드 viewer의 snapshot 결속과 기존 V1/K-P0 앱의 별도 용도는
[원 K-LC0 closeout](STAGE3_K_LC0_DISTANCE_BAND_V1_CLOSEOUT.md#실행-대상-구분)에 있다.
원 저장3보드 CONTROL/K-LC0 trace와 이 앱의 새 actual K-P0/K-LC0 pair는 서로 다른 evidence다.
옛 trace를 이 JSON 형식으로 재라벨하거나 새 앱에서 열 수 있다고 안내하지 않는다.
이 절차는 향후 사용 안내이며 이번 문서 작업에서 앱을 재실행하지 않았다.

## evidence / 문서 closeout / 다음 선택

고정 evidence root는
`C:\Projects\GraduationProject\K_LC0_RANDOM_EXPERT_COMPARE_2026-11-02\codex_20261102_01`이다.
`REPORT_KO.md`, `NEW_FILES.json`, `MANIFEST.json`, `SOURCE_IDENTITY_FINAL.json`,
`TEST_SUMMARY.json`, `TEST_01~04` logs/JSON, `source_snapshots`, `PILOT_PLAN.json`,
`PILOT_RESULTS.json`, `PILOT_ORIGINAL_OVERRIDES.json`, `pilot_runs`, native PNG/receipts를 보존한다.
`review_claude/CLAUDE_K_LC0_COMPARE_REVIEW_KO.md` §7과 `crosscheck.json`이 R-1 근거다.
현재 문서 작업은 이 기록을 읽고 hash/경로/수치/문서 링크만 검사했으며 과거 도구를 실행하지 않았다.

[CURRENT_HANDOFF](../CURRENT_HANDOFF.md)의 precommit 상태와 새 recovery/COMMIT_PLAN을 따른다.
옛 viewer 안내 정정판 codex_20261102_02의 COMMIT_PLAN/USER_GIT_STEPS가 이전 _01 계획을
교체한다. _01 산출물은 보존하며 커밋 대상20경로는 같고 문서 hash/예상 staged blob을 갱신했다.
다음 작업은 사용자 선택이다: 다른 보드 경로를 바탕으로 필요한 인근 확정 안전 수 처리 개선,
짧은 영상 pilot 후 전체 분석 필요성 판단, Main/Live 최소 알고리즘 선택 통합.
영상/정책 개선을 Main 통합의 무조건적인 선행 gate로 만들지 않는다.
거리 연동 기준CPS UI는 선택 개선, 독립50/50 조기 처리·일반guess 변경은 별도 후순위다.
이번에 이 작업들을 자동 시작하지 않는다.

D0–D5 **FINAL ACCEPTANCE PASS / CLOSED**, **PHASE1_INCONCLUSIVE_TRANSFER**,
effectiveness **NOT ESTABLISHED**, Production K/Gate P **미승인**을 유지한다.
Extended 전체 종료·Stage4·새 package 수용은 선언하지 않는다. ZiNi holdout
2,010,000..2,010,099 및 E0/E1/R0/Phase1/E2/공식100k의 생성·개봉·재실행은 하지 않는다.
