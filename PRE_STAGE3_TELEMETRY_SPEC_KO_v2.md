# PRE_STAGE3_TELEMETRY_SPEC — 한국어 번역본

> **버전:** 공식 개정 2 — 동결된 구현 명세  
> **상태:** FROZEN FOR PRE-STAGE 3 IMPLEMENTATION  
> **구현 상태:** 이 명세를 기준으로 구현 진행 가능  
> **용도:** Stage 3 시작 전에 Stage 2 solver를 공정하게 측정하기 위해 필요한 최소 telemetry, 재현 가능한 benchmark, persistence, statistics 기반을 정의한다.  
> **주의:** 이 문서는 이해와 검토를 위한 한국어 번역본이다. 교차검증과 최종 구현 기준은 영어 원본 `PRE_STAGE3_TELEMETRY_SPEC_v2.md`를 우선한다. 두 문서가 충돌하면 영어 원본을 authoritative source로 취급한다.

---

## 0. 검토 규칙과 근거 우선순위

이 개정본은 이전 draft에 대한 두 번의 독립 전면 감사, 그 finding에 대한 adjudication, 그리고 최종 Revision 2에 대한 Codex/Claude Code 독립 delta review를 거쳐 동결되었다.

근거 우선순위는 계속 다음과 같다.

1. 현재 `main` source code
2. 현재 tests
3. 필요할 때의 executable verification
4. `ARCHITECTURE.md`
5. 이 문서
6. reviewer 해석

Revision 2는 이제 **FROZEN FOR PRE-STAGE 3 IMPLEMENTATION** 상태다. 두 delta review 모두 implementation blocker가 없다고 판정했다. Freeze 전에 다음 네 가지 non-blocking 문서/contract 보완을 반영했다.

- prefix digest의 정확한 bytes와 SHA-256 algorithm;
- 완전한 `git_dirty` / official-baseline eligibility 규칙;
- canonical rational TEXT의 SQL 사용 제한;
- literal unlimited decimal-string 보장이 아니라 benchmark domain을 기준으로 한 exact probability round-trip 요구사항.

이 문서와 현재 source/tests가 충돌하면 먼저 다음 둘 중 무엇인지 판정한다.

- 이 문서가 명시한 **의도적인 proposed change**인지;
- 아니면 **specification defect**인지.

다른 valid style도 가능하다는 이유만으로 frozen design choice를 다시 열지 않는다. Correctness, consistency, testability, scope defect가 구체적으로 입증될 때만 재검토한다.

## 0.1 프로젝트 맥락

이 프로젝트는 단계별로 진행하는 지뢰찾기 졸업프로젝트다.

현재 프로젝트 진행 단계는 다음과 같다.

```text
Stage 1 — UI/UX + Replay
    플레이 가능한 PyQt5 지뢰찾기 애플리케이션
    Replay 기록 / 저장 / 불러오기 / 재생 / 시킹 / 속도 조절
    기존 게임 통계 및 관련 UI 기반

Stage 2 — Simple Algorithm
    local deterministic inference
    exact complete-board probability analysis
    observation-only decision pipeline
    현재 runner를 통한 synchronous execution
    확정 수가 없을 때 minimum-risk guessing

Pre-Stage 3 — 현재 작업
    재현 가능한 telemetry
    fixed benchmark board
    SQLite benchmark 저장
    statistics / graph 기반
    신뢰 가능한 Stage 2 baseline

Stage 3 — 다음 구현 목표
    Speed-focused Algorithm
```

Stage 3의 주목적은 단순히 Python 실행 속도를 빠르게 만드는 것이 아니다.

Stage 2의 위험도 원칙을 유지하면서, 실제 지뢰찾기를 modeled physical play time 기준으로 더 빠르게 진행하도록 action과 action 순서를 선택하는 것이 목표다.

Stage 3는 **이상적이지만 인간이 실제로 수행 가능한(idealized but human-feasible) 지뢰찾기 플레이어**를 모델링해야 한다. 물리적 실행은 순간적인 cursor 이동, 이동 비용 0, 무제한 action rate를 가정하지 않고, 가능한 범위에서 실제 인간의 마우스 이동과 입력 timing에 최대한 가깝게 구성한다. 다만 인간의 실수, 망설임, 무작위 jitter, 피로를 재현하는 것이 목적은 아니다. 현실적인 인간의 물리적 제약을 유지하면서 플레이 속도를 최적화하는 것이 목적이다.

이후 Stage 3에서는 다음 요소를 고려하는 방향을 예상한다.

- cursor movement distance와 path
- cell size / target width
- movement-time model
- OPEN / FLAG / CHORD의 물리적 입력 비용
- 현실적인 inter-action timing과 CPS 한계/버스트
- action ordering과 짧은 horizon routing
- replay 기반 timing 및 movement calibration

Human replay data와 controlled pointing experiment는 이후 이 물리 모델을 **보정(calibration)하고 검증(validation)**하는 자료로 사용할 수 있다. 이는 현실적인 timing/movement 제약을 추정하기 위한 근거이며, 알고리즘이 인간 replay를 frame 단위로 그대로 모방해야 한다는 뜻은 아니다.

따라서 현재의 Pre-Stage 3 작업은 **Stage 3 변경을 넣기 전에** 신뢰할 수 있는 Stage 2 측정 baseline을 확립하기 위해 존재한다.

리뷰어는 반드시 이 프로젝트 맥락 안에서 SPEC을 판단해야 한다. Stage 2 자체를 다시 설계하거나, Stage 3를 미리 구현하거나, 공정한 Stage 2 → Stage 3 비교에 필요하지 않은 범용 연구 framework로 시스템을 확장해서는 안 된다.

---

## 0.2 소프트웨어공학 원칙

모든 검토 finding과 이후 구현 판단은 다음 프로젝트 전체 소프트웨어공학 원칙을 준수해야 한다.

### 핵심 원칙

- **Single Responsibility Principle (SRP):** 각 module/class는 명확한 하나의 변경 이유를 가져야 한다.
- **Separation of Concerns (SoC):** 게임 규칙, solver 추론, 실행, telemetry, persistence, statistics, UI는 책임이 다르면 분리한다.
- **확장성:** Stage 3/4가 측정 인프라를 재사용할 수 있어야 하지만, 이를 이유로 지금 speculative abstraction을 만들지는 않는다.
- **유지보수성:** 영리하지만 결합도가 높은 설계보다 명시적이고 이해하기 쉬운 contract를 우선한다.
- **테스트 가능성:** 중요한 의미와 invariant는 독립적으로 테스트할 수 있어야 한다.
- **Backward compatibility:** 명시적인 이유와 테스트가 없는 한 기존 Stage 1/2 동작과 public contract를 깨뜨리지 않는다.
- **최소 필요 abstraction:** 미래 가능성만으로 generic framework, interface, registry, service, plugin system을 도입하지 않는다.
- **측정 후 최적화:** pilot 측정에서 실제 비용이나 병목이 확인된 뒤 최적화한다.

### 불필요하거나 중복되어 보이는 요소에 대한 규칙

어떤 field, model, abstraction, module이 불필요하거나 중복되어 보이더라도 리뷰어는 **바로 삭제를 권고해서는 안 된다.**

반드시 다음을 설명해야 한다.

1. 왜 불필요하거나 중복되어 보이는지;
2. 제거하면 어떤 정보, 편의성, 검증 능력, 미래 호환성, 명확성을 잃는지;
3. 가장 적절한 선택이 다음 중 무엇인지:
   - **KEEP NOW**
   - **DEFER / REVISIT AFTER PILOT**
   - **REMOVE**

특히 의도적인 denormalization과 중복 summary field에 이 원칙을 적용한다.

목표는 abstraction 수를 최대화하거나 파일 수를 최소화하는 것이 아니다. 현재 연구와 구현 필요에 의해 정당화되는 가장 작은 구조로 명확한 책임을 유지하는 것이 목표다.

---

## 0.3 Revision 2 감사 판정 반영

다음 결정은 이 개정본에서 해결되었으며 더 이상 open design question이 아니다.

```text
exact SQLite probability
    → canonical reduced rational TEXT, 항상 "n/d"

board fingerprint
    → frozen canonical binary encoding + SHA-256 lowercase hex

Generator V1
    → local random.Random(seed).sample(...)
    → CPython 3.12.14 reference runtime
    → golden fingerprints + prefix digest + pair-time fingerprint validation

fixed-board runner integration
    → keyword-only initial_open + optional observer
    → Stage 2 실행 loop는 하나만 authoritative하게 유지

SQLite operating mode
    → 처음에는 WAL + synchronous=FULL
    → pilot 근거가 있을 때만 NORMAL 재검토

v1 committed game outcome
    → result가 authoritative하며 NOT NULL
    → per-game termination_reason/error_code는 defer
```

그 밖에 이번 개정본에 반영한 adjudicated change는 다음과 같다.

- benchmark run에는 `benchmark_set_id`가 필수다.
- official baseline은 Git이 무시하지 않는 working tree 전체가 clean이어야 하며 `git_dirty`를 기록한다.
- `safe_cells_opened_delta`는 `FLAGGED → safe-number` 공개도 포함한다.
- `explicit_flag_delta`는 Engine의 자동 flag/unflag 효과를 제외한다.
- Stage 2 adapter는 selector semantic drift self-check를 수행한다.
- paired comparison은 coverage를 명시적으로 검증하며 missing/mismatched pair를 조용히 제외하지 않는다.
- DB 자체 failure 때문에 `FAILED` status 기록도 실패할 수 있으므로 failure finalization은 best-effort다.
- v1 `action_events`는 `WITHOUT ROWID`를 사용한다.
- custom PRNG, resume, chunking, no-replay mode, parallelism, Stage 3 physical telemetry는 evidence가 필요해질 때까지 defer한다.

---

# 1. 목표

Pre-Stage 3의 목적은 속도 중심 Stage 3 작업을 시작하기 전에 신뢰할 수 있는 Stage 2 기준선을 만드는 것이다.

필요한 최소 파이프라인은 다음과 같다.

```text
고정 benchmark set
→ 재현 가능한 board
→ Stage 2 game 실행
→ action 단위 telemetry
→ game 단위 summary
→ SQLite 저장
→ 통계 집계
→ 기본 그래프
→ Stage 2 baseline
```

