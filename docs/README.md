# Project Documentation Index

현재 문서의 위치와 authority를 찾기 위한 인덱스다. 과거 문서는 당시의
provenance로 읽고, 현재 상태는 `CURRENT_HANDOFF.md`와 각 최신 closeout을 우선한다.

## Current recovery / navigation

- [Current project handoff](CURRENT_HANDOFF.md): 현재 source 수용, 닫힌 기준선, 커밋 준비와 다음 작업 선정 경계.
- [Project README](../README.md): 실행 방법, 주요 기능과 프로젝트 개요.
- [Architecture](../ARCHITECTURE.md): Engine/UI/Replay/analysis/worker 책임 경계.
- [Building](../BUILDING.md): Windows PyInstaller 빌드와 package 검증 절차.
- [Stage-3 Extended index](stage3-extended/README.md): 현재 Extended roadmap/index와 closeout 안내. 현재 상태 복구는 [CURRENT_HANDOFF](CURRENT_HANDOFF.md)를 우선한다.

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
- [Program K remediation design V1.3.1 — exact frozen bytes](stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1.md)
- [Program K V1.3.1 acceptance receipt — design-boundary authority / FINAL DESIGN ACCEPTED](stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1_ACCEPTANCE.md)
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

As of **2026-11-02 (Asia/Seoul)**, milestones **1–9 are CLOSED** and the separate
Program K research visualization/comparison path **D0–D5 is FINAL ACCEPTANCE
PASS / CLOSED**, including implemented D4 and final user packaged A–H PASS.

Post-D5 bounded work is recorded separately:

- [K-LC1 / SINGLETON_BAND_V1 closeout](stage3-extended/STAGE3_K_LC1_SINGLETON_BAND_V1_CLOSEOUT.md):
  별도 실험적 source checkpoint. 복구4 starts/4완주, Claude R2 PASS, 외부 저장 viewer,
  8191 완료145→153의 O(23,0) 자연스러움과97 무변화에 대한 **제한된 사용자 확인**.
  미보고 native 제스처·일반 효과성·production으로 확대하지 않는다.

- [K-LC0 / DISTANCE_BAND_V1 closeout](stage3-extended/STAGE3_K_LC0_DISTANCE_BAND_V1_CLOSEOUT.md):
  native survivors/21/20 band와 혼합3보드6회, Claude PASS, 고정 viewer의 당시 사용자 경로 확인.
  옛 viewer는 원316파일 raw hash에 묶인 역사적 도구이며 현재 문서5불일치로 새 로딩이 거부된다.
- [K-LC0 Random Expert 비교 closeout](stage3-extended/STAGE3_K_LC0_RANDOM_EXPERT_COMPARE_CLOSEOUT.md):
  actual K-P0→active K-LC0 새 실행/JSON/재생, 별도5 pair, Claude 최종54/54 및 R-1 정정,
  **2026-11-02 사용자 native 수용**. K-LC0 freeze·일반 효과성·production 수용이 아니다.
- [Human pacing JSON V1 closeout](stage3-extended/STAGE3_HUMAN_PACING_JSON_V1_CLOSEOUT.md):
  canonical 30-game arithmetic / independent Claude PASS; presentation reference only.
- [Random Expert Exhibition V1 source closeout](stage3-extended/STAGE3_RANDOM_EXPERT_EXHIBITION_V1_CLOSEOUT.md):
  new public-corpus V1/K-P0 execution, RF-1~3 re-review PASS, UI feedback and the
  user's subsequent **2026-11-01 native source reacceptance**. No new package or Main integration.

- [Program K research-demo closeout](stage3-extended/STAGE3_PROGRAM_K_RESEARCH_DEMO_CLOSEOUT.md):
  D0–D5, immutable K/CONTROL adapters, exact pairs, independent playback, final
  R1/R2 Korean UI, final package identity, regression and user acceptance.
- [Current handoff](CURRENT_HANDOFF.md): concise recovery record and current next.
- [Extended Program K history](stage3-extended/README.md#current-program-k-boundary):
  E0/E1, E2 I1–I8, R0/amendment/harness, historical static blocks and Fresh V2 results.

Final **D5** visualization/package source is `fb59d5fa253f04f50ea57c6a9e863aa1999a517e`;
`05920abeaec541a52fd22753dadec66f5cb98bca` is the earlier historical visualization
anchor. Remediation technical anchor `48f6ebc97e6c4d3ed4a746a92a8d169783803bf9`
retains its own historical role. Accepted E1/R0 executions are not attributed to
current viewer HEAD.

Scientific disposition: **PHASE1_INCONCLUSIVE_TRANSFER**. Phase-1 Attempt #2
execution/integrity and measurement quality passed. Current de-dup remediation-class
timing profiling is **STOP / DEFER — UNBOUNDED_RESEARCH_RISK**. Phase 2 is
**NOT AUTHORIZED**; R0-B and Actual E2 are **NOT RUN / NOT AUTHORIZED**;
Program K effectiveness is **NOT ESTABLISHED**. This is not PHASE1_NO_GO, an E2
failure or proof of ineffectiveness. Production K integration is **NOT STARTED**;
Gate P is **NOT PASSED**. Frozen specifications remain unchanged historical authorities.

**CURRENT NEXT (2026-11-02): 사용자 문서 검수 → K-LC1 신규4+문서6의 정확한10경로
Git 절차 → 새 SHA로 postcommit recovery2개 갱신. 실제 Git과 Desktop 교체는 사용자 소유다.**
현재 main / HEAD == local origin/main == `496fab0fc8829af7a255c403346985be7ae6a005`,0/0이다.
K-LC0의 기존20경로 commit/push는 끝났으며 옛3e9f/precommit 지시를 반복하지 않는다.
이번 문서 갱신 후 기존문서5수정·신규closeout1·LC1 source4가 미커밋이고 staged diff는 비어 있다.
현재 LC0/LC1 확인은 외부 저장8191/97 viewer다. 기존 앱은 actual K-P0/K-LC0 그대로다.
과거 closeout과 PENDING/실패 자료는 dated snapshot이며 현재 안내는 handoff/recovery를 따른다.
Recheck live Git on recovery. Extended remains **ACTIVE**, with effectiveness
research deferred/unresolved; global closure and Stage 4 transition are not decided.
Future research reopening requires new evidence and separate authorization;
no profiling/R0/E2 rerun is a documentation-recovery step.
The ZiNi final holdout `2,010,000 .. 2,010,099` remains unopened/excluded.

그 뒤 Main/Live 최소 알고리즘 선택 통합, 거리 연동 관람 속도, 추가 지역 평가 등은
사용자가 다음 unit을 고른다. 관람 속도 변경과 선택 정책 비용 가중치 변경은 별개이며
이번에는 어느 쪽도 추가하지 않는다. 정책 개선은 Main 통합의 무조건적인 선행 gate가 아니다.

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
