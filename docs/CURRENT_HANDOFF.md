# Current Project Handoff

Updated: **2026-11-04 (Asia/Seoul)** — K 현재 판 인수·기존 FLAG 준비·ACK 수동 인계·Simple 준비·Replay UI/단축키 보완의 범위 한정 독립 검토와 사용자 native 수용 완료. 문서 마감·사용자 Git 준비 상태다.

## 현재 계약과 수용

현재 authority는 [K 인수·Simple 준비·Replay UI closeout](stage3-extended/STAGE3_MAIN_LIVE_K_ADOPTION_UI_CLOSEOUT.md)이다. [이전 K v3–v5](stage3-extended/STAGE3_MAIN_LIVE_K_P0_CLOSEOUT.md)와 [Simple/V1](stage3-extended/STAGE3_MAIN_LIVE_SIMPLE_V1_CLOSEOUT.md)은 역사다. 최신 사용자 확인은 “드디어! 전부 통과야.”이며 마지막 native 안내 5항목과 이전 주요 기능 수용에 결속한다. 모든 옛 체크리스트의 최종 bytes 재실행·preset별 완주·모든 OS/DPI·전체 suite를 추정하지 않는다.

K는 세 preset에서 새 판과 수동/Simple/V1 현재 판을 인수·재인수한다. 기존 FLAG를 사용자가 모두 해제할 필요는 없다. native session의 공개 FLAG-masked local proof로 확인된 지뢰만 유지하고 나머지를 실제 해제한 뒤 같은 session으로 진행한다. 미확인은 오답/안전 판정이 아니며 실제 지뢰도 해제될 수 있다. 공통 wire v7, K_P0_PUBLIC_FLAG_ADOPT_LOCAL_BOOTSTRAP_V1, 원 M/decision graph, VALIDATE→ADMITTED→무yield 최종 비교/token/step1→원 입력 ACK 경계를 유지한다.

ACK 중 수동 입력은 정상 인계로 처리하며 원 K 입력 receipt만 확인한 후 옛 owner를 정리한다. 현재 수동 판을 덮어쓰거나 NEXT를 보내지 않는다. 진짜 이력/ACK/정리 실패는 최초 원인 fail-closed로 잠근다. Simple/V1/K 모두 수동 클릭 시 Auto와 guess OFF이며 재개는 명시 Auto ON이다. Auto OFF만으로는 일시정지한다. 추천·계산 종료 버튼은 제거했다.

Simple 준비는 직접 공개 증명으로 기존 FLAG를 확인한다. planner/Model C는 그대로다. 표 밖 이동은 null/OUTSIDE_FROZEN_TABLE과 unmodeled count로 남기며 0비용·완전 합계로 취급하지 않는다. 원 확률/확정색/V1·K 가상 원형은 표시 전용이다.

정책 줄 간격, Replay의 기존 source_type 기반 알고리즘 사용 기록과 키 동작을 수용했다. Live Space/Return/Enter 새 게임, Replay Space 재생/일시정지, Replay Enter/reset 무동작이다. 비편집 정책 콤보 focus를 보존하면서 키가 동작하고 편집 입력은 유지한다. 종료 정리 실패는 잠금을 유지한 채 이유와 비활성 제어로 알린다. **K-P0 (실험적)** 표시와 Main LC0/LC1 disabled, V1/K custom 미지원은 유지한다.

## 최종 검증과 이력

- 현재 source107 manifest SHA256: **848cbdc1423479fa2f65b2da5c915b033b5af075b111bef78007c3cd2077e5b2**. 최종 Codex R02 345 method/479 subtest, 독립 review_claude_02 345/479와 probe4/4, worker0. R1/O1/O2/O3 CLOSED; O3는 offscreen fake 예외 한정이다. 옛 340/476 PASS에서 놓친 R1은 옛 bytes의 실패로 보존한다.
- 앞선 버전별 선택 검사: FLAG-free353/481+실제5사례6owner, FLAG Unit2 413/677+6사례7owner, Native Feedback443/731+6사례7owner. 각각의 Codex/Claude 실행과 원장/정리 근거다. 이를 합산하거나 최종 bytes의 새 worker 실행으로 표현하지 않는다.
- 독립 실행 중단/보충, fixture·helper·probe 실패와 정정, 전역 TEMP/scratch 등 절차 이탈은 원 evidence에 보존한다. 기술 적합성은 모든 절차 무결점 판정이 아니다.
- 마지막 S1/S2와 이전 낮은 우선순위 OPTIONAL은 보류한다. Simple의 유한 재FLAG, terminal 기록/문구·guess 초기화·긴 이력 성능 등 알려진 한계는 새 closeout을 따른다. 이번에 새 수정 루프를 열지 않는다.
- **F02 NOT_VERIFIED / 과거 Qt FileDialog FAIL / 과거 중단 focused temp 정리 NOT_VERIFIED** 유지. 옛 runner 복구·재검증을 재개하지 않으며 제한 registry/private INI를 사용자 전체 설정 보존으로 확대하지 않는다.

## Git / NEXT

문서 작성 기준 **main / HEAD = local origin/main = a9928921e873f11c72283d35a6d0d9847eacd8e3 / ahead·behind 0·0 / staged 0**. 수용된 미커밋 source/tests24(M15/U9)와 문서8(기존7·신규1), 합계 **32경로(M22/U10)**다. a992892까지는 이전 Git/recovery 완료본이고 이번 32경로의 push는 아직 아니다. raw 실행 bytes와 정규화 Git blob을 구분한다.

현재 산출물은 MAIN_LIVE_K_ADOPTION_UI_DOC_CLOSEOUT_2026-11-04/coordinator_01이다. **NEXT: 정확한 plan의 사용자 일괄 stage·commit·push → 실제 receipt/SHA 확인 → postcommit recovery 두 파일 교체본 → 사용자 Desktop 교체 → Main/Live LC0 다음 LC1 연결 단위 확정.** 이 문서의 precommit snapshot 대신 완료 후 실제 receipt/recovery를 Git authority로 삼으며 같은 내용을 위해 추가 문서 commit을 만들지 않는다. 옛 사용자 Git helper를 다시 실행하지 않는다. 이 마감에서는 LC 구현/추가 독립 실행 검토를 시작하지 않는다.

## 영구 경계

D0–D5 CLOSED / FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인, V1 CLOSED/FROZEN, Extended ACTIVE. Phase2와 R0-B/ActualE2 미승인/미실행. frozen 정책·Model C·holdout 2,010,000..2,010,099·공식/formal evidence를 유지한다. 별도 K-LC0 실제 비교 앱과 LC1의 저장 trace4개 viewer 수용을 Main 연결·새 package·Stage4 승인으로 확대하지 않는다.
