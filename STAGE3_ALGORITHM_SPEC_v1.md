# Stage-3 Algorithm Specification
## v1 — FROZEN

### 0. Status

이 문서는 **Stage-3 Algorithm Specification v1의 동결된 알고리즘 명세**다.

**최종 판정:** `A. STAGE-3 ALGORITHM SPECIFICATION v1 — FROZEN`  
**판정일:** 2026-10-06  
**추가 algorithm finding:** BLOCKER 0 / REQUIRED BEFORE FREEZE 0 / OPTIONAL 0  
**심사 원본:** `STAGE3_ALGORITHM_SPEC_v1_FREEZE_CANDIDATE_r1.md`  
**심사 원본 SHA-256:** `88d5a6e0066e3bdc68327b58ea7bb147a16f7671158645121356764f58cdbcdd`

본 승격본은 심사 원본의 상태·승격 기록만 변경했다. 알고리즘 의미는 변경하지 않았다. §33의 통합 설계·구현·acceptance 작업은 완료 선언이 아니라 다음 단계의 요구사항으로 유지한다.

Draft v1.1 이후 다음 설계 gate와 evidence가 해소되었다.

- Stage-3 physical Model C calibration 완료 및 integer timing table 동결
- expert replay validation V1.1 완료 — `PASS WITH LIMITATION`
- E-FIRST vs L-FIRST paired policy pilot 완료
- Stage-2 probability / win-rate 독립 audit 완료 — baseline reopen 불필요

현재 문서의 algorithm semantics는 동결되었다.
Source/spec consistency audit와 최종 freeze review는 BLOCKER/REQUIRED 0으로 종료되었다.
추가 algorithm semantic change 없이 §33의 implementation 단계로 진행한다.

Stage 2의 기존 semantics와 accepted 100k baseline은 Stage 3 구현 편의를 위해
변경하지 않는다.

Experimental pilot code는 evidence prototype일 뿐 production implementation으로
자동 승격되지 않는다. Production Stage-3 구현은 이 문서를 기준으로 별도 review를
거쳐야 한다.

---

## 1. Objective

Stage 3는 Python 코드 자체를 빠르게 실행하는 단계가 아니다.

목적은 Stage-2의 risk discipline을 보존하면서 행동의 선택과 순서를 바꾸어 **modeled physical Minesweeper play time**을 줄이는 것이다.

플레이어 모델은:

- 이상적이지만 인간이 물리적으로 수행 가능한 플레이어
- 현실적인 cursor movement와 input timing을 가짐
- 인간의 실수, 망설임, 피로, random jitter는 모델링하지 않음

으로 정의한다.

Stage 3에서 최종 목적은 **speed**다.

Efficiency는 speed를 향상시키는 경우 사용할 수 있는 수단일 뿐, 그 자체가 Stage-3 목적함수는 아니다.

따라서 더 많은 semantic actions를 사용하더라도 modeled physical time이 더 짧다면 Stage 3에서는 허용될 수 있다.

---

## 2. Information Boundary

Stage-3 V1 planner가 행동을 결정할 때 사용할 수 있는 정보는 공개정보와 V1이
명시적으로 도입한 physical state뿐이다.

허용 decision input은 다음으로 고정한다.

- current public observation
- public total mine count
- current cursor target cell
- frozen integer physical timing table / validated profile identity
- Stage-3 specification version

V1은 past action history를 별도 planner state로 요구하지 않는다.
필요한 physical history는 마지막 action target으로 표현되는 current cursor에 이미
요약되어 있다.

다음은 decision oracle 또는 admissibility 검증에 사용할 수 없다.

- hidden mine layout
- answer-sensitive `BoardSnapshot` mine/adjacency data
- board fingerprint를 이용한 정답 추론
- answer-derived 3BV / Ops / completed-3BV information
- hidden truth에 민감한 engine counter/snapshot field
- future terminal result
- replay의 future action
- evaluator-only information
- FLAG/CHORD가 실제로 안전한지 hidden layout으로 사후 확인한 값을 다시 planner에 입력하는 것

Hidden layout은 engine execution, benchmark identity validation, replay reconstruction,
post-hoc evaluation처럼 **solver decision과 분리된 경계**에서만 사용할 수 있다.

## 3. Stage-2 Inference Reuse

Stage 3는 새로운 주력 지뢰추론 알고리즘을 만드는 단계가 아니다.

현재 Stage-2 inference의 큰 계층을 그대로 유지한다.

### Local path

열린 숫자 `N`, 주변 FLAG 수 `F`, 주변 HIDDEN set `H`를 사용한다.

`N-F == 0`이면 `H`는 safe.

`N-F == len(H)`이면 `H`는 mine.

같은 observation에서 inferred fact를 다른 constraint로 재전파하거나 subset inference를 수행하지 않는다.

### Probability path

Local deterministic certainty가 없을 때만 exact complete-board probability를 계산한다.

전체 공개 total mine count까지 사용해 complete-board world를 정확하게 센다.

100% mine, 0% safe, 또는 그 외 exact probability를 `Fraction` 의미로 유지한다.

Stage 3는 **local certainty가 있는데 단지 더 좋은 route를 찾기 위해 probability를 추가 계산하지 않는다.**

---

## 4. Risk Preservation

