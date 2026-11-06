# Architecture

현재 구현의 책임 분리, 데이터 흐름과 설계 경계를 설명한다. 실행과 기능 사용법은 [README.md](README.md)를 참고한다.

## 1. 설계 목표와 원칙

- **게임 규칙과 UI 정책을 분리한다.** Engine이 상태 전이와 규칙을 담당하고, UI는 입력을 action으로 바꾸고 결과를 표시한다.
- **분석과 실행을 분리한다.** 같은 position 분석을 Live 표시, 동기 runner, Replay Analysis에서 재사용한다.
- **정보의 목적을 구분한다.** 수를 고르는 solver와 실제 보드를 사용하는 통계·metric 계산 사이에 [정보 경계](#public-information)를 둔다.
- **공개 인터페이스와 불변 전달 모델을 사용한다.** Engine 내부의 가변 배열을 다른 모듈이 직접 수정하지 않도록 한다.
- **검증 범위를 명확히 한다.** 회귀 테스트로 동작을 유지하고, 탐색 결과를 보장 범위보다 강하게 해석하지 않는다.

<a id="dependencies"></a>

## 2. 전체 Architecture와 dependency direction

화살표는 주요 호출·의존 방향을 나타낸다. 모든 import를 나열한 그래프는 아니며, subprocess 실행 경계는 별도로 표시한다.

```text
main.py ── engine 생성 → UI에 주입
                         │
                         ▼
                   ui_manager.py
                         ├─ Core Engine ─────────▶ core_engine.py
                         │                            ├─ board_snapshot.py
                         │                            └─ board_analyzer.py
                         ├─ V1/K Live public worker ▶ live_policy_job.py / live_policy_transport.py
                         │                            ╰─ live_policy_worker.py
                         │                               ├─ live_flag_review.py (준비 검토)
                         │                               ├─ frozen stage3_planner / runner validator
                         │                               └─ live_k_policy.KOwner → K session/policy
                         ├─ GUI fixed layout/history ▶ live_same_board.py (policy 입력 아님)
                         ├─ Draw-only Auto cursor ▶ live_auto_cursor.py
                         ├─ Simple analysis ─────▶ simple_decision.py
                         │  / presentation ─────▶ live_analysis.py
                         ├─ Replay ─────────────▶ replay_recorder.py
                         │                        replay_json.py
                         │                        replay_player.py ─▶ core_engine.py
                         │                          └─ 공통 계약: replay_model.py
                         ├─ Replay Analysis ────▶ replay_analysis.py
                         │                          ├─ simple_decision.py
                         │                          └─ live_analysis.py
                         ├─ Replay Statistics ──▶ replay_statistics.py
                         │                          ├─ replay_player.py
                         │                          └─ board_analyzer.py
                         ├─ Human Mouse Trace ──▶ mouse_trace.py
                         │                       mouse_trace_ui.py
                         └─ ZiNi worker
                              ╰─ subprocess ────▶ zini_metric_worker.py
                                                    └─ zini_calculator.py
                                                         ├─ zini_core.py
                                                         ├─ zini_min_ties.py
                                                         └─ zini_advanced.py
```

`board_analyzer.py`는 `BoardSnapshot`을 입력으로 사용한다. ZiNi의 min-ties/advanced 전략은 공통 `zini_core.py` 시뮬레이션을 재사용한다. 계산 모듈은 UI를 참조하지 않으며 `core_engine.py`도 PyQt5에 의존하지 않는다.

Simple Algorithm 내부와 실행 계층의 관계는 다음과 같다.

```text
UI / replay_analysis / simple_runner
                 │ position 분석 호출
                 ▼
          simple_decision
            ├─▶ simple_algorithm       local inference, Constraint/Move 모델
            └─▶ simple_probability     local move가 없을 때 exact probability
                       └─▶ simple_algorithm   constraint 생성·검증 재사용

SimpleDecision ── 데이터 ─▶ live_analysis ─▶ Live / Replay UI 표시
                           (solver 호출이나 행동 실행 없음)

simple_runner ──▶ simple_decision
              ├─▶ core_engine.step()     동기 실행
              └─▶ replay_recorder        실행한 행동 기록
```

`live_analysis.py`는 decision/probability 모델을 참조하는 순수 presentation 계층이다.
Live Auto는 UI의 QTimer 제어이며 `simple_runner.run_simple()`을 호출하지 않는다. V1/K는 `live_policy_job`/`live_policy_transport`를 통해 public-only `live_policy_worker`를 사용한다. V1은 `live_policy`/`live_flag_review`와 frozen planner, K는 `live_k_policy.KOwner`의 persistent session/M·원 graph를 사용한다. K는 VALIDATE/ADMITTED 뒤 최종 비교·token 소비·첫 입력1·정확 ACK를 거친다. `live_auto_cursor`는 별도 표시이며 선택·비용·입력 권한이 없다.
Solver가 `core_engine`에서 가져오는 것은 `Action`, `CellState` 같은 공개 타입이다.

## 3. 모듈별 책임

### Engine, 정적 보드와 UI

| 모듈 | 책임 |
| --- | --- |
| `main.py` | Qt 설정·GUI import 전 ZiNi / Stage-3 / Live policy worker 모드 분기, Windows Qt plugin 경로 설정, QApplication과 engine 생성, UI에 engine 주입 |
| `core_engine.py` | 지뢰 배치, OPEN/FLAG/CHORD, flood fill, 승패 판정, 타이머, active/wasted 클릭 및 진행량 집계 |
| `board_snapshot.py` | 크기·지뢰 수·배치 여부·mine layout·adjacent를 담은 불변 `BoardSnapshot` |
| `board_analyzer.py` | 확정 보드의 opening 그룹과 OPENING/BORDER/ISOLATED 분류, 정적 3BV/Ops |
| `ui_manager.py` | PyQt5 화면·입력 정책·렌더링, Live Analysis/Auto 제어, Replay 이동·시간·파일 대화상자, 통계 표시, ZiNi worker 관리, Stage-3 launcher 창 소유 |

`BoardSnapshot`은 `frozenset`과 중첩 tuple로 값을 복사한다. 아직 지뢰가 배치되지 않았으면 `mines_placed=False`, 지뢰 집합은 비어 있고 adjacent는 현재 0 배열이다. 이 상태를 조회할 수는 있지만 BoardAnalyzer와 ZiNi 계산은 확정 보드를 요구한다.

Ops는 8방향으로 연결된 0 영역의 수이고, 3BV는 Ops에 고립 숫자 칸 수를 더한 값이다. Engine은 정적 분석 결과를 받아 opening 그룹의 최초 개방과 고립 숫자의 최초 개방을 동적 진행량으로 집계한다. Border 숫자는 별도 3BV 점수로 중복 계산하지 않는다.

### Simple Algorithm: 추론, 확률, decision

| 모듈 | 책임 |
| --- | --- |
| `simple_algorithm.py` | observation 검증, clue별 `Constraint`, 직접 추론과 deterministic move 선택 |
| `simple_probability.py` | 공개 조건에 맞는 complete-board world 수와 셀별 지뢰 확률 계산, 확률 기반 move 선택 |
| `simple_decision.py` | `analyze_position(observation, num_mines)`으로 두 계산 경로를 통합한 `SimpleDecision` 반환 |
| `simple_runner.py` | 현재 engine을 동기 실행하고 guess 전 중단 또는 종료, 실제 행동의 Replay 기록 |
| `live_analysis.py` | 계산된 Simple/V1/K 증거를 `LiveAnalysis`/overlay/status로 변환, exact 확률 포맷과 Reduction |
| `live_k_policy.py` | K snapshot/proposal/permit/ACK·safe_cells DTO, exact 추측/확정색 투영, worker-only persistent KOwner |
| `live_policy_job.py`, `live_policy_worker.py`, `live_policy_transport.py` | public-only V1/K 세션·v10 wire·고정판 provenance·검증·ACK·정리 소유권 |
| `live_same_board.py` | GUI-only 불변 FixedLayout/FixedOrigin/CompletedLiveGame, 원 배치 재설정과 분리된 완료판 근거 |
| `live_auto_cursor.py` | mouse-transparent/NoFocus 가상 셀 좌표 보간, 논리 cursor/Model C와 분리 |

Local inference는 열린 숫자 `N`, 인접 깃발 수 `F`, 인접 HIDDEN 집합 `H`로 `N-F` 제약을 만든다.

- `N-F == 0`: H의 모든 칸이 안전하다.
- `N-F == len(H)`: H의 모든 칸이 지뢰다.
- 같은 observation 안에서 새 사실을 다른 constraint에 전파하거나 subset 추론을 추가하지 않는다.
- 확정 지뢰의 FLAG를 확정 안전의 OPEN보다 먼저 선택한다. 같은 우선순위는 화면 읽기 순서 `(y, x)`로 결정한다.

Exact probability는 local move가 없을 때만 호출한다. Clue constraint에 속한 frontier를 constraint 공유 관계로 component 분리하고, 각 component를 bounds pruning으로 열거한다. 지뢰 수별 정수 histogram을 prefix/suffix convolution으로 결합하고, 나머지 unconstrained/floating 칸은 조합 수로 가중한다. 전체 지뢰 수를 맞추므로 component별 확률을 단순 평균하지 않는다.

열린 숫자·깃발·총 지뢰 수와 일치하는 모든 complete board를 같은 가중치로 센다. 각 `CellProbability`는 `mine_worlds`, `total_worlds`와 정확한 `Fraction` 비율을 제공한다. 100% 지뢰가 있으면 FLAG를 우선하고, 아니면 floating 칸까지 포함한 최소 지뢰 확률의 칸을 OPEN한다. 동률은 `(y, x)` 순서다.

`SimpleDecision`은 선택된 `move`, `constraints`, `deterministic_result`, `probability_result`를 보존하는 frozen dataclass다.

| `DecisionKind` | 의미 |
| --- | --- |
| `LOCAL_DETERMINISTIC` | 직접 추론에서 선택. Probability 계산을 건너뛰며 `probability_result=None` |
| `GLOBAL_CERTAINTY` | Exact probability에서 선택된 셀의 지뢰 world 수가 정확히 0 또는 전체 world 수 |
| `PROBABILITY_GUESS` | 선택된 셀의 지뢰 world 수가 0과 전체 사이인 OPEN |

Certainty는 정수 world 수로 판정하며 표시용 반올림이나 float을 사용하지 않는다. 선택할 HIDDEN이 없는 일관된 position은 `None`을 반환한다.

### Stage-3 V1: 동결 구현과 완료 범위

2026-10-10 **Stage-3 V1 CLOSED**: 동결 알고리즘·텔레메트리·공식 100k 검증을 수용했다. Qualified implementation commit은 `611984133b83be11bcd2105f401ecdddcfd68a15`로 유지하며, 이후 문서 커밋을 공식 실행 commit으로 취급하지 않는다.

| 모듈 | V1 책임 |
| --- | --- |
| `stage3_planner.py`, `stage3_physical.py` | 공개 observation과 동결 timing profile/table로 OPEN·FLAG·CHORD 후보를 계획하고 E-first 정책으로 선택 |
| `stage3_runner.py`, `stage3_benchmark_runner.py` | 검증된 첫 action 하나를 실행한 뒤 재계획하는 동기 실행 및 benchmark 흐름 |
| `stage3_telemetry.py`, `benchmark_modeled_time.py`, `benchmark_comparison.py` | Stage-3 event 계약, modeled time 재구성, paired outcome 및 WW ratio-of-totals 비교 |

공식 `EXPERT_GENERAL_V1` 100,000보드의 WW 37,702게임에서 동결 Model C의 modeled time-to-win 합계는 Stage 2보다 약 **30.089144% 감소**했다. 승패·기록된 guess 시퀀스 동등성은 이 corpus의 관찰 결과이며 보편적 회귀 불변식이 아니다. 이 수치는 CPU 계산시간·benchmark wall time·인간 플레이 시간의 30% 감소를 뜻하지 않는다. Model C의 OPEN·FLAG·CHORD 동일 비용 가정도 함께 적용한다.

[최종 판정문](docs/stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)과 [동결 명세·감사 보존 위치](docs/stage3-v1/README.md)를 기준으로 읽는다. OPTIONAL 4건은 비차단 DEFER다. 현재 Live/Replay UI의 Simple Algorithm과 Stage-3 V1 실행 경계를 구분한다. ZiNi 개선은 별도 마일스톤으로 종료했다. Stage-3 실행·재생·Visualizer 통합은 아래 Extended foundation에 구현되어 있고, 새 알고리즘·물리 모델 설정은 후속 범위다.

### Stage-3 Extended: Execution / Playback / Visualizer Foundation

Slices 1–4는 pre-Slice-5 기준점 `b9af830495ce97552f2058ef91b59a4fd495222b`까지
main에 통합되었다. Slice 5 문서 closeout 및 독립 감사 기준점은
`18964add02c508d67429ef29cb59ce879c01017d`이며 이후 HEAD를 고정하는 값이 아니다.
자동·packaged manual 수용, 독립 Claude 감사와 ChatGPT 최종 판정을 거쳐 이
foundation은 **FINAL ADJUDICATION PASS / CLOSED**다.
[수용 기록](docs/stage3-extended/STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)은 자동·수동
증거를 구분하고, [최종 판정](docs/stage3-extended/STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md)은
F-1 문서 정리와 F-2 worker transport hardening 보류를 기록한다.
Stage-3 Extended 전체는 **ACTIVE**이며 Stage-3 V1 / Model C는 frozen이다.

| 모듈 | 책임 |
| --- | --- |
| `stage3_execution.py` | indexed `EXPERT_GENERAL_V1` 보드와 spec, 완료된 `Stage3RunResult`를 불변 `Stage3Execution`으로 유지 |
| `stage3_execution_worker.py` | Qt 없이 한 index 실행, token/execution/error envelope를 trusted-local pickle로 atomic 게시 |
| `stage3_execution_job.py` | 한 subprocess, token, polling/cancel, reap 후 job 디렉터리 전체 삭제 |
| `stage3_visualizer_launcher.py` | job과 viewer 소유, index/Run/Cancel, 완료 시 자동 열기, 마지막 완료 결과 다시 열기 |
| `stage3_trace_player.py` | fixed layout의 정수 index 재구성; incremental `next()`, arbitrary seek는 index 0부터 재구성; planner 호출 없음 |
| `stage3_modeled_playback.py` | Qt 독립 modeled timeline; monotonic clock, 정확한 부분 시간, 배속·pause·boundary catch-up |
| `stage3_visualizer_ui.py` | execution만 입력받는 읽기 전용 보드·controls·modeled Qt frame 요청·smoothstep cursor; retained truth의 HIDDEN-only 참조와 committed trace-target route |

```text
main.py / MinesweeperUI
  ↓ owns launcher only (no Stage-3 subprocess fields)
Stage3VisualizerLauncherWindow
  ├─ Stage3ExecutionJob (parent-side process owner)
  │    ╰─ subprocess → stage3_execution_worker
  │                      ↓ indexed EXPERT_GENERAL_V1 → frozen run_stage3()
  │                    Stage3Execution
  │                      ╰─ atomic result → job reaps + cleans → launcher
  ╰─ Stage3VisualizerWindow(completed execution)
       ├─ Stage3TracePlayer → committed observation / recorded action
       ╰─ Stage3ModeledPlayback(player) → exact timeline / boundary consumption
```

Source job은 `sys.executable`과 `__file__` 기준 절대 worker script 경로를 쓴다.
Frozen job은 `sys.executable --stage3-execution-worker`로 같은 EXE에 재진입한다.
`main.py`의 두 worker dispatch는 Qt 설정과 GUI import보다 먼저 실행된다.
동결 profile은 `stage3_physical.py`의 `__file__` 옆 `calibration/`에서 읽고,
원본 bytes SHA-256과 table SHA-256을 각각 검증한다. Bundle의 `_internal/`
아래 같은 상대 경로에 원본 파일을 포함해야 한다.

Job의 정상 polling/cancel은 UI thread에서 블로킹 대기를 하지 않는다. 최종 shutdown만
terminate 0.5초 + kill/reap 1초의 제한된 대기를 허용하며, reap/cleanup 실패 시
소유권을 유지하고 close를 거부한다. Launcher close는 job과 viewer를 정리하고,
main close는 launcher close 성공을 먼저 요구한다. 전체 private job 디렉터리를
reap 후 삭제하므로 worker의 미완성 atomic 파일도 cleanup 범위에 포함된다.

Benchmark 실행은 현재 Live/Replay 보드와 독립적이다. 보드 identity/layout은
설정·재구성에만 쓰고 planner에는 공개 observation만 전달한다. Viewer는
solver 결정 입력이 아니며 새 실행이나 계획을 만들지 않는다.

**Replay != Stage-3 Trace Playback != ZiNi Trace.** Replay는 실제 게임 행동과
elapsed time, Stage-3는 완료 실행의 action index와 정확한 modeled µs,
ZiNi Trace는 answer-board 기반 계산 경로의 사후 설명이다. Presentation 간격은
Model C 비용과 독립적이며 커서 선은 칸 중심 간 변위다. Arbitrary seek는 index 0부터
재구성하는 기존 결정을 유지한다. Slice 5에서 checkpoint/seek 최적화는 하지 않았다.

### Stage-3 Extended: Version / Settings Identity Separation

`Application/release != algorithm identity != physical model/profile != playback/presentation`.

| 소유자 / 소비자 | 책임과 경계 |
| --- | --- |
| Release/tag/build 문서 | 배포 identity. 현재 main을 historical `v0.2.0`으로 표시하지 않으며 runtime app-version 상수나 QApplication version은 없다. |
| `stage3_identity.py` | Frozen `STAGE3_V1_IDENTITY`: algorithm spec version/hash와 solver stage/policy만 유지. Stage/policy 문자열은 기존 `telemetry_schema` public 상수를 참조하며 telemetry semantic version 자체는 별개다. |
| `stage3_physical.py` | 불변 `MODEL_C_V1_IDENTITY`의 model ID, profile version/hash, table hash, unit과 실제 profile/table 인증·cost를 소유. `MODEL_C_DISPLAY_NAME`은 인증에 참여하지 않는 별도 표시 alias다. |
| Benchmark producer / modeled evaluator | 위 authoritative 값을 소비한다. 기존 public 상수는 compatibility alias이며 canonical snapshot의 9개 key·값·type·serialization·거부 규칙을 보존한다. |
| Launcher / viewer | Identity를 읽기 전용으로 표시한다. Launcher corpus ID는 `EXPERT_GENERAL_V1`, viewer의 run 정보는 기존 execution에서 읽는다. |
| `stage3_visualizer_ui.py` | Index/Modeled-Time controls와 비영속 presentation을 소유한다. Index는 20..5000 ms, 기본 200 ms; modeled speed는 기본 1×다. 두 label에 `(presentation)`을 표시한다. |

Dependency는 benchmark/UI → identity owner 방향이다. Identity owner는 UI나
presentation settings를 참조하지 않는다. UI가 profile을 다시 열거나 해석하지 않는다.
`stage3_identity` import는 Qt, solver 실행, profile I/O, subprocess, settings를 요구하지 않는다.

Snapshot은 `initial_open`, `initial_cursor`, `algorithm_spec_version`,
`algorithm_spec_sha256`, `physical_model_id`, `physical_profile_version`,
`physical_profile_sha256`, `timing_table_sha256`, `timing_unit`이다.
Initial OPEN/cursor는 execution configuration이며 algorithm identity 객체의 필드가 아니다.
Profile descriptor 비교가 실제 profile bytes/table authentication을 대체하지 않는다.
Semantic model ID, concrete profile identity, exact timing-table artifact identity도 구분한다.

`Stage3Execution(spec, board, result)`와 trusted-local pickle envelope는 그대로다.
DB migration, Replay schema 변경, ZiNi 변경, algorithm/profile 선택기 또는 registry는 없다.
Game-index text, autoplay, playback index·mode·interval·배속은 비영속 local state이며
viewer를 다시 열면 Index / 200 ms / modeled 1×로 돌아간다. Stage-3 QSettings와
presentation semantic version은 도입하지 않았다.

- `Replay != Stage-3 Trace Playback != ZiNi Trace`.
- `Presentation interval != Model C time`; interval 편집은 timer와 label만 바꾼다.
- `decision_compute_ns != modeled physical time`; Replay elapsed time도 별도다.
- `rendered UI cell size != calibration physical identity`.
- Playback/display settings는 planner 입력이 아니며 recorded action/cost와 total을 바꾸지 않는다.
- Frozen V1 official 100k 결과는 원래 algorithm/profile identity에 계속 귀속된다.
  향후 algorithm/profile 변경은 별도의 명세·identity·평가를 요구한다.

### Stage-3 Extended: Modeled-Time Playback / Synthetic Smooth Cursor Presentation

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-15)**.
[Closeout](docs/stage3-extended/STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md)에 최종 tests,
fresh package/worker/profile 및 사용자 native GUI A–K 수용을 기록했다.

