# Stage-3 Algorithm Specification
## Draft v1.1 — REVIEW CANDIDATE

### 0. Status

이 문서는 **Stage 3 최종 동결 명세가 아니다.**

현재까지의 설계 논의와 ChatGPT self-review 1~3차 결과를 통합한 외부 독립 검토용 후보안이다.

Codex와 Claude Code의 독립 리뷰, finding별 실제 코드·테스트 대조, 필요한 pilot/calibration evidence 검토를 거친 뒤에만 다음 상태로 전환할 수 있다.

`STAGE-3 ALGORITHM SPECIFICATION v1 — FROZEN`

Stage 2의 기존 semantics는 Stage 3 구현 편의를 위해 변경하지 않는다.

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

Stage-3 planner가 행동을 결정할 때 사용할 수 있는 정보는 공개정보와 Stage-3가 명시적으로 도입한 physical state뿐이다.

주요 허용 입력은:

- current public observation
- public total mine count
- 이미 실제로 실행된 public action history가 필요할 경우 그 기록
- current cursor position
- frozen physical-model calibration profile

이다.

다음은 decision oracle로 사용할 수 없다.

- hidden mine layout
- answer-sensitive `BoardSnapshot`
- board fingerprint를 이용한 정답 추론
- answer-derived 3BV / Ops
- future terminal result
- evaluator-only information

---

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

현재 inference layer에서 certainty가 있으면 uncertain guess를 실행하지 않는다.

### Guess required

정말 guess가 필요하면:

\[
p_{\min}=\min_c p(c)
\]

를 구하고,

\[
p(c)=p_{\min}
\]

인 OPEN만 Stage-3 후보로 허용한다.

더 가까운 cell이라도:

\[
p(c)>p_{\min}
\]

이면 speed를 이유로 선택하지 않는다.

따라서 Stage-3 V1의 risk preservation은 **decision-local minimum-risk preservation**이다.

이는 Stage 2와 Stage 3가:

- 동일 action trace
- 동일 개별 board outcome
- 동일 aggregate win rate

를 가져야 한다는 뜻은 아니다.

동일 minimum-risk 후보 중 서로 다른 셀을 고르면 개별 fixed board 결과가 달라질 수 있다.

---

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

CHORD candidate는 최소한 다음 조건을 만족해야 한다.

- target은 이미 열린 숫자 cell
- clue number는 의미 있는 CHORD target이어야 함
- 실제/virtual setup 이후 주변 flag count가 clue number와 같음
- 현재 Stage-2 flag-as-mine assumption 하에서 non-flag hidden neighbors가 safe
- 실제로 최소 한 칸 이상의 hidden non-flagged cell을 열 수 있음

즉 terminal CHORD의:

\[
R>0
\]

이어야 한다.

CHORD의 R은 해당 action이 현재 공개정보에서 확실하게 직접 열 non-flagged hidden safe neighbors의 수다.

그중 0 cell이 포함되어 flood opening이 발생하더라도 그 추가 opening은 R에 미리 포함하지 않는다.

Safe CHORD라는 표현은 hidden answer board를 확인했다는 뜻이 아니라 **Stage-2에서 inherited한 flag-as-mine assumption에 상대적인 safety**를 뜻한다.

---

## 12. Candidate Generation

Certainty phase의 주요 candidate category는 다음과 같다.

### Direct reveal

현재 certain-safe cell의 OPEN.

현재 상태에서 바로 가능한 safe CHORD.

### Setup reveal

현재 already-certain mine FLAG(s)를 setup으로 사용하는 `FLAG(s) → OPEN`.

현재 already-certain mine FLAG(s)를 setup으로 사용하는 `FLAG(s) → CHORD`.

Setup 이후 newly-safe OPEN이 여러 개면 각 terminal OPEN은 별도 route candidate가 될 수 있다.

Candidate generation은 board 전체 certain FLAG들의 모든 permutation을 탐색하지 않는다.

CHORD goal은 해당 clue 주변의 local certain mine setup set만 고려한다.

즉 candidate generation은 **goal-driven and local**이어야 한다.

---

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

