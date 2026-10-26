# PROGRAM K REMEDIATION DESIGN V1.3.1 — OVERSHOOT CORRECTION

**V3-R1 — CLOSED BY CHATGPT/USER DESIGN ADJUDICATION**

V1.3의 전체 설계와 기존 closure를 유지합니다. 이번 정정은 **text-family overshoot window 복원, reference 예외 유지, 전체 procedural-excess budget 추가**, 그리고 V3-O1~O3 정리에 한정합니다.

새로운 source/contract 모순은 발견하지 못했습니다. 구현이나 실행 승인은 포함하지 않습니다.

## 1. PREFLIGHT / AUTHORITY

시작·종료 read-only 확인 결과입니다.

| 항목 | 결과 |
|---|---|
| Branch | `main` |
| HEAD | `be1fa9d74d3fb6c4efba91df02741cb98699551f` |
| 로컬 `origin/main` | HEAD와 동일 |
| Ahead / behind | `0 / 0` |
| Index / worktree | Clean |
| 비무시 untracked 파일 | 없음 |
| Worktree/index `git diff --check` | 모두 exit `0` |

전역 Git ignore 파일 접근 권한 경고는 있었으며 명령들은 성공했습니다. Git mutation은 없었습니다.

[저장된 V1.3 설계](<C:/Projects/GraduationProject/PROGRAM_K_REMEDIATION_DESIGN_V1_3_CODEX_FULL.txt>), 관련 source/tests, frozen authorities를 대조했습니다. V3 findings의 판정 권위는 이번 사용자 메시지에 제공된 re-audit 결과와 최종 재정입니다.

Frozen hashes도 일치했습니다.

```text
Protocol:
10b1055a6e1bcab8e03ab504755c9c9d655d5457800318396afb6e31497ba2fa

Amendment:
5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf
```

이번에는 codec diagnostics도 다시 실행하지 않았습니다. 아래 diagnostic 수치는 V1.3 결과를 재사용한 산술 예시입니다.

## 2. 유지되는 설계와 정정 대상

다음 V1.3 규칙은 그대로 유지합니다.

| 영역 | 유지되는 규칙 |
|---|---|
| Logical evidence | 변경 없는 `records.encode()` canonical bytes와 semantic digests |
| Evidence content | Exact counts/probabilities, decisions, certificate premises/history, Oracle expected/actual 및 failure evidence |
| Rank copies | rank-0/1/2의 독립적인 완전한 durable copies |
| Physical representation | RF02, WB02, qualified codec/profile |
| Calibration | Physical/logical maxima와 두 독립 3/2 floors |
| Archive authority | Actual physical durable bytes |
| Logical floor | Postprocessing workload qualification guard; archive credit 아님 |
| Constructors | Two-component text와 truthful 479-entry reference catalog |
| Synthetic domains | P=0, K=1, O-primary=2, O-repeat=3, D=4, reference=5 |
| Search | 최대 8 unique candidates, deterministic schedule, no zlib monotonicity assumption |
| Validation | Worker ≠ parent ≠ coordinator ≠ independent readback |
| Store | Append-only, immutable keys, incremental hashes, durability 후 progress |
| Accounting | 모든 experiment-local bytes, fixed/support 및 final archive cap |
| Compatibility | V1 historical evidence 불변, V1/V2 isolation |
| Research boundaries | 기존 ownership/counts/factors/caps/selectors/N ladder와 full shared 10,000 bootstrap |
| Governance | Fresh separately authorized R0-A 이후에만 후속 admission 검토 |

V1.3에서 다음 문구와 수치는 V1.3.1로 대체합니다.

- “모든 family에 고정 4,096 B excess cap이 없다” → **positive-floor text families에는 inclusive +4096 window 적용**.
- “최종 archive capacity만으로 aggregate excess를 제한한다” → **persistence 전 global procedural budget도 검사**.
- Reference additional entry 최소 14 B → **13 B**.
- Reference q 및 packed-prefix 상한 → **copy-aware 상한으로 정정**.
- R-8 overshoot tests → 이번 window/budget 규칙을 검사하도록 정정.