Risk는 speed와 가중합하지 않는다.

즉 다음과 같은 목적함수를 사용하지 않는다.

\[
time+\lambda risk
\]

Risk는 먼저 admissible candidate를 제한하는 hard constraint다.

### Certainty available

현재 `analyze_position()`이 LOCAL deterministic evidence를 반환하면 Stage 3는
그 **같은 LOCAL inference result** 안의 current-certain safe/mine facts를
speed planning에 사용할 수 있다.

Stage 2의 단일-move selector처럼 반드시 FLAG를 OPEN보다 먼저 실행할 필요는 없다.
Stage 3의 목적 자체가 certainty action의 순서와 route를 바꾸는 것이기 때문이다.

그러나 다음 경계는 유지한다.

- local certainty가 존재하는 동안 speed를 이유로 exact probability path를 강제로 호출하지 않는다.
- current-certain mine만 FLAG할 수 있다.
- current-certain safe만 certainty OPEN할 수 있다.
- certainty가 남아 있는데 uncertain guess로 건너뛰지 않는다.
- V1은 logical-known-mine state를 별도로 유지하지 않는다.
- UNFLAG를 planning action으로 사용하지 않는다.

따라서 reveal plan이 더 이상 없고 certain mine만 남으면 §22의 FLAG fallback이
반복되어 필요한 physical FLAG를 실제 observation에 반영한다. 이 deliberate
V1 제약은 Stage-2의 local/probability boundary를 보존하기 위한 것이다.

LOCAL이 비어 실제 probability path에 도달한 경우, `ProbabilityResult`에서 확인된
모든 0% safe / 100% mine fact를 current global certainty evidence로 사용할 수 있다.
이 경우에도 certainty가 존재하면 uncertain guess를 실행하지 않는다.

### Guess required

Local certainty가 없고 exact probability path에도 0%/100% certainty가 없어
실제 guess가 필요하면 V1은 **Stage-2 selector의 guess를 그대로 실행한다.**

Probability minimum의 정의역은 frontier만이 아니라
`ProbabilityResult.probabilities`에 포함된 **모든 selectable HIDDEN cell**이다.

\[
p_{\min}=\min_{c\in HIDDEN}p(c)
\]

Stage-2 selector가:

\[
p(c)=p_{\min}
\]

인 칸들 중 `(y,x)` 최소 좌표를 선택하므로 Stage-3 V1도 그 exact OPEN coordinate를
그대로 사용한다.

즉 V1에서는 cursor가 더 가까워도 다른 equal-risk guess로 바꾸지 않는다.

이 선택은 Stage-3 V1 비교에서 guess-policy 변화와 speed-planning 효과가 섞이지
않게 하기 위한 control이다. Nearest minimum-risk guess는 P0 extension으로
별도 보관한다.

Stage-3 V1은 decision-local minimum-risk discipline을 보존한다. 최종 benchmark에서는
Stage-2와 Stage-3의 whole-prefix outcomes를 반드시 함께 보고하며, outcome이 같은지
검증 결과 없이 가정하지 않는다.

## 5. Certainty Candidate Pool

Stage 3는 Stage-2 selector가 고른 단 하나의 move만 받아들이는 것이 아니라, 해당 inference call에서 이미 계산된 전체 certainty evidence를 speed planning에 사용할 수 있다.

예를 들어 local inference 결과가:

`certain mines = {A,B}`  
`certain safe = {C,D,E}`

라면 Stage 3는 A~E 전체를 candidate generation의 재료로 사용할 수 있다.

이는 stronger inference가 아니라 **같은 inference result를 사용하는 다른 selection policy**다.

마찬가지로 probability path까지 실제로 도달한 경우 exact probability result 안의 모든 0%/100% certainty를 사용할 수 있다.

단, local certainty가 존재하는데 global certainty를 더 찾기 위해 probability path를 강제로 호출하지 않는다.

---

## 6. Current Evidence vs Virtual Planning Evidence

Stage 3는 반드시 두 종류의 evidence를 구별한다.

### Current execution evidence

현재 실제 public observation에서 Stage-2 inference가 확인한 사실.

이 evidence는 실제 first action의 실행 근거가 될 수 있다.

### Virtual planning evidence

현재 admissible certainty action을 가상으로 적용했을 때, 같은 공개정보 규칙이 미래 hypothetical public state에서 만들어내는 결과.

이 evidence는 **현재 admissible first action들의 순서를 평가하는 데만 사용한다.**

Virtual state에서 새로 얻은 fact는 아직 실제 실행 권한을 갖지 않는다.

예를 들어:

`FLAG A → virtual state에서 B가 safe`

라고 계산되더라도 현재 observation에서 B를 바로 OPEN하지 않는다.

실제 runtime은 우선 `FLAG A` 하나만 수행한 뒤 fresh real observation에서 B의 safety를 다시 확인한다.

핵심 원칙:

**planning evidence ≠ execution evidence**

---

## 7. Allowed Virtual Lookahead

Stage-3 V1의 virtual setup에는 **현재 inference layer에서 이미 certain mine인 cell만** FLAG로 사용할 수 있다.

Current-certain FLAG를 가상 적용한 결과:

- `N-F == 0`이 새롭게 성립하여 safe OPEN이 unlock될 수 있음
- clue의 실제 flag count가 number와 같아져 safe CHORD가 unlock될 수 있음

