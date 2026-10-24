# Program K E2 — R0 Attribution Amendment v1

> Status: **CANDIDATE — NOT CONTENT-FROZEN / NOT ACCEPTED**
>
> Work unit: **contract authoring only** following the independent R0 attribution audit.
> This revision is a **document correction** after the independent exact-byte audit
> of the prior candidate bytes; see §13.
>
> Authoring date: **2026-10-24 (Asia/Seoul)**.
>
> This candidate does not authorize implementation, real-seed subset calculation,
> R0-A, R0-B, Actual E2, E3, or Gate P. The existing uncommitted eight-file R0-PRE
> observability candidate is not accepted by this document.

## 1. Identity, scope, and authority

This amendment does **not** replace the frozen E2 effectiveness protocol. The
original frozen protocol remains authoritative everywhere except the specifically
enumerated superseded R0 attribution/admission clauses in §2 below. This is an
**additive operational-accounting authority only**, effective only after separate
acceptance.

It changes no solver action, research threshold, subset label, subset algorithm,
bootstrap algorithm, effect gate, or treatment policy. It cannot authorize R0,
Actual E2, E3, or Gate P by itself.

The exact base and parent identities are:

| Binding | Identity |
| --- | --- |
| Frozen base protocol | `docs/stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md` |
| Frozen protocol commit | `6d3eb456d72632d24e9cab14bdeea0cffd279092` |
| Frozen protocol blob | `3351017f0f0116be00917be3ff95312120f43117` |
| Frozen protocol SHA-256 | `10b1055a6e1bcab8e03ab504755c9c9d655d5457800318396afb6e31497ba2fa` |
| Accepted implementation parent HEAD | `9071469e2e4a884722ea02e2faea3441d916876c` |
| Amendment path | `docs/stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md` |
| Amendment byte identity | `AMENDMENT_SHA256 = SHA256(exact amendment file bytes)`; eventual freeze receipt required |

The external content-freeze receipt MUST record the amendment path, exact byte
length, `AMENDMENT_SHA256`, the three frozen protocol identifiers above, the
accepted parent HEAD, and the explicit separate acceptance. The digest covers the
complete file, including encoding and line endings. The digest belongs in that
external receipt, not in a self-referential hash field inside the file. A
candidate hash is an identification aid, not a freeze or acceptance. No freeze
receipt or acceptance is issued by this authoring work. §10.1 defines how the
frozen bytes relate to freeze state.

This amendment defines **no global authority order**. The frozen base protocol §2
authority order remains authoritative and is **not superseded**. After acceptance,
the amendment adds only these narrow rules:

- **Superseded-clause precedence.** For a dispute about a clause explicitly
  superseded in §2 below, the accepted amendment controls only the replacement
  R0 attribution/admission semantics stated for that clause in this document.
  This precedence is an exception between this amendment and the base E2
  protocol text only.
- **Normative contract versus current implementation.** Current committed source
  and current tests remain the authority for what the current implementation
  actually does; current source and tests, including the uncommitted R0-PRE
  source and tests, may be factual evidence of what those current bytes do.
  After this amendment is content-frozen and accepted, however,
  the replacement R0 attribution/admission semantics of the explicitly
  superseded clauses are the frozen normative semantic contract that future
  implementation must follow. Where current source or tests still differ from
  those semantics, the difference is an implementation nonconformance to be
  corrected through the separately authorized sequence in §10, not a basis for
  reinterpreting, narrowing, or invalidating this amendment.
- **No reordering.** The normative-contract rule mirrors base §2's own
  distinction between evidence of what actually occurred and a frozen semantic
  contract. Neither rule lowers the factual evidence priority of source or
  tests, and neither globally reorders current committed source, current tests,
  the frozen Program-K research specification, the frozen Gate-R E0/E1
  protocol, accepted P-8/E0/E1/R3/F1 evidence, the accepted E1
  closeout/current handoff, executable evidence, or AI interpretation.
- **Separate amendment authority.** Once accepted, this amendment is a
  separately accepted amendment authority for its enumerated replacement
  semantics only. It is not silently mapped onto, or substituted for, any of the
  eight items listed in base §2.
- Outside explicitly superseded clauses, base §2 applies unchanged.
- Before acceptance, neither rule has any effect.

The current uncommitted R0-PRE candidate and its tests are inspection material,
not accepted authority. Here "not accepted authority" means that those
uncommitted bytes are not an accepted implementation baseline and do not define
the frozen normative contract; they may still be factual evidence of what they
do, and after acceptance any divergence from the replacement semantics remains
implementation nonconformance as defined above. The source citations in §12 are
observations of inspected snapshots that explain the proposed accounting; citing
them neither accepts uncommitted work nor changes the standing that base §2 gives
any source or test.

## 2. Exhaustive list of superseded base-protocol clauses

All section numbers in this table refer to the frozen base protocol.

| Base area | Exact scope of supersession | Replacement here |
| --- | --- | --- |
| §6.5 | Only the timing restriction requiring N freeze before a corpus digest can be used prospectively, for (a) R0 admission projection and (b) the real-count minimum scale targets of the R0-B synthetic corpus. Final corpus identity and the digest bytes/formula remain unchanged. | §§3, 8 |
| §20.1 | R0-A component measurement interpretation, including complete K/D standalone boundaries, three separately observed route-specific Oracle wall calibrations (primary, K-bind, D-repeat), and audit-only Oracle byte observations. Board identities, 64-board count, candidate concurrencies, and outcome blindness remain unchanged. | §§4–5, 9 |
| §20.3 | R0-B synthetic attributable sizing families, their realized synthetic-corpus counts and real-count minimum scale targets, their attributable-byte sizing inputs, and zero-row Oracle sizing. Schema-valid synthetic Nmax records, the actual postprocessing path, and the full shared bootstrap workload remain unchanged. | §§6, 8 |
| §21.3 | R0-A measured component attribution: conservative standalone and route-specific walls, strictly non-overlapping bundle-stream byte ownership, audit-only Oracle byte normalization, zero-row Oracle byte observations, and bytes-only R measurement. Its inclusive-overlap restriction is superseded only to permit the expressly stated wall convention. | §§4–7, 9 |
| §21.4 | Execution projection's single Oracle term, replaced by route-specific primary, K-bind, and D-repeat Oracle wall terms counted by `min(N,128)`, `I_OK(N)`, and `I_OD(N)`, plus the meaning of complete standalone K/D walls. The four conceptual P/K/O/D wall components and safety factor remain. | §§4–5 |
| §21.6 | Archive projection: non-overlapping P/K/O/D/R ownership of bundle-stream bytes, repeat Oracle count, once-per-union rank-0 reference bytes, and fixed-allowance ownership of supporting operational/provenance bytes. Archive ceiling and fixed allowance value remain. | §§6–7 |