## 3. V3-R1 — TEXT FAMILIES의 정확한 acceptance

적용 family는 다음 다섯 개입니다.

```text
P
K
O-primary
O-repeat
D
```

각 family의 positive physical floor `T_P > 0`에 대해:

\[
T_P \le P_{\text{actual}} \le T_P+4096
\]

동시에:

\[
L_{\text{actual}}\ge T_L
\]

그리고 기존 모든 semantic bindings, expanded/legacy/wire/physical composite caps를 통과해야 합니다.

**4,096 B는 synthetic-sizing procedure의 overshoot guard입니다. Frozen archive factor 또는 새로운 archive allowance가 아닙니다.**

### 후보 선택

V1.3의 two-component constructor와 최대 8회 schedule을 유지합니다.

- Repetitive text가 logical volume을 공급.
- Deterministic entropy component가 physical size를 조절.
- Physical/logical bytes는 actual canonical bodies와 complete frames에서 측정.
- Search pair/gap 선택 규칙 유지.
- Compressed-size monotonicity 가정 금지.
- Additional retry/backtracking 금지.

평가된 후보 중 모든 조건을 통과한 eligible candidates에 대해 기존 tie-break를 적용합니다.

```text
lexicographic minimum:
(actual_physical_bytes, actual_logical_bytes, h)
```

이는 bounded candidate set 안의 최소이며 global optimum 주장이 아닙니다.

### 전용 rejection

```text
SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT
```

적용 조건:

```text
text_window_applicable
and actual_physical_bytes > physical_target + 4096
```

Overshoot 후보는 trial ledger에 해당 reason으로 기록하고 후보 탐색을 계속할 수 있습니다. 그것만으로 추가 trial을 허용하지 않습니다.

최대 8회 후 eligible candidate가 없고, 다른 조건을 통과한 후보들이 모두 text window 때문에 탈락했다면 이 전용 reason을 terminal disposition으로 사용합니다. 복합 실패인 경우에도 trial별 overshoot reason을 일반적인 search exhaustion으로 지우지 않습니다.

### 최대 aggregate text excess

\[
4096(10000+256+128+4+256)=43,597,824
\]

```text
Maximum text-family procedural excess:
43,597,824 B
```

이 값은 **상한**입니다. Global budget에서 미리 전액 차감하지 않고 실제 채택한 text excess만 차감합니다.

Zero-row Oracle는 계속 `P=L=T_P=T_L=0`이며 text window를 적용하지 않습니다. 빈 stream에 filler나 frame을 추가하지 않습니다.

## 4. V3-R1 — REFERENCE R의 정확한 acceptance

Reference에는 `+4096` window를 적용하지 않습니다.

최대 8 unique candidate search를 유지하고 다음을 모두 통과한 후보만 eligible입니다.

```text
actual_physical_bytes >= physical_target
actual_logical_bytes  >= logical_target
all expanded / legacy / wire / physical composite caps
all truthful semantic bindings
all K/D copied-reference bindings
```

선택 규칙은 정확히 다음입니다.

```text
lexicographic minimum:
(actual_physical_bytes, actual_logical_bytes, q)
```

따라서:

- Physical size가 더 작은 eligible candidate가 우선.
- Physical size가 같으면 logical size가 작은 후보 우선.
- 두 size가 같으면 q가 작은 후보 우선.
- First successful candidate를 즉시 선택하는 방식으로 바꾸지 않음.
- Global budget에 맞추려고 8회 밖의 추가 reference search를 하지 않음.

Reference actual excess는 반드시 unit/family별로 기록합니다.

\[
E_{R,u}=P_{R,u}-T_{P,R}
\]

`E_R > 4096`이라는 이유만으로 거부하지 않습니다. 그러나 모든 payload caps와 **global procedural-excess budget**은 적용합니다.

## 5. V3-R1 — GLOBAL PROCEDURAL-EXCESS BUDGET

