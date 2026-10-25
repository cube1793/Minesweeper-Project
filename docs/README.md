# Project Documentation Index

현재 문서의 위치와 authority를 찾기 위한 인덱스다. 과거 문서는 당시의
provenance로 읽고, 현재 상태는 `CURRENT_HANDOFF.md`와 각 최신 closeout을 우선한다.

## Current recovery / navigation

- [Current project handoff](CURRENT_HANDOFF.md): 현재 milestone, 닫힌 기준선, 다음 필수 작업.
- [Project README](../README.md): 실행 방법, 주요 기능과 프로젝트 개요.
- [Architecture](../ARCHITECTURE.md): Engine/UI/Replay/analysis/worker 책임 경계.
- [Building](../BUILDING.md): Windows PyInstaller 빌드와 package 검증 절차.
- [Stage-3 Extended index](stage3-extended/README.md): Extended roadmap와 각 milestone 상태.

## Stage 1 / Stage 2 / Pre-Stage3 — CLOSED

공통 앱/Replay/ZiNi/Stage-2 실행 구조와 telemetry/benchmark 기반은 root 문서와
아래 Pre-Stage3 명세에서 확인한다.

- [Pre-Stage3 telemetry specification v2](../PRE_STAGE3_TELEMETRY_SPEC_v2.md)
- [Pre-Stage3 telemetry specification v2 — 한국어](../PRE_STAGE3_TELEMETRY_SPEC_KO_v2.md)

## Stage-3 V1 — CLOSED / FROZEN

**FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED**

- [Stage-3 V1 record / preservation guide](stage3-v1/README.md)
- [Stage-3 V1 final adjudication](stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)
- [Frozen algorithm specification v1](../STAGE3_ALGORITHM_SPEC_v1.md)
- [Frozen telemetry / benchmark specification v1](../STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md)
- [Stage-3 historical handoff](../STAGE3_HANDOFF.md)

Historical design / implementation:

- [Algorithm specification draft v1.1](../STAGE3_ALGORITHM_SPEC_DRAFT_v1.1.md)
- [Implementation Slice A](../STAGE3_IMPLEMENTATION_SLICE_A.md)
- [Specification freeze adjudication](../STAGE3_SPEC_FREEZE_ADJUDICATION.md)
- [Replay validation protocol v1.1 amendment](../STAGE3_REPLAY_VALIDATION_PROTOCOL_V1_1_AMENDMENT.md)

Validation / audit:

- [B7 pilot report](../STAGE3_B7_PILOT_REPORT.md)
- [B7-C compute diagnostics](../STAGE3_B7C_COMPUTE_DIAGNOSTICS.md)
- [B9 independent Claude audit](../STAGE3_B9_CLAUDE_INDEPENDENT_AUDIT.md)
- [Archived Slice-B B8 adjudication](archive/stage3-v1/STAGE3_SLICE_B_B8_ADJUDICATION.md)
- [Archived Slice-B final adjudication](archive/stage3-v1/STAGE3_SLICE_B_FINAL_ADJUDICATION.md)

## ZiNi Improvement — CLOSED

- [ZiNi Improvement index](zini-improvement/README.md)
- [ZiNi Improvement final adjudication](zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md)

The final quality holdout `2,010,000 .. 2,010,099` remains forbidden/unopened.

## Stage-3 Extended — ACTIVE

Start from:

- [Stage-3 Extended README](stage3-extended/README.md)
- [Program K research specification — FROZEN / ACCEPTED](stage3-extended/STAGE3_PROGRAM_K_RESEARCH_SPEC.md)
- [Program K Gate-R E0/E1 research protocol — FROZEN / ACCEPTED](stage3-extended/STAGE3_PROGRAM_K_GATE_R_PROTOCOL.md)
- [Program K Gate-R E1 closeout — FINAL PASS / ACCEPTED](stage3-extended/STAGE3_PROGRAM_K_E1_CLOSEOUT.md)
  — E0/E1 implementation qualification CLOSED; effectiveness remains an E2 question.
- [Program K E2 Effectiveness Protocol — FROZEN / ACCEPTED](stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md)
- [Program K E2 R0 Attribution Amendment v1 — CONTENT-FROZEN / ACCEPTED](stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md)
- [Stage-3 Extension Backlog](../STAGE3_EXTENSION_BACKLOG.md): candidate ideas only;
  not an implementation priority list.

Closed milestones / durable closeouts:

- [Visualizer Foundation acceptance](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)
- [Visualizer Foundation final adjudication](stage3-extended/STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md)
- [Identity Separation closeout](stage3-extended/STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md)
- [Modeled-Time Playback closeout](stage3-extended/STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md)
- [Human Mouse Trace closeout](stage3-extended/STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md)
- [Same-board Comparison contract](stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md)
- [Same-board Comparison closeout](stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md)
- [Timeline Analytics contract](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CONTRACT.md)
- [Timeline Analytics closeout](stage3-extended/STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md)
- [Selected Exemplar Viewer contract](stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CONTRACT.md)
- [Selected Exemplar Viewer closeout](stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md)
- [Visualization Usability Polish closeout](stage3-extended/STAGE3_VISUALIZATION_USABILITY_POLISH_CLOSEOUT.md)
  — CLOSED; Same-board usability and Visualizer reference overlays accepted at
  `31630dd6ffa2301c41534fca3b003838d865f313`.