**No unrelated clause is superseded.** In particular, the authority order in §2,
the existing selector in §6.6, subset definitions in §§15–16, bootstrap in §9,
postprocessing projection in §21.5, memory/watchdog admission in §21.7, and
outcome-blind selection rule in §21.8 remain authoritative. Requirements that
replace no base text — R0-B supporting-stream materialization, synthetic-domain
corpus selection and its hygiene boundary, bounded auxiliary structural
fixtures, and the R0-B payload-fit and fixed-allowance pass conditions (§8),
containment-maxima coverage (§9), freeze representation (§10.1), and downstream
provenance binding (§10.2) — are additive and supersede no base clause.

## 3. Prospective admission digest and symbolic subset counts

For each candidate `N` in `{1000, 2500, 5000, 10000}`, define
`admission_corpus_digest(N)` using **exactly the same bytes and formula as base
§6.5**, over the first N already-sealed candidate indices:

```text
CORPUS_LABEL = ASCII("PROGRAM_K_E2_CORPUS_V1")

corpus_bytes(N) =
    CORPUS_LABEL
    || 0x00
    || protocol_seed
    || uint64_be(N)
    || uint64_be(index_0)
    || uint64_be(index_1)
    || ...
    || uint64_be(index_(N-1))

admission_corpus_digest(N) = SHA256(corpus_bytes(N))
                           # raw 32 bytes where used as seed input
```

This is a prospective use of the existing digest, not a new domain-separated
hash. The ordered prefix, protocol-seed bytes, big-endian integer encoding, label,
and separators are identical to §6.5.

The prospective digest exists only to derive outcome-blind subset membership for
R0 admission projection and for the real-count minimum scale targets of the R0-B
synthetic corpus in §8.
It does not freeze N, generate boards, inspect outcomes or effectiveness, replace
the final `corpus_digest`, or change the candidate stream. It does not regenerate
or substitute candidate indices. If candidate N is later selected, the following
equality is mandatory:

```text
admission_corpus_digest(N) == final §6.5 corpus_digest(N)
```

Apply the **existing frozen §6.6 selector**, with its existing seed formula,
counter/hash/rejection rules and duplicate handling, using
`admission_corpus_digest(N)` in the existing `corpus_digest` input position:

| Set of primary corpus positions | Existing label, exactly | Existing count |
| --- | --- | --- |
| `K_N` | `PROGRAM_K_E2_KCONTROL_V1` | `min(N,256)` |
| `O_N` | `PROGRAM_K_E2_ORACLEB_V1` | `min(N,128)` |
| `D_N` | `PROGRAM_K_E2_DETERMINISM_V1` | `min(N,256)` |

These are the existing K-CONTROL, Oracle-B, and determinism memberships. Define:

```text
U_KD(N) = |K_N union D_N|
I_OD(N) = |O_N intersection D_N|
I_OK(N) = |O_N intersection K_N|
```

All three counts use exactly the same prospective digest and the same frozen
selector memberships. They are exact set counts, determined without generating
boards or inspecting outcomes, and are outcome-blind. Membership depends on the
candidate-specific digest. Do not infer these counts from independence
assumptions, add K and D counts without removing their intersection, or reuse a
different candidate N's membership.

No actual protocol-seed `U_KD`, `I_OD`, or `I_OK` count may be generated before
this amendment is content-frozen and separately accepted. The stricter sequence
in §10 also requires subsequent implementation qualification and commit before
any such real-seed calculation; `I_OK` has exactly the same authorization point
as `U_KD` and `I_OD`. Synthetic seeds may be used in later authorized tests. All
counts remain symbolic in this candidate; no real-seed calculation is part of
contract authoring.

## 4. Four-component wall contract

The four conceptual execution-wall components remain **P/K/O/D**. Wall accounting
is named:

```text
CONSERVATIVE_STANDALONE
```

For each frozen candidate concurrency `c` in `{1,2,4}`, use the same first 64
sealed rehearsal board identities required by base §20.1. These observations are
operational measurements, never effectiveness evidence.

`P64_wall(c)` is the baseline primary CONTROL + K-P0 operational component on
those 64 boards, with optional K/D reference maintenance disabled and Oracle-B disabled
for attribution.

`K64_wall(c)` is the **complete standalone K-CONTROL component interval**. It
includes every prerequisite and target boundary needed by that measurement:

- prerequisite primary setup needed to create the accepted reference;
- setup evidence persistence/readback required by the R0 measurement;
- prior/reference encoding and preparation;
- the K-CONTROL target wave;
- K target persistence/readback/cleanup.

`D64_wall(c)` is the **complete standalone determinism component interval**,
analogously including:

- prerequisite primary setup/reference generation;
- setup persistence/readback;
- prior/reference preparation;
- the determinism target wave;
- D target persistence/readback/cleanup.

Oracle-B is disabled in every P, K, and D baseline calibration, including K/D
prerequisite setup. All Oracle-caused work, including downstream handling of an
Oracle-bearing PRIMARY prior on `O_N intersection K_N` and
`O_N intersection D_N`, is attributed to the route-specific O walls in §5. It
must not be hidden inside, or assumed to be covered by, a P, K, or D baseline
wall. Each standalone boundary must directly cover all required setup,
preparation, target, persistence, readback, and cleanup; a target-only interval
is insufficient. No hidden setup wall may be omitted.

K and D standalone walls intentionally double include their prerequisite setup
on `K_N intersection D_N`. They also include prerequisite primary work despite
the all-N primary term. This is an explicit **conservative upper-bound convention**,
not a claim about the shared Actual-E2 schedule. The same convention permits an
O route boundary (§5) to count an entire directly timed affected phase that also
contains baseline work. It is permitted for wall accounting only. It does not
permit duplicate logical byte ownership.

Every future R0 route measurement, for P, K, D, and each Oracle route in §5,
MUST either:

- **A.** directly reproduce the corresponding Actual-E2 operational phases; or
- **B.** use a documented conservative directly timed boundary that provably
  contains or dominates those phases.

This includes bundle encoding, IPC, validation, coordinator-equivalent admission,
persistence, readback, and cleanup when attributable to that route. R0-only
overhead may make a calibration conservative. Unproven omission of Actual-E2
coordinator work is not allowed.

Do not obtain an attributed component or route wall by subtracting independently
timed whole runs; no subtractive inference from separate whole runs is
permitted. Resource/watchdog/progress/cleanup evidence and complete launcher
measurement remain required by the base protocol.

## 5. Route-specific Oracle walls and execution projection

The accepted execution structure (§12.2) runs primary Oracle-B for each `O_N`
board. For each `O_N intersection K_N` board, K-CONTROL consumes the
Oracle-bearing PRIMARY bundle as its prior. For each `O_N intersection D_N`
board, determinism consumes that Oracle-bearing prior and also runs repeat
Oracle-B. Oracle-enabled evidence therefore changes later operational work as
well as the direct Oracle checks:

- audit-row encoding;
- bundle construction/canonical encoding;
- worker revalidation;
- IPC transmission;
- parent decode/revalidation;
- coordinator revalidation/admission;
- durable Oracle audit persistence/readback/cleanup;
- downstream propagation, decode, and revalidation of an Oracle-bearing PRIMARY
  prior when that board is also in K or D.

P/K/D baseline wall measurements keep Oracle-B disabled, so this work cannot be
left outside O. O remains one conceptual top-level component with three internal
route submeasurements, defined in §§5.1–5.3. Each route wall is a separate
64-unit calibration on the same 64 rehearsal identities, never a reduction to
whatever intersection happens to occur in a rehearsal subset.

Direct observer intervals or directly timed whole affected phases are allowed. If
a whole phase contains baseline work as well, counting the entire affected phase
is allowed as a conservative wall upper bound (§4). The existing direct Oracle
applicability/check timer alone is not a sufficient route boundary (§12.3). No
route wall may be obtained by whole-run subtraction, and no Oracle-caused work
may be hidden inside P, K, or D. Oracle audit persistence belongs to O; coverage
byte ownership is defined in §6 and remains with P/D.

### 5.1 `O64_PRIMARY_ROUTE_WALL(c)`

Written `O64_primary_route_wall(c)` in §5.4, this is a 64-unit Oracle-enabled
PRIMARY route with:

- `oracle_b_selected = true`;
- optional K/D reference maintenance disabled for this calibration
  (`k_control_selected = false` and `determinism_selected = false`).

The measured Oracle route MUST cover all Oracle-caused work from the accepted
Oracle maintenance through verified operational admission, including as
applicable:

- Oracle applicability/check work;
- Oracle audit-row creation/encoding;
- Oracle-bearing bundle construction/canonical encoding, including any
  Actual-E2 encoding of the accepted Oracle-bearing PRIMARY bundle as a
  downstream prior;
- worker revalidation;
- IPC send/receive;
- parent decode/revalidation;
- coordinator-equivalent revalidation/admission;
- Oracle audit persistence;
- readback;
- cleanup.

K/D downstream binding is not included here. Its candidate count is
`min(N,128)`.

### 5.2 `O64_K_BIND_ROUTE_WALL(c)`

Written `O64_k_bind_route_wall(c)` in §5.4, this is a 64-unit operational
calibration of the extra downstream handling required when an Oracle-bearing
PRIMARY prior is consumed by K-CONTROL. Each calibration unit is Oracle-selected
and K-selected but not determinism-selected, so its prerequisite PRIMARY prior is
necessarily Oracle-enabled and carries the rank-0 reference (§12.2). That
prerequisite's own primary Oracle work and reference generation are calibration
prerequisites, not inputs to this route.

The route MUST cover the directly observed Oracle-bearing prior path, including:

- primary-prior encoding/preparation, if not already fully owned by the primary
  O route;
- transfer/spawn argument transport;
- downstream decode;
- downstream revalidation;
- accepted prior binding;
- corresponding parent-side prior binding/revalidation.

The ordinary K solver/target work remains owned by K and is not reclassified as
Oracle work. A whole affected binding/validation phase may be counted
conservatively. No subtraction. Its candidate count is `I_OK(N)`.

### 5.3 `O64_D_REPEAT_ROUTE_WALL(c)`

Written `O64_d_repeat_route_wall(c)` in §5.4, this is a 64-unit operational
calibration for the `O_N intersection D_N` path. Each calibration unit is
Oracle-selected and determinism-selected but not K-selected, so its prerequisite
PRIMARY prior is necessarily Oracle-enabled and carries the rank-0 reference
(§12.2). That prerequisite's own primary Oracle work and reference generation
are calibration prerequisites, not inputs to this route.

The route MUST cover:

- downstream handling of the Oracle-bearing PRIMARY prior by the determinism
  worker/parent, including its transport, decode, revalidation, and binding,
  plus primary-prior encoding/preparation if not already fully owned by the
  primary O route;
- repeat Oracle maintenance;
- repeat Oracle audit-row encoding;
- repeat Oracle-bearing bundle encoding/revalidation;
- IPC;
- parent/coordinator-equivalent validation/admission;
- repeat Oracle audit persistence/readback/cleanup.

The ordinary Oracle-disabled determinism baseline remains owned by D. Directly
timed affected phases may be conservatively inclusive. No whole-run subtraction.
Its candidate count is `I_OD(N)`.

### 5.4 Amended execution projection

The amended execution projection is exactly:

```text
execution_projection(N,c)
    = EXECUTION_WALL_SAFETY_FACTOR * (
          P64_wall(c) * N / 64
        + K64_wall(c) * min(N,256) / 64
        + D64_wall(c) * min(N,256) / 64
        + O64_primary_route_wall(c) * min(N,128) / 64
        + O64_k_bind_route_wall(c) * I_OK(N) / 64
        + O64_d_repeat_route_wall(c) * I_OD(N) / 64
      )
```

The last three terms together form the O component and replace the single base
`O64_wall(c) * min(N,128) / 64` term. No maximum across Oracle routes is formed
for execution wall. There is no fifth execution-wall component, and R remains
bytes-only. The safety factor, launcher ceiling, postprocessing projection
requirements, and N-selection rule remain unchanged. The wall-only conservative
duplicate-inclusion rule remains permitted. Byte ownership remains strictly
non-overlapping.

## 6. Strictly non-overlapping byte ownership

Byte accounting remains:

```text
NON_OVERLAPPING
```

The following table defines exact logical ownership of projected durable
**experiment bundle-stream bytes**: the component bundle streams persisted per
unit under `(position, rank, index)` keys. Distinct persisted worker-rank copies
are distinct durable bytes, even when their record payloads match. Their
existence does not authorize counting the same persisted logical byte twice.

| Component | Owned durable bytes | Exclusions / boundary |
| --- | --- | --- |
| P | Baseline primary durable bytes, including baseline `oracle_b_coverage` with `selected=false`. | No rank-0 `control_maintenance`; no Oracle audit rows. |
| K | K-CONTROL target-worker durable bytes, including its rank-2 copied `control_maintenance`. | No prerequisite primary setup bytes. |
| D | Determinism target-worker baseline durable bytes, including its rank-1 copied `control_maintenance` and repeat coverage with `selected=false`. | No repeat Oracle audit rows; no prerequisite primary setup bytes. |
| O | Oracle audit rows only, for primary or repeat. | Does not own `oracle_b_coverage` or `repeat_oracle_b_coverage`; no setup archive bytes. |
| R | Rank-0 PRIMARY `control_maintenance` stream bytes only, generated/persisted exactly once for every board in `K_N union D_N`. | No K/D worker copies, repeat-generated reference stream, other primary stream, or complete setup archive. |

D retains all other baseline target-worker bytes, including its repeat-generated
`repeat_control_maintenance` stream; that stream is not rank-0 PRIMARY R.