- **Stage3TracePlayer:** index k는 traces[:k]를 적용한 정수 상태다. `next()`는 현재
  engine의 격리된 복사본에 pending action 하나만 적용·검증한 뒤 게시한다.
  실패 시 공개 상태는 유지된다. `go_to()`는 여전히 index 0부터 재구성하고
  `previous()`는 이를 사용한다. 커서·current trace·누적 정수 µs를 소유한다.
- **Stage3ModeledPlayback:** recorded `modeled_action_us`를 분해하거나 재계산하지 않는다.
  monotonic nanoseconds를 정확한 Fraction µs로 반영하며 running/partial/speed,
  pause/resume, 여러 boundary catch-up, zero-duration 및 `cancel_partial()`을 소유한다.
  Qt·geometry·profile I/O·planner를 소유하지 않는다.
- **Stage3VisualizerWindow:** Index 기본값과 20..5000 ms/step(기본 200)을 유지한다.
  Modeled-Time의 16 ms PreciseTimer는 frame 요청이며 elapsed time은 controller가
  계산한다. 정수 index가 같으면 overlay만 갱신하고, catch-up으로 여러 action을
  적용해도 마지막 committed board를 한 번만 refresh한다.

Pending action의 raw progress u 동안 보드는 pre-action 상태를 유지하고 경계에서
action을 한 번 적용한다. UI에서만 Fraction을 float로 바꾸고
`q = u² * (3 - 2u)`, `P = A + q * (B - A)`를 렌더된 칸 중심에 적용한다.
A/B는 pending trace의 cursor-before/target이다. 같은 칸은 정지하며 별도 dwell,
curve, overshoot, jitter는 없다. Detail panel은 last-applied trace를 유지한다.

Pause는 요청 시각까지 반영하고 부분 위치를 동결한다. Resume은 새 clock anchor로
이어 간다. 0.25× / 0.5× / 1× / 2× / 4× / 8×(기본 1×) 변경 전에는 old speed로
경계를 처리한다. 수동 버튼·slider press/seek는 timer 정지 → `cancel_partial()` →
기존 정수 navigation 순서다. 같은 index slider interaction도 취소하지만 programmatic
slider 동기화는 취소하지 않는다. Mode 전환은 committed index를 유지하고 paused가 된다.
오류·close는 재생을 멈추며 final index에서 wrap/restart하지 않는다.

다음 경계를 유지한다:

- QTimer frame request != modeled-time authority; 16 ms는 실측 FPS 보장이 아니다.
- Presentation speed != Model C parameter; 1×는 recorded modeled time의 표시 배율이다.
- Smoothstep easing != physical acceleration model.
- Synthetic cursor != actual OS trajectory; rendered geometry는 calibration pixel size와 별개다.
- Replay elapsed time != Stage-3 modeled time.
- `decision_compute_ns != modeled physical time`.

### Stage-3 Extended: Same-board Comparison — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-17)**. Qualified source/package candidate:
`a59d0d963bdf1544a03968163b884342e2797ee0`. The
[contract](docs/stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md) preserves
the engineering semantics; the [closeout](docs/stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md)
records automated/package/native acceptance. Stage-3 Extended remains ACTIVE.
The later [Visualization Usability Polish closeout](docs/stage3-extended/STAGE3_VISUALIZATION_USABILITY_POLISH_CLOSEOUT.md)
qualifies selected-run playback and reference rendering at
`31630dd6ffa2301c41534fca3b003838d865f313`; the original execution/transport
contract and historical acceptance remain preserved.

| Module | Durable responsibility |
| --- | --- |
| `same_board_comparison.py` | Immutable captured Human context; exact finalized layout/canonical fingerprint; full-stream terminal admission and opening facts |
| `same_board_runner.py` | Separate fixed-layout Stage-2 / frozen Stage-3 engines; native solver evidence and separately labeled metrics; parent composition |
| `same_board_execution_worker.py` | Trusted-local token + `ReplayBoard` request only; one execution; atomic solver-only result/error |
| `same_board_execution_job.py` | One parent-owned child/private directory, token binding, poll/cancel, terminate → kill, reap before cleanup; original Human context stays in parent |
| `same_board_playback.py` | Human and Stage-2 `ReplayPlayer`s plus fixed-layout Stage-3 trace player; three independent remembered indices |
| `same_board_timed_playback.py` | Qt-independent immutable run timing projections and per-run presentation progress; exact Human Replay timestamps / solver Model C boundaries, pause/re-anchor/catch-up; no Engine execution |
| `same_board_comparison_launcher.py` | One captured context, job, retained completed execution and at most one result viewer |
| `same_board_comparison_ui.py` | One public-observation board; selected-run controls and one presentation QTimer; three timed states, full Human Mouse Trace, separate reference layers/context/synthetic cursor; no worker ownership |
| `visualization_reference_overlays.py` | Neutral immutable clue derivation and answer/route painters; caller supplies truth, public HIDDEN mask and route points; no acquisition, prefix selection, clocks/playback, Engine, solver, Model C or jobs |

Main Tools **Compare as full-game Human Replay…** declares caller intent and
captures either the completed Live recording or the entire original retained
Replay, regardless of displayed index. `source_type == SOURCE_HUMAN` is necessary;
metadata, declaration and successful reconstruction are not exclusively-Human
historical provenance proof. Incomplete/post-terminal streams are Comparison
rejections without changing ordinary Replay validity. Later source changes cannot
retarget the captured context; **Open Comparison…** raises its existing owner.

The exact Human finalized layout is installed with `reset_with_mines()`. Stage 2
uses unchanged `run_simple(..., accept_guesses=True, initial_open=(0,0), observer=...)`;
Stage 3 uses unchanged frozen V1. A mined origin legitimately loses immediately:
fresh-game first-OPEN mine-placement safety does not relocate this fixed layout.
No fabricated benchmark identity, solver hidden-layout leakage or retry is added.
The narrow `benchmark_modeled_time.evaluate_ordered_actions()` seam authenticates
Model C and includes first/terminal costs without invented telemetry records.

Parent validation rechecks outcome-bearing types, layout/fingerprint, streams,
terminal states and modeled costs with local Model C authentication. It deliberately
does not recursively walk all trusted-local nested decision evidence; native
decision/probability/plan evidence is retained. This is not arbitrary pickle security.
Normal Run/Cancel do not wait. Final launcher shutdown is irreversible and may
reject close while retaining cleanup ownership; job shutdown precedes viewer close.
Main close orders Comparison owner, Stage-3 Visualizer owner, then remaining teardown.

Index 0 is fixed all-HIDDEN; n means exactly n recorded inputs of that run.
Selection restores only that run's remembered index/range. Current status and
final outcome differ at intermediate indices, including PLAYING at 0 and LOST at
1 for an immediate solver loss. Stage-3 playback executes only `trace.move`, never
plan suffixes. Viewer reopen retains the completed execution without solver rerun.

Human Replay elapsed **seconds**, Human Mouse Trace **microseconds**, each solver's
Model C cost through termination **microseconds**, each solver's decision compute
**nanoseconds**, and presentation timing remain separate authorities. No common
timeline, normalized progress, generic speed winner/ranking/ratio or controlled
experiment claim is introduced. Full Human Mouse Trace is independent of action
index. Comparison's synthetic action-target cursor and completed action-target
route are separate from that actual recorded trace. None is solver input.

Same-board UI creates one independent timed controller per run and advances only
the selected one. Human offers Index / Replay Time; solvers offer Index / Model C
Time. Human boundaries preserve stored Replay floats exactly. Stage-2 prefixes
are projected once from retained targets/authenticated table and reconciled to
the retained total; Stage 3 uses recorded action costs. SameBoardPlayback remains
the committed-board authority. Manual seek aligns/cancels partial state; pause
preserves partial progress, and late ticks apply the final due prefix once.

Index is 20..5000 ms/action, default 200, with `Max (20 ms)` and committed input
clamping. Time speed uses exact 0.25 steps from 0.25x to 8x. A 16 ms presentation
request uses raw controller progress for cell-center straight smoothstep
`q = u²(3 - 2u)` in the UI. Human's initial synthetic anchor is its first action
target, not a borrowed Mouse Trace sample or invented origin. Partial ticks and
reference toggles do no domain execution; committed seeks may retain existing
Engine reconstruction. This is not an Engine-free navigation claim.

Both Comparison and Visualizer default `Show hidden answers` / `Show action-target
route` OFF. Answer clues derive once from retained finalized truth, then only the
current public HIDDEN mask is decorated (mine/nonzero clue, zero blank, opacity
0.35). Cell text/accessibility and flags/terminal feedback remain unchanged.
Route membership is caller-owned completed targets only, including repeats,
excluding future targets and any initial-cursor incoming segment. Shared painting
uses purple alpha 165 / width 2.0 and white under-stroke alpha 100 / width 3.5.
Layers are board → answers → route → actual Human trace where present → selected
context → synthetic cursor; all overlays are mouse-transparent.

Visualizer retains direct seek, Index timing and existing modeled smooth cursor
with six speeds (0.25x, 0.5x, 1x, 2x, 4x, 8x). **No Index smooth interpolation
was added.** Its partial modeled refresh leaves public observation/answer mask/
route at the committed prefix. Reference truth never enters planner/admissibility
or executed choice. The neutral helper creates no feature-to-feature UI dependency.


### Stage-3 Extended: Program K research / effectiveness boundary

Program K의 bounded experimental 구현은 K-C capability의 논리 지뢰 집합 M과
K-P0의 선택적 물리 FLAG·OPEN·CHORD 실행을 제공한다. Gate-R E0/E1과 Actual E1,
E2 구현 I1–I8, R0 harness, remediation 1A–1W는 수용된 구현 이력이다.
생산 통합은 **NOT STARTED**, Gate P는 **NOT PASSED / NOT AUTHORIZED**다.

Remediation 기술 anchor는 `48f6ebc97e6c4d3ed4a746a92a8d169783803bf9`다.
[정확한 V1.3.1 설계](docs/stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1.md)와
[acceptance receipt](docs/stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1_ACCEPTANCE.md)는
frozen 상태를 유지한다. RF02/WB02, qualified codec, dual physical/logical sizing,
B_proc와 독립 validation/readback 책임은 accepted experimental 구현에 남아 있다.
Fresh R0-A V2 Attempt #2는 integrity PASS이며 static storage blocker를 해소했지만,
18/18 comparable route wall은 퇴화했다. 전체 remediation은 PARTIAL SUCCESS이고
realized R0-B constructibility는 미입증이다. 과거 old-source/representation의
static proofs와 역사적 execution identity는 새 viewer HEAD로 대체하지 않는다.

Timing Phase-1 Attempt #2 execution/integrity와 measurement quality는 PASS,
최종 과학적 판정은 **PHASE1_INCONCLUSIVE_TRANSFER**다. 현재 de-dup remediation-class
profiling은 **STOP / DEFER — UNBOUNDED_RESEARCH_RISK**다. Phase 2는
**NOT AUTHORIZED**, R0-B와 Actual E2는 **NOT RUN / NOT AUTHORIZED**,
effectiveness는 **NOT ESTABLISHED**다. 이는 PHASE1_NO_GO 또는 E2 실패 판정이 아니다.
구현 수용, timing diagnostic, 효과성, production qualification은 서로 다른 경계다.

### Program K read-only research visualization / comparison — CLOSED

별도 D0 authority의 D1–D5 구현·패키지·사용자 acceptance가 **FINAL PASS / CLOSED**다.
최종 소스 `fb59d5fa253f04f50ea57c6a9e863aa1999a517e`와 상세 증거는
[연구 데모 closeout](docs/stage3-extended/STAGE3_PROGRAM_K_RESEARCH_DEMO_CLOSEOUT.md)에
기록한다. Stage-3 V1 및 기존 production Same-board architecture는 변경하지 않는다.

| Research module | 현재 책임 |
| --- | --- |
| `experiments/program_k_trace_adapter.py` | `load_accepted_e1_traces()` / `project_accepted_e1_traces()`: accepted E1/COMPLETE/profile bytes와 역사적 source/audit를 인증해 immutable K-P0 frames/actions/provenance로 projection; stdlib only, K-P0-only admission |
| `experiments/program_k_control_trace_adapter.py` | 별도 `ControlTracePresentation`: CONTROL의 archived V1/public-effect/cost audit와 physical stream admission; K 지식이나 fake K model을 만들지 않음 |
| `experiments/program_k_trace_viewer.py` | `KTracePlayer`, `KTracePlayback`, public board와 committed logical-known-mine rendering; in-memory 탐색·표시만 수행 |
| `experiments/program_k_trace_comparison.py` | `load_accepted_e1_pairs()` / `ProgramKComparisonPair`: exact same-board binding과 `RecordedDifference`; 공통 playhead 없음 |
| `experiments/program_k_trace_comparison_ui.py` | CONTROL/K 패널의 독립 player/controller/timer/clock, Korean audience presentation; evidence I/O·gameplay 없음 |
| `experiments/program_k_trace_demo.py` | accepted K 사례를 한 번 읽고 K-only viewer를 여는 standalone launcher |
| `experiments/program_k_trace_comparison_demo.py` | 네 accepted pair를 한 번 읽고 비교 UI를 최대화해 여는 standalone exhibition launcher |

허용 의존 방향은 **research UI → research adapters/models**, 그리고 research
presentation에서 의미가 일치하는 **stable production presentation helper**로 향한다.
생산 모듈이 `experiments.program_k_*`를 import해서는 안 된다. CONTROL sibling은
D1의 제한된 parsing/authentication helper를 재사용하지만 D1의 K-only 계약은 넓히지
않는다. 기존 main menu/algorithm selector/worker와 연결하지 않는다.