을 평가할 수 있다.

반면 다음과 같은 재귀적 hypothetical inference search는 하지 않는다.

`virtual FLAG → 새로운 mine 추론 → 그 mine도 virtual FLAG → ...`

현재 direct `N-F` 규칙에서는 known mine FLAG가 전에 없던 `remaining == hidden count` mine certainty를 새로 만들 수 없으므로, 이러한 mine-recursion은 V1 핵심에 필요하지 않다.

또한 **virtual state에서 exact probability를 다시 계산하지 않는다.**

즉 hypothetical probability search tree를 만들지 않는다.

---

## 8. Planning Horizon

Stage 3의 planning horizon은 **현재 공개정보에서 deterministic하게 평가할 수 있는 첫 safe reveal까지**다.

대표 plan은:

`OPEN`

`CHORD`

`FLAG(s) → OPEN`

`FLAG(s) → CHORD`

형태다.

FLAG는 새 hidden clue를 reveal하지 않으므로 first reveal 이전 setup에 포함될 수 있다.

OPEN 또는 CHORD가 실행되면 새로운 hidden clue information이 공개될 수 있으므로 그 지점에서 plan을 종료한다.

따라서:

**first reveal = replanning boundary**

다.

여러 safe OPEN이 이미 있더라도:

`OPEN A → OPEN B → OPEN C`

전체를 하나의 고정 multi-reveal plan으로 실행하지 않는다.

첫 OPEN 후 opening, 새로운 certainty, 새로운 CHORD 또는 terminal state가 생길 수 있기 때문이다.

---

## 9. Think Multiple Actions, Execute One

Planner는 여러 action으로 이루어진 plan을 평가할 수 있지만 runtime에서 실제로 commit하는 것은 항상 첫 physical action 하나뿐이다.

예:

`FLAG A → FLAG B → CHORD C`

가 best plan이라도 실제 실행은:

`FLAG A`

하나다.

이후:

`engine execution → fresh public observation → cursor update → complete replan`

을 수행한다.

Pending multi-action queue를 Stage-3 decision state에 두지 않는다.

---

## 10. OPEN Candidate Semantics

현재 certain-safe HIDDEN cell은 direct OPEN candidate가 될 수 있다.

Stage-3 V1에서 OPEN의 guaranteed reveal count는 항상:

\[
R=1
\]

이다.

실제 OPEN 결과 hidden cell이 0이어서 flood opening이 발생할 수 있지만, hidden clue 값을 보기 전에는 그 추가 reveal을 plan score에 포함하지 않는다.

따라서 R은 realized opening size가 아니라:

> 행동하기 전에 현재 공개정보만으로 보장할 수 있는 직접 safe reveal 수

를 의미한다.

Future hidden clue value를 추론해서 opening size를 예측하는 기능은 V1에 넣지 않는다.

---

## 11. CHORD Candidate Semantics

CHORD는 Stage-3의 정식 action candidate다.

V1의 CHORD target은 다음 조건을 모두 만족해야 한다.

- target은 이미 열린 숫자 cell
- clue number `N`은 `1..8`
- 실제 state 또는 current-certain FLAG virtual setup 이후 주변 physical flag count가 `N`
- non-flag HIDDEN neighbor가 최소 한 칸 존재
- Stage-2의 solver-generated flag-as-mine contract 아래 그 non-flag HIDDEN neighbors가 safe

따라서 terminal CHORD의:

\[
R>0
\]

이어야 한다.

CHORD의 R은 해당 action이 현재 공개정보에서 확실하게 직접 열 non-flagged hidden
safe neighbor의 수다.

그중 0 cell이 포함되어 flood opening이 발생하더라도 추가 flood reveal은 R에
미리 포함하지 않는다.

Safe CHORD라는 표현은 hidden answer board를 확인했다는 뜻이 아니다.
실행 admissibility는 current public evidence와 solver-generated FLAG state만으로
판정한다. Hidden layout, counter snapshot, answer-derived metric으로 CHORD safety를
검증해서는 안 된다.

V1 physical model은 canonical CHORD를 **single target input**으로 모델링하며,
UI의 left-click chord mode에 해당하는 common input cost를 사용한다.
BOTH_CLICK 등의 별도 gesture cost는 V1 범위 밖이다.

## 12. Candidate Generation

Current certainty evidence는 §5의 rule로 얻는다.

- LOCAL decision이면 `deterministic_result`의 safe/mine pool만 사용한다.
- 실제로 probability path에 도달한 decision이면 `ProbabilityResult`의 0%/100% pool을 사용한다.
- LOCAL certainty가 존재할 때 더 많은 global fact를 얻기 위해 probability를 호출하지 않는다.

Candidate generation은 다음처럼 고정한다.

### Direct safe OPEN

각 current-certain safe HIDDEN cell마다:

`OPEN(cell)`

을 생성하며 `R=1`이다.

### Direct safe CHORD

각 positive revealed clue에 대해 현재 physical flags만으로 clue가 이미 만족되고
hidden non-flag neighbor가 남아 있으면:

`CHORD(clue)`

를 생성한다.

R은 직접 열리는 hidden non-flag neighbor 수다.

### Current-certain FLAG setup

각 clue constraint `C`에 대해:

