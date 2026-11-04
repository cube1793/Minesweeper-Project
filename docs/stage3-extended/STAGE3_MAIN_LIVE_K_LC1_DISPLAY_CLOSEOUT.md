# Main/Live K-LC1 및 표시 안정화 closeout

기준일: **2026-11-04 (Asia/Seoul)**. **구현·범위 한정 독립 검토·사용자 native 수용 완료. 문서 마감·사용자 일괄 Git 준비.**

기준 commit은 **4f34a9690fd913f8702404a3c1c6122c078bd4d0**(수용된 Main LC0)다. LC1 연결 뒤 Replay/확정색 표시를 별도 증분으로 개선했다. 최종 source314와 두 독립 검토를 버전별로 구분한다. [LC0 closeout](STAGE3_MAIN_LIVE_K_LC0_CLOSEOUT.md)과 [별도 LC1 정책/viewer closeout](STAGE3_K_LC1_SINGLETON_BAND_V1_CLOSEOUT.md)은 이전 역사다. 원 보고서의 PENDING·FAIL은 당시 상태로 유지한다.

## 1. 사용자 수용과 현재 범위

사용자는 LC1 독립 검토 뒤 “다 정상인데 몇 가지 피드백.”이라고 기능을 확인하고 Replay 참고 추천/실제 입력의 혼동과 빠른 Auto의 확정색 깜박임을 제기했다. 표시 증분을 구현·독립 검토한 뒤 native 안내를 확인하고 **“이제 다 괜찮은 것 같아.”**라고 수용했다.

이 수용은 현재 사용자 환경과 안내 경로에 한정한다. 보고되지 않은 preset별 완주 횟수·DPI 수치·모든 OS·희귀 오류·새 package 수용을 추정하지 않는다. 표시 검토의 OPTIONAL 문구2개와 내부 identity 메모는 필수 수정으로 승격하지 않고 남긴다.

- Main 정책: Simple, frozen V1, K-P0, K-LC0, K-LC1. K 계열은 초급·중급·상급의 새 판/FLAG-free 현재 판/기존 FLAG 준비/정상 수동 인계 뒤 재인수를 지원한다. V1/K 계열 custom은 미지원이다.
- 새 판 Auto/guess OFF. 수동 첫 press는 모든 정책의 Auto/guess를 끄고 원 gesture를 처리한다. Auto OFF만으로는 유효 계산/pending을 보관한다. 다시 Auto ON할 때 필요한 owner 정리를 먼저 마친다.
- 기존 FLAG는 공개 local proof로 확인·정리한다. 미확인은 오답/안전 판정이 아니며 실제 지뢰의 FLAG도 해제될 수 있다. 물리 입력은 Replay에 기록한다.
- K-P0/K-LC0/K-LC1 **(실험적)** 표시는 유지한다. 라벨 변경·새 UI 기능은 이번 문서 마감에 섞지 않는다. 실험적 표기를 지우더라도 Production 승인과는 별개다.

## 2. LC1 선택·실제 입력 계약

Live 정책 ID는 K_LC1, 원 정책 정의는 SINGLETON_BAND_V1이다. normal 결정은 동일 native 분석1/선택1 → 원 apply_singleton_band1(내부 actual LC0 apply_distance_band1)로 진행한다. 원 native g, 실제 LC0 baseline b, LC1 final을 구분한다. g를 실행하고 LC1이라고 표기하지 않는다.

예외 후보는 원 survivors의 direct safe OPEN(R=1, setup 없음, 현재 HIDDEN/selection_safe_cells)뿐이다. HIDDEN8 성분 C에는 숨은 논리 M도 연결하고 C−preinput_M={target}인지 검사한다. native g 대비 105% 초과·110% 이하, D(p)<D(b)를 만족해야 하며 전체 계획 D→정확 Fraction(E)→L→frozen tie로 선택한다. 적격 후보가 없으면 실제 b를 유지한다. EXACT_GUESS·initial OPEN과 native 정책·Model C는 불변이다. 110%는 전체 게임 비용 보장이 아니다.