Fresh R0-A에서 physical maxima와 minima가 인증된 뒤, accepted counts를 사용하여 계산합니다.

\[
S_{\min}=\sum_f n_fT_{P,f}
\]

\[
B_{\mathrm{proc}}
=
\text{MAX\_ARCHIVE\_BYTES}
-
\text{FIXED\_REPORT\_RECEIPT\_ALLOWANCE}
-
S_{\min}
\]

상수는 변경하지 않습니다.

```text
MAX_ARCHIVE_BYTES             = 17,179,869,184
FIXED_REPORT_RECEIPT_ALLOWANCE =    268,435,456

Attributable procedural capacity:
16,911,433,728 B
```

### 5.1 Materialization 전

- `B_proc < 0`: 기존 설계의 minimum archive infeasibility 처리로 fail closed.
- `B_proc = 0`: 초기 budget 검사는 통과하지만 모든 accepted attributable excess가 0이어야 함.
- `B_proc > 0`: 실제 cumulative excess를 이 budget 안에서 관리.

이 검사는 현재 source에 이미 구현되어 있다는 뜻이 아닙니다. V1.3.1 구현 계획의 필수 pre-materialization guard입니다.

### 5.2 V1.3 pure lower-bound preflight와의 관계

기존 pure preflight도 유지합니다.

\[
S_{\min}+S_{\text{proven mandatory}}\le\text{archive cap}
\]

두 검사의 의미를 구분합니다.

| 검사 | 의미 |
|---|---|
| Proven-support lower-bound preflight | 증명된 최소 physical bytes만으로 불가능한지 검사 |
| `B_proc` 계산 | 이번 재정에 따라 full fixed allowance를 reserve한 procedural admission 검사 |

Full allowance를 reserve하는 것은 이번 명시적 재정입니다. 이것이 `268,435,456 B` 전부를 실제 mandatory support bytes라고 재해석하는 것은 아닙니다.

Reservation만으로 `B_proc<0`이 된 경우에도 fail closed하지만, 이를 frozen experiment 자체의 불가능성이 입증되었다고 확대 해석하지 않습니다. 실패 보고에 reservation basis를 명시합니다.

### 5.3 Unit persistence 전 검사

각 family의 dual floors와 text window를 통과한 뒤, fresh coordinator validation이 actual bytes를 독립 산출합니다.

다음 worker unit에 포함되는 모든 family의 excess를 합칩니다.

\[
\Delta E_u=\sum_{f\in u}(P_{u,f}-T_{P,f})
\]

모든 항은 음수가 아니어야 합니다. 한 family의 undersize를 다른 family의 excess와 상쇄할 수 없습니다.

Persistence 전:

\[
E_{\text{committed}}+E_{\text{reserved}}+\Delta E_u
\le B_{\mathrm{proc}}
\]

를 검사합니다.

초과하면:

```text
SYNTHETIC_PROCEDURAL_EXCESS_BUDGET
```

으로 fail closed합니다.

### 5.4 Atomic reservation / durability

검사 단위는 개별 row가 아니라 **complete worker unit**입니다.

```text
immutable candidate
→ fresh coordinator validation
→ all family/window/cap checks
→ complete-unit excess calculation
→ budget check and reservation
→ attributable frame persistence
→ required durability
→ committed excess/counts/progress update
```

- Candidate trials에는 budget을 차감하지 않음.
- 한 unit의 일부 family만 먼저 persist한 뒤 나머지 family의 budget을 검사하지 않음.
- 해당 unit의 첫 attributable frame을 쓰기 전에 reservation 완료.
- Required durability 이후 committed ledger에 반영.
- Partial write/fsync failure는 기존 poison/abort 처리.
- Partial evidence가 남은 run에서 reservation을 refund하고 계속하지 않음.
- 기존 START/ERROR support events는 fixed/support accounting에 남으며 attributable excess에 넣지 않음.

현재 materialization은 serial입니다. 이 설계는 worker scheduling을 변경하지 않습니다.

### 5.5 Ownership과 double counting 방지

