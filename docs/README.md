# Project Documentation Index

기존 문서를 이동하지 않고 현재 위치에서 찾을 수 있도록 정리한 문서 지도다. Stage 1의 앱·Replay·ZiNi와 Stage 2의 실행 구조는 공통 문서에서, Stage-3 V1의 현재 수용 상태는 Closeout에서 확인한다. 과거 문서의 상태·경로·판정은 당시 기록으로 읽는다.

## Project-wide documents

- [Project README](../README.md): 실행 방법, 기능 범위와 프로젝트 개요.
- [Architecture](../ARCHITECTURE.md): 앱·분석·알고리즘·Replay의 구조와 책임 경계.
- [Building](../BUILDING.md): Windows 배포본 빌드 절차와 release 검증 안내.

## Stage 2 / Pre-Stage3

Stage-2 baseline, telemetry 및 benchmark 기반 문서다. Historical provenance를 위해 현재 경로를 유지한다.

- [Pre-Stage3 telemetry specification v2](../PRE_STAGE3_TELEMETRY_SPEC_v2.md)
- [Pre-Stage3 telemetry specification v2 — 한국어](../PRE_STAGE3_TELEMETRY_SPEC_KO_v2.md)

## Stage 3 V1 — Frozen specification and design

- [Frozen algorithm specification v1](../STAGE3_ALGORITHM_SPEC_v1.md)
- [Frozen telemetry and benchmark specification v1](../STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md)
- [Stage-3 handoff](../STAGE3_HANDOFF.md): Pre-Stage3 완료에서 Stage 3 설계로 넘어간 당시 인수인계 기록.

### Historical design / implementation records

- [Algorithm specification draft v1.1](../STAGE3_ALGORITHM_SPEC_DRAFT_v1.1.md): 동결 전 설계 기록.
- [Implementation Slice A](../STAGE3_IMPLEMENTATION_SLICE_A.md)
- [Specification freeze adjudication](../STAGE3_SPEC_FREEZE_ADJUDICATION.md)
- [Replay validation protocol v1.1 amendment](../STAGE3_REPLAY_VALIDATION_PROTOCOL_V1_1_AMENDMENT.md)

## Stage 3 V1 — Validation and audit

아래 문서는 각 검증·감사 단계의 기록이며, 공식 100k 최종 수용 판정은 Closeout에서 확인한다.

- [B7 pilot report](../STAGE3_B7_PILOT_REPORT.md)
- [B7-C compute diagnostics](../STAGE3_B7C_COMPUTE_DIAGNOSTICS.md)
- [B9 independent Claude audit](../STAGE3_B9_CLAUDE_INDEPENDENT_AUDIT.md)

## Stage 3 V1 — Closeout

**FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED**

- [V1 기록·보존 위치 안내](stage3-v1/README.md): 공식 결과의 해석 한계와 외부 closeout·official evidence 보존 위치.
- [V1 최종 판정문](stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)

Release/evidence 자료는 기존 위치를 유지한다. 배포 절차는 위 Building 문서에서, 공식 100k artifact 탐색은 V1 기록·보존 위치 안내에서 시작한다.

## Stage 3 V1 — Archived adjudication records

- [Slice B — B8 adjudication](archive/stage3-v1/STAGE3_SLICE_B_B8_ADJUDICATION.md)
- [Slice B — final adjudication](archive/stage3-v1/STAGE3_SLICE_B_FINAL_ADJUDICATION.md)

## Stage 3 Extended

- [Stage 3 Extended 문서 시작점](stage3-extended/README.md)
- [기존 extension backlog](../STAGE3_EXTENSION_BACKLOG.md): V1에서 deferred된 후보와 검토 조건. 최종 구현 우선순위를 확정하는 문서로 취급하지 않는다.

## Experiments

- [E/L policy pilot](../experiments/STAGE3_E_L_POLICY_PILOT.md): 별도 실험 기록.

## Document-location policy

- 기존 Stage-2 / Pre-Stage3 / Stage-3 V1 문서는 historical provenance를 위해 현재 위치를 유지한다.
- Frozen spec, audit, evidence 및 qualification 문서를 탐색 편의만을 위해 대규모로 이동하지 않는다.
- 앞으로 새 Stage-3 Extended 문서는 기본적으로 `docs/stage3-extended/` 아래에 생성한다.
- Official benchmark/evidence artifact root는 documentation cleanup 대상이 아니다.
- 기존 `results/`의 release/evidence 문서와 `experiments/` 문서는 해당 위치에서 유지한다.