`KTracePlayback`은 `Stage3ModeledPlayback`의 물리 timing mechanics를 재사용하고,
completed-route painter는 `visualization_reference_overlays.py`를 재사용한다.
CONTROL은 별도 `ControlTracePlayer` / `_ControlBoard`를 사용해 K 용어·knowledge layer가
섞이지 않도록 한다. K를 `Stage3Execution`이나 `Stage3RunResult`로 위장하지 않는다.

입력 authority는 accepted E1 bytes다. 로딩은 archived PASS 기록을 검증하되
solver/evaluator를 다시 실행하지 않는다. 탐색은 immutable D1/CONTROL observation을
직접 표시하므로 Engine reconstruction, hidden layout 대체, 파일 재읽기가 없다.
Model C는 기록된 정수 비용과 합계를 사용하며 wall time·CPU time·human recorded time과
다르다. Synthetic cursor는 cell-center 사이 표시용 이동이며 실제 mouse trajectory가 아니다.

논리 지뢰 표시 계약:

- ordinary HIDDEN, logical-known but physically HIDDEN, physical FLAG를 구분한다.
- frame 0의 M은 empty다. k > 0의 M은 정확히 k개 입력 후 D1 frame state이며
  `actions[k-1].preinput_M`에 해당한다. `answer_reference`에서 지식을 추론하지 않는다.
- 숨은 논리 지뢰에만 초록 diamond를 그린다. FLAG는 primary glyph이고 logical provenance는
  secondary detail로 남는다. Explicit FLAG와 automatic WIN flag는 별도 상태다.
- 자동 WIN FLAG나 terminal answer disclosure가 이전 K 지식을 만들지 않는다.
  Hidden-answer/reference truth는 별개 개념이며 이 UI에는 answer toggle이 없다.
- Partial motion 중 board/M/route/cumulative Model C는 committed frame에 고정되고
  cursor/target만 움직인다. Layer는 public → logical marker → route → target → cursor다.

비교는 repetition 1의 S-LIFECYCLE 6↔8, S-REPLAN 12↔14, S-LOSS 18↔20, X-0 24↔26이다.
Registration/materialization, case/source, fingerprint와 exact terminal layout은 같고
operation/result는 별개다. CONTROL은 frozen V1 실행, K-P0는 실제 K policy이며
K-CONTROL shadow analysis는 포함하지 않는다. 좌우 clocks/playheads는 독립적이다.
공통 action index·normalized progress·race clock·동기 semantic position은 없다.
Pair 변경만 양쪽 partial motion을 버리고 frame 0으로 초기화한다.

`RecordedDifference`는 K-P0 minus CONTROL의 사례별 산술 사실이다. S-LOSS의
comparative `model_c_us`는 None이며 종료 비용은 좌우 별도로 표시한다. 효과성 지표로
승격하지 않는다. Korean 표시 이름과 내부 action/status/mode/identity는 분리되고,
기술 provenance는 tooltip/accessibility로 보존된다.

### Random Expert Exhibition V1 — accepted standalone source

2026-11-01 UI 피드백 반영 후 사용자 native 재수용을 기록한 별도 source 앱이다.
[전시 closeout](docs/stage3-extended/STAGE3_RANDOM_EXPERT_EXHIBITION_V1_CLOSEOUT.md)이
검증·수용·실행 identity를 구분한다. D5 preserved-E1 viewer, Main/Live, production
Same-board worker를 변경하지 않으며 새 package/EXE 또는 Gate-P 수용이 아니다.

| 전용 모듈 (`experiments/random_expert_exhibition*`) | 책임 |
| --- | --- |
| entry / ui | standalone 최대화 창, 새 추첨·index·취소, 독립 패널과 공통 관람 명령 |
| job / process / worker | Qt 밖 실제 pair 계산; 정수 token·private atomic transport·Windows Job Object 소유 tree·취소/timeout/reap/cleanup |
| execution | 공개 EXPERT_GENERAL_V1 index0..99999에서 layout 한 번 생성; 두 fresh all-HIDDEN engine에 같은 layout/인증 Model C와 OPEN(0,0), cursor(0,0); frozen V1 capture → actual K-P0 순차 실행·검증·투영 |
| model | native action/cost/effect를 검증한 immutable action과 N+1 public frames; source/algorithm/physical identity와 terminal summary |
| playback | 완료 trace만 읽는 독립 clock/playhead; Fraction 관람 duration 또는 기존 Model C 배율; engine/solver/evidence I/O 없음 |

layout은 설치·검증 전용이며 정책 입력이 아니다. V1 투영 뒤 불필요한 full evidence를 놓고
K-P0를 실행한다. LOST는 정상 결과이며 오류/취소/timeout은 LOST로 변환하지 않는다.
parent wall cap120초는 전시 응답성 보호값이다. RF-1의 0.75초 고정 비차단 exit drain은
cap/cancel 의도를 늦추지 않는다. RF-2의 advisory progress OSError만 best-effort이고
final result 발행은 엄격하다. RF-3는 pre-token 오류 원인을 stderr에 남기되 admission을
완화하지 않는다. worker GUI import·사용자 파일 import·production dispatch 통합은 없다.

frame0의 M은 비어 있고 frame i+1은 완료 trace i의 preinput_M을 사용한다.
M_before 연결, logical M / physical FLAG / automatic WIN flag를 구분한다.
자동 flags는 입력 수에 넣지 않는다. partial 이동은 cursor/target만 바꾸고
board/M/완료 route/누적 Model C를 미리 공개하지 않는다. seek는 해당 패널만 정지·commit한다.
함께 재생/일시정지는 각 현재 위치·속도에 명령하며 index/진행률을 맞추지 않는다.
함께 처음으로는 같은 pair의 두 frame0으로 돌아가되 모드·속도는 보존한다.

관람 ms/CPS는 정확한 Fraction µs duration 하나를 편집한다(20~10000ms / 0.1~50CPS).
기본250ms, 200/500ms preset, 소수3자리 입력·환산 `≈`, 확정 입력과 신호 차단으로 drift를
방지한다. 실행 중 변경은 구 속도까지 정산하고 partial을 유지한다. Model C 모드에서는
관람 입력을 비활성화해 값을 보존한다. 실제 Model C 비용·정책은 바꾸지 않는다.
관람 속도는 인간 physical model/calibration이 아니다. 통계적 효과성을 주장하지 않으며
Model C time-to-win 차이는 양쪽 WON일 때만 정의한다.

### Experimental K-LC0 / separate random Expert comparison

2026-11-02 source checkpoint다. 계보는 frozen V1 → K-P0 → 실험적 K-LC0이며
V1-LC0 구현은 생략했다. V1도 CHORD를 사용하고 Stage2 Simple과 구별한다.
이2026-11-02 checkpoint에서 K-P0/K-LC0는 별도 policy/entry였다. 이후 Main에는 K-P0/K-LC0/K-LC1이 연결됐으며 현재 계약은 [최신 Main closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_K_LC1_DISPLAY_CLOSEOUT.md)을 따른다.
기존 V1/K-P0 앱의 `3e9f3935...` 뒤 K-LC0 4개·비교 앱9개와 문서7개의20경로는
`496fab0fc8829af7a255c403346985be7ae6a005`로 commit/push 완료됐다.
그 이전 실행은 당시 raw hash/dirty identity를 따르며 새 HEAD로 소급 식별하지 않는다.

| 신규 경로 | 책임 |
| --- | --- |
| `experiments/program_k_lc0_policy.py` | native 선택1회·기존 survivors·정확21/20 band; 전체 계획 D→E→L→frozen tie 및 별도 validator |
| `experiments/program_k_lc0_runner.py` | 기존 공개 port/session/실행 검증·effect archive 재사용; 첫 입력만 실행 후 재계획; active K-LC0와 진단 CONTROL |
| `experiments/k_lc0_exhibition.py`, `_ui.py` | 명시적 index/추첨 요청·취소·JSON 열기, current pair/다음 요청 분리, 독립/공통 재생 |
| `experiments/k_lc0_exhibition_job.py`, `_worker.py` | 새 start/admission adapter와 private child; 기존 RF poll/cancel/drain/shutdown/cleanup 상속 |
| `experiments/k_lc0_exhibition_execution.py` | 공개 Expert layout1개·fresh engine2개·동일 table로 actual run_k_p0 → run_k_lc0(control=False), 실제 return만 projection |
| `experiments/k_lc0_exhibition_model.py`, `_store.py` | immutable ComparePair/Trace/ChoiceNote, 엄격한 JSON v1·request binding·exclusive 저장/round-trip |

band는 `20*L(p)*R(g) <= 21*L(g)*R(p)`이며 D는 cursor부터 모든 setup/terminal까지의
계획 거리다. native exact_route 순서와 guess·추론·M 유지·Model C는 그대로다.
runtime monkeypatch, 후보 추가 생성, survivor 복원, 지역 완료 보장은 없다.

CompareJob은 start의 필요한 골격만 복사해 command/durable request/identity를 바꾸며
기존 job을 일반화하지 않는다. suspended launch→Job assign→resume, venv 자손 containment,
120초 pair cap, 비차단 poll, 고정0.75초 drain, 취소/닫기/timeout 우선·reap 후 cleanup을
유지한다. progress OSError는 best-effort, final result는 token/index/run ID/policy에 strict하다.
저장 실패와 worker 정리는 별도로 표시한다.

CompareTrace는 K-P0 전용 ExhibitionTrace로 위장하지 않는다. 작은 ComparePlayer/panel
adapter가 PublicBoard/TracePanel/AbsoluteSeekSlider/ExhibitionPlayback을 재사용한다.
기존 타입 제한을 완화하지 않는다. 완료 frame의 M/observation/flags/누적 비용/route만
공개하며 다음 선택의 계획 suffix는 완료 route가 아니다. 자동 WIN flags는 입력에 세지 않는다.

저장 JSON은 당시 source40개 hash/HEAD/dirty 상태, profile/table, board/run identity,
각 실제 action/M 경계와 N+1 frames, 선택 요약을 보존한다. JSON 열기는 실행 모듈을
호출하지 않고 저장값을 검증·재생한다. private pickle은 소유 child transport에만 사용한다.
자체 checksum은 서명이나 출처 증명이 아니다. reader는 generator/추론/native 후보를
재인증하지 않으며 전체 native 후보/proof는 미저장이다. 과거 고정 viewer 산출물은 새 앱의
필수 실행 의존성이 아니다. 향후 user_runs와 고정 pilot manifest도 구분한다.

기존 고정3보드 외부 viewer는 당시 source snapshot에 묶인 역사적 검토 도구다.
review_data.py의 load_review()는 원 LAUNCH_IDENTITY에 있는316파일의 현재 raw hash를
검사한다. 현재는 문서5개가 불일치하므로 새 로딩을 거부한다. source 실행 없이 hash로
확인했으며 인증 제한을 풀거나 옛 viewer를 수정하지 않았다. 현재 비교 안내는 새 앱을
중심으로 한다. 기존 저장3보드 CONTROL/K-LC0 trace와 새 actual K-P0/K-LC0 pair는 별도 evidence다.
도구의 현재/역사적 구분, reader의 optional 보강, 혼합 pilot/검증과 R-1 정정은
[정책 closeout](docs/stage3-extended/STAGE3_K_LC0_DISTANCE_BAND_V1_CLOSEOUT.md)과
[비교 앱 closeout](docs/stage3-extended/STAGE3_K_LC0_RANDOM_EXPERT_COMPARE_CLOSEOUT.md)에 있다.
Claude PASS 및 사용자 native 수용은 experimental source 범위다. 일반 효과성·production·
K-LC0 freeze·새 package는 승인하지 않았다. 거리 연동 기준CPS UI도 아직 없다.

### Experimental K-LC1 / saved LC0–LC1 path review

2026-11-02 별도 실험적 checkpoint다. 계보는 frozen V1 → K-P0 → K-LC0 → K-LC1이며
V1 확장은 생략했다. 원 K-LC0/DISTANCE_BAND_V1과 기존 실행 UI·policy는 불변이다.

| 신규 repo 경로 | 책임 |
| --- | --- |
| `experiments/program_k_lc1_policy.py` | SINGLETON_BAND_V1, 새 SingletonSelection 기록·별도 validator; native/실제 LC0 b/최종 선택 분리 |
| `experiments/program_k_lc1_runner.py` | 기존 public port/session/물리 validator/effect archive 경계로 실제 첫 move만 실행 후 fresh replan |
| `tests/test_program_k_lc1.py` | 선택 산술·불변성·기록 변조·작은 runner seam의 focused 검증 |
| `tests/fixtures/program_k_lc1_singleton_native.json` | 세 captured public state의 detached 선택 산술 fixture; 새 추론/engine 증거 아님 |

입력당 native 선택1회 후 동일 결과에 실제 LC0 `apply_distance_band(control=False)`를 적용해
b를 얻는다. 원 survivor 중 certainty safe pool의 물리 HIDDEN direct-safe OPEN 하나(R=1,
setup 없음)만 예외 대상이다. HIDDEN8-neighbor 성분 C에는 숨은 논리 M도 연결한 뒤
`C − preinput_M = {target}`인지 본다. 물리 FLAG와 M은 다르며 추론 독립 component 인증이 아니다.
native g 기준 `20*L(p)*R(g) > 21*L(g)*R(p)`, `10*L(p)*R(g) <= 11*L(g)*R(p)`,
`D(p) < D(b)`를 만족해야 한다. 전체 계획 D→정확 Fraction(L,R)→L→frozen tie로 고른다.
추가 추론/후보/route/pruning은 없고 guess·초기 OPEN·M·Model C는 불변이다.
110%는 한 선택의 L/R 상한이지 전체 게임 비용 제한이 아니다.

외부 저장 viewer는 K_LC1_PILOT_RECOVERY_TRACE_V1 / K_LC1_PUBLIC_SELECTION_RECORD_V1의
662 actions/666 frames/662 choices를 immutable하게 보존한다. 원 UI의 표시 클래스만 정적으로
재사용하며 pure DTO/playback import 외 solver/worker/generator 계층은 차단한다.
reader는 저장 manifest/TRACE_INDEX/trace·historical launch/review R2 identity를 검사한다.
현재 repo source/docs/HEAD를 과거 raw hash와 비교하는 startup 조건은 없다.
이번 doc refresh가 새 viewer를 무효화한다고 추정하지 않았고 reader 텍스트만 정적으로 확인했다.

현재 확인 도구는 외부 저장8191/97 viewer이며 `experiments.k_lc0_exhibition`에는 LC1이 없다.
사용자 확인은 두 저장 경로에 한정된다. native Qt 렌더 확인/offscreen tests/미확인 CU 제스처를
분리하며 자세한 수치·알려진 한계·실행 안내는
[K-LC1 closeout](docs/stage3-extended/STAGE3_K_LC1_SINGLETON_BAND_V1_CLOSEOUT.md)을 따른다.
위 내용은 별도 저장 viewer의 역사적 범위다. 현재 Main은 K-P0/K-LC0/K-LC1 및 속도 입력을 연결했으며 [관람 속도/CPS closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_PACING_CLOSEOUT.md)을 따른다. 기존 비교 앱에 LC1이 추가됐다는 뜻은 아니다. Production·새 package/Stage4는 미승인이다.

### Replay

| 모듈 | 책임 |
| --- | --- |
| `replay_model.py` | Frozen `ReplayBoard`, `ReplayEvent`, `ReplayData`; 좌표·지뢰 수·action·시간·schema 검증 |
| `replay_recorder.py` | 메모리에 실제 이벤트를 누적하고 확정된 snapshot을 한 번 capture하도록 호출자가 관리 |
| `replay_json.py` | JSON 구조 변환, UTF-8 파일 입출력. 도메인 검증은 model에 위임 |
| `replay_player.py` | 저장된 fixed board를 독립 engine에 복원하고 action 순서대로 재생 |
| `replay_analysis.py` | 현재 공개 position의 Simple 추천과 내부 비교 데이터. 읽기 전용 |
| `replay_display.py` | 녹화된 다음 입력의 문구/테두리와 별도 Simple 참고 표시. 비교 판정은 화면에 노출하지 않음 |
| `live_display_state.py` | 동일 Auto context의 HIDDEN 확정색만 다음 계산까지 보관하는 immutable frame. 입력 권한 없음 |
| `live_pacing.py` | Fraction 입력, 정수 ns 고정 주기, 원 Model C 관람 배속과 deadline. 정책/비용 변경 없음 |
| `live_fixed_cadence.py` | 실제 입력 시각과 예정 목표를 분리한 제한된 위상 보정. 입력 권한 없음 |
| `replay_statistics.py` | 별도 player로 counter timeline을 만들고 위치·재생 시간·ZiNi에 따른 Counters 반환 |

Replay 재생, Replay Analysis, Replay Statistics는 서로 다른 책임이다. 재생은 기록을 engine에 적용하고, Analysis는 현재 position의 추천을 설명하며, Statistics는 과거 행동의 통계를 집계한다. Analysis는 플레이 평가 점수를 계산하지 않는다.

<a id="human-mouse-trace"></a>

### Human Mouse Trace / Path Visualization

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-16)**. Qualified implementation/package
SHA와 source·package·사용자 native 수용은
[closeout](docs/stage3-extended/STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md)에 기록한다.

