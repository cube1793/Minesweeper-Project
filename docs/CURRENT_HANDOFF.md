# Current Project Handoff

> Project: Minesweeper graduation project  
> ChatGPT Project: `졸업프로젝트`  
> Purpose: Recover the current project state safely when a chat is restarted or reaches its maximum length.  
> Updated: 2026-10-13 (Asia/Seoul)

---

## 1. Authority / evidence order

When current state or implementation facts are disputed, use this order:

1. current Git source code
2. current tests
3. executable verification
4. frozen specifications / final adjudications / handoff documents
5. README / ARCHITECTURE / documentation index
6. prior ChatGPT / Codex / Claude interpretations or remembered summaries

Agreement between multiple AI reviews is not proof by itself.

---

## 2. Current stable baseline

Repository:

`C:\Users\User\Desktop\졸프\Minesweeper Project\Minesweeper-Project`

Stable branch:

`main`

Local main / feature merge-base at closeout:

`3213c7f9958b73be77f1739a2d1a68962005c1c2` — `docs: add current project handoff`

Closeout working branch: `feature/zini-improvement`.
Verified implementation HEAD before this documentation-only closeout commit:
`2595ee67bf1b8e3ae06aae991ca13813a65aacba` — `feat: add zini explorer ui`.
The initial working tree was clean with 142 tracked files. The closeout commit
follows this implementation; obtain its identity from live Git rather than
treating the pre-closeout hash as the current HEAD. This closeout does not merge or push.

Current live branch / HEAD / working-tree status:

Always verify from the live Git repository when needed.
Do not treat this handoff document as authoritative for the latest HEAD after later commits.

Important Stage-3 V1 identities:

- qualified implementation/evidence commit: `611984133b83be11bcd2105f401ecdddcfd68a15`
- V1 closeout/archive state before Extended workspace: `3e60c6bc41260c094a868841cd7df179d46ad6c1`
- Stage-3 V1 implementation branch was merged into `main` and its job is finished.

If the live repository disagrees with this section, trust the live repository and update this handoff rather than forcing Git back to these values.

---

## 3. Closed milestones

The following are closed baselines, not work-in-progress:

### Stage 1
- playable UI/UX
- Replay save/load/current-game replay
- Replay controls, Index/Time playback, speed controls
- board analysis / 3BV / Ops
- existing ZiNi functionality

### Stage 2
- Simple Algorithm
- exact probability fallback
- runner / replay instrumentation

### Pre-Stage3
- deterministic benchmark-board infrastructure
- telemetry model/schema/repository/statistics
- official 100,000-game Stage-2 baseline
- final architecture/engineering audit

### Stage 3 V1
- frozen speed-focused algorithm
- frozen physical Model C
- telemetry / benchmark integration
- official 100,000-game Stage-3 run
- G0–G5 validation
- independent Claude final audit
- ChatGPT final adjudication
- closeout / evidence preservation / housekeeping
- main merge / remote push

Final technical verdict:

`FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED`

Accepted official result under frozen Model C:

- corpus: `EXPERT_GENERAL_V1`, exact `[0,100000)`
- both-win games: `37,702`
- Stage-3 modeled time-to-win aggregate reduction vs Stage 2: about `30.089144%`
- this is a frozen modeled-time result, not a claim of 30% faster human play or CPU execution.

Do not reopen Stage-3 V1 merely because an Extended design looks cleaner.

### ZiNi improvement — CLOSED (2026-10-13)

- TYPE S semantics-preserving optimizations accepted.
- Post-hoc Trace backend, transport/controller and ZiNi Explorer UI implemented.
- V2 quality research closed without adoption; **V1 RETAINED**.
- C3 fresh quality: **NO-SIGNAL**; C4 Family A: **NO-GO**.
- Final `EXPERT_GENERAL_V1` holdout, indices 2,010,000..2,010,099 (100 boards),
  remains unopened: not generated/fingerprinted/calculated/inspected for final
  quality adjudication. Development failed before authorization, so it was
  deliberately not consumed.

See [final adjudication](zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md).
Milestone closure does not itself complete manual GUI smoke or merge the branch.

---

## 4. Current milestone

The next active milestone is **Stage-3 Extended**, separate from frozen Stage-3 V1.
Its existing direction is retained in section 7 and `docs/stage3-extended/`.
No Stage-3 Extended implementation is part of ZiNi closeout.

The ZiNi feature branch first needs the closeout report's manual GUI smoke and
an explicit later merge decision. Automated/offscreen checks are not a claim
that the normal desktop UI has been visually verified.

---

## 5. Accepted ZiNi boundaries

- **TYPE S:** implemented core optimizations preserve V1 semantics and are
  protected by reference and frozen golden tests. No speed ratio is claimed here.
- **TYPE Q:** V1 remains the production quality policy. V2 A/B/C policies,
  experimental G6/F-2/K0/N-setupOFF and lambda are not production settings.
  V2 research is closed; no Family A implementation or further lambda/search/
  semantics tuning is authorized by this milestone.
- **Trace / Explorer:** the post-hoc backend, result transport/controller and
  separate Explorer UI are implemented. Trace is built lazily on request from
  the final result, without rerunning search. It is not a full search-tree record.

Replay = playback of actually executed game actions.
ZiNi Trace = playback/explanation of answer-board-based ZiNi simulation choices.
**Replay != ZiNi Trace**; similar controls do not justify merging their models.

