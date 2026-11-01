# RANDOM_EXPERT_EXHIBITION_V1 Source Closeout

Recorded: **2026-11-01 (Asia/Seoul)**. Non-frozen closeout record.

**새 standalone 전시 기능 source 구현·RF 수정·UI 보완 완료 / 사용자 native 재수용 기록.**
이번 V1은 전시 기능 버전이며 frozen Stage-3 V1 또는 K-P0의 정의를 바꾸지 않는다.

## 1. 수용과 authority

사용자는 UI 피드백 3건 반영 뒤 직접 확인하고 2026-11-01 (Asia/Seoul)에
**“방금 내가 수동으로도 확인했고 괜찮은것 같아.”**라고 보고했다.
이를 아래 snapshot과 일치하는 **현재 source의 사용자 native 재수용**으로 기록한다.
사용자가 보고하지 않은 실행 횟수·보드·승률·DPI·새 실행 receipt는 추정하지 않는다.

최초 구현/RF/UI 산출물의 생성 당시 PENDING USER 표기는 그대로 보존한다.
이 closeout이 후속 수용을 기록한다. RF-1~3의 Claude 독립 재감사 PASS는 그
lifecycle/transport 수정과 직접 회귀 범위이며, **새 UI 전체의 Claude 감사 PASS가 아니다**.
새 package/EXE 수용, Main/Live 통합 또는 통계 효과성 수용은 없다.

구현 의미는 실제 source/tests, 과거 실행은 각 receipt/evidence, frozen 계약은 해당
spec/protocol을 따른다. 이 문서·recovery·AI 해석은 이를 덮어쓰지 않는다.
사용자 보고는 수동 수용의 authority이며 새 자동 검증 결과를 만들지 않는다.

## 2. 보드와 실제 paired execution

- **EXPERT_GENERAL_V1 공개 corpus index 0..99999**, Expert 30×16 / 99만 지원한다.
  새 추첨 또는 index 지정을 제공하며 index/seed/fingerprint를 표시한다.
  unseen/holdout 생성기가 아니다. 바로 앞 index 제외 외 결과를 보고 재추첨하지 않는다.
- 보드는 한 번 생성해 같은 확정 layout을 두 fresh engine에 `reset_with_mines()`로
  설치·검증한다. all-HIDDEN, canonical OPEN(0,0), cursor(0,0), 같은 인증 Model C다.
  layout/fingerprint는 정책 입력으로 전달하지 않는다. 승리·zero opening을 보장하지 않는다.
- 하나의 child에서 **frozen V1 → actual K-P0**를 순차 실행한다.
  `run_control_capture()`가 unchanged `run_stage3()`를 실행하고,
  `run_k_p0(..., capture_effects=True)`가 실제 K 정책을 실행한다. K-CONTROL 대체가 아니다.
- 완주 runner를 재작성하지 않는다. native result/evidence를 검증·투영해 compact immutable
  결과를 만들고, V1의 불필요한 full evidence 참조는 K 실행 전 놓아준다.
  한쪽 LOST여도 다른 쪽을 실행한다. runner/transport 오류를 LOST로 바꾸거나 보드를 교체하지 않는다.

이 앱은 새로운 전시 실행이다. 고정 accepted E1을 읽는
[기존 D0–D5 연구 데모](STAGE3_PROGRAM_K_RESEARCH_DEMO_CLOSEOUT.md)와 별도다.
D5 adapter의 E1 case/schedule/hash qualification을 완화하거나 새 trace에 E1 provenance를
붙이지 않았다. production Same-board worker와 `main.py` dispatch도 그대로다.

## 3. 완료 trace와 관람 의미

각 결과는 실제 action 순서·target·cursor_before·modeled_action_us·terminal outcome과
index 0을 포함한 N+1 public frames, 누적 Model C를 보존한다. 첫/마지막 입력을 포함한
cost 합계가 native 결과와 같고 자동 WIN flags는 physical input 수에 넣지 않는다.

K의 logical M은 physical FLAG와 다르다. frame 0의 M은 비어 있고,
frame i+1에는 완료한 trace i의 `preinput_M`을 commit한다.
`M_before`는 직전 committed frame과 이어진다. 마지막 M도 마지막 정당한 trace에서만
오며 terminal answer나 자동 WIN flags로 과거 K 지식을 만들지 않는다.
physically HIDDEN인 logical mine은 빈 다이아몬드, physical FLAG는 깃발을 우선 표시한다.

