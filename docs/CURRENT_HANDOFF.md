# Current Project Handoff

Updated: **2026-11-05 (Asia/Seoul)** — 같은 보드/Replay 기능은 cd8ee2e에서 마감됐다. 후속 고속 CPS 제한 진단은 여섯 측정·산술 및 묶음 독립 검토 수용을 마쳤고 문서6경로의 Git 마감을 준비한다. 제품 source/tests 변경은 없다.

## 현재 authority와 기능

현재 기능·실패 이력·B/C 근거는 [같은 보드/Replay closeout](stage3-extended/STAGE3_MAIN_LIVE_SAME_BOARD_CLOSEOUT.md)을 따른다. [관람 속도/CPS closeout](stage3-extended/STAGE3_MAIN_LIVE_PACING_CLOSEOUT.md)은 완료 commit **4c10217**까지의 이전 checkpoint이며 원 속도 계약은 유지한다.

현재 후속 성능 근거는 [고속 CPS 제한 진단 closeout](stage3-extended/STAGE3_MAIN_LIVE_HIGH_CPS_DIAGNOSTIC_CLOSEOUT.md)이다. 실제 실행 HEAD는 **cd8ee2ef23a2753f858f8945d7a9bff1580369fb/source333**이며 이후 문서 commit을 그 실행 HEAD로 소급하지 않는다.

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

## 고속 CPS 제한 진단 — 묶음 독립 수용

**COMPLETE_BOUNDED_DIAGNOSTIC / 독립 수용**, 필수 증거 수정0·제품 결함0이다. V1/K-LC1, 기존 30×16/99 합성 공개 저부하 fixture, fixed0ms의 MIN1/TRACE/MIN2 여섯 run이다. 각 actual/Replay/ACK62/62/62, 총 Auto372, steady60/59gap이다.

- RESUME 약44.060분, Python10/12, owner7/8, C보정2/2. C01은 actual0의 bootstrap 실패 뒤 한 번 대체했고 성공6개 timed signature가 같다. C02는 마감 PowerShell 집계 보정으로 새 Python/owner0이다. P01의 실제 startup 순서 검증 공백과 이전 Unit1 PARTIAL/4·상한2/당시 NOT_VERIFIED는 보존한다.
- V1 drift0.678704%/관측 TRACE 변화+1.938511%, LC1 drift1.759086%/+0.740295%. 잠정5%는 사용자·제품 수용치가 아니며 순차 관측의 drift와 인과 overhead를 완전히 분리하지 못한다.
- 부모 anchor만 gap을 비중첩 분할한다. 성공 read_next 약6.5–7ms와 render_board 약22ms는 중첩된 후속 후보이며 순수 IPC/poll·단독 원인·자연 판 상한은 미확정이다. MIN은 공통 seam을 포함한 하네스 기준이다. native paint/실제 표시 지연은 미측정이며 최적화는 **NOT_PERFORMED**다.
- Claude 약27.915분, 새 제품 Python/Qt/worker/owner0, 도구 오류2/2. CROSSCHECK205=정확201+참고2+문자열 주석 문제2, review manifest는 자기 제외16/포함17파일이다. E1 setup timerType1·E2 UI 구간 잘라냄·M3 하네스 기준 문구를 closeout에 명확히 했고 M1/M2 helper 유지보수는 선택 권고로 남긴다. 원 evidence는 수정하지 않았다.
- 조율은 기존 TRACE만으로 poll 구간을 추가 재구성했다. parent 진입 간격 median30.3407/30.83585ms, worker 부재 read 반환→다음 read mean10.194602/10.235673ms다. 새 실행0이고 순수 timer/scheduler 비용으로 귀속하지 않으며 이 보충 자체를 Claude 독립 수용으로 부르지 않는다.

## 기존 B/C 측정·분석의 남은 한계

