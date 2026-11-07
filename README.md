# Minesweeper Project

Python과 PyQt5로 개발한 지뢰찾기 졸업프로젝트입니다. 직접 플레이하면서 통계를 확인하고, Simple Algorithm, frozen Stage3 V1과 K-P0/K-LC0/K-LC1으로 현재 수를 분석하거나 Main/Live Auto를 진행할 수 있습니다. Replay 기록·재생·분석과 3BV/Ops, ZiNi 보드 분석까지 구현되어 있습니다.

## 핵심 기능

- **게임:** 초급·중급·상급·사용자 지정 난이도, OPEN·FLAG·CHORD, 화음 입력 방식과 셀 크기 조절
- **플레이 통계:** Time, Est Time, 3BV, 3BV/s, Ops, 클릭별 active/wasted 집계, CPS, Efficiency, IOE, Thrp, Corr, ZiNi, ZNE, ZNT
- **Simple Algorithm:** 확정 수와 최소 지뢰 확률 후보 표시, 확정 수 자동 진행, 선택적인 추측 실행
- **Replay:** JSON 저장·불러오기, 위치 이동과 자동 재생, 시점별 통계, 녹화된 다음 입력과 별도 Simple 참고 분석
- **같은 보드 재플레이:** 종료판의 동일 배치로 새 판 시작, 같은 배치 완료 기록 보관, Replay 기본 종료와 원 배치 재플레이 선택
- **Human Mouse Trace:** Live 보드의 실제 포인터 경로와 action marker 기록, 게임 종료 후 또는 Replay에서 선택적으로 표시
- **Same-board Comparison:** 완료 Human Replay의 고정 배치에서 Human / Stage 2 / Stage 3 결과와 선택 run의 독립 Index/시간 재생, 정답 참조·완료 action-target route 표시

## Stage 4 — 공개 정보 효율 계획 기반과 제한 선택 정책

공개 관측만으로 오프닝의 지뢰/0 확률을 계산하는 `stage4_opening.py`와, 작은 상태에서 OPEN·FLAG·CHORD 수순을 비교하는 `stage4_planning.py`를 추가했습니다. **안전성 유지(S), 평균 성과(M), 목표 기록(R)**는 공통 후보군을 서로 다른 위험 조건과 목적함수로 평가합니다. 속도·이동 거리·Model C 시간은 이 선택 목표에 들어가지 않습니다.

Unit 1·2의 기반에 이어, `stage4_evaluation.py`로 실제 한 입력마다 다시 계획하는 평가기를 추가했습니다. Unit 3은 등록된 작은 사례에서 독립 한정 수용됐고 필수 수정은 0건입니다. 최종 36설정의 점수 비교가 일치했으며, 123건은 동결 후 신규 113건과 동결 전 완료 기록 재사용 10건입니다. 세 방식이 평균 효율과 목표 도달 확률에 따라 다르게 선택하는 사례도 확인했습니다.

Unit 4의 `stage4_belief.py`는 공개 관측과 전체 지뢰 수로 배치 수 D, 칸별 지뢰 배치 수 M, 여러 칸의 공동 사건 수 W를 정확히 계산합니다. 새 시험 21개와 독립 재계산을 거쳐 한정 수용됐습니다. 기존 Replay의 상급 크기 6관측에서도 값이 일치했으며, 시간·작업 한도 안에서 완료하지 못한 값은 미확정으로 남깁니다. 행동을 고르는 정책이나 일반 상급판 전체의 실용성 검증은 아직 아닙니다.

Unit 5의 `stage4_candidates.py`는 직접 OPEN, 깃발 해제와 CHORD 준비를 포함한 후보 수순의 전체 입력 비용·공동 생존·0 사건을 계산합니다. 새 시험 A 25개/B 1개, 엔진 339 macro와 큰 공개 관측 6개의 독립 재현을 거쳐 한정 수용됐습니다. S/M/R의 위험 허용을 표시하며 최종 행동은 아직 선택하지 않습니다.

Unit 6는 `stage4_posterior.py`·`stage4_rollout.py`·`stage4_policy.py`로 공개 배치 표본, 고정 P0 가상 진행과 실제 다음 입력 한 개를 반환하는 S/M/R 선택기를 추가했습니다. 독립 ACCEPT_BOUNDED와 구현자 PARTIAL/U6-R02 이력은 유지합니다. 당시 큰 18호출의 fallback은 Unit 6의 결과로 남깁니다.

Unit 7은 P0 추측 밀도의 중복 계산을 줄여 등록 조건의 모델 평가 완료 범위를 넓혔습니다. 기본 10M은 6/18 완료·12 fallback이며 완료 6건 모두 모든 후보의 모델 점수가 0입니다. 별도 EXPANDED 30M은 18/18 완료지만 그중 9건은 점수가 0입니다. 독립 필수 수정은 0건이며 실행 속도·실제 승률·효율 향상은 확립되지 않았습니다. 그 당시의 밀도 P0와 기본값은 유지하며, Unit 8은 별도 모듈로 추가했습니다.

Unit 8은 공개 정밀 확률 후속 Q와 목적별 평가 G의 프로토타입을 추가했습니다. 제품 축은 **ACCEPT_BOUNDED**, 제품 필수 수정 0이며 구현자 **PARTIAL**, U8-H05와 원 manifest 부재는 유지합니다. Q 15/G 14 시험과 작은 G·엔진 경로는 독립 수용됐지만, 큰 평가는 기본 0/18·확대 3/18 완료에 그쳐 실제 효율 향상은 확립되지 않았습니다. G의 점수는 후보 뒤 Q 모델의 값이며 매 입력 다시 G를 부르는 실제 정책의 정확한 성과와 구분합니다. RV8-H1 합산 helper는 별도 보정본의 합산만 확인했고 원 실행은 재수행하지 않았습니다.