```text
setup = C.hidden_cells ∩ current_certain_mines
remaining = C.hidden_cells - setup
```

로 둔다.

다음이 모두 참일 때만 그 clue용 setup을 생성한다.

```text
len(setup) == C.remaining_mines
remaining is not empty
```

이 setup은 clue를 정확히 만족시켜 `remaining`을 current public logic상 safe로 만든다.

그때:

- positive clue이면 `setup FLAG(s) -> CHORD(clue)`를 생성한다.
- `remaining`의 각 cell마다 `setup FLAG(s) -> OPEN(cell)`을 생성한다.

Proper subset의 setup, unrelated certain-mine detour, virtual state에서 새로 추론한
mine의 재귀적 FLAG는 생성하지 않는다.

동일 physical action sequence가 여러 clue에서 중복 생성되면 하나로 deduplicate한다.

### Exact local routing

Setup FLAG가 있을 경우 current cursor에서 모든 setup FLAG를 거쳐 terminal
OPEN/CHORD에 도달하는 최소 modeled-time route를 정확히 구한다.

V1은 local required set에 대해 Held-Karp dynamic programming을 사용한다.

Reveal 가능한 하나의 clue에는 terminal reveal cell이 최소 하나 남아야 하므로
setup mine 수는 구조적으로 최대 7개다. 이는 임의 candidate cap이 아니다.

동일 route cost이면 setup coordinate sequence의 `(y,x)` lexicographic order를 사용한다.

Candidate generation은 board 전체 certain FLAG permutation을 탐색하지 않는다.
Goal-driven local setup만 생성한다.

## 13. Cursor State

Stage-3 physical state에는 current cursor target cell이 포함된다.

각 action 이후 cursor는 해당 action target cell center에 남는 것으로 모델링한다.

OPEN flood fill이나 CHORD로 여러 cell이 열려도 cursor는 이동하지 않는다.

따라서:

`OPEN(x,y) → cursor=(x,y)`

`FLAG(x,y) → cursor=(x,y)`

`CHORD(x,y) → cursor=(x,y)`

다.

---

## 14. Canonical First Action Boundary

Primary benchmark의 first click은 기존 frozen policy에 따라 `(0,0)` OPEN으로 고정된다.

Stage-3 planner가 첫 action을 새로 선택하지 않는다.

Canonical modeled physical-time benchmark에서는 첫 OPEN 직전에 cursor가 `(0,0)` cell center에 이미 위치했다고 가정한다.

따라서 first OPEN의 displacement는 `(dx,dy)=(0,0)`이고 frozen timing table의:

```text
T[0][0] = 126005 us
```

가 physical input cost로 포함된다.

첫 OPEN 완료 후 cursor는 `(0,0)`에 남고, fresh observation을 받은 뒤 Stage-3 planning이 시작된다.

Pre-board cursor movement는 primary solver comparison에서 제외한다.

---

## 15. Terminal Boundary

Modeled physical play time은 canonical initial OPEN의 physical input부터 game을 WON 또는 LOST로 만드는 마지막 physical input 완료까지 포함한다.

Engine이 승리 시 자동으로 수행하는 remaining-mine flagging과 같이 인간의 별도 input이 아닌 내부 상태 변경에는 physical action cost를 추가하지 않는다.

---

## 16. Physical-Time Model

Stage-3 V1 production policy는 calibration 식을 runtime에서 다시 계산하지 않는다.

Authoritative planner cost는 frozen physical profile의 **30×16 integer timing table**이다.

```text
model_id            = overlap_floor_log2_distance_v1
timing_tick_unit    = 1_us
table_order         = dx_major_dy_minor
table_dimensions    = [30, 16]

physical profile SHA-256
= 52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b

timing table SHA-256
= 7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b
```

Action target A에서 B로 이동해 B에 input을 완료하는 cost는:

\[
T[|\Delta x|][|\Delta y|]
\]

의 integer microseconds다.

Calibration provenance의 continuous Model C는:

\[
T_{\mu s}(dx,dy)=
\max\left(
c_{\mu s},
k_{\mu s}\log_2\left(1+\sqrt{dx^2+dy^2}\right)
\right)
\]

이고 frozen fit은:

```text
c_us = 126004.7
k_us = 113948.22229792871759145720547680405050991560898536508405341934986759339499353944
```

이다.

그러나 planner는 이 식이나 `c_us`, `k_us`를 읽어 재계산하지 않는다.
Profile에 저장된 integer table만 authoritative input으로 사용한다.

대표 timing ticks:

```text
T(0,0)   = 126005 us
T(1,0)   = 126005 us
T(1,1)   = 144891 us
T(3,0)   = 227896 us
T(4,3)   = 294552 us
T(8,6)   = 394196 us
T(10,0)  = 394196 us
T(20,10) = 518010 us
T(29,15) = 578005 us
```

`T(0,0) == T(1,0)`은 fitted floor regime의 의도된 결과다.

Plan latency:

\[
L(P)=\sum_i T_i
\]

는 current cursor에서 terminal reveal input 완료까지의 integer microsecond 합이다.

V1에서는 OPEN / FLAG / CHORD 모두 같은 timing table을 사용한다.

```text
c_OPEN = c_FLAG = c_CHORD
```