| 항목 | 현재 계약 |
| --- | --- |
| Canonical 정의 | K_LC1_SINGLETON_BAND_FIRST_INPUT_V1 |
| FLAG-free 정의 | K_LC1_PUBLIC_ADOPT_SINGLETON_BAND_FIRST_INPUT_V1 |
| FLAG 준비 정의 | K_LC1_PUBLIC_FLAG_ADOPT_LOCAL_BOOTSTRAP_V1 |
| normal phase | K_LC1 |
| 공통 wire | v9. v8 등 다른 버전은 거부 |
| 한도 | normal480 + preparation480 =960; pending VALIDATE64; V1 seq1921; K envelope31681/FLAG 포함63362; 메시지2MiB |
| 시간 한도 | compute30 / ACK5 / exit5 / drain0.75초 |

지속 native session/M·원 graph/selection identity·game/run/generation/entry/시작 및 M revision·이력·token/nonce가 이어진다. worker VALIDATE→ADMITTED 뒤 GUI 최종 비교→token 소비→실제 step1 사이에는 yield가 없고 정확한 ACK 뒤 NEXT로 간다. 계획 suffix는 실행하지 않는다.

ACK 중 정상 수동 입력은 원 receipt만 확인하고 현재 보드/M/cursor/revision을 되돌리거나 NEXT를 보내지 않는다. 옛 owner 종료·reap·tree0·private cleanup 뒤 새 owner를 허용한다. 실제 receipt/이력/정리 오류는 기존 fail-closed다. FLAG bootstrap의 가린 판 분석은 정상 입력 승인에 쓰지 않는다.

## 3. Replay 및 확정색 표시 계약

**Replay:** 녹화된 다음 event를 첫 줄과 테두리로 표시한다. Simple 참고 후보는 별도 줄이며 추천 테두리를 만들지 않는다. 참고 분석 OFF/오류에도 녹화 입력은 남고 OFF에서는 분석 호출0이다. CHORD는 열린 anchor, PLAYING의 FLAGGED 대상 FLAG는 UNFLAG로 표시한다. WON/LOST 뒤 FLAG는 자동 종료 깃발 때문에 UNFLAG로 오해하지 않는다. 끝·빈 기록에는 다음 입력이 없고 범위 밖 target은 테두리를 만들지 않는다.

“추천과 다름/같음/동등/비교 대상 아님”은 일반 UI/tooltip에서 제거했다. 내부 ReplayComparisonKind/compare_replay_action/comparison_text는 유지한다. Simple은 다음 녹화 event를 읽기 전에 원 공개 상태로 분석하므로 녹화 입력이 후보를 바꾸지 않는다. Replay JSON/source_type·녹화 데이터·Space/Enter·통계는 불변이다.

**확정색:** 실행 분석은 매 입력 뒤 무효화하되 별도 CertaintyFrame이 같은 유효 game/policy/run/generation/owner/revision/이력·관측 context의 SAFE/MINE만 보관한다. Auto 입력1회 뒤 ACK/다음 계산 대기 중 여전히 HIDDEN인 색만 유지하며 열린/FLAG 칸은 즉시 제외한다. 이전 추천·guess·확률을 보관하지 않는다. 새 분석 결과로 통째 교체하고 합집합으로 누적하지 않는다.

pause와 확률 토글은 유효 frame을 유지한다. 수동 첫 press·정책·reset/난이도·Replay·게임 종료·분석 OFF·오류·owner 폐기는 지운다. 오래된 응답/frame과 같은 모양의 새 판은 context 비교로 거부한다. 표시 frame을 조작해도 token/실제 입력/다음 선택 권한을 얻지 못한다. 추가 solver/select/worker·sleep·processEvents·입력 지연·repaint lock은 없다. CellButton은 그림과 tooltip 값이 모두 같을 때만 중복 update를 생략한다.

## 4. 버전별 검증 근거

외부 root는 C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs다. 각 단위의 codex_01과 review_claude_01이 원 보고서·원장·manifest를 보관한다.