이 인프라는 Stage 2, Stage 3, 이후 단계들을 **동일한 board**에서 공정하게 paired comparison 할 수 있어야 한다.

이 인프라는 범용 연구 플랫폼이 아니다.

---

# 2. 범위 경계

## 2.1 지금 반드시 필요한 것

첫 구현 범위는 다음으로 제한한다.

- deterministic benchmark-board 생성
- 고정 benchmark-set 의미 정의
- Stage 2 한 게임 실행 instrumentation
- action 단위 telemetry
- game 단위 summary telemetry
- run 단위 metadata
- SQLite 저장
- transaction 무결성
- 기본 aggregate statistics
- 소규모 pilot
- backend 검증 후 기본 통계/그래프 UI
- 최종적으로 10k / 100k Stage 2 baseline 실행

## 2.2 명시적으로 연기하는 것

이 문서에서 미래 호환성을 언급했다고 해서 다음을 지금 구현해서는 안 된다.

- 병렬 benchmark worker
- multi-process SQLite writer
- database sharding
- database archive/compaction
- 중단된 run의 resume
- 복잡한 migration framework
- plugin/event-bus architecture
- 범용 dependency-injection framework
- 모든 미래 Stage를 위한 generic planner telemetry
- action마다 board snapshot 저장
- standard telemetry에 전체 candidate list 저장
- Stage 3 cursor/timing field
- Stage 3 physical-action planner
- held-button planning
- risk-band/aggressive-speed policy
- 정확한 mouse-down/up timing capture
- probability enumeration 내부 benchmark cancellation
- 오래된 `RUNNING` run 자동 복구
- 실제 필요성이 확인되기 전 custom stable PRNG 구현

구체적인 필요가 생겼을 때 이후 단계에서 설계한다.

---

# 3. 반드시 유지해야 할 기존 architecture

현재 프로젝트는 다음과 같이 책임을 분리한다.

```text
core_engine.py
    rules / state transition / timer / click accounting

simple_algorithm.py
    local deterministic inference

simple_probability.py
    exact complete-board probability

simple_decision.py
    pure position analysis

simple_runner.py
    synchronous execution

Replay modules
    recording / playback / analysis / statistics

board_snapshot.py
board_analyzer.py
    immutable static board representation / 3BV / Ops
```

Pre-Stage 3는 이 문서에서 작은 확장을 명시한 경우를 제외하면 이 경계를 유지해야 한다.

다음은 강한 architecture 제약이다.

- Solver decision logic은 hidden mine layout을 읽지 않는다.
- `analyze_position()`은 observation-only 상태를 유지한다.
- `MinesweeperEngine`에 telemetry persistence를 넣지 않는다.
- solver logic에서 SQLite에 접근하지 않는다.
- UI에 SQL/statistics 의미론을 직접 넣지 않는다.
- Replay event와 telemetry event는 별도 모델로 유지한다.
- Benchmark code가 Stage 2 inference rule을 복제해서는 안 된다.

---

# 4. 현재 첫 클릭 의미론

현재 Engine 정책은 다음과 같다.

```text
fresh game
→ mines_placed == False

first valid OPEN(x, y)
→ (x, y) 한 칸만 제외하고 지뢰 배치
→ 주변 8칸은 여전히 지뢰 후보
→ adjacency / static analysis 계산
→ (x, y) 공개
```

따라서:

- 첫 OPEN 칸은 반드시 안전하다.
- 첫 OPEN이 `0`을 보장하지 않는다.
- 주변 8칸의 안전을 보장하지 않는다.

첫 action이 `FLAG`라면 안전 OPEN 칸 없이 지뢰가 배치된다. 이후 그 flag를 해제해도 board는 다시 생성되지 않는다.

`reset_with_mines()`는 다르다. 이미 확정된 layout을 설치하고 `mines_placed=True`로 만든다.

---

# 5. Benchmark 첫 클릭 정책

주 benchmark 정책은 다음이다.

```text
FIRST_CLICK_FIXED_0_0
```

Benchmark generator는 `(0, 0)`이 지뢰가 아닌 board를 생성해야 한다.

제외 규칙은 fresh Engine 정책을 재현해야 한다.

```text
(0, 0) 한 칸만 제외
주변 8칸은 제외하지 않음
```

주 benchmark game은 다음 action을 실행한다.

```text
ActionEvent #0 = OPEN(0, 0)
```

이 action은 solver inference로 취급하지 않는다.

action 0의 값은 다음과 같다.

```text
inference_category = NULL
selection_candidate_count = NULL
target_mine_probability = NULL
minimum_available_mine_probability = NULL
decision_compute_ns = NULL
```

OPEN 결과 자체는 flood reveal과 terminal state를 포함해 정상적으로 기록한다.

---

# 6. Fixed benchmark board를 위한 `simple_runner` 확장

## 6.1 현재 충돌

현재 `run_simple()`은 이미 배치된 all-hidden board에 대해 의도적으로 다른 동작을 한다.

```text
all hidden + mines_placed=False
→ special first OPEN policy

all hidden + mines_placed=True
→ normal analyze_position()
```

`reset_with_mines()`로 불러온 benchmark board는 이미 `mines_placed=True`다.

따라서 단순히:

```text
reset_with_mines(...)
run_simple(...)
```

를 실행하면 fresh-game first-OPEN policy를 재현하지 못한다. 이것은 실제 integration 문제다.

## 6.2 동결할 API 방향

`run_simple()`에 keyword-only option을 additive하게 추가한다.

```python
run_simple(
    engine,
    *,
    accept_guesses=False,
    initial_open=None,
    observer=None,
)
```

`initial_open=None`, `observer=None`인 기본 경로는 현재 runner와 backward-compatible해야 한다.

주 benchmark에서는:

```python
run_simple(
    engine,
    accept_guesses=True,
    initial_open=(0, 0),
    observer=...,
)
```

를 사용한다.

`initial_open`은 solver decision이 아니라 execution policy다.

`initial_open`이 지정된 경우 runner는 **Engine을 변경하기 전에** 다음을 검증해야 한다.

- 좌표는 두 정수 `(x, y)` 쌍이어야 하며 bool은 정수로 허용하지 않는다.
- Engine은 `PLAYING`이어야 한다.
- 시작 observation은 전부 `HIDDEN`이어야 한다.
- 좌표는 board 범위 안이어야 한다.
- target은 `HIDDEN`이어야 한다.

이후 runner는 그 OPEN에 대해 `analyze_position()`을 호출하지 않고 직접 실행한다.

Runner는 explicit initial cell이 실제로 안전한지 판단하기 위해 hidden mine position을 읽어서는 안 된다. Benchmark generator/evaluator가 benchmark first click의 안전성을 보장한다.

`initial_open`이 지정되면 해당 invocation에서는 기존 fresh-game implicit `(0,0)` first-open policy보다 우선한다.

## 6.3 Observer 계약

`observer`는 의도적으로 작은 optional callback이며 **generic EventBus가 아니다.**

개념적으로:

```text
observer(SimpleActionTrace)
```

Observer는 immutable execution facts만 받는다. Engine이나 hidden board layout을 전달해서는 안 된다.

성공적으로 실행된 각 action의 순서는 다음과 같다.

```text
move selected / explicit initial OPEN chosen
→ engine.step()
→ Replay event recorded
→ 필요하면 replay board captured
→ fresh public observation obtained
→ action-effect deltas derived
→ runner progress/invariant checks pass
→ observer(trace) exactly once
```

규칙:

- terminal action도 정확히 한 번 trace를 만든다.
- 실행되지 않은 pending guess는 trace를 만들지 않는다.
- terminal Engine에는 새 action도 trace도 없다.
- observer exception은 전파하고 숨기지 않는다.
- observer code는 외부 reference를 통해 game state를 변경해서는 안 된다.
- `observer=None`이면 normal runner path에 telemetry 동작을 추가하지 않는다.

Trace는 작은 runner-to-observer DTO다. Database model이 아니며 `SimpleRunResult`를 telemetry container로 만들지 않는다.

## 6.4 v1에서 채택하지 않는 대안

`benchmark_runner.py` 안에 두 번째 완전한 Stage 2 game loop를 만들지 않는다.

Benchmark만을 위해 `MinesweeperEngine`에 fixed-layout/deferred-placement mode를 추가하지 않는다.

Optional observer를 generic event system으로 일반화하지 않는다.

모든 trace를 `SimpleRunResult`에 담아 반환하는 방식도 기술적으로는 타당하지만, Revision 2는 runner result semantics를 유지하고 telemetry consumption을 `SimpleRunResult` 밖에 두기 위해 작은 opt-in observer boundary를 유지한다.

---

# 7. Benchmark board 생성

작은 benchmark-board module을 만든다.

```text
benchmark_board.py
```

책임은 benchmark board generation과 board identity다. Solver logic이나 persistence logic을 포함하지 않는다.

## 7.1 Benchmark set

주 corpus:

```text
EXPERT_GENERAL_V1
```

의미:

```text
width = 30
height = 16
num_mines = 99
first_click = (0, 0)
unfiltered general boards
generator version = V1
```

`GENERAL`은 solver result, guess occurrence, 3BV, opening size, probability pattern, 특정 board 난이도, Stage 2 win/loss로 filtering하지 않는다는 뜻이다.

Filtered/adversarial corpus는 다른 benchmark-set ID를 사용해야 한다.

## 7.2 Stream과 run 범위 의미

`EXPERT_GENERAL_V1`은 deterministic prefix stream이다.

V1에서는:

```text
game_index == seed
```

예:

```text
100-game pilot      → game_index 0..99
1,000-game pilot    → 0..999
10,000-game run     → 0..9,999
100,000-game run    → 0..99,999
```

따라서:

```text
100 ⊂ 1,000 ⊂ 10,000 ⊂ 100,000
```

v1 `BenchmarkRun`은 항상 정확한 prefix를 의미한다.

```text
game_index ∈ [0, requested_games)
```

`COMPLETED` run은 missing/extra index 없이 정확히 그 index 집합을 가져야 한다.

이 set에서는 `game_index`와 `seed`가 같지만 둘 다 유지한다. 의미가 각각 corpus position과 generator input으로 다르기 때문이다.

Chunked/non-prefix run과 `first_game_index` field는 defer한다. 10k pilot 이후 100k 운영 위험이 실제로 이를 정당화하는지 판단한다.