For each component, attribution must account for its actual durable stream/row
representation, including the attributable Actual-E2 key and line framing,
rather than only an in-memory payload estimate or a diagnostic framing.
Calibration setup archives may be observed for operational containment, but
their whole totals are not projected K/D target bytes, O bytes, or R bytes.

The `selected=true` coverage encoding is one canonical byte shorter than the
`selected=false` baseline. This does **not** create a negative O component. P and
D keep their baseline false-coverage ownership, giving a small conservative byte
overestimate. It is a projection convention, not permission to falsify Actual-E2
coverage records. No component may be negative.

One O byte-sizing authority may serve primary and repeat only if implementation
qualification proves it is at least the maximum corresponding measured unit
payload. For normalized archive admission and R0-B sizing, take the conservative
maximum of the corresponding primary and repeat 64-unit audit-only totals and,
separately, of their maximum audit-only unit bytes. This maximum applies to
audit-only bytes only, never to execution wall (§5). Do not substitute a total
for a maximum unit observation. Preserve the existing conservative componentwise
maxima across candidate concurrencies when forming concurrency-independent
archive/sizing authorities.

### 6.1 Supporting operational/provenance bytes

The P/K/D/O/R table partitions experiment bundle-stream bytes only.
Schema-required supporting operational/provenance bytes outside those component
bundle streams are covered by the existing:

```text
FIXED_REPORT_RECEIPT_ALLOWANCE = 268_435_456
```

This includes, as applicable:

- operations/event rows;
- resource-sample rows;
- coordinator receipts/status rows;
- runtime/identity/manifest-style fixed supporting metadata not already inside a
  component's bundle-byte measurement; the per-unit `boards` and `runtime`
  bundle streams remain owned by their P/K/D component.

No byte already included in P/K/D/O/R is owned again by the fixed allowance, and
the allowance's numeric value is unchanged. This is an archive projection
ownership convention, not permission to omit those streams from R0-B. R0-B must
still materialize the schema-required operations/resources/identity supporting
streams so the actual postprocessing/qualification path is exercised, and must
measure the realized bytes of this bucket against the allowance (§8.3).

### 6.2 Zero-row Oracle rule

A scheduled Oracle applicability unit may legitimately produce zero Oracle audit
rows. Future readiness/R0 measurement types MUST therefore permit:

- audit-only durable byte total = 0;
- audit-only maximum unit bytes = 0;

when the corresponding measured route emits no Oracle audit rows. This MUST NOT
convert the scheduled operational unit itself into "not run". Its wall,
applicability, and completion evidence remain explicit, and a zero byte
observation never removes the corresponding route wall. Do not fabricate one byte
or one fake audit row merely to satisfy an existing positive-integer type
invariant. §8 defines the R0-B consequences.

## 7. Archive projection

Define:

```text
archive_projection(N)
    = ARCHIVE_BYTES_SAFETY_FACTOR * (
          P64_bytes * N / 64
        + K64_bytes * min(N,256) / 64
        + O64_bytes * (min(N,128) + I_OD(N)) / 64
        + D64_bytes * min(N,256) / 64
        + R64_bytes * U_KD(N) / 64
      )
      + FIXED_REPORT_RECEIPT_ALLOWANCE
```

`P64_bytes`, `K64_bytes`, and `D64_bytes` are 64-unit attributable totals under
§6. `O64_bytes` is the conservative primary/repeat **audit-only** 64-unit
authority; coverage is excluded, and the value may be zero under §6.2.
`R64_bytes` is the exact attributable 64-unit total of rank-0 PRIMARY
`control_maintenance` stream bytes, taken as the conservative maximum over the
R0 setup routes and candidate concurrencies required by §9. Any route or
concurrency maximum must select among those exact attributable observations.
`FIXED_REPORT_RECEIPT_ALLOWANCE` also covers the supporting bytes in §6.1.

`I_OK(N)` does not appear in the archive projection. The
`O_N intersection K_N` route creates execution-wall overhead only and no new
durable Oracle audit family, because the K-CONTROL target does not persist
Oracle audit rows. The PRIMARY bundle it consumes is persisted once at rank 0
and owned there by P, O, and R as defined in §6.

No setup archive total may substitute for `R64_bytes`. No logical byte may belong
to two projected components. No negative byte component or coverage subtraction
is permitted.

Admission still requires:

```text
archive_projection(N) <= MAX_ARCHIVE_BYTES
```

`MAX_ARCHIVE_BYTES`, the archive safety factor, and the fixed report/receipt
allowance remain unchanged.

## 8. R0-B synthetic families, supporting streams, and minimum payloads

At `Nmax = 10000`, the synthetic non-evidence workload MUST structurally cover
these six **attributable sizing families**, at the realized counts of the
accepted synthetic corpus `S` defined in §8.1:

| Synthetic family | Realized unit count | Real-count minimum scale target | Attributable sizing basis |
| --- | --- | --- | --- |
| `primary` | `10000` | — | P baseline primary |
| `k_control` | `256` | — | K target worker, including rank-2 reference copy |
| `oracle_primary` | `128` | — | Primary Oracle audit rows only |
| `oracle_repeat` | `I_OD_SYN` | `I_OD_SYN >= I_OD(10000)`, with structural floor `>= 1` unless separately covered (§8.1) | Repeat Oracle audit rows only |
| `determinism` | `256` | — | D baseline target worker, including rank-1 copy |
| `reference` | `U_KD_SYN` | `U_KD_SYN >= U_KD(10000)` | R rank-0 PRIMARY `control_maintenance` only |

The synthetic plan also contains `I_OK_SYN` Oracle-bearing K-bind units, with
`I_OK_SYN >= I_OK(10000)` and structural floor `>= 1` unless separately covered
(§8.1). `I_OK_SYN` remains a wall and structural-placement fact, not a seventh
durable Oracle audit sizing family, because the K target persists no Oracle
audit rows (§7).

The real research-corpus values `U_KD(10000)`, `I_OD(10000)`, and `I_OK(10000)`
are minimum scale targets only; the synthetic reference and repeat family counts
are not literally those values. All R0-B postprocessing and archive performance
evidence MUST use the actual realized synthetic counts and MUST NOT silently
substitute the smaller real target counts. The admission argument MUST record
both the real target counts and the realized synthetic counts and prove their
componentwise dominance.

These are the six attributable sizing families, not the complete schema stream
inventory. R0-B MUST additionally generate every schema-required supporting
operations/resources/identity/provenance stream needed by the actual
qualification/readback path; their bytes are covered by the fixed allowance
(§6.1) and checked under §8.3.

Primary and repeat Oracle synthetic streams remain structurally distinct even if
they share one conservative maximum sizing scalar. The reference bucket does not
represent a whole primary/setup worker or either K/D worker's copied stream.
Symbolic count definitions do not authorize calculating their real-seed values
during this authoring phase.

