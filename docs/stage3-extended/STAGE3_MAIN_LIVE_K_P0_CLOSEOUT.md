# Main/Live K-P0 first connection and probability/cursor closeout

Updated: **2026-11-03 (Asia/Seoul)**. Status: **현재 범위 구현·독립 검토·사용자 수용 완료 / 문서 마감 / 사용자 commit·push PENDING**.

Main의 실험적 K-P0 첫 연결과 K 추측 확률·V1/K 가상 원형 커서 보완을 마감한다. 사용자는 현재 동작이 괜찮다는 의견을 주고, 같은 판 K 인수와 확정 칸 색상이 후속임을 확인한 뒤 “좋아, 계속 가자.”라고 마감에 동의했다. 항목별 native 실행 수·모든 preset 완주·모든 gesture·DPI 수용은 추정하지 않는다. [이전 Simple/V1 closeout](STAGE3_MAIN_LIVE_SIMPLE_V1_CLOSEOUT.md)은 당시 버전의 역사로 보존한다.

## 현재 기능과 사용

- **K-P0 (실험적)**를 선택하고 **선택 정책으로 새 게임**을 누른다. 초급·중급·상급 세 preset의 명시 새 게임만 지원하며 custom은 미지원이다. 새 판은 수동 가능·Auto OFF·guess OFF, 정책 선택만으로 실행하지 않는다. 분석-only는 실제 입력하지 않는다.
- K Auto OFF는 같은 owner와 유효 pending 보관 일시정지다. 수동 입력 없이 재개할 수 있다. 수동 첫 press·추천/계산 종료·정책 전환 등으로 owner를 종료한 뒤 같은 판 K 재진입은 미지원이다. 수동/Simple/V1로 진행한 판의 K 신규 인수도 후속이다. 기존 V1의 cleanup 뒤 ADOPT와 Simple 혼합 입력은 유지한다.
- K 추측 대기에서 **지뢰 확률**과 기존 **확률 표시**를 사용한다. 원 K 결정의 exact 정수를 표시하며 추가 추론·선택을 하지 않는다. 작은 양수·거의100%를 확정0%/100%로 오표시하지 않는다.
- K는 현재 다음 한 수 추천과 추측 확률만 표시한다. **확정 안전/지뢰 초록·빨강 overlay는 미연결**이다. K의 추론 능력 부재를 뜻하지 않으며, 이미 확정한 정보의 표시 투영은 후속 UI 작업이다.
- V1/K **자동 커서 표시**는 기본ON이다. 마지막 실제 셀에서 target까지 기존 관람 간격으로 직선 보간하고 간격0은 점프한다. K 승인 대기에서 target에 먼저 도착할 수 있으므로 입력 완료 표식으로 해석하지 않는다.
- 커서는 draw-only다. OS 마우스·확정 논리 cursor·Model C 비용을 바꾸지 않고 인간 Mouse Trace/Replay에 합성 경로를 쓰지 않는다. 표시 OFF/ON은 입력 예약·승인·선택을 바꾸지 않는다. Main 속도는 여전히 ms 관람 간격이다.

## 세션·입력·표시 계약

worker 안의 `live_k_policy.KOwner`가 persistent KLocalSession/M과 원 decision/selection graph를 소유한다. 분석이 M을 갱신할 수 있으므로 pending을 버리고 같은 session에서 재분석하지 않는다.

```text
공개 snapshot → K 분석/선택 → pending 보관
→ VALIDATE(현재 session.M + 원 graph) → ADMITTED
→ GUI 최종 비교 → token 소비 → 실제 engine 입력 1회
→ status-first 정확 ACK → NEXT
```

최종 비교·token·step 사이 event-loop yield/await/modal은 없다. 애니메이션은 입력 승인 권한을 갖지 않는다. 확률 primitive DTO는 snapshot/proposal/token/permit/ACK에 결속하며 원 graph를 wire로 재구성하거나 숨은 layout을 K 판단에 전달하지 않는다.

확률은 `EXACT_GUESS`의 기존 `phase_e`를 읽는다. `ExactGuessProbabilities`는 정수 분모/분자, reading-order 좌표, 최소 후보·선택 값, HIDDEN minus pending M coverage, 전체 지뢰 budget을 검사한다. pending M을 실제 FLAG나 ACK 완료로 승격하지 않는다. initial/certain에는 임의 확률을 만들지 않는다. 새 입력·retire·reset·정책·Replay·오류·close는 표시를 만료시킨다.

Unit1 wire v3에서 현재 **v4**로 갱신했다. 메시지2MiB, V1 sequence1921, K envelope31681, pending당 VALIDATE64, 계산30초/응답5초/terminal exit·reap5초/drain0.75초 경계를 유지한다. 정의 ID는 `K_P0_NATIVE_DEFAULT_FIRST_INPUT_V1`이다. frozen V1·K 알고리즘·Model C/profile·table은 불변이다.