## 7.3 Generator V1

Reference algorithm:

```python
rng = random.Random(seed)

candidates = [
    (x, y)
    for y in range(height)
    for x in range(width)
    if (x, y) != first_click
]

mines = rng.sample(candidates, num_mines)
```

요구사항:

- local `random.Random(seed)`만 사용한다.
- global `random.seed(seed)`를 호출하지 않는다.
- candidate order는 fixed row-major다.
- first-click cell만 제외한다.
- 주변 8칸은 제외하지 않는다.
- 생성 후 board를 filtering하지 않는다.

### Reference-runtime 계약

Generator V1의 reference runtime은:

```text
CPython 3.12.14
```

이다.

Benchmark는 실제 Python implementation/version을 `environment_snapshot`에 기록해야 한다.

Seeded PRNG의 결정성은 benchmark 재현성을 위해 의도적으로 사용한다. 다만 이 SPEC은 `random.sample()` output이 모든 미래 Python implementation/version에서 항상 동일하다고 가정하지 않는다.

따라서 V1 compatibility는 golden tests(§9)와 실제 paired comparison 시 fingerprint 검증(§10)으로 보호한다.

새 runtime에서 V1 golden이 깨지면:

- 기존 golden을 조용히 새 값으로 바꾸지 않는다.
- V1 재현에는 reference runtime을 사용하거나,
- V2 같은 새 generator/set version을 정의한다.

장기적으로 runtime-independent regeneration이 concrete requirement가 되기 전까지 custom project-owned PRNG/sampling algorithm은 defer한다.

---

# 8. Benchmark board identity

잠정 pure model:

```text
BenchmarkSetSpec
- benchmark_set_id
- width
- height
- num_mines
- first_click_x
- first_click_y
- board_generator_version
- seed_scheme

BenchmarkBoard
- game_index
- seed
- mine_positions
- board_fingerprint
```

v1에서는 별도 `board_id`를 추가하지 않는다.

## 8.1 동결할 canonical fingerprint encoding

Fingerprint는 generation metadata가 아니라 **실제 mine layout**을 식별한다.

Canonical payload:

```python
payload = (
    b"MSLAYOUT1\0"
    + struct.pack(">III", width, height, num_mines)
    + b"".join(
        struct.pack(">II", x, y)
        for x, y in sorted(mine_positions, key=lambda c: (c[1], c[0]))
    )
)

board_fingerprint = hashlib.sha256(payload).hexdigest()
```

계약:

- 정수 encoding은 unsigned 32-bit big-endian이다.
- 좌표 값 자체는 `(x, y)`로 저장하지만 순서는 `(y, x)` reading order다.
- payload에는 정확히 `num_mines`개의 서로 다른 in-bounds 좌표가 있어야 한다.
- domain tag는 정확히 10 bytes인 `b"MSLAYOUT1\0"`다.
- persisted fingerprint는 정확히 64자의 lowercase hexadecimal text다.

Fingerprint payload에 seed, benchmark-set ID, generator version, first-click policy, solver stage, solver policy를 넣지 않는다.

결과:

- generation 방식이 달라도 layout이 같으면 fingerprint는 같다.
- fingerprint는 UNIQUE가 아니다.
- duplicate layout도 `game_index`가 다른 별도 corpus entry로 유지한다.

Encoding 변경은 새 fingerprint/generator compatibility contract가 필요하며 기존 golden을 조용히 다시 쓰면 안 된다.

## 8.2 Hidden-information 규칙

`mine_positions`와 `board_fingerprint`는 evaluation/environment 정보다.

`analyze_position()`, Stage 2 move selection, future Stage 3 move selection에 전달해서는 안 된다.

Solver는 public observation과 public mine count만 받는다.

---

# 9. Golden reproducibility test

Generator V1은 여러 규모에서 재현성을 검증해야 한다.

## 9.1 대표 seed fingerprint

Frozen Generator V1과 fingerprint contract를 사용하는 `EXPERT_GENERAL_V1`의 authoritative lowercase SHA-256 fingerprint는 다음과 같다.

```text
seed 0      fbd8b8069ef4f449bbc844329579b6538d2b175c1cf99eb22c49c0585322e053
seed 1      007b8d203106dd32d1b5b6c46052bbeeeb9fde2be89c81023b01519fba1bee9e
seed 2      58b8e6399a435371a430a75bd0a51035614242662b53015c61eb61292ccdd28a
seed 42     9a86f62d6fcc7bd8a19f53308a84d0710c8238b5fbf72ea5041fa38e4603f2ac
seed 999    45f1236c061ece7041aba1312f16137ee68f2c43da2d7c0b9f2065c37877cace
seed 99999  9a5903f41835faa195d0c1e457ee5721cd93f514c503043b6b08492b4425a0af
```

이 값들은 사람이 읽을 수 있는 seed → board identity fixture다. Revision 2 delta review에서 reference runtime CPython 3.12.14로 독립 재현되었다.

## 9.2 Prefix digest

정확한 prefix:

```text
game_index 0..999
```

의 fingerprint를 index 오름차순으로 생성한다.

Digest algorithm은 다음으로 동결한다.

```python
hashlib.sha256(
    b"
".join(fp.encode("ascii") for fp in fingerprints)
).hexdigest()
```

Contract:

- `fingerprints`는 `game_index 0..999`를 오름차순으로 담은 정확히 1,000개 entry다.
- 각 entry는 §8에서 정의한 64-character lowercase hexadecimal board fingerprint다.
- separator는 정확히 하나의 LF byte `0x0A`다.
- trailing separator/newline은 없다.
- outer digest algorithm은 SHA-256이다.

Authoritative first-1,000 prefix digest:

```text
93852d335a46af9420dbdcdf0e256bb9149778f33602f6a4facdf0295677777c
```

이 digest는 whole-prefix compatibility를 빠르게 확인하는 compact check다.

## 9.3 Engine-equivalence 검증

대표 test는 Generator V1의 first-click exclusion과 mine sampling이 동일한 deterministic sample 결과를 사용하는 현재 Engine fresh-game placement policy와 동등함을 검증해야 한다.

## 9.4 Golden 정책

지원 환경에서 V1 golden output이 달라지면 compatibility break로 취급한다. Test를 통과시키기 위해 goldens를 단순 업데이트하지 않는다.

실제 Stage comparison은 여전히 비교 대상 모든 game의 fingerprint를 확인해야 한다. Golden은 조기 경고이고, pair-time identity validation이 최종 방어선이다.

---

# 10. Paired comparison 규칙

Paired comparison은 **identity**와 **coverage**를 모두 명시적으로 검증해야 한다.

## 10.1 Official comparison eligibility

Official baseline comparison은 completed run끼리 수행한다. Partial/aborted/failed run은 진단용 통계를 볼 수 있지만 full paired baseline처럼 조용히 취급하면 안 된다.

비교 전에 다음 run-level fact가 compatible한지 검증한다.

```text
benchmark_set_id
width
height
num_mines
first_click_policy
board_generator_version
telemetry semantic version compatibility
```

`solver_stage`, `solver_policy`, solver configuration은 비교 대상일 수 있으므로 같을 필요가 없다.

Compute-time comparison에는 execution environment compatibility도 필요하다. §34와 §38을 따른다.

## 10.2 명시적 comparison range

Caller/statistics layer는 명시적인 prefix를 선택해야 한다.

```text
[0, N)
```

두 run 모두 해당 범위의 모든 index를 가져야 한다.

Missing game을 조용히 버리는 SQL inner join을 사용하면 안 된다.

## 10.3 Per-game identity

각 비교 `game_index`에서 다음 값의 equality를 요구한다.

```text
benchmark_set_id
game_index
seed
board_fingerprint
first_click_x
first_click_y
```

Missing row나 mismatch가 하나라도 있으면 요청한 pair/range를 invalid로 보고해야 한다.

Duplicate fingerprint는 허용하며 `game_index`가 다른 별도 corpus entry로 유지한다.

Pilot은 nested prefix다. 100-game pilot과 1,000-game prefix를 더해서 1,100개의 독립 board라고 표현하면 안 된다.

---

# 11. Telemetry 원칙

핵심 원칙:

> Raw event를 먼저 저장하고 summary는 그 위에 둔다.

Standard telemetry는 frame-based가 아니라 event-based다.

Standard telemetry에서는 매 action마다 board snapshot을 저장하지 않는다.

수십만 판 규모를 감당할 수 있을 정도로 작아야 한다.

선택된 seed에 대해서만 향후 debug/full telemetry를 추가할 수 있다.

---

# 12. Generic telemetry model

잠정 module:

```text
telemetry_model.py
```

가능하면 model은 immutable하게 만든다.

DB가 생성하는 ID는 pure telemetry model에 포함하지 않는다.

즉:

- Python `BenchmarkRun`에는 `run_id`가 필수 아님
- Python `GameRecord`에는 `game_id`, `run_id`가 필수 아님
- Python `ActionEvent`에는 `game_id`가 필수 아님

Repository가 저장 시 relational ID를 붙인다.

---

# 13. Generic inference category

Generic telemetry가 Stage 2의 `DecisionKind`에 의존하지 않도록 한다.

개념적으로 telemetry-level enum을 정의한다.

```text
InferenceCategory
- LOCAL_DETERMINISTIC
- GLOBAL_CERTAINTY
- PROBABILITY_GUESS
```

Stage 2 adapter는:

```text
DecisionKind → InferenceCategory
```

로 매핑한다.

이 중복은 의도적이다.

이유:

- Stage 2 decision type은 solver implementation detail이다.
- telemetry는 Stage 3/4에도 유지되어야 한다.

매핑 누락이 없음을 테스트한다.

---

# 14. Stage 2 decision telemetry adapter

잠정 module:

```text
simple_telemetry.py
```

기존 `SimpleDecision` evidence를 generic telemetry fact로 변환한다.

잠정 immutable model:

```text
DecisionTelemetry
- inference_category
- selection_candidate_count
- target_mine_probability
- minimum_available_mine_probability
```

`decision_compute_ns`는 `DecisionTelemetry`에 속하지 않는다. Timing은 execution infrastructure 책임이다.

## 14.1 Candidate count 의미

`selection_candidate_count`는:

> solver priority rule을 적용한 뒤 최종 selector class에서 실제로 경쟁한 cell 수

를 의미한다.

