# Current Project Handoff

Updated: **2026-11-03 (Asia/Seoul)** — Main/Live K-P0 첫 연결·추측 확률·V1/K 원형 커서의 현재 범위 사용자 수용, 문서 마감·사용자 Git 준비(precommit).

## 현재 상태와 수용

Main의 Simple/frozen V1·수동↔V1 인수·공개 FLAG 검토는 `98203e809581f969685addeed45d7ebc7ff4c528`에서 commit/push 완료됐다. [이전 closeout](stage3-extended/STAGE3_MAIN_LIVE_SIMPLE_V1_CLOSEOUT.md)은 당시 버전의 역사로 보존한다.

현재 **K-P0 (실험적)** 세 preset 명시 새 게임 연결과 K 추측 확률·V1/K 가상 원형 커서까지 구현됐다. Unit1과 UI 증분 각각 독립 REQUIRED_FIXES0이며, 사용자는 현재 동작이 괜찮다는 의견을 주고 같은 판 K 인수·확정색 표시를 후속으로 둔 뒤 마감을 진행하도록 동의했다. [K closeout](stage3-extended/STAGE3_MAIN_LIVE_K_P0_CLOSEOUT.md)이 현재 계약·bytes·수용·한계의 상세 기록이다. native6항목 전체·모든 preset 완주·DPI 실행 결과는 추정하지 않는다.

새 판은 수동 가능·Auto OFF·guess OFF, 정책 선택만으로 실행하지 않는다. K Auto OFF는 같은 owner/pending 보관 일시정지다. 수동 first press/추천·계산 종료/정책 변경 뒤 같은 판 K 재인수, 수동/Simple/V1 진행 판의 K 신규 인수는 미지원이다. 기존 V1 cleanup 뒤 ADOPT와 Simple 혼합 입력은 유지한다. K는 별도 persistent M/session과 VALIDATE→ADMITTED→최종 비교/token→실제 입력1→ACK→NEXT를 사용한다.

K 확률은 기존 EXACT_GUESS 정수 표시이며 확정 안전/지뢰 초록·빨강 overlay는 아직 없다. V1/K 원형은 기존 관람 간격의 가상 커서로 OS 마우스·논리 cursor·Model C·인간 trace/Replay를 바꾸지 않는다. K 승인 대기 중 먼저 target에 도착할 수 있다. 현재 wire v4, LC0/LC1 selector 실행은 disabled다.

## 현재 Git과 NEXT

**main / HEAD == local origin/main == `98203e809581f969685addeed45d7ebc7ff4c528` / ahead·behind0·0 / staged0.** 이번 새 **source/tests18 + 문서6 = 미커밋24경로(M13/U11)**이며 새 commit/push 완료가 아니다. runtime raw89는 UI manifest `142d897fdb531f86dc44b64ab715e9418cb4fcb81db11aa0648ec0ccc4610feb`에 결속한다. raw 실행 identity와 예상 Git blob을 구분한다.

K-LC0의20경로496fab0, K-LC1의10경로d1201e4, 이전 Simple/V1의24경로98203e8은 완료된 역사다. 옛 precommit/NEXT/script를 반복하지 않는다. 새 commit으로 과거 K/v3·A–F run identity를 대체하지 않는다. 로컬 origin 확인은 fetch/서버 ref 조회가 아니다.

**NEXT: 이번 문서/정확한 새24경로 plan 확인 → 사용자 일괄 stage·commit·push → receipt·실제 SHA 확인 → postcommit recovery 교체 사본 준비.** 후속은 K 확정색, 같은 판 K 인수·재인수, LC0/LC1 Main 연결로 별도 범위를 정한다. 지금 후속 source/worker/연구를 자동 시작하지 않는다.

## 근거와 한계

- Unit1 Codex428+새 worker7의435는 합성이다. Claude 독립428/subtest857+K01–K07 각1회, 각각 owner7/fixture자손1. 당시 wire v3 오류 근거를 v4 전체 재실행으로 쓰지 않는다.
- 현재 UI Codex430(R04 398+R05 9+R06 23)+worker2는 합성432다. 현재 Claude focused430/subtest785 1회+worker2 1회, owner2/fixture자손0과 DTO/UI/정적 probe를 별도로 수행했다. 전체 suite·실제 Main UI+worker 동시 smoke는 없다.
- source/출력·Git/index는 독립 시작/종료 동일했다. 사용자 범위 수용을 세부 native/DPI/모든 gesture·package/효과성 PASS로 확대하지 않는다. Unit1/최신 UI OPTIONAL은 보류한다.
- Unit1 오류, UI fixture 중단2회(access violation 포함), close 잔상·mock 오류 수정, 각 helper 이력은 보존한다. **Codex 중단 focused 미기록 temp 정리 NOT_VERIFIED**를 유지한다.
- UI Claude python3 Store alias2회·미등록 승인 Python one-liner2회는 절차 이탈이다. reviewer의 project import/쓰기/policy owner0 보고를 interpreter 호출0으로 바꾸지 않는다. 절차 전체 준수 PASS는 아니다.
- UI Claude 보고서 종료 추정19:15/33분은 실제 전달19:12/약30분, temp13개는 manifest 포함14개로 정정한다. 원본 hash는 보존하며 조율 기록과 K closeout에 정정을 남긴다.
- **독립 F02 NOT_VERIFIED**, 과거 shared Qt FileDialog **FAIL**, offscreen glyph 한계와 E helper R1 전 재사용 금지는 유지한다. private INI/제한 registry 결과로 과거 판정을 닫지 않으며 재검증 루프를 재개하지 않는다.

## Main과 별도 전시/저장 viewer

`main.py`는 Live 판에 실제 입력한다. 승인 Python은 `C:\venvs\minesweeper\Scripts\python.exe -B`, native Qt는 `windows`다. 별도 `experiments.k_lc0_exhibition`은 actual K-P0/K-LC0 비교 앱이며 [K-LC1 저장 viewer](stage3-extended/STAGE3_K_LC1_SINGLETON_BAND_V1_CLOSEOUT.md)는8191/97 네 저장 trace만 읽는다. Main에는 K-P0만 추가 연결됐고 LC0/LC1·새 package는 미연결/미수용이다.

## 문서 마감·recovery와 영구 경계

이번 output: `C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\MAIN_LIVE_K_P0_DOC_CLOSEOUT_2026-11-03\coordinator_01`. before/after·검수·보호 receipt, COMMIT_PLAN, 사용자 일괄 Git script를 제공한다. coordinator는 source/tests·Git/index·Desktop·과거 evidence를 수정하지 않고 문서6개만 갱신한다. 사용자 Git 뒤 receipt·실제 SHA의 recovery2개 사본을 준비하고 사용자가 Desktop을 교체한다.

D0–D5 FINAL ACCEPTANCE PASS/CLOSED, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인, V1 CLOSED/FROZEN, Extended ACTIVE. Phase2·R0-B/ActualE2 미승인/미실행. frozen 정책·Model C·holdout2,010,000..2,010,099·공식/formal evidence 경계를 유지한다. 이 마감은 새 실험·정책·Production·Stage4 실행 권한이 아니다.
