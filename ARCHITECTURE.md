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
Live Auto는 UI의 QTimer 제어이며 `simple_runner.run_simple()`을 호출하지 않는다.
Solver가 `core_engine`에서 가져오는 것은 `Action`, `CellState` 같은 공개 타입이다.

## 3. 모듈별 책임

### Engine, 정적 보드와 UI

| 모듈 | 책임 |
| --- | --- |
| `main.py` | Windows Qt plugin 경로 설정, QApplication과 engine 생성, UI에 engine 주입 |
| `core_engine.py` | 지뢰 배치, OPEN/FLAG/CHORD, flood fill, 승패 판정, 타이머, active/wasted 클릭 및 진행량 집계 |
| `board_snapshot.py` | 크기·지뢰 수·배치 여부·mine layout·adjacent를 담은 불변 `BoardSnapshot` |
| `board_analyzer.py` | 확정 보드의 opening 그룹과 OPENING/BORDER/ISOLATED 분류, 정적 3BV/Ops |
| `ui_manager.py` | PyQt5 화면·입력 정책·렌더링, Live Analysis/Auto 제어, Replay 이동·시간·파일 대화상자, 통계 표시, ZiNi worker 관리 |

`BoardSnapshot`은 `frozenset`과 중첩 tuple로 값을 복사한다. 아직 지뢰가 배치되지 않았으면 `mines_placed=False`, 지뢰 집합은 비어 있고 adjacent는 현재 0 배열이다. 이 상태를 조회할 수는 있지만 BoardAnalyzer와 ZiNi 계산은 확정 보드를 요구한다.

Ops는 8방향으로 연결된 0 영역의 수이고, 3BV는 Ops에 고립 숫자 칸 수를 더한 값이다. Engine은 정적 분석 결과를 받아 opening 그룹의 최초 개방과 고립 숫자의 최초 개방을 동적 진행량으로 집계한다. Border 숫자는 별도 3BV 점수로 중복 계산하지 않는다.

### Simple Algorithm: 추론, 확률, decision

| 모듈 | 책임 |
| --- | --- |
| `simple_algorithm.py` | observation 검증, clue별 `Constraint`, 직접 추론과 deterministic move 선택 |
| `simple_probability.py` | 공개 조건에 맞는 complete-board world 수와 셀별 지뢰 확률 계산, 확률 기반 move 선택 |
| `simple_decision.py` | `analyze_position(observation, num_mines)`으로 두 계산 경로를 통합한 `SimpleDecision` 반환 |
| `simple_runner.py` | 현재 engine을 동기 실행하고 guess 전 중단 또는 종료, 실제 행동의 Replay 기록 |
| `live_analysis.py` | 계산된 decision을 `LiveAnalysis`/overlay/status로 변환, 확률 포맷과 Reduction |

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

### Replay

| 모듈 | 책임 |
| --- | --- |
| `replay_model.py` | Frozen `ReplayBoard`, `ReplayEvent`, `ReplayData`; 좌표·지뢰 수·action·시간·schema 검증 |
| `replay_recorder.py` | 메모리에 실제 이벤트를 누적하고 확정된 snapshot을 한 번 capture하도록 호출자가 관리 |
| `replay_json.py` | JSON 구조 변환, UTF-8 파일 입출력. 도메인 검증은 model에 위임 |
| `replay_player.py` | 저장된 fixed board를 독립 engine에 복원하고 action 순서대로 재생 |
| `replay_analysis.py` | 현재 공개 position의 추천을 구한 후 다음 event와 비교. 읽기 전용 |
| `replay_statistics.py` | 별도 player로 counter timeline을 만들고 위치·재생 시간·ZiNi에 따른 Counters 반환 |

Replay 재생, Replay Analysis, Replay Statistics는 서로 다른 책임이다. 재생은 기록을 engine에 적용하고, Analysis는 현재 position의 추천을 설명하며, Statistics는 과거 행동의 통계를 집계한다. Analysis는 플레이 평가 점수를 계산하지 않는다.

### ZiNi

| 모듈 | 책임 |
| --- | --- |
| `zini_calculator.py` | 공개 계산 API, 설정·결과 모델, 기존 호출 인터페이스와 내부 helper 재노출 |
| `zini_core.py` | 정적 3BV unit, 가상 개방/깃발 상태, Premium 평가, 클릭·flag/chord·fallback 공통 시뮬레이션 |
| `zini_min_ties.py` | 최대 Premium 동점 후보의 경로 탐색, 시간·상태 수 제한 |
| `zini_advanced.py` | Neighborhood beam, `standard_v1`·`chain_v1`·`standard_seeded_chain_v1` 정책 |
| `zini_metric_worker.py` | 별도 Python process에서 계산하고 임시 결과 파일을 atomic replace로 기록 |