partial 이동 중에는 synthetic cursor/target만 표시한다. board/M/완료 route/누적 Model C는
선택·완료한 frame에 고정된다. pause는 partial fraction을 보존하고 seek는 해당 패널을
멈춘 뒤 partial을 버려 선택 frame으로 이동한다. 탐색·설정 변경은 immutable memory만
읽으며 engine/solver 재실행, 보드 재생성, evidence I/O가 없다.

왼쪽 frozen V1과 오른쪽 연구용 K-P0는 각각 독립 index/playhead/clock을 가진다.
공통 명령도 index·진행률을 맞추지 않는다. 같은 input index나 진행률은 같은 보드 진척을
뜻하지 않는다. outcome, 전체/OPEN/FLAG/CHORD 수, Model C 종료 비용을 별도로 표시한다.
K-P0 minus V1 차이는 해당 보드의 기술적 산술이다.
**Model C time-to-win 차이는 양쪽 WON일 때만 정의되며 그 밖에는 N/A**다.
LOST 종료 비용을 승리 시간으로 비교하지 않는다.

## 4. 수용된 관람 조작

| 조작 | 동작 |
| --- | --- |
| 새 보드 추첨 / index 지정 / 취소 | 기존 corpus의 한 보드를 실행; 계산 중 중복 시작 방지 |
| 패널별 처음·이전·재생/일시정지·다음·끝·입력 번호 | 각 패널만 조작 |
| 함께 재생 | 각 현재 위치·속도로 시작/재개; running/ended 쪽을 toggle하거나 rewind하지 않음 |
| 함께 일시정지 | 두 timer 정지, 각 partial 보존; 반복 클릭 안전 |
| 함께 처음으로 | 같은 pair의 두 frame 0, M/route/누적 비용 0; partial 폐기, 각 모드·속도 보존 |
| slider | groove 왼쪽 클릭 위치의 가장 가까운 frame으로 직접 seek; style groove/handle span과 offset 사용 |
| handle / 키보드 | native press·drag·release, 키보드 탐색 유지; release에 추가 page step 없음 |
| 관람 간격 | 기본 250 ms=4 CPS, preset 200/500 ms 유지; custom 20~10000 ms / 0.1~50 CPS |
| Model C 시간 모드 | 기존 0.25/0.5/1/2/4/8배; 수동 관람 입력은 비활성화하되 값 보존 |

공통 버튼은 trace 없음·계산 중·clear·취소·닫기에 맞춰 활성 상태를 갱신한다.
수동 ms/CPS는 하나의 **Fraction µs duration**을 편집하는 두 표현이다.
UI 입력/표시는 소수 셋째 자리이며 반올림 환산값에는 `≈`를 붙인다.
예: 3 CPS의 내부 값은 `1000000/3 µs`, 환산 표시는 `≈333.333 ms`다.
표시 갱신 신호를 차단해 환산값을 setter로 되먹이지 않는다. 불완전한 타이핑은 적용하지 않고
확정/스핀 조절 때 반영한다. bool/0/음수/NaN/Infinity/범위 밖 API 값은 거부한다.
재생 중 변경은 구 속도로 경과 시간을 정산하고 partial fraction과 재생 상태를 보존한다.

관람 CPS는 설명용 입력 진행률이다. 계산 wall, Model C, 실제 인간 시간과 별개이며
synthetic 직선 커서는 실제 human mouse trace가 아니다. 관람 기본값의 근거·한계는
[Human pacing JSON closeout](STAGE3_HUMAN_PACING_JSON_V1_CLOSEOUT.md)을 따른다.
일반 안내는 한국어이며 source/hash 세부는 tooltip/정보에 둔다. 작은 창에는 패널별 scroll이 있다.

## 5. Windows lifecycle / RF-1~3

Qt UI thread에서 complete runner나 exact analysis를 실행하지 않는다. at-most-one child,
정수 request token, stale 배제, private trusted-local atomic transport를 사용한다.
worker는 GUI 없이 실행되며 사용자 파일 import 기능이 아니다. 완료 결과를 받은 뒤 재생한다.
Windows venv launcher는 suspended 상태에서 소유 Job Object에 할당한 뒤 실행하고
worker가 membership을 확인한다. cancel/timeout/close 의도 우선, terminate→kill→reap→
private cleanup 뒤 단일 종료 통지이며, 정리 실패는 소유권과 진단을 유지해 새 실행을 막는다.