에 해당하는 common-cost model이다. Action-specific timing은 P1 extension이다.

Routing objective 또한 Euclidean distance 합이 아니라 **이 integer timing-table cost의 합**이다.

## 17. Cell Size

Uniform square grid에서 pixel movement distance와 target width가 같은 비율로 scaling되므로 normalized \(D/W\)에서는 cell size가 직접 정책값에서 소거될 수 있다.

그러나 cell size metadata를 제거하지 않는다.

KEEP 이유:

- calibration provenance
- 실제 UI/pixel validation
- effective target-width 확장 가능성

현재 V1 policy에서 직접 decision variable이 아닐 수 있지만 calibration information으로 유지한다.

---

## 18. Plan Metrics

First-reveal plan \(P\)마다 다음을 계산한다.

### Latency

\[
L(P)
\]

현재 cursor에서 terminal OPEN 또는 CHORD가 완료될 때까지 modeled physical time.

### Guaranteed reveal count

\[
R(P)
\]

현재 공개정보만으로 terminal reveal이 확실하게 직접 여는 safe hidden cell 수.

FLAG는 R에 포함하지 않는다.

Flood/opening expansion은 R에 포함하지 않는다.

### Guaranteed reveal efficiency

\[
E(P)=\frac{L(P)}{R(P)}
\]

낮을수록 modeled time per guaranteed safe reveal이 좋다.

E는 전체 미래 게임시간의 수학적 optimality를 보장하는 값이 아니다.

Stage-3 V1에서 사용할 **local speed heuristic**이다.

---

## 19. Dominance

Plan A와 B에서:

\[
L_A\le L_B
\]

이고:

\[
R_A\ge R_B
\]

이며 최소 하나가 strict하면 B는 dominated plan으로 제거할 수 있다.

동일 `(L,R)`인 두 plan은 서로를 dominance 근거로 제거하지 않는다. 단, 제3의 plan에 strict하게 dominated되면 둘 다 제거할 수 있다.

현재 E-FIRST/L-FIRST ordering에서는 이 dominance rule이 최종 winner를 바꾸지 않는
semantics-preserving structural pruning임을 사용한다.

Draft review 당시에는 objective 결과에 영향을 주지 않는다는 이유로 제거 후보였으나,
10k pilot에서 candidate survivor 수를 크게 줄이는 실제 구조적 효과가 확인되었다.
따라서 V1은 이를 **KEEP**한다.

이 pruning은 새로운 heuristic objective가 아니며, action count나 임의 score를
도입하지 않는다.

## 20. Frozen Reveal-Plan Selection Policy

Stage-3 V1의 reveal-plan primary policy는 **E-FIRST**다.

Selection hierarchy는 다음 순서로 고정한다.

1. 현재 risk/certainty contract에 맞는 admissible candidate만 생성한다.
2. §19 dominance pruning을 적용한다.
3. 다음 guaranteed reveal efficiency가 exact하게 가장 작은 plan을 남긴다.

\[
E(P)=\frac{L(P)}{R(P)}
\]

E 비교에는 float division을 사용하지 않는다.

Plan A, B는:

\[
L_A R_B \;\mathop{\lessgtr}\; L_B R_A
\]

의 integer cross-product로 exact 비교한다.

4. Exact E tie이면 더 작은 integer `L`을 우선한다.
5. E와 L까지 같으면 다음 deterministic fallback key를 사용한다.

```text
terminal target y
terminal target x
terminal action rank   (OPEN=0, FLAG=1, CHORD=2)
setup FLAG route coordinate sequence in lexicographic (y,x) order
```

Action count는 tie objective로 사용하지 않는다.

Non-zero E-equivalence tolerance는 사용하지 않는다.

## 21. E / L Policy Gate — CLOSED

E-FIRST와 L-FIRST는 production implementation 전에 별도 EXPERIMENTAL harness에서
paired total modeled whole-game time으로 비교했다.

Primary evidence corpus:

```text
EXPERT_GENERAL_V1
game_index == seed
range = [100000, 110000)
games = 10,000
status = VALID
```

Hard-gate 결과:

```text
paired E/L guess checkpoints = 37,135
E/L checkpoint mismatch      = 0
E/L final-result mismatch    = 0

Stage-2 reference cross-check = first 1,000 games
reference guess checkpoints   = 3,685
Stage-2 reference mismatch    = 0

E-FIRST outcomes = 3,777 WON / 6,223 LOST
L-FIRST outcomes = 3,777 WON / 6,223 LOST
```

Primary metric은 predicted plan L 합이 아니라 **실제로 실행된 physical action stream의
whole-game modeled time**이었다.

```text
E-FIRST total = 249,438.903381 s
L-FIRST total = 263,685.929334 s

E - L = -14,247.025953 s
L-FIRST 대비 E-FIRST = 5.403028515% 감소

paired per-game:
E faster = 7,053
L faster =   124
tie      = 2,823
```

Actual physical actions:

```text
E-FIRST = 1,380,247
L-FIRST = 1,563,604
```

E-FIRST는 first reveal latency 자체는 더 길게 선택하는 경우가 많았다.

```text
E-FIRST longer-L choices = 379,555
chosen-plan L:
    E P50 = 144,891 us
    E P95 = 512,117 us
    E P99 = 657,840 us

    L P50 = 126,005 us
    L P95 = 432,614 us
    L P99 = 567,884 us
```