Each synthetic unit payload remains at least:

```text
ceil(R0-A corresponding max attributable unit bytes * 3/2)
```

The corresponding maxima must cover the measured candidate concurrencies. If one
Oracle scalar is shared, it must also cover both primary and repeat maxima; the
same scalar does not collapse the two streams or their distinct counts. A zero
audit-only maximum under §6.2 gives a zero Oracle minimum payload.

The existing full shared **10,000-replicate** G8/G5/G9 bootstrap requirement at
Nmax remains unchanged, including the frozen draws, seed/algorithm, and shared
replicate structure. Aggregation, validation, publication, readback, report
generation, bounded phase progress, and the base complexity contract remain
required. Synthetic R0-B records are never E2 research evidence.

### 8.1 Synthetic-domain corpus and dominance

R0-B MUST use a synthetic corpus `S` that remains outside every research,
rehearsal, holdout, and otherwise reserved index domain prohibited by the
accepted I7 qualification hygiene (§12.1). `S` uses:

- the real frozen protocol seed;
- the unchanged corpus digest function;
- the unchanged frozen K/O/D selector labels and algorithm;
- exactly `Nmax = 10000` synthetic primary positions;
- the synthetic corpus's own ordered indices and the memberships `K_S`, `O_S`,
  and `D_S` derived from them.

Define:

```text
U_KD_SYN = |K_S union D_S|
I_OD_SYN = |O_S intersection D_S|
I_OK_SYN = |O_S intersection K_S|
```

After the separately authorized implementation qualification and commit, and
only after the real protocol-seed target counts may legally be computed (§10),
`S` is acceptable only if:

```text
U_KD_SYN >= U_KD(10000)
I_OD_SYN >= max(I_OD(10000), 1)
I_OK_SYN >= max(I_OK(10000), 1)
```

The `>= 1` structural floor for `I_OD_SYN` or `I_OK_SYN` may instead be met by
an already-required, separately bounded synthetic structural fixture that proves
that route; that route's dominance condition (`I_OD_SYN >= I_OD(10000)` or
`I_OK_SYN >= I_OK(10000)`, respectively) still applies to `S`. If `S` itself
meets the floor, no redundant auxiliary fixture is required for that route. Any
such fixture stays outside the measured Nmax scale totals and must not alter
`archive_projection` or measured postprocessing scale totals; if a realized
count is zero, R0-B performance/archive accounting uses that zero.

The memberships of `S` are the only memberships written into, validated by, and
qualified through its work plan. Exact position equality with the real research
corpus is explicitly **not** required, and the plan validation that re-derives
memberships from the plan's own indices is never bypassed.

R0-B synthetic evidence does not use real E2 primary indices, does not generate
real E2 boards, does not use treatment outcomes, does not inspect effectiveness,
does not use holdout indices, and never becomes E2 research evidence. Its
purpose is operational sizing and qualification only. The accepted I7
research/holdout-domain guard remains a preserved hygiene boundary, not an
implementation nonconformance.

### 8.2 Deterministic synthetic corpus selection

The future implementation MUST define, qualify, and commit a deterministic,
outcome-blind synthetic-corpus search/selection rule **before** real target
counts are calculated. The rule must freeze at least:

- one or more allowed synthetic index domains, all disjoint from the primary and
  rehearsal domains, the holdout, every range of the base §5.3 documented
  exposure registry, and every other domain reserved by the accepted I7 guard;
- a deterministic candidate-corpus enumeration order;
- corpus length `Nmax = 10000`;
- unchanged protocol seed, digest, and selector use;
- a finite search bound;
- a deterministic tie/first-match rule;
- failure behavior.

After `U_KD(10000)`, `I_OD(10000)`, and `I_OK(10000)` are authorized and
computed, those three values may be used **only** as numeric dominance targets
for that already-qualified rule. They may not alter the selector, protocol seed,
candidate-index algorithm, treatment data, board contents, outcomes or
effectiveness, or the frozen search enumeration rule. No board generation or
outcome inspection is needed to select the synthetic corpus.

If the finite deterministic search finds no allowed synthetic corpus satisfying
the required dominance and structural floors, R0-B is **NOT READY** and Actual
E2 is **NOT READY**. There is no fallback to research-domain indices, holdout
indices, selector bypass, membership forgery, count truncation, or cap
loosening.

### 8.3 R0-B pass conditions

For every synthetic unit, the sum of all simultaneously present synthetic family
payloads after the required 3/2 minimum sizing MUST fit inside the frozen
`max_payload_bytes` per-unit payload cap. The check applies to the actual family
combination on that unit, including especially `determinism` plus
`oracle_repeat` and `primary` plus `reference` plus `oracle_primary` where
applicable. If any required synthetic unit cannot fit, R0-B **fails closed** and
Actual E2 is **NOT READY**. Do not split one logical unit into multiple fake
units to evade the cap, reduce the 3/2 minimum, drop a required family, truncate
payload, or raise or loosen `max_payload_bytes` or another frozen cap without
separate adjudication. This is an admission/readiness failure, not permission
to change the experiment.

R0-B MUST measure and record the actual realized bytes assigned to the
`FIXED_REPORT_RECEIPT_ALLOWANCE` bucket, including the schema-required
supporting operational/provenance streams and the report/receipt/manifest
material governed by that allowance, and MUST verify:

```text
realized_fixed_allowance_bytes <= FIXED_REPORT_RECEIPT_ALLOWANCE
FIXED_REPORT_RECEIPT_ALLOWANCE  = 268_435_456
```

If exceeded, R0-B **fails closed** and Actual E2 is **NOT READY**. Unused
P/K/D/O/R budget may not be borrowed to hide an allowance overflow, and the
allowance may not be raised without separate adjudication.

## 9. Required future R0-A observations and unchanged limits

The future qualified implementation MUST expose sufficient directly attributable
facts to determine:

- P64 wall, baseline bytes, and maximum attributable unit bytes;
- K64 complete standalone wall, target bytes, and maximum target unit bytes;
- D64 complete standalone wall, baseline target bytes, and maximum baseline
  target unit bytes;
- `O64_primary_route_wall(c)` (§5.1), primary audit-only bytes, and maximum
  primary audit-only unit bytes;
- `O64_k_bind_route_wall(c)` (§5.2), a wall-only observation with no durable
  Oracle audit bytes;
- `O64_d_repeat_route_wall(c)` (§5.3), repeat audit-only bytes, and maximum
  repeat audit-only unit bytes;
- R64 rank-0 PRIMARY `control_maintenance` bytes and maximum attributable unit bytes;
- all existing memory, watchdog, cap, progress, readback, and cleanup facts.

Each Oracle route wall is a separate execution-projection input with its own
candidate count (§5.4); no wall maximum across Oracle routes is formed. For
normalized archive admission and R0-B sizing, O64 audit-only bytes and maximum
audit-only unit bytes use the conservative maximum of the corresponding primary
and repeat observations (§6); either may be zero under §6.2. Wall, 64-unit byte
total, and maximum unit bytes are separate measured quantities. R is
**bytes-only**; no fifth execution-wall component is introduced.