| 수정 | 원인과 해결 |
| --- | --- |
| RF-1 | launcher 종료 직후 ActiveProcesses 집계 잔류를 즉시 실패로 오판. 최초 종료 관측에 **0.75초** 고정 drain deadline을 한 번 설정하고 QTimer/monotonic poll로 비차단 대기. zero가 되면 원래 판정, 계속 nonzero이면 소유 tree 종료·reap 후 FAILED |
| RF-2 | progress.json 교체의 Windows 공유 위반이 계산을 폐기. 내부 phase/completed는 유지하고 progress의 **OSError만** best-effort; 최종 result.pkl atomic 발행 실패는 계속 실패 |
| RF-3 | token 이전 REQUEST_TRANSPORT 원인이 malformed token에 가려짐. worker stderr에도 root cause를 남겨 부모 bounded stderr tail에 보존. containment 순서와 엄격 token/index/envelope 수용 검사는 유지 |

**pair parent wall cap 120초는 그대로**다. drain보다 cap/cancel 의도가 먼저다.
119.6초 종료 관측으로 drain deadline이 120.35초여도 120.0초에는 TIMEOUT이며,
120.05초 cleanup 완료는 성공이나 cap 연장이 아니다. GUI poll에 sleep/양수 wait를 넣지 않았다.
이 cap은 전시 응답성 보호값이고 solver cap/연구 Operating Envelope가 아니다.
timeout/cancel은 미완료이며 WON/LOST/승리 시간을 만들어내지 않는다.

## 6. 단계별 검증 기록

아래는 각 단계의 보존된 기록이다. 겹치는 검사·반복 실행을 새 독립 검사/표본으로 합산하지 않는다.
이번 문서 작업에서는 테스트·앱·solver·분석을 실행하지 않았다.

| 단계 | 기록된 검사 / 실행 | 판정과 범위 |
| --- | --- | --- |
| 최초 구현 | focused 50 + direct helper 41 PASS; 이후 fixture 관련 13 재확인 | 고유 91, 반복 13은 추가 고유 검사 아님; 이전 개발 중간 실행은 원본 로그에 보존 |
| 최초 Claude 감사 | focused 50 PASS + 자체 경계/Windows 검사 | 종합 REQUIRED_FIXES RF-1~3; execution/projection/M/playback/containment PASS 영역 구분 |
| RF 수정 | focused **67=기존50+신규17**, suite 1회 67 PASS, 실패/오류/skip 0 | lifecycle/transport 회귀; helper41 재실행 없음 |
| RF 실제 Windows | 별도 **50회** = 정상 synthetic40 + progress lock1 + final lock1 + absent scope3 + invalid index5 | production QTimer 50ms / 실제 Job Object·venv launcher; 정상40 오폐기0·owned worker 잔류0. Expert40 실행 아님 |
| RF 실제 paired smoke | **board97 1회**, 120초 cap, wall 3.032초 | 실제 ExhibitionJob→worker→frozen V1→actual K-P0; SUCCEEDED, exit0, reap/cleanup, tree0 |
| RF Claude 재감사 | focused67 1회 PASS + 자체 RF 경계/실제 Windows 재현 | **PASS, 새 REQUIRED_FIXES 없음**. 정상40 중 **회차26/32**는 실제 drain 뒤 성공; 생존 descendant1회는 정리 후 FAILED |
| UI 보완 첫 suite | 고유 **84=기존67+신규17**, 전체 1회 **83 PASS / 1 FAIL / 0 ERROR / 0 SKIP** | offscreen held-button drag event 전달 실패 기록 보존 |
| UI 관련 재확인 | test-only 전달 보정 후 slider **4 PASS** | 총 **88 method 실행**, 미해결0. 최종84 전체 suite를 다시 한 번 모두 PASS한 것은 아님 |
| UI 개발 native | windows backend, 1920×1080 / 96 DPI·100%, 작은 창900×760 | 인증된 저장 RF smoke97 trace 주입; 새 solver 실행/사용자 수용 아님 |
| 사용자 후속 native | 위 §1의 사용자 직접 확인 보고 | 현재 source 재수용; 횟수·보드·DPI 등의 새 receipt는 없음 |