Unit 9는 정확 계수와 READY 캐시를 결합한 보존 후보를 독립 검토했습니다. 두 hard 상태의 D/M과 후보 수학은 재현됐고 기본 예산 완료는 0→3/18로 증가했지만, 확대 예산은 3→3/18이라 채택 기준에 미달했습니다. **PARTIAL_IMPROVEMENT와 원복이 정당하며 후보는 현재 제품에 없습니다.** 같은 시간·명목 한도를 비교했으며 별도 auxiliary 작업까지 같은 총 계산량이었다는 뜻은 아닙니다. 필수 발견은 제품/근거 모두 0, 선택 11건을 보존합니다.

Unit 10은 `stage4_belief_counter.py`로 독립 base D/M 계수기를 추가했습니다. 전파·메모 계산의 보조 처리까지 합쳐 20만 작업/협력 2초를 적용하며 호출 간 캐시는 없습니다. 작은 28문제·918 mask와 큰 8관측의 D/M이 독립 재계산과 일치했고, hard 두 상태는 각 측정 3/3회 완료했습니다. 제품/API·과금·중단·메모는 **ACCEPT_BOUNDED**, 필수 수정은 제품/근거 모두 0입니다. Unit 10의 수용은 독립 API 범위였으며 일반 안정 시간과 실전 효율은 미확립입니다.

Unit 11은 Q/G에 합산 계수기를 API 선택 옵션으로 연결했습니다. 기본은 `UNIT4_LEGACY`이며 `UNIT10_SUMMED`는 명시적으로 지정합니다. 연결·회계는 등록 범위에서 독립 수용됐고 필수 수정은 0건입니다. 검토된 네 파일을 반영한 뒤 A의 48개 메서드가 통과했습니다. 큰 요청의 READY는 기본 0/18, 확대 3/18로 이전과 같으며 실전 효율은 미확립입니다.

작은 상태의 계획기는 최대 64칸·닫힘/깃발 8칸의 선언 후보군을 지원합니다. 새 계수기의 480칸 상한이 이 계획기의 지원 범위를 넓히지는 않습니다. Main 메뉴에는 아직 연결하지 않았으며 Unit 2 C01과 Unit 3 U3-H01, 이전 구현자의 PARTIAL은 별도로 보존합니다.

현재 범위는 [Stage 4 인덱스](docs/stage4/README.md), [기반 closeout](docs/stage4/STAGE4_OPENING_PLANNING_FOUNDATION_CLOSEOUT.md), [평가기 Unit 3 closeout](docs/stage4/STAGE4_EVALUATION_UNIT3_CLOSEOUT.md), [공개 계수기 Unit 4 closeout](docs/stage4/STAGE4_PUBLIC_COUNTS_UNIT4_CLOSEOUT.md), [후보 수순 근거 Unit 5 closeout](docs/stage4/STAGE4_CANDIDATE_EVIDENCE_UNIT5_CLOSEOUT.md), [rollout 선택 정책 Unit 6 closeout](docs/stage4/STAGE4_ROLLOUT_POLICY_UNIT6_CLOSEOUT.md), [색인 P0 Unit 7 closeout](docs/stage4/STAGE4_INDEXED_P0_UNIT7_CLOSEOUT.md), [정밀 후속 Unit 8 closeout](docs/stage4/STAGE4_EXACT_OBJECTIVE_PILOT_UNIT8_CLOSEOUT.md), [보존 후보 Unit 9 closeout](docs/stage4/STAGE4_EXACT_COMPLETION_UNIT9_CLOSEOUT.md), [독립 계수기 Unit 10 closeout](docs/stage4/STAGE4_STANDALONE_COUNTS_UNIT10_CLOSEOUT.md), [Q/G 합산 연결 Unit 11 closeout](docs/stage4/STAGE4_QG_COUNTER_INTEGRATION_UNIT11_CLOSEOUT.md)을 참고하세요. 작은 목적 선택 사례는 일반 성능이나 최고 기록의 근거가 아닙니다.

## Main/Live Simple·V1·K-P0/K-LC0/K-LC1 — 기존 수용과 거리 관람 추가

2026-11-05 기준 **같은 보드 재플레이·동일 배치 기록·ACK/정리 후 Replay 진입·기본/명시 종료 선택까지 범위 한정 독립 검토 및 최종 사용자 native 수용**을 마쳤습니다. 현재 사용자 환경에서 확인한 범위이며 모든 OS/DPI·preset별 완주·전체 suite·효과성을 뜻하지 않습니다.

2026-11-06 추가한 **거리 기반 관람 모드**와 후속 **고정 6 CPS 성능 보완**은 독립 검토와 이번 PC의 사용자 native 확인을 마쳤습니다. 사용자 확인은 세 속도 방식의 진행·중단과 Replay 두 종료 뒤 설정 보존에 한정하며, 전시 노트북 확인은 별도 대기입니다. 원 본작업의 실행계약 PARTIAL은 [거리 관람 closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_DISTANCE_VIEW_CLOSEOUT.md), 후속 최적화·검토·반영은 [고정 6 CPS 최적화 closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_FIXED6_OPTIMIZATION_CLOSEOUT.md)에서 구분합니다.