Canonical modeled physical-time benchmark에서는 첫 OPEN 직전에 cursor가 `(0,0)` cell center에 이미 위치했다고 가정하는 것이 현재 draft의 기준이다.

따라서 첫 OPEN은 movement distance:

\[
d=0
\]

이고 baseline input cost만 발생한다.

첫 OPEN 완료 후 cursor는 `(0,0)`에 남고, fresh observation을 받은 뒤 Stage-3 planning이 시작된다.

Pre-board cursor movement는 primary solver comparison에서 제외한다.

---

## 15. Terminal Boundary

Modeled physical play time은 canonical initial OPEN의 physical input부터 game을 WON 또는 LOST로 만드는 마지막 physical input 완료까지 포함한다.

Engine이 승리 시 자동으로 수행하는 remaining-mine flagging과 같이 인간의 별도 input이 아닌 내부 상태 변경에는 physical action cost를 추가하지 않는다.

---

## 16. Physical-Time Model

현재 V1 Review Candidate의 movement/input 모델은 action \(i\)에 대해:

\[
T_i=c+b\log_2(1+d_i)
\]

를 사용한다.

여기서:

\[
d_i=\sqrt{(\Delta x_i)^2+(\Delta y_i)^2}
\]

이고 distance는 cell-width 단위의 normalized Euclidean distance다.

Plan의 first reveal latency는:

\[
L(P)=\sum_i T_i
\]

다.

Routing 또한 raw Euclidean distance 합이 아니라 **modeled physical time 합**을 최소화해야 한다.

현재 V1에서는:

\[
c_{OPEN}=c_{FLAG}=c_{CHORD}=c
\]

로 둔다.

Action-specific baseline cost는 data가 실제 차이를 보여줄 때만 확장 후보로 검토한다.

---

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

즉:

> 더 늦으면서 동시에 더 적게 보장해서 reveal하는 plan

은 이후 heuristic trade-off 비교 대상에서 제거한다.

이 dominance rule은 E에 의존하지 않는다.

---

## 20. Current Reveal-Plan Selection Policy

현재 Review Candidate의 selection hierarchy는 다음과 같다.

먼저 risk-admissible plan만 남긴다.

그다음 dominated plan을 제거한다.

그 후:

\[
E(P)
\]

가 작은 plan을 우선하는 것을 V1의 주 후보 정책으로 둔다.

E가 **effectively equivalent**한 경우:

\[
L(P)
\]

가 더 작은 plan을 선호한다.

L까지 정책상 동률이면 performance 의미를 추가하지 않는 deterministic fallback을 사용한다.

Action count가 적다는 이유만으로 우선하지 않는다.

그것은 Stage-4 efficiency objective를 Stage 3에 끌어오는 것이기 때문이다.

---

## 21. E / L Policy Gate

이 항목은 아직 **FROZEN되지 않았다.**

다음 반례가 존재한다.

Plan A:

\[
L=50,\quad R=1,\quad E=50
\]

Plan B:

\[
L=400,\quad R=9,\quad E\approx44.4
\]

E-first라면 B를 선택하지만 first new information은 훨씬 늦게 얻는다.

따라서 official freeze 전에 pilot에서 최소한 다음을 확인해야 한다.

- best/second-best E gap 분포
- chosen-plan L distribution
- P50/P95/P99/max reveal latency
- E improvement 때문에 매우 긴 setup을 선택하는 빈도
- E-equivalence tolerance 필요 여부

Arbitrary한 1%, 5%, 10% tolerance를 evidence 없이 먼저 정하지 않는다.

Pilot 결과에 따라 exact E comparison이 충분할 수도 있고, latency protection 정책이 추가로 필요할 수도 있다.

이 항목은 현재 Stage-3 V1의 **가장 중요한 algorithm-policy review gate**다.

---

## 22. FLAG-Only Fallback

Risk-admissible certainty는 존재하지만 first-reveal plan을 만들 수 없는 경우:

> current cursor에서 modeled physical action cost가 가장 작은 certain FLAG

를 실행한다.

동률이면 deterministic fallback을 사용한다.

“이 FLAG가 미래에 더 유용할 것 같다”는 speculative potential score는 V1에 넣지 않는다.

