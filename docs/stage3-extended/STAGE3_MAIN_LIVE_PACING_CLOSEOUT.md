# Main/Live 관람 속도·고정 CPS·입력 정밀도 closeout

문서 기준: **2026-11-05 (Asia/Seoul)**. 구현, 범위 한정 독립 검토 및 사용자 native 수용을 완료했다. 최종 사용자의 **“좋아, 전부 통과인 것 같아.”**를 현재 환경과 전달한 확인 항목의 수용으로 기록한다. 모든 OS/DPI·preset 완주·전체 suite·모든 부하에서의 속도·effectiveness·Production 승인을 뜻하지 않는다.

이 문서는 [LC1/표시 closeout](STAGE3_MAIN_LIVE_K_LC1_DISPLAY_CLOSEOUT.md) 이후 누적된 속도 변경의 현재 authority다. 이전 연결·인수·Replay·확정색 계약은 유지한다. 과거 보고서의 FAIL/PENDING은 당시 bytes와 실행 범위의 역사이며 덮어쓰지 않는다.

## 1. 현재 사용자 동작

- 새 창은 **고정 간격 200ms / 목표 CPS 5**, Auto OFF, 추측 OFF다. 사용자가 바꾼 값은 정책 변경·reset·Replay 왕복으로 기본값에 덮어쓰지 않는다.
- 고정 모드에서는 **자동 간격·목표 CPS**만, Model C 모드에서는 **Model C 배속**만 편집한다. 모드별 값은 따로 보관하며 숨긴 필드의 늦은 편집 신호는 적용하지 않는다.
- 목표 CPS는 OPEN·FLAG/UNFLAG·CHORD 한 행동을 각각 1회로 센 목표 속도다. 보조적인 셀 개방 개수나 물리 마우스 버튼 개수로 세지 않는다. 왼쪽 Counters CPS는 기존 전체 클릭 수/게임 경과 시간이다. 시작·수동·pause·계산 지연 등을 포함하므로 목표와 항상 일치하는 계기가 아니다.
- CPS **6을 입력하면 6이 남는다**. 실행 주기는 **166,666,667ns**, 간격 표시는 **166.667ms**다. 화면에 반올림된 값을 실행 주기에 다시 넣지 않는다.
- Main의 K-P0/K-LC0/K-LC1 콤보·정책·분석 결과 줄에서 `(실험적)`을 제거했다. 라벨 정리일 뿐 Production 또는 정책 freeze 변경이 아니다.
- 같은 보드를 새 게임으로 다시 플레이하는 Main 기능은 **미구현**이다. Replay 시청 및 별도 Same-board Comparison은 재플레이 기능과 다르다.

## 2. 실행 주기와 시간 경계

`live_pacing.FixedPeriod.period_ns` 하나가 고정 실행 주기의 권위다. CPS는 정확한 Fraction으로 읽어 `ceil(1,000,000,000 / CPS)` ns로 만든다. ms 직접 입력은 정확한 수에 1,000,000을 곱해 올림한다. CPS 범위는 0.5–1000, 유한 ms는 1–2000이며 0ms는 준비되는 대로 한 입력씩 실행하는 최대 속도다. 범위 밖·잘못된 입력은 이전 유효값으로 돌아간다.

| 입력 | 실행 주기 | 표시/의미 |
| --- | ---: | --- |
| 5 CPS | 200,000,000ns | 200ms |
| 6 CPS | 166,666,667ns | 166.667ms, 목표 6 유지 |
| 3 CPS | 333,333,334ns | 333.333ms, 목표 3 유지 |
| 7 CPS | 142,857,143ns | 142.857ms, 목표 7 유지 |
| 250ms | 250,000,000ns | 4 CPS |
| 0ms | 0ns | 최대 속도, 유한 CPS 목표 아님 |

`source/requested`는 사용자가 마지막으로 편집한 표현을 보관할 뿐 별도 실행 권위가 아니다. 같은 주기를 다른 문자열로 확정해도 phase·timer·nonce·보류 permit을 다시 만들지 않는다. 실제 주기 변경만 기존 취소·응답 drain·재예약 경로를 사용한다. Enter/focus-out/spin 확정과 편집기 키보드 보호를 유지한다.