새 판은 수동 가능·Auto OFF·추측 허용 OFF입니다. K-P0/K-LC0/K-LC1은 초급·중급·상급에서 새 판과 수동/Simple/V1로 진행한 현재 판을 인수하고, 정상 수동 인계 뒤 재인수할 수 있습니다. 기존 깃발은 공개 정보로 확인·정리하므로 사용자가 모두 해제할 필요는 없습니다. 미확인 깃발은 오답/안전 판정이 아니며 실제 지뢰의 깃발도 해제될 수 있습니다. V1과 K 계열의 사용자 지정 보드는 미지원입니다.

Auto OFF는 일시정지입니다. 모든 정책은 수동 첫 입력에서 Auto와 추측 허용을 끄고 원래 클릭을 처리합니다. 다시 진행하려면 Auto를 켭니다. 별도 **추천·계산 종료** 버튼은 제거했으며 정책 라벨·선택·새 게임 버튼은 같은 줄에 있습니다.

K 확률은 이미 계산된 exact 수치이며, 확정 안전은 초록·HIDDEN 논리 지뢰는 빨강으로 표시합니다. 확률 OFF에도 확정색은 남습니다. 같은 Auto 세션의 다음 계산을 기다리는 동안 유효한 확정색만 유지하고, 열린 칸과 깃발 칸의 색은 즉시 지웁니다. 새 결과가 오면 통째로 교체하며 이전 추천·확률을 다음 입력으로 재사용하지 않습니다. V1/K의 **자동 커서 표시**는 가상 원형입니다. 승인 대기 중 실제 입력보다 먼저 도착할 수 있고 간격 0은 점프합니다. OS 마우스·Model C·인간 Mouse Trace에 합성 경로를 만들지 않습니다.

현재 기능·버전별 검증·실패 이력과 B/C 근거는 [같은 보드/Replay closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_SAME_BOARD_CLOSEOUT.md)에 정리했습니다. [관람 속도/CPS closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_PACING_CLOSEOUT.md)은 이전 수용 checkpoint이며 원 속도 계약은 유지합니다. [LC1 및 표시 개선](docs/stage3-extended/STAGE3_MAIN_LIVE_K_LC1_DISPLAY_CLOSEOUT.md)과 [K 인수/UI](docs/stage3-extended/STAGE3_MAIN_LIVE_K_ADOPTION_UI_CLOSEOUT.md)는 이전 checkpoint입니다. Main의 세 K 정책에서 “(실험적)”을 제거했지만 F02 NOT_VERIFIED·과거 Qt FileDialog 보존 FAIL·effectiveness NOT ESTABLISHED·Production K/Gate P 미승인은 그대로입니다.

### 자동 진행 속도

새 창은 **고정 간격 200 ms / 목표 CPS 5**입니다. 고정 모드에서는 간격과 목표 CPS를 서로 환산하고, Model C와 거리 기반 모드에서는 각 배속을 조절합니다. CPS 6을 입력하면 6을 유지하며 내부 주기는 약 166.667 ms입니다. 화면에 반올림된 값이 실행 주기를 덮어쓰지 않습니다.

고정 속도는 예정 입력 주기를 유지하되 작은 지연만 보정합니다. 200ms에서 일부 간격은180ms까지 짧아질 수 있고, 큰 지연 후에는 새 주기로 시작해 밀린 입력을 몰아 실행하지 않습니다. 계산이 늦으면 목표 CPS에 미달할 수 있습니다. 왼쪽 Counters CPS는 실제 클릭/게임 시간이고 목표 설정과 별도입니다.

**Model C 기반**은 기존 거리별 행동 비용을 배속으로 나눈 관람 지연입니다. 고정 CPS와 다른 방식이며 원 정책·비용 표는 바꾸지 않습니다. 현재 창에서 바꾼 간격·배속은 reset/정책 변경/Replay 왕복 후에도 유지합니다.

**거리 기반**은 이미 정해진 다음 입력까지의 거리에 따라 관람 대기를 조절하는 별도 모드입니다. 배속은 0.05–8배이며 고정값·Model C 배속과 각각 보존됩니다. 1배의 기본 대기는 약 91.7–550 ms이고, 0.05배에서는 관람 대기만 최대 11초입니다. 다음 입력을 고른 뒤 대기하므로 실제 간격에는 계산·통신 시간도 포함됩니다. **배속 2배가 실측 CPS 2배를 보장하지 않습니다.** 기존 정책 선택, Model C 비용, Replay 시계는 바꾸지 않습니다.

V1/K-LC1의 0ms 저부하 [고속 CPS 제한 진단](docs/stage3-extended/STAGE3_MAIN_LIVE_HIGH_CPS_DIAGNOSTIC_CLOSEOUT.md)은 여섯 측정과 원시 자료의 독립 검토를 마쳤습니다. 계산·통신·화면 갱신의 시간을 일부 구분했으며, 일반 처리량 상한이나 단독 병목을 확정한 결과는 아닙니다. 최적화와 원 정책·속도 계약 변경은 수행하지 않았습니다.

후속 [성능·거리 관람 작업](docs/stage3-extended/STAGE3_MAIN_LIVE_DISTANCE_VIEW_CLOSEOUT.md)의 당시 22회 측정에서는 렌더 후보를 사전 기준 미달로 되돌렸습니다. 이후 별도 실전 보드 검증에서 동일 스타일시트 재설정 생략과 worker 응답 알림을 결합한 후보를 독립 수용하고 정확히 반영했습니다. 원본 대비 평균 입력 간격 개선율 중앙값은 12.484226%, 결합본은 약 5.77–5.80 CPS였으며 해당 기계·보드·세션의 결과입니다. 일반 안정 상한·모든 부하·노트북 성능의 보장이 아닙니다. 사용자가 별도로 보고한 목표 10 CPS에서의 약 8–9 CPS도 측정 방식·구간이 미확인인 참고 관측으로 남깁니다.

