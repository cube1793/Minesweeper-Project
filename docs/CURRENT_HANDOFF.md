# Current Project Handoff

Updated: **2026-11-03 (Asia/Seoul)** — Main/Live Simple·V1 기능/UI 사용자 native 수용, 문서·Git 준비(precommit).

## 현재 상태와 수용

Main의 Simple·frozen Stage3 V1 Auto, 수동↔V1 재인수, 공개 FLAG 검토/미검증 해제와 네 UI 개선을 사용자가 최신 native 창에서 확인했다. 기존 기능에 “전부 정상이긴한데 몇 가지 개선점”, 개선 뒤 “모두 정상인 것 같아.”라고 확인했다. [상세 closeout](stage3-extended/STAGE3_MAIN_LIVE_SIMPLE_V1_CLOSEOUT.md)에 계약·버전별 근거·한계를 모았다.

새 판은 수동 가능·Auto OFF·guess OFF이며 정책 선택만으로 실행하지 않는다. Simple의 수동/Auto 혼합은 유지하고, V1은 첫 유효 board press에서 Auto를 끄고 원래 gesture를 이어간다. 실제 수동 입력 뒤 다음 V1 segment는 guess OFF이며, 이전 owner의 exit/reap/tree0/cleanup 뒤 같은 판의 현재 상태를 새 ADOPT owner로 인수한다.

V1 Auto OFF는 owner·유효 pending을 보관하는 일시정지다. **추천·계산 종료**는 pending을 버리고 worker를 종료한다(Simple에서는 비활성). 일시정지/간격/guess 변경만으로 유효 계획·FLAG 검토를 다시 계산하지 않는다. 정책 변경은 Auto OFF와 옛 owner retire 뒤 다음 명시 ON에 적용하며 보드·기록은 보존한다.

FLAG 검토는 모든 FLAG를 HIDDEN으로 둔 공개 view의 직접 zero/all+전체수 zero/all만 인정한다. PROVED_MINE 유지, SAFE/UNVERIFIED는 준비 FLAG 토글로 해제/닫힘 유지다. 미검증은 오답/안전 판정이 아니며 실제 지뢰도 해제될 수 있다. K-P0/LC0/LC1 실행은 disabled, 화면 Stage3 V1의 내부 frozen identity와 Model C는 불변이다. Main은 ms 관람 간격만 제공한다.

## 현재 Git과 NEXT

main / HEAD == local origin/main == `d1201e481da7199a46b4ab80eaf5c303e77db10a`, ahead/behind0/0, staged0. **source/tests18 + 문서6 = 미커밋24경로(M13/U11)**이며 clean/새 commit/push 완료가 아니다. 현재 raw bytes는 F SOURCE_MANIFEST와 이번 COMMIT_PLAN의 source18에 결속한다. raw 실행 identity와 예상 LF index blob은 구분한다.

K-LC0의20경로는496fab0, K-LC1의10경로는d1201e4에서 사용자 commit/push가 이미 끝났다. 옛 closeout/recovery의 precommit/NEXT를 반복하지 않는다. 미래 commit SHA로 과거 run identity를 대체하지 않는다. 로컬 origin/main 확인은 fetch/서버 조회가 아니다.

**NEXT: 문서/24경로 commit plan 검수 → 사용자의 stage·commit·push → 실제 새 SHA로 외부 postcommit recovery2개 갱신 → K 연결 첫 단위 준비.** K 지속 세션/M/FLAG/ACK·재인수는 V1과 별도 계약으로 다음 단위에서 다룬다. 현재 문서가 구현을 자동 승인하지 않는다. Main Model C/CPS/거리 가변 속도, package, 후속 알고리즘 연구·Stage4는 별도 남은 작업이며 대규모 영상 분석/재평가를 새 필수 gate로 만들지 않는다.

## 근거와 남는 한계