### 고정 모드의 제한된 위상 보정

`live_fixed_cadence.FixedCadence`는 실제 시각과 예정 목표를 분리한다. P는 정수 ns 주기, T는 이번 예정 목표, A는 실제 입력 시각이다.

1. Auto ON/재개/실제 속도 또는 모드 변경 시 첫 목표는 해당 시각+P다. 첫 owner 준비 중 판·정책·revision이 같고 아직 입력이 없으면 이 첫 목표를 보존한다.
2. `0 <= 10*(A-T) <= P`이면 다음 목표는 **T+P**다. 작은 지연은 예정 흐름을 유지해 누적하지 않는다.
3. 더 늦거나 유효한 위상이 없으면 다음 목표는 **A+P**다. 밀린 입력을 여러 개 몰아 실행하지 않는다.
4. 각 입력은 자기 예정 목표보다 빠르지 않다. 작은 보정으로 연속 입력 간격은 **0.9P**까지 짧아질 수 있다. 200ms 설정에서 180ms는 허용되며, 모든 간격이 정확히 200ms라는 계약이 아니다.
5. phase는 game/policy/run/generation/revision과 함께 관리한다. 수동 인계·OFF·reset·정책/모드 변경 이후 옛 위상을 재사용하지 않는다.

고정 모드는 **Qt.PreciseTimer**, Model C 모드는 기존 timer type을 사용하며 정지한 뒤 type을 바꾼다. 예정 시간 판정은 **time.perf_counter_ns / QPC**다. timer가 일찍 울리면 남은 시간을 다시 기다린다. OS 타이머 설정 변경, busy wait, 추가 thread 또는 미래 여러 수의 queue는 없다.

K는 현재 proposal만 VALIDATE한다. 남은 주기 중 검증할 수 있고 일찍 온 permit은 token을 소비하지 않고 보관한다. 목표 도달 후 조건을 다시 확인하고 기존 **최종 비교 → token 소비 → 실제 step 1회**를 yield 없이 수행한다. 정확한 원 입력의 ACK 전에 NEXT를 보내지 않는다. 보류 중 입력 이력 변조·늦은 응답·수동 인계·종료의 방어는 유지한다.

### Model C 모드

원 frozen 행동 비용을 배속(정확한 Fraction, 0.05–8)으로 나눈 **관람 지연**을 사용한다. 기존 표·실행 비용 기록·정책 선택을 수정하지 않는다. 고정 모드의 위상 보정을 Model C에 적용하지 않는다. V1/K의 원형은 `perf_counter` 초 단위로 보간하며 ns deadline과 서로 다른 기준점을 섞지 않는다.

Model C는 이미 거리별 비용을 포함하지만 관람 지연은 실제 계산·통신 시간과 별개다. 인간의 행동 속도를 실측 보장하는 모델도 아니며, 이전 `기준 CPS(1칸)` 환산 UI는 현재 제거됐다. 추가 거리별 보정이나 녹화 기반 자연스러운 속도 프로필은 별도 후속 작업이다.

## 3. 검증 계보와 최종 결과

아래는 **서로 다른 bytes·선택 범위**의 실행이다. 행별 수를 더해 전체 suite PASS로 부르지 않는다. 원 구현/독립 보고서와 원시 timing·실패 기록은 외부 output에 보존한다. coordinator는 이번 문서 마감에서 프로젝트 Python/Qt/worker를 실행하지 않았다.