전체 hidden cell 수가 아니며 category 사이의 값은 직접 비교할 수 없다.

### LOCAL_DETERMINISTIC

선택 action이 FLAG라면:

```text
pool = deterministic_result.mine_cells
candidate_count = len(pool)
target probability = 1
minimum available probability = NULL
```

Mine pool이 비었을 때만 deterministic OPEN을 선택한다.

```text
pool = deterministic_result.safe_cells
candidate_count = len(pool)
target probability = 0
minimum available probability = NULL
```

### GLOBAL_CERTAINTY

Exact probability가 certain-mine FLAG를 선택하면:

```text
pool = all HIDDEN cells with mine_worlds == total_worlds
candidate_count = len(pool)
target probability = 1
minimum available probability = NULL
```

Certain-mine pool이 priority에서 이기지 않은 경우 global certain-safe OPEN은:

```text
pool = all HIDDEN cells with mine_worlds == 0
candidate_count = len(pool)
target probability = 0
minimum available probability = NULL
```

이다.

### PROBABILITY_GUESS

Pool은 frontier뿐 아니라 unconstrained/floating HIDDEN cell도 포함한다.

```text
minimum_available_mine_probability
    = 모든 selectable HIDDEN cell 중 exact minimum mine probability

pool
    = 그 exact minimum에 tied인 모든 selectable HIDDEN cell

selection_candidate_count
    = len(pool)

target_mine_probability
    = decision.move의 exact probability
```

Stage 2에서는:

```text
target_mine_probability == minimum_available_mine_probability
```

가 exact하게 성립해야 한다.

이 equality는 Stage 2 adapter/test invariant이며 **generic Collector invariant가 아니다.** 이 문장이 future Stage 3 risk-band policy를 승인하는 것은 아니다. Risk-band 정책은 별도의 명시적 Stage 3 specification이 필요하다.

## 14.2 Drift self-check

Adapter는 Stage 2 evidence로 final pool을 재유도하므로 실제 selector와 해석이 drift하면 fail-fast해야 한다.

최소 다음을 assert한다.

```text
derived action type == decision.move.action
decision.move coordinate is in the derived final pool
decision.move coordinate == min(pool, key=(y,x))
```

Stage 2 guess에서는 추가로:

```text
target probability == exact minimum probability
```

를 확인한다.

이 검증에 hidden layout을 사용하면 안 된다.

---

# 15. Python telemetry 내부 probability type

Stage 2 probability는 arbitrary-size integer world count에 기반한 exact 값이다.

수집 경계에서 정보를 잃으면 안 된다.

Python 표현:

```text
Fraction | None
```

대상:

- `target_mine_probability`
- `minimum_available_mine_probability`

규칙:

- initial policy OPEN → 둘 다 `None`;
- deterministic/global certainty → target은 exact `Fraction(0,1)` 또는 `Fraction(1,1)`, minimum은 `None`;
- probability guess → target/minimum은 정상 uncertain guess에서 `(0,1)` 범위의 exact `Fraction`.

SQLite persistence는 §31의 canonical rational TEXT codec을 사용한다.

---

# 16. `simple_runner` instrumentation

Duplicate runner를 만들지 않고 §6의 optional observer를 사용한다.

작은 immutable trace 계약:

```text
SimpleActionTrace
- move
- decision
- decision_compute_ns
- status_after
- safe_cells_opened_delta
- explicit_flag_delta
```

Runner-to-observer execution DTO이며 직접 persistence하지 않는다. `ActionEvent`를 대체하지도 않는다.

## 16.1 Compute-time 경계

Stage 2에서는 기존 analysis/selection call만 측정한다.

```python
t0 = perf_counter_ns()
decision = analyze_position(observation, engine.num_mines)
t1 = perf_counter_ns()

decision_compute_ns = t1 - t0
```

Engine step, observer, Collector, Replay recording, SQLite, board generation, static board analysis는 포함하지 않는다.

Initial explicit benchmark OPEN은:

```text
decision = None
decision_compute_ns = None
```

이다.

이 값은 analysis/selection 주변의 elapsed wall time이지 pure CPU time도, modeled physical play time도 아니다. OS scheduling과 실행 환경의 영향을 받을 수 있다.

Future Stage 3가 같은 field 이름을 재사용하려면 fresh public observation을 받은 시점부터 semantic action을 선택할 때까지의 complete decision/planning boundary를 측정해야 한다. Stage 3가 materially 다른 좁거나 넓은 boundary를 사용한다면 invalid direct comparison을 만들지 말고 별도 timing field를 정의해야 한다.

## 16.2 Observer 호출 시점

정확한 observer call order는 §6.3을 따른다.

`accept_guesses=False`에서 pending guess처럼 분석됐지만 실행되지 않은 decision에는 trace를 만들지 않는다.

Primary Stage 2 baseline은 `accept_guesses=True`이므로 정상 benchmark game은 terminal state까지 실행한다.

---

# 17. Action-effect 의미

Action-effect field는 semantic action과 실행 전후 public observation만으로 계산한다. Hidden 정보를 solver decision으로 되돌려 보내지 않는다.

## 17.1 `safe_cells_opened_delta`

정의:

> action 전 public state가 `HIDDEN` 또는 `FLAGGED`였고 action 후 safe number `0..8`이 된 coordinate의 수.

형식적으로:

```text
safe_cells_opened_delta = count of (x,y) where
    before[y][x] ∈ {HIDDEN, FLAGGED}
    and
    after[y][x] ∈ {0,1,2,3,4,5,6,7,8}
```

예:

```text
single number OPEN   → 1
flood OPEN           → >1 가능
FLAG                 → 0
CHORD                 → >1 가능
mine OPEN             → 0
losing CHORD          → 그 action이 공개한 safe cell만 count
```

`FLAGGED → safe`를 포함하는 것은 의도적이다. 현재 Engine의 flood/chord 동작은 잘못 flag된 safe cell을 자동으로 해제하며 공개할 수 있기 때문이다.

Terminal mine-display state(`EXPLODED`, `MINE`, `FALSE_FLAG`)는 safe reveal에 절대 포함하지 않는다.

완료 game 전체에서 이 값을 합산해 추가 consistency check에 사용할 수 있지만, Engine 내부 revealed counter가 telemetry 정의의 authoritative source는 아니다.

## 17.2 `explicit_flag_delta`

Raw `count_flags(after) - count_flags(before)`로 계산하지 않는다.

정의:

> Engine의 automatic side effect를 제외하고 semantic input action 자체가 직접 만든 flag-state 변화.

Generic action 의미:

```text
FLAG on HIDDEN   → +1
FLAG on FLAGGED  → -1
OPEN             → 0
CHORD            → 0
```

현재 Stage 2 runner는 HIDDEN target만 선택하므로 정상 FLAG trace는 `+1`, OPEN은 `0`이다.

제외되는 automatic effect:

- 승리 시 남은 mine에 대한 automatic flag;
- flood/chord가 잘못 배치된 safe flag를 자동으로 제거하는 효과.

현재 Engine은 `Action.FLAG`를 toggle로 사용한다. Baseline Stage 3에서는 semantic UNFLAG를 제외하므로 별도 UNFLAG action type은 지금 추가하지 않는다. Future policy가 의도적으로 unflag한다면 `explicit_flag_delta=-1`로 현재 field를 재정의하지 않고 그 효과를 보존할 수 있다.

---

# 18. ActionEvent

잠정 generic Python model:

```text
ActionEvent
- action_index

- inference_category
- selection_candidate_count
- target_mine_probability
- minimum_available_mine_probability
- decision_compute_ns

- action_type
- x
- y

- status_after
- safe_cells_opened_delta
- explicit_flag_delta
```

좌표 naming은 현재 프로젝트를 따른다.

```text
(x, y)
observation[y][x]
```

구체적인 interoperability 이유가 없다면 `row/col`을 새로 도입하지 않는다.

## 18.1 Initial event

Benchmark initial OPEN은 event index `0`이다.

Inference metadata는 없다.

## 18.2 Event index 소유자

Collector가 index를 소유한다.

```text
action_index = len(events)
```

Index는 연속이어야 한다.

```text
0..N-1
```

Python model에는 별도 event ID가 필요 없다.

---

# 19. TelemetryCollector

잠정 module:

```text
telemetry_collector.py
```

Collector는 한 게임의 in-memory state다.

책임:

- 이미 실행된 action fact 수용
- immutable ActionEvent 생성
- terminal 뒤 event 거부
- 연속적인 event sequence 유지
- raw event list에서 GameRecord finalize
- summary ↔ raw consistency 검증

하지 않는 책임:

- solver 호출
- Engine action 실행
- SQLite 접근
- Stage 2 selector 의미 계산
- 두 번째 game-rules engine 역할

---

# 20. GameRecord

잠정 summary:

```text
GameRecord
- game_index
- seed
- board_fingerprint

- first_click_x
- first_click_y

- result

- total_actions
- open_count
- flag_count
- chord_count

- local_deterministic_count
- global_certainty_count
- probability_guess_count

- had_probability_guess
- first_guess_action_index

- board_3bv
- board_ops

- compute_time_total_ns
- compute_time_max_ns
```

`termination_reason`과 per-game `error_code`는 v1에서 의도적으로 **defer**한다. v1 fail-fast policy에서는 committed game이 정상 WIN/LOSS outcome이고 technical-failure game은 persist하지 않고 rollback한다. Future policy가 technical/aborted game row를 저장하기 시작하면 그때 field를 추가할 수 있다.

가능한 summary 값은 finalization 시 immutable raw ActionEvent에서 파생한다.

## 20.1 필수 invariant

```text
total_actions
= open_count + flag_count + chord_count
= len(ActionEvents)
```

정확히 한 번의 policy initial OPEN 이후 analyzed decision이 이어지는 primary Stage 2 baseline에서는:

```text
local_deterministic_count
+ global_certainty_count
+ probability_guess_count
= total_actions - 1
```

이것은 Stage 2 benchmark validation rule이지 모든 future solver에 적용하는 universal DB invariant가 아니다.

Guess invariant:

```text
guess_count == 0
↔ had_probability_guess == false
↔ first_guess_action_index == NULL
```

그리고:

```text
guess_count > 0
↔ had_probability_guess == true
↔ first_guess_action_index points to first guess event
```

Compute invariant:

```text
compute_time_total_ns
= sum(non-null event decision_compute_ns)
```

```text
compute_time_max_ns
= max(non-null event decision_compute_ns)
```

Analyzed decision이 없으면:

```text
compute_time_total_ns = 0
compute_time_max_ns = NULL
```

---

# 21. Game result 의미

Committed v1 game row에는 정확히 하나의 authoritative outcome이 있다.

```text
WIN
LOSS
```

Mapping:

```text
Engine WON  → WIN
Engine LOST → LOSS
```

정상 probability-guess mine hit은 committed LOSS다.

Technical solver/Engine/telemetry/repository failure를 loss로 계산하면 안 된다. v1 fail-fast behavior에서는:

```text
technical failure
→ 열려 있다면 current game persistence transaction rollback
→ technical-error GameRecord를 저장하지 않음
→ 새 game 시작 중단
→ BenchmarkRun fail
```

Persist할 수 있는 경우 technical failure detail은 run-level `failure_code`에 둔다.

이 단순한 result domain은 의도적이다. Run policy가 error/aborted game도 persist하도록 바뀔 때만 per-game outcome field를 확장한다.

---

# 22. Board 3BV / Ops

`board_3bv`와 `board_ops`는 static evaluation-only metric이다.

현재 architecture 정의:

```text
Ops = 8-connected zero region 수
3BV = Ops + isolated number cell 수
```

`reset_with_mines()`가 이미 Engine 내부 static analysis를 수행하더라도 benchmark가 evaluation을 위해 `analyze_board(snapshot)`을 다시 실행할 수 있다.

이는 계산 중복이다.

중복을 피하려면 Engine public API를 변경하거나 internal static analysis data를 반환해야 하므로 초기에는 중복을 허용한다.

Pilot에서 측정한 뒤 최적화 여부를 판단한다.

---

# 23. BenchmarkRunner

잠정 module:

```text
benchmark_runner.py
```

책임:

- BenchmarkRun 생성
- 요청된 game index 순회
- deterministic BenchmarkBoard 생성
- v1에서 game마다 fresh Engine 생성
- `reset_with_mines()`
- 설치된 board identity 검증
- Collector 생성
- one-game executor 호출
- Stage 2 decision trace를 adapter를 통해 변환
- GameRecord finalize
- 완전한 game transaction 저장
- progress 제공
- run status finalize

BenchmarkRunner는 inference logic을 복제하면 안 된다.

---

# 24. Fresh Engine 정책

v1에서는 benchmark game마다 새 `MinesweeperEngine`을 만든다.

이유:

- 가장 강한 state isolation
- 가장 단순한 correctness model
- cross-game state leakage 방지

Pilot profiling에서 Engine 생성이 유의미한 비용임이 확인되면 재사용을 검토할 수 있다.

Solver `decision_compute_ns`는 Engine 생성이 측정 범위 밖이므로 영향을 받지 않는다.

---

# 25. Stage 2 baseline solver configuration

Primary Stage 2 baseline은 실제 guess를 허용해야 한다.

```text
accept_guesses = True
initial_open = (0, 0)
```

그렇지 않으면 fixed-board run이 실제 guess 전에 멈추거나 fresh-game first-click policy를 재현하지 못한다.

`solver_config_snapshot`에는 최소한 이 policy 값들과 Stage 2 decision에 영향을 주는 다른 configuration을 기록한다.

Baseline은 다음을 보고한다.

- Win Rate
- Guess Game Rate
- Guess Count
- Guess probabilities
- inference categories
- decision compute time

이 configuration에서 benchmark executor가 예상 밖으로 `GUESS_REQUIRED`를 반환하면 benchmark invariant failure로 취급한다.

---

# 26. Run lifecycle

상태:

```text
CREATED
RUNNING
COMPLETED
ABORTED
INTERRUPTED
FAILED
```

정상 transition:

```text
CREATED → RUNNING → COMPLETED
```

의도적 stop:

```text
RUNNING → ABORTED
```

Caught fatal benchmark failure:

```text
RUNNING → FAILED
```

`INTERRUPTED`는 process kill, crash, power loss처럼 정상 finalization 없이 죽은 stale run을 나중에 식별하기 위한 예약 상태다. Automatic stale-run recovery는 defer한다.

Database failure는 최종 `FAILED` status update마저 불가능하게 만들 수 있다. 따라서 fatal-failure behavior는:

```text
가능하면 current game transaction rollback
→ 새 game 시작 안 함
→ 별도 transaction으로 best-effort FAILED 기록
→ failure 전파
```

이다.

그 status update도 실패하면 persisted `RUNNING` row가 남을 수 있다. 이는 deferred stale-run recovery와 연결된 v1의 알려진 한계이지 지금 recovery framework를 만들 이유는 아니다.

---

# 27. Stop 동작

v1에서는 exact probability enumeration 내부에 cancellation check를 추가하지 않는다.

아직 실행할 game이 남아 있는 상태에서 stop이 요청되면:

```text
current game finish
→ completed game commit
→ 새 game 시작 안 함
→ run ABORTED
```

Stop request를 확인한 시점에 이미 requested range 전체가 완료되었다면 `ABORTED`가 아니라 `COMPLETED`로 finalization한다.

아주 비싼 single decision 때문에 stop이 지연될 수 있다. Solver 내부까지 들어가는 immediate/deep cancellation은 defer한다.

---

# 28. BenchmarkRun

잠정 pure model field:

```text
telemetry_schema_version

created_at
started_at
finished_at
run_status

git_commit
git_dirty
app_version

solver_stage
solver_policy
solver_config_snapshot

width
height
num_mines
difficulty_name

first_click_policy
board_generator_version
benchmark_set_id

requested_games
processed_games

environment_snapshot
failure_code
```

요구사항:

- `git_commit` 필수;
- `git_dirty` 필수;
- benchmark run에서는 `benchmark_set_id` 필수;
- `git_dirty`는 §34.1의 정의에 따라 run 시작 시 Git이 무시하지 않는 working tree에서 한 번 계산한다;
- official baseline 실행은 `git_dirty == false`를 요구한다;
- development pilot은 dirty를 허용하지만 그 사실을 기록하며 official-baseline eligible하지 않다.

BenchmarkRun v1에는 wins/losses/rates를 직접 저장하지 않고 games에서 derive한다.

`processed_games`는 의도적으로 다음을 뜻한다.

> 이 run에서 complete game transaction이 성공적으로 commit된 수.

Invariant:

```text
processed_games == COUNT(games for run_id)
```

`COMPLETED`는:

```text
processed_games == requested_games
```

뿐 아니라 v1 prefix run에서 정확한 game-index coverage `{0, ..., requested_games-1}`를 요구한다.

---

# 29. SQLite architecture

잠정 module:

```text
telemetry_schema.py
telemetry_repository.py
```

`telemetry_schema.py` 책임:

- DDL;
- physical schema version;
- stable persistence enum/string constants;
- minimal schema initialization / minimal migration boundary.

`telemetry_repository.py` 책임:

- connection 및 PRAGMA initialization;
- transactions;
- inserts;
- run-status updates;
- persistence queries;
- exact rational TEXT를 포함한 model ↔ persistence codec.

`benchmark_statistics.py`는 read-only aggregation query를 직접 실행하거나 repository query helper를 사용할 수 있지만 persistence 상수를 magic integer/string으로 중복 작성하지 말고 import해야 한다.

Repository는 game legality rule, Stage 2 inference semantics, 3BV calculation을 포함하면 안 된다.

---

# 30. SQLite table 관계

v1은 세 개의 주요 table을 사용한다.

```text
benchmark_runs
    1 ───── N games
                1 ───── N action_events
```

Foreign key:

```text
games.run_id
→ benchmark_runs.run_id
ON DELETE CASCADE

action_events.game_id
→ games.game_id
ON DELETE CASCADE
```

모든 connection에서:

```sql
PRAGMA foreign_keys = ON;
```

을 활성화한다.

---

# 31. Probability persistence 표현 — 해결됨

Python telemetry는 exact `Fraction`을 유지한다.

SQLite authoritative representation은 두 probability field 모두에 대해 canonical reduced rational `TEXT`를 사용한다.

## 31.1 Canonical codec

Non-null probability는 항상 정확히 다음 형식으로 저장한다.

```text
"numerator/denominator"
```

예:

```text
Fraction(0,1) → "0/1"
Fraction(1,1) → "1/1"
Fraction(1,3) → "1/3"
```

Canonical 요구사항:

- numerator는 부호 없는 base-10 nonnegative integer이며 `0`을 제외하고 leading zero가 없다.
- denominator는 부호 없는 base-10 positive integer이며 leading zero가 없다.
- fraction은 lowest terms로 reduced되어 있다.
- denominator는 positive다.
- 값은 `0 <= p <= 1`이어야 한다.
- parsed value를 serialize하면 저장된 문자열과 정확히 같아야 한다.

Repository codec은 Python `Fraction`과 explicit canonical formatter로 생성/검증한다. 관대한 `Fraction(text)` parsing만 믿으면 안 된다.

## 31.2 Nullability 의미

```text
initial policy OPEN
    target = NULL
    minimum = NULL

deterministic/global certainty
    target = "0/1" or "1/1"
    minimum = NULL

probability guess
    target = exact rational TEXT
    minimum = exact rational TEXT
```

Stage 2 guess에서는 두 exact 값이 같지만 risk-discipline auditability와 future policy comparison을 보존하기 위해 둘 다 유지한다.

## 31.3 기각/연기한 표현

`REAL`은 exactness를 나중에 복구할 수 없으므로 authoritative probability로 사용하지 않는다.

SQLite INTEGER numerator/denominator도 Stage 2 world count가 SQLite signed 64-bit integer range를 넘을 수 있으므로 general exact representation으로 쓰지 않는다.

Derived approximate `REAL` analytics column은 defer한다. 나중에 profiling/query requirement가 정당화하면 exact TEXT에서 추가할 수 있다.

Custom BLOB codec도 현재 evidence가 추가 복잡성을 정당화하지 않으므로 defer한다.

v1 codec은 benchmark domain에서 실제로 도달 가능한 모든 probability를 exact하게 round-trip해야 한다. 여기에는 SQLite signed 64-bit INTEGER 범위를 충분히 넘는 값과 Expert board의 이론적 world-count 규모를 대표하는 값이 포함된다. 다만 CPython의 integer-string safety limit와 무관한 literal unlimited decimal-string conversion을 보장한다는 뜻은 아니다. Codec은 process-global `sys.set_int_max_str_digits()` 설정을 변경하면 안 된다.