`live_auto_cursor.py`는 가상 float 위치와 확정 논리 cursor를 분리한다. mouse-transparent/NoFocus이며 셀 중심·scroll offset·resize를 따른다. OFF·guess/간격 변경·수동 인계·reset·정책·Replay·오류·close는 오래된 callback을 폐기한다. guess OFF는 추측만 막으며 확정 수 Auto는 허용한다.

## 버전별 검증과 identity

외부 산출물 상위는 `C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs`다. 아래 실행을 합쳐 하나의 전체 suite·한 번의 최종 실행으로 쓰지 않는다.

| 단위와 하위 폴더 | 실제 근거 | 한계 |
| --- | --- | --- |
| `MAIN_LIVE_K_P0_UNIT1_2026-11-03\codex_01` | 최종 focused428 + 새 worker7의435 합성. owner7/fixture자손1, reap/tree0/private cleanup | 당시 wire v3, 한 번의 최종435 실행이 아님 |
| 같은 Unit1 `review_claude_01` | 독립428/subtest857 + K01–K07 각1회, REQUIRED_FIXES0. owner7/fixture자손1 | 당시 bytes 범위, native/효과성 미판정 |
| `MAIN_LIVE_K_P0_UI_FEEDBACK_2026-11-03\codex_01` | 현재 focused430=R04 398+R05 9+R06 23, 새 worker2=P01. owner2/fixture자손0 | 현재432는 버전 결속 합성 |
| 같은 UI `review_claude_01` | 현재 bytes의 focused430/subtest785 1회 + worker2 1회, REQUIRED_FIXES0. owner2/fixture자손0 | offscreen/fake job/작은5×1·2×1 wire 검사 범위 |

ui_p01은 K canonical OPEN→선택 추측 지뢰2/3→검증 취소/재승인→OPEN→WON ACK, ui_p02는 v4 V1 초기 입력→WON ACK다. 두 owner의 runtime 보조 PID와 fixture 자손·별도 owner를 구분한다. FINISHED 근거는 검증된 job record의 `terminal`이며 별도 wire 파일 캡처가 남았다고 주장하지 않는다.

UI Claude DTO probe는40게임(추측30·확정822 proposal), 변조28+wire5종, UI probe10개와 정적 대조를 수행했다. method/subtest/owner와 별도 계수다. projection 추가 analyze/select/solver0, 핵심 AST와 job/worker/core/containment raw 불변을 확인했다. 새 정상2사례를 v4 timeout/drain 오류 경로 재실증으로 확대하지 않는다.

| 자료 | SHA256 |
| --- | --- |
| Unit1 source manifest | `d3da995dae6380ace823f634c66ef5a991036794de28cf66966056fe8daca7d1` |
| Unit1 Claude 보고서 | `3b96776d951dd6646102e13652452a4293707ba786e743b8fbbf153d0cfea0a8` |
| 현재 UI source manifest(raw89) | `142d897fdb531f86dc44b64ab715e9418cb4fcb81db11aa0648ec0ccc4610feb` |
| 현재 UI handoff | `13a2a0c076310f2cc0adf665fd46cf7093e7bac081946fb6181ec46e89fa6088` |
| 현재 Codex output manifest204 | `6c60ed004cc62b089063814feaec7d7b796b2208e147c4af7d7fbe1710e3b774` |
| 현재 Claude 보고서 | `2289e10d003c3a99ba4630688fc9f7a96a29d74351751e671e33acae126e963a` |
| 현재 Claude output manifest44 | `1fccc62961261e24d90a88d41b01f920df265193460d4ee888530d9c8803842d` |

## 실패·실행 절차 이력과 정정

Unit1 테스트 오류·finalizer 오타, UI fixture 수명 오류·중단2회(access violation 포함), R03 close 확률 잔상과 read-only method mock 오류는 원 로그와 함께 보존한다. fixture timer cancel/deferred QObject destruction과 close 만료를 수정했고 현재 Claude430은 해당 순서와 실패했던 두 method를 포함해 통과했다.

Codex UI 보호 helper1/1, Claude UI probe 기대값 오류의 helper1/1은 기존 Unit1 Codex/Claude 각1/1과 별도다. 실패 기록과 누계를 유지한다. **Codex 중단 focused의 미기록 temp 정리는 NOT_VERIFIED**다. 전역 TEMP를 추정 검색·삭제하지 않는다.