The R64 total and maximum-unit authority MUST conservatively cover every R0 setup
route capable of producing the rank-0 PRIMARY `control_maintenance` stream,
including K setup, D setup, the Oracle-enabled prerequisite setups of the §5.2
K-bind and §5.3 Oracle-repeat routes, and any other R0 setup that creates the
same rank-0 family. Take the conservative maximum across those routes and
candidate concurrencies. Do not substitute complete setup archive bytes.

The R0-A containment and operational maxima used by readiness MUST include every
authorized calibration route: P, K standalone, D standalone, the O primary
route, the O K-bind route, the O D-repeat route, and every Oracle-enabled
prerequisite setup used by those routes. This applies to every relevant existing
containment fact or cap, including memory, watchdog/case/launcher limits,
paired-board or route wall limits where applicable, payload maxima, and
resource/progress/cleanup completeness. No calibration route may be omitted
merely because its wall belongs internally to O.

The base §21.2 values remain exactly:

```text
EXECUTION_WALL_SAFETY_FACTOR       = 2.0
POSTPROCESS_WALL_SAFETY_FACTOR     = 2.0
ARCHIVE_BYTES_SAFETY_FACTOR        = 1.5
MEMORY_SAFETY_FACTOR               = 1.5

MAX_ACTUAL_E2_LAUNCHER_WALL        = 12 hours
MAX_COMBINED_MEMORY_BYTES          = 4_294_967_296
MAX_ARCHIVE_BYTES                  = 17_179_869_184
FIXED_REPORT_RECEIPT_ALLOWANCE     =    268_435_456
```

All other existing provisional/final caps and ceilings remain unchanged. The
largest-admitted-N rule and its throughput/concurrency tie-breaks are unchanged;
effectiveness is not an admission input.

## 10. Governance, acceptance, and freeze sequence

The following sequence is mandatory; later steps cannot be inferred from earlier
ones:

1. Author the candidate document. This work unit stops at an unfrozen candidate.
2. Obtain an independent **read-only audit of the exact candidate bytes**, bound
   to their SHA-256 and byte length.
3. Obtain ChatGPT/user adjudication of that candidate and the audit findings.
   Authorship, an internal completeness check, or AI interpretation is not acceptance.
4. Content-freeze the adjudicated amendment with SHA-256 and the external
   content-freeze receipt described in §1, recording separate acceptance
   explicitly in that receipt. Any change after content freeze requires re-audit
   and re-freeze; an earlier digest cannot identify changed bytes. If
   adjudication requires edits, audit the resulting exact bytes before their
   freeze; §10.1 applies to the status header.
5. Only after freeze and acceptance may a separately authorized implementation
   work unit change readiness/R0-PRE code. This document itself does not authorize
   those source/test edits.
6. Only after that implementation, including the deterministic synthetic-corpus
   selection rule of §8.2, is qualified and committed may actual protocol-seed
   `U_KD`, `I_OD`, and `I_OK` counts be computed; for R0-B they are then passed
   only as numeric dominance targets into that already-qualified rule. Preserve
   outcome blindness and bind the prospective/final digest equality; no
   real-seed shortcut is authorized during document review or implementation
   qualification.
7. Only after an accepted harness and separate real-R0 authorization may real
   R0-A/R0-B execute. Synthetic seed tests do not grant real-R0 authorization.
8. Actual E2 remains separately authorized later, subject to accepted R0 evidence
   and its separately frozen operating envelope. E3 and Gate P remain outside
   this amendment's authority.

### 10.1 Freeze representation

The exact content-frozen amendment bytes MAY intentionally retain the
`CANDIDATE — NOT CONTENT-FROZEN / NOT ACCEPTED` authoring header. Freeze and
acceptance authority then live exclusively in the external content-freeze
receipt. After receipt acceptance, the header is historical authoring text, not
the live freeze-state authority. Editing the header at freeze time would change
the SHA-256 and therefore requires another exact-byte audit before freeze. Do not
edit the status line merely during freeze unless the resulting bytes are
re-audited.

### 10.2 Downstream provenance binding

Later authoritative artifacts MUST record:

- `AMENDMENT_SHA256`;
- the exact amendment byte length;
- the external freeze-receipt identity/reference;
- the frozen base protocol identity (commit, blob, and SHA-256 in §1).

At minimum, bind these into:

- R0 evidence / manifest;
- the R0 admission decision;
- the selected E2 Operating Envelope;
- the Actual-E2 manifest, if Actual E2 is later authorized.

This is provenance only. It changes no research semantics and supersedes no base
clause.

## 11. Explicit non-goals

This amendment does **not**:

- reorder or supersede the base §2 authority order;
- change the frozen protocol bytes or protocol seed;
- change K/O/D subset labels;
- change selector PRNG/hash/rejection rules or duplicate handling;
- change candidate indices or their order;
- change treatment actions or treatment policy;
- change Model C;
- change G5/G8/G9 or any research threshold/effect gate;
- change bootstrap draws, replicates, algorithm, or shared-stream structure;
- change safety factors or caps;
- change the fixed report/receipt allowance value;
- authorize copy-by-reference persistence in place of separately durable copies;
- authorize Actual E2;
- authorize E3 or Gate P.

It also grants no immediate R0 or implementation authority and does not accept
the current uncommitted R0-PRE candidate.

## 12. Source basis and attribution rationale

The following sources were read as text, without executing repository code or
tests. Frozen-protocol references are to the exact commit/blob/SHA-256 in §1.
Committed I7 qualification and I8 readiness references are to accepted parent
`9071469e2e4a884722ea02e2faea3441d916876c`. Current audit/execution/operational
sources and their current tests include uncommitted R0-PRE work; citations to
them are observations, not acceptance. Line numbers identify the inspected
snapshots. Where this section records a difference between current source/tests
and the replacement semantics, such as I8's four-family projection (§12.1) or the
R0-PRE gaps (§12.3), it records current-implementation fact; after acceptance,
§1 classifies that difference as implementation nonconformance, not as a reading
of this amendment. The accepted I7 research/holdout-domain guard is not such a
difference: it is a preserved hygiene boundary (§8.1).

### 12.1 Frozen protocol, committed I7, and committed I8

- [Frozen E2 protocol](STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md), §2
  (lines 126–142) defines the authority order that this amendment leaves
  unchanged; §6.5 (396–420) specifies the exact corpus digest and its original
  post-N-freeze timing; §6.6 (422–463) specifies the unchanged selector/labels.
  §§15.1, 16.4, and 16.5 retain K/O/D counts. §§20.1, 20.3, 21.3, 21.4, and 21.6
  contain the affected operational attribution clauses. §9 and §21.2 preserve
  bootstrap and safety/cap authority. The prospective digest resolves the
  admission dependency without changing those identity bytes or research rules.
