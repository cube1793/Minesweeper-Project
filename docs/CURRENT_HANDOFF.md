# Current Project Handoff

Updated: **2026-11-05 (Asia/Seoul)** — Main 같은 보드 재플레이·동일 배치 기록·Replay ACK/정리 뒤 진입·기본/명시 종료 선택의 구현, 범위 한정 독립 검토, 최종 사용자 native 수용 완료. 문서/Git 마감 단계.

## 현재 authority와 기능

현재 기능·실패 이력·B/C 근거는 [같은 보드/Replay closeout](stage3-extended/STAGE3_MAIN_LIVE_SAME_BOARD_CLOSEOUT.md)을 따른다. [관람 속도/CPS closeout](stage3-extended/STAGE3_MAIN_LIVE_PACING_CLOSEOUT.md)은 완료 commit **4c10217**까지의 이전 checkpoint이며 원 속도 계약은 유지한다.

- Live WON/LOST와 worker 정리 뒤 같은 배치의 새 판을 시작한다. 새 game_id/세대·시간/입력/Replay/M 초기화, Auto/guess OFF, 정책·속도·표시 선호 유지. V1/K는 세 preset, custom은 기존 Simple/수동 범위다.
- 고정판은 **FIXED_BOARD/wire v10**의 공개 관측 기반 정상 추론을 사용한다. all-HIDDEN이어도 canonical 안전 첫 수가 아니며 guess OFF 대기, ON에서 첫 지뢰면 LOST가 정상이다. 숨은 layout은 GUI의 배치 복원에만 쓰고 정책에 넘기지 않는다.
- 기록은 동일 dimensions/지뢰 수/전체 좌표 묶음이다. 첫 Live 재플레이 뒤 활성화, 현재 완료판은 메뉴/Replay 진입 전 game_id당 한 번 캡처한다. 진행 중/미증명/정리 미확정 판과 imported Replay를 완료 Live로 위장하지 않는다. 원 Replay/source/evidence는 불변이다.
- **기본 Replay 종료**: 보고 있던 Replay의 크기/지뢰 수로 미배치 canonical 새 게임, fixed origin 없음, 기록 묶음/활성화/메뉴 초기화. **명시적 같은 보드 다시 플레이**: Replay의 원 배치로 닫힌 fixed 새 판, 기존 같은 배치 기록 유지. 이전 Live position의 재개가 아니다. 저장 파일은 지우지 않는다.
- 새 게임/난이도 재구성과 다른 배치 Replay의 성공한 진입은 기록을 비운다. 취소/invalid load/같은 배치 왕복은 보존하고 옛 QAction/closure는 무효다.
- Replay 요청은 Auto/guess·입력 예약을 회수하고 Live에서 원 ACK·worker 정리를 기다린다. 정리 뒤 queued commit 1회, 실패 시 Live와 최초 구체 사유 유지. reset/정책/난이도/수동 첫 press/close는 예약을 폐기한다. 보관 불가 완료판이 있으면 구체 사유로 파일 진입도 거부한다.
- Simple/V1/K-P0/K-LC0/K-LC1의 인수/FLAG 준비·수동 인계, 원 session/M/decision identity, VALIDATE→ADMITTED→무yield token→step1→정확 ACK→NEXT는 유지한다. old owner 정리 전 새 owner는 시작하지 않는다.
- 기본 고정200ms/목표5 CPS, FixedPeriod.period_ns·정확 Fraction·QPC/PreciseTimer·bounded fixed-rate를 유지한다. 6 CPS=166,666,667ns, 작은 지연은 위상 유지, 큰 지연은 실제 입력+P, 최소0.9P다. Model C는 원 행동 비용/배속이며 frozen 표를 바꾸지 않는다.
- 확률·확정색·가상 원형/녹화입력·Simple 참고분석/키보드·human trace 경계는 이전 수용대로다. K 라벨에서 실험적 접미사를 뺀 것은 Production 승인이 아니다.

## 검증과 사용자 수용

최종 source333 manifest SHA256: **07feed55cdfd2979c4022efd3c90b5b6fe1a541de175df13f2965ced729676e5**.