그럼에도 whole-game total이 명확히 감소했으므로 별도 latency-protection cap이나
E tolerance는 도입하지 않는다.

Revalidation:

```text
actual physical actions revalidated = 2,943,851 PASS
predicted plans cost-checked         = 5,104,340 PASS
focused tests                        = 24 PASS
runtime failure                      = 0
```

따라서:

**Gate A — CLOSED: E-FIRST selected.**

**Gate B — CLOSED: exact E, zero non-zero tolerance.**

L-FIRST는 rejected alternative로 evidence와 함께 보존하되 V1 production policy로
구현하지 않는다.

## 22. FLAG-Only Fallback

Current certainty evidence는 존재하지만 §12의 first-reveal plan을 만들 수 없는 경우:

> current cursor에서 integer timing-table action cost가 가장 작은 current-certain FLAG

를 한 개 실행한다.

동일 cost tie이면 `(y,x)` 최소를 사용한다.

FLAG fallback도 실제로 **한 action만** commit하고 fresh public observation으로
완전히 replan한다.

이 fallback은 V1에서 중요한 compatibility 제약이다.

표시되지 않은 local certain mine은 local certainty로 계속 남아 probability path를
막을 수 있으므로, reveal plan으로 처리되지 않는 certain mine은 필요할 때 실제
FLAG로 observation에 반영해야 한다.

즉 V1은:

```text
logical known mine != physical flag
```

라는 별도 retained state를 도입하지 않는다.

Known-mine / no-flag execution은 P0 extension으로 DEFER한다.

“이 FLAG가 미래에 더 유용할 것 같다”는 speculative potential score는 사용하지 않는다.
Reveal까지 deterministic하게 연결되는 FLAG라면 이미 setup plan으로 평가되어야 한다.

## 23. Probability Guess Selection

Local certainty가 없고 exact probability path에서도 certainty가 없어 실제 guess가
필요하면 Stage-3 V1은 **frozen Stage-2 decision.move를 그대로 실행한다.**

Stage-2 probability selector는:

- `ProbabilityResult.probabilities`의 모든 HIDDEN cell을 대상으로
- exact minimum mine probability를 찾고
- equal minimum-risk OPEN 중 `(y,x)` 최소를 선택한다.

Stage-3 V1은 이 coordinate를 cursor distance로 다시 선택하지 않는다.

Guess OPEN은 unknown reveal이므로 그 너머의 virtual plan을 만들지 않는다.

Guess의 physical cost는 current cursor에서 Stage-2-selected target까지 frozen timing
table로 계산해 whole-game modeled time에 포함한다.

Nearest minimum-risk guess는 risk floor 자체는 유지하지만 fixed-board outcomes와
후속 trajectory를 바꿀 수 있으므로 P0 extension으로 별도 평가한다.

Minimum risk보다 높은 칸을 speed 때문에 허용하는 risk-speed policy는 V1 범위 밖이다.

## 24. Determinism

Stage-3 V1 policy는 다음 함수로 결정된다고 본다.

```text
f(
    current public observation,
    public total mine count,
    current cursor cell,
    frozen integer timing table,
    Stage-3 specification version
)
```

V1 decision input에는 retained solver fact나 action-history-dependent hidden state가 없다.

Cursor는 마지막 실제 physical action target이며 canonical initial value는 `(0,0)`이다.

동일한 위 입력에는 항상 같은 action을 반환해야 한다.

따라서 official policy는 elapsed wall-clock time, CPU speed, planner timeout으로
탐색 결과를 바꾸지 않는다.

Candidate generation, exact routing, dominance, E/L comparison, FLAG fallback,
guess selection, final tie-break 모두 deterministic이어야 한다.

## 25. Numeric Determinism — CLOSED

Numeric determinism contract는 다음처럼 동결한다.

- physical action cost: frozen timing table의 positive integer microseconds
- plan L: integer sum
- reveal R: positive integer
- E ordering: integer cross-product
- E tie: exact equality only
- non-zero epsilon/tolerance: 없음
- runtime `log2`, fitted float/Decimal parameter 재계산: 없음

Physical profile whole-file SHA와 separately encoded timing-table SHA를 시작 시 검증해야 한다.

따라서 calibration fitting의 floating/Decimal 계산은 provenance 생성 단계에만 존재하고,
official Stage-3 action selection에는 들어오지 않는다.

**Gate C — CLOSED.**

## 26. Compute-Time Policy

Modeled physical play time과 Python decision/planning compute time은 서로 다른 metric이다.

Official Stage-3 action policy에서 wall-clock timeout으로 action을 바꾸지 않는다.

임의 candidate-count hard cap도 V1 policy에 넣지 않는다. Local setup은 구조적으로
최대 7 FLAG이고 exact routing은 bounded하다.

E/L evidence pilot은 reproducible policy evidence를 위해 Python compute timing을
의도적으로 primary artifact에서 제외했으므로, 그 pilot 결과로 production planner의
compute performance를 주장하지 않는다.

Production implementation 이후 controlled pilot에서 적어도 다음을 별도로 측정한다.

- median
- P90 / P95 / P99
- maximum
- probability analysis time
- planner-only overhead
- exact routing / candidate generation tail