- [Committed I8 readiness](../../experiments/program_k_e2_readiness.py), lines
  245–283 at the accepted parent, defines only four sizing families:
  `primary`, `k_control`, `oracle_b`, `determinism`, with counts
  `(10000,256,128,256)`. Its `_scaled`/projection functions (383–413) likewise use
  four multipliers, and archive projection takes componentwise maxima across
  concurrencies. `ComponentMeasurement` requires positive wall, durable bytes,
  and maximum unit bytes (149–150), and `ComponentSizes` requires positive unit
  sizes (252–254), although the `ComponentMeasurement` description (137–138)
  states that an Oracle-B unit without an applicable private comparison still
  has a completed operational path. I8 therefore requires a later implementation
  update for route-specific Oracle walls with `I_OK`/`I_OD` multiplicities,
  separate Oracle primary/repeat structural streams, rank-0 R union accounting,
  and zero-byte audit-only Oracle observations. No such update is implemented or
  accepted here.
- [Current readiness tests](../../tests/test_program_k_e2_readiness.py), lines
  245–255, 301–306, and 318–335, assert the existing four-family sizing and
  projection contract. Lines 257–299 require complete Nmax/bootstrap/phase facts,
  and lines 157–161 reject zero component wall/byte values. These tests were
  inspected, not run; they do not certify the proposed amendment.
- [Committed I7 qualification](../../experiments/program_k_e2_qualification.py),
  the inspected durable-layout reader, requires every stream file, including
  `operations`, `resources`, and `qualification_identity` (60–61, 543–551). It
  validates identity rows (552–558), operation events (`_events`, 448–512), and
  resource samples (601–620), binds each D/K unit to its primary premise
  (594–596), and caps each reconstructed unit payload (576). R0-B therefore must
  materialize those supporting streams even though §6.1 assigns their bytes to
  the fixed allowance, and must fit each composite unit under that payload cap
  (§8.3).
- I7 `_plan` (142–155) requires the real protocol seed (144) and rejects every
  board index in the primary/rehearsal research domain or the holdout domain
  (151–154). [Current execution source](../../experiments/program_k_e2_execution.py)
  `make_work_plan` (129–143) derives the K/O/D memberships from the plan's own
  ordered indices, corpus digest, and frozen selector, and `revalidate_work_plan`
  (146–157) rejects any plan whose memberships differ; `validate_work_plan`
  applies that check in I7 `_plan` (143) and in the Actual-E2 coordinator
  (operational source 109–115, 1326). A synthetic plan outside the protected
  domains therefore necessarily has its own memberships: exact matching of the
  real N=10000 membership positions was infeasible without bypassing that
  validation or using research-domain indices, and it is removed. The
  synthetic-domain dominance design of §§8.1–8.2 preserves the I7 guard.

### 12.2 Accepted execution structure visible in current sources

- [Current execution source](../../experiments/program_k_e2_execution.py), lines
  593–595, creates PRIMARY `control_maintenance` under
  `k_control_selected or determinism_selected`. [Current operational source](../../experiments/program_k_e2_operational.py),
  `_kinds` (118–124) and `_workflow` (770–784), runs one primary worker before
  selected targets. Together these establish once-per-`K_N union D_N` PRIMARY
  reference generation, not one rank-0 stream per K and another per D.
- Current execution source, lines 695–697, retains primary `control_`/`kp0_`
  streams in the determinism bundle; lines 987–991 explicitly copy
  `control_maintenance` into K-CONTROL. Current operational source assigns
  PRIMARY/DETERMINISM/K_CONTROL ranks 0/1/2 (127–129) and persists every bundle
  stream using `(position, rank, index)` keys (836–856). Consequently the rank-1
  and rank-2 copies remain separately durable in D and K, while R owns only the
  once-per-union rank-0 stream. [Current execution tests](../../tests/test_program_k_e2_execution.py),
  lines 918–950, inspect this three-worker stream roundtrip contract.
- Current execution source, `execute_repeat` (684–697), runs only for D-selected
  work and invokes `_run_pair` with that work's existing Oracle membership.
  `_run_pair` (596–605) enables Oracle-B with `oracle_b_selected`. Thus repeat
  Oracle runs on `O_N intersection D_N`, in addition to primary O. Current
  execution tests (559–585) distinguish primary/repeat coverage and unselected
  audit absence.
- Current execution source, `execute_k_control` (970–991), runs only for
  K-selected work and revalidates the primary prior with that work's existing
  Oracle membership (978); its bundle streams (989–991) include no Oracle audit
  stream. `execute_repeat` revalidates its prior the same way (689). That
  revalidation (`revalidate_bundle`, 322–417) decodes every prior row, including
  Oracle audit rows, in its generic loop (351–355) and raw status scans
  (401–408), and calls `_validate_k_children` (420–440), which requires the
  prior's coverage selection to equal the work's Oracle membership (429–430) and
  decodes the Oracle children (434–437). An Oracle-selected K or D unit therefore
  needs an Oracle-bearing prior, so both `O_N intersection K_N` and
  `O_N intersection D_N` add downstream Oracle-bearing prior handling; only the
  latter adds a durable repeat Oracle audit family.
- Prior propagation is structural as well. `_workflow` encodes each primary
  bundle returned by its supervisor as the downstream prior, whether or not a K
  or D target follows (782–783). `_supervise_operation` passes those bytes to the
  spawned worker as a process argument (477–479); `_worker_main` decodes them
  (299) before `execute_repeat` or `execute_k_control` (301, 304); and the
  parent's `_bind_prior_bundle` decodes and revalidates the prior again (450–452)
  when it accepts the downstream result (654).
- Oracle rows also add primary-route validation and IPC work. They are encoded at
  execution source line 605; `_bundle` revalidates the constructed bundle (536);
  the worker revalidates it again (operational source 309) and sends its
  canonical encoding (317) through acknowledged frames (211–228); the parent
  decodes and revalidates it (652–653); and the Actual-E2 coordinator revalidates
  every returned bundle once more (1405–1408) before admission (1416). These
  routes justify the route-specific O walls and their `min(N,128)`, `I_OK(N)`,
  and `I_OD(N)` counts.

### 12.3 Unaccepted R0-PRE measurement gaps

- Current operational source's `R0ComponentMeasurement` description (1003–1011)
  expressly excludes K/D setup from target walls. Setup execution and
  persistence/readback (1229–1238) and prior encoding (1239–1244) precede
  `target_started` (1245); the reported target interval is accumulated at
  1304–1305. [Current operational tests](../../tests/test_program_k_e2_operational.py),
  lines 920–952, assert this setup-before-target boundary. It is insufficient for
  the complete standalone wall contract proposed here and must later be corrected.