Reveal까지 deterministic하게 연결되는 FLAG라면 이미 setup plan으로 평가되어야 한다.

---

## 23. Probability Guess Selection

Local certainty가 없고 exact probability path에서도 certainty가 없어서 실제 guess가 필요한 경우:

\[
G=\{c\mid p(c)=p_{\min}\}
\]

만 admissible guess pool로 둔다.

Guess OPEN은 그 자체가 unknown reveal이므로 그 너머까지 plan하지 않는다.

따라서 G 안에서는 current cursor에서 modeled physical cost가 가장 작은 OPEN을 선택한다.

동률은 deterministic fallback.

Risk를 조금 높여 speed를 얻는 aggressive risk-speed variant는 Stage-3 V1 범위 밖이다.

---

## 24. Determinism

동일한:

- public observation
- public total mine count
- cursor state
- physical calibration profile
- Stage-3 specification version

이 입력되면 같은 action을 선택해야 한다.

따라서 official policy는 elapsed wall-clock time을 보고 탐색 결과를 바꾸지 않는다.

예:

`50ms 동안 찾은 best candidate를 실행`

같은 정책은 사용하지 않는다.

Computer speed에 따라 다른 action이 나올 수 있기 때문이다.

Candidate generation, routing, comparison, final tie-break 모두 deterministic해야 한다.

---

## 25. Numeric Determinism Gate

Physical model에는 calibration parameter와 `log2()` 기반 값이 들어가므로 Stage-2의 exact Fraction probability와 달리 numeric representation 문제가 생긴다.

Official freeze 전 다음 중 하나와 같은 canonical comparison contract를 정해야 한다.

- canonical fixed precision
- deterministic quantization
- fixed-point / integer time representation
- 명시적으로 재현 가능한 다른 numeric contract

환경별 floating-point의 미세 차이가 행동 선택을 바꾸지 않도록 해야 한다.

이 결정은 E-equivalence policy와 함께 검토한다.

---

## 26. Compute-Time Policy

Modeled physical play time과 Python decision/planning compute time은 서로 다른 metric이다.

Official Stage-3 action policy에서 wall-clock timeout을 사용하지 않는다.

임의의 candidate-count hard cap도 evidence 없이 먼저 넣지 않는다.

현재 local goal structure가 실제로 pathological한 compute cost를 보이는지 pilot에서 측정한다.

Compute performance는 적어도:

- median
- high percentiles
- maximum
- probability path와 planner overhead의 tail

을 별도로 진단한다.

실제 bottleneck evidence가 생기면 먼저 deterministic structural pruning 또는 algorithmic improvement를 검토한다.

Modeled physical time과 compute time을 하나의 weighted objective로 합치지 않는다.

---

## 27. Calibration

\(c,b\)는 임의로 정하지 않는다.

Primary calibration은 목적지가 이미 알려진 controlled pointing/selection experiment를 사용한다.

실제 Minesweeper replay interval을 바로 fit하면:

- clue reading
- decision time
- motor execution

이 섞이므로 physical model calibration과 구분한다.

Official calibration profile은 최소한 다음 provenance를 보존해야 한다.

- protocol/version
- grid/cell configuration
- environment/input-device information
- sample count
- fitted \(c,b\)
- fit/residual evidence

대규모 다인간 연구는 Stage-3 V1 필수조건이 아니다.

---

## 28. Expert Replay Validation

숙련자 replay는 physical model의 primary fitting ground truth가 아니라 **realism validation evidence**로 사용한다.

확인할 수 있는 항목은 예를 들어:

- modeled total time의 현실성
- short/long cursor movement 차이
- 빠른 FLAG/CHORD sequence의 human feasibility
- sustained/burst action rate의 현실성

등이다.

대규모 expert replay dataset은 V1 필수가 아니다.

소수의 적절한 reference replay로 validation을 수행할 수 있다.

---

## 29. CPS / Burst Gate

Positive baseline input cost \(c\) 자체가 무한 action rate를 막기 때문에 V1 초기 모델에는 임의 CPS cap을 바로 추가하지 않는다.

Calibration 및 replay validation 후:

- sustained CPS
- burst CPS
- minimum inter-action interval

등이 실제로 필요하다는 evidence가 있을 경우 다시 검토한다.

현재 상태:

**DEFER — evidence required.**

---

## 30. Stage-3 vs Stage-4 Boundary

Stage 3:

> Speed is the objective. Efficiency is an instrument when it improves speed.

Stage 4:

> 행동/클릭 효율 자체를 주 최적화 대상으로 연구한다.

따라서 Stage 3에서 CHORD, FLAG setup, 효율적인 route를 활용하는 이유는 클릭 수 자체를 줄이기 위해서가 아니라 modeled physical time을 줄이기 위해서다.

동일한 modeled speed 결과에서 action count가 더 적다는 이유만으로 Stage-3 tie-break를 주지 않는다.

---

## 31. Explicitly Deferred / Out of Scope for V1

다음은 Stage-3 V1 핵심에 넣지 않는다.

- minimum-risk보다 높은 위험을 허용하는 risk-speed trade-off
- action-specific \(c_{OPEN},c_{FLAG},c_{CHORD}\)
- direction-dependent movement model
- sustained CPS hard limit
- burst CPS hard limit
- human mistake model
- hesitation
- fatigue
- random jitter
- expected information gain
- future hidden clue prediction
- arbitrary deep game-tree search
- virtual exact-probability recursion
- generic planner framework
- generic TSP framework
- plugin/EventBus/solver registry
- wall-clock-dependent planning termination
- Stage-4 action-count objective

이 항목은 필요성이 실제 evidence로 확인될 때만 재검토한다.

---

## 32. Required Gates Before Freeze

현재 Draft v1.1에서 공식 freeze 전에 반드시 해결하거나 판정해야 할 핵심 open items는 다음이다.

**Gate A — E vs L policy**

E-first가 실제로 excessive reveal latency를 만드는지 pilot evidence로 검토한다.

**Gate B — E-equivalence**

Non-zero tolerance가 실제 필요한지 결정한다.

**Gate C — Numeric determinism**

Physical-time comparison의 canonical numerical contract를 확정한다.

**Gate D — Calibration**

Official \(c,b\) profile을 얻거나 최소한 calibration protocol을 freeze 가능한 수준으로 확정한다.

**Gate E — CPS/Burst**

초기 model validation 결과 hard constraint가 실제 필요한지 KEEP-DEFER 판단을 확정한다.

**Gate F — Final deterministic tie key**

E와 L까지 policy상 동일한 경우의 완전 deterministic fallback ordering을 명시한다.

---

## 33. Post-Freeze Work — Not Part of Algorithm Freeze

Algorithm specification이 먼저 freeze된 뒤에 다음을 설계한다.

- Stage-3 execution/integration seam
- Telemetry V1 field의 의미 재검토
- CHORD 및 planner semantics가 기존 telemetry에 진실하게 들어가는지 확인
- Stage-2 immutable 100k baseline과 Stage-3 artifact의 paired comparison path
- Shared benchmark path 수정 전 Stage-2 semantic action golden 필요 여부
- Stage-3 compute-time protocol
- Modeled physical-time reporting
- Whole-prefix outcomes와 both-win/time-to-win 분석의 분리

---

## 34. Current Review Claim

이 Draft가 주장하는 것은 다음 수준으로 제한한다.

Stage 3는:

> **Stage-2의 공개정보 기반 risk discipline을 보존하고, 현재 admissible certainty/minimum-risk evidence와 그 deterministic short-horizon consequences를 이용하여, cursor-aware modeled physical speed를 최적화하려는 first-reveal receding-horizon planner**

다.

Stage 3는:

- 전체 게임의 mathematically optimal play-time을 보장하지 않는다.
- Stage 2보다 강한 general mine solver임을 주장하지 않는다.
- hidden answer를 사용하지 않는다.
- human behavior 전체를 시뮬레이션하지 않는다.
- Stage 4의 click-efficiency objective를 대신하지 않는다.

현재 이 문서의 상태는:

`DRAFT v1.1 — REVIEW CANDIDATE`

이며 아직:

`FROZEN`

이 아니다.