실제 bottleneck evidence가 생기면 먼저 deterministic structural pruning,
memoization 또는 algorithmic improvement를 검토한다.

Compute-time 최적화가 선택 action semantics를 바꾸어서는 안 된다.

Modeled physical time과 compute time을 하나의 weighted objective로 합치지 않는다.

## 27. Calibration — CLOSED

Stage-3 V1 physical calibration은 완료되었고 Model C를 동결한다.

Calibration은 controlled Minesweeper-like grid에서 reference operator의
START press → TARGET press physical timing을 수집했다.

Frozen protocol의 주요 identity:

```text
grid       = 30 × 16
cell size  = 28 logical px
protocol   = STAGE3_CALIBRATION_V1
model id   = overlap_floor_log2_distance_v1
```

Accepted calibration data는 warmup 24회와 official 384회, 총 408 accepted attempt를 포함한다.
Objective invalid attempt 73회도 삭제하지 않고 provenance에 별도 기록되었다.

Final Model C는 §16의 overlap-floor log-distance model이다.

Production planner는 fitted parameters를 다시 fit하거나 식으로 table을 생성하지 않는다.
`calibration/stage3_physical_profile_v1.json`의 frozen integer timing table과 hashes를
검증한 뒤 그대로 사용한다.

이 profile은 한 reference operator의 V1 physical model이다.

다음을 주장하지 않는다.

- 인간 전체 population model
- elite player의 exact lower bound
- 모든 input device/platform에서 동일한 timing

Action-specific cost, anisotropy, CPS/burst는 evidence-triggered extension으로 남긴다.

**Gate D — CLOSED.**

## 28. Expert Replay Validation — CLOSED WITH LIMITATION

Expert replay는 calibration fit의 ground truth가 아니라 frozen Model C의 realism
validation evidence로 사용했다.

Final V1.1 corpus:

```text
records reconstructed = 30 / 30
transitions           = 5,035
STANDARD games        = 20
NO_FLAG games         = 10
```

Replay의 P는 재구성한 연속 input target 사이의 press-to-press transition에 frozen timing table을 적용한 합이다. 첫 input 이전 구간과 첫 input 자체의 cost는 포함하지 않는다. H는 replay metadata의 displayed human completion time이다. 아래 aggregate P/H는 per-game ratio의 평균이 아니라 `sum(P) / sum(H)`이며, §14–15 solver benchmark의 첫 input을 포함하는 modeled whole-game total과 측정 경계를 구분한다.

Aggregate press-model / human-time ratio:

```text
overall P/H = 76.175%
30 / 30 games have modeled P < human H
```

Transition-level classification에는 MODEL_BELOW / ambiguous / MODEL_ABOVE가 모두 존재했고,
MODEL_ABOVE가 특히 early transitions에 집중되는 현상도 관찰되었다.

이 원인을 특정 행동 메커니즘으로 식별하지 못했으므로 replay 결과를 이용해
`c/k/table`을 재fit하거나 임의 보정하지 않는다.

Final disposition:

**Replay Validation V1.1 — PASS WITH LIMITATION**

**Physical Model C — KEEP / FROZEN**

따라서 V1에서는:

- profile/table refit 없음
- action-specific costs 추가 없음
- direction anisotropy 추가 없음
- CPS/burst constraint 추가 없음

으로 유지한다.

## 29. CPS / Burst Gate — DEFER

Frozen timing table에는 각 physical input마다 positive floor cost가 있으므로
무한 action rate는 이미 허용되지 않는다.

Calibration과 replay validation은 V1에 별도:

- sustained CPS hard cap
- burst CPS hard cap
- minimum inter-action interval

을 추가해야 한다는 충분한 evidence를 만들지 못했다.

따라서:

**Gate E — CLOSED AS DEFER.**

향후 replay/calibration evidence가 독립 제약의 필요성을 보일 때만 P1 physical-model
extension으로 재검토한다.

## 30. Stage-3 vs Stage-4 Boundary

Stage 3:

> Speed is the objective. Efficiency is an instrument when it improves speed.

Stage 4:

> 행동/클릭 효율 자체를 주 최적화 대상으로 연구한다.

따라서 Stage 3에서 CHORD, FLAG setup, 효율적인 route를 활용하는 이유는 클릭 수 자체를 줄이기 위해서가 아니라 modeled physical time을 줄이기 위해서다.

동일한 modeled speed 결과에서 action count가 더 적다는 이유만으로 Stage-3 tie-break를 주지 않는다.

---

## 31. Explicitly Deferred / Out of Scope for V1

다음은 Stage-3 V1 production algorithm에 넣지 않는다.

### P0 — first extensions after V1

- logical known-mine / no-flag execution
- nearest exact-minimum-risk guess

두 항목 모두 speed-oriented일 수 있으나 V1 비교 경계를 깨끗하게 유지하기 위해
의도적으로 분리한다.

### P1 — physical-model extensions

- action-specific `OPEN / FLAG / CHORD` timing
- direction-dependent / anisotropic movement
- sustained CPS hard limit
- burst CPS hard limit
- explicit minimum inter-action interval

### P2 — larger planning/state extensions

- retained certainty facts across observations
- longer deterministic reveal horizon
- richer guaranteed reveal value
- future hidden clue / opening-value prediction
- virtual exact-probability recursion