- The R0-PRE direct Oracle timer in [current audit source](../../experiments/program_k_e2_audit.py)
  (`audit_k_p0`, 360–379) brackets only the Oracle applicability/check blocks and
  reports one closed fact after the audit (400–404). Audit-row encoding and every
  later validation, IPC, admission, persistence, and downstream step lie outside
  those intervals.
- Current operational `_persist_r0(..., oracle_only=True)`, the R0-PRE Oracle-only
  writer, iterates both `oracle_b_coverage` and `oracle_b_audits` (1137), with
  their combined byte total returned at 1161. Current operational tests (954–975,
  especially 969–971) expect both files. The writer therefore includes coverage
  today. It also keys every row as `(index,)` (1142, 1145), a diagnostic framing
  that differs from the Actual-E2 component framing `(position, rank, index)`
  (836–856). Its unit wall is only the direct Oracle interval total plus the
  Oracle-only persistence interval (1293–1294), and the component wall adds those
  persistence intervals to the union of the Oracle intervals (1272–1275, 1307).
  It therefore does not yet account for all Oracle-caused audit-row encoding,
  bundle revalidation, IPC, parent/coordinator validation, or downstream
  `O_N intersection K_N` / `O_N intersection D_N` prior handling. It must later
  be corrected to audit-only O byte ownership with Actual-E2 framing, P/D
  retaining their false-coverage baseline, and the route boundaries in §5.
- Current operational `_persist_r0` for non-Oracle P/K/D persistence (1121–1128)
  returns the whole `_EvidenceSink.byte_length`, and `_EvidenceSink.admit` adds
  resource samples (857–860), an END/ERROR event (863–864), and, for an admitted
  primary, a progress event (867–871) beside the bundle streams (836–856).
  Current R0-PRE P/K/D byte totals may therefore include supporting operational
  rows that §6.1 assigns to the fixed allowance; they are not yet the final
  non-overlapping P/K/D attributable-byte measurements and must later be
  corrected.
- Current observed-Oracle routing permits only PRIMARY
  (`R0_ORACLE_PRIMARY_ONLY`, operational source 292–294), and the worker's Oracle
  observer accepts only the non-repeat K-P0 arm (245). `_r0_work` (1040–1043)
  creates works with at most one subset flag set, and current operational tests
  (893–900) do not establish an Oracle repeat R0 calibration. No current R0
  route calibrates K-bind or D-repeat Oracle-bearing prior handling. The
  execution-layer repeat observer test (execution tests 411–434) does not close
  that operational gap. The three Oracle route observations, zero-row Oracle
  measurement types, conservative audit-only byte normalization, the
  deterministic synthetic-corpus selection rule, and the R0-B pass conditions of
  §8 remain future implementation obligations; this document does not claim
  that any of them exists.

These findings distinguish accepted persistence/execution structure from
unaccepted measurement changes. They neither accept a current correction nor
report an R0 result; no implementation correction for any gap above is claimed.

## 13. Authoring boundary and review disposition

The first candidate bytes (27,545 bytes, SHA-256
`ebe5a534e5e22e6036d4869cc4c8f90b50653eff9025e37064cb13f7d7ef1cae`) received an
independent read-only exact-byte audit with BLOCKER 0 / REQUIRED 2: an Oracle
wall boundary that omitted Oracle-caused validation, IPC, and downstream prior
work, and a global authority order that contradicted base §2. The first
correction restored base §2 authority and stated the accepted amendment's
normative status relative to current source/tests (§1), replaced the single
normalized Oracle wall with route-specific Oracle walls and `I_OK` (§§3, 5), and
added the fixed-allowance ownership, zero-row, R64 source, wall-dominance,
freeze-representation, and provenance clarifications (§§4, 6–10).

Those corrected bytes (47,905 bytes, SHA-256
`dfa9324caf21c6a78e4b9d20fa52af8c5001497a64e82108c6ac086eb35e2831`) received an
independent exact-byte re-audit with BLOCKER 0 / REQUIRED 1 / OPTIONAL 6: the
R0-B rule requiring the exact real N=10000 membership positions was infeasible
through the accepted I7 qualification path. This revision is a document
correction of that candidate. It replaces exact-position placement with the
synthetic-domain dominance rule and deterministic synthetic-corpus selection
(§§8.1–8.2), distinguishes real target counts from realized synthetic counts
(§8), adds the R0-B payload-fit and fixed-allowance pass conditions (§8.3) and
containment-maxima coverage (§9), records the R0-PRE supporting-row overlap
(§12.3), and clarifies the authority wording (§1). Identifier-width hardening
remains optional and is not added. Neither prior candidate was frozen or
accepted, and neither prior digest identifies these bytes; both are historical
audit input only.

The only authorized change in this correction work unit is this amendment file.
The existing dirty R0-PRE files must remain byte-identical to entry:

| Existing dirty path | Entry SHA-256 |
| --- | --- |
| `experiments/program_k_e2_analysis.py` | `5a60a9f68bb21a0f2ca12bd9c720a6e4931021339741c454fb055c5754f4d9e7` |
| `experiments/program_k_e2_audit.py` | `f6ba6a06a76c749a5a5ab9d52eaf1e21ba079888f33374b6f597097b4ef05bbd` |
| `experiments/program_k_e2_execution.py` | `099ca9d76166af7a50abf1a41c0a4862219431f5352ddf97367c0f1ded5e083e` |
| `experiments/program_k_e2_operational.py` | `a46f380567bbf0b2151ef78e4f713f0374f4d8f5e989e3aa26f0fa1bbdf0fec3` |
| `tests/test_program_k_e2_analysis.py` | `303babfc75065ca443f9c40b0a0f8a359e40950a7774e51e876c6597218f33b3` |
| `tests/test_program_k_e2_audit.py` | `de65634d6e9f46d52fc52ea2f35df046c20e4022c69bf3b1e7c9d476ddc9e4d9` |
| `tests/test_program_k_e2_execution.py` | `00ed698e341dd6ef1456da38d316826707e967cfc9f1866939f52e34e662c814` |
| `tests/test_program_k_e2_operational.py` | `ae8a0b631b8443804652171420211c3ef4dae936ce9dc258ecd78e05e8378da3` |

End-of-authoring verification must compare those hashes, verify no other file
change or untracked path, zero staged files, unchanged HEAD/origin, a passing
`git diff --check`, and no new R0/result root. No implementation, source/test
modification, test execution, board generation, holdout access, R0-A/R0-B,
Actual E2, real-seed candidate/subset calculation (including `U_KD`, `I_OD`, or
`I_OK`), or git add/commit/push belongs to this work unit.

Open obligations are independent exact-byte re-audit of these revised bytes,
ChatGPT/user adjudication, content freeze and separate acceptance, followed only
then by separately authorized implementation qualification and later operational
work. This document's disposition is **candidate for content review**, not
self-freeze, self-acceptance, harness acceptance, or operational readiness.