ZiNi trace의 `ZiniMove`는 `ReplayEvent`와 다른 모델이다. 예를 들어 `flag_chord` 한 항목의 `clicks_added`에는 새 깃발들과 CHORD의 클릭 비용이 함께 들어간다.

## 4. 핵심 데이터 흐름

### 4.1 Live 입력과 분석·자동 진행

```text
사용자 입력 / Live Auto timeout
→ UI의 단일 action 경로
→ engine.step(x, y, action) 한 번
→ step 이후 경과 시간으로 Replay event 기록
→ 기존 분석 무효화 → 보드·통계 갱신
→ 분석 표시 ON이면 fresh observation으로 분석 → overlay
→ Auto ON이고 실행 가능한 추천이면 다음 timeout 예약
```

UI는 화음 입력 방식을 OPEN/CHORD 같은 action으로 변환한다. 실제 화음 성립 조건, 연쇄 개방과 승패는 engine이 처리한다. Live 기본 통계는 engine에서 받고, 일부 파생 Counters 조합은 UI에 남아 있다.

수동 `현재 상태 분석`은 행동을 실행하지 않는다. `분석 표시`가 OFF이면 그 결과는 다음 행동에 지워지고, ON이면 매 행동 후 갱신된다. Auto는 single-shot QTimer로 추천 하나만 예약하며, timeout에 observation 일치 여부와 HIDDEN target, 첫 수 정책의 유효성을 다시 검사한다.

추측 허용이 OFF이면 guess 추천과 overlay를 유지한 채 대기한다. 사용자가 직접 행동하면 예약을 취소하고 새 상태에서 분석한다. Reset·난이도 변경·Replay 진입·창 닫기·게임 종료·분석 오류도 예약을 취소한다. 행동을 여러 개 queue하지 않으며 비종료 Auto 행동 후 HIDDEN 수가 줄지 않으면 중단한다.

### 4.2 UI 없는 동기 runner