- [Fixed-Exemplar Human/Domain Interpretation closeout](stage3-extended/STAGE3_FIXED_EXEMPLAR_INTERPRETATION_CLOSEOUT.md)
  — FINAL ACCEPTANCE PASS / CLOSED; BLOCKER 0 / REQUIRED 0; additional gameplay NONE.

### Current Program-K state / next work

Milestones **1–9 remain CLOSED**. Milestone **10 — Program K: Logical Known-Mine
Capability + Selective Physical Materialization** remains **ACTIVE**.
Current state as of **2026-10-26 (Asia/Seoul): PRE-ACTUAL-E2 — REAL R0-A CLOSED**.
Program K is the whole research program; E2 is its effectiveness experiment;
Gate P is later production/integration qualification after E2/any required E3.

Gate-R E0/E1 implementation qualification is **CLOSED / ACCEPTED**. Actual E1 is
**E1_PASS / E1_QUALIFIED / ACCEPTED**, `progression_allowed = true`; the
[E1 closeout](stage3-extended/STAGE3_PROGRAM_K_E1_CLOSEOUT.md) remains the
historical evidence authority. Program K effectiveness is still **NOT ESTABLISHED**.

The [E2 Effectiveness Protocol](stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md)
remains **FROZEN / ACCEPTED — CONTENT FREEZE PASS / BLOCKER 0 / REQUIRED 0**.

Program K E2 implementation slices **I1–I8 are 8/8 COMPLETE / ACCEPTED**.
The [R0 Attribution Amendment v1](stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md)
is **CONTENT-FROZEN / ACCEPTED**. Amendment conformance (`cdba3513`), the accepted
N=10000 target counts/synthetic selection, and setup-containment repair (`e6593f7`)
are complete/accepted.

**R0 harness implementation — FINAL ACCEPTANCE PASS / COMMITTED / PUSHED** at
`7e7f847816fedb77cef67b576eab665afabfbfbf` (`7e7f847`),
`feat: add Program K E2 R0 harness`; **BLOCKER 0 / REQUIRED 0 / OPTIONAL 0**.
Accepted historical full-source qualification: **4117/4117 PASS**
(`4111 MAIN + 6 ISOLATED`). Exact identities, receipts and qualification history
are in the [current handoff](CURRENT_HANDOFF.md).

The verified source baseline before this documentation refresh is
`c0bc270bce1996797f9ecec80e79ea8998d3205d` (`c0bc270`): `main` / local
`origin/main` aligned, ahead/behind **0/0**, clean index/worktree.

**Real R0-A: COMPLETE / INTEGRITY PASS / EVIDENCE ACCEPTED / CLOSED — NO RERUN.**
Its accepted evidence is **OPERATIONAL NON-EFFECTIVENESS** evidence. Subsequent
read-only static review confirmed both the **execution-wall admission blocker**
and the **R0-B whole-archive capacity blocker**; exact evidence, calculations and
authority are recorded in the [current handoff](CURRENT_HANDOFF.md) and
[Extended README](stage3-extended/README.md).

**Real R0-B: NOT RUN / NOT AUTHORIZED**; it has not failed an executed run.
**Complete R0 adjudication: NOT DONE.** Final N/concurrency: **NOT SELECTED**;
final Operating Envelope: **NOT SELECTED / NOT FROZEN**. E2 PASS/FAIL/DEFER: **NONE**.
**Actual E2: NOT RUN / NOT AUTHORIZED. Program K effectiveness: NOT ESTABLISHED.**
E3 is conditional/not triggered; Gate P, production integration and native K
visual acceptance are not started. Program K final closeout is not done;
Stage-3 Extended remains **ACTIVE**.

**NEXT:** source-only / read-only engineering investigation and a remediation
proposal for ChatGPT/user adjudication. No automatic R0-B, envelope freeze or
Actual-E2 execution follows the accepted R0-A evidence. Later operational work
requires blocker resolution/adjudication and separate authorization; preserve the
closed R0-A evidence unchanged.

Recovery order:
[CURRENT_HANDOFF](CURRENT_HANDOFF.md) →
[Extended README](stage3-extended/README.md) →
[frozen E2 protocol](stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md) →
[frozen R0 Attribution Amendment](stage3-extended/STAGE3_PROGRAM_K_E2_R0_ATTRIBUTION_AMENDMENT_v1.md) →
current source/tests for disputed implementation facts.
Do not repeat E2-D0/protocol/amendment audits, E0/E1 execution, official 100k,
E/L, accepted P-8/R3/F1 or closed Viewer/Timeline/Polish work merely for recovery.
The ZiNi final holdout `2,010,000 .. 2,010,099` remains unopened/excluded.

## Experiments

- [E/L policy pilot](../experiments/STAGE3_E_L_POLICY_PILOT.md)

The E/L pilot is historical/experimental evidence, not the current production planner.
Its historical source provenance and the explicitly reviewed compatible Engine identity
remain distinct.

## Document-location / evidence policy

- Do not relocate frozen Stage-2 / Pre-Stage3 / Stage-3 V1 records merely for neatness.
- New Stage-3 Extended documentation normally belongs under `docs/stage3-extended/`.
- Official benchmark/evidence roots are not documentation-cleanup targets.
- Large DB/JSONL/result/package trees stay in their established locations.
- `results/` acceptance roots are evidence, not substitutes for tracked closeout documents.
- Current Git source/tests outrank stale uploaded snapshots.