| 단위 / 독립 검토 | 실제 확인 범위와 판정 |
| --- | --- |
| Model C 최초 검토 | 263 methods / 412 subtests, real 3사례/4owner/5입력. **RV-R1 FAIL**: coarse clock 때문에 Simple 18회 중 7회 조기 입력, 최대 약 3.82ms. 제품 자체의 같은 clock 측정만으로는 검출하지 못함 |
| Model C clock 보충 | 267/462, real 3사례/4owner/5입력/VALIDATE4, probe18. Qt timer32회·Simple18회 조기0. QPC100ns와 원형의 초 단위 확인. **RV-R1/RV-O2 CLOSED**, 이전 FAIL 유지 |
| 최초 정수 ms↔CPS | 선별 **87/247**만 독립 실행, worker0. 274개 전체 독립 PASS 아님. 이후 exact ns 계약으로 대체 |
| 기본200ms/K 라벨 | 10/45, worker0. 남은 분석 줄 라벨 보충은 **정적 검토만**, 독립 Python/Qt 재실행0. 구현자 최종6/9는 별도 근거 |
| 최초 실제 고정 간격 | 291/518, real4owner/121입력, probe48. 당시 계약은 범위 한정 PASS였지만 **D1: 지표 선택 문제**를 발견. 수동 prefix가 든 카운터/engine 기준이 실제 행동 속도를 부풀림 |
| PreciseTimer 단독 구현 | 74/306, 3owner/126입력, 조기0. 실제 간격 기준 V1 4.8359 PASS, LC1 **4.7258 FAIL**. 독립 단독 검토를 생략하고 다음 보정 검토에 포함 |
| 제한된 고정 위상 보정 | 84/696, 3owner/126입력, probe37, 정적13. 독립 V1 **4.993804**, LC1 **4.922384**. 각60입력. 조기/최소간격 위반0, 필수 수정0 |
| **최종 정밀 입력 UI** | **105 methods / 1,084 subtests**, **3owner/96입력**, probe32. 목표 이전 입력·최소간격 위반0, 필수 수정0. 소스327개와 결속 |

최종 독립 실행의 V1 10입력씩 세 구간은 6 CPS **5.974007**, 250ms **4.000381**, 다시 6 CPS **5.971516**이었다. 짧은 관찰값이며 고부하 처리량 보장이 아니다. LC1 기본 5 CPS 60입력은 **4.903573 CPS**, 평균 약203.9ms였다. 구현자의 같은 종류 실행 LC1 **4.833199**와 서로 대체하지 않는다. 모든 owner의 reap/tree0/channel/handle 정리를 확인했다.

현재 속도 검증의 주 지표는 **(N−1)/(마지막 Auto 입력 시각−첫 Auto 입력 시각)**다. 수동 prefix·시작/종료 시간은 제외한다. 4.75–5.25 수용 범위 및 P/10 보정 한도는 **coordinator가 정한 기준**이며 사용자가 직접 정한 숫자가 아니다. 왼쪽 Counters 정의는 바꾸지 않았다. 실제 LC1 계산 부하가 커지면 deadline을 놓쳐 속도가 내려갈 수 있다.

## 4. 증거 위치·identity와 실패 보존

외부 root: `C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs`.

각 root의 `codex_*`는 구현, `review_claude_*`는 독립 검토다.

- `MAIN_LIVE_MODEL_C_PACING_UNIT1_2026-11-04`: codex_01/02, review_claude_01/02.
- `MAIN_LIVE_CPS_INTERVAL_UNIT1_2026-11-04`: codex_01, review_claude_01_trimmed. 원 미실행 kit와 구분한다.
- `MAIN_LIVE_DEFAULT_LABEL_POLISH_2026-11-05`: codex_01/02/03, review_claude_01/02.
- `MAIN_LIVE_FIXED_ACTION_CADENCE_UNIT1_2026-11-05`: codex_01/02, review_claude_01. profiling을 줄인 저부하 harness 승격 및 최초 성능 미달을 보존한다.
- `MAIN_LIVE_PRECISE_CADENCE_UNIT1_2026-11-05`: codex_01의 LC1 미달 기록.
- `MAIN_LIVE_FIXED_RATE_UNIT1_2026-11-05`: codex_01, review_claude_01.
- `MAIN_LIVE_PACING_INPUT_PRECISION_UNIT1_2026-11-05`: codex_01, review_claude_01. 최종 source/실행 authority.
- `MAIN_LIVE_PACING_DOC_CLOSEOUT_2026-11-05/coordinator_01`: native 수용, 문서 전후, 검증 및 사용자 Git plan/receipt.