### 같은 보드 재플레이와 기록

종료한 Live 판에서 정리가 끝나면 **같은 보드 다시 플레이**로 지뢰 배치를 유지한 새 판을 시작합니다. 모든 칸을 닫고 시간·클릭·Replay 기록을 초기화하며 Auto/추측은 OFF입니다. 정책·속도·표시 선호는 유지합니다. 고정 배치에서는 첫 클릭도 지뢰일 수 있고, Auto는 수동 첫 수 없이 추측 허용 설정에 따라 진행합니다.

**재플레이 전 기록**은 첫 Live 재플레이 뒤 활성화됩니다. 같은 전체 배치의 완료판을 보관하고 메뉴나 Replay를 열 때 방금 끝난 판도 중복 없이 포함합니다. 진행 중인 판이나 외부 파일을 완료 Live로 위장하지 않습니다. 새 게임·난이도 변경·다른 배치의 성공한 Replay 진입은 묶음을 비우고, 불러오기 취소·오류와 같은 배치 재플레이는 유지합니다.

Replay에서는 **Replay 종료**가 기본 새 게임입니다. 보고 있던 Replay의 크기·지뢰 수를 유지한 일반 미배치 판으로 초기화하고 기록 묶음을 비웁니다. 별도 **같은 보드 다시 플레이**를 누르면 원 배치의 닫힌 새 판과 기존 같은 배치 기록을 유지합니다. 저장해 둔 파일은 지우지 않으며 이전 Live 진행 상황을 이어가는 기능은 아닙니다.

Auto 중 Replay 요청은 원 입력 확인과 worker 정리가 끝날 때까지 Live에서 기다린 뒤 한 번만 전환합니다. 실패하면 Live에 구체적인 사유가 남습니다. 사용자에게 새 선택을 요구하는 재선택이나 강제 실패 해제는 하지 않습니다. 별도 Same-board Comparison은 기존 기능으로 유지합니다.

## Simple Algorithm

사람에게 보이는 열린 숫자·닫힌 칸·깃발과 공개 총 지뢰 수를 사용해 수를 추천합니다. 실제 숨겨진 지뢰 배치를 정답으로 참조하지 않습니다. 기존 Simple 분석기는 **깃발을 지뢰라고 가정**하며, Main Auto에서는 그 전에 공개 정보로 기존 깃발을 확인·정리합니다.

1. **Local deterministic inference:** 열린 숫자에서 인접 깃발 수를 뺀 값으로 확정 안전/지뢰를 찾습니다.
2. **Exact probability:** local 확정 수가 없을 때 공개 조건을 만족하는 전체 보드 경우의 수로 지뢰 확률을 계산합니다.
3. 확률이 정확히 0 또는 1이면 **certainty**, 그 사이이면 **guess**입니다. Guess에서는 최소 지뢰 확률의 칸을 추천하므로 패배할 수 있습니다.

| UI 항목 | 동작 |
| --- | --- |
| 현재 상태 분석 | 현재 보드를 한 번 분석해 추천만 표시 |
| 분석 표시 | Live에서는 행동 후 분석 갱신. Replay에서는 Simple 참고 분석을 켜고 끔 |
| 확정 수 자동 진행 | Live에서 한 번에 한 행동을 실행하고 새 observation으로 다시 분석 |
| 추측 허용 | 자동 진행이 guess도 실행하도록 허용. OFF이면 추측 직전에 대기 |
| 확률 표시 | 이미 계산된 확률의 표시만 전환. Local 추론만 한 경우 확률을 추가 계산하지 않음 |
| Reduction | 화면의 열린 숫자를 `N − 인접 깃발 수`로 표시. 원본 observation은 유지 |