| 소유자 | 책임 |
| --- | --- |
| `ui_manager.py` | Live 보드 event 수용·좌표 변환, physical action 관측, recording/eligibility 수명과 Replay event 연결 |
| `mouse_trace.py` | Qt 독립 point/segment/data 계약, 독립 monotonic clock과 recorder; semantic action을 재정의하지 않음 |
| `mouse_trace_ui.py` | 불변 trace와 Replay events의 선택적 정적 경로/marker 표시, 입력을 가로채지 않는 overlay와 cache |
| `replay_model.py`, `replay_json.py` | Human Replay v2의 trace attachment 검증·저장·복원; v1은 trace-free로 계속 지원 |

좌표는 **board-local Qt logical pixels**이며 전달된 subpixel 위치를 보존한다.
Event-driven exact accepted samples만 기록하고 timer sampling, min-distance filtering,
의미를 바꾸는 point dropping/throttling은 없다. 같은 segment의 연속된 동일 위치
비-action sample만 중복 제거하며 action marker와 segment 경계는 보존한다. 보드 이탈,
scroll/geometry·cell-size 변경, hide/deactivate 같은 연속성 단절은 segment를 나눈다.
OS-global 좌표는 변환에만 쓰고 저장하지 않는다.

Recording은 앱/session 기본 ON이다. 첫 committed timed human OPEN/FLAG 전까지만
선택을 바꿀 수 있고, 그 action에서 선택이 잠긴다. OFF이면 그 판의 trace를
무효화한다. 첫 OPEN은 L release, 첫 FLAG는 R press의 관측 위치/시각을 사용하며,
Replay append 성공 후 그 관측이 trace의 **0 µs** 기준점이 된다. 관측은 동기
engine/ZiNi/Replay 처리보다 먼저 얻는다. Untimed pre-start CHORD는 trace를 시작하지
않으며 후속 CHORD도 timed OPEN/FLAG보다 먼저 trace를 시작할 수 없다.
Mode-A CHORD marker는 L release, Mode-B marker는 armed BOTH의 첫 release를 쓴다.
Replay elapsed time과 trace clock은 별개다.

Marker는 실제 `ReplayEvent` index로 action 의미를 참조한다. Committed human action이
Replay append 실패로 빠지면 전체 trace를 무효화한다. 실제 Auto action도 Human
trace 자격을 무효화하며 Auto toggle만으로는 무효화하지 않는다. 종료된 Live 판은
trace를 동결하고 표시를 허용한다. Replay seek는 전체 trace attachment를 유지한다.

Recorder는 primitive tuple의 private 저장소를 사용해 public point 객체를 장기간
보유하는 GC 비용을 피한다. Pre-start의 무관한 movement/press는 geometry 처리 전에
gating하며 첫 FLAG가 가능한 R press만 필요한 정확한 관측을 얻는다. Mode-B에서
L hold로 FLAG가 억제된 R press는 시작 전 관측을 materialize하지 않는다.
Overlay는 transformed geometry와 bounded raster를 cache한다. Raster 예산은
**16 MiB**이며 oversized 보드는 visible-region cache 또는 cached-geometry 직접
렌더링으로 처리한다. 이 예산은 전체 trace/geometry 메모리 상한을 뜻하지 않는다.
Hardening 후 native 사용자 시험에서 trace ON은 수용 가능했고 최종 package에서
눈에 띄는 회귀는 없었다. Zero overhead나 새 microbenchmark 수치는 주장하지 않는다.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`.
Human trace는 실제 sampled Live-board pointer presentation data다. Model C calibration
evidence, OS-global trajectory, Stage-3 synthetic cursor 또는 solver decision 입력이 아니다.

### ZiNi

| 모듈 | 책임 |
| --- | --- |
| `zini_calculator.py` | 공개 계산 API, 설정·결과 모델, 기존 호출 인터페이스와 내부 helper 재노출 |
| `zini_core.py` | 정적 3BV unit, 가상 개방/깃발 상태, Premium 평가, 클릭·flag/chord·fallback 공통 시뮬레이션 |
| `zini_min_ties.py` | 최대 Premium 동점 후보의 경로 탐색, 시간·상태 수 제한 |
| `zini_advanced.py` | Neighborhood beam, `standard_v1`·`chain_v1`·`standard_seeded_chain_v1` 정책 |
| `zini_metric_worker.py` | 별도 Python process에서 계산하고 임시 결과 파일을 atomic replace로 기록 |
| `zini_trace.py` | 완료된 V1 경로의 사후 검증, 불변 step delta와 적용 전 Premium 진단, engine/clock 없는 논리 index player |
| `zini_explorer.py` | worker 결과와 전송 snapshot 소유, transport 검증, 요청 시 Trace 생성·cache 및 이동; Qt/search/I/O 없음 |
| `zini_explorer_ui.py` | 별도 읽기 전용 보드, index 이동·자동 재생과 경로 진단 표시; controller를 참조하고 탐색은 실행하지 않음 |

ZiNi trace의 `ZiniMove`는 `ReplayEvent`와 다른 모델이다. 예를 들어 `flag_chord` 한 항목의 `clicks_added`에는 새 깃발들과 CHORD의 클릭 비용이 함께 들어간다.

## 4. 핵심 데이터 흐름

### Benchmark Statistics: Pre-Stage 3 / Stage 1 통계·시각화 확장

```text
ui_manager.py                    상단 도구 메뉴 진입점과 보조 창 생명주기
    └─▶ benchmark_statistics_ui.py
            ├─▶ benchmark_statistics_presentation.py   순수 표시·KO/EN·plot 좌표
            ├─▶ benchmark_statistics.py                실행 탐색·통계 의미
            │       └─▶ telemetry_repository.py / telemetry_schema.py
            └─▶ telemetry_repository.connect_database_readonly()