R은 기존대로 rank-0 reference ownership에 한 번 귀속됩니다. K/D 안의 copied/repeated reference bytes는 K/D actual physical bytes에 포함됩니다.

따라서 그 copies는 K/D excess에 이미 반영되며 R excess로 다시 더하지 않습니다.

Logical excess, rejected candidate bytes, 미사용 text-window capacity, 미사용 fixed allowance는 procedural budget credit으로 사용할 수 없습니다. `B_proc`는 초기 인증된 값으로 고정합니다.

### 5.6 Final reconciliation

성공 run의 최종 값은 다음과 정확히 일치해야 합니다.

\[
E_{\text{final}}
=
\sum_f
\left(
P^{\text{total}}_f-n_fT_{P,f}
\right)
\]

```text
E_final == committed procedural ledger
E_final <= B_proc
```

이 검사와 별개로 기존 검사를 반드시 수행합니다.

```text
realized_fixed_allowance_bytes <= FIXED_REPORT_RECEIPT_ALLOWANCE
actual_archive_bytes <= MAX_ARCHIVE_BYTES
```

`SYNTHETIC_PROCEDURAL_EXCESS_BUDGET`은 다음과 구분합니다.

- `R0B_ARCHIVE_CAP`
- `R0B_FIXED_ALLOWANCE_CAP`
- Frozen experiment infeasibility 판단
- Candidate-search exhaustion
- Text physical overshoot
- Logical/physical floor shortfall

## 6. REPORTING / V2 evidence facts

각 accepted unit/family에 다음을 기록합니다.

```text
physical_target
actual_physical_bytes
procedural_excess
text_window_applicable
text_window_upper_bound, when applicable

logical_target
actual_logical_bytes
logical_excess

constructor/domain
selected knob
selected trial
```

Rejected candidates에는 signed margins, violated conditions와 정확한 rejection reason을 유지합니다.

Run 전체:

```text
physical_minimum_total
fixed_allowance_reservation
B_proc
realized_cumulative_excess
remaining_procedural_budget
```

\[
\text{remaining}=B_{\mathrm{proc}}-E_{\text{committed}}
\]

In-flight reservation이 있으면 이를 별도 표시합니다. 아직 durable하지 않은 unit을 realized/committed로 보고하지 않습니다. 실패한 partial unit은 partial/failed 상태로 기록합니다.

Family별 actual total, excess total, maximum excess 및 text-window applicability도 보고합니다.

V2 adapter/readback은 다음을 independently reproduce해야 합니다.

1. Fresh R0-A의 independent physical/logical maxima.
2. 두 exact ceilings.
3. Unit별 dual floors와 text window.
4. Reference minimum-candidate selection facts.
5. `B_proc` 계산.
6. Unit/family excess와 final ledger reconciliation.
7. Actual physical archive accounting.

V1/V2 schema isolation과 historical V1 decoding은 변경하지 않습니다. 새 reporting facts를 historical evidence에 보충하거나 migration하지 않습니다.

## 7. V3-O1 — Reference entry와 q bound 정정

추가 constraint의 최소 canonical 증가분은 **13 B**입니다.

예를 들어:

```text
[[3,0],0,[]]
```

는 12 B이며, 기존 nonempty list에 추가할 때 comma 1 B가 붙습니다.

### 정정된 상한

Single-copy의 느슨한 상한:

\[
q\le\lfloor M/13\rfloor=5,162,220
\]

그러나 K/D는 각각 두 reference/V1-premise copies를 포함하므로 copy-aware absolute bound는:

\[
q\le\lfloor M/26\rfloor=2,581,110
\]

입니다.

```text
M = 67,108,864 B
copy-aware q ceiling = 2,581,110
```

이 값은 실제 admissible `q_hi`가 아닙니다. 실제 `q_hi`는 다음을 모두 포함한 exact arithmetic으로 더 낮춰야 합니다.

- Complete 479-entry catalog.
- Fixed maintenance/record bodies.
- 두 copies.
- 다른 required streams.
- Text-family logical minimum reserve.
- Exact `Lsum` 및 `Llegacy` caps.