| 단위 / snapshot | 구현자 검증 | 독립 검토 |
| --- | --- | --- |
| MAIN_LIVE_K_LC1_UNIT1_2026-11-04 / source310 | focused625/905는622+3 합성; real6사례/8owner/Auto10 | focused625/905 단일 실행; real6/8/10; probe24 PASS; REQUIRED_FIXES0 |
| MAIN_LIVE_DISPLAY_STABILITY_2026-11-04 / source314 | focused263/355는260+3 합성; real2사례/2owner/Auto4; ID-gate QA9조건 | focused263/355 단일 실행; real2/2/4; probe9 PASS; REQUIRED_FIXES0 |

두 수치를 더해 전체 suite라고 하지 않는다. LC1의625는 source310, 표시263은 최종 source314에 결속한다. 후자는 source310에서5개 수정+4개 신규이고305개는 불변이다. 표시 검토는 입력/ACK/timeout/retire 등 핵심54메서드 AST 불변도 확인했다. 이번 문서 마감에서는 제품 test/worker를 다시 실행하지 않았다.

LC1 P01은 합성6×14 공개 상태와 실제 낭비 CHORD(0,0)를 설치한 seam이다. normal LC1 OPEN(2,1), 실제 LC0/native g FLAG(0,11)→CHORD(1,11)의 차이와 산술을 확인했다. 8owner/24소유PID의 Job 소속·reap·tree0·channel/handle 정리를 확인했다. source310 probe는84cursor의 직접 native/독립 oracle 대조, 원 선택 바꿔치기와 입력 이력 변조 거부를 확인했다.

표시 P01은 LC1 OPEN(2,1)→FLAG(0,11), V1 FLAG(0,11)→CHORD(1,11) 총4입력이다. 2owner/6소유PID와 별도 runner4PID 종료를 확인했다. 의도된 cancel exit1을 오류 종료로 오해하지 않는다. 대기 sample은 확정색만 있고 이전 추천·확률0이다. 자연 초기 flood·모든 preset 완주를 뜻하지 않는다.

독립 표시 probe는 녹화 다음 event7변형에서도 Simple 입력/결과 불변, 참고 OFF17이동 분석0, 종료 후 FLAG 표시, 늦은 ACK/proposal/frame 차단, 위조 SAFE frame의 입력 영향0, 같은 그림의 update 생략을 확인했다. HIDDEN6 fixture라 새 결과 교체와 합집합의 차이는 실행만으로 구별하지 못했지만 코드상 새 분석이 frame보다 우선해 합집합 경로가 없다. offscreen에는 실제 compositor/GPU/DPI/글꼴 한계가 있다. 사용자의 후속 native 확인은 별도 수용 근거다.

## 5. 실패·절차 이력과 보류 사항

- LC1 focused 최초3건은 wire 기대값 오류였다. product bytes는 같고3개 test의 기대를 수정한 뒤 보완 실행했다. 원 FAIL과622+3 합성을 보존한다. p01의 “wasted OPEN” 서술은 실제 CHORD(0,0)이며 독립 검토가 정정했다.
- 표시 초기 fixture/종료 FLAG 표현과 기대값 실패를 수정했다. 최종 R01은 PS 정렬 gate에서 차단되어 test0, R02는260PASS+3FAIL, 기대 보완3PASS였다. 원 기록과 승인된 별도 PS5.1 QA 재시도9조건을 보존한다. 전역 실행 정책은 바꾸지 않았다.
- LC1 검토 helper의 PS5.1 ID 비교 공백은 독립 수동 exact 대조가 보완했다. 이후 typed/ordinal 비교와9조건 QA를 준비했다. 표본 숫자/원 파일을 소급 고치지 않았다.
- 표시 검토 kit H1은 EXECUTION_LEDGER.json 초기화 누락이다. reviewer가 C01 전에 review root에 빈 데이터 파일을 생성했다. 실패 실행·재실행·helper 변경 없이 준비를 보완했으므로 **복구0/1** 판정이 맞다. coordinator가 후속 템플릿에 초기화를 추가했다. H2의 상속 campaign 필드를 별도 실행 예산으로 세지 않는다.
- **표시 OPTIONAL O1:** Replay 상태 tooltip 끝의 Live 범례 “테두리: 실제 추천”이 남는다. 실제 Replay 테두리는 녹화 다음 입력이다.
- **표시 OPTIONAL O2:** Auto 입력 직후 pause하면 실제 새 요청 없이도 “다음 수 계산 중”이 남을 수 있다. 색 유지와 입력 정지는 정상이다.
- **표시 OPTIONAL O3:** owner object id 재사용은 이론적으로 가능하지만 run UUID/generation이 함께 검증되어 관찰된 영향은 없다.
- LC1의 나머지 낮은 권고(process 실행 파일 label·개행·binding 메모)와 이전 OPTIONAL은 원 보고서에 보존한다. 일괄 해결됐다고 표시하지 않는다. LC0 probe48/49와 옛 mouse 기대2개 실패도 당시 기록이다.
- **F02 NOT_VERIFIED, Qt shared FileDialog 보존 FAIL, 이전 중단 TEMP와 LC0 전역 TMPDIR 잔여물 NOT_VERIFIED**는 그대로다. 현재 private 정리·제한된 INI/registry 또는 native 수용으로 이를 PASS로 바꾸지 않는다. 옛 F02/설정/TEMP 재검증 루프와 전역 TEMP 검색·삭제는 재개하지 않는다.