### Experimental / other-stage items

- `p_min`보다 높은 위험을 허용하는 risk-speed trade-off
- expected information gain을 primary Stage-3 objective에 혼합
- dead-tile / secondary-safety / 50/50 / BFDA 같은 win-rate-oriented advanced
  guess policy를 Stage-3 V1 speed comparison에 혼합
- Stage-4 action-count/click-efficiency objective
- human mistake, hesitation, fatigue, random jitter

### Unnecessary generic infrastructure

- generic planner framework
- generic TSP framework
- plugin/EventBus/solver registry
- wall-clock-dependent search termination

Exact local Held-Karp routing은 V1에 필요한 bounded implementation이며 generic TSP
framework를 정당화하지 않는다.

## 32. Freeze Gates — RESOLVED

Draft v1.1의 algorithm-policy gates는 다음처럼 판정되었다.

| Gate | Final disposition |
|---|---|
| A — E vs L policy | **CLOSED — E-FIRST** |
| B — E-equivalence | **CLOSED — exact comparison, zero tolerance** |
| C — Numeric determinism | **CLOSED — integer timing table + exact cross-products** |
| D — Calibration | **CLOSED — Physical Model C / frozen profile+table** |
| E — CPS/Burst | **CLOSED AS DEFER — no V1 hard cap** |
| F — Deterministic ties | **CLOSED — exact-route lexicographic tie; reveal E→L→terminal key→setup key; FLAG fallback cost→`(y,x)`; guess frozen Stage-2 `(y,x)`** |
| G — Replay realism validation | **CLOSED — PASS WITH LIMITATION; no refit** |

추가 supporting audit:

```text
Stage-2 Probability / Win-rate Audit
= PROBABILITY CORRECT
= baseline remains valid
= BLOCKER 0 / REQUIRED 0
```

Algorithm 정책과 source/spec consistency에 대한 final freeze review가 완료되었다.
**Algorithm freeze는 CLOSED이며, §33의 구현·통합·acceptance 작업은 다음 단계로 이관한다.**

## 33. After Algorithm Freeze — Implementation / Acceptance Work

Algorithm freeze 이후 implementation seam을 별도로 확정한다.

최소 요구사항은 다음과 같다.

- production Stage-3 planner와 runner 책임을 분리한다.
- planner는 public observation / num_mines / cursor / frozen timing table만 받는다.
- hidden engine/layout/board fingerprint가 planner input으로 들어가지 않는다.
- CHORD가 정식 action이므로 Stage-2 `run_simple`을 무리하게 확장해 재사용하지 않는다.
- Stage-2 production solver semantics는 그대로 둔다.
- experimental E/L harness를 production module로 단순 복사하지 않는다.
- Stage-3 전용 telemetry adapter가 필요하면 Stage-2 adapter의 `(y,x)` self-check를
  억지로 재사용하지 않는다.
- 기존 telemetry/schema를 Stage-3 의미에 맞지 않게 재해석하지 않는다.
- shared benchmark path를 수정하기 전에 작은 accepted Expert prefix에 대한
  Stage-2 semantic-action regression golden을 추가한다.
- accepted Stage-2 100k DB 원본은 immutable하게 유지한다.
- Stage-2↔Stage-3 official comparison은 같은 `EXPERT_GENERAL_V1` board identity를
  paired 검증한다.
- modeled physical time, Python compute time, wall time, action count, game outcome을
  서로 다른 metric으로 보고한다.

Implementation 완료 후에는 최소한 다음 acceptance를 거친다.

```text
source/spec review
focused planner/runner tests
Stage-2 regression tests
hidden-information boundary tests
determinism tests
frozen profile/table hash tests
paired pilot / benchmark
whole-prefix outcome reporting
modeled-time revalidation
```

Codex implementation 후 바로 commit/push하지 않고 review/adjudication을 먼저 수행한다.

## 34. Frozen Specification Claim

이 동결 명세가 정의하는 Stage 3 V1은:

> **Stage-2의 공개정보 기반 risk discipline과 exact guess selector를 보존하면서,
> current certainty evidence의 direct/FLAG-setup OPEN·CHORD plan을 deterministic하게
> 생성하고, frozen cursor-aware integer physical-time model에서
> `E=L/R`을 최소화하여 첫 physical action 하나만 실행한 뒤 fresh observation으로
> 완전히 replan하는 E-FIRST first-reveal receding-horizon speed planner**

다.

Stage 3 V1은 다음을 주장하지 않는다.

- 전체 게임 modeled time의 mathematically global optimum
- Stage 2보다 높은 win rate
- stronger general mine inference
- hidden-answer-aware planning
- 인간 행동 전체의 simulation
- click-count 최소화 자체
- advanced AI guess policy

E-FIRST의 선택 근거는 10,000-game paired development evidence에서 L-FIRST보다
actual action-stream total modeled time이 5.403028515% 낮았다는 것이다.

현재 문서 상태:

`STAGE-3 ALGORITHM SPECIFICATION v1 — FROZEN`

최종 source/spec consistency audit와 freeze adjudication은 BLOCKER 0 / REQUIRED 0으로 종료되었다.
알고리즘 의미를 추가 수정하지 않고 §33에 정의된 implementation 단계로 진행할 수 있다.