최초 Claude의 정상40 중2 오폐기와 오류경로30 중3 오진단은 당시 관측값이지 발생률 추정이 아니다.
RF 재감사의 정상40과 Codex 정상40도 별도 batch이며 효과성 표본으로 합치지 않는다.
기존 실제 cancel/timeout/close와 주입 clock의 정확 cap 경계 검사는 각 focused 기록에 있다.
실제 Expert 보드로 120초를 기다린 검사는 주장하지 않는다.

UI 실패는 기본 QSlider와 새 slider 모두 QTest.mouseMove 후100, explicit held-button
QMouseEvent 후140이었던 대조로 확인했다. QTest press/release를 유지하고 중간 이동만
test에서 보정했다. `REPORT_KO.txt`, `validation_summary.json`, `test_ui_attempt_01.py`,
`drag_diagnosis.json`, 두 검사 로그가 이 경위를 보존한다. 해당 기록에 따라 **초기 suite 후
production ui/playback source는 바뀌지 않았고 drag test 전달만 수정됐다**고 기록한다.
별도 native 전후 source hash도 동일하다. 이는 새 전체 suite 실행을 뜻하지 않는다.

UI 개발 native의 화면 index/표시 보드는 모두97로 맞췄다. 서로 다른 속도의 공통 재생/정지,
먼 클릭·non-center drag, reset, 3 CPS/249 ms 확정 입력, 작은 창 scroll과 닫기를 기록했다.
화면5장·native_session/verification에 source29 hashes, 요청0, guarded solver/생성0,
exit0·소유 process/temp 없음이 남아 있다. 과거 trace.source는 변경하지 않았다.
**UI Claude 독립 검토, 다른 DPI/OS/모든 Qt style, 새 package/EXE 검증은 미수행**이다.

## 7. 사전 고정 pilot과 RF smoke

최초 Expert pilot **11, 97, 2026 각1회**, 재시도 없음. generator는 EXPERT_GENERAL_V1,
seed=index이며 모두 parent SUCCEEDED / exit0 / reap·cleanup 완료 / tree0이었다.
아래 비용은 terminal까지의 Model C µs이며 wall과 다르다.

| index | 알고리즘 | outcome | 전체 (OPEN / FLAG / CHORD) | Model C 종료 비용, µs |
| --- | --- | --- | --- | ---: |
| 11 | V1 | LOST | 180 (36 / 80 / 64) | 31,903,234 |
| 11 | K-P0 | LOST | 147 (74 / 32 / 41) | 25,850,847 |
| 97 | V1 | WON | 198 (38 / 97 / 63) | 36,301,612 |
| 97 | K-P0 | WON | 136 (64 / 30 / 42) | 24,410,331 |
| 2026 | V1 | LOST | 214 (24 / 98 / 92) | 39,348,203 |
| 2026 | K-P0 | LOST | 175 (71 / 44 / 60) | 31,297,480 |

| index | fingerprint | 최초 parent wall, s | K−V1 Model C time-to-win, µs |
| --- | --- | ---: | ---: |
| 11 | `7747c9bbb6b29e2b8b8e138d3b5db2baee283fa4bc03d8128000ff1abcb45d6c` | 2.516 | N/A |
| 97 | `934b8add0bd242af16729c74130c12ca1973a6805292d1b41ce72240a6549861` | 2.437 | −11,891,281 |
| 2026 | `d6db3efd68fdbc362709429d64c8d0742ea22301396f620c471014c125b167ca` | 2.906 | N/A |

RF smoke97은 같은 index의 실제 재실행1회로, 원래97과 board/전체 action·frame·M·cost 및
algorithm/physical identity가 동일한 기록이다. UI native97은 **그 저장 trace의 재생**이다.
이를 새 독립 보드로 세지 않으며 세 pilot으로 일반 승률·속도 향상·대표성·효과성을 주장하지 않는다.

## 8. 실행과 source identity

기존 승인 venv/PyQt5, 현재 checkout 및 인증된
`calibration/stage3_physical_profile_v1.json`과 Git을 사용한다. 설치·새 환경은 필요하지 않다.
기록된 개발 환경은 Windows 11 / Python 3.12.10 / PyQt 5.15.11 / Qt 5.15.2이며,
이번 문서 작업이 다른 환경을 새로 qualification한 것은 아니다.
PowerShell의 일반 native 환경에서 `QT_QPA_PLATFORM=offscreen`이 설정되지 않아야 한다.