- A/B의267·288/353·Claude108은 당시 버전. A Expert2착수/첫237입력 완주 뒤 transport 보완이 있었으며 최종 transport/현재 D/F bytes 전체 완주로 소급하지 않는다.
- D 최종380=F01 110+F02 6+F06 264 합성, 누적1167/역사1실패. 최초 운영 helper 오류로 Beginner1/V1 owner0이었다.
- E 새 Beginner2 case, V1 owner3/ZiNi2, 운영80 assertion PASS 중6중복. 공개7상태·Replay6event·Auto3(UNFLAG1/FLAG2)·수동3/Model C445066µs. Auto OPEN/CHORD·guess ON·WON/LOST·terminal-only Replay NOT_REACHED.
- E Claude source PASS/제품 REQUIRED_FIX 없음,374 PASS, 독립 proof5689상태/15957FLAG/위반0. Claude F02 역사7method/실제생성0(두 runner 오류)로 **독립 F02 NOT_VERIFIED**. D Codex 실제6개 PASS와 분리하며 추가 독립 재실행은 이번 완료의 의무 gate가 아니다.
- F 최종35는 R03 34+R04 DPI1, 누적102method/186subtest. geometry42는 fixture 고정 크기/SetNoConstraint이며 native 최소 폭/다른 OS·DPI 수용이 아니다. R03 실행 plan/helper 사본과 final runtime/test 동일성을 구분한다.
- offscreen glyph 누락은 그대로다. 이번 사용자 native 수용이 과거 PNG를 고치거나 모든 branch/package를 검증한 것은 아니다.
- Qt 공용 FileDialog 설정 보존 **FAIL 유지**, 정확한 이전 값/복원 판정 없음. 이후 값·last-write 차이의 주체/원인은 미확인. 정상 사용자 대화상자 history 동작과 자동화 계약 실패를 구분한다.
- **E 운영 helper는 R1 수정 전 재사용 금지**. 이번에 고치거나 실행하지 않는다. 미래 자동화는 실제 대화상자를 피하거나 정확한 격리 계약을 먼저 정한다. optional O1/O2/O3은 원 기록에 남긴다. P1 reap 뒤 추가 strict read와 drain의 일반 poll read를 전체1회로 축약하지 않는다.

## Main과 별도 전시/저장 viewer

실행은 closeout의 승인 Python `-B`/`QT_QPA_PLATFORM=windows` 안내를 따른다. `main.py`는 현재 Live 보드에서 실제 입력한다. [K-LC1 closeout](stage3-extended/STAGE3_K_LC1_SINGLETON_BAND_V1_CLOSEOUT.md)의 외부 viewer는 저장8191/97만 재생하고, 기존 `experiments.k_lc0_exhibition`은 actual K-P0/K-LC0 전시다. Main K/LC 연결·새 package 수용으로 혼동하지 않는다.

## 보존된 경계와 recovery

D0–D5 FINAL ACCEPTANCE PASS / CLOSED, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인, Stage3 V1 core CLOSED/FROZEN, Extended ACTIVE 유지. Phase2 NOT AUTHORIZED, R0-B/ActualE2 NOT RUN/NOT AUTHORIZED이며 [기존 연구 경계](stage3-extended/README.md#current-program-k-boundary)를 재개하지 않는다. holdout2,010,000..2,010,099와 공식 evidence를 열거나 실행하지 않는다.

이번 output: `C:\Projects\GraduationProject\MAIN_LIVE_SIMPLE_V1_DOC_CLOSEOUT_2026-11-03\codex_20261103_02`. REPORT_KO, COMMIT_PLAN, USER_GIT_STEPS_KO.md/.ps1, 문서 before/after/patch/hash, 정적 검사·보존 receipt·manifest와 Desktop 동명 교체용2개를 제공한다. 교체본은2026-11-03 내용/precommit이며 Desktop 원본은 읽기만 했다. 사용자 Git 후 실제 SHA로 postcommit 사본을 작성한 뒤 사용자가 Desktop을 교체한다.

source/tests/fixture·기존 산출물 수정0, 테스트·앱·worker·solver·pilot·분석·build·network·Computer Use0, Git 쓰기0. 승인된 문서6개만 바꾸고 사용자 검수와 Git 실행 전에 STOP한다.