Entry들의 실제 canonical 길이는 서로 다르므로 모든 entry를 13 B로 가정하여 `q_hi`를 정하면 안 됩니다. 13 B는 absolute upper-bound derivation에만 사용합니다.

Packed u16 indices와 u32 prefix lengths의 reservation은 다음으로 정정합니다.

```text
6q + 4 <= 15,486,664 B
```

고정 catalog와 Python object memory는 별도입니다. Existing memory guards와 V1.3의 aggregate readback reservation은 유지합니다.

### Search bounds 영향

Search schedule과 최대 trial 수는 바뀌지 않습니다.

| 항목 | 유지되는 상한 |
|---|---:|
| Unit/family별 unique trials | 8 |
| Family instances | 11,150 |
| Candidate evaluations | 89,200 |
| Changed-row compressor invocations | 102,400 |
| Changed-row compressor input | 6,871,947,673,600 B |

Text-window 검사와 budget 산술 때문에 codec call을 추가하지 않습니다. 기존 baseline encoding 및 독립 boundary validation은 계속 별도로 수행합니다.

## 8. V3-O2 — K shadow accounting 3종 명시

30×16 observation에서:

```text
t = (1,0)
t만 HIDDEN
나머지 479 cells는 CLUE_0
num_mines = 0
```

다음 세 accounting slots를 각각 명시적으로 구성합니다.

```text
local_before
local_after
after
```

세 값 모두:

```text
P = ()
M = ()
J = ()

H = (t,)
U = (t,)
b = 0
```

Clue accounting은 각각 **479-entry catalog를 한 번씩** 포함합니다.

```text
constraints = (
    (source, 0, (), Uc(source), 0)
    for every opened source in reading order
)

Uc(source) = (t,) if source is adjacent to t
             ()   otherwise
```

- 5개 entries는 `Uc=(t,)`.
- 나머지 474개 entries는 `Uc=()`.
- `q`개의 redundant V1 constraints를 이 세 accounting catalog에 반복 복사하지 않습니다.
- 이 fixture에서는 acquired mine이나 certificate가 없으므로 세 accounting 값은 value-equal입니다.

연결된 shadow fields:

```text
acquired_mines       = ()
S_new                = ()
S_first              = (t,)
S_second_all         = (t,)
S_current            = (t,)
selection_safe_cells = (t,)

local_certificates   = ()
exact_certificates   = ()
phase_d              = None
phase_e              = None
phase_e_status       = "NOT_REACHED"
continuation         = "LOCAL_SAFE"
guess_target         = None
```

이는 [KControlAccounting와 ShadowDecision](<C:/Projects/GraduationProject/Minesweeper Project/Minesweeper-Project/experiments/program_k_e2_records.py:1017>), [production accounting mapping](<C:/Projects/GraduationProject/Minesweeper Project/Minesweeper-Project/experiments/program_k_e2_execution.py:777>) 및 [clue-accounting construction](<C:/Projects/GraduationProject/Minesweeper Project/Minesweeper-Project/experiments/program_k_capability.py:286>)과 대조했습니다.

## 9. V3-O3 — Mandatory bounded performance diagnostic

V3-O3를 design blocker로 승격하지 않습니다.

대신 구현 qualification에서 **대규모 qualification 전에 반드시 수행할 bounded diagnostic**으로 둡니다. 이번 작업에서는 실행하지 않습니다.

### 측정 대상

V1.3의 exact truthful reference construction을 사용합니다.

- 30×16 observation.
- Complete 479-entry catalog.
- V1.3 witness인 `q=463,000` added entries.
- 해당 reference의 실제 K/D copies와 binding inputs.
- 구현된 qualified codec/profile.
- 정확한 canonical records와 실제 validation paths.

작은 대체 record의 결과를 이 대형 reference의 성능으로 보고하지 않습니다.

### 직접 측정할 항목

- Canonical encode wall.
- Canonical decode wall.
- Record/semantic validation wall.
- K reference/control binding wall.
- D copied/repeat-reference binding wall.
- 전체 diagnostic wall.
- Peak RSS 및 기존 operational memory metrics.