## 31.4 Rational TEXT의 SQL 의미론

Canonical rational TEXT는 SQLite에서 **opaque exact persistence value**이며 numeric SQL type이 아니다.

Canonical string equality만으로 의미가 보존되는 다음 연산은 사용할 수 있다.

```text
=
!=
DISTINCT
GROUP BY
COUNT
```

다음처럼 probability TEXT를 numeric ordering/arithmetic에 직접 사용하면 안 된다.

```text
< / > / <= / >=
numeric probability 순서를 위한 ORDER BY
MIN / MAX
AVG / SUM
CAST(... AS REAL)
산술식
```

Probability의 수치 통계는 repository codec으로 Python `Fraction`에 decode한 뒤 `benchmark_statistics.py` 또는 equivalent statistics layer에서 계산/정렬한다.

다음 fixture를 test에 포함한다.

```text
"1/3" and "2/9"
```

Lexicographic SQL `MIN`은 수학적 minimum이 아니며 SQLite의 `"n/d"` numeric coercion/cast도 올바른 fraction conversion이 아니다.

# 32. SQLite 물리 schema

## 32.1 Schema version

SQLite physical schema version에는:

```sql
PRAGMA user_version
```

을 사용한다.

Telemetry semantics를 나타내는 `telemetry_schema_version`과 분리한다.

v1에는 별도 schema metadata table이 필요 없다.

## 32.2 `benchmark_runs`

Conceptual columns:

```text
run_id INTEGER PRIMARY KEY

telemetry_schema_version INTEGER NOT NULL

created_at TEXT NOT NULL
started_at TEXT NULL
finished_at TEXT NULL

run_status TEXT NOT NULL

git_commit TEXT NOT NULL
git_dirty INTEGER NOT NULL
app_version TEXT NULL

solver_stage TEXT NOT NULL
solver_policy TEXT NOT NULL
solver_config_snapshot TEXT NOT NULL

width INTEGER NOT NULL
height INTEGER NOT NULL
num_mines INTEGER NOT NULL
difficulty_name TEXT NULL

first_click_policy TEXT NOT NULL
board_generator_version TEXT NOT NULL
benchmark_set_id TEXT NOT NULL

requested_games INTEGER NOT NULL
processed_games INTEGER NOT NULL DEFAULT 0

environment_snapshot TEXT NOT NULL
failure_code TEXT NULL
```

Structural check 예:

```text
width > 0
height > 0
0 <= num_mines < width*height
requested_games > 0
0 <= processed_games <= requested_games
git_dirty IN (0,1)
COMPLETED → processed_games=requested_games
```

## 32.3 `games`

Conceptual columns:

```text
game_id INTEGER PRIMARY KEY

run_id INTEGER NOT NULL
game_index INTEGER NOT NULL
seed INTEGER NOT NULL

board_fingerprint TEXT NOT NULL

first_click_x INTEGER NOT NULL
first_click_y INTEGER NOT NULL

result INTEGER NOT NULL

total_actions INTEGER NOT NULL
open_count INTEGER NOT NULL
flag_count INTEGER NOT NULL
chord_count INTEGER NOT NULL

local_deterministic_count INTEGER NOT NULL
global_certainty_count INTEGER NOT NULL
probability_guess_count INTEGER NOT NULL

had_probability_guess INTEGER NOT NULL
first_guess_action_index INTEGER NULL

board_3bv INTEGER NOT NULL
board_ops INTEGER NOT NULL

compute_time_total_ns INTEGER NOT NULL
compute_time_max_ns INTEGER NULL
```

Required uniqueness:

```text
UNIQUE(run_id, game_index)
```

Seed나 fingerprint uniqueness는 요구하지 않는다.

Persisted `board_fingerprint`는 64-character lowercase-hex contract를 만족해야 한다. Complete codec은 Python에서 검증하고 DB는 length/lowercase/hex domain 같은 stable shape check를 둘 수 있다.

Stable same-row arithmetic check 예:

```text
total_actions = open_count + flag_count + chord_count
had_probability_guess IN (0,1)
probability_guess_count = 0 → had_probability_guess = 0 and first_guess_action_index IS NULL
probability_guess_count > 0 → had_probability_guess = 1 and first_guess_action_index IS NOT NULL
```

Cross-row/raw-event consistency는 Python/repository test 책임이다.

## 32.4 `action_events`

Conceptual columns:

```text
game_id INTEGER NOT NULL
action_index INTEGER NOT NULL

inference_category INTEGER NULL
selection_candidate_count INTEGER NULL

target_mine_probability TEXT NULL
minimum_available_mine_probability TEXT NULL

decision_compute_ns INTEGER NULL

action_type INTEGER NOT NULL
x INTEGER NOT NULL
y INTEGER NOT NULL

status_after INTEGER NOT NULL

safe_cells_opened_delta INTEGER NOT NULL
explicit_flag_delta INTEGER NOT NULL

PRIMARY KEY(game_id, action_index)
```

v1은:

```sql
WITHOUT ROWID
```

를 사용한다. `(game_id, action_index)`가 natural key이고 현재 evidence에서 insert bottleneck 없이 의미 있는 storage reduction이 확인되었기 때문이다.

Event surrogate ID는 추가하지 않는다.

Stable structural range/domain check는 SQL에 둔다. Stage 2 selector semantics, action-0 null pattern, exact candidate-pool 의미, `target==minimum`은 SQL CHECK가 아니라 Python/adapter validation에 둔다.

---

# 33. Persistence enum mapping

Implementation enum numeric value를 암묵적으로 persistence하면 안 된다.

Stable persistence mapping/constant는 `telemetry_schema.py`가 소유하고 repository/statistics가 공유한다.

v1 mapping을 동결한다.

```text
Action
1 = OPEN
2 = FLAG
3 = CHORD

InferenceCategory
1 = LOCAL_DETERMINISTIC
2 = GLOBAL_CERTAINTY
3 = PROBABILITY_GUESS

StatusAfter
1 = PLAYING
2 = WON
3 = LOST

GameResult
1 = WIN
2 = LOSS
```

Run status와 policy identifier도 Python enum `.value`에 우연히 결합하지 말고 explicit stable string으로 persistence한다.

Core Engine enum ordering이 DB 의미를 암묵적으로 결정해서는 안 된다.

---

# 34. Timestamp, provenance, snapshot

Timestamp는 UTC ISO-8601 text로 저장한다. UI는 local time으로 render할 수 있다.

`solver_config_snapshot`과 `environment_snapshot`은 deterministic JSON TEXT로 serialize한다. 예:

```python
json.dumps(value, sort_keys=True, separators=(",", ":"))
```

## 34.1 Source provenance

다음을 기록한다.

```text
git_commit
git_dirty
```

`git_dirty`는 **run 시작 시 한 번** 계산한다.

Revision 2의 canonical clean-tree check는 다음과 동등해야 한다.

```bash
git status --porcelain=v1 --untracked-files=all
```

이 명령이 아무 entry도 출력하지 않을 때만 `git_dirty = false`다. 따라서 staged 변경, unstaged 변경, Git이 무시하지 않는 untracked file은 모두 dirty로 처리한다. Benchmark DB, cache, build artifact처럼 legitimate generated output은 telemetry code에서 예외 처리하지 말고 `.gitignore`에 포함해 dirty 판정에서 자연스럽게 제외한다.

Minimum official-baseline eligibility는 새 DB column이 아니라 **derived predicate**다.

```text
run_status == COMPLETED
AND git_dirty == false
AND requested v1 prefix의 exact coverage가 검증됨
```

Official execution mode는 benchmark run row를 만들기 전에 dirty working tree를 거부해야 한다. Development pilot은 dirty를 허용하지만 `git_dirty=true`를 유지하고 official-baseline eligible하지 않다.

이 규칙은 어떤 untracked source가 "execution-relevant"인지 분류하는 별도 framework를 만들지 않고 단순하고 재현 가능한 provenance contract를 유지하기 위한 것이다.

## 34.2 Minimum environment snapshot

최소 포함:

```text
Python implementation
Python version
platform / OS
machine architecture
CPU count
가능하면 CPU identifier/model
SQLite version
perf_counter clock information
```

가능하면 relevant application version metadata도 기록한다.

Environment capture를 hardware inventory framework로 확장하지 않는다.

Compute-time comparison은 relevant environment/provenance key가 compatible할 때만 직접 비교 가능한 값으로 본다. Modeled Stage 3 physical time은 별도 metric이며 Python elapsed compute time과 혼동하면 안 된다.

---

# 35. Game transaction boundary

Completed game 하나가 atomic persistence unit이다.

Solver가 game을 플레이하는 동안 SQLite transaction을 열어 두지 않는다.

Game 종료 후 `GameRecord`와 events가 finalize되면:

```text
BEGIN

INSERT games(...)
→ get game_id

bulk INSERT action_events(game_id, ...)

UPDATE benchmark_runs
SET processed_games = processed_games + 1

COMMIT
```

Transaction 내부 어디서든 failure가 나면:

```text
ROLLBACK
```

DB에는 다음이 생기면 안 된다.

- committed game의 partial action stream;
- game 없는 action row;
- processed count 증가 없이 commit된 game.

Batch insertion(`executemany` 또는 equivalent)을 사용하고 action마다 transaction을 만들지 않는다.

Persistence failure로 DB 자체가 unwritable해지면 이후 best-effort run-status update도 실패할 수 있으며 §26이 이 한계를 정의한다.

---

# 36. SQLite operating mode

모든 connection에서 다음을 초기화하고 활성 여부를 확인한다.

```sql
PRAGMA foreign_keys = ON;
```