**B1 NOT_SATISFIED**: 기존40행 속도/burst 산술은 재현됐지만 동일 owner·설정별60입력 조건은 미충족이다. 설정별 별도 owner60과 동일 owner12를 혼동하지 않는다. 당시 함수별 NOT_MEASURED/최적화 NOT_TRIGGERED를 후속 진단으로 소급 변경하지 않는다. B1은 이번 진단의 선행 조건이 아니며 OUT_OF_SCOPE다. V1 target8→7.914/10→9.183 및 특정 상급0ms 값은 관측일 뿐 일반 상한이 아니다. window peak의 이산 경계 편향도 보존한다.

C는30판/5,035전이/24 player OOF 산술 재현 PASS다. RMSE constant152.440/log129.389/bands128.597ms, log와 bands 차이는0.792ms이며 긴 gap 제외 시 순위가 뒤집힌다. d>16은3표본/비정상 장거리 전이가 있어 해석하지 않는다. action UNKNOWN·직선 target 거리로 판단/운동 시간을 분리할 수 없다. 새 거리 보정식은 제품 미적용, 원 Model C는 불변이다.

과거 overnight helper5/3 위반, history2/2와 probe fixture 실패, entry F01 수정 이력, exit helper2/2를 보존한다. 최종 OPTIONAL0이 과거 유지보수/그래프/측정/harness 권고 전체의 CLOSED를 뜻하지 않는다. **F02 NOT_VERIFIED / 과거 Qt shared FileDialog FAIL / 이전 TEMP NOT_VERIFIED** 유지. 재검증 루프나 전역 TEMP 검색을 열지 않는다.

## Git / 다음 단계

작성 출발 main/HEAD=local origin/main=**cd8ee2ef23a2753f858f8945d7a9bff1580369fb**, ahead/behind0/0, staged0, index e7825f54f9a94d806e50d86bbf6186fedf2672286b924eff5f01f505113ed4ba. source/tests 변경0에 이번 **문서6경로(M5/U1)**만 묶는다. 조율 root는 **MAIN_LIVE_HIGH_CPS_REVIEW_CLOSEOUT_2026-11-05/coordinator_01**이다. 이전 같은 보드26경로 commit/push·Desktop 교체는 이미 완료됐다.

**NEXT: 이번 새 USER_GIT_STEPS_KO.ps1 한 번 → 실제 receipt/parent/문서6경로/blob/push/clean 확인 → 실제 새 authority에 결속한 recovery2개 → 사용자 Desktop 교체/hash 확인.** coordinator는 Git 쓰기와 Desktop 교체를 실행하지 않는다. 완료 SHA는 실제 receipt/recovery/live Git을 따르며 postcommit 문구만의 추가 commit은 만들지 않는다.

그 뒤 우선 후보는 성공 read_next의 외부 세부 구간 또는 render_board 내부의 작은 분해다. 원시 poll 구간 보충도 함께 사용하되 원인 확인 전 최적화를 시작하지 않는다. 새 측정/프로필/연구를 자동 승인하지 않는다. 새 성능 측정 범위는 새 Codex 채팅/GPT-6 Astra/Max/**Standard**를 기본으로 하며 Ultrafast OFF다. Claude는 큰 단위 뒤 새 세션/Opus5.5/Max/Auto/Fast OFF, 같은 범위 보충은 기존 세션을 사용할 수 있고 실제 미노출 설정은 UNCONFIRMED로 기록한다.

## 역할과 영구 경계

구현·실제 측정은 별도 Codex, 독립 검토는 Claude Code, 현재 채팅은 조율·문서·Git/recovery 인계다. 작은 환경/helper 수정은 정해진 범위·복구 예산 안에서 Codex가 이어가고 결과가 모이거나 큰 단위가 끝나면 Claude에 묶어서 넘긴다. coordinator는 제품 source/tests·프로젝트 Python/Qt/worker·실제 Git 쓰기·Desktop 교체를 수행하지 않는다. 긴 프롬프트는 높이 제한 스크롤·전문 복사·TXT로 제공하고 큰 단위 후 문서와 사용자 Git을 일괄 마감한다.

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE. Phase2/R0-B/ActualE2 미승인/미실행. frozen 정책·Model C·holdout **2,010,000..2,010,099**·금지 연구 formal evidence 경계를 지킨다. Main source 수용은 새 package/Stage4/연구 자동 승인과 다르다.