Setup/record construction과 각 측정 구간을 구분하여 보고합니다. 필요한 validation을 제거하거나 setup 비용을 임의 차감하여 개선을 주장하지 않습니다.

### 실행 경계

- 단일 bounded reference fixture와 필요한 K/D objects에 한정.
- Corpus materialization, solver, board generation, bootstrap, R0 실행 없음.
- 시작 전에 wall/memory/cancellation bounds를 선언.
- Existing payload/process-memory guards 유지.
- Timeout/resource breach 시 중단하고 결과를 보존.
- 측정과 검토가 완료되기 전 대규모 qualification으로 진행하지 않음.

결과는 implementation qualification evidence이며 R0 calibration/admission evidence가 아닙니다. 성능 문제가 나타나면 그 범위의 구현·설계를 검토하되, caps나 semantics를 자동 변경하지 않습니다.

## 10. RF02 / CAPS / TRUST BOUNDARIES — 변경 없음

### Frame

```text
mode:u8
logical_length:u32BE
payload_length:u32BE
key_components:canonical unsigned LEB128
payload
contextual_crc32:u32BE
```

```text
overhead = 13 + Σ ULEB128_width(key_component)
```

- Experiment key `(position, rank, index)`는 full uint64.
- Stream/profile/type/arity는 authenticated context.
- No stream prologue.
- Empty Oracle 0 B.
- Coverage RAW와 exact −1 B convention 유지.
- CRC는 corruption check이며 containing SHA-256 closure를 대체하지 않음.

Codec는 raw DEFLATE `level=6, wbits=-15, memLevel=8, Z_DEFAULT_STRATEGY`, fresh compressor, 65,536 B chunks, one `Z_FINISH`, strictly-smaller일 때만 compression입니다.

### Caps

```text
Lsum    <= M
Llegacy <= M
Wnew    <= M

Synthetic:
Sunit   <= M

M <= 67,108,864 B
```

Actual fragment cap, bounded inflation, truncation/trailing-data rejection도 유지합니다.

### Validation / store

- Worker, parent, coordinator, readback 독립 검증.
- Same-boundary private context 안에서만 decoded/canonical/frame reuse.
- K/D comparison은 logical bytes.
- Whole-unit admission 후 exact frame append.
- Dirty checkpoint와 fsync 후 progress.
- Partial failure poison.
- Independent final readback.
- Aggregate serialized read-ahead upper reservation `402,786,480 B` 유지; actual Python heap은 기존 memory guards로 관리.

Global budget은 이 경계를 약화하지 않고 **fresh coordinator validation과 persistence 사이에 추가되는 guard**입니다.

## 11. Archive close와 source plan

Archive close 순서는 유지합니다.

1. Pre-manifest experiment files 완료.
2. Coordinator/status 완료.
3. Existing-file inventory.
4. Self/future-completion을 제외한 manifest.
5. Manifest를 bind하는 completion receipt.
6. Manifest/completion 포함 final inventory.
7. Attributable/fixed partition.
8. Fixed/support cap.
9. Whole archive cap.
10. Counts, dual minima, totals 및 procedural-excess reconciliation.

새 budget이 final physical inventory를 대체하지 않습니다.

V1.3의 **2 ADD + 6 MODIFY** production-file 계획을 유지합니다. 이번 정정 때문에 추가 production module은 필요하지 않습니다.

주요 변경 책임은 다음과 같습니다.

