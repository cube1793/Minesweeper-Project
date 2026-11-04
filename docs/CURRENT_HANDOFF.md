# Current Project Handoff

Updated: **2026-11-04 (Asia/Seoul)** — Main/Live K-LC1 및 Replay/확정색 표시 개선의 구현·범위 한정 독립 검토·사용자 native 수용 완료. 문서 마감 및 사용자 일괄 Git 준비.

## 현재 기능과 수용

현재 authority는 [LC1 및 표시 개선 closeout](stage3-extended/STAGE3_MAIN_LIVE_K_LC1_DISPLAY_CLOSEOUT.md)이다. [LC0 closeout](stage3-extended/STAGE3_MAIN_LIVE_K_LC0_CLOSEOUT.md)은 4f34a96까지, [K 인수/UI closeout](stage3-extended/STAGE3_MAIN_LIVE_K_ADOPTION_UI_CLOSEOUT.md)은 7f15355까지의 이전 checkpoint다. 사용자는 LC1 주요 기능을 확인한 뒤 제안한 Replay/확정색 개선까지 **“이제 다 괜찮은 것 같아.”**라고 수용했다. 현재 사용자 환경·안내 범위이며 모든 OS/DPI·preset 완주·전체 suite를 의미하지 않는다.

Simple/V1/K-P0/K-LC0/K-LC1을 선택할 수 있다. K 계열은 세 preset의 새 판, FLAG-free 현재 판, 기존 FLAG 준비 후 인수, 정상 수동 인계 후 재인수를 지원한다. 실제 오류만 fail-closed하며, 정상 ACK 중 수동 인계는 원 receipt 확인만 하고 현재 판을 덮어쓰거나 NEXT를 보내지 않는다. 옛 owner 정리 뒤 명시 Auto ON으로 재인수한다. V1/K 계열 custom 보드는 미지원이다.

LC1은 원 native 선택과 SINGLETON_BAND_V1을 사용한다. 실제 LC0 baseline b를 구한 뒤 원 survivor의 singleton direct-safe OPEN에만 105% 초과·110% 이하와 더 짧은 D 조건을 적용한다. native g/LC0 b/LC1 final identity와 물리 검증에 결속하고 첫 입력1회만 실행한다. 일반 효과성·전체 게임 비용 상한을 주장하지 않는다.

공통 wire는 v9다. 지속 session/M, 시작 revision·이력, VALIDATE→ADMITTED→무yield token/step1→정확 ACK 경계를 유지한다. Simple/V1/K 모두 수동 첫 press에 Auto/guess OFF, Auto OFF만으로는 pause다. 기존 FLAG를 모두 수동 해제할 필요는 없다. 미확인 FLAG 해제는 오답/안전 판정이 아니며 실제 지뢰의 깃발도 포함될 수 있다.

Replay는 녹화된 다음 입력의 첫 줄·테두리를 Simple 참고 후보와 분리한다. 참고 분석 OFF/오류에도 녹화 입력이 보이고, 일반 UI의 비교 판정 문구는 제거됐다. 내부 비교 API와 저장 형식은 불변이다. 알고리즘 사용 기록은 기존 source_type으로 표시하고 정책 이름 이력을 새로 만들지 않는다. Replay Space는 재생/일시정지, Return/Enter는 새 게임을 만들지 않는다.

Auto 입력 뒤 다음 계산을 기다리는 동안 같은 유효 context의 HIDDEN 확정색만 유지한다. 열린/FLAG 칸, 이전 추천·확률은 제외하고 새 결과로 교체한다. 수동 첫 press·정책·reset·Replay·종료·분석 OFF·오류·owner 폐기에서 지운다. 표시 frame은 추론/승인/실제 입력에 쓰지 않는다. V1/K 원형은 OS 경로와 분리된 가상 커서다.