v1 database mode:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
```

이유:

- WAL은 intended local writer + statistics-reader workflow에 적합하다.
- 현재 profiling에서 SQLite insert는 Stage 2 bottleneck으로 확인되지 않았다.
- 따라서 v1은 필요 없는 속도를 위해 durability를 먼저 낮추지 않고 더 보수적인 설정으로 시작한다.

`synchronous=NORMAL`을 영구 기각하는 것은 아니다. Representative pilot에서 database durability sync가 material bottleneck이라는 evidence가 생기고 reduced recent-commit durability를 허용할 수 있을 때 재검토한다.

UI/statistics reader는 WAL checkpoint를 불필요하게 지연시키지 않도록 read transaction을 짧게 유지한다. Evidence 없이 custom checkpoint-management framework를 만들지 않는다.

---

# 37. Index 정책

처음에는 최소화한다.

기존 key만으로도 다음을 지원한다.

- run lookup
- run 내 game 순서
- game 내 action 순서

모든 statistic field에 미리 index를 만들지 않는다.

Pilot 후:

```text
EXPLAIN QUERY PLAN
```

을 기준으로 필요한 index만 추가한다.

증거 없이 high-volume action table의 index를 늘리지 않는다.

---

# 38. Statistics layer

잠정 module:

```text
benchmark_statistics.py
```

UI presentation이 아니라 derived benchmark statistics를 소유한다.

## 38.1 Coverage 우선

모든 statistics result는 사용한 run status와 coverage를 식별해야 한다.

Official baseline statistics는 valid completed requested prefix를 요구한다. Partial run 통계도 진단용으로 볼 수 있지만 requested/processed coverage를 눈에 보이게 표시하고 complete baseline처럼 다루면 안 된다.

## 38.2 초기 정의

최소 보고 항목:

- processed games;
- wins;
- losses;
- win rate;
- games with probability guess;
- guess-game rate;
- mean/distribution of guess count;
- probability-guess event distribution;
- local/global/guess action counts;
- total actions;
- OPEN/FLAG/CHORD counts;
- compute-time total/mean/max 및 유용한 percentile;
- 3BV distributions.

정의:

```text
win_rate = WIN / (WIN + LOSS)

guess_game_rate = games_with_guess / (WIN + LOSS)

mean_guess_count
    = 모든 WIN/LOSS game의 probability_guess_count 평균
      zero-guess game도 0으로 포함

mean_decision_compute_ns
    = sum(non-null decision_compute_ns)
      / count(non-null decision_compute_ns)
```

Analyzed decision이 하나도 없으면 mean decision compute time은 0이 아니라 `NULL`이다.

기본 probability distribution의 observation unit은 하나의 `PROBABILITY_GUESS` ActionEvent다. 다른 단위를 사용하면 명시적으로 label한다.

## 38.3 Interpretation 경계

Primary corpus는 `FIRST_CLICK_FIXED_0_0` 조건부다. 첫 cell의 안전만 보장하고 zero opening은 보장하지 않는다. 따라서 보고되는 win/guess statistics는 이 corpus 조건을 명시해야 하며 모든 Minesweeper first-click policy의 일반 대표값처럼 표현하면 안 된다.

Compute-time comparison은 diagnostic이며 environment-sensitive하다. Stage 3 modeled physical-play objective가 아니다.

Technical failure를 loss로 재분류하지 않는다.

---

# 39. Graph/UI 방향

Graph layer는 Pre-Stage 3 / Stage 1 statistics expansion deliverable로 유지하지만 **benchmark backend가 올바르다는 것을 증명하는 조건 자체는 아니다.**

Backend pilot data와 aggregation semantics가 검증된 뒤 구현한다.

Preferred in-app plotting library:

```text
PyQtGraph
```

필요하면 Matplotlib을 나중에 report/export-quality static figure용으로 사용할 수 있지만 처음부터 둘 다 구현하지 않는다.

UI는 SQL/statistics semantics를 직접 계산하지 않고 aggregation result를 소비해야 한다.

`ui_manager.py`를 statistics/plotting monolith로 더 키우지 않는다. UI 단계가 시작되면 작은 dedicated presentation/widget module을 선호한다.

---

# 40. Human history와 solver benchmark

사람 플레이 history와 solver benchmark telemetry는 같은 DB schema를 반드시 공유할 필요가 없다.

공유할 수 있는 것:

- aggregation 개념
- graph widget
- visual presentation pattern

겉보기 재사용을 위해 하나의 generalized schema로 억지로 통합하지 않는다.

---

# 41. Replay 분리

`ReplayEvent`와 `ActionEvent`는 별도 모델로 유지한다.

Replay 목적:

> game 재현

Telemetry 목적:

> solver decision, inference, effect, performance 측정

합치지 않는다.

현재 Stage 2 runner는 항상 replay 정보를 만든다. 대규모 benchmark에서 replay 생성 overhead는 나중에 profiling할 수 있다.

Pilot evidence 없이 `record_replay=False` optimization을 추가하지 않는다.

추후 추가한다면 기존 default replay 동작은 backward-compatible하고 테스트로 보호되어야 한다.

---

# 42. Standard vs debug telemetry

v1 standard telemetry:

- semantic action당 ActionEvent 하나
- game당 GameRecord 하나
- event당 board snapshot 없음
- decision당 full candidate list 없음

향후 debug telemetry는 다음을 포함할 수 있다.

- selected seed only
- full candidates
- 추가 probability evidence
- board-state checkpoints

100k 전체 corpus에 debug-scale data를 기본 저장하지 않는다.

---

# 43. Validation ownership

## Database

Stable structural fact를 enforce한다.

- FK integrity;
- unique `(run_id, game_index)`;
- primary `(game_id, action_index)`;
- stable enum/domain values;
- basic numeric ranges;
- processed/requested bounds;
- stable CHECK에 적합한 same-row summary arithmetic.

Solver-selection semantics를 SQL CHECK에 넣지 않는다.

## Python model / Collector

다음을 enforce한다.

- structural nullability rule;
- action-index continuity;
- terminal 이후 event 금지;
- summary/raw consistency;
- guess-summary consistency;
- compute aggregation consistency;
- initial policy event null pattern;
- complete terminal game finalization.

## Stage 2 adapter/tests

다음을 enforce한다.

- complete `DecisionKind → InferenceCategory` mapping;
- exact final competition pool/candidate count;
- FLAG-priority semantics;
- deterministic/global probability `0/1` semantics;
- Stage 2 guess `target == exact minimum`;
- actual `decision.move`와 `(y,x)` tie-break에 대한 adapter drift self-check.

이 검증은 public decision evidence를 사용하고 hidden layout을 사용하지 않는다.

## Benchmark evaluator / integration tests

Solver execution과 분리된 evaluation 단계에서는 known fixed board를 사용해 generated board identity와 대표 certainty soundness 같은 evaluation fact를 audit할 수 있다. Hidden layout이 solver input으로 들어가면 안 된다.

## Engine / Runner

다음을 enforce한다.

- action legality;
- target-visibility contract;
- explicit initial-open precondition;
- fresh observation after action;
- progress contract;
- terminal handling;
- observer ordering.

Concrete reason 없이 layer 사이에서 같은 책임을 중복하지 않는다.

---

# 44. 파일 경계 — 잠정

예상 신규 파일:

```text
benchmark_board.py
telemetry_model.py
simple_telemetry.py
telemetry_collector.py
telemetry_schema.py
telemetry_repository.py
benchmark_runner.py
benchmark_statistics.py
```

예상 기존 수정:

```text
simple_runner.py
```

초기에는 변경하지 않을 가능성이 높은 파일:

```text
core_engine.py
simple_algorithm.py
simple_probability.py
simple_decision.py
board_snapshot.py
board_analyzer.py
Replay modules
ui_manager.py
```

`ui_manager.py` 수정은 이후 graph/statistics UI 단계에 속한다.

이 file split은 설계 목표이지 필요도 없는 파일을 미리 전부 만들라는 뜻이 아니다.

---

# 45. 불필요한 generic abstraction 금지

다음을 미리 만들지 않는다.

```text
TelemetryService
generic EventBus
generic Solver interface hierarchy
generic DecisionResult replacing SimpleDecision
generic GameSession framework
plugin telemetry registry
generic storage backend interface
```

새 abstraction은 현재 구체적 책임이 있거나 실제 두 번째 implementation pressure가 생겼을 때만 도입한다.

`simple_telemetry.py`는 Stage 2 → generic telemetry semantic adapter라는 구체적 역할이 있을 때만 정당화된다.

---

# 46. Pilot 전략

Full baseline 전에:

```text
unit/integration fixtures
→ ~100 games
→ ~1,000 games
→ 10,000 games
```

다음을 검증하고 기록한다.

- reproducibility/golden checks;
- event/summary invariants;
- paired identity behavior;
- DB 및 WAL growth;
- transaction/failure behavior;
- exact probability codec;
- per-game action/event counts;
- game wall-duration distribution;
- decision compute-time distribution 및 maximum/tail case;
- basic aggregation;
- query plans;
- 여전히 관련 있다면 replay overhead;
- 여전히 관련 있다면 duplicate static-analysis cost.

10k run 이후 예상 100k 운영 시간이 chunked/non-prefix run 또는 resume를 정당화하는지 명시적으로 결정한다. Evidence 전에 그 mechanism을 추가하지 않는다.

그 다음 같은 core data model이 안정적이면:

```text
100,000-game baseline
```

으로 진행한다.

1M games는 v1 completion requirement가 아니다.

---

# 47. 완료 및 Stage 3 readiness 조건

## 47.1 Backend validation gate

Stage 2 benchmark backend는 다음 조건에서 validated된 것으로 본다.

- Generator V1이 reference contract 아래 deterministic하고 golden-tested다.
- canonical fingerprint encoding이 frozen되고 검증된다.
- 같은 benchmark index가 matching fingerprint를 재현한다.
- explicit first OPEN policy가 정확히 재현된다.
- hidden layout이 solver decision으로 들어갈 수 없다.
- Stage 2 baseline이 guess를 실제로 실행하며 terminal까지 진행한다.
- ActionEvent가 index 0부터 terminal action까지 contiguous하다.
- GameRecord summary가 raw event와 일치한다.
- exact probability가 persistence round-trip에서 보존된다.
- one game = one atomic DB transaction이다.
- run progress가 committed game 및 exact prefix coverage와 일치한다.
- paired comparison이 mismatch/missing row를 거부한다.
- core aggregate statistics와 denominator가 검증된다.
- representative 100/1k/10k run이 operationally stable하다.
- baseline provenance가 commit/config/environment를 포함하며 official baseline은 §34.1 clean-tree eligibility rule을 만족한다.

이 gate에 도달했다는 것은 **measurement design의 schema/semantics를 freeze할 만큼 신뢰할 수 있다**는 뜻이다. 아직 Pre-Stage 3 전체 작업이 끝났다는 뜻은 아니다.

## 47.2 Full Stage 2 baseline

Intended full Stage 2 baseline target은:

```text
EXPERT_GENERAL_V1 100,000 games
```

이다.

10k pilot이 concrete chunking/resume 필요성을 증명하면 telemetry model을 재설계하지 말고 100k run 전에 필요한 범위만 좁게 해결한다.

Completed full baseline은 database/results와 함께 commit, configuration, environment, benchmark-set identity, specification version을 보존해야 한다.

## 47.3 Graph/UI 완료

Basic statistics/graph UI는 Pre-Stage 3 project work에 계속 포함되지만 **backend measurement correctness를 증명하는 요소 자체는 아니다.**

Validated backend aggregation이 존재한 뒤 같은 statistics layer를 사용해 구현한다. Graph 구현 편의를 위해 Stage 2 benchmark semantics를 바꾸면 안 된다.

## 47.4 Stage 3-A 전환

Project-level Pre-Stage 3는 다음 조건에서 완료된다.

- validated backend/schema가 frozen됨;
- intended full Stage 2 baseline이 완료되고 보존됨;
- basic statistics/graph presentation이 validated aggregation result를 소비할 수 있음.

Project가 stage boundary를 바꾸기로 별도로 기록하지 않는 한, 그 이후에만 Stage 3-A implementation이 solver/action-selection behavior를 변경하기 시작한다.

Stage 3-A는 frozen Stage 2 baseline과 명시적으로 paired board에서 비교해야 한다.

---

# 48. 필수 테스트 — 상위 수준

최소 다음 test를 추가한다.

## Benchmark board

- first-click coordinate never mined;
- surrounding cells remain eligible mines;
- deterministic seed output;
- 0/1/2/42/999/99999 representative golden fingerprints;
- exact §9.2 SHA-256/LF contract에서 first-1,000 prefix digest가 `93852d335a46af9420dbdcdf0e256bb9149778f33602f6a4facdf0295677777c`와 일치;
- input set/iteration order와 무관한 canonical fingerprint encoding;
- duplicate fingerprint allowed;
- generator가 global RNG를 변경하지 않음;
- Generator V1 representative placement가 현재 Engine first-open exclusion policy와 동등함.

## Runner instrumentation

- default current semantics unchanged;
- `initial_open` validation이 Engine mutation 전에 실행됨;
- explicit benchmark initial OPEN exactly once;
- explicit initial OPEN bypasses solver;
- initial trace `decision=None` / null inference/compute metadata;
- compute timer가 `analyze_position()`만 감쌈;
- observer가 fresh observation 및 runner validation 뒤 successful action마다 정확히 한 번 호출됨;
- terminal action도 한 번 observe됨;
- pending/unexecuted guess에는 trace 없음;
- observer exception propagates;
- terminal Engine에 extra action/trace 없음;
- initial-open safety 판단에 hidden board를 보지 않음;
- benchmark configuration 밖 guess behavior unchanged.

## Stage 2 adapter

- local safe/mine pool count;
- global 0%/100% pool count;
- unconstrained/floating cell 포함 exact minimum guess tie count;
- exact Fraction preserved;
- mapping exhaustiveness;
- derived pool/action이 실제 `decision.move`와 일치;
- `(y,x)` tie-break self-check;
- Stage 2 guess target equals exact minimum.

## Collector/model

- contiguous indices;
- terminal event 이후 record 금지;
- count correctly derived;
- initial-event nullable pattern;
- guess summary correct;
- compute total/max correct;
- zero-decision game total=0/max=NULL;
- `safe_cells_opened_delta`가 `FLAGGED → safe`를 count;
- win auto-flag/flood auto-unflag가 `explicit_flag_delta`를 오염시키지 않음.

## Probability persistence

- canonical `0/1`, `1/1`, ordinary fraction round-trip;
- SQLite signed 64-bit INTEGER 범위를 넘는 값과 benchmark-domain을 대표하는 약 100자리 값의 exact round-trip;
- noncanonical/malformed value rejected;
- codec이 process-global `sys.set_int_max_str_digits()`를 변경하지 않음;
- rational TEXT를 numeric SQL로 취급하지 않음: `"1/3"` / `"2/9"` fixture로 numeric ordering/aggregation 전에 `Fraction` decode가 필요함을 검증;
- authoritative comparison이 derived float approximation을 사용하지 않음.

## Repository

- 모든 connection에서 FK enabled/verified;
- WAL/FULL initialization;
- one-game atomic transaction;
- game/action/progress failure rollback;
- processed count same transaction increment;
- `(run_id, game_index)` uniqueness;
- required `benchmark_set_id`;
- stable enum mapping;
- `WITHOUT ROWID` action table schema;
- cascading delete;
- completed-run processed-count invariant;
- 가능한 범위에서 best-effort FAILED path behavior test.

## Statistics / pairing

- completed prefix coverage validation;
- missing pair를 silent drop하지 않고 reject;
- fingerprint/seed/first-click mismatch reject;
- win/guess denominator correct;
- mean guess count에 zero-guess game 포함;
- partial run 통계가 coverage를 표시하고 official full baseline으로 취급되지 않음.

## Integration

- generated board → Engine → explicit initial OPEN → Stage 2 runner → telemetry → DB;
- persisted fingerprint matches actual played board;
- primary baseline ActionEvent 0이 null inference metadata를 가진 policy OPEN;
- official paired run이 requested identity field 전부 검증;
- staged/unstaged/non-ignored untracked file을 모두 포함하는 provenance test; official mode는 run 생성 전에 dirty 상태를 거부하고 eligibility는 COMPLETED + clean tree + exact prefix coverage에서 derive.

---

# 49. Revision 2 delta-review 종료 기록

Revision 2는 이전 full-audit/adjudication cycle 이후 Codex와 Claude Code의 독립 delta review를 각각 받았다.

두 reviewer의 최종 판정은 모두 다음과 같았다.

```text
Ready to freeze for implementation: YES
```

남은 implementation blocker는 없었다.

Freeze 전에 최종 반영한 correction은 다음 네 가지다.

1. §9.2를 lowercase fingerprint ASCII bytes의 LF(`0x0A`) join + no trailing newline + SHA-256으로 동결하고 검증된 golden 값을 삽입;
2. `git_dirty`를 Git이 무시하지 않는 working tree 전체에 대해 정의하고 official-baseline eligibility를 derived predicate로 정의;
3. canonical rational TEXT는 SQLite numeric semantics에서 opaque하므로 numeric statistics 전에 `Fraction`으로 decode해야 함을 명시;
4. probability exact round-trip 범위를 benchmark domain과 SQLite 64-bit 초과 값으로 정밀화하고 CPython global integer-string safety setting은 변경하지 않도록 명시.

이 correction은 이미 adjudication된 선택을 명료화한 것이다. Stage 1/2를 재설계하거나 persistence representation을 바꾸거나 새 framework를 추가하지 않는다.

# 50. Freeze 기록

Revision 2는 Pre-Stage 3 구현을 위한 frozen specification이다.

Freeze 근거:

```text
검토한 main commit:
f11bc199e093e54cdda1d258d5977fe4cb14a261