```powershell
Set-Location -LiteralPath 'C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m experiments.random_expert_exhibition
```

선택적으로 `--index 97`을 붙이면 창을 연 뒤 그 index를 한 번 실제 실행한다.
source entry는 [random_expert_exhibition.py](../../experiments/random_expert_exhibition.py)다.
개발용 저장 trace 주입/shortcut은 production 기능이 아니다. 새 source는 새 창에서 실행한다.

**2026-11-01 문서 작업 시작의 커밋 전 snapshot**: main,
HEAD == local origin/main == `6b26697b7986752966b67035ecf7e3ba73465f35`, ahead/behind0/0,
tracked/staged diff 없음, source8+tests5=**13파일 untracked**.
이는 clean 또는 HEAD만으로 재현되는 구현이 아니다. 현재13파일은 UI의 `after/` 및
inventory와 hash/byte 일치한다. 이번에 기존 문서5개와 새 closeout2개를 준비한다.
향후 사용자 commit 뒤에도 이 SHA를 latest HEAD로 간주하지 말고 live Git을 다시 확인한다.

원래 pilot, RF smoke, 최신 viewer는 각각 실제 source hashes/dirty 상태를 가진다.
RF는 job/worker가, 후속 UI는 ui/playback이 변경됐다. 과거 receipt를 최신 source 실행으로
재표기하지 않는다. D5 final package source는 계속
**`fb59d5fa253f04f50ea57c6a9e863aa1999a517e`**다. 미래 커밋 SHA는 지정하지 않는다.

## 9. 상세 출처·복구·남은 경계

아래 root들은 읽기 전용 역사적 기록이다. 생성 당시 PENDING과 실패 로그도 보존한다.

| root (공통 prefix `C:\Projects\GraduationProject\`) | 주요 기록 |
| --- | --- |
| `RANDOM_EXPERT_EXHIBITION_V1_2026-11-01` | REPORT_KO.txt, implementation_summary.json, MANIFEST.json, pilot_results.json, pilot_11/97/2026_source.json, review_claude/CLAUDE_REVIEW_KO.md·crosscheck.json |
| `RANDOM_EXPERT_EXHIBITION_V1_RF_FIX_2026-11-01` | REPORT_KO.txt, RF_RESOLUTION.json, MANIFEST.json, focused_01, windows_checks, smoke_97.json, review_claude/CLAUDE_RF_REVIEW_KO.md·crosscheck.json |
| `RANDOM_EXPERT_EXHIBITION_V1_UI_FEEDBACK_2026-11-01` | REPORT_KO.txt, UI_FEEDBACK_RESOLUTION.json, MANIFEST.json, feature_file_inventory.json, validation_summary.json, focused_01, slider_recheck, drag_diagnosis.json, native_session.json·native_verification.json |
| `RANDOM_EXPERT_EXHIBITION_V1_DOC_CLOSEOUT_2026-11-01` | 이번 closeout의 SOURCE_SNAPSHOT.json, Git·보존·문서 점검, REPORT_KO.txt, DOCUMENTATION_CLOSEOUT.json, RECOVERY_CURRENT_KO.txt, RECOVERY_CONTEXT_KO.txt, COMMIT_PLAN.json |

이번 문서 작업은 source13/tests를 수정하지 않고 명명된 source/evidence/manifest hash와
문서 링크·실행 entry·Git/whitespace만 확인한다. 기존60 핵심 파일 중 README/ARCHITECTURE/
handoff 3개만 이번 승인 문서 갱신 대상이며 나머지57과 absent3는 보존 대상이다.
원본 manifest/report를 갱신하지 않고 새 snapshot에 변경 이유를 기록한다.

**Program K D0–D5 FINAL ACCEPTANCE PASS / CLOSED**, **PHASE1_INCONCLUSIVE_TRANSFER**,
effectiveness **NOT ESTABLISHED**, Production K/Gate P 미승인을 유지한다.
Phase2/R0-B/ActualE2/추가 profiling/Stage4, ZiNi final holdout
`2,010,000..2,010,099` 생성·열람·사용은 승인되지 않았다.
Main/Live selector 통합은 미구현이며 새 package/EXE도 없다.
Extended 전체 종료는 결정하지 않았다. 문서·커밋 마무리 후 다음 work unit은 사용자가 선정한다.
**stage/commit/push/merge는 사용자 수행**이며 이 작업은 검토 가능한 계획에서 STOP한다.
