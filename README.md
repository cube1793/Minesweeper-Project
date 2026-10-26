# Minesweeper Project

Python과 PyQt5로 개발한 지뢰찾기 졸업프로젝트입니다. 직접 플레이하면서 통계를 확인하고, Simple Algorithm으로 현재 수를 분석하거나 자동 진행할 수 있습니다. Replay 기록·재생·분석과 3BV/Ops, ZiNi 보드 분석까지 구현되어 있습니다.

## 핵심 기능

- **게임:** 초급·중급·상급·사용자 지정 난이도, OPEN·FLAG·CHORD, 화음 입력 방식과 셀 크기 조절
- **플레이 통계:** Time, Est Time, 3BV, 3BV/s, Ops, 클릭별 active/wasted 집계, CPS, Efficiency, IOE, Thrp, Corr, ZiNi, ZNE, ZNT
- **Simple Algorithm:** 확정 수와 최소 지뢰 확률 후보 표시, 확정 수 자동 진행, 선택적인 추측 실행
- **Replay:** JSON 저장·불러오기, 위치 이동과 자동 재생, 시점별 통계, 추천과 실제 다음 수 비교
- **Human Mouse Trace:** Live 보드의 실제 포인터 경로와 action marker 기록, 게임 종료 후 또는 Replay에서 선택적으로 표시
- **Same-board Comparison:** 완료 Human Replay의 고정 배치에서 Human / Stage 2 / Stage 3 결과와 선택 run의 독립 Index/시간 재생, 정답 참조·완료 action-target route 표시

## Simple Algorithm

사람에게 보이는 열린 숫자·닫힌 칸·깃발과 공개 총 지뢰 수를 사용해 수를 추천합니다. 실제 숨겨진 지뢰 배치를 정답으로 참조하지 않으며, **깃발은 지뢰라고 가정**합니다.

1. **Local deterministic inference:** 열린 숫자에서 인접 깃발 수를 뺀 값으로 확정 안전/지뢰를 찾습니다.
2. **Exact probability:** local 확정 수가 없을 때 공개 조건을 만족하는 전체 보드 경우의 수로 지뢰 확률을 계산합니다.
3. 확률이 정확히 0 또는 1이면 **certainty**, 그 사이이면 **guess**입니다. Guess에서는 최소 지뢰 확률의 칸을 추천하므로 패배할 수 있습니다.

| UI 항목 | 동작 |
| --- | --- |
| 현재 상태 분석 | 현재 보드를 한 번 분석해 추천만 표시 |
| 분석 표시 | Live에서는 행동 후, Replay에서는 위치 변경 후 분석 갱신 |
| 확정 수 자동 진행 | Live에서 한 번에 한 행동을 실행하고 새 observation으로 다시 분석 |
| 추측 허용 | 자동 진행이 guess도 실행하도록 허용. OFF이면 추측 직전에 대기 |
| 확률 표시 | 이미 계산된 확률의 표시만 전환. Local 추론만 한 경우 확률을 추가 계산하지 않음 |
| Reduction | 화면의 열린 숫자를 `N − 인접 깃발 수`로 표시. 원본 observation은 유지 |