## 6. 핵심 identity

| 파일 | SHA256 |
| --- | --- |
| LC1 source310 manifest | ef225ff6dafd639e3f30a68968fe4fdb33b14fba26a6aecec75d29bd3a6a44ee |
| LC1 구현 handoff | edc087fb086f87e0c573059f8e8f5c5ef0667a8627b20411f6b4b30b91541133 |
| LC1 review OUTPUT_MANIFEST(39) | 0987b9b67db3a1c7c3d8b95681b571ddc0e9e287ad241846a92254b0e59a37f2 |
| 표시 source314 manifest | 61d96678759c04f38f4931cc0bd5b465a10953b2b6c78f82c03d99691138bb3d |
| 표시 구현 handoff | e6641f332979331128bc32486394feb07cef5c0e1af50fb0da58bb3f221cdaab |
| 표시 구현 OUTPUT_MANIFEST(407) | 9371eb484f7aa4068067a5369273e7de7506eb6b3748c173ed57e30608afb6e7 |
| 표시 review report | 758dfeffd340872c996c060dcff30d1a7aa22920e283652005f56272044dfa08 |
| 표시 review OUTPUT_MANIFEST(44) | 69706fc5685c1d669ab448e1773aa06fc06128f184485f9c7f0e3bd8867fe763 |

구현자·검토자의 원 manifest, raw 파일, 실패 이력은 수정하지 않았다. 원 raw SHA256과 Git CRLF→LF 정규화 blob OID는 구분한다. 문서8개는 실행 source314 manifest에 포함되지 않는다.

## 7. 문서·Git 및 다음 절차

문서 작성 시 **main / HEAD = local origin/main =4f34a9690fd913f8702404a3c1c6122c078bd4d0 / ahead·behind0·0 / staged0**다. LC1+표시 source/tests22(M14/U8) + 문서8(기존7/신규1) = **30경로(M21/U9)**의 미커밋 단위다. 외부 evidence/helper/recovery는 commit 대상이 아니다.

조율 root: MAIN_LIVE_K_LC1_DISPLAY_DOC_CLOSEOUT_2026-11-04/coordinator_01. source314, 원 evidence, 다른 문서, Desktop recovery, index를 보존하고 문서8개만 갱신한다. 사용자용 단일 script는 고정 raw/정규화 blob identity로 정확한30경로 stage·commit·push를 수행하고 receipt를 남긴다. coordinator는 Git 쓰기나 제품 실행을 하지 않는다.

**NEXT: 사용자 일괄 Git → 실제 receipt/commit 확인 → postcommit recovery 두 사본 → 사용자 Desktop 교체 → 다음 작업 범위 선정.** 이미 완료된 LC0 Git은 반복하지 않는다. postcommit 문구만을 위한 추가 문서 commit을 만들지 않으며 실제 완료 SHA는 receipt/recovery/live Git으로 확인한다.

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE다. Phase2/R0-B/ActualE2는 미승인/미실행이며 frozen 정책·Model C·holdout **2,010,000..2,010,099**·공식/formal evidence 경계를 유지한다. Main LC1 수용은 별도 viewer의 실험 결과 확대나 새 package/Stage4/연구 시작 승인이 아니다.