Live에서 초록은 확정 안전, 빨강은 확정 지뢰, 주황은 최소 위험 후보이며 테두리는 선택된 추천을 뜻합니다. Replay의 테두리는 녹화된 다음 입력입니다. 여러 추천을 queue해서 실행하지 않습니다. 새 게임의 첫 수는 별도 [FIRST_CLICK 정책](ARCHITECTURE.md#first-click)을 따릅니다.

## Replay / Replay Analysis

**Replay**는 보드와 실제 클릭 이벤트를 기록하고 같은 순서로 재생하는 기능입니다.

- `Replay 저장`과 `Replay 다른 이름으로 저장`으로 JSON을 저장하고, `Replay 불러오기`로 다시 열 수 있습니다. 지뢰 배치가 끝났다면 미완료 게임도 저장할 수 있습니다.
- 게임 종료 후 `이번 판 Replay`로 파일 저장 없이 바로 볼 수 있습니다.
- Replay는 기존 JSON의 `source_type`으로 **알고리즘 사용 기록: 있음/없음**을 표시합니다. 첫 실제 Auto 입력부터 기록하며, 알고리즘 이름·현재 참고 분석 정책과는 별개입니다. 옛 파일의 필드 생략은 기존 loader에서 `human`으로 읽으므로 “기록 없음”이 과거 자동 사용의 부재를 증명하지는 않습니다.
- Replay의 Space는 재생/일시정지이며 끝·빈 기록을 자동으로 되감지 않습니다. Return/Enter는 새 게임을 만들지 않습니다. Live에서는 Space/Return/Enter가 새 게임이며 편집 중인 입력 위젯의 키는 보존합니다.
- 처음·이전·다음·마지막 위치와 slider 이동, Index/Time 자동 재생을 지원합니다. Time 모드는 기록된 이벤트 시간을 사용하며 0.25배속부터 8배속까지 조절합니다.
- 완료된 Replay는 현재 위치에 맞는 Counters를 표시하고, 미완료 Replay의 Counters는 마스킹합니다.
- 기본 **Replay 종료**는 보고 있던 Replay의 크기·지뢰 수로 일반 새 게임을 시작하고 기록 묶음을 비웁니다. **같은 보드 다시 플레이**는 원 배치의 고정 새 판과 기존 같은 배치 기록을 유지합니다. 이전 Live position의 재개가 아닙니다.

**Replay Analysis**는 현재 공개 position의 Simple 결과를 참고용으로 보여 줍니다. **녹화된 다음 입력**은 별도 첫 줄과 테두리로 표시하며, 참고 분석 OFF나 분석 오류에도 남습니다. CHORD는 열린 중심 칸, UNFLAG는 해제할 깃발 칸을 가리킵니다. 끝·빈 기록에는 다음 입력이 없다고 표시합니다.

참고 분석 ON에서는 Simple의 확정색·이미 계산한 확률·참고 후보를 별도 줄에 표시합니다. OFF에서는 위치 이동이나 분석 버튼으로 Simple을 호출하지 않습니다. 화면의 “추천과 다름”·“비교 대상 아님” 등 비교 판정 문구는 제거했습니다. 내부 비교 API는 유지하며 분석이 녹화 입력을 바꾸거나 행동을 실행하지 않습니다. 확률·Reduction 표시도 사용할 수 있습니다. 위치 의미와 내부 데이터 계약은 [Replay index](ARCHITECTURE.md#replay-index)와 [비교 규칙](ARCHITECTURE.md#replay-comparison)을 참고하세요.

## ZiNi / 보드 분석

- **3BV/Ops:** opening 그룹과 고립 숫자 칸을 분석해 보드의 정적 지표와 플레이 진행량을 계산합니다.
- **ZiNi:** 실제 mine layout을 사용하는 board metric입니다. 위 Simple Algorithm과 정보 경계 및 목적이 다릅니다.
- deterministic G.ZiNi, maximum-Premium min-ties 탐색, neighborhood beam 및 seeded-chain 탐색을 제공합니다.
- 화면의 ZiNi는 별도 subprocess에서 계산한 **bounded best-so-far**입니다. 전역 최적해나 정확한 최소 클릭 수를 보장하지 않습니다.
- Live에서는 첫 OPEN 또는 FLAG로 지뢰 배치가 확정되면 백그라운드 계산을 시작합니다. 진행 중에는 결과를 숨기고, 종료 시 계산이 끝났다면 즉시 표시합니다. 아직 계산 중이면 `-`를 유지합니다. Replay의 계산 시작은 완료 기록에 한정됩니다.
- **ZiNi Explorer:** 종료된 Live 게임 또는 완료 Replay에서 ZiNi 결과가 준비되면 별도 창으로 최종 계산 경로를 확인합니다. 처음·이전·다음·마지막, slider와 Index 자동 재생을 지원합니다. 헤더에는 누적 Clicks를 표시하고, 좌표·새로 열린 칸/깃발 수·Premium 진단은 기본으로 접힌 **상세 정보**에서 확인합니다. 초기 창 크기는 보드와 화면 공간에 맞추며 큰 사용자 지정 보드나 작은 화면에서는 스크롤을 유지합니다. Trace는 요청 시 사후 구성하며, 실제 게임 행동을 기록한 Replay와 별도 모델입니다.

2026-10-13 **ZiNi improvement CLOSED**: 의미를 보존하는 속도 최적화와 Trace/Explorer를 수용했습니다. 품질 정책은 **V1 유지**, V2 연구는 **종료·미채택**, 최종 holdout은 의도적으로 미개봉 상태입니다. [최종 판정](docs/zini-improvement/ZINI_IMPROVEMENT_FINAL_ADJUDICATION.md)을 참고하세요. Stage-3 Extended의 ACTIVE 경계를 유지하며, 별도 승인된 Stage 4의 공개 정보 계획 기반을 개발 중입니다.

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
10. **분리 상태** — Program K: Logical Known-Mine Capability + Selective Physical Materialization.
    연구 시각화·비교 D0–D5는 **FINAL ACCEPTANCE PASS / CLOSED**이며,
    효과성 연구는 **DEFERRED / unresolved**입니다.

Program K의 bounded experimental 구현, K-C 논리 지뢰 집합 M과 K-P0의 실제
OPEN / FLAG / CHORD 실행은 보존됩니다. Gate-R E0/E1, E2 구현 I1–I8,
R0 harness와 remediation 1A–1W는 수용된 구현 이력입니다.
Fresh R0-A V2 Attempt #2는 integrity PASS이며 static storage blocker를 해소했지만,
실행 시간은 퇴화했습니다. 후속 timing Phase-1 최종 판정은
**PHASE1_INCONCLUSIVE_TRANSFER**입니다. 현재 de-dup remediation-class profiling은
**STOP / DEFER — UNBOUNDED_RESEARCH_RISK**이며 Phase 2는 **NOT AUTHORIZED**입니다.
R0-B와 Actual E2는 **NOT RUN / NOT AUTHORIZED**, 효과성은 **NOT ESTABLISHED**입니다.

별도로 승인된 연구 데모는 이미 저장된 accepted E1 기록을 재생합니다.
K의 논리 지뢰/물리 깃발 구분과 **CONTROL ↔ K-P0 동일 보드 비교**가 구현·수용됐고,
좌우 기록은 독립적으로 탐색·재생됩니다. 최종 소스는
`fb59d5fa253f04f50ea57c6a9e863aa1999a517e`, 최종 Windows onedir 패키지는
`results/program-k-trace-demo-final-acceptance/20261031-230251/dist/ProgramKResearchComparison/`
이며 사용자 packaged A–H acceptance도 **PASS**입니다.
전시 데모 승인과 효과성 입증은 별개입니다. Production K integration은
**NOT STARTED**, Gate P는 **NOT PASSED**이며 V1을 대체하지 않습니다.

저장소 루트에서 source 데모를 열 수 있습니다. 정확한 accepted 로컬 E1 archive와
Model-C profile이 필요하며, 아래 명령은 K를 다시 실행하지 않습니다.

```powershell
python -B -m experiments.program_k_trace_demo
python -B -m experiments.program_k_trace_comparison_demo
```

세부 source/package/data identity와 검증·사용자 승인은
[Program K 연구 데모 closeout](docs/stage3-extended/STAGE3_PROGRAM_K_RESEARCH_DEMO_CLOSEOUT.md)에
기록했습니다. 후속 새 실행 전시는 아래 별도 source 기능입니다.
Extended 전체는 **ACTIVE**이며 전체 종료나 Stage 4 전환을 결정하지 않았습니다.
아래는 **2026-11-05 문서 작성 당시의 snapshot**입니다. 이후 마감과 현재 거리 관람 상태는 [CURRENT_HANDOFF](docs/CURRENT_HANDOFF.md)를 우선합니다.

**2026-11-05 현재 Main K-LC1·표시 개선에 이어 속도/CPS 입력까지 범위 한정 독립 검토·사용자 native 수용을 마쳤고 문서/Git 준비 중입니다.**
작성 기준 main/HEAD=local origin/main=68c272e7272032cdfe9774a36d41c3686a8f375e,0/0,staged0입니다.
이번 source/tests22 + 문서6 =28경로(M14/U14)는 미커밋입니다. 이전 LC1/표시30경로는68c272e에서 완료됐습니다.
NEXT는 사용자 일괄 Git → 실제 receipt/commit 검증 → recovery 교체 → 다음 작업 범위 선정입니다.
[CURRENT_HANDOFF](docs/CURRENT_HANDOFF.md)와 [Extended roadmap](docs/stage3-extended/README.md)을 따르세요.

Timeline Analytics는 **FINAL ACCEPTANCE PASS / CLOSED**입니다.
[최종 closeout](docs/stage3-extended/STAGE3_TIMELINE_ANALYTICS_CLOSEOUT.md)에
수용된 fixed exemplars/report와 후속 연구의 해석 경계를 기록했습니다.

## Random Expert Exhibition V1 — source / 사용자 native 수용

**2026-11-01 사용자 native 재수용 기록.** 공개 `EXPERT_GENERAL_V1` corpus의
index **0..99999**에서 새로 추첨하거나 지정한 Expert 30×16 / 99 보드 하나로
frozen Stage-3 V1과 **actual K-P0(연구용)**를 실행합니다. 같은 layout의 fresh engine
두 개를 사용해 child에서 V1→K 순서로 계산한 뒤 완료 trace를 독립 재생합니다.
새 unseen/holdout 생성기나 production K가 아니며, 위 D5의 preserved-E1 재생과 별도입니다.

승인된 기존 venv/PyQt5와 checkout의 인증 Model C profile을 사용합니다.
일반 Windows native 터미널에서 실행합니다(`QT_QPA_PLATFORM=offscreen` 설정 없음).

```powershell
Set-Location -LiteralPath 'C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m experiments.random_expert_exhibition
```

선택적으로 `--index 97`을 붙이면 창을 연 뒤 해당 index를 한 번 실제 실행합니다.

- 새 추첨 / index 실행 / 계산 취소, 좌우 독립 처음·이전·재생·일시정지·다음·끝·seek.
- **함께 재생 / 함께 일시정지 / 함께 처음으로**: 각 위치·속도를 유지해 명령합니다.
  처음으로는 같은 보드의 두 frame 0으로 돌아가며 모드·속도 설정은 보존합니다.
- slider 트랙 클릭은 클릭 위치로 직접 seek하며 손잡이 드래그·키보드도 지원합니다.
- 기본 **250ms=4 CPS**, preset **200/500ms**, 수동 **20~10000ms / 0.1~50 CPS**.
  ms/CPS는 연동되며 반올림 환산 표시는 `≈`로 구분합니다. Model C 배율 모드도 유지합니다.

논리 M은 빈 다이아몬드, 물리 FLAG는 깃발로 구분합니다. board/M/완료 route/누적 비용은
완료 frame에서만 바뀝니다. 두 index·진행률은 같은 보드 진척을 뜻하지 않습니다.
관람 속도와 synthetic 직선 커서는 실제 인간 시간·mouse trace가 아니며 Model C를 바꾸지 않습니다.
양쪽 WON이 아니면 Model C 승리 시간 차이는 N/A입니다.

**이 외부 전시의 source-only 수용**입니다. 이 수용은 새 package/EXE·Main/Live 통합·효과성 승인이 아닙니다. 현재 Main Simple/V1/K-P0/K-LC0/K-LC1 수용은 위의 최신 Main/Live closeout을 따릅니다.
RF lifecycle/transport 독립 재감사 PASS와 후속 UI의 사용자 수용을 구분합니다.
[전시 기능 closeout](docs/stage3-extended/STAGE3_RANDOM_EXPERT_EXHIBITION_V1_CLOSEOUT.md)에
단계별 검증·실행 identity·한계를, [Human pacing 분석 closeout](docs/stage3-extended/STAGE3_HUMAN_PACING_JSON_V1_CLOSEOUT.md)에
관람 기준의 근거와 해석 한계를 기록했습니다. 커밋 전 snapshot과 현재 Git은 구분해 확인하세요.

## K-LC0 / 새 Expert 비교 — 실험적 source checkpoint

**2026-11-02 사용자 native 수용:** “확인했고 다 괜찮은 것 같아.”
직전 안내한 새 index/추첨·표시 identity/저장, 저장8191의 Model C0.5배·독립/공통
재생·seek, 저장 열기·취소 후 재실행·닫기 범위의 수용입니다. 사용자 실행 횟수나
index/DPI/OS별 receipt를 새로 추정하지 않습니다. 기존 고정3보드 viewer의 당시 정상 동작과
전반적 경로 개선 체감 확인은 별도 역사적 이력입니다. 옛 viewer는 원 LAUNCH_IDENTITY의
316개 파일 raw hash에 묶인 검토 도구입니다. 문서 5개가 달라진 현재 checkout에서는
새 로딩이 인증 실패로 거부되므로 현재 실행용으로 안내하지 않습니다.

계보는 frozen V1 → K-P0 → 실험적 K-LC0이며 V1-LC0는 구현하지 않았습니다.
V1도 CHORD를 사용하며 Stage2 Simple과 구별합니다. K-LC0는 기존 native survivors의
정확21/20 band 안에서 전체 계획 거리 D→E→L→frozen tie로 고르고 첫 입력 후 재계획합니다.
guess·추론·M·Model C는 그대로이며 지역 완료·전체 거리 최소·일반 개선을 보장하지 않습니다.

새 source 앱은 왼쪽 actual K-P0, 오른쪽 active K-LC0를 같은 공개 Expert layout의 두
fresh engine/session에서 전용 child로 순차 실행합니다. 다음 요청 입력값과 현재 표시
identity를 구분하고, 완료 pair를 새 run ID의 JSON으로 저장·재독합니다.
재독에는 solver/보드 재생성/planner 호출이 없습니다. 기본 사용자 기록 root는
`C:\Projects\GraduationProject\K_LC0_RANDOM_EXPERT_COMPARE_RUNS`입니다.

```powershell
Set-Location -LiteralPath 'C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:QT_QPA_PLATFORM='windows'
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m experiments.k_lc0_exhibition
```

시작만으로 계산하지 않으며 `--index 314`도 입력란만 설정합니다. 지정 실행/새 추첨 버튼이
새 실행입니다. `--open '<pair.json 경로>'`는 저장 재생, `--small`은 작은 창입니다.
기존 독립/공통 재생·seek·수동 간격/CPS·Model C 배율과 Windows RF lifecycle을 재사용합니다.
LOST 비용은 승리 시간이 아니며 관람 CPS·합성 커서·Model C·인간 시간은 별개입니다.

원11/97/2026의 혼합 결과와 새5 pair는 별도입니다. 새8191은 입력+2·거리−14.942997칸·
Model C−15,738µs, 나머지 네 보드는 같은2~4입력 조기LOST였습니다.
Claude 검토는 두 구현 모두 PASS / REQUIRED_FIXES 없음입니다. 새 앱 최종 source의
새54 tests는 Claude54/54로 확인됐습니다. Codex TEST_04는 최종 직전 UI였다는 R-1 정정을
[새 비교 앱 closeout](docs/stage3-extended/STAGE3_K_LC0_RANDOM_EXPERT_COMPARE_CLOSEOUT.md)에
기록했습니다. [원 정책·고정 viewer closeout](docs/stage3-extended/STAGE3_K_LC0_DISTANCE_BAND_V1_CLOSEOUT.md)은
정책 경계·검증 이력과 옛 viewer의 snapshot 결속을 설명합니다. 현재 K-P0/K-LC0 비교에는
위 새 앱을 사용합니다. 기존 저장3보드의 CONTROL/K-LC0 trace와 새 앱의 실제 실행/저장
pair는 별도 work unit의 evidence이며 같은 기록으로 취급하지 않습니다.

이 비교 앱 수용 당시 K-P0/K-LC0는 별도 entry였습니다. 현재 Main에는 K-P0/K-LC0/K-LC1이 연결됐습니다. 이 비교 앱 source 수용은
K-LC0 freeze·일반 효과성·production·새 package 승인이 아닙니다.
다음 작업은 사용자 선택이며 영상/정책 개선이 Main 통합의 무조건적인 선행 gate는 아닙니다.

## K-LC1 / SINGLETON_BAND_V1 — 제한된 저장 경로 확인

원 K-LC0를 보존한 별도 실험적 source checkpoint입니다. 2026-11-02 사용자는
8191의 완료145→153 구간에서 O(23,0) 처리 경로가 “좀 더 자연스러워진 것으로 판단됨”,
97은 “정상적임을 확인함. (양쪽에서 차이는 없음)”이라고 확인했습니다.
잔여 지역 선택의 한계를 설명받은 뒤 “그럼 넘어가자.”라고 동의했습니다.
미보고 slider/drag/key/manual rate·모든 native 조작/DPI/OS 수용으로 확대하지 않습니다.

실제 LC0의105% baseline 위에 원 survivor direct-safe OPEN의 productive singleton,
native g 대비105% 밖/110% 이내·엄격한 거리 감소만 허용합니다. K-LC1은 frozen이 아니며
원 K-LC0 교체, 일반 효과성·승률·production 승인이 아닙니다.

아래 별도 저장 경로의 확인 도구는 외부 `K_LC1_USER_PATH_REVIEW_2026-11-02\codex_20261102_01\review_viewer.py`입니다.
8191/97 저장 LC0/LC1 네 trace만 재생합니다. 기존 `experiments.k_lc0_exhibition`은
actual K-P0/K-LC0 앱 그대로이며 LC1 실행은 통합되지 않았습니다.
[K-LC1 closeout](docs/stage3-extended/STAGE3_K_LC1_SINGLETON_BAND_V1_CLOSEOUT.md)에
실행 명령,145→153/97 확인 순서, 복구 pilot·검토·viewer 기록과 알려진 한계를 정리했습니다.
당시 source4·문서6의10경로는 d1201e4에서 commit/push 완료됐습니다. 외부 viewer는 그 commit 대상이 아닙니다.
이후 Main/Live LC1 연결·표시 개선과 속도 입력까지 사용자 수용했으며 현재 상태는 [최신 Main closeout](docs/stage3-extended/STAGE3_MAIN_LIVE_PACING_CLOSEOUT.md)을 따릅니다.

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
- 플레이 중에는 경로 표시가 비활성입니다. 정책 선택·분석·Auto ON만으로는 기록을 잃지 않으며, **실제 Auto 입력이 한 번이라도 실행되면** 그 판의 Human trace 자격을 잃습니다. 이후 수동으로 전환해도 새 판 전까지 복구되지 않습니다. Committed human
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
$env:PYTHONDONTWRITEBYTECODE='1'
$env:GIT_OPTIONAL_LOCKS='0'
$env:QT_QPA_PLATFORM='windows'
& 'C:\venvs\minesweeper\Scripts\python.exe' -B .\main.py
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
├─ stage4_opening.py            # 공개 관측의 exact D/M/Z와 오프닝 질의 근거
├─ stage4_planning.py           # 작은 상태의 비용·공개 분기 계획과 S/M/R 선택
├─ stage4_evaluation.py         # 공개 prefix 재생·매 입력 재계획·미완료/정확 집계
├─ stage4_belief.py             # 한도·취소를 갖춘 공개 D/M/공동 사건 W의 정확 계수
├─ stage4_candidates.py         # 후보 수순의 비용·공동 생존·0 사건·위험 허용 근거
├─ stage4_posterior.py          # 공개 일관 배치의 정확한 정수 rank 표본
├─ stage4_rollout.py            # 가상 환경과 공개 정보만 받는 고정 P0
├─ stage4_policy.py             # S/M/R 선택·fallback·인스턴스 내 원자 입력
├─ live_analysis.py             # Simple/V1/K의 계산된 증거 표시와 Reduction
├─ live_k_policy.py             # K public DTO와 worker-only persistent owner
├─ live_policy_job.py           # Live V1/K owner·검증·ACK·cleanup
├─ live_policy_worker.py        # public-only V1/K worker dispatch
├─ live_policy_transport.py     # v10 strict wire·sequence·payload 경계
├─ live_auto_cursor.py          # 입력과 분리된 가상 원형 커서
├─ live_distance_pacing.py      # 별도 거리 관람 수식·배속·정확한 대기 deadline
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

Engine, 보드 분석, Replay, Simple Algorithm, Live/Replay Analysis와 Auto, ZiNi, Stage-3 실행·재생·Visualizer와 process lifecycle을 검증합니다. Stage 4의 테스트는 공개 정보·작은 상태의 계획·독립 oracle·엔진 대조, Unit 3 평가기의 입력·미완료·집계, Unit 4 계수기의 D/M/W·한도·취소·원자적 확정, Unit 5의 후보 비용·생존·0 사건·미완료 처리, Unit 6의 posterior·가상 전이·선택·continuation을 다룹니다. Unit 6는 A 13개와 B 11개(v01), 추가 B 4개(v02)의 별도 실행이며 v02 28개 일괄 실행이 아닙니다. Unit 7의 고유 PASS 34개도 run02의 5개와 run03의 29개를 합친 별도 실행이며 v02 일괄 34개 실행은 없습니다. Unit 8은 Q 15개와 G 14개의 별도 실행 및 24개 작은 엔진 경로에 한정되며, 큰 base 전체의 독립 재계수는 수행하지 않았습니다. Unit 9의 47개 시험은 보존 후보에 대한 별도 실행이며 후보 신규 시험 파일은 현재 저장소에 없습니다. 구체적인 파일과 검증 범위는 [테스트 전략](ARCHITECTURE.md#test-strategy)을 참고하세요. 일부 UI 테스트는 PyQt5가 없으면 skip되므로 UI까지 검증하려면 위 의존성을 설치해야 합니다.

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

- Simple/Replay 분석은 FLAG를 지뢰로 가정합니다. V1 인수의 별도 FLAG 검토는 제한된 공개 직접 증명만 인정하며, 모든 오답 깃발 탐지나 최대 증명력을 보장하지 않습니다.
- 큰 constraint component의 exact probability는 지수 시간이 걸릴 수 있습니다. Simple Live/Replay 분석은 UI thread에서 동기 실행되어 지연될 수 있습니다. V1 계획/FLAG 검토는 별도 bounded public-only worker입니다.
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