delta-review candidate SPEC SHA-256:
0d138ca2cce23dc2a73eb8ea6903e0be9ca1b61584beb63e8e587d79d5ab2afd

독립 delta-review 판정:
YES / YES

남은 implementation blocker:
none
```

위 candidate SPEC hash는 두 reviewer가 실제로 검토한 pre-freeze 문서를 식별한다. 현재 frozen 파일은 §49에 요약한 non-blocking correction과 status/freeze-record update만 추가 반영한 문서다.

# 51. Revision 2 decision 요약

Revision 2에서 동결한 design decision:

```text
SQLite persistence
raw events + derived summaries
fixed reproducible paired boards
EXPERT_GENERAL_V1 prefix stream
seed = game_index
first click fixed at (0,0)
exclude first-click cell only
Generator V1 reference runtime = CPython 3.12.14
frozen binary encoding을 가진 SHA-256 canonical layout fingerprint
executed semantic action마다 one ActionEvent
first OPEN = event 0, inference 아님
exact Python Fraction probabilities
canonical exact SQLite rational TEXT "n/d"
committed WIN/LOSS game마다 one GameRecord
one completed game = one DB transaction
processed_games retained intentionally
benchmark_set_id required
fresh Engine per game initially
technical failure fail-fast
best-effort FAILED run-status persistence
Stage 2 baseline accept_guesses=True
run_simple explicit initial_open + optional observer
action_events WITHOUT ROWID
initial WAL + synchronous=FULL
official baseline clean non-ignored Git working tree provenance requirement
explicit paired-prefix coverage validation
PyQtGraph later for in-app graphs
```

Intentional v1 deferral:

```text
custom stable PRNG/sampling implementation
parallelism / multi-process writer
resume/recovery implementation
10k pilot이 정당화하기 전 chunked/non-prefix run range
archive/sharding
per-game technical ERROR row / termination_reason / error_code
record_replay=False optimization
derived REAL probability column
EXPLAIN evidence 없는 extra action-table index
대규모 debug snapshot/full candidate list
deep cancellation inside probability solver
Stage 3 physical timing/planner telemetry
generic research-platform abstraction
```

Pilot evidence가 요구할 때만 재검토할 항목:

```text
100k operational chunking/resume
synchronous=NORMAL
additional indexes
Engine reuse
duplicate static analysis 제거
replay suppression
```

Revision 2는 독립 delta review를 완료했으며 구현용으로 frozen 상태다. 구현 또는 pilot evidence가 concrete defect를 드러내지 않는 한 추가 architecture review는 필요하지 않다.

---

# 52. 최종 원칙

이 인프라의 목적은 telemetry의 양을 최대화하는 것이 아니다.

다음 문장을 방어 가능하게 만드는 것이 목적이다.

> Stage 2와 이후 단계는 재현 가능한 paired board에서, 명시적으로 기록된 solver policy 아래 평가되었고, solver에게 hidden information을 제공하지 않으면서 보고된 통계를 raw event 수준에서 재구성할 수 있는 충분한 증거를 남겼다.

이 문장을 지지하는 데 필요하지 않은 것은 별도의 근거가 있을 때만 추가한다.
