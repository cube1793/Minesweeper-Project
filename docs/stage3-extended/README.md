# Stage 3 Extended

## Status

Stage-3 V1은 **FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED**이며 frozen baseline이다.
ZiNi Improvement도 **CLOSED / V1 RETAINED**이고 미개봉 최종 holdout은 그대로 유지한다.
**Stage-3 Extended는 ACTIVE**다. 이 문서는 의존 관계에 따른 roadmap이며 고정 구현 일정이 아니다.

첫 milestone **Execution / Playback / Visualizer Foundation**은
**FINAL ADJUDICATION PASS / CLOSED (2026-10-14)**다.
자동 검증과 실제 Windows worker/profile/startup, 사용자의 packaged interactive
acceptance, 독립 Claude 감사 및 ChatGPT 최종 판정이 모두 PASS다.
[최종 판정](STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md)에 종료 범위와 F-1/F-2 처분을 기록했다. [Slice 5 수용 기록](STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)에
수동 tester/date, 네 terminal path의 PID·job-directory cleanup 및 controls PASS를 기록했다.
종료 범위는 이 foundation뿐이며 Stage-3 Extended 전체는 계속 active다.

## Closed / integrated

- Execution integration audit: 구현에 반영되어 완료.
- Slice 1 — Execution Context + Pure Trace Playback (`cf7544b`).
- Slice 2 — Subprocess Execution Worker (`d100a49`).
- Slice 3 — Read-only Stage-3 Visualizer Window (`490a8cf`).
- Slice 4 — Application Integration + Process Lifecycle (`b9af830`; pre-Slice-5 baseline).
- Slice 5 — Acceptance / Packaging / Documentation Closeout (`18964ad`): **CLOSED**, committed/merged/pushed.

Full commit identities and the dated Git baselines are in the acceptance and final
adjudication records. `18964add02c508d67429ef29cb59ce879c01017d` is the Slice 5
documentation closeout / independent-audit baseline, not a permanent latest HEAD.
Current components are `Stage3Execution`, worker, parent-owned `Stage3ExecutionJob`,
launcher, pure `Stage3TracePlayer` and execution-only viewer. Indexed
`EXPERT_GENERAL_V1` execution is independent of the current Live/Replay board.

## Foundation final adjudication — CLOSED

Automated acceptance and user-performed packaged manual acceptance are complete.
Normal success, Cancel, launcher-close and main-close during active jobs passed,
with each owned worker gone and job directory removed. Parent PID 5352 also exited
on main close. Playback, responsiveness and retained-result reopen passed.
No algorithm, production Python, profile or playback-seek optimization changed.
Source tests: **1628 passed, 0 failures/errors/skips** in the development environment.
The independent audit also passed: focused **122**, frozen protection **92**,
Stage-2 / ZiNi / Replay / Stage-3 benchmark boundary **86**, full suite **1628**
with **0 failures/errors/skips**, and packaged-worker deterministic equivalence.
ChatGPT final adjudication: **BLOCKER 0 / REQUIRED production 0**.
F-1 is the required documentation-only historical/current-state correction,
addressed by this closeout; it is not an implementation blocker.
F-2 remains **OPTIONAL / DEFER** for future worker/release transport hardening.
No release/tag or next-milestone implementation is part of this closeout.

## Next active milestone — Version / Settings Identity Separation

**Version / Settings Identity Separation** is justified by the concrete UI:

| Identity | Meaning |
| --- | --- |
| Application/release | App integration and distribution version |
| Stage-3 algorithm | Frozen V1 decision/execution semantics; future versions separately specified |
| Physical profile | Authenticated Model C/profile used for planning costs |
| Playback/presentation | Index interval and display choices, independent of recorded costs |

Slice 5 adds no selectors or new settings model. A changed app version does not
change the algorithm/profile identity. A future profile must not be silently
compared as the same frozen official Model C result.

## Later candidates

- Modeled-Time Playback / explicitly synthetic smooth cursor presentation.
- Same-board Human / Stage-2 / Stage-3 comparison.
- Representative-board demonstrations and Timeline Analytics as needed.
- First actual Extended algorithm research: likely nearest **exact-minimum-risk**
  guess among equal-risk candidates, using physical cost. This is a candidate,
  not an adopted policy or authorization to modify V1.

External screen-recording tools remain the default for demonstrations.

## Deferred / evidence-triggered

- Known-mine / no-flag execution.
- Action-specific OPEN / FLAG / CHORD timing.
- Anisotropy.
- CPS / burst constraints.
- Richer / longer planning.

Revisit only with evidence and a separate specification/evaluation contract.
Arbitrary Stage-3 seeks continue to rebuild from index 0. Incremental-forward
optimization remains deferred until modeled-time/smooth-animation requirements
or measured lag justify it; the manual report includes no quantitative lag result.

Manual UX follow-ups are nonblocking and unimplemented: clearer Run/new-execution
versus 결과 열기/retained-result labels, smooth **synthetic/interpolated** cursor
motion, and Modeled-Time Playback for inspecting Model-C action durations. A future
cursor path must not be described as an actual OS mouse trajectory. Final WON
with Step 0/current PLAYING is correct; the 20–5000 ms presentation interval is
intentional and separate from Model C; manual seek stopping autoplay is accepted.
Endpoint/straight-line cursor presentation remains accepted modeled displacement,
not an actual OS trajectory. See the acceptance and final adjudication records
for the full KEEP/DEFER observations and the unfixed F-2 transport case.

## Boundaries and references

`Replay != Stage-3 Trace Playback != ZiNi Trace`. The viewer never supplies solver
decision input. Playback interval is not Model C time, CPU speed or human speed.
V1 official 100k results, algorithm, profile and qualification remain frozen.
Extended is separate scope and does not reopen accepted V1 or closed ZiNi work.

- [V1 final adjudication](../stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)
- [Frozen algorithm](../../STAGE3_ALGORITHM_SPEC_v1.md)
- [Frozen telemetry/benchmark specification](../../STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md)
- [Historical extension backlog](../../STAGE3_EXTENSION_BACKLOG.md)
- [ZiNi final adjudication](../zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md)
- [Documentation index](../README.md)
- [Current handoff](../CURRENT_HANDOFF.md)

New Extended records belong here. Existing frozen specs, audit/evidence paths,
official 100k artifacts and historical decisions retain their identities and locations.