```

- `benchmark_statistics.py`는 불변 `BenchmarkRunSummary` 목록을 run_id 내림차순으로 반환하고, 기존 `RunStatistics`와 `RunCoverage`를 계산한다. 통계 공식과 공식 사용 가능 판정은 이 계층에만 있다. UI에는 SQL이나 통계 공식이 없다.
- Repository의 읽기 전용 연결은 URI `mode=ro`, autocommit을 사용한다. 물리 스키마 버전과 필수 테이블을 확인하며 schema 초기화·migration·journal/synchronous 변경·checkpoint를 하지 않는다. 기존 writer 연결의 FK/WAL/FULL 동작은 유지한다.
- 보조 창이 연결을 소유한다. 새 DB의 연결·목록·첫 실행 조회 성공 후 이전 연결을 닫는다. 실패 시 기존 선택을 유지하고 오류를 표시한다. 창 닫기와 Escape에서도 연결을 닫는다. 실행 선택 시 짧은 동기 조회를 수행하며 여러 쿼리에 걸친 동시 writer의 snapshot 일관성을 보장하지 않는다.
- Presentation은 Qt/SQL 없이 분수·비율·나노초와 불변 plot point를 표시용으로 변환한다. 확률의 exact Fraction 순서와 원본 identity를 유지하고 X 좌표만 float으로 변환한다. float이 겹쳐도 점을 합치지 않는다. 추측 횟수와 보드 3BV는 backend 분포 그대로 숫자 막대에 표시한다.
- 100게임 pilot의 추측 이벤트 396개/정확한 위험 255개에 맞춰 위험 그래프는 연속 확률 축의 scatter를 쓴다. Hover·점 선택·분수 목록으로 exact risk를 확인하며 categorical label 255개나 새로운 확률 bin을 만들지 않는다.
- 한국어/영어는 이 창 전용 텍스트 사전과 runtime selector로 전환한다. 도메인 식별자는 그대로 유지한다. 번역 시 현재 결과와 plot item을 유지하고 통계를 다시 조회하지 않는다.
- 계산 시간은 환경 영향을 받는 진단 지표다. 평균·최대와 네 percentile을 함께 표시한다. 100게임 측정은 thread, cache, index 추가의 근거가 아니므로 도입하지 않는다. 확장성은 1k/10k pilot에서 재평가한다.
- **Pairing UI: DEFER / REVISIT WHEN STAGE 3 COMPARISON UI EXISTS.** 실제 Stage 3 비교 흐름이 생길 때 두 실행·접두 범위 선택 GUI를 재검토한다. `validate_paired_prefix()`, paired identity, 공식/진단 규칙과 Batch 8 테스트는 유지된다.

검증은 repository 읽기 전용/파일 보존, 실행 목록의 불변성·SELECT-only, 순수 포맷/정확한 확률 순서, 실제 offscreen Qt의 연결·언어·그래프·main engine ownership 경계를 포함한다. 자동 테스트는 자체 임시 DB를 쓰며 외부 pilot artifact에 의존하지 않는다.

### 4.1 Live 입력과 분석·자동 진행

2026-11-05 현재 같은 보드 재플레이·그룹 기록·ACK 정리 뒤 Replay 진입과 기본/명시 종료 선택까지 범위 한정 독립 검토 및 사용자 native 수용을 마쳤다. 현재 [같은 보드/Replay 계약](docs/stage3-extended/STAGE3_MAIN_LIVE_SAME_BOARD_CLOSEOUT.md)과 기존 [속도/CPS 계약](docs/stage3-extended/STAGE3_MAIN_LIVE_PACING_CLOSEOUT.md)을 따른다. [LC1 및 표시 계약](docs/stage3-extended/STAGE3_MAIN_LIVE_K_LC1_DISPLAY_CLOSEOUT.md)은 이전 checkpoint다. [LC0 Main 계약](docs/stage3-extended/STAGE3_MAIN_LIVE_K_LC0_CLOSEOUT.md), [K 인수/UI 계약](docs/stage3-extended/STAGE3_MAIN_LIVE_K_ADOPTION_UI_CLOSEOUT.md), [이전 Simple/V1](docs/stage3-extended/STAGE3_MAIN_LIVE_SIMPLE_V1_CLOSEOUT.md)은 버전별 역사다.

새 판은 수동 가능·Auto OFF·guess OFF다. Simple/V1/K 계열 모두 수동 board press에서 Auto와 guess를 끄고 원 gesture를 이어간다. Auto OFF만으로는 유효 pending을 보관한다. 별도 추천·계산 종료 버튼은 제거했다. 정책 변경은 옛 owner retire 뒤 다음 명시 ON에 적용하고 판·기록을 보존한다. 재인수 전에는 옛 owner의 exit/reap/tree0/private cleanup을 확인한다.

K-P0/K-LC0/K-LC1은 세 preset의 canonical 새 판과 현재 판 ADOPT/재인수를 지원한다. FLAG-free ADOPT는 빈 M과 현재 global revision·실제 입력 이력에 결속한다. FLAG 인수는 각 정책의 PUBLIC_FLAG_ADOPT_LOCAL_BOOTSTRAP_V1 정의를 사용한다. native KLocalSession이 detached FLAG-masked 공개 관측을 한 번 local 분석하고 원 FLAG와 증명 M의 교집합만 유지하며 나머지는 row-major로 실제 해제한다. 같은 session/proof를 이어 실제 판 검증·정상 분석/선택을 수행한다. M 외부 주입, V1 proof 재사용, masked graph의 실제 입력 승인은 없다.

worker는 원 session.M·decision/selection identity로 VALIDATE→ADMITTED를 반환한다. GUI는 yield 없이 최종 비교→token 소비→step1을 수행하고 정확한 원 입력의 ACK 뒤 NEXT로 간다. ACK 중 수동 인계는 불변 _KInputReceipt로 기존 입력/game/Replay prefix를 확인하며 현재 수동 판을 과거 상태로 되돌리거나 NEXT를 보내지 않는다. 실제 ACK/이력/정리 오류의 fail-closed와 최초 원인 기록은 유지한다.

현재 공통 wire v10이며 KSnapshot의 game_id와 V1 fixed_game_id/고정판 정의를 entry provenance에 결속한다. 정책/정의/entry/phase와 game/run/generation/token/nonce/시작·M revision이 끝까지 결속된다. K 일반 입력≤480, 준비≤480, 합계≤960, pending VALIDATE≤64, V1 seq≤1921, 기존 K envelope≤31681, FLAG 준비 포함 envelope≤63362, 메시지≤2MiB와 compute30/ACK5/exit5/drain0.75초를 유지한다. 게임 전체 revision/event 수가 480에 묶인다는 뜻은 아니다. V1의 준비 FLAG-free proof·입력 경계를 변경하지 않는다.

Simple Main 준비는 live_simple_preparation.py에서 공개 FLAG-masked 직접 zero/all·전체 지뢰 수로 기존 FLAG를 확인한다. 기존 Simple planner는 불변이다. 수동 입력은 준비 epoch를 폐기하고 Auto를 끈다. 실제 준비 입력은 event를 남긴다. Model C 표 밖(dx≥30 또는 dy≥16) 이동은 null/OUTSIDE_FROZEN_TABLE과 unmodeled 입력 수로 기록하며 0비용이나 완전 합계로 표현하지 않는다.

K_LC0는 같은 normal DecisionAnalysis와 native select_policy를 각 한 번 얻고 원 apply_distance_band(control=False)를 한 번 적용한다. 원 survivors의105% 정수 band와 전체 exact_route D→Fraction E→L→frozen tie를 유지한다. K_LC1은 같은 native 선택에 원 apply_singleton_band를 한 번 적용하며 내부에서 실제 LC0 baseline b를 한 번 구한다. HIDDEN8 성분에서 M을 뺀 집합이 target 하나인 원 survivor의 direct safe OPEN만 105% 초과·110% 이하 및 D(p)<D(b) 조건으로 예외 선택한다. 원 graph/selection/native·물리 검증에 결속하며 첫 입력1회만 실행한다. guess/initial과 native 정책·Model C는 불변이다. 110%는 전체 게임 비용 상한이 아니다.

K exact 확률은 원 phase_e의 primitive projection, 확정색은 원 selection_safe_cells/preinput_m의 HIDDEN 셀 표시다. 확률 OFF에도 확정색은 남고 V1/K 가상 원형은 OS 마우스·Model C와 분리된다. 표시를 위한 추가 추론·선택·FLAG·ACK 승격은 없다.

live_display_state의 DisplayContext는 game/policy/run/generation/owner/revision/이력·관측 digest에 결속된다. CertaintyFrame은 SAFE/MINE만 저장한다. 같은 context에서 Auto 입력1회 후 다음 계산을 기다릴 때 여전히 HIDDEN인 색만 유지한다. 열린/FLAG 칸은 즉시 제외하고 이전 추천·확률은 보관하지 않는다. 새 분석이 있으면 새 frame으로 교체하며 합집합을 누적하지 않는다. pause는 유효 frame을 유지하고, 수동 첫 press·정책·새 게임·Replay·종료·분석 OFF·오류·owner 폐기는 frame을 지운다. 실행 분석의 무효화와 표시는 분리되므로 frame이 token/입력/다음 선택을 승인하지 못한다. CellButton은 overlay/확률 문구/테두리/tooltip이 모두 같을 때만 중복 update를 생략한다.

Live Space/Return/Enter는 새 게임 한 번, Replay Space는 기존 재생/일시정지 한 번이다. Replay Return/Enter/reset은 상태를 바꾸지 않는다. 비편집 정책 콤보의 focus에서도 Live 키가 동작하며 편집 가능한 콤보·line/text/spinbox, popup/modal, auto-repeat 방어를 유지한다. 종료 정리 예외는 기존 closing/job 잠금을 유지하면서 한 줄 이유·전체 tooltip/접근성 설명과 비활성 제어로 표시한다. 강제 종료/추가 worker/자동 복구를 만들지 않는다.

#### Main/Live 관람 속도

2026-11-06의 추가 거리 모드는 [거리 관람 closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_DISTANCE_VIEW_CLOSEOUT.md), 후속 성능 보완은 [고정 6 CPS 최적화 closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_FIXED6_OPTIMIZATION_CLOSEOUT.md)을 따른다. 검토된 최적화 bytes 반영 뒤 이번 PC의 사용자 native 수용을 마쳤고 전시 노트북은 별도 대기다. 기존 고정/Model C의 실행 계약과 회계는 유지한다.

기본은 고정200ms/목표5CPS다. 고정 모드의 실행 권위는 FixedPeriod.period_ns 하나다. 정확한 Fraction 입력을 ns로 올림하고 표시 반올림을 되먹이지 않는다. 6CPS는166,666,667ns이며 사용자가 입력한6을 유지한다. 같은 주기 재확정은 timer/phase/nonce를 바꾸지 않고 실제 주기 변경만 drain 후 재예약한다. 고정 간격·목표 CPS와 Model C 배속은 모드별로 표시하며 숨긴 편집기의 늦은 commit을 막는다.

고정 목표 T와 실제 입력 A를 분리한다. 0<=10*(A-T)<=P이면 다음 목표는T+P, 그 밖에는A+P로 재시작한다. 각 입력은 자기 목표 이전에 실행하지 않으며 작은 보정의 최소 간격은0.9P다. Auto/owner/수동/모드 전환의 위상 수명을 따로 관리하고 밀린 입력을 몰아 실행하지 않는다. K의 현재 proposal은 먼저 VALIDATE할 수 있지만 permit은 목표까지 보관한다. due 시 재검증→token→step의 기존 무yield 구간과 정확ACK 뒤 NEXT는 유지한다.

고정 모드와 새 거리 모드는 PreciseTimer, Model C는 기존 timer type이다. deadline은 time.perf_counter_ns(QPC), 원형은 perf_counter 초를 쓴다. timer의 조기 callback은 남은 시간을 재대기한다. Model C는 원 행동 비용/배속(0.05–8)의 ceil-ms 관람 지연이며 고정 위상 보정을 적용하지 않는다. 거리 모드 추가 자체는 frozen 비용 기록·원 추론·worker/job/transport를 바꾸지 않았다. 아래 후속 최적화도 비용·정책·wire·deadline 계약은 유지한다.

`live_distance_pacing.py`의 `DistanceWait`는 이미 선택된 target과 public/actual cursor 사이의 Euclidean 칸 거리로 version 고정된 `distance_view_log_v1` 관람 시간을 만든다. Decimal precision 50의 sqrt/ln, 정확한 Fraction 배속, ns 올림을 사용한다. 1배의 대기는 약 91.7–550 ms이며 배속 0.05–8은 원 Model C 배속과 독립이다. 제품은 사용자 outputs를 읽지 않고 상수와 provenance hash만 포함한다. 이 수식은 기존 descriptive fit의 관람 기본안이며 원 연구 Model C나 정책 비용을 대체하지 않는다.

`_fixed_pacing_active()`는 고정/Model C/거리 모드를 명시적으로 구분한다. 거리 관람은 proposal 이후 시작하고 종료된 뒤 K VALIDATE→ADMITTED로 진행한다. 최대 11초 대기 동안 permit을 미리 보관하거나 원 cap을 늘리지 않는다. 원형은 동일 기간을 사용한다. 취소·모드/배속 변경·수동 인계·보드/Replay 전환은 기존 nonce·reservation·permit 폐기 경로를 따른다.

거리 metadata는 `live_input_records.distance_view`에만 추가되며 원 action/Model C/compute/Replay 회계는 유지한다. Simple의 내부 UI Live UUID와 policy owner가 없는 입력의 null run_id를 같은 owner로 결합하지 않는다. 미지원 보드에서는 실효 고정 모드이며 지원 복귀와 Replay 두 종료 후에도 세 모드의 선호를 보존한다.

성능 주 지표는 Auto 입력 사이 (N-1)/Δt다. UI 왼쪽의 전체 클릭/게임 경과 CPS는 별도 통계다. 같은 보드 재플레이는 아래 계약으로 수용했다. 거리 관람은 추가됐지만 burst 처리량 보장·B1 동일 owner별 60입력·일반 안정 상한은 미확정이다. 실제 거리 간격은 관람 대기에 계산·통신·검증 시간이 더해지므로 배속과 CPS는 비례하지 않는다. 세 K 정책의 Main 라벨에서 “(실험적)”을 제거했지만 연구/Production 판정은 그대로다.

[고속 CPS 제한 진단](docs/stage3-extended/STAGE3_MAIN_LIVE_HIGH_CPS_DIAGNOSTIC_CLOSEOUT.md)은 source333/cd8ee2e에서 V1/K-LC1의 고정0ms·하네스 MIN/TRACE/MIN 여섯 run을 독립 수용했다. 실제 입력 후 `_apply_live_action`의 Replay·render·통계 갱신이 ACK 게시 앞에 있고, 정확 ACK 뒤 NEXT가 이어진다. 부모 단일 process anchor만 gap을 비중첩 분할하며 worker 계산/검증·transport·UI 소계는 중첩 설명이다. 성공 read_next와 render_board가 후속 분해 후보지만 순수 poll/IPC 원인·안정 상한은 미확정이고 최적화는 미수행이다. setup timerType1을 실행 중 Auto timer의 관측으로 쓰지 않으며 고정 모드 PreciseTimer 계약은 유지한다.

후속 22회 진단 당시의 렌더 후보는 미채택·복원했다. 원 main의 outer Job 미적용 PARTIAL은 보존하며, 외부 측정 helper 보완과 T1/T2는 별도 독립 수용이다. 이후 실전 고정 6 CPS 작업의 G01에서 실제 owner/worker graph를 검증해 해당 helper 재사용 조건을 채웠다. 이 외부 controller는 일반 Main의 제품 worker 구조를 교체하지 않는다.

현재 `_render_cell`은 목표 스타일시트와 widget의 실제 `styleSheet()` 문자열이 다를 때만 setter를 호출한다. font/text 경로와 외부 스타일 변경의 복구는 유지한다. `LivePolicyJob`은 private 채널의 `QFileSystemWatcher` 알림에서 기대 worker 파일의 존재를 확인하고 기존 `poll()`만 호출한다. 힌트는 입력 승인이 아니며 25ms fallback, 원 deadline, strict read/seq/nonce/token/ACK 검증을 유지한다. watcher는 채널 삭제 전에 disconnect/remove/deleteLater하며 늦은 알림은 기존 상태 가드로 거부한다.

이 결합본의 원본 대비 직접 3쌍은 간격 개선 중앙값 12.484226%, CPU/입력 +3.856749%로 사전 기준 안이었다. 앞선 C2의 C1 대비 추가 효과 4.820778% < 5% 및 CPU +13.17%는 별도 비교 결과로 유지한다. Git 보호 도구에는 `diff.autoRefreshIndex=false`와 모든 Git 읽기 뒤 최종 index 해시 기록을 적용했다. 과거 index raw-byte gate FAIL을 소급 수정하지 않는다.

```text
사용자 입력 / Live Auto timeout
→ UI의 단일 action 경로
→ engine.step(x, y, action) 한 번
→ step 이후 경과 시간으로 Replay event 기록
→ 실행 분석 무효화 → 같은 Auto context의 HIDDEN 확정색만 보관 → 보드·통계 갱신
→ 분석 표시 ON이면 fresh observation으로 분석 → overlay
→ Auto ON이고 실행 가능한 추천이면 다음 timeout 예약
```

UI는 화음 입력 방식을 OPEN/CHORD 같은 action으로 변환한다. 실제 화음 성립 조건, 연쇄 개방과 승패는 engine이 처리한다. Live 기본 통계는 engine에서 받고, 일부 파생 Counters 조합은 UI에 남아 있다.

<a id="physical-mouse-input"></a>

**Physical mouse gesture policy** — L/R은 현재 held button 상태다.

| 모드 | Press / release 의미 |
| --- | --- |
| A — left-click chord | R press target에서 즉시 FLAG/UNFLAG; R release는 FLAG에 inert. L release는 target에 따라 OPEN 또는 revealed-number CHORD. R을 누른 중에도 L-release CHORD가 가능하고, L hold 중 여러 R cycle은 독립적으로 FLAG한다. |
| B — both-button chord | 단독 R press는 즉시 FLAG/UNFLAG. L이 먼저 held이면 R press FLAG를 억제하고 BOTH를 arm한다. R hold에 L이 합류해도 BOTH를 arm하되 이전 R action을 되돌리지 않는다. Press origin은 일치할 필요가 없다. |
| C — chord disabled | A와 같은 즉시 R-press FLAG/UNFLAG와 inert R release. Hidden target의 L-release OPEN은 유지하며 revealed-number 또는 L/R overlap으로 CHORD하지 않는다. |

Mode B의 armed overlap은 **어느 버튼이든 첫 release**에서 소비되고, 현재 release
pointer target에 정확히 한 CHORD를 시도한다. 보드 밖 release도 overlap을 소비한다.
같은 overlap의 trailing release는 추가 OPEN/FLAG/CHORD를 만들지 않는다. 남은
버튼을 유지한 채 빠진 버튼을 다시 press하면 새 overlap을 arm하므로 all-buttons-up을
요구하지 않는다. Mode A/C에서는 L hold 중 새로 FLAG된 같은 target을 L release로
열지 않으며, 다른 unflagged hidden target은 정상 OPEN할 수 있다.

Ordinary L-held preview는 유지한다. Mode-B BOTH preview는 현재 pointer를 따라
HIDDEN, FLAGGED 또는 revealed 0..8 중심을 포함한 3×3 영역의 HIDDEN 칸을 누름 표시한다.
FLAGGED 중심 자체는 flag/undepressed 상태를 유지한다. 첫 release 후 BOTH preview는
끝나고 남은 single-button 표시로 돌아간다. Reset/rebuild/difficulty, hide/deactivate,
Replay 진입·종료와 cell-size 변경은 stale held input을 무효화한다.
Engine은 physical press/release/origin 정책을 모르며 semantic OPEN/FLAG/CHORD와
기존 active/wasted 규칙만 처리한다.

아래 갱신 규칙은 기존 Simple 경로다. 수동 `현재 상태 분석`은 행동을 실행하지 않는다. `분석 표시`가 OFF이면 그 결과는 다음 행동에 지워지고, ON이면 매 행동 후 갱신된다. Auto는 single-shot QTimer로 추천 하나만 예약하며, timeout에 observation 일치 여부와 HIDDEN target, 첫 수 정책의 유효성을 다시 검사한다.

추측 허용이 OFF이면 guess 추천과 overlay를 유지한 채 대기한다. 사용자가 직접 행동하면 Auto/guess를 끄고 예약을 취소한 뒤 새 상태에서 표시를 갱신한다. Reset·난이도 변경·Replay 진입·창 닫기·게임 종료·분석 오류도 예약을 취소한다. 행동을 여러 개 queue하지 않으며 비종료 Auto 행동 후 HIDDEN 수가 줄지 않으면 중단한다.

#### Main/Live 같은 보드 기록과 Replay 전환

`live_same_board.py`의 FixedLayout/FixedOrigin/CompletedLiveGame은 GUI 전용 불변 모델이다. Live WON/LOST·원 입력 확인·owner 정리 후 원 dimensions/지뢰 수/전체 mine 좌표로 모두 닫힌 새 판을 만든다. 새 game_id·세대·시간/입력/Replay/M과 Auto/guess를 초기화하되 정책·속도·표시 선호는 유지한다. layout은 engine 재설정에만 쓰고 public worker snapshot에는 넣지 않는다.

고정판은 FIXED_BOARD provenance로 시작하며 CANONICAL_NEW 안전 첫 수를 재사용하지 않는다. revision0/all-HIDDEN에서도 첫 proposal부터 공개 관측의 정상 분석·선택, guess gate를 거친다. 첫 OPEN 지뢰 LOST는 정상이다. 공통 wirev10과 game/entry/definition/세대 결속으로 고정판을 canonical로 위장하지 못하게 한다. V1/K preset/custom 지원 경계는 기존과 같다.

기록은 첫 Live 재플레이로 활성화된 동일 FixedLayout 묶음이다. 현재 완료판은 메뉴/Replay 진입 전 원 Live engine·이력·정리 근거로 캡처하고 game_id로 중복을 제거한다. detached Replay/evidence/source_type은 보존한다. 새 게임/난이도/다른 배치의 성공한 진입/기본 Replay 종료는 그룹·메뉴를 비운다. 같은 배치 재플레이·취소·invalid load는 유지하며 옛 QAction/closure는 무효다. imported/진행 중 Replay를 완료 Live로 만들지 않는다.

Replay 진입은 _ReplayEntryRequest에 원 game/세대/정책/전체 이력·상태/owner와 frozen ReplayData를 결속한다. Auto/guess·입력 예약을 회수한 뒤 Live에서 ACK/cleanup을 기다린다. 원 ACK validator 뒤 observer, 원 finished handler 앞 구체적 실패 guard, finished 뒤 queued commit 순서다. V1은 ACK 검증에 필요한 owner/세대를 유지하고 K는 봉인 receipt drain을 쓴다. 정상 정리 후 단 한 번 전환하며 실패하면 Live와 최초 구체 사유를 유지한다. reset/난이도/정책/수동 첫 press/close는 예약을 폐기한다.

기본 _exit_replay_mode()는 Replay 크기/지뢰 수로 일반 canonical 미배치 새 게임을 만들고 기록을 비운다. keyword-only same_board=True 또는 명시적 같은 보드 버튼은 Replay 원 배치의 fixed 새 판과 기존 동일 배치 기록을 유지한다. 두 경로 모두 가드를 mutation 전에 확인하고 저장 파일을 지우지 않는다. NoFocus 버튼/키 규칙을 유지하며 기존 on_reset의 Replay no-op를 기본 종료 경로로 잘못 호출하지 않는다.

최종 독립49/143·실제 V1 canonical/K-LC1 fixed2owner·probe28과 사용자 native 수용은 [같은 보드 closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_SAME_BOARD_CLOSEOUT.md)에 결속한다. 기존 보호 메서드 본문과 바뀐 호출 경로/signal을 구분한다. B 측정40행은 산술 재현됐으나 B1 동일 owner별60입력은 미충족, C30판/24player의 거리 적합은 민감도 순위 역전이 있어 제품 관람 프로필을 확정하지 않았다. frozen 정책·Model C와 효과성/Production 판정은 유지한다.

### 4.2 UI 없는 동기 runner

`run_simple(engine, *, accept_guesses=False)`는 pure analyzer와 달리 engine을 변경하는 실행 계층이다. [첫 수 정책](#first-click)을 적용한 뒤 **physical action 한 번 → fresh observation → 다시 분석**을 반복한다.

- 기본값은 local/global certainty를 실행하고 실제 guess 직전에 `GUESS_REQUIRED`로 반환한다.
- `accept_guesses=True`이면 guess도 실행한다. Solver 오류는 임의 fallback 없이 전파한다.
- WON/LOST에는 추가 분석·행동을 하지 않는다.
- PLAYING에서 move가 없거나, HIDDEN 대상의 OPEN/FLAG가 아니거나, 비종료 행동 후 HIDDEN 수가 감소하지 않으면 `SimpleRunnerError`다. 임의 step 제한 대신 진행 여부를 검사한다.

결과 `SimpleRunResult`는 frozen dataclass로, `status`, `stop_reason`(`WON`, `LOST`, `GUESS_REQUIRED`), 이번 호출의 `moves`, `replay_data`, 미실행 `pending_decision`, `started_from_hidden`을 담는다. Guess 대기 중 engine status는 PLAYING이다. 중간 합류 기록의 범위는 [schema v1 한계](#replay-schema-v1)를 따른다.

### 4.3 Replay 기록과 재생

Replay 진입은 원 ACK와 owner 정리를 마친 뒤 한 번만 commit한다. 기본 종료는 현재 Replay 크기의 canonical 미배치 새 게임과 기록 초기화, 명시적 같은 보드 버튼은 fixed 원 배치와 기존 그룹 보존이다. 위 Main/Live 계약과 [최종 closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_SAME_BOARD_CLOSEOUT.md)을 따른다.

```text
Live UI / simple_runner
→ engine.step()
→ ReplayRecorder.record_event(step 이후 elapsed_time, 좌표, action)
→ 확정 BoardSnapshot capture → ReplayData ↔ JSON

ReplayData → ReplayPlayer
           → reset_with_mines()로 독립 engine 생성
           → 저장 이벤트 적용 → observation → UI