| 최종 핵심 파일 | SHA256 |
| --- | --- |
| precision codex_01/source_manifest.json (327) | `a700d67dfabc6df4a9ed597c2bf0e4d228a7f4ed830bcd8a0f6495c7d78fc228` |
| precision codex_01/OUTPUT_MANIFEST.json (236) | `cf7af506b437dfa8e30e844078abacf253ae59dc68484a18b4f0fe49c690d0dd` |
| precision review_claude_01/OUTPUT_MANIFEST.json (71) | `30ea8804abb7683e83e7d98f755edb4c7d1e9455030d26dd41211c8d7f22cbcc` |
| fixed-rate review_claude_01/OUTPUT_MANIFEST.json (63) | `62f8adabe01b7c0de25bb649e4a15b0732e4c196887e5c14142a10672098c1ce` |
| clock review_claude_02/OUTPUT_MANIFEST.json (72) | `0a3731f20c405dff0e57cc225e304c9c63b4a90ea7c59799ca8927b729b68dea` |

clock FAIL·profiling 성능 FAIL·PreciseTimer LC1 FAIL은 최종 수용으로 삭제하지 않는다. 최종 UI D01은 제품 편집기 결함으로 D02에서 수정했고, D03은 창을 표시하지 않은 시험 누락으로 D04에서 수정했다. 최종105개에 모두 포함됐다. 최초 정적 LF/CRLF 검사기의 오류도 원 결과·보완 결과를 함께 보존한다. helper 오류/복구/과도한 파일명 열거와 실행 당시 설정·미확인 항목은 각 원장을 따른다.

## 5. 남은 선택 사항과 영구 경계

최종 OPTIONAL은 표시값과 비교하는 editor `setValue`의 API 명칭/의미, 부하에 따른 위상 재시작, 제품 지역 변수 이름에 의존하는 측정 harness다. 현재 사용자 경로의 필수 수정은 아니다. 이전 tooltip·focus·초기화 순서·pause 문구 등은 구현 시점별 기록을 보존하며 한꺼번에 해결됐다고 주장하지 않는다.

다음 후보는 **같은 보드 다시 플레이**, **0ms/고속 CPS·burst 처리량 측정 후 필요한 최적화**, **거리별 자연스러운 관람 속도 보정**이다. 각각 별도 범위·인계가 필요하며 이번 문서 마감은 해당 구현을 시작하지 않는다. 같은 보드 기능의 진행 중 허용 여부 등 세부 UX는 후속 단위에서 정한다.

**D0–D5 CLOSED**, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE. Phase2/R0-B/ActualE2 미승인/미실행, frozen 정책·원 Model C·holdout **2,010,000..2,010,099** 및 공식/formal evidence 경계를 유지한다. 과거 **F02 NOT_VERIFIED**, **Qt shared FileDialog FAIL**, **TEMP NOT_VERIFIED**는 유지하며 재검증 루프를 열지 않는다. 새 package/Stage4/연구 승인을 뜻하지 않는다.

## 6. 문서 마감과 사용자 Git 절차

작성 시 main / HEAD = local origin/main = **68c272e7272032cdfe9774a36d41c3686a8f375e**, ahead/behind0/0, staged0. 기존 source/tests **22경로(M9/U13)**에 문서 **6경로**를 더한 **28경로(M14/U14)**만 한 번에 stage/commit/push하도록 준비한다. 문서는 README, ARCHITECTURE, docs index, CURRENT_HANDOFF, Extended index와 이 파일이다. 다른 과거 closeout 본문은 수정하지 않는다.

coordinator는 source327, 원 구현·검토 manifest9개와 포함 파일, 다른 문서·Desktop recovery를 대조한다. 실제 사용자 script는 HEAD/index/status/raw hash/정규화 blob을 확인한 뒤 지정 경로만 처리한다. **Git 쓰기와 Desktop 교체는 사용자 단계**다. 완료 SHA는 후속 실제 receipt/recovery/live Git을 따른다. 문서의 precommit 시각을 바꾸기 위한 추가 commit은 만들지 않는다.

NEXT: 사용자 `USER_GIT_STEPS_KO.ps1` 한 번 실행 → 실제 receipt/부모/변경 경로/blob/push/clean 확인 → 새 commit에 결속된 recovery 두 사본 준비 → 사용자 Desktop 교체 → 다음 구현 단위. 과거 완료 script는 재실행하지 않는다.