마우스 경로는 기록을 켠 수동 판 종료 후에 표시할 수 있다. 실제 Auto 입력1회가 있으면 그 판의 Human trace는 무효다. 단순 정책 선택·분석·Auto ON만으로는 실제 Auto 입력으로 보지 않는다. K-P0/K-LC0/K-LC1의 **(실험적)** 표시는 유지한다. 삭제·새 package·추가 연구는 이번 문서 작업에 포함하지 않는다.

## 검증과 알려진 한계

- 최신 source314 manifest SHA256: **61d96678759c04f38f4931cc0bd5b465a10953b2b6c78f82c03d99691138bb3d**.
- LC1 독립 검토: 당시 source310에서 **625 methods / 905 subtests**, 실제 **6사례 / 8 owner / Auto10**, probe24 PASS. Codex의 622+3 합성을 단일 실행으로 확인했다.
- 표시 증분 독립 검토: source314에서 **263 methods / 355 subtests**, 실제 **2사례 / 2 owner / Auto4**, probe9 PASS. source310 대비 5수정+4신규이고 핵심 실행/ACK 등 54메서드는 불변이다. 서로 다른 snapshot/선택 범위의 수치를 전체 suite로 합산하지 않는다.
- 두 검토 모두 REQUIRED_FIXES0. 합성 공개 상태·offscreen·작은 실제 worker 사례이며 자연 초기 flood의 모든 선택, 모든 preset 완주·DPI/OS·성능 우월성을 보장하지 않는다. 사용자 native 수용은 후속 확인으로 별도 기록한다.
- 표시 O1: Replay tooltip의 Live 범례 “테두리: 실제 추천” 잔여. O2: Auto 입력 직후 pause의 “다음 수 계산 중” 잔여. O3: object id의 이론적 재사용은 run/generation으로 보완됨. 필수 수정은 아니며 이번에는 제품을 수정하지 않았다. 이전 OPTIONAL·실패 이력도 보존한다.
- 검토 kit H1의 EXECUTION_LEDGER 사전 생성은 실행 실패 전 데이터 초기화이며 복구로 세지 않는다. 검토 복구0/1. 후속 템플릿은 별도 보완했다. PS5.1 typed/ordinal ID 비교 수정·9조건 QA와 구현자의 승인된 추가 QA 이력도 보존한다.
- 과거 F02 NOT_VERIFIED, Qt shared FileDialog FAIL, 과거 중단 TEMP 및 LC0 검토의 전역 TMPDIR 잔여물 NOT_VERIFIED는 유지한다. 현재 private cleanup·제한된 registry/INI·native 수용으로 덮지 않는다. 전역 TEMP 검색/삭제나 과거 재검증 루프를 열지 않는다.

## Git / NEXT

문서 작성 기준 **main / HEAD = local origin/main = 4f34a9690fd913f8702404a3c1c6122c078bd4d0 / ahead·behind0·0 / staged0**. LC1+표시 source/tests22(M14/U8)에 문서8(기존7·신규1)을 더한 **30경로(M21/U9)** 미커밋 단위다. 이전 LC0의 29경로 commit/push·recovery는 완료됐다. 원 실행 raw와 정규화 Git blob을 구분한다.

조율 root: MAIN_LIVE_K_LC1_DISPLAY_DOC_CLOSEOUT_2026-11-04/coordinator_01. **NEXT: 사용자 단일 script로 정확한30경로 stage/commit/push → 실제 receipt·commit 검증 → postcommit recovery 두 사본 → 사용자 Desktop 교체 → 다음 작업 범위 선정.** 완료 SHA는 실제 receipt/recovery/live Git을 따른다. postcommit 문구만을 위한 추가 문서 commit은 만들지 않는다. 이 단위는 제품 재수정·추가 독립 실행 검증을 요구하지 않는다.

## 영구 경계

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE. Phase2/R0-B/ActualE2 미승인/미실행. frozen 정책·Model C·holdout 2,010,000..2,010,099·공식/formal evidence 경계를 유지한다. Main 연결 수용은 새 package/Stage4/연구 자동 시작 권한이 아니다.