초록은 확정 안전, 빨강은 확정 지뢰, 주황은 최소 위험 후보이며 테두리는 선택된 추천을 뜻합니다. 여러 추천을 queue해서 실행하지 않습니다. 새 게임의 첫 수는 별도 [FIRST_CLICK 정책](ARCHITECTURE.md#first-click)을 따릅니다.

## Replay / Replay Analysis

**Replay**는 보드와 실제 클릭 이벤트를 기록하고 같은 순서로 재생하는 기능입니다.

- `Replay 저장`과 `Replay 다른 이름으로 저장`으로 JSON을 저장하고, `Replay 불러오기`로 다시 열 수 있습니다. 지뢰 배치가 끝났다면 미완료 게임도 저장할 수 있습니다.
- 게임 종료 후 `이번 판 Replay`로 파일 저장 없이 바로 볼 수 있습니다.
- 처음·이전·다음·마지막 위치와 slider 이동, Index/Time 자동 재생을 지원합니다. Time 모드는 기록된 이벤트 시간을 사용하며 0.25배속부터 8배속까지 조절합니다.
- 완료된 Replay는 현재 위치에 맞는 Counters를 표시하고, 미완료 Replay의 Counters는 마스킹합니다.
- Replay 종료는 이전 Live 판을 이어가는 대신 저장해 둔 Live 난이도로 **새 게임**을 시작합니다.

**Replay Analysis**는 재생 중인 현재 position에서 Simple Algorithm의 추천을 구한 뒤 실제 다음 이벤트와 비교합니다. `현재 상태 분석`으로 한 번 분석하거나 `분석 표시`로 이동에 따라 갱신할 수 있습니다. 확률·Reduction 표시도 사용할 수 있습니다.

비교 결과는 추천과 일치, 동등 후보, 추천과 다름, 비교 대상 아님, 다음 실제 수 없음으로 구분합니다. **“추천과 다름”은 오답이나 실수 판정이 아닙니다.** 분석은 행동을 실행하지 않으며 Replay에서는 자동 진행·추측 허용이 비활성화됩니다. 위치와 비교의 정확한 의미는 [Replay index](ARCHITECTURE.md#replay-index)와 [비교 규칙](ARCHITECTURE.md#replay-comparison)을 참고하세요.

## ZiNi / 보드 분석

- **3BV/Ops:** opening 그룹과 고립 숫자 칸을 분석해 보드의 정적 지표와 플레이 진행량을 계산합니다.
- **ZiNi:** 실제 mine layout을 사용하는 board metric입니다. 위 Simple Algorithm과 정보 경계 및 목적이 다릅니다.
- deterministic G.ZiNi, maximum-Premium min-ties 탐색, neighborhood beam 및 seeded-chain 탐색을 제공합니다.
- 화면의 ZiNi는 별도 subprocess에서 계산한 **bounded best-so-far**입니다. 전역 최적해나 정확한 최소 클릭 수를 보장하지 않습니다.
- Live에서는 첫 OPEN 또는 FLAG로 지뢰 배치가 확정되면 백그라운드 계산을 시작합니다. 진행 중에는 결과를 숨기고, 종료 시 계산이 끝났다면 즉시 표시합니다. 아직 계산 중이면 `-`를 유지합니다. Replay의 계산 시작은 완료 기록에 한정됩니다.
- **ZiNi Explorer:** 종료된 Live 게임 또는 완료 Replay에서 ZiNi 결과가 준비되면 별도 창으로 최종 계산 경로를 확인합니다. 처음·이전·다음·마지막, slider와 Index 자동 재생을 지원합니다. 헤더에는 누적 Clicks를 표시하고, 좌표·새로 열린 칸/깃발 수·Premium 진단은 기본으로 접힌 **상세 정보**에서 확인합니다. 초기 창 크기는 보드와 화면 공간에 맞추며 큰 사용자 지정 보드나 작은 화면에서는 스크롤을 유지합니다. Trace는 요청 시 사후 구성하며, 실제 게임 행동을 기록한 Replay와 별도 모델입니다.

2026-10-13 **ZiNi improvement CLOSED**: 의미를 보존하는 속도 최적화와 Trace/Explorer를 수용했습니다. 품질 정책은 **V1 유지**, V2 연구는 **종료·미채택**, 최종 holdout은 의도적으로 미개봉 상태입니다. [최종 판정](docs/zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md)을 참고하세요. 현재 활성 마일스톤은 Stage-3 Extended입니다.

계산 전략과 결과 해석은 [ZiNi 설계](ARCHITECTURE.md#zini-results)에 정리되어 있습니다.

## Benchmark Statistics / 벤치마크 통계

상단 **도구 → 벤치마크 통계**에서 별도 창을 열고, **데이터베이스 열기**에서 기존 텔레메트리 SQLite 파일을 선택합니다. 데이터베이스는 읽기 전용으로 열며 생성·초기화·마이그레이션하지 않습니다. 게임, Live Auto, Replay 상태는 유지됩니다.

- 실행 선택: 저장된 실행의 ID·솔버·보드·첫 클릭 정책, 요청/처리/저장 수와 정확한 접두 범위, Git dirty 및 공식 사용 가능 여부를 표시합니다. 부분/실패 실행에는 **진단용 실행** 표시가 붙습니다.
- 실행 요약: 승패·승률·추측 비율/평균, 행동/추론 횟수, 계산 시간의 총합·평균·최대·P50/P90/P95/P99를 표시합니다.
- 그래프: 0회 추측 게임을 포함한 추측 횟수 분포, 이벤트별 확률 추측 위험 분포, 정적 보드 3BV 분포를 제공합니다. 위험 그래프의 점을 가리키거나 아래 선택 목록을 사용하면 정확한 분수를 확인할 수 있습니다.
- 언어: 기본 한국어이며 창 안에서 English로 전환할 수 있습니다. 선택 실행과 그래프 데이터는 유지됩니다.

의사결정 계산 시간은 **진단용이며 실행 환경에 영향을 받습니다**. 조회는 실행 선택 시 동기적으로 이루어집니다. 진행 중인 실행을 다시 조회하려면 다른 실행을 선택했다가 돌아오거나 DB를 다시 엽니다.

이 기능은 Pre-Stage 3 그래프/통계 결과물이자 Stage 1 통계/시각화 확장입니다. 두 실행의 pairing GUI는 실제 Stage 3 비교 흐름이 생길 때 재검토하도록 의도적으로 보류했습니다. 기존 `validate_paired_prefix()` 백엔드는 유지됩니다.

## Stage-3 V1 — CLOSED

2026-10-10 최종 판정으로 **동결 Stage-3 V1 알고리즘·텔레메트리·공식 100k 검증이 완료**되었습니다. Qualified implementation commit은 `611984133b83be11bcd2105f401ecdddcfd68a15`입니다. 이후 문서 정리 커밋은 공식 100k 실행 commit이 아닙니다.

동결 Model C를 적용한 공식 `EXPERT_GENERAL_V1` 100,000보드 중 양쪽 모두 승리한 **WW 37,702게임에서 modeled time-to-win 합계가 Stage 2보다 약 30.089144% 감소**했습니다. 보드별 승패와 기록된 guess 시퀀스의 동등성은 이번 corpus의 관찰 결과입니다. CPU 계산시간·benchmark wall time·실제 인간 플레이 시간의 30% 감소나 모든 보드의 동등성을 뜻하지 않습니다.

[최종 판정문 원문](docs/stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)과 [V1 기록·보존 위치 안내](docs/stage3-v1/README.md)를 참고하세요. 최종 감사 OPTIONAL 4건은 비차단 **DEFER**입니다. ZiNi 개선은 별도 마일스톤으로 종료했습니다. Stage-3 실행·재생·Visualizer는 현재 앱에 통합되어 있으며, 새 알고리즘이나 물리 모델 설정은 후속 **Extended** 범위입니다.

## Stage-3 Visualizer

메인 화면 왼쪽 **Counters** 패널의 **Stage-3 Visualizer** 버튼으로 별도 실행 창을 엽니다.
현재 Live/Replay 보드와 독립된 `EXPERT_GENERAL_V1` 벤치마크의 **Game Index**
(0 이상의 십진 정수)를 입력하고 **Run**을 누릅니다. 실행은 subprocess에서
진행하며 **Cancel**로 취소할 수 있습니다. 완료하면 결과 Visualizer가 자동으로
열리고, 결과 창만 닫은 뒤에는 실행 창의 **결과 열기**로 마지막 완료 결과를 다시
엽니다. 새 Run, 취소/실패 또는 실행 창 종료 후에는 이전 결과를 유지하지 않습니다.

- **First / Previous / Next / Last**, slider, **Play / Pause**로 행동 index를 이동합니다.
  Index 0은 적용 전, index N은 기록된 action N개를 적용한 상태입니다. 최종 결과가
  WON이어도 Step 0의 현재 재구성 상태는 PLAYING이며 정상입니다. 수동 seek는 자동 재생을 멈춥니다.
- OPEN / FLAG / CHORD와 커서·대상을 표시합니다. 선은 **cursor-before → action-target**
  칸 중심 사이의 modeled displacement이며 실제 OS 마우스 궤적이 아닙니다.
- 행동별·누적·전체 modeled time은 정확한 정수 **µs**로 표시합니다.
- **Index**는 기본 모드입니다. **Playback: Index · N ms/step (presentation)**은
  화면 재생 간격을 표시하며 범위 20–5000 ms, 기본 200 ms를 유지합니다.
- **Modeled-Time**은 기록된 Model C의 `modeled_action_us`를 따라 재생합니다.
  **Playback: Modeled-Time · 1× (presentation)**처럼 현재 배속을 표시하며,
  0.25× / 0.5× / 1× / 2× / 4× / 8× 중 선택합니다. 기본은 1×입니다.
  배속은 presentation만 바꾸며 기록된 시간·total·planner·물리 모델은 바꾸지 않습니다.
- Modeled-Time의 synthetic cursor는 현재 pending action의 칸 중심 사이를 직선 smoothstep
  (`q = u²(3 − 2u)`)으로 표시합니다. 부분 구간에는 적용 전 보드를 유지하고
  modeled 경계에서 action을 적용합니다. 같은 칸 action은 이동하지 않습니다.
  별도 dwell 모델은 없으며 실제 OS 마우스 궤적이나 물리적 가속도 모델이 아닙니다.
- **Show hidden answers**와 **Show action-target route**는 기본 OFF입니다.
  정답 참조는 현재 HIDDEN 셀의 지뢰/0이 아닌 숫자만 희미하게 표시하며 공개·terminal
  상태를 덮어쓰지 않습니다. Route는 완료된 실행 target만 포함하고 pending/future
  target 및 가상의 initial-cursor 진입선은 제외합니다. 선택 segment/cursor와 별개입니다.
  기존 direct slider track seek와 handle drag를 유지하며 **Index smooth interpolation은 추가하지 않았습니다**.
- Pause/Resume은 부분 진행을 보존합니다. 수동 navigation과 모드 전환은 부분 진행을
  취소하고 정수 index 상태로 돌아가며, 모드 전환은 자동 시작하지 않습니다.
  설정은 저장하지 않으며 다시 열면 Index / 200 ms / modeled 1×로 돌아갑니다.
- 실행 창을 닫으면 소유한 job과 결과 창도 정리합니다. 메인 창 종료도 이 경계를 따릅니다.
  Visualizer는 완료 실행을 읽기 전용으로 재생하며 solver에 판단 입력을 주지 않습니다.

`Replay != Human Mouse Trace != Stage-3 Trace Playback != ZiNi Trace`입니다. Stage-3 V1 / Model C는
변경되지 않았습니다. 2026-10-14 자동 검증과 실제 Windows 패키지 수동 수용,
독립 Claude 감사 및 ChatGPT 최종 판정을 통과하여 **Execution / Playback /
Visualizer Foundation은 FINAL ADJUDICATION PASS / CLOSED**입니다.
[최종 판정과 후속 범위](docs/stage3-extended/STAGE3_VISUALIZER_FOUNDATION_FINAL_ADJUDICATION.md) 및
[수용 증거와 수동 검증 기록](docs/stage3-extended/STAGE3_VISUALIZER_FOUNDATION_ACCEPTANCE.md)을
참고하세요.

**Version / Settings Identity Separation — FINAL ACCEPTANCE PASS / CLOSED
(2026-10-15)**: 고정 identity와 표시 경계를 분리하고 최종 source tests,
fresh package/worker 및 사용자 native packaged GUI 수용을 완료했습니다.
[Identity Separation closeout](docs/stage3-extended/STAGE3_IDENTITY_SEPARATION_CLOSEOUT.md)에
검증 수치와 범위를 기록했습니다.

| Identity | 현재 의미 |
| --- | --- |
| Application / release | Release/tag/build 문서의 배포 identity. Runtime app-version 상수는 의도적으로 도입하지 않았으며 현재 main은 historical v0.2.0이 아닙니다. |
| Stage-3 algorithm | `stage3_identity.STAGE3_V1_IDENTITY`의 동결 V1 알고리즘 identity |
| Physical model / profile | `stage3_physical.MODEL_C_V1_IDENTITY`의 인증된 Model C/profile/table identity; `Model C` 표시는 별도 alias |
| Playback / presentation | Index/Modeled-Time·간격·배속 등 비영속 viewer 상태; planner 입력이나 물리 시간 identity가 아닙니다. |

실행 창은 `Benchmark: EXPERT_GENERAL_V1`, `Algorithm: Stage-3 V1`,
`Physical: Model C · profile v1`을 각각 표시합니다. Viewer도 Algorithm과
Physical을 분리하며 recorded modeled time은 간격을 바꿔도 그대로입니다.
V1 알고리즘/profile semantics와 공식 100k 결과의 identity는 변경되지 않았습니다.

**Modeled-Time Playback / Synthetic Smooth Cursor Presentation —
FINAL ACCEPTANCE PASS / CLOSED (2026-10-15)**: 최종 source regression,
fresh package/profile/worker 검증과 사용자의 native packaged GUI A–K 수용을
완료했습니다. [Closeout 기록](docs/stage3-extended/STAGE3_MODELED_TIME_PLAYBACK_CLOSEOUT.md)을
참고하세요. 동결 Stage-3 알고리즘과 물리 모델 semantics는 변경하지 않았습니다.

Stage-3 Extended 전체는 **ACTIVE**입니다. 현재 roadmap은 다음과 같습니다.

1. **CLOSED** — Execution / Playback / Visualizer Foundation.
2. **CLOSED** — Version / Settings Identity Separation.
3. **CLOSED** — Modeled-Time Playback / Synthetic Smooth Cursor Presentation.
4. **CLOSED** — Human Mouse Trace / Path Visualization.
5. **CLOSED** — Same-board Human / Stage-2 / Stage-3 Comparison.
6. **CLOSED** — Representative-board Demonstrations / Timeline Analytics (Slices 0–4 COMPLETE / ACCEPTED).
7. **CLOSED** — Selected Exemplar Board-State Reconstruction / Human Interpretation Viewer.
   Slices 0–4 COMPLETE / ACCEPTED; qualified `ff6358ae62b6f343bda36069d7164bda9aebee74`.
   [Viewer closeout](docs/stage3-extended/STAGE3_EXEMPLAR_BOARD_VIEWER_CLOSEOUT.md).
8. **CLOSED** — Visualization Usability Polish: Same-board selected-run timed
   playback/synthetic cursor 및 두 UI의 hidden-answer/completed-route 참조.
   Qualified `31630dd6ffa2301c41534fca3b003838d865f313`.
   [Closeout](docs/stage3-extended/STAGE3_VISUALIZATION_USABILITY_POLISH_CLOSEOUT.md).
9. **CLOSED** — Fixed-Exemplar Human / Domain Interpretation.
   [Closeout](docs/stage3-extended/STAGE3_FIXED_EXEMPLAR_INTERPRETATION_CLOSEOUT.md).
10. **ACTIVE** — Program K: Logical Known-Mine Capability + Selective Physical Materialization.

현재 Program K는 **PRE-ACTUAL-E2**입니다. E2 구현 I1–I8은 8/8 COMPLETE / ACCEPTED이고,
accepted Real R0-A는 원래 source/representation에 대해 COMPLETE / INTEGRITY PASS /
EVIDENCE ACCEPTED / CLOSED입니다. 그 R0-A에서 도출된 execution-wall admission과
R0-B minimum whole-archive의 두 static block은 **역사적 old-source/old-representation
증거로 그대로 보존**되며, 아직 operationally resolved로 재해석하지 않습니다.

후속 remediation engineering investigation은 CLOSED / ACCEPTED입니다.
[Program K remediation design V1.3.1](docs/stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1.md)은
**FINAL DESIGN ACCEPTED / FROZEN BY EXACT TRACKED BYTES**이고,
[acceptance receipt](docs/stage3-extended/STAGE3_PROGRAM_K_REMEDIATION_DESIGN_V1_3_1_ACCEPTANCE.md)는
**BLOCKER 0 / REQUIRED 0; design phase CLOSED**를 기록합니다. Authority-freeze commit은
`83c9f0c` (`docs: freeze accepted Program K remediation design`)입니다.

Remediation implementation은 아직 **NOT STARTED**입니다. 현재 다음 work unit은 별도
명시적 승인이 필요한 **Remediation Slice 1A — RF02 / WB02 / codec / qualified-profile
primitives**입니다. Fresh R0-A, Real R0-B, Actual E2는 모두 **NOT AUTHORIZED / NOT RUN**이며
Program K effectiveness는 **NOT ESTABLISHED**입니다. 자세한 현재 상태와 recovery order는
[CURRENT_HANDOFF](docs/CURRENT_HANDOFF.md)와 [Stage-3 Extended index](docs/stage3-extended/README.md)를
우선합니다.

Timeline Analytics는 **FINAL ACCEPTANCE PASS / CLOSED**입니다.
[최종 closeout](docs/stage3-extended/STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md)에
수용된 fixed exemplars/report와 후속 연구의 해석 경계를 기록했습니다.

## Same-board Human / Stage-2 / Stage-3 Comparison — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-17)**. Source/package/lifecycle 검증과
프로젝트 사용자의 native/manual **A–L PASS**를 수용했습니다. Qualified source/package
SHA는 `a59d0d963bdf1544a03968163b884342e2797ee0`입니다.
[Closeout 기록](docs/stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CLOSEOUT.md)과
[기술 계약](docs/stage3-extended/STAGE3_SAME_BOARD_COMPARISON_CONTRACT.md)을 참고하세요.
이후 **Visualization Usability Polish (2026-10-18) CLOSED**에서 아래 재생/참조 UX를
수용했습니다. 새 qualified implementation은 `31630dd6ffa2301c41534fca3b003838d865f313`이며
[polish closeout](docs/stage3-extended/STAGE3_VISUALIZATION_USABILITY_POLISH_CLOSEOUT.md)에
자동/package 회귀와 **사용자 source-GUI A–M / V-A..V-I** 수용을 구분해 기록했습니다.

- 완료된 Live 판 또는 Human-labeled Replay에서 **도구 → Compare as full-game Human Replay…**를
  선택합니다. 이 명시적 동작은 전체 Human 기록으로 제출한다는 의도이며 역사적 출처의 증명이 아닙니다.
  Replay는 현재 표시 index와 무관하게 원본 전체를 사용합니다. 미완료·terminal 이후 event 등은
  Comparison 전용 admission 사유로 거절하며 일반 Replay 사용 규칙을 바꾸지 않습니다.
- 실행 창은 한 번 capture한 context를 유지합니다. Main의 새 게임·Replay 교체로 대상이 바뀌지
  않으며 **Open Comparison…**은 기존 창을 엽니다. **Run / Cancel / Open Result**로 실행·취소·
  완료 결과 재열기를 제어하며 결과 창 재열기는 solver를 다시 실행하지 않습니다.
- 결과 창은 한 보드와 Human / Stage 2 / Stage 3 선택, First / Previous / Next / Last,
  direct-track-seek slider와 native handle drag를 제공합니다. 세 run의 상태를 독립적으로
  기억하고 선택 run만 재생합니다. Human은 **Index / Replay Time**, solver는 **Index / Model C Time**입니다.
  공통 synchronized clock/playhead는 없습니다. 현재 재구성 status와 최종 outcome은 별개입니다.
- Index는 20..5000 ms/action, 기본 200, 최소 **Max (20 ms)**이며 범위 밖 입력은 commit 시
  보정합니다. Time 배속은 0.25x..8x의 정확한 0.25 단위입니다. 약 16 ms refresh는
  표시 요청일 뿐 timing authority나 보장 FPS가 아닙니다.
- Smooth synthetic action-target cursor는 칸 중심 직선/smoothstep을 사용합니다.
  Human의 첫 anchor는 첫 action target이며 가상의 첫 이동이나 실제 Mouse Trace 좌표를
  빌리지 않습니다. 부분 pause/resume을 보존하고 수동 이동은 부분 진행을 취소합니다.
- **Show hidden answers / Show action-target route**는 기본 OFF이며 retained fixed truth와
  완료 action targets만 표시합니다. Pending target은 commit 전 route에 들어가지 않습니다.
  실제 Human Mouse Trace는 Human에서 전체 기록을 그대로 표시하며 route/synthetic cursor와
  별개입니다. 정답 참조는 HIDDEN-only이며 공개/terminal glyph와 solver 판단을 바꾸지 않습니다.
- Human Replay elapsed **s**, 각 solver의 Model C cost through termination **µs**, 각 solver의
  decision compute **ns**를 구분합니다. 일반 speed winner/ranking/ratio는 없습니다.
- 이미 확정된 배치를 그대로 쓰므로 `(0,0)` 지뢰에 대한 solver 첫 OPEN 패배도 정상 결과입니다.
  같은 배치나 recorded start는 동일한 역사적 mine-placement policy, 실행 의미, exclusively-Human
  provenance 또는 통제 실험의 증명이 아닙니다. 기존 Stage-3 Visualizer는 별도로 유지됩니다.

## Human Mouse Trace / Path Visualization — CLOSED

**FINAL ACCEPTANCE PASS / CLOSED (2026-10-16)**. 물리 마우스 입력 보정과 성능
hardening을 포함한 source/package 검증 및 최종 사용자 native 수용을 완료했습니다.
Qualified implementation/package SHA는 `e32145fa5c114e1ce500ad2e837ef6000cc49cca`입니다.
[Closeout 기록](docs/stage3-extended/STAGE3_HUMAN_MOUSE_TRACE_CLOSEOUT.md)에 증거를 정리했습니다.

- **마우스 경로 기록**은 앱/session 기본 ON이며 첫 committed timed human OPEN/FLAG
  전까지만 선택할 수 있습니다. 첫 OPEN은 L release, 첫 FLAG는 R press 관측에서
  trace의 0 µs를 시작합니다. 시작 전 untimed CHORD는 trace를 시작하지 않습니다.
  OFF도 첫 committed timed OPEN/FLAG에서 선택이 잠기며 해당 판의 trace를 무효화합니다.
- 실제 Live 보드 포인터를 board-local Qt logical-pixel 좌표로 기록합니다. 전달·수용된
  event sample의 subpixel 위치를 보존하며 timer sampling, 최소 거리 필터 또는
  의미를 바꾸는 point dropping은 없습니다. Trace는 독립 monotonic clock을 사용하고
  연속성이 끊기면 segment를 나눕니다.
- 종료된 Human 판 또는 trace가 있는 Replay에서 **마우스 경로 표시**를 선택합니다.
  Replay v2는 별도 Mouse Trace 모델을 attachment로 저장하며 marker의 action 의미는
  실제 `ReplayEvent` index가 제공합니다. v1은 계속 읽을 수 있는 trace-free 형식입니다.
- 실제 Auto action이 실행되면 그 판의 Human trace 자격을 잃습니다. Committed human
  action의 Replay append 실패도 전체 trace를 무효화합니다.

물리 입력은 UI 정책이며 Engine은 semantic OPEN / FLAG / CHORD만 받습니다.
Mode A/C의 FLAG/UNFLAG는 **R press**에 즉시 실행되고 R release에는 반복되지 않습니다.
Mode A는 R을 누른 중에도 L release의 OPEN/좌클릭 CHORD와 독립적인 R 입력을 유지하며,
Mode C는 CHORD를 하지 않습니다. Mode B는 held-button overlap으로 BOTH를 구성합니다.
L을 누른 중 R press는 FLAG를 억제하고, R 이후 L이 합류하면 이미 실행된 FLAG는
유지됩니다. Press origin은 무관하며 첫 release에서 현재 pointer target으로 한 번
CHORD를 시도합니다. 뒤 release는 inert이고, 한 버튼을 계속 누른 채 새 overlap을
반복할 수 있습니다. FLAGGED 중심은 flag를 유지하면서 주변 HIDDEN 칸만 눌림 preview를
표시합니다. 자세한 계약은 [입력 경계](ARCHITECTURE.md#physical-mouse-input)를 참고하세요.

Primitive recorder 저장소, pre-start gating, geometry cache와 **16 MiB** bounded raster
cache를 적용했습니다. Hardening 후 사용자 native 시험에서 trace ON은 수용 가능했고
최종 패키지에서도 눈에 띄는 성능 회귀는 없었습니다. Zero overhead를 뜻하지 않습니다.
Human Mouse Trace는 실제 sampled Live-board presentation data이며 OS-global trajectory,
Stage-3 synthetic cursor, Model C calibration evidence 또는 solver 입력이 아닙니다.

## 실행 방법

Windows 배포본은 [Releases](https://github.com/cube1793/Minesweeper-Project/releases)에서
ZIP 전체를 압축 해제한 뒤 `Minesweeper/Minesweeper.exe`를 실행합니다.
`_internal` 폴더를 EXE와 함께 유지해야 하며 Python 설치는 필요하지 않습니다.
배포본 빌드와 검증 방법은 [BUILDING.md](BUILDING.md)에 정리되어 있습니다.

Python 3.10 이상과 PyQt5, PyQtGraph가 필요합니다. Repository 루트에서 실행합니다.

```powershell
python -m pip install -r requirements.txt
python main.py
```

기본 보드는 상급 `30 × 16 / 99 mines`입니다. UI에서 난이도를 바꿀 수 있습니다.
Windows에서는 `main.py`가 Qt import 전에 설치된 PyQt5의 플랫폼 플러그인 경로를 설정합니다.

## 프로젝트 구조

아래는 역할별 파일 안내입니다. 실제 의존 방향은 [Architecture 구조도](ARCHITECTURE.md#dependencies)를 참고하세요.

```text
Minesweeper-Project/
├─ main.py                      # 진입점, engine 생성 및 UI 주입
├─ ui_manager.py                # PyQt5 화면, 입력, Live Auto, Replay 제어
├─ mouse_trace.py               # Human 포인터 sample/segment와 순수 recorder
├─ mouse_trace_ui.py            # 선택적 경로/Replay action marker overlay와 cache
├─ core_engine.py               # 게임 규칙, 상태, 시간·클릭 통계
├─ board_snapshot.py            # 불변 정적 보드 데이터
├─ board_analyzer.py            # 3BV/Ops 분석
├─ simple_algorithm.py          # local deterministic inference
├─ simple_probability.py        # exact probability와 확률 기반 선택
├─ simple_decision.py           # 순수 position 분석 및 decision 통합
├─ simple_runner.py             # UI 없이 동기 실행·중단·Replay 기록
├─ live_analysis.py             # 계산된 decision의 표시 모델과 Reduction
├─ stage3_identity.py           # 동결 Stage-3 알고리즘 identity
├─ stage3_physical.py           # Model C/profile/table identity·인증·비용
├─ stage3_execution.py          # 고정 expert 보드 identity + 완료된 V1 실행
├─ stage3_execution_worker.py   # Stage-3 trusted-local subprocess 진입점
├─ stage3_execution_job.py      # 부모 process·token·임시 디렉터리 수명 관리
├─ stage3_visualizer_launcher.py # 실행·취소·결과 다시 열기, job/viewer 소유
├─ stage3_trace_player.py       # 정수 index 재구성·incremental next()
├─ stage3_modeled_playback.py   # 순수 modeled timeline·정확한 부분 시간·배속
├─ stage3_visualizer_ui.py      # 모드 controls·Qt frame 요청·synthetic cursor 표시
├─ same_board_comparison.py     # Human full-stream admission·고정 layout identity
├─ same_board_runner.py         # 독립 solver 실행·native evidence·분리된 metric
├─ same_board_execution_worker.py # token + 고정 board만 받는 subprocess
├─ same_board_execution_job.py  # parent 소유 process·취소·reap·cleanup
├─ same_board_playback.py       # 세 run의 독립 remembered action index
├─ same_board_comparison_launcher.py # captured context·job·완료 결과 소유
├─ same_board_comparison_ui.py  # 읽기 전용 결과·public observation·Human overlay
├─ replay_model.py              # Replay 데이터 계약
├─ replay_recorder.py           # 실제 이벤트와 확정 보드 기록
├─ replay_json.py               # JSON 변환·파일 입출력
├─ replay_player.py             # 독립 engine으로 재생
├─ replay_analysis.py           # 현재 position 추천과 다음 이벤트 비교
├─ replay_statistics.py         # 시점별 통계 timeline
├─ zini_calculator.py           # ZiNi 공개 API와 결과·설정 모델
├─ zini_core.py                 # 공통 시뮬레이션과 deterministic 정책
├─ zini_min_ties.py             # maximum-Premium 동점 탐색
├─ zini_advanced.py             # bounded neighborhood beam·chain 정책
├─ zini_metric_worker.py        # UI ZiNi 계산용 subprocess
├─ zini_trace.py                # 완료 경로의 사후 검증·진단과 논리 단계 재생
├─ zini_explorer.py             # 결과 transport 검증·Trace 지연 생성·세션 제어
├─ zini_explorer_ui.py          # 별도 읽기 전용 ZiNi Explorer 창
├─ scripts/
│  └─ benchmark_zini_advanced.py
└─ tests/                       # unittest 기반 단위·회귀·UI 테스트
```

## 테스트

Repository 루트에서 실행합니다.

```powershell
python -m unittest discover -s tests -v
```

Engine, 보드 분석, Replay, Simple Algorithm, Live/Replay Analysis와 Auto, ZiNi, Stage-3 실행·재생·Visualizer와 process lifecycle을 검증합니다. 구체적인 파일과 검증 범위는 [테스트 전략](ARCHITECTURE.md#test-strategy)을 참고하세요. 일부 UI 테스트는 PyQt5가 없으면 skip되므로 UI까지 검증하려면 위 의존성을 설치해야 합니다.

Qt UI 테스트는 기본적으로 `offscreen` 플랫폼을 사용합니다. Windows에서 플랫폼 플러그인 탐색 오류가 발생하면 `QT_QPA_PLATFORM_PLUGIN_PATH`를 해당 Python의 실제 PyQt5 설치 경로 아래 `Qt5/plugins/platforms` 또는 `Qt/plugins/platforms`로 지정합니다.

## Benchmark

고정 보드에서 ZiNi 전략별 클릭 수, 탐색 종료 사유, 실행 시간과 trace 유효성을 비교합니다.

```powershell
python scripts/benchmark_zini_advanced.py --board board_c --mode quick
python scripts/benchmark_zini_advanced.py --board expert1003 --mode quick
```

`--mode full`은 더 많은 평가 예산과 seed를 사용하며 수 분이 걸릴 수 있습니다. `--csv results.csv`로 결과를 저장할 수 있습니다. Benchmark는 단위 테스트를 대체하지 않습니다.

Expert seed 1003의 알려진 **120-click trace**는 `tests/test_zini_core.py`의 회귀 fixture로 유지됩니다. 테스트는 해당 trace의 재현, 클릭 합계, 안전 칸 완료와 깃발 유효성을 확인합니다. 이는 모든 설정의 탐색이 같은 값을 찾는다는 뜻은 아닙니다.

## 주요 제한과 향후 방향

- 잘못 꽂은 깃발은 분석의 가정을 깨뜨릴 수 있습니다. 감지된 모순은 분석 불가로 표시하지만 모든 오답 깃발을 찾아내지는 못합니다.
- 큰 constraint component의 exact probability는 지수 시간이 걸릴 수 있습니다. 현재 Live/Replay 분석은 UI thread에서 동기 실행되어 화면이 지연될 수 있습니다.
- Simple Algorithm은 닫힌 칸의 OPEN/FLAG만 추천합니다. CHORD·UNFLAG는 추천 범위 밖입니다.
- Replay schema v1은 full-game과 continuation/suffix를 구분할 metadata가 없습니다. 중간부터 기록한 구간의 복원·분석에는 [schema v1 한계](ARCHITECTURE.md#replay-schema-v1)가 적용됩니다.
- 향후 후보는 UI controller/worker 관리 분리, 분석 성능 개선, Replay checkpoint, subprocess 실패·취소 검증 확대입니다. AI 학습 환경은 아직 구현하지 않았습니다.

설계 목표, 모듈별 책임, 데이터 흐름과 invariants는 **[ARCHITECTURE.md](ARCHITECTURE.md)**에서 설명합니다.

## 라이선스 / License

Copyright © 2026 cube1793

이 프로젝트는 GNU General Public License v3.0 only (`GPL-3.0-only`)에 따라 배포됩니다.  
소스 코드는 해당 라이선스의 조건에 따라 사용, 수정 및 재배포할 수 있습니다.  
자세한 내용은 [`LICENSE`](LICENSE) 파일을 참고하세요.

This project is licensed under the GNU General Public License v3.0 only (`GPL-3.0-only`).  
See [`LICENSE`](LICENSE) for details.