`run_simple(engine, *, accept_guesses=False)`는 pure analyzer와 달리 engine을 변경하는 실행 계층이다. [첫 수 정책](#first-click)을 적용한 뒤 **physical action 한 번 → fresh observation → 다시 분석**을 반복한다.

- 기본값은 local/global certainty를 실행하고 실제 guess 직전에 `GUESS_REQUIRED`로 반환한다.
- `accept_guesses=True`이면 guess도 실행한다. Solver 오류는 임의 fallback 없이 전파한다.
- WON/LOST에는 추가 분석·행동을 하지 않는다.
- PLAYING에서 move가 없거나, HIDDEN 대상의 OPEN/FLAG가 아니거나, 비종료 행동 후 HIDDEN 수가 감소하지 않으면 `SimpleRunnerError`다. 임의 step 제한 대신 진행 여부를 검사한다.

결과 `SimpleRunResult`는 frozen dataclass로, `status`, `stop_reason`(`WON`, `LOST`, `GUESS_REQUIRED`), 이번 호출의 `moves`, `replay_data`, 미실행 `pending_decision`, `started_from_hidden`을 담는다. Guess 대기 중 engine status는 PLAYING이다. 중간 합류 기록의 범위는 [schema v1 한계](#replay-schema-v1)를 따른다.

### 4.3 Replay 기록과 재생

```text
Live UI / simple_runner
→ engine.step()
→ ReplayRecorder.record_event(step 이후 elapsed_time, 좌표, action)
→ 확정 BoardSnapshot capture → ReplayData ↔ JSON

ReplayData → ReplayPlayer
           → reset_with_mines()로 독립 engine 생성
           → 저장 이벤트 적용 → observation → UI
```

Live UI와 runner 모두 확정 보드를 recorder에 한 번 전달하고 실제 action을 기록한다. 승리 시 engine의 자동 깃발은 별도 physical action/event가 아니다. Runner의 source는 `algorithm`이며 UI의 기존 recorder는 `human`을 사용한다. `source_type`은 게임 단위 필드이므로 Live Auto와 사람 입력을 event별로 구별하지 않는다.

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

```text
현재 Replay observation + num_mines + status + index
→ FIRST_CLICK presentation 또는 (analyze_position() → present_decision())
→ 추천 완성 후 다음 event 조회
→ compare_replay_action() → ReplayStepAnalysis → UI
```

`analyze_replay_step(observation, num_mines, *, current_index, events, status)`는 추천·presentation과 next event, 비교 kind/text를 묶는다. 비교 의미는 [비교 규칙](#replay-comparison)에 정의한다.

- 분석 ON: Replay 진입 및 index 변경 시 이전 분석 제거 → fresh board render → 현재 position 분석.
- 분석 OFF: 수동 1회 분석 가능. 다음 index 변경 시 결과 제거.
- Time autoplay: 한 tick에서 도래한 event들을 적용한 뒤 최종 index를 한 번 분석한다. Event가 없는 tick, 같은 index의 time seek, slider 동기화에서는 재분석하지 않는다.
- 마지막 index가 PLAYING이면 다음 event가 없어도 추천을 표시한다. WON/LOST에서는 solver를 호출하지 않고 overlay를 지우며 “게임 종료”를 표시한다. 저장된 terminal 이후 이벤트의 탐색은 유지한다.
- Replay에서는 Live Auto와 추측 허용이 OFF/disabled다. 분석 자체는 어느 engine에도 action을 실행하지 않는다.

공개 상태 모순과 validation/runtime 오류는 UI slot에서 처리해 overlay를 제거한다. 분석 오류가 Replay의 index·engine·counter timeline·data 또는 Live engine을 변경하지 않으며, 이동/자동 재생을 계속 허용하고 다음 위치에서 다시 분석한다.

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

종료된 Live 게임 또는 완료 Replay의 Counters를 표시할 때 확정 snapshot으로 worker를 시작한다.

```text
UI: snapshot + config + job token → 임시 payload
→ Python subprocess: ZiNi 계산 → token + clicks/error 결과 파일
→ UI polling: 현재 token과 일치하면 반영 → process·임시 파일 정리
```

현재 Counters 설정은 `standard_seeded_chain_v1`, 총 1000 evaluations, standard phase 500, seed 0이며 시간 제한은 없다. 계산 완료 전이나 실패 시 ZiNi는 `-`다. 보드 변경과 창 닫기는 기존 process를 정리한다. **오래된 token을 거르는 책임은 UI**에 있고 worker는 token을 결과에 돌려준다.

## 5. 중요한 설계 경계와 invariants

### 5.1 Engine / UI와 상태 소유권

- Engine은 PyQt5·화음 입력 모드·Replay slider를 모른다. `reset()`, `configure()`, `reset_with_mines()`, `step()`, observation/snapshot/counter API가 연동 경계다.
- `step()`의 반환은 `(observation, reward, terminated, truncated, info)`이며 `info`에는 기본 통계가 들어간다. Gymnasium 스타일이지만 Gymnasium environment 자체는 구현하지 않았다.
- 게임 중 범위 내 지원 action은 해당 category의 active 또는 wasted 한쪽에 한 번만 집계한다. Terminal 이후 입력과 범위 밖 입력은 클릭으로 세지 않는다.
- UI의 `self.engine`은 주입된 Live engine을 계속 유지한다. ReplayPlayer는 별도 engine을 소유하며 seek 때 교체할 수 있어 UI는 현재 모드의 engine을 매번 선택한다.
- Replay 종료는 같은 Live engine을 저장한 난이도로 reset한다. 이전 Live position의 재개 기능은 아니다.

<a id="public-information"></a>

### 5.2 Public observation과 hidden-information isolation

좌표는 `(x, y)`, 배열 접근은 `observation[y][x]`다. Solver 입력은 사람에게 보이는 **0..8, HIDDEN, FLAGGED**와 공개 총 지뢰 수뿐이다. Engine의 terminal 전용 상태 코드(EXPLODED/MINE/FALSE_FLAG)는 solver 입력이 아니므로 호출자가 종료를 먼저 처리한다.

`analyze_position()`은 engine, BoardSnapshot, ReplayData나 hidden mine layout을 받지 않는다. 입력을 변경하거나 행동을 실행하지 않고 같은 공개 입력에 같은 결정을 반환한다. Snapshot API가 public이라고 해서 그 안의 지뢰 정보가 solver의 public observation이 되는 것은 아니다.

Replay 추천 경로도 다음을 decision input으로 사용하지 않는다.

- `ReplayBoard.mine_positions`
- `BoardSnapshot.mines`와 `BoardSnapshot.adjacent`
- ReplayPlayer가 재구성한 engine의 hidden board layout

다음 Replay event는 [추천 계산 완료 후](#replay-analysis-flow) 비교 용도로만 읽는다. 재생 복원·기록·Replay Statistics·ZiNi가 실제 layout을 사용하는 경로와 분리한다. Live/runner의 첫 수 확인에서는 snapshot의 **`mines_placed` boolean만** 정책 입력으로 사용하며 layout은 읽지 않는다.

깃발은 지뢰로 가정한다. Analyzer는 local 추론 전에 개별 clue와 `0 <= num_mines - flag_count <= hidden_count`를 검증한다. Local 경로는 직접 모순과 안전/지뢰 충돌을 확인하지만 전체 constraint 만족 가능성을 검사하지 않는다. 전체 world의 존재 여부는 probability 경로에서 검사한다. 따라서 감지되지 않은 잘못된 깃발까지 교정하거나 certainty의 실제 안전을 무조건 보장하지 않는다.

<a id="first-click"></a>

### 5.3 FIRST_CLICK: Live와 Replay의 서로 다른 정책

Engine은 **미배치 상태의 첫 OPEN 한 칸만** 지뢰 후보에서 제외한다. 주변 8칸의 안전이나 첫 숫자 0은 보장하지 않는다. 먼저 FLAG하면 안전지대 없이 지뢰를 배치하며, 이를 해제해도 배치는 유지된다. `reset_with_mines()`도 지정된 배치를 그대로 사용한다.

아래는 PLAYING position에 적용하는 정책이다.

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

GLOBAL_CERTAINTY의 다른 0% OPEN/100% FLAG도 동등 후보다. FIRST_CLICK에는 SAFE evidence가 없으므로 다른 첫 OPEN은 DIFFERENT다. **DIFFERENT는 “추천과 다름”이며 오답·실수·나쁜 수의 판정이 아니다.** 다음 실제 행동은 status text로만 표시하고 별도 board overlay를 추가하지 않는다.

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

<a id="test-strategy"></a>

## 6. 테스트 전략

`unittest`로 규칙 회귀, 순수 계산, 모듈 간 계약과 Qt UI 연동을 나누어 검증한다. 아래는 현재 테스트의 주요 범위이며 모든 보드·플랫폼에 대한 완전성 증명은 아니다.

| 영역 | 테스트 파일 (`tests/` 아래) | 주요 검증 |
| --- | --- | --- |
| Engine regression | `test_engine_regression.py` | 첫 OPEN/FLAG와 FLAG→UNFLAG, 설정 검증·reset, flood/chord 결과, 승패·observation, 타이머, 클릭 분류 |
| BoardSnapshot / BoardAnalyzer | `test_engine_regression.py`, `test_board_analyzer.py` | snapshot 복사·불변성, 미배치 보드 거부, opening/border/isolated와 3BV/Ops |
| Replay model / JSON | `test_replay_model.py`, `test_replay_json.py` | 좌표·개수·시간 순서 검증, fixed-board 복원, JSON round-trip과 오류 |
| Replay recorder / player | `test_replay_recorder.py`, `test_replay_player.py` | capture 조건, 실제 event 누적, index 0·seek·next·previous |
| Replay Statistics | `test_replay_statistics.py` | 완료/미완료 마스킹, counter·파생 공식, 이벤트 사이 시간, UI engine ownership과 snapshot 선택 |
| Simple local inference | `test_simple_algorithm.py` | 두 직접 규칙, FLAG 우선·동률, 중복 제거, 모순·입력 검증, 비전파·subset 추론 범위 |
| Exact probability | `test_simple_probability.py` | component 분할·전역 결합, floating 조합 가중, 정확한 world 수·Fraction·certainty·move 선택 |
| Probability oracle | `test_simple_probability_oracle.py` | Production helper와 독립적인 작은 complete-board 전수 열거와 비교. 작은 grid의 exhaustive 상태 및 seeded public observation |
| Decision analyzer | `test_simple_decision.py` | local 우선과 probability 생략, 세 decision 종류, mine budget, 불변 입력·공개 API 경계 |
| Runner | `test_simple_runner.py` | 첫 수/guess 정책, 한 행동 후 재분석, 진행 검사·오류, 실제 event 순서, partial/continuation 재생과 정보 격리 |
| Live Analysis | `test_live_analysis.py` | 순수 presentation, 정확한 후보·확률 포맷, 실제 Qt 표시·갱신·Reduction·오류·첫 수 정책 |
| Live Auto | `test_live_auto.py` | timeout당 한 행동, fresh 분석·기록, guess 대기/허용, stale 추천·무진행·취소, 실제 QTimer 첫 수 종료 |
| Replay Analysis pure | `test_replay_analysis.py` | index 의미, 추천 후 event 조회, 숨은 배치 격리, 첫 수·동등 후보·비교 범위, terminal·불변성 |
| Replay Analysis UI | `test_replay_analysis_ui.py` | 실제 Qt controls, 이동/자동 재생별 갱신, 같은 index 재계산 방지, 표시 전환, 오류 복구·engine ownership·Auto 차단 |
| ZiNi deterministic / min-ties | `test_zini_core.py`, `test_zini_calculator.py` | Premium·unit·동작 의미, 고정 trace, 클릭 합계·안전 칸·깃발 유효성, bounded min-ties 종료 |
| ZiNi advanced | `test_zini_advanced.py` | 정책별 rollout, budget·종료 metadata, baseline 유지, 고정 seed/evaluation 재현성, trace 재적용 |

정보 격리 테스트는 solver를 공개 enum만 있는 engine 대체 모듈로 로드하거나, hidden snapshot/layout 접근을 실패시키는 방식도 사용한다. Probability oracle은 answer board로 정답을 주입하지 않고 공개 조건을 직접 열거한다.

Qt 관련 테스트는 offscreen으로 실행하며 일부는 PyQt5 미설치 시 skip된다. Replay Statistics의 UI 책임 검증에는 probe/stub도 사용한다. 실제 QTimer 테스트가 있지만 모든 OS 입력·화면·이벤트 순서를 검증하는 것은 아니다. ZiNi worker 실행은 UI 테스트에서 대체하므로 실제 subprocess 실패·취소·종료를 포괄하는 테스트와 구분해야 한다.

실행 명령은 [README 테스트](README.md#테스트)를 참고한다. [Benchmark](README.md#benchmark)는 고정 보드의 전략 비교와 trace 검증 도구이며 단위 테스트나 최적성 증명을 대체하지 않는다.

## 7. 현재 한계와 기술 부채

- **Exact probability 비용:** sampling·cutoff·approximate fallback 없이 component를 열거하므로 큰 연결 component에서 지수 시간이 걸린다. Live/Replay 분석은 현재 UI thread에서 동기 실행하며 background analysis worker나 전체 Replay 추천 사전 계산은 없다.
- **Solver 범위:** 닫힌 칸의 OPEN/FLAG만 선택한다. CHORD/UNFLAG, 장기 승률 최적화, 일반적인 오답 깃발 교정은 제공하지 않는다. 검증 범위는 [정보 경계](#public-information)를 따른다.
- **Replay 저장 표현력:** 중간 합류 및 첫 position 해석의 제약은 [schema v1 한계](#replay-schema-v1)에 정리했다. Event별 human/auto 출처도 구분하지 않는다.
- **Replay 비용:** 진입 시 통계 timeline을 전체 순회로 생성한다. Seek/previous는 처음부터 재구성하며 checkpoint가 없다.
- **UI 책임 집중:** 파생 Live Counters 계산, Replay 시간·slider·button 제어, Live Auto, ZiNi process 생명주기가 한 UI 클래스에 남아 있다.
- **ZiNi 실행과 검증:** Counters는 evaluation 수만 제한하므로 실행 시간 상한은 없다. 실제 worker의 실패·취소와 운영체제별 GUI 동작은 자동 검증 범위를 더 넓혀야 한다. 결과의 해석 범위는 [ZiNi 결과](#zini-results)를 따른다.
- **내부 결합:** `zini_calculator.py`가 내부 helper도 재노출하고 전략 모듈이 일부 결과 타입을 지연 import한다. 공개 API와 내부 구현의 경계는 더 정리할 수 있다.

## 8. 향후 확장 방향

현재 기능에 포함되지 않은 개선 후보다.

- Live 파생 통계 계산기, Replay controller와 ZiNi worker 관리 서비스를 분리한다.
- UI 표시 formatter와 계산 모델의 경계를 정리하고, exact analysis의 비동기 실행·취소 방식을 검토한다.
- Replay의 시작 상태/segment metadata와 event 출처 표현을 검토하고 checkpoint 또는 lazy timeline으로 긴 기록의 이동 비용을 줄인다.
- 실제 subprocess 실패·취소·종료 테스트와 QTest 기반 입력 통합 검증을 늘린다.
- 다양한 보드·seed로 benchmark를 확대한다.
- 기존 engine 공개 API를 기반으로 AI/Gymnasium 환경을 별도 계층에 추가할 수 있다.