- overnight A: 최종 독립119/299, owner14, probe118; B/C는 별도 산술 검토다.
- history flow: 최종 독립33/52, owner2, fixture 실패 수정 후 probe67.
- entry guard: 최종 독립45/86, owner2, probe30. RV2-O1의 실제 진입 실패 경로를 막고 O3/O4를 해소했다.
- **최종 exit choice: 독립49/143, owner2(V1 canonical/K-LC1 fixed), probe28, REQUIRED0/OPTIONAL0.** 입력/Replay/ACK 각1, NEXT0, ACK→정리→commit과 reap/tree0/channel/handle 정리를 확인했다.

버전별 숫자를 합쳐 전체 suite로 쓰지 않는다. 사용자는 source332 기능을 수용한 뒤 기본 종료를 새 판으로 바꾸도록 요구했고, 최종 source333의 두 종료 선택을 안내한 뒤 **“이제 통과야.”**라고 수용했다. 현재 사용자 환경/항목에 한정하며 모든 OS/DPI·부하·전체 suite를 뜻하지 않는다.

## B/C 측정·분석의 남은 한계

**B1 NOT_SATISFIED**: 40행 속도/burst 산술은 원시 QPC에서 재현됐지만 동일 owner·설정별60입력 조건은 미충족이다. 설정별 별도 owner60과 동일 owner12를 혼동하지 않는다. 함수별 시간 NOT_MEASURED, 최적화 NOT_TRIGGERED다. V1 target8→7.914/10→9.183 및 특정 상급0ms 값은 관측일 뿐 일반 상한이 아니다. window peak의 이산 경계 편향도 보존한다.

C는30판/5,035전이/24 player OOF 산술 재현 PASS다. RMSE constant152.440/log129.389/bands128.597ms, log와 bands 차이는0.792ms이며 긴 gap 제외 시 순위가 뒤집힌다. d>16은3표본/비정상 장거리 전이가 있어 해석하지 않는다. action UNKNOWN·직선 target 거리로 판단/운동 시간을 분리할 수 없다. 새 거리 보정식은 제품 미적용, 원 Model C는 불변이다.

과거 overnight helper5/3 위반, history2/2와 probe fixture 실패, entry F01 수정 이력, exit helper2/2를 보존한다. 최종 OPTIONAL0이 과거 유지보수/그래프/측정/harness 권고 전체의 CLOSED를 뜻하지 않는다. **F02 NOT_VERIFIED / 과거 Qt shared FileDialog FAIL / 이전 TEMP NOT_VERIFIED** 유지. 재검증 루프나 전역 TEMP 검색을 열지 않는다.

## Git / 다음 단계

작성 기준 main/HEAD=local origin/main=**4c1021711e53e45a29450da9fa3bebee54e80887**, ahead/behind0/0, staged0. source/tests20 + 문서6의 **26경로(M19/U7)** 미커밋 단위다. 조율 root는 **MAIN_LIVE_SAME_BOARD_DOC_CLOSEOUT_2026-11-05/coordinator_01**이다.

**NEXT: 새 USER_GIT_STEPS_KO.ps1 한 번 → 실제 receipt/parent/26경로/blob/push/clean 확인 → 새 commit에 결속한 recovery2개 → 사용자 Desktop 교체/hash 확인.** 이전 Git 스크립트는 재실행하지 않는다. 완료 SHA는 후속 실제 receipt/recovery/live Git을 따르고 postcommit 문구만의 추가 문서 commit은 만들지 않는다.

그 뒤 B1 보완 필요성 판단, 필요 시 함수 단위 병목 측정, frozen Model C와 분리된 거리 기반 관람 프로필 설계를 별도 범위로 정한다. B/C·성능·프로필 구현을 여기서 자동 시작하지 않는다. Codex 기본 속도는 사용자의 최신 선택인 **Standard**다. Claude는 Opus5.5/Max/Auto/Fast OFF, 실제 미노출 설정은 미확인으로 기록한다.

## 역할과 영구 경계

구현은 별도 Codex, 독립 검토는 Claude Code, 현재 채팅은 조율·문서·Git/recovery 인계다. coordinator는 제품 source/tests·프로젝트 Python/Qt/worker·실제 Git 쓰기·Desktop 교체를 수행하지 않는다. 긴 프롬프트는 전문 복사/스크롤, 큰 단위 후 문서와 사용자 Git 일괄 절차를 유지한다.

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE. Phase2/R0-B/ActualE2 미승인/미실행. frozen 정책·Model C·holdout **2,010,000..2,010,099**·금지 연구 formal evidence 경계를 지킨다. Main source 수용은 새 package/Stage4/연구 자동 승인과 다르다.