```

Live UI와 runner 모두 확정 보드를 recorder에 한 번 전달하고 실제 action을 기록한다. 승리 시 engine의 자동 깃발은 별도 physical action/event가 아니다. Runner의 source는 `algorithm`이며 UI의 새 판은 `human`이다. Main의 첫 실제 Auto 입력(준비 UNFLAG 포함)부터 `algorithm`으로 바꾸고 이후 mixed 수동 구간도 non-human으로 유지한다. 분석/Auto toggle만으로 HUMAN을 바꾸지 않는다. `source_type`은 게임 단위 필드이므로 Live Auto와 사람 입력을 event별로 구별하지 않는다. Replay UI는 algorithm/ai를 사용 기록 있음, human을 기록 없음, 데이터 없음을 확인 불가로 표시한다. 옛 JSON의 필드 생략은 기존 decoder에서 human으로 읽으므로 실제 과거 사용 여부를 확정하지 않는다. 알고리즘 이름/정책 변경 이력은 새로 저장하지 않는다.

<a id="replay-index"></a>

**Replay index semantics**

`event_count = len(events)`일 때 다음 계약을 사용한다.

| 값 | 의미 |
| --- | --- |
| `current_index == i` | `events[:i]`를 적용한 현재 position |
| `events[i]` | 아직 적용하지 않은 실제 다음 event (`i < event_count`) |
| `current_event` | 마지막 적용 event인 `events[i-1]`; index 0에서는 `None` |
| `i == event_count` | 모든 event 적용 완료, 다음 event 없음 |
| `current_time` | 마지막 적용 event의 기록 시간; index 0에서는 0 |

`go_to(i)`와 `previous()`는 새 fixed-board engine에서 앞부분을 다시 적용한다. `next()`는 현재 engine에 다음 event를 적용한다. Index 자동 재생 간격, Time 자동 재생의 clock·배속·slider는 UI 책임이다. Time 모드의 화면 시간은 이벤트 사이에서도 진행할 수 있어 `current_time`과 구분된다.

<a id="replay-analysis-flow"></a>

### 4.4 Replay Analysis 갱신

녹화 표시와 참고 분석은 분리된다. replay_display는 현재 index의 저장 event를 읽어 첫 줄과 테두리를 표시한다. 참고 분석 OFF·오류에서도 유지한다. PLAYING의 FLAGGED 대상 FLAG만 UNFLAG로 해석하고, WON/LOST 뒤 저장 FLAG는 자동 종료 깃발 때문에 UNFLAG로 바꾸지 않는다. CHORD는 열린 anchor를 표시하며, 끝·빈 기록·범위 밖 좌표는 안전하게 처리한다.

참고 분석 ON일 때만 현재 공개 observation의 Simple 분석을 수행한다. analyze_replay_step은 먼저 presentation을 완성한 뒤 다음 event를 읽으므로 녹화 입력이 후보 선택에 영향을 주지 않는다. 내부 ReplayStepAnalysis와 비교 API는 유지하지만 UI는 비교 kind/text를 읽지 않고 “Simple 참고 분석 / 참고 후보”와 확정색·이미 계산한 확률만 표시한다. Simple 추천 테두리는 제거한다.

- 참고 분석 OFF: index 이동·분석 버튼·확률/Reduction 토글에서 solver 호출0. 녹화된 다음 입력은 계속 표시한다.
- ON: 진입·index 변경 뒤 fresh 공개 상태를 분석한다. 같은 index의 단순 표시 토글은 재분석하지 않는다.
- Time autoplay: 도래한 event를 적용한 뒤 최종 index를 한 번 분석한다. event가 없는 tick과 slider 동기화는 재분석하지 않는다.
- WON/LOST에서는 solver를 호출하지 않고 참고 overlay를 지운다. 저장된 종료 후 event의 탐색/녹화 표시는 유지한다.
- Live Auto와 추측 허용은 OFF/disabled다. 분석은 action을 실행하거나 저장된 Replay를 수정하지 않는다.

공개 상태 모순·validation/runtime 오류는 참고 overlay만 제거하며 Replay의 index·engine·통계·녹화 입력을 바꾸지 않는다. 이동/재생과 다음 위치의 분석을 계속 허용한다.

### 4.5 Replay Statistics

```text
ReplayData
→ ReplayStatisticsAnalyzer.analyze()
→ ReplayCounterTimeline (초기 상태 + 각 event 적용 후 entry)
→ statistics_at(timeline, index, replay_time, board_zini)
→ UI Counters
```

별도 ReplayPlayer와 BoardAnalyzer로 전체 기록을 한 번 순회한다. Engine의 공개 counter snapshot 차이로 action별 active/wasted를 누적하고, 보드 분석과 observation으로 완료 Ops를 계산한다. 이 과정은 추천 계산과 독립적이다.

마지막 상태가 WON/LOST이면 완료 Replay다. 완료 기록은 현재 위치가 PLAYING이어도 통계를 표시하며, 미완료 기록은 Counters 전체를 마스킹한다. 전체 3BV/Ops와 board ZiNi는 고정되고 진행량·클릭 수는 index를 따른다. 속도 지표는 재구성 engine의 실행 시간이 아닌 UI가 전달한 Replay 시간을 쓴다. ZNE/ZNT는 ZiNi와 현재 total/active 클릭 수로 계산하며 0인 분모는 마스킹한다.

### 4.6 ZiNi worker

Live에서는 첫 OPEN/FLAG로 mine layout이 확정된 직후 불변 snapshot으로 worker를 시작한다. 배치 전에는 실행하지 않고, 같은 보드의 후속 행동은 실행 중이거나 결과 polling을 기다리는 작업을 재시작하지 않는다. 완료 결과는 controller에 저장하되 PLAYING 중에는 ZiNi와 Explorer를 공개하지 않는다. 종료 시 저장된 결과가 있으면 즉시 표시하며, 아직 계산 중이면 placeholder를 유지한다. Replay의 worker 시작과 표시 조건은 기존처럼 완료 기록에 한정된다.

```text
UI policy → ZiniMetricJob: snapshot + shared config + token → private payload
→ Python subprocess worker: ZiNi 계산 → token + clicks + final moves + error
→ ZiniMetricJob: nonblocking poll / token validation / reap / temp cleanup
→ UI policy: 현재 board/mode 결과이면 Counters 반영
```

단일 Counter 설정과 process lifecycle은 PyQt-independent `zini_metric_job.py`가
소유한다. `standard_seeded_chain_v1`, 총 1000 evaluations, standard phase 500,
seed 0, elapsed/stall cutoff 없음이며 bounded best-so-far 값이다. Job이 token을
검증하고 UI는 현재 board/mode 소유권을 확인한다. Worker는 계산과 결과 envelope를
담당한다. `ui_manager`와 standalone Exemplar Viewer가 같은 job owner를 사용하되
각자의 QTimer/시작·표시 정책은 분리한다. Pending/failure는 `-`; board 변경/close는
취소·reap·private-file cleanup을 수행한다. Viewer는 성공 결과를 board fingerprint로
cache하며 같은 board solver 전환이나 navigation/playback은 계산을 재시작하지 않는다.

### 4.7 ZiNi Trace / Explorer

```text
ui_manager → zini_explorer controller → zini_trace → V1 core simulation
          └→ zini_explorer_ui → controller의 불변 결과와 index 탐색