---

## 6. Next action

Complete the normal desktop manual GUI smoke recorded in the external
`ZINI_IMPROVEMENT_CLOSEOUT_REPORT.txt`: finished-game ZiNi, Explorer navigation/
board display, pending-worker reset/close, and separate Replay use.
Then make a separate merge decision before starting Stage-3 Extended planning.
Do not reopen ZiNi research or consume the reserved final holdout as a merge check.

---

## 7. Stage-3 Extended boundary

Stage-3 Extended is the next active milestone, not unfinished V1 work.

Current direction:

- Stage-3 application execution integration
- unified execution / replay / visualizer surface
- same-board Human / Stage-2 / Stage-3 comparison
- representative-board demonstrations
- timeline analytics where useful
- algorithm-version selection
- physical-model configuration separated from algorithm version
- playback/display settings separated from planning inputs
- later Stage-3 V2/V3... algorithm extensions (distinct from closed ZiNi V2 research)

Built-in screen recording is not currently a priority; external tools such as OBS can record the visualization.

Primary documentation location for new Extended work:

`docs/stage3-extended/`

---

## 8. Documentation map

Start from:

- `docs/README.md`
- `docs/stage3-v1/README.md`
- `docs/stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md`
- `docs/stage3-extended/README.md`
- `docs/zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md`
- `README.md`
- `ARCHITECTURE.md`

Existing Stage-2 / Pre-Stage3 / Stage-3 V1 historical documents may intentionally remain at their existing paths for provenance.

Do not reorganize frozen/evidence paths merely for visual neatness.

---

## 9. Engineering principles

Continue to apply:

- Single Responsibility Principle
- Separation of Concerns
- maintainability
- extensibility
- testability
- backward compatibility
- DRY only where it removes meaningful duplication
- KISS
- YAGNI
- evidence before optimization
- minimum necessary abstraction

When something appears unnecessary, do not remove it immediately.

First state:

1. why it may be unnecessary
2. what would be lost by removing it
3. whether to `KEEP`, `DEFER`, or `REMOVE`

---

## 10. Working-role convention

For major milestones:

- ChatGPT: design / review / final adjudication
- Codex: implementation / execution / focused verification
- Claude Code: independent read-only audit when warranted

For disputed findings, return to source/tests rather than choosing an AI by reputation.

---

## 11. New-chat recovery prompt

The following prompt is intentionally generic so it can be used whether the previous chat ended immediately or much later.

```text
이 채팅은 ChatGPT Project `졸업프로젝트`의
Minesweeper 졸업프로젝트 작업을 이어가는 새 채팅입니다.

이전 채팅이 최대 길이에 도달했거나 새 작업 단위로 분리한 것입니다.

내 기억이나 과거 AI 답변만으로 현재 상태를 추정하지 말고,
Project에 첨부된 최신 파일과 현재 Git 상태를 기준으로 먼저 현재 프로젝트 상태를 복원하세요.

증거 우선순위:
1. 현재 Git source code
2. 현재 tests
3. 실행 가능한 검증 결과
4. frozen specification / final adjudication / handoff 문서
5. README / ARCHITECTURE / documentation index
6. 과거 ChatGPT / Codex / Claude 해석과 기억

먼저 `docs/CURRENT_HANDOFF.md`와 `docs/README.md`를 읽고,
현재 작업과 직접 관련된 source/tests를 확인하세요.

Stage-3 V1은 이미 CLOSED인 frozen baseline입니다.
현재 작업 때문에 임의로 다시 열거나 과거 frozen semantics를 변경하지 마세요.

현재 진행 중인 milestone은 최신 handoff/source를 기준으로 복원하세요.
2026-10-13 ZiNi improvement는 CLOSED이며 다음 활성 milestone은 Stage-3 Extended입니다.
ZiNi TYPE S와 Trace/Explorer는 수용되었고, V2 품질 연구는 미채택으로 종료했습니다.
V1 품질 정책과 미개봉 최종 holdout을 유지하며 ZiNi 연구를 임의로 재개하지 마세요.

현재 작업이 이미 그 단계를 지나갔다면 최신 handoff/source/tests를 우선하세요.

프로젝트 원칙:
- SRP / Separation of Concerns
- maintainability / extensibility / testability
- backward compatibility
- KISS / YAGNI
- evidence before optimization
- minimum necessary abstraction

기존 요소가 불필요해 보이면 바로 제거하지 말고:
1. 왜 불필요해 보이는지
2. 제거하면 무엇을 잃는지
3. KEEP / DEFER / REMOVE 중 무엇을 권하는지
를 먼저 설명하세요.

응답 시작 시 바로 구현안을 내지 말고 짧게:
1. 복원한 현재 프로젝트 상태
2. 현재 milestone
3. 직전까지 완료된 것
4. 다음으로 해야 할 한 단계
5. 아직 불확실하거나 확인이 필요한 것
을 정리한 뒤 이전 채팅의 연속 작업으로 진행하세요.

이미 확인 가능한 내용을 다시 사용자에게 묻지 마세요.
```

---

## 12. Handoff maintenance rule

Update this file only at meaningful boundaries, for example:

- milestone completed
- branch/baseline changed
- major design decision frozen
- new strategy/version accepted
- current next action materially changed

Do not turn this file into a full changelog or duplicate every audit artifact.