| Source surface | V1.3.1 추가 책임 |
|---|---|
| [readiness](<C:/Projects/GraduationProject/Minesweeper Project/Minesweeper-Project/experiments/program_k_e2_readiness.py>) | Pure `B_proc` 계산, window/budget policy, V2 facts 재검증 |
| [r0_harness: constructor](<C:/Projects/GraduationProject/Minesweeper Project/Minesweeper-Project/experiments/program_k_e2_r0_harness.py:633>) | Text eligibility, R tuple minimum, corrected q/accounting |
| [r0_harness: materialization](<C:/Projects/GraduationProject/Minesweeper Project/Minesweeper-Project/experiments/program_k_e2_r0_harness.py:755>) | Pre-persistence reservation, committed ledger, reporting |
| [operational sink](<C:/Projects/GraduationProject/Minesweeper Project/Minesweeper-Project/experiments/program_k_e2_operational.py:889>) | Fresh validated metrics와 whole-unit persistence 사이의 private seam |
| [archive accounting](<C:/Projects/GraduationProject/Minesweeper Project/Minesweeper-Project/experiments/program_k_e2_r0_harness.py:1470>) | Exact physical totals와 excess ledger reconciliation |
| 예정 V2 evidence adapter | Window/budget facts의 독립 재현 |

현재 harness는 `sink.admit()` 뒤에 family bytes를 집계합니다. V2에서는 독립 검증된 unit metrics를 persistence 전에 확보하여 budget을 검사하고, durability 성공 뒤 committed totals를 갱신해야 합니다.

Overshoot policy는 generic physical codec에 넣지 않습니다. Logical record schema와 solver/game/audit semantics도 변경하지 않습니다.

## 12. TEST / QUALIFICATION PLAN

기존 V1.3 tests와 모든 R-1~R-8 closure tests를 유지하고 아래를 추가·명확화합니다.

### Text window

각 P/K/O-primary/O-repeat/D에 대해, 다른 조건이 모두 충족될 때:

- `P=T_P`: PASS.
- `P=T_P+4096`: PASS.
- `P=T_P+4097`: `SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT`.
- Physical window PASS / logical floor FAIL: logical shortfall.
- Logical PASS / physical minimum FAIL: physical shortfall.
- No cross-credit.
- Zero-row Oracle는 window 미적용, actual bytes 0.
- Candidate rejection reason과 terminal exhaustion 분류 보존.

### Reference

- Truthful `E_R>4096` 후보 허용.
- Eligible candidates 중 `(P,L,q)` lexicographic minimum.
- First-pass candidate를 무조건 선택하지 않음.
- Lower-physical candidate가 semantic/cap 조건을 실패하면 제외.
- 13 B minimum-entry arithmetic.
- Copy-aware `2,581,110` absolute q bound.
- Actual baseline-aware `q_hi`가 더 엄격한지.
- Packed-prefix reservation 정정.
- 세 shadow accounting slots 각각 479 entries.
- q repetitions가 accounting catalog에 증식하지 않음.
- K/D copied-reference binding 유지.

### Global budget

- `B_proc<0`: materialization 전 minimum-archive infeasibility 처리.
- `B_proc=0`: zero excess만 허용.
- `E_next=B_proc`: PASS.
- `E_next=B_proc+1`: `SYNTHETIC_PROCEDURAL_EXCESS_BUDGET`.
- Complete composite unit의 첫 attributable write 전에 거부.
- Rejected trials는 budget을 소비하지 않음.
- Negative shortfall로 excess 상쇄 금지.
- K/D copies를 R로 중복 차감하지 않음.
- Reservation 후 partial-write/fsync failure에서 abort/poison.
- 미사용 fixed allowance나 text window로 budget 증가 금지.
- Final ledger와 actual family totals의 equality.
- Procedural-budget failure와 archive-cap/search-exhaustion failure 구분.
- Budget PASS가 independent inventory/fixed/archive checks를 생략하지 않음.

### 기존 qualification 유지

- RF02 arithmetic/corruption/truncation/context substitution.
- Immutable unique keys와 canonicality.
- Worker/parent/coordinator/readback 독립 검증.
- Dirty checkpoint, failure atomicity, progress-after-durability.
- V1 literal fixtures와 모든 fact adapters.
- V1/V2/profile/basis mixing rejection.
- Complete Program-K E2 및 관련 Stage-3/Model-C/provenance regression.
- Accepted isolation-aware full gate.
- 대규모 qualification 전 V3-O3 bounded performance diagnostic.

