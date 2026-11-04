# Current Project Handoff

Updated: **2026-11-04 (Asia/Seoul)** — Main/Live K-LC0 Unit1 구현·독립 검토 필수 수정0·사용자 native 수용 완료. 문서 마감·사용자 Git 준비.

## 현재 기능과 수용

현재 authority는 [LC0 Main closeout](stage3-extended/STAGE3_MAIN_LIVE_K_LC0_CLOSEOUT.md)이다. [K 인수/UI closeout](stage3-extended/STAGE3_MAIN_LIVE_K_ADOPTION_UI_CLOSEOUT.md)은7f15355까지의 이전 checkpoint다. 사용자는 LC0 native 확인 후 마우스 경로 활성 조건을 재확인하고 **“내가 잘못 판단한것 같네, 다시 확인해보니 전부 정상같아.”**라고 수용했다. 이는 현재 환경·안내 경로에 한정하며 모든OS/DPI·preset완주·전체suite를 뜻하지 않는다.

K-P0/K-LC0는 세 preset의 새 판, FLAG-free 현재 판, 기존 FLAG 준비, 정상 수동 인계 뒤 재인수를 지원한다. LC0는 native K-LC0/DISTANCE_BAND_V1 control=False이며 원 survivors105% band의 전체 route D→E→L→tie로 선택한다. 원 graph/DistanceSelection과 물리 검증을 모두 결속하고 실제 첫 입력1회만 실행한다. native g를 LC0로 대체 표기하지 않는다.

공통 wirev8과 필수 game_id, 정책별 정의/normal phase, 시작·M revision/token/nonce/정확 ACK가 이어진다. bootstrap은 동일 native session의 공개 local proof며 M 외부 주입이 없다. 수동ACK인계는 옛 receipt만 처리하고 현재판을 덮어쓰거나NEXT를 보내지 않는다. 새owner는reap/tree0/cleanup뒤 시작한다. 실제 오류의 fail-closed는 유지한다.

Simple/V1/P0/LC0 모두 수동 첫press에Auto/guess OFF, Auto OFF만으로는pause다. 기존 확률/확정색/가상원형, Replay 사용기록·Space/Enter/editorfocus를 유지한다. 마우스 경로 표시는 기록을 켠 수동판 종료 후에만 가능하다. 실제자동입력1회가있으면그판trace는무효이며 단순정책선택/분석/AutoON은해당하지않는다.

K-P0/K-LC0의(실험적)표시는유지한다. LC1연결/native이후UI정리에서검토할수있으나라벨삭제자체가Production승인은아니다. Main LC1 disabled, V1/K/LC0 custom 미지원. 별도 LC1 저장viewer는 Main 실행과다르다.

## 검증과 남은 한계

- source111 manifest SHA256 **fd58110b2dba907560767ddab1d9e6d0899411cff534cb68a1ec0549df76b629**.
- Codex555/794는동일bytes의536/788+19/6합성, Claude555/794는단일실행이다. 각실worker6사례/8owner/Auto10. Claude는최초환경실패시도1/Popen0후복구1회로누적시도9다. 각campaign의24소유PID기록·reap/tree0/private/handle정리가있다.
- Claude probe49중48PASS,1개는MAX_INPUTS를480으로기대한오류다. 현재/HEAD는480+480=960. 원FAIL을보존하고재실행하지않는다. no-yield는Python수준관찰과정적근거다. 모든수는선택범위·해당버전근거다.
- TMPDIR상속으로최초process와focused가쓴전역TEMP잔여물은이번추가NOT_VERIFIED다. 복구campaign의전용tmp정리와구분한다. 이후wrapper는TMP/TEMP/TMPDIR모두고정한다. 원evidence를고치거나전역TEMP검색/삭제루프를열지않는다.
- 옛mouse기대2개는HEAD에서도실패한기존기대값문제로독립확인했다. 현재Qt첫press/release계약은검증됐고, 해당test갱신·개행/측정차이는보류권고다.
- 과거F02 NOT_VERIFIED, Qt shared FileDialog FAIL, 과거중단temp NOT_VERIFIED, 이전OPTIONAL/실패/절차정정은유지한다. 제한INI/registry와native수용으로덮지않는다.

## Git / NEXT

문서작성기준 **main / HEAD = local origin/main =7f15355a1d17a3fab1b4b11d85897b02a6bda5d5 / ahead·behind0·0 / staged0**. LC0 source/tests21 + 문서8 = **29경로(M25/U4)** 미커밋이다. 이전7f15355의32경로Git/recovery는완료이력이다. 원실행raw와정규화Gitblob을구분한다.

이번root는 MAIN_LIVE_K_LC0_DOC_CLOSEOUT_2026-11-04/coordinator_01. **NEXT: 사용자29경로일괄stage/commit/push→실제receipt/SHA확인→postcommit recovery두사본→사용자Desktop교체→Main LC1 연결단위준비.** postcommit문구만위한추가문서commit은하지않고완료SHA는실제receipt/recovery/liveGit을따른다. 옛Githelper재실행,LC0재구현,추가독립검증은하지않는다.

## 영구 경계

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인, V1 CLOSED/FROZEN, Extended ACTIVE. Phase2/R0-B/ActualE2 미승인/미실행. frozen정책·ModelC·holdout2,010,000..2,010,099·공식/formal evidence유지. 새package/Stage4/연구자동시작권한은아니다.