```

Worker는 한 번의 탐색이 반환한 최종 moves를 전달한다. Controller는 해당 job에 전송한 snapshot을 유지하며, Counters 갱신 중에는 Trace를 만들지 않는다. 사용자가 Explorer를 열 때만 `build_zini_trace()`로 최종 경로를 검증·재구성하고 cache한다. 이 과정은 search/RNG를 호출하지 않는다. Trace 실패는 이미 유효한 숫자 ZiNi를 없애지 않는다.

접근 조건은 Live WON/LOST 또는 완료 Replay이며, 완료 Replay에서는 현재 seek 위치와 무관하다. 진행 중 Live와 미완료 Replay에서는 접근할 수 없다. Board/mode 변경은 세션을 무효화하고 창을 닫는다. Explorer만 닫으면 Trace와 논리 index가 유지된다.

Explorer는 처음·이전·다음·마지막, slider와 간격을 조절하는 Index 자동 재생을 유지한다. 헤더는 누적 physical Clicks만 표시하며, 좌표·새 reveals/flags·Premium/tie 진단은 새 창마다 기본으로 접힌 상세 정보에 둔다. 접힌 동안에도 진단 값을 갱신하며 펼침/접힘은 재생 상태를 바꾸지 않는다. 초기 창은 보드 크기와 실제 layout chrome으로 계산하고 화면의 available geometry 이내로 제한한다. 큰 보드와 작은 화면을 위한 QScrollArea는 유지한다. Index 0은 적용 전, N은 논리 move N개를 적용한 상태다. **Replay != ZiNi Trace**: 실제 행동 시간이나 ReplayEvent 모델을 공유하지 않으며, 적용 전 선택 관계는 탐색 phase·beam·RNG 이력을 뜻하지 않는다. Trace schema와 ZiNi semantics version은 각각 1이다.

## 5. 중요한 설계 경계와 invariants

### 5.1 Engine / UI와 상태 소유권

- Engine은 PyQt5·화음 입력 모드·Replay slider를 모른다. `reset()`, `configure()`, `reset_with_mines()`, `step()`, observation/snapshot/counter API가 연동 경계다.
- `step()`의 반환은 `(observation, reward, terminated, truncated, info)`이며 `info`에는 기본 통계가 들어간다. Gymnasium 스타일이지만 Gymnasium environment 자체는 구현하지 않았다.
- 게임 중 범위 내 지원 action은 해당 category의 active 또는 wasted 한쪽에 한 번만 집계한다. Terminal 이후 입력과 범위 밖 입력은 클릭으로 세지 않는다.
- UI의 `self.engine`은 주입된 Live engine을 계속 유지한다. ReplayPlayer는 별도 engine을 소유하며 seek 때 교체할 수 있어 UI는 현재 모드의 engine을 매번 선택한다.
- Replay 종료의 기본은 같은 Live engine을 현재 Replay 크기의 canonical 새 판으로 재구성하고 그룹을 비우는 것이다. 명시적 같은 보드 선택만 원 layout의 fixed 새 판과 그룹을 유지한다. 이전 Live position의 재개 기능은 아니다.

<a id="public-information"></a>

### 5.2 Public observation과 hidden-information isolation

좌표는 `(x, y)`, 배열 접근은 `observation[y][x]`다. Solver 입력은 사람에게 보이는 **0..8, HIDDEN, FLAGGED**와 공개 총 지뢰 수뿐이다. Engine의 terminal 전용 상태 코드(EXPLODED/MINE/FALSE_FLAG)는 solver 입력이 아니므로 호출자가 종료를 먼저 처리한다.

`analyze_position()`은 engine, BoardSnapshot, ReplayData나 hidden mine layout을 받지 않는다. 입력을 변경하거나 행동을 실행하지 않고 같은 공개 입력에 같은 결정을 반환한다. Snapshot API가 public이라고 해서 그 안의 지뢰 정보가 solver의 public observation이 되는 것은 아니다.

Replay 추천 경로도 다음을 decision input으로 사용하지 않는다.

- `ReplayBoard.mine_positions`
- `BoardSnapshot.mines`와 `BoardSnapshot.adjacent`
- ReplayPlayer가 재구성한 engine의 hidden board layout

다음 Replay event는 [추천 계산 완료 후](#replay-analysis-flow) 비교 용도로만 읽는다. 재생 복원·기록·Replay Statistics·ZiNi가 실제 layout을 사용하는 경로와 분리한다. Live/runner의 첫 수 확인에서는 snapshot의 **`mines_placed` boolean만** 정책 입력으로 사용하며 layout은 읽지 않는다.

Simple/Replay 및 일반 frozen planner는 깃발을 지뢰로 가정한다. V1 인수는 그 전에 detached FLAG-free view의 직접 zero/all+전체수 zero/all로 검토해 PROVED_MINE만 유지하며 SAFE/UNVERIFIED를 준비 토글로 해제한다. UNVERIFIED는 실제 안전/오답 판정이 아니며 hidden truth/counter 차이를 사용하지 않는다. Analyzer는 local 추론 전에 개별 clue와 `0 <= num_mines - flag_count <= hidden_count`를 검증한다. Local 경로는 직접 모순과 안전/지뢰 충돌을 확인하지만 전체 constraint 만족 가능성을 검사하지 않는다. 전체 world의 존재 여부는 probability 경로에서 검사한다. 따라서 감지되지 않은 잘못된 깃발까지 교정하거나 certainty의 실제 안전을 무조건 보장하지 않는다.

<a id="first-click"></a>

### 5.3 FIRST_CLICK: Live와 Replay의 서로 다른 정책

Engine은 **미배치 상태의 첫 OPEN 한 칸만** 지뢰 후보에서 제외한다. 주변 8칸의 안전이나 첫 숫자 0은 보장하지 않는다. 먼저 FLAG하면 안전지대 없이 지뢰를 배치하며, 이를 해제해도 배치는 유지된다. `reset_with_mines()`도 지정된 배치를 그대로 사용한다.

아래는 기존 Simple/runner/Replay의 PLAYING 정책이다. V1/K의 CANONICAL_NEW는 fresh provenance·placement 전·all-HIDDEN·revision0·cursor(0,0)·owner seq0에 결속된다. 기본 Replay 종료는 이 일반 새 판 규약으로 돌아간다. 명시적 FIXED_BOARD는 이미 배치된 공개 all-HIDDEN 상태로 정상 분석/guess gate를 거치며 initial 안전 예외가 아니다. 수동 입력/FLAG→UNFLAG 뒤 all-HIDDEN도 ADOPT_CURRENT seq0이며 guess gate를 따른다.

| 상황 | 분석·실행 정책 |
| --- | --- |
| Live fresh game / runner 시작: all-hidden이고 `mines_placed=False` | Solver를 거치지 않고 `OPEN (0, 0)`을 첫 수로 사용. UI는 추천을 표시하고 Auto가 켜졌을 때 실행; runner는 직접 실행 |
| Live/runner: 이미 지뢰가 배치된 all-hidden 보드 (FLAG → UNFLAG 또는 fixed board) | 일반 `analyze_position()` 적용. Guess라면 추측 허용 정책에 따라 대기/실행 |
| 열린 칸이나 FLAGGED가 있는 Live/runner 시작 | 현재 observation을 바로 분석 |
| Replay: index 0 + all-hidden + PLAYING | Full-game fresh start를 가정해 `first_click_presentation()` 표시. Snapshot을 읽거나 solver를 호출하지 않음 |
| Replay: index > 0의 all-hidden + PLAYING | 일반 fixed-layout 확률 분석 |

`FIRST_CLICK`은 별도 시작 정책의 이름이며 `DecisionKind` 멤버가 아니다.
`first_click_presentation()`은 `OPEN (0, 0)` 추천 테두리만 제공하고 SAFE/0% evidence는 만들지 않는다. Pure analyzer만 all-hidden에 호출하면 fixed-layout 확률 `num_mines / HIDDEN 수`를 계산한다.

ReplayPlayer는 fixed board로 복원하므로 index 0부터 `mines_placed=True`다. Replay의 첫 수 표시는 복원 보드의 (0, 0)이 안전하다는 판정이 아니며, [schema v1의 full-game 가정](#replay-schema-v1)에 따른 비교 기준이다.

<a id="replay-schema-v1"></a>

### 5.4 Replay schema v1과 continuation의 한계

현재 v2는 Human Mouse Trace attachment를 추가한다. `ReplayEvent`의 action/좌표/
elapsed-time 계약은 그대로이고 v1도 계속 읽을 수 있다. v2는 Human trace가 있는
기록에 쓰며 v1은 trace-free다. 두 버전 모두 아래 continuation metadata의 한계를
해결하지 않으며 trace segment를 Replay 시작 상태 metadata로 해석하지 않는다.

v1에는 board, events, 게임 단위 source_type과 schema_version이 있다. **Full-game/continuation/suffix 구분, 시작 observation, 이전 클릭 이력 metadata는 없다.** ReplayPlayer는 항상 클릭 없는 fixed board에서 시작하므로 중간 상태에서 시작한 구간만으로 원래 position을 복원할 수 없다. 이 구간도 Replay Analysis에서는 위 index 0 정책을 적용받는다.

Runner는 이번 호출의 실제 행동만 기록하고 가짜 초기화 클릭을 추가하지 않는다. `started_from_hidden=False` 결과는 continuation이며, 이전 기록이 있다면 동일 board와 시간 순서를 유지해 `previous.events + result.replay_data.events`로 연결해야 한다. 이미 종료된 engine에 호출하면 새 moves/events는 비어 있다.

`started_from_hidden=True`는 시작 observation이 모두 HIDDEN이라는 뜻일 뿐 첫 수 안전성이나 과거 통계의 완전성을 뜻하지 않는다. 또한 **처음부터 기록했지만 아직 종료되지 않은 partial Replay**와 **중간부터 시작한 suffix**는 다르다. 전자는 저장된 시작 상태부터 재생할 수 있다. v1은 게임 종료 자체를 저장 조건으로 요구하지 않는다.

<a id="replay-comparison"></a>

### 5.5 Replay Analysis comparison

이미 계산된 presentation의 evidence만으로 다음 event를 비교한다. 별도 solver 호출이나 move 재선택을 하지 않는다.

| 비교 kind | 의미 |
| --- | --- |
| `EXACT_RECOMMENDATION` | 추천과 action 및 좌표가 모두 일치 |
| `EQUIVALENT_CANDIDATE` | 다른 SAFE 칸의 OPEN, 다른 MINE 칸의 FLAG, 또는 PROBABILITY_GUESS에서 정확히 같은 최소 위험을 가진 후보의 OPEN |
| `DIFFERENT` | 비교 가능한 HIDDEN 대상 OPEN/FLAG이지만 위 조건에 해당하지 않음 |
| `UNSUPPORTED_ACTUAL` | CHORD, FLAGGED에 FLAG(UNFLAG), 이미 열린/깃발 칸 대상 행동 등 solver의 행동 계약 밖. Terminal로 presentation이 없는 경우도 포함 |
| `NO_NEXT_ACTION` | 다음 event가 없음 |

GLOBAL_CERTAINTY의 다른 0% OPEN/100% FLAG도 동등 후보다. FIRST_CLICK에는 SAFE evidence가 없으므로 다른 첫 OPEN은 DIFFERENT다. **DIFFERENT는 내부 비교 분류이며 오답·실수·나쁜 수의 판정이 아니다.** 현재 UI는 이 비교 문구를 노출하지 않는다. 녹화된 다음 입력의 첫 줄·테두리와 Simple 참고 표시를 분리하며, 내부 비교 데이터는 그대로 유지한다.

### 5.6 Reduction / Probability 표시

`live_analysis.py`는 기존 decision의 move와 evidence를 표시 모델로 옮기며 추천을 다시 고르지 않는다. 확정 안전/지뢰, 최소 위험 후보, 그 외 불확실한 칸과 선택된 추천을 구분한다.

Reduction은 열린 숫자를 화면에서만 `N-F`로 바꾼다. 양수는 숫자, 0은 blank, 잘못된 깃발로 음수가 되면 음수로 표시한다. Cell state 판정·solver 입력에는 원래 observation을 유지해 음수를 HIDDEN 등의 상태 코드로 오해하지 않게 한다.

확률 표시 ON/OFF는 이미 계산된 analysis 결과를 다시 표시할 뿐 계산 경로나 추천을 바꾸지 않는다. Local inference에서는 확률을 추가 계산하지 않는다. 확률은 P(mine)이며 근사 표시가 0%/100%로 반올림되어 certainty처럼 보이지 않도록 `<1%`, `>99%` 등을 사용한다.

<a id="zini-results"></a>

### 5.7 ZiNi 결과의 의미

ZiNi는 실제 mine layout을 사용하는 board metric/analysis다. 가상 상태에서 안전 칸 개방과 실제 지뢰의 FLAG/CHORD 비용을 계산하며, [public-information solver](#public-information)와 목적이 다르다.

| 계산 API | 보장 범위 |
| --- | --- |
| `calculate_g_zini()` | 최대 Premium과 고정 tie-break/fallback 정책으로 생성한 deterministic 클릭 경로 |
| `calculate_g_zini_min_ties()` / `calculate_g_zini_min_ties_bounded()` | 최대 Premium 동점 후보 안에서 더 짧은 경로 탐색. Bounded API의 시간·상태 제한은 선택 사항 |
| `calculate_g_zini_neighborhood_beam_bounded()` | deterministic 결과를 유효한 baseline으로 두고 제한된 neighborhood를 탐색한 best-so-far |

Min-ties의 `exact=True`는 **그 동점 탐색 범위**를 완료했다는 의미다. 제한에 걸리면 `exact=False`와 종료 metadata를 반환한다. Advanced 결과의 `exact`는 항상 False이며 `TIME_LIMIT`, `EVALUATION_LIMIT`, `STALL_LIMIT`, `SEARCH_EXHAUSTED`로 종료 이유를 구분한다. SEARCH_EXHAUSTED도 설정된 전략의 후보 소진일 뿐이다.

어느 bounded 결과도 전역 최적해, 이론적 최소 클릭 수, 모든 정책 중 최선을 증명하지 않는다. 고정 seed와 evaluation budget의 재현성은 테스트하지만 wall-time 제한이 있는 실행의 결과까지 동일하다고 보장하지 않는다.

2026-10-13 [ZiNi 최종 판정](docs/zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md): TYPE S 최적화와 Trace/Explorer를 수용하고 V1 품질 정책을 유지한다. V2 A/B/C 정책과 연구 semantics는 미채택이며 lambda는 production parameter가 아니다. 연구는 종료했고 최종 holdout은 미개봉 상태다.

<a id="test-strategy"></a>

<a id="stage4-public-planning"></a>

## Stage 4 공개 정보 계획 기반 — 한정 수용

`stage4_opening.analyze_openings`는 공개 숫자와 전체 지뢰 수에 맞는 배치 수 D, 후보가 지뢰인 수 M, 후보와 이웃이 모두 안전한 수 Z를 정확한 정수로 제공한다. 물리 깃발은 추론용 사본에서 HIDDEN으로 정규화한다. 이 모듈의 `query_order`는 질의 순서이며 전체 플레이 전략이 아니다.

`stage4_planning.plan_next(PlanningRequest)`는 별도 공개 DTO와 counted 입력 원장의 총 C만 받는다. 원장 항목은 action·좌표·counted·공개 관측 ID다. 실제 배치·BoardSnapshot·active/wasted 분리값·진행 3BV/ops·ZiNi는 정책 입력과 키/trace에서 제외한다. 실제 보드 정보는 평가 harness가 별도로 보유한다.

가상 배치는 공개 제약에서만 생성하며, 동일한 공개 결과를 묶은 뒤 공통 다음 수를 선택한다. 후보군 `progress_preparations_v1`은 직접 OPEN/깃발 해제 OPEN, 기존 CHORD와 여러 칸을 여는 CHORD의 정준 FLAG 준비를 비교한다. 모든 FLAG/OPEN/CHORD는 각각 1입력이고 자동 확장은 추가 입력이 아니다. 단일 대상 준비 CHORD와 비정준 준비 순열 등의 제외를 명시하며 전체 정책 최적성을 주장하지 않는다.

S는 안전 조건 안에서, M은 추측 설정 안에서 완주 성과 E[X]를 최대화한다. R은 명시적인 목표 IOE 도달 확률을 최대화한다. X는 WON의 3BV/C이며 LOST와 추측 OFF의 `GUESS_BLOCKED`는 0으로 평가하되 별도 집계한다. S의 불가피한 추측은 HIDDEN과 FLAGGED 전체의 최소 위험 OPEN이며, 해제 비용도 포함한다.

한 번에 최대 한 입력만 반환한다. 수순 score는 선언 후보군의 준비 수순 평가값이다. 모든 후속 호출이 exact이면 매 입력 재계획 정책의 **주 목적값에 대한 하한**이며 일반적인 동등성은 미증명이다. 한도 때문에 준비 도중 다음 호출이 실패할 수 있으며, Unit 3 평가기는 이를 `UNRESOLVED`로 기록한다. 부분 trace는 진단용이며 전체 행동 권한이 아니다.

지원 상한은 전체 64칸, 닫힘/깃발 8칸, 배치 256개, 원자 깊이 12, 전개 50,000개, 호출 10초다. 미완료는 action/score/terminal이 없는 `INSUFFICIENT`이며 Main/Live에 fallback이나 실행 권한을 연결하지 않았다. 현 단계의 native/UI 검증은 해당하지 않는다. 상세 범위와 9개 비차단 권고는 [Stage 4 closeout](docs/stage4/STAGE4_OPENING_PLANNING_FOUNDATION_CLOSEOUT.md)을 따른다.

`stage4_evaluation`은 `PublicCase`/`prepare_case`로 전체 공개 posterior와 실제 prefix 재생을 결속하고, `Settings`/`plan_trials`/`Budget`/`run_attempt`/`aggregate`로 한 입력씩 실행·집계한다. 실제 배치와 3BV는 평가기만 소유하며 `public_request`는 공개 필드만 받는다. WON/LOST/GUESS_BLOCKED/UNRESOLVED와 NOT_STARTED를 구분한다. 미완료 질량을 분모에서 없애지 않고 완전 평균 null·coverage·정확한 유리수 구간을 기록한다. `aggregate`는 전달된 완전 등록과 Attempt를 신뢰하는 API이며 임의 외부 입력 검증기로 주장하지 않는다.

Unit 3은 신규 17개 시험과 독립 실제 정책 174시도 재생으로 한정 수용됐다. 최종 36설정 MATCH, 123건은 신규 113 + 동결 전 재사용 10이고 4설정은 전량 재사용이다. 낮춘 depth 3/5의 8사례는 FLAG 뒤 미완료를 재현했고, 기본 12의 28배치는 모두 종결했다. 이는 일반적인 재계획 연속성 증명이 아니다. 제품 필수 수정은 0이며, 응답 형식·emit 실패의 일부 예외 경로는 기록된 UNRESOLVED 대신 예외로 나갈 수 있다는 비차단 한계가 있다. 상세 처분과 U3-H01 영구 공백은 [평가기 closeout](docs/stage4/STAGE4_EVALUATION_UNIT3_CLOSEOUT.md)을 따른다.

stage4_belief.count_public(BeliefRequest, cancelled=...)는 독립된 공개 계수기다. 물리 FLAG를 identity에 보존하면서 미지수로 취급하고, 숫자 제약의 component별 정수 histogram·prefix/suffix 합성곱·비제약 칸 조합 수로 D/M/W를 구한다. W는 여러 칸이 동시에 안전/지뢰인 공동 사건이며 주변확률의 곱이 아니다. 정수와 Fraction은 손실 없는 문자열로 직렬화한다. action·E[X]·목표 도달 확률을 반환하지 않으며 기존 계획기와 UI의 import 경로에 연결하지 않았다.

Unit 4의 상한은 480칸/정준 사건 16개/work 200,000/협력 시간 2초다. base와 모든 사건이 한 예산을 공유하고 열거·DP 곱셈마다 검사한다. base D/M은 전체 완료 뒤 원자적으로 공개하며, 사건 중단 시 PARTIAL로 exact base와 완료된 사건만 남긴다. D=0 모순, W=0 불가능 사건, null 미완료를 구분한다. 0 한도와 비활성 CHORD의 None도 명시된 API다. 요청 생성·identity·publish 일부·직렬화에 비중단 구간이 있고, 현재 Windows/Python 3.12.10 monotonic은 약 15.6 ms 단위이므로 2초는 실시간 응답 보장이 아니다.

독립 검토는 작은 32관측/13,627 bitmask, 분석해 7요청과 Replay 6관측의 D/M/W를 모두 재계산했다. Replay의 M 1,956개와 공동 사건 37개가 일치했고 component M 346개는 두 번째 방법으로 확인했다. EXACT 37개 중 W=0은 19개, W=D는 7개, 중간 확률은 11개여서 일반 큰 frontier 비용 근거로 확대하지 않는다. 새 시험은 A 17개와 B 4개의 별도 실행이다. 예상 UTC의 원시 오류 등 5개 비차단 처분은 [Unit 4 closeout](docs/stage4/STAGE4_PUBLIC_COUNTS_UNIT4_CLOSEOUT.md)에 남겼다. 일반 상급판 지원·효율·Main/Live 통합은 후속 범위다.

`stage4_candidates.analyze_candidates(CandidateRequest, cancelled=...)`는 Unit 4의 공개 API만 사용해 `progress_preparations_evidence_v1` 후보를 만든다. 모든 닫힌 OPEN과 해제 OPEN, 양수 숫자의 최종 FLAG 조합·대칭차 편집·CHORD를 열거하고 전체 sequence 길이를 비용으로 센다. 기존 1대상 CHORD와 생존 0 후보를 보존하며 편집 1대상 CHORD는 제외한다. Ws는 모든 직접 대상 T의 공동 안전, Zt는 T와 각 대상의 이웃 전체가 안전한 공동 사건이다. S/M/R의 위험 eligibility만 표시하며 최종 선택/종단/E[X]는 반환하지 않는다.

후보/사건에 하나의 한도를 적용하고 exact base와 완성된 근거만 보존한다. 상한은 생성 4,096/후보 2,048/새 사건 512/backend 33/work 500,000/협력 10초이며 각 backend는 기존 상한과 남은 예산을 따른다. 중단 뒤의 제한된 materialize는 시간 한도 밖이므로 hard real-time 보장이 아니다. S의 안전 칸 부재 규칙도 생존 가능한 최소 M의 직접 OPEN만 허용한다.

새 시험은 A 25개/B 1개의 별도 실행이다. 24관측과 339 engine macro, 큰 6관측의 고유 사건 4,699개가 독립 일치했다. 국소 하한 비율과 0 대상 수를 최종 IOE나 독립 오프닝 개수로 해석하지 않는다. 코드로만 확인된 7종 응답 방어, backend 내부 취소/시간 미시험, 최초 controller 부재의 원시 공백은 [Unit 5 closeout](docs/stage4/STAGE4_CANDIDATE_EVIDENCE_UNIT5_CLOSEOUT.md)에 구분했다.

### Unit 6 posterior / rollout / 실제 선택

`stage4_policy.RolloutPolicy.select_next(PolicyRequest)`는 공개 grid·총 지뢰 수·counted 합 C·S/M/R·guess·target·공개 seed·episode·limits·continuation으로 원자 입력 하나를 반환한다. Main/Live와 연결하지 않은 순수 계산 API다.

`stage4_posterior`는 component histogram과 suffix/binomial의 정확한 정수 rank를 균등 추출한다. D≤N은 전체 배치, 그 외 복원추출이며 중복 slot과 공통 bank를 유지한다. 실제 배치나 board seed는 입력하지 않는다.

`stage4_rollout`의 가상 layout/B는 evaluator만 소유한다. 고정 P0는 공개 grid/지뢰 수/C/guess와 자원 제한만 받는다. 모든 후보×동일 bank가 종결된 경우에만 mean/win/hit를 비교한다. 이 값은 고정 P0 모델의 값이며 실제 재계획 정책의 정확한 성과가 아니다. 미완료는 null이다.

root의 위험 허용은 Unit 5 exact 근거를 따른다. S/M은 모델 평균, R은 양의 target 달성률을 우선한다. 모델 한도에는 완전한 root를 가진 명시적 fallback을 허용하지만 global timeout/cancel·root incomplete·model error는 입력을 내지 않는다. basis는 READY와 함께 해석한다. 32개 fallback 표기 중 실제 입력 반환은 29개이고 나머지 3개는 오류/취소의 잔존 필드다.

FLAG 준비 continuation은 같은 RolloutPolicy 인스턴스의 공개 발행·소비 상태와 예상 grid/C에 결속된다. 매 입력 뒤 현재 exact 후보로 재검증한다. 미적용 입력 후 같은 위치는 계속 STALE이므로 인스턴스 수명·복구는 이후 UI/worker 계약에서 다룬다.

Unit 6 독립 ACCEPT_BOUNDED와 필수 수정 0, 당시 큰 18호출의 fallback을 과거 기록으로 보존한다. [Unit 6 closeout](docs/stage4/STAGE4_ROLLOUT_POLICY_UNIT6_CLOSEOUT.md)에 W1~W3, N1~N9, U1~U8과 U6-R02 영구 공백을 기록했다.

### Unit 7 색인 P0와 모델 완료 범위

P0 `PUBLIC_LOCAL_COST_P0_V2_INDEXED_HINT`는 전역/숫자별 잔여 밀도를 한 번 만들고 관련 미지수에 max를 전달한다. 추측에 도달하면 안전 집합이 비어 있어 기존 힌트와 선택이 같다. 추론·5,000 subcap·안전 후보·가상 전이·보상은 byte 동일하다. 이 힌트는 정확한 지뢰 확률이 아니며 P0가 기존 Simple 정밀 확률을 호출하지 않는다. work ID는 `P0_WORK_V2_RESIDUAL_CONSTRAINT_EDGES`다. 개별 P0 상한 20,000, 제품 aggregate 기본 10M을 유지하고 허용 상한만 30M으로 넓혔다.

등록 354건(고유 150)의 의미와 각 버전 work가 독립 재현됐다. 기본 10M은 6/18 완료·12 fallback이고 완료 6건 모두 모든 후보 모델 점수가 0이다. EXPANDED 30M은 18/18 완료·9건 전 후보 점수 0이며 12요청은 10M을 넘는다. 가상 3,456행과 실제 소보드 10경로(6승/3패/추측 금지 1)가 재현됐지만 일반 효율은 미확인이다.

Phase B의 12입력 중 8개는 같은 코드를 실행하며 비율이 0.7684~1.0245로 흩어진다. 변경 구간 4개의 비율도 그 안에 있어 속도 개선은 미확립이다. CPU 46/96이 0이고 양의 최소는 15.625ms라 단일 호출 CPU 개선도 주장하지 않는다. 34 PASS는 5+29 별도 실행이다. Unit 6의 30.0과 Unit 7 exact_json의 "30"은 같은 수치 한도지만 policy request_id가 36/36 다르다.

[Unit 7 closeout](docs/stage4/STAGE4_INDEXED_P0_UNIT7_CLOSEOUT.md)에 W1~W4, N1~N5, U1~U8와 U7-R01 공백을 남겼다. 공통 P0의 정확 확률 보완과 S/M/R별 후속 목적은 새 계약/모델 버전으로 검증할 다음 범위이며 이번 변경에 포함되지 않는다.

### Unit 8 공개 정밀 확률 Q / 목적별 평가 G

`stage4_exact_pilot.ExactPilot`는 공개 grid·지뢰 수·counted C·guess·prior·limits만 받는다. P0 V2의 guess=False 안전 경로 뒤에 Unit 4의 정확 D/M을 사용한다. FLAG는 미지수이고 정확 안전/지뢰 집합으로 OPEN·해제·CHORD 준비의 전체 비용을 비교한다. 안전 부재가 증명된 때만 최소 위험 추측이나 GUESS_BLOCKED가 가능하다. 완료 base만 최대 256개 FIFO 캐시에 보관하며 새 요청의 0한도·시간·취소 검사를 우선한다.

`stage4_objective_pilot.choose_objective`의 G는 Unit 5 후보와 공통 posterior bank로 후보 뒤 Q를 평가한다. 실제 B와 배치는 가상 평가자만 보유하며 Q에는 주지 않는다. S/M/R의 목적을 유지하고 모든 N16×K6 행이 완료돼야 점수와 수순을 발행한다. 미완료는 null이며 fallback을 추가하지 않았다. 실제 입력마다 G를 다시 호출한 값과 후보 뒤 Q 모델값은 다를 수 있다.

개별 Q는 local 20,000/exact 200,000/최대 2초와 G 잔여 한도 중 작은 값을 받는다. 등록된 G 기본 exact20M/local10M/30초는 0/18, 확대 exact60M/local30M/30초는 3/18 완료다. 기본 local 12건은 합계 cap, exact 6+6건은 개별 cap, 확대 8+1건은 부모 30초 또는 남은 시간에 막혔다. 일반 성능·효율·실전 정책 수용이 아니다.

제품 축 ACCEPT_BOUNDED, 원 전체 PARTIAL/U8-H05·원 manifest 부재·R02/R03 공백을 유지한다. Q 15/G 14 시험은 별도 실행, 작은 G 102건·엔진 24 trial이 독립 재현됐다. 큰 Q 92,545건의 결정은 각 저장 base와 대조했으며 큰 base 자체를 전수 재계수한 것은 아니다. [Unit 8 상세](docs/stage4/STAGE4_EXACT_OBJECTIVE_PILOT_UNIT8_CLOSEOUT.md)에 W1~W5, O1~O4, U1~U6와 helper의 좁은 보정 범위를 기록한다.

### Unit 9 보존 후보 — 현재 제품 미적용

보존된 `stage4_belief_accel`은 잔여 제약 전파·정규화·메모와 지뢰 수 histogram의 lift를 사용한 base-only 정확 계수 후보다. `stage4_exact_accel`은 G별 READY FIFO와 execution profile을 제공했다. 두 기존 파일의 작은 연결과 신규 다섯 파일은 실행 snapshot으로만 보관하고 repo는 Unit 8 bytes로 복구했다.

후보 수학 CORRECT_BOUNDED, 실측 REPRODUCED, 새 Job 12개 수용, 필수 발견 0이다. 기본 완료0→3/18과 확대3→3/18로 채택 기준을 충족하지 못해 PARTIAL_IMPROVEMENT 및 원복이 정당하다. 상세는 [Unit 9 closeout](docs/stage4/STAGE4_EXACT_COMPLETION_UNIT9_CLOSEOUT.md)을 따른다.

같은 시간·명목 cap 조건이다. 후보 auxiliary는 G exact/local 합계에 미과금이며 별도 호출 cap을 사용한다. 앞으로 재사용하려면 총 auxiliary 예산/비교 단위를 먼저 정한다. 공개 cache_entries는 base만 제어하고 READY는 별도 한도다. READY miss에도 origin이 생기므로 hit는 ready_cache_hit로 판별한다. 상태 없는 choose_exact의 불필요한 cache 삽입과 단독 count_base의 오류 우선순위는 후속 설계 메모다.

실제 F는 macro를 끝까지 적용한 뒤 다음 G를 부르는 24 trial이다. 각 원자 입력마다 재계획하는 구현을 검증한 것이 아니다. 완료 C/D 11 G의1,056행은 독립 재생했지만 미완료 C63/D10의 부분 행은 재생하지 않았다. 원 P01 신원 공백과 기존 PARTIAL은 유지한다.

## 6. 테스트 전략

`unittest`로 규칙 회귀, 순수 계산, 모듈 간 계약과 Qt UI 연동을 나누어 검증한다. 아래는 현재 테스트의 주요 범위이며 모든 보드·플랫폼에 대한 완전성 증명은 아니다.

| 영역 | 테스트 파일 (`tests/` 아래) | 주요 검증 |
| --- | --- | --- |
| Engine regression | `test_engine_regression.py` | 첫 OPEN/FLAG와 FLAG→UNFLAG, 설정 검증·reset, flood/chord 결과, 승패·observation, 타이머, 클릭 분류 |
| BoardSnapshot / BoardAnalyzer | `test_engine_regression.py`, `test_board_analyzer.py` | snapshot 복사·불변성, 미배치 보드 거부, opening/border/isolated와 3BV/Ops |
| Replay model / JSON | `test_replay_model.py`, `test_replay_json.py` | 좌표·개수·시간 순서 검증, fixed-board 복원, JSON round-trip과 오류 |
| Replay recorder / player | `test_replay_recorder.py`, `test_replay_player.py` | capture 조건, 실제 event 누적, index 0·seek·next·previous |
| Physical mouse input | `test_ui_mouse_input.py` | R-press FLAG, Mode A/B/C, origin-independent BOTH·첫 release·re-arm, FLAGGED-center preview와 stale input |
| Human Mouse Trace | `test_mouse_trace.py`, `test_mouse_trace_ui.py`, `test_mouse_trace_overlay.py` | exact/subpixel sample·독립 clock·action 관측, eligibility·Replay v2, geometry/raster cache·oversized fallback |
| Replay Statistics | `test_replay_statistics.py` | 완료/미완료 마스킹, counter·파생 공식, 이벤트 사이 시간, UI engine ownership과 snapshot 선택 |
| Simple local inference | `test_simple_algorithm.py` | 두 직접 규칙, FLAG 우선·동률, 중복 제거, 모순·입력 검증, 비전파·subset 추론 범위 |
| Exact probability | `test_simple_probability.py` | component 분할·전역 결합, floating 조합 가중, 정확한 world 수·Fraction·certainty·move 선택 |
| Probability oracle | `test_simple_probability_oracle.py` | Production helper와 독립적인 작은 complete-board 전수 열거와 비교. 작은 grid의 exhaustive 상태 및 seeded public observation |
| Stage 4 opening | `test_stage4_opening.py` | exact D/M/Z, 공개 관측/깃발 정규화, 상관·전역 지뢰 수, 모순/실패, 작은 독립 배치 oracle |
| Stage 4 bounded planning | `test_stage4_planning.py`, `stage4_planning_oracle.py` | S/M/R, 공개 원장/누설 차단, 공개 분기·원자 비용, GUESS_BLOCKED/한도, 1,017개 주입 전이와 45개 실제 경로의 구분 |
| Stage 4 evaluator | `test_stage4_evaluation.py` | 공개 prefix 전수 재생, 한 입력 후 재계획, 미완료/미시작·분모·구간·정확 산술, 실제 planner 연결. 별도 17개 시험 |
| Stage 4 public counts | `test_stage4_belief.py`, `stage4_belief_oracle.py` | 공개 D/M/W, 물리 FLAG, 전역 지뢰 수, 공동 사건, 한도·취소·부분 결과·원자적 확정. 새 21개 시험은 A 17/B 4로 별도 실행 |
| Stage 4 candidate evidence | `test_stage4_candidates.py`, `stage4_candidates_oracle.py` | 정준 수순·전체 비용·공동 생존/0 사건·eligibility·미완료·engine macro. A 25/B 1 별도 실행과 6 snapshot 대조 |
| Stage 4 rollout policy | `test_stage4_posterior.py`, `test_stage4_rollout.py`, `test_stage4_policy.py`, `stage4_policy_oracle.py` | A 13/B 11(v01)+추가 B 4(v02) 별도 실행. 정수 rank·공개 P0·원자 선택·fallback·continuation·작은 25시도/큰 첫 선택 18회 |
| Stage 4 indexed P0 | `test_stage4_rollout_indexed.py`, `stage4_rollout_reference.py` | 기존 P0 의미·새 work·한도·fixture. 고유 PASS 34=5+29 별도 실행, 독립 재구현 354건, 10M/30M profile 구분. reference는 사본 |
| Stage 4 exact/objective pilot | `test_stage4_exact_pilot.py`, `test_stage4_objective_pilot.py`, `stage4_pilot_oracle.py` | 공개 확률 후속·S/M/R·한도/캐시·원자적 null; Q 15/G 14 별도 실행, 작은 engine 24 trial; 큰 base 전수 재계수 없음 |
| Decision analyzer | `test_simple_decision.py` | local 우선과 probability 생략, 세 decision 종류, mine budget, 불변 입력·공개 API 경계 |
| Runner | `test_simple_runner.py` | 첫 수/guess 정책, 한 행동 후 재분석, 진행 검사·오류, 실제 event 순서, partial/continuation 재생과 정보 격리 |
| Live Analysis | `test_live_analysis.py` | 순수 presentation, 정확한 후보·확률 포맷, 실제 Qt 표시·갱신·Reduction·오류·첫 수 정책 |
| Live Auto | `test_live_auto.py` | timeout당 한 행동, fresh 분석·기록, guess 대기/허용, stale 추천·무진행·취소, 실제 QTimer 첫 수 종료 |
| Replay Analysis pure | `test_replay_analysis.py` | index 의미, 추천 후 event 조회, 숨은 배치 격리, 첫 수·동등 후보·비교 범위, terminal·불변성 |
| Replay Analysis UI | `test_replay_analysis_ui.py` | 실제 Qt controls, 이동/자동 재생별 갱신, 같은 index 재계산 방지, 표시 전환, 오류 복구·engine ownership·Auto 차단 |
| ZiNi deterministic / min-ties | `test_zini_core.py`, `test_zini_calculator.py` | Premium·unit·동작 의미, 고정 trace, 클릭 합계·안전 칸·깃발 유효성, bounded min-ties 종료 |
| ZiNi advanced | `test_zini_advanced.py` | 정책별 rollout, budget·종료 metadata, baseline 유지, 고정 seed/evaluation 재현성, trace 재적용 |
| ZiNi golden / TYPE S | `test_zini_golden.py`, `test_zini_core.py` | 고정 10 workloads의 전체 moves·clicks·non-elapsed metadata, reference Premium 및 solved 판정 동등성 |
| ZiNi Trace / Explorer | `test_zini_trace.py`, `test_zini_explorer.py`, `test_zini_explorer_ui.py` | 사후 Trace 검증, lazy 생성, 정보 gate, index/delta·Qt 표시 및 세션 수명 |
| Stage-3 Extended | `test_stage3_identity.py`, `test_stage3_execution.py`, `test_stage3_trace_player.py`, `test_stage3_modeled_playback.py`, `test_stage3_execution_worker.py`, `test_stage3_visualizer_ui.py`, `test_stage3_execution_job.py`, `test_stage3_visualizer_launcher.py` | identity·incremental 재생·fake-clock exact timeline·synthetic cursor·worker transport·취소·종료·cleanup |
| Same-board domain / execution | `test_same_board_comparison.py`, `test_same_board_runner.py`, `test_benchmark_modeled_actions.py` | Human full-stream admission·exact layout·safe/mined origin·native evidence·분리된 metrics |
| Same-board transport / lifecycle | `test_same_board_execution_worker.py`, `test_same_board_execution_job.py`, `test_same_board_solver_transport.py`, `test_same_board_worker_dispatch.py` | board-only transport·token·parent validation·cancel/reap/cleanup·source/frozen dispatch |
| Same-board playback / UI | `test_same_board_timed_playback.py`, `test_same_board_playback.py`, `test_same_board_comparison_ui.py`, `test_same_board_comparison_launcher.py`, `test_same_board_main_ui.py` | 독립 timing/index·partial pause/catch-up·public observation·Human overlay 분리·captured source·result reopen·main close |
| Neutral reference overlays | `test_visualization_reference_overlays.py`, Same-board/Visualizer UI modules | immutable clues·HIDDEN mask·completed prefix·opacity/z-order·public glyph 보존·partial/toggle no-domain guards |
| Program K research demo | `test_program_k_trace_adapter.py`, `test_program_k_control_trace_adapter.py`, `test_program_k_trace_comparison.py`, `test_program_k_trace_viewer.py`, `test_program_k_trace_comparison_ui.py` | pinned evidence·immutable projection·exact pairing·독립 clocks·committed M·no I/O/execution·R2 presentation |
| Frozen Stage-3 | `test_stage3_runner.py`, `test_stage3_planner.py`, `test_stage3_physical.py`, `test_stage3_telemetry.py` | V1 action/plan·authenticated profile·정수 timing·telemetry 보호 |
| ZiNi worker | `test_zini_worker_dispatch.py` | Qt 없는 실제 source/dispatch subprocess, transport·stale token·실패 처리, 모의 process를 사용한 UI 정리 경계 |

정보 격리 테스트는 solver를 공개 enum만 있는 engine 대체 모듈로 로드하거나, hidden snapshot/layout 접근을 실패시키는 방식도 사용한다. Probability oracle은 answer board로 정답을 주입하지 않고 공개 조건을 직접 열거한다.

Qt 관련 테스트는 offscreen으로 실행하며 일부는 PyQt5 미설치 시 skip된다. Replay Statistics의 UI 책임 검증에는 probe/stub도 사용한다. 실제 QTimer와 Explorer controls/표시 상태 테스트가 있지만 모든 OS 입력·화면·이벤트 순서를 검증하는 것은 아니다. Worker entry-point 테스트는 실제 subprocess를 실행하며, UI lifecycle 테스트의 process 대체와 구분한다. 배포 EXE 및 실제 화면의 worker 취소·종료는 별도 smoke 확인이 필요하다.

실행 명령은 [README 테스트](README.md#테스트)를 참고한다. [Benchmark](README.md#benchmark)는 고정 보드의 전략 비교와 trace 검증 도구이며 단위 테스트나 최적성 증명을 대체하지 않는다.

## 7. 현재 한계와 기술 부채

- **Exact probability 비용:** sampling·cutoff·approximate fallback 없이 component를 열거하므로 큰 연결 component에서 지수 시간이 걸린다. Simple Live와 Replay 참고 분석은 UI thread에서 동기 실행한다. Main V1/K의 원 추론은 기존 contained worker에서 수행하고 부모의 검증·입력·표시는 UI thread에 남는다. 전체 Replay 추천 사전 계산은 없다.
- **Live/Replay의 Simple Algorithm 범위:** 닫힌 칸의 OPEN/FLAG만 선택한다. CHORD/UNFLAG, 장기 승률 최적화, 일반적인 오답 깃발 교정은 제공하지 않는다. 검증 범위는 [정보 경계](#public-information)를 따른다.
- **Replay 저장 표현력:** 중간 합류 및 첫 position 해석의 제약은 [schema v1 한계](#replay-schema-v1)에 정리했다. Event별 human/auto 출처도 구분하지 않는다.
- **Stage-3 후속 범위:** Milestones 1–9와 Program K 연구 데모 D0–D5는 CLOSED다. Effectiveness는 NOT ESTABLISHED, Phase-1은 PHASE1_INCONCLUSIVE_TRANSFER이며 현재 de-dup timing path는 STOP / DEFER다. Extended 전체는 명시적 project-closeout 판정 전까지 ACTIVE다. Stage-3 Visualizer checkpoint/cache, modeled-time slider, persistence와 Foundation Run/결과 열기 라벨 개선은 DEFER이며 Foundation F-2도 OPTIONAL / DEFER를 유지한다.
- **Replay 비용:** 진입 시 통계 timeline을 전체 순회로 생성한다. Seek/previous는 처음부터 재구성하며 checkpoint가 없다.
- **UI 책임 집중:** 파생 Live Counters, Replay 시간·slider·button, Live Auto 정책은 UI에 남아 있다. ZiNi subprocess/config lifecycle은 공유 `ZiniMetricJob`으로 분리되었고 각 UI는 표시/eligibility 정책을 소유한다.
- **ZiNi 실행과 검증:** Counters는 evaluation 수만 제한하므로 실행 시간 상한은 없다. 실제 worker의 실패·취소와 운영체제별 GUI 동작은 자동 검증 범위를 더 넓혀야 한다. 결과의 해석 범위는 [ZiNi 결과](#zini-results)를 따른다.
- **내부 결합:** `zini_calculator.py`가 내부 helper도 재노출하고 전략 모듈이 일부 결과 타입을 지연 import한다. 공개 API와 내부 구현의 경계는 더 정리할 수 있다.

## 8. 향후 확장 방향

현재 기능에 포함되지 않은 개선 후보다.

Same-board Comparison, **Representative-board Demonstrations / Timeline Analytics**,
Selected Exemplar Viewer, Visualization Usability Polish와 Fixed-Exemplar Human /
Domain Interpretation까지 milestones 1–9는 모두 CLOSED다. Stage-3 Extended 자체는
**ACTIVE**이고 현재 milestone 10은 Program K다.

Program K 연구 시각화·비교와 최종 packaged 사용자 acceptance는 완료됐다.
위 Program K 후속 연구의 재개와 별개로 Stage 4 Unit 1~8은 각 범위에서 수용됐고 Unit 9 보존 후보는 검증 뒤 채택하지 않았다. 다음 후보는 정확 계수만 분리해 재사용할 수 있는지에 대한 별도 설계다. auxiliary 총예산·cache 한도를 명시하며 실전 효율이나 UI 연결은 별도 결정한다.
현재 timing profiling은 STOP / DEFER이며 새 증거와 별도 bounded authorization 없이
재개하지 않는다. R0-B/Actual E2는 미실행·미승인이고 production/Gate P도 미수용이다.
향후 effectiveness 경로를 다시 열더라도 frozen R0 adjudication, operating-envelope,
별도 E2 승인 조건을 건너뛰지 않는다. Stage 4 기반의 한정 수용은 Program K 연구 재개나
Extended 전역 종료 선언이 아니다. 과거 static blocks는 원래 source/representation의 증거로 보존한다.

Nearest exact-minimum-risk guessing using movement cost는 별도 backlog 후보일 뿐 Program K
정책에 포함되지 않는다. Human Mouse Trace는 [수용된 계약](#human-mouse-trace)의 실제
samples로 유지하고 synthetic route/cursor나 공통 clock과 합치지 않는다. Model C refit,
임의 cap 완화, 새 solver 정책 또는 provenance schema 확장은 별도 승인 없이 허용되지 않는다.

- Live 파생 통계 계산기와 Replay controller의 추가 분리를 검토한다. ZiNi process/job owner 추출은 Viewer 공유 seam으로 완료됐다.
- UI 표시 formatter와 계산 모델의 경계를 정리하고, exact analysis의 비동기 실행·취소 방식을 검토한다.
- Replay의 시작 상태/segment metadata와 event 출처 표현을 검토하고 checkpoint 또는 lazy timeline으로 긴 기록의 이동 비용을 줄인다.
- 실제 subprocess 실패·취소·종료 테스트와 QTest 기반 입력 통합 검증을 늘린다.
- 다양한 보드·seed로 benchmark를 확대한다.
- 기존 engine 공개 API를 기반으로 AI/Gymnasium 환경을 별도 계층에 추가할 수 있다.