**이번에는 테스트나 performance diagnostic을 실행하지 않았습니다.**

## 13. 기존 diagnostic 수치에 대한 산술 예시

아래는 V1.3 diagnostic physical minima를 재사용한 예시입니다. Fresh R0-A 또는 admission 값이 아닙니다.

```text
Indicative physical minimum total:
15,388,034,006 B

Indicative B_proc:
17,179,869,184
− 268,435,456
− 15,388,034,006
= 1,523,399,722 B
```

최대 text excess를 가정하면:

```text
1,523,399,722 − 43,597,824
= 1,479,801,898 B
```

이 값은 별도의 R cap을 새로 정하는 것이 아닙니다.

V1.3 reference witness의 excess는:

```text
71,239 B/unit × 506
= 36,046,934 B
```

따라서 위 illustrative assumptions에서:

```text
1,523,399,722
− 43,597,824
− 36,046,934
= 1,443,754,964 B
```

가 남습니다.

V1.3 text diagnostics의 physical excess `P=5`, `K=0`, `D=2`, `O-primary=1`, `O-repeat=1 B`는 복원된 window 안에 있습니다. 다만 당시 명시한 partial/full-family diagnostic 범위의 한계도 그대로 유지합니다.

**이번 정정으로 새 static contradiction은 드러나지 않았습니다.** 실제 constructor 성공과 archive fit는 fresh evidence로 판단해야 합니다.

## 14. CLOSURE / GOVERNANCE

| Finding | V1.3.1 상태 |
|---|---|
| V3-R1 | **CLOSED BY CHATGPT/USER DESIGN ADJUDICATION** |
| V3-O1 | 13 B, copy-aware q 및 packed bound 정정 |
| V3-O2 | 세 accounting slots를 479-entry catalog 기준으로 명시 |
| V3-O3 | Mandatory bounded implementation-performance diagnostic으로 채택; design blocker 아님 |
| 기존 R-1/R-2/R-4/R-5/R-6/R-8 | Closure 유지, 관련 tests 정정 |
| 기존 R-3/R-7 | **CLOSED BY CHATGPT/USER DESIGN ADJUDICATION** 유지 |
| RR-1~RR-4 및 adopted O-findings | 이번 명시적 정정 외 유지 |

향후 순서는 변경하지 않습니다.

1. Independent closure re-audit.
2. 별도 구현 승인.
3. 구현, bounded performance diagnostic, qualification.
4. 사용자가 qualified source commit.
5. Historical R0-A unchanged 보존.
6. 별도 NEW R0-A 승인 및 c=1/2/4 calibration.
7. Execution projection, physical/logical floors, `B_proc`, constructibility 재평가.
8. 조건 충족 시 첫 real R0-B 별도 승인.
9. Complete R0 adjudication.
10. 최종 N/concurrency/envelope 선택.
11. Actual E2 별도 승인.

Historical R0-A는 원래 source의 accepted evidence로 계속 유효합니다. 변경된 source/profile/procedure의 current admission evidence로 사용할 수 없습니다.

## 15. FINAL VERDICT

**PROGRAM K REMEDIATION DESIGN V1.3.1 READY FOR INDEPENDENT CLOSURE RE-AUDIT**

이는 implementation-ready, feasibility PASS 또는 실행 승인이 아닙니다.

## 16. BOUNDARY STATUS

- 파일·source·tests·docs·evidence 변경 없음.
- 테스트·codec/performance diagnostics 실행 없음.
- Git mutation 없음.
- R0-A / R0-B / Actual E2 실행 없음.
- Solver / board generation / bootstrap 실행 없음.
- Synthetic materialization 없음.
- Target recount / corpus search 없음.
- Holdout 접근 없음.
- Frozen authority 수정 없음.
- Historical accepted R0-A 보존.
- Program K effectiveness는 **NOT ESTABLISHED**.

PROGRAM K REMEDIATION DESIGN V1.3.1 OVERSHOOT-CORRECTION COMPLETE — NO IMPLEMENTATION AUTHORIZED