UI Claude의 미승인 python3 Store alias2회·미등록 승인 Python one-liner2회와 wrapper tmp/argv 누락·보충 설명을 기록한다. reviewer는 이4호출에 project import/쓰기/policy owner0을 보고했다. interpreter 호출 자체와 owner0은 다르며 정상 검증·절차준수 PASS로 세지 않는다. 승인 Python의 bounded 검사와 raw identity를 기술 근거로 사용한다.

원 UI 보고서의 종료 추정19:15/33분은 실제 전달 **19:12/약30분**, temp13개는 manifest단계 포함 **14개**로 정정한다. coordinator는14개가 비어 있음을 확인했다. 원 보고서/manifest/hash는 보존한다.

기존 독립 **F02 NOT_VERIFIED**, 과거 Qt shared FileDialog 보존 **FAIL**, E helper R1 전 재사용 금지와 offscreen glyph 한계는 유지한다. 이번 private INI/제한 registry 검사는 native 사용자 설정 전체 보존이나 과거 실패 복원이 아니다. 이 항목의 복구·재검증 루프는 재개하지 않는다.

## 사용자 수용·남는 항목

사용자는 Unit1 뒤 “다 괜찮은 것 같고 몇 가지 피드백.”으로 확률/커서를 요청했고, 새 구현·검토 뒤 “다 괜찮은것 같은데 몇 가지 피드백.”으로 같은 판 K 제한과 확정색 부재를 질문했다. 둘 다 후속임을 확인한 뒤 현재 단위를 마감하도록 동의했다. 이를 **현재 범위의 사용자 수용**으로 기록한다.

개별 native6항목 명세, preset별 실행 수·완주, 창 단위 RIGHT/BOTH, 실제 DPI/scroll/glyph 환경은 보고되지 않았다. 독립 V1 이동 probe도 없으며 Codex focused 검사가 근거다. 실제 Main UI+실제 worker 동시 smoke·전체 suite·새 package/EXE·효과성 검증은 없다. 모든 branch/OS/DPI PASS를 만들지 않는다.

OPTIONAL은 보류한다. Unit1 O-1..O-7과 UI O-U1(승인 대기 원형), O-U2(step 뒤 overlay 갱신 순서 hardening), O-U3(FINISHED 주석/terminal 근거), O-U4(중복 clear)가 남는다. 필수 수정0이며 주석 정리를 위해 source bytes를 바꾸거나 새 process campaign을 열지 않는다.

후속 작업:

1. **K 확정 안전/지뢰 초록·빨강 표시**: 이미 확정한 정보의 표시 투영. 이전 pending-M overlay 보류 계약을 명시 개정하고 실제 FLAG·입력 승인·ACK와 분리한다.
2. **같은 판 K 신규 인수·재인수**: 수동/Simple/V1 public state의 새 session/M 초기화·외부 FLAG·owner 정리·ACK를 별도 설계한다.
3. **Main LC0/LC1 연결**: 기존 실험적 정책·검토 근거와 lifecycle을 확인할 별도 구현 단위다. 현재 selector 실행은 disabled다.

거리 가변 CPS/Model C 관람 모드·package·후속 연구·Stage4도 별도 남은 작업이다. 후속 자동 착수를 이 문서로 승인하지 않는다.

## 문서·Git·recovery와 경계

작성 시 main/HEAD/local origin/main=`98203e809581f969685addeed45d7ebc7ff4c528`, ahead/behind0/0, staged0이다. 이전 Simple/V1의24경로 Git은 이 SHA에서 완료됐다. 이번은 **새 K source/tests18 + 문서6 = 새로운24경로(M13/U11)**의 precommit snapshot이다.

문서6개는 root README/ARCHITECTURE, docs CURRENT_HANDOFF/README, Extended README, 이 K closeout이다. 이전 closeout·과거 evidence·Desktop 원본은 보존한다. raw 실행 bytes와 정규화 Git blob을 구분하며 새 commit을 과거 실행 identity로 소급하지 않는다.

문서 검수·정확한 COMMIT_PLAN·사용자 일괄 Git script는 `C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\MAIN_LIVE_K_P0_DOC_CLOSEOUT_2026-11-03\coordinator_01`에 있다. coordinator는 stage/commit/push를 실행하지 않는다. 사용자 단일 절차 뒤 receipt·실제 SHA를 확인하고 Desktop recovery 교체 사본을 준비한다. postcommit 문구를 위해 같은 추적 문서를 다시 commit하지 않는다.

D0–D5 FINAL ACCEPTANCE PASS/CLOSED, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인, V1 CLOSED/FROZEN, Extended ACTIVE. Main의 실험적 K 연결은 Production/Gate-P 판정을 바꾸지 않는다. Phase2·R0-B/ActualE2 미승인/미실행. frozen 정책·Model C·holdout `2,010,000..2,010,099`·공식/formal evidence 경계를 유지한다.
