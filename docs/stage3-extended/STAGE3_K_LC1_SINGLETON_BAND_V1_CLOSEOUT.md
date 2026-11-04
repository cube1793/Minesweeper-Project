# K-LC1 / SINGLETON_BAND_V1 — 별도 실험적 source checkpoint

> **현재 상태 안내 (2026-11-04):** 아래 별도 LC1 source4+문서6의 10경로 commit/push는 **d1201e4**에서 완료됐다. 저장8191/97 viewer와 원 정책·pilot은 역사로 보존한다. 이후 **Main/Live LC1 연결 및 표시 개선도 사용자 수용 완료**했으며 [현재 Main closeout](STAGE3_MAIN_LIVE_K_LC1_DISPLAY_CLOSEOUT.md)을 따른다. 아래 “현재 HEAD”·미커밋·Main 미연결 표기는 2026-11-02 당시의 범위다. Main 수용이 이 viewer의 실험 결과나 효과성·Production 판정을 확장하지 않는다.

작성 기준: **2026-11-02 (Asia/Seoul)**. 구현·복구 pilot·독립 검토·저장 viewer를 완료했고,
아래 두 저장 경로에 대한 제한된 사용자 확인을 반영한다. 이번 문서 갱신 자체는 정적 작업만
수행했다. K-LC1은 frozen이 아니며 원 K-LC0 교체·일반 효과성·production 승인이 아니다.
현재 HEAD는 `496fab0fc8829af7a255c403346985be7ae6a005`, 이번 source4+문서6은 미커밋이다.
향후 current Git/NEXT는 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md)와 최신 recovery를 따른다.
과거 PENDING/실패/검토 보고서는 당시 snapshot으로 보존한다.

## 1. 제한된 사용자 확인과 수용 경계

사용자2026-11-02 발언(이번 문서 지시에서 전달된 adjudication):

> 게임 8191의 145-153 구간에서 O(23,0) 처리 경로는 좀 더 자연스러워진 것으로 판단됨.
> 게임 97도 정상적임을 확인함. (양쪽에서 차이는 없음)

이후 잔여 구역 선택 이유를 설명받고 지금 고쳐야 하는지 질문했다. Coordinator는 구현 결함이
아닌 후속 정책 개선 범위로 알려진 한계를 기록하고 넘어갈 것을 권고했고, 사용자는 최종
**“그럼 넘어가자.”**라고 동의했다. 해당 경로의 제한된 확인이며 미보고 slider/drag/key/manual
rate·모든 native 조작/DPI/OS PASS를 추정하지 않는다. 특정 사례의 자연스러움은 일반 효과성,
승률, native g 최적성, production 또는 새 package 수용을 뜻하지 않는다.

## 2. 고정 정책 계약

계보는 **frozen V1 → K-P0 → 실험적 K-LC0 → 별도 K-LC1**이다. V1 확장은 생략했고 원
정책들은 그대로다. V1도 CHORD를 사용하며 Stage2 Simple과 다르다.
K-LC0 / DISTANCE_BAND_V1은 원105% 계약을 유지한다. K-LC1 정의는 SINGLETON_BAND_V1이다.

입력당 native select_policy1회가 evidence/candidates/routes/pruning/survivors/g를 소유한다.
동일 native 결과에 `apply_distance_band(control=False)`를 순수 적용해 현재 actual LC0 선택 b를
얻는다. CONTROL(native K-P0 g)은 이번 baseline이 아니다. 추가 추론·후보·route·repruning 없이
다음 조건을 모두 만족하는 원 survivor p만 예외로 허용한다.

- 현재 certainty selection_safe_cells에 target이 있고 물리 HIDDEN이다. DIRECT_SAFE_OPEN,
  setup 없음, action은 OPEN 하나, R=1이다.
- 현재 물리 HIDDEN8-neighbor 성분 C에는 숨은 논리 M도 포함해 연결한다. 이후 현재
  `native evidence.after.M == preinput_M`을 빼면 `C − preinput_M = {target}`이다.
  물리 FLAG와 M을 혼동하지 않는다. 생산적 잔여 하나라는 공개 기하 조건이며 전역 추론상
  독립 component를 인증하는 조건은 아니다.
- native g 기준 원105% 밖: `20*L(p)*R(g) > 21*L(g)*R(p)`.
- native g 기준110% 이내: `10*L(p)*R(g) <= 11*L(g)*R(p)`.
- 모든 setup/terminal을 포함한 계획 전체 거리 `D(p) < D(b)`이며 동률은 예외가 아니다.

적격 복수 후보는 D→정확 Fraction(L,R)→L→frozen final tie key로 고른다. 정수 band 비교에
반올림/epsilon을 넣지 않고 기존 route_distance/float 동률 계약을 유지한다. 적격이 없으면 b다.
새 SingletonSelection/validator가 native·b·최종 선택·예외 판정을 분리한다. 105% 밖 선택을
기존 DistanceSelection으로 위장하거나 LC0 validator를 느슨하게 만들지 않았다.

실제 첫 move 하나만 실행한 뒤 fresh 재계획한다. 초기 OPEN(0,0), native 실패 전파,
EXACT_GUESS risk/target/no-setup, 기존 물리 validator, 추론·M 획득/유지·Model C는 불변이다.
guess에서는 예외를 평가하지 않는다. 110%는 한 선택의 L/R 상한이지 전체 게임 비용 악화10%
한도가 아니다. singleton/observer 계산과 관람 선호는 charged Model C에 더하지 않는다.

## 3. source·fixture·검증과 초기 실패 보존

신규 source는 아래4개뿐이며 외부 산출물에 project runtime을 의존시키지 않았다.

| 경로 | raw bytes | SHA256 |
|---|---:|---|
| experiments/program_k_lc1_policy.py | 11487 | 34e2270646f41b65493580d16948e7e90314b7f0ce5f07620dffe11b9a2b36e9 |
| experiments/program_k_lc1_runner.py | 4245 | 25180bde809ad13da52a92afbb23d5f41f215975097991ad19ea6bbb86dda99b |
| tests/test_program_k_lc1.py | 30728 | c67d734260b6fe25632a37e132246fb723999b8183da50898c2f44252c8a9c8f |
| tests/fixtures/program_k_lc1_singleton_native.json | 574621 | 1d00d24309c76418b0af3707c984fc4a5751036ea2ada20048e7314674f49d44 |

LR01/02/03은 같은8191 LC0 궤적의 input21/37/145 공개 state에서 추출한 선택 산술 fixture다.
LR01은196.1307%로 상한 밖, LR02는103.4014%로 기존 override 유지, LR03은108.3559555%의
O(23,0) 예외다. 미래 frame·terminal truth·engine private state를 포함하지 않으며 새 추론/engine
실행 증거로 읽지 않는다. 18980의 식 차감 추론 확장은 별도 범위이며 구현하지 않았다.

초기 최종 source tests는 신규41+직접 의존161=**202 PASS**, 고유202/실행239회/2 invocations,
마지막 invocation202 PASS다. Claude는 새41 tests를 독립적으로1회 실행해41 PASS했다.
복구 통합26과 저장 검산57은 **명명 assertion**으로 unittest 고유 method 수에 합산하지 않는다.
이번 문서 작업에서는 어느 tests/검산 도구도 재실행하지 않았다.

초기 외부 helper는 SimpleMove와 MoveProjection을 dataclass 전체 equality로 비교해 첫 완료
입력에서 실패했다. 실제 **LC0 2 starts / LC1 0 / 완주0**, 저장 action/frame stream도 없었다.
원 결과는 ERROR/미완료로 남겼고 LOST·성공으로 바꾸거나 과거 자료로 채우지 않았다.
corrected_NOT_RUN 참고본의5 guard assertion은 전체 helper 검증본이 아니었다.

복구는 helper를 새 root에 고쳐 action/x/y 필드 비교와 전체 observer/serializer/writer/reader
경로를 검증한 별도 campaign이다. 작은 통합 starts7(실제 작은 engine6+명시 합성 prefix1),
완료5/의도 오류2는 public starts와 별도다. 합성 첫 prefix는 자연 engine flood가 아니다.

## 4. 고정 pilot과 Claude R2

순서는8191→97, 각 actual LC0(control=False)→actual LC1이다. layout은 index마다1개,
동일 layout을 두 fresh engines/sessions에 설치했다. 복구 campaign은2 layouts/4 fresh engines/
**4 starts / 재시도0 / 완료4**, 두 pair 모두 정상 정리됐다. 각 pair cap120초, worker wall
16.891/11.109초, 강제 descendant 정리/timeout 없음이다. 오류/정리 실패 시 다음 pair를 막는
규칙은 유지한다. 실제 OS 오류 주입 검증을 했다고 확대하지 않는다.

K-LC1 두 campaign의 역사 누계 public starts는 **6(LC0 4, LC1 2)**이다. 새 campaign retry0은
역사적으로 재실행이 없다는 뜻이 아니다. 작은 통합 starts7은 이 누계에 넣지 않는다.

저장 자료는 **4 actual traces / 662 actions / 666 frames / 662 choices**다.
Claude 최종 판정은 범위 한정 **PASS / REQUIRED_FIXES 없음**, 독립 R2 검산 PASS와
의도 변조20건 검출이다. R2가 최종 기준이며 R1의 flood 검산 누락/도구 수정 이력은 보존한다.
source·fixture·helper·저장 기록의 계약 일치이며 일반 효과성/사용자 수용/native g 최적성
독립 증명은 아니다. 전체 native 후보/proof/world counts가 저장됐다고 주장하지 않는다.

| index | LC0 / LC1 | 각 입력·O/F/C | LC0 Model C µs | LC1 Model C µs | LC0 거리 | LC1 거리 |
|---|---|---|---:|---:|---:|---:|
| 8191 | WON / WON | 195 · 76/50/69 | 34822276 | 34707214 | 476.07710546661247 | 474.447861778886 |
| 97 | WON / WON | 136 · 64/30/42 | 24118721 | 24118721 | 300.7441703767382 | 300.7441703767382 |

차이는 LC1−LC0다.8191은 **−115062µs / −1.6292436877264436칸**,97은0이다.
8191 예외는 input_0=145(146번째 입력)에서 O(23,0)1회다. 그 직전145 actions/146 frames가
같고 native g/b도 같다. LC0의 F(25,12)→C(24,12) 대신 LC1은 OPEN부터 실행했다.
frame153에서 observation/cursor/M/명시·자동 flags/status가 재합류하며 누적 비용은 다르다.
97은 예외0이며 저장 actions/frames 전체가 같다. 같은 input번호를 일반적인 동기화로 읽지 않는다.

8191은 **설계 출처(in-sample) 보드**다. 이 자연 궤적에서의 재현과97 무변화를 일반 개선/
승률 증거로 확대하지 않는다. 실제 run wall(observer 포함)은8191 LC0 3.2554542초 대
LC1 5.3417767초,97은2.0768061초 대2.6219825초로 LC1이 더 길었다. Model C 절감은
실제 solver 속도 개선이 아니다.110%도 전체 게임 보장이 아니며 결과에 맞춰 튜닝하지 않았다.

## 5. viewer와 개발 확인/사용자 확인의 구분

외부 viewer는 K_LC1_PILOT_RECOVERY_TRACE_V1 / K_LC1_PUBLIC_SELECTION_RECORD_V1의 원
662/666/662를 immutable하게 보존한다. 최종 focused **23 unique / 2 invocations / 46 method
실행 / 최종23 PASS**이며 원 source41/161이나 pilot을 재실행한 것이 아니다.

offscreen 검사와 실제 native 개발 기록, 위 사용자 경로 확인을 구분한다.

- native R1은 Windows 렌더를 확인했으나 작은 창이900×814였다.
- viewer layout 제약 조정 후 native probe R2는 비동기 restore 직후 크기를 너무 일찍 판정해
  exit1, 부분 이미지3개를 남겼다. source/probe/실패 이력은 보존했다.
- R3는 restore 이벤트 후 resize하여1920×1080·96DPI/100% 최대화와900×760의 실제 Windows
  Qt QWidget.grab 렌더4장을 확인했다. 자기 창/timer를 정리했고 solver/worker는0회다.
- Computer Use는 kernel assets 초기화 오류가 reset 재시도에도 반복돼 실제 click/key/drag
  gesture는 **미확인**이다. 이를 사용자 모두 PASS로 바꾸지 않는다.

현재 LC0/LC1 확인 도구는 아래 **저장 재생 전용** viewer다. 외부 viewer는 이번 Git 대상이 아니다.
기존 `experiments.k_lc0_exhibition`은 actual K-P0/K-LC0 앱 그대로이며 LC1 선택 실행 미통합이다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:GIT_OPTIONAL_LOCKS='0'
$env:QT_QPA_PLATFORM='windows'
& 'C:\venvs\minesweeper\Scripts\python.exe' -B 'C:\Projects\GraduationProject\K_LC1_USER_PATH_REVIEW_2026-11-02\codex_20261102_01\review_viewer.py'
```

기본8191/최대화이며 `--small` 또는 `--index 97`을 붙일 수 있다.
8191 대표 지점 완료145/145로 seek해 g/b/최종을 보고 **145→153 구간 보기**를 누르면8개
저장 입력을 각 속도로 재생하고153에서 멈춘다.146/152도 따로 비교하고,97의 시작/마지막136을
확인할 수 있다. 공통 재생은 일반적인 위치/속도 동기화가 아니다. 완료 보드/M/FLAG/cost/route와
pending 선택 메모를 분리한다. 관람 ms/CPS·Model C 배율은 정책/인간 시간과 다르다.

새 reader는 저장 manifest/trace/review R2 identity를 검사하고 historical launch hash를 보존한다.
현재 docs/HEAD 전체와 과거 raw hash가 같아야 열린다는 조건은 없다. 이번 doc refresh에서
reader source 텍스트의 의존 경계만 확인했으며 source를 실행하지 않고 무효화를 추정하지 않았다.
옛 K-LC0 고정3보드 viewer의316파일 guard/문서5불일치는 역사적 별도 도구의 제한 그대로다.

## 6. 알려진 한계와 후속 후보

사용자 첫 사진의8191 완료138에서 실제 이탈 결정은 **input137**이다. 당시 safe pool은
인근 O(13,2)/O(14,3)을 알고 있었다. 각 OPEN L193056/R1보다 먼 F(23,3)→C(22,3)의
L491649/R3(칸당163883)가 유리했다. 해당 HIDDEN 성분의 productive remainder는
{(14,0),(14,1),(13,2),(14,3)}4개라 singleton이 아니며 가까운 OPEN도 g 대비 약17.8%
높아110% 범위 밖이다. 저장 진단에 SINGLETON/WITHIN_110 불충족이 남아 있다.

복귀 input152의 현재 safe pool은 {(13,2),(14,3)}, input153은 {(13,2)}다. 현재 safe pool을
수학적으로 모든 증명 가능한 안전 칸과 동일시하지 않는다. input170의 먼 O(2,14)는 당시
EXACT_SAFE pool 한 칸이었고, input178의 먼 이동 O(27,11)는 safe pool이 빈 EXACT_GUESS였다.
이 설명은 저장 choice/public 기록의 정적 확인이며 새 추론을 수행한 것이 아니다.

가까운 안전 칸 여러 개 묶음, 지역 연속성, 장래 복귀 비용은 후속 정책 설계 후보다.
두 OPEN의 단순 비용337947µs/2 산술만으로 전체 게임 개선을 증명할 수 없다. 이번에는 구현/
효과 검증하지 않았고 사용자는 알려진 한계를 남기고 넘어가기로 했다. 관람용 거리 연동 CPS는
재생만 바꾸며 선택 정책 비용 가중치 변경과 별개다. 둘 다 이번 범위에 추가하지 않았다.

## 7. 현재 Git 준비와 근거 위치

기존 K-LC0 20경로 commit/push는496fab0에서 완료됐다. 옛3e9f/precommit/NEXT를 재실행하지 않는다.
현재 정확한 commit 대상은 LC1 source4 + 기존문서5 + 이 closeout1 = **10경로**다.
외부 doc output의 COMMIT_PLAN은 각 raw bytes/SHA와 예상 staged blob bytes/SHA/OID를 구분한다.
fixture raw CRLF는574621bytes이며 core.autocrlf=true/attributes unspecified에서 예상 LF blob은
543035bytes, SHA256 `e7b8edda78dfebdec0dacf72a91217a03c4be367d149b2f03c7fd66c5cff8ff9`,
OID `6eb3e50b8d6a993f30868a9589ca6e16bcf9a780`다. worktree나 과거 raw 실행 identity를 바꾸지 않는다.

외부 evidence roots(원 보고서·manifests·identity·실패 이력은 수정하지 않음):

- 구현: `C:\Projects\GraduationProject\K_LC1_SINGLETON_MIN_IMPLEMENTATION_2026-11-02\codex_20261102_01`
- 복구 pilot: `C:\Projects\GraduationProject\K_LC1_PILOT_RECOVERY_2026-11-02\codex_20261102_01`
- Claude: 위 pilot의 `review_claude/CLAUDE_K_LC1_REVIEW_KO.md`, `crosscheck.json`, `TRACE_VERIFY_R2.json`
- viewer: `C:\Projects\GraduationProject\K_LC1_USER_PATH_REVIEW_2026-11-02\codex_20261102_01`
- 이번 문서/Git 준비: `C:\Projects\GraduationProject\K_LC1_DOC_CLOSEOUT_2026-11-02\codex_20261102_01`

CURRENT NEXT는 사용자 문서 검수 → 정확한10경로 stage/검증/commit/push(사용자 실행)
→ 실제 새 SHA를 받아 postcommit recovery2개 갱신이다. Desktop 원본은 직접 바꾸지 않았고
외부 동명 교체용 사본만 작성했다. 스크립트는 AST parse로만 확인했으며 아직 실행하지 않았다.
main/HEAD/origin/변경집합/빈 staged diff/raw hash가 다르면 중단하며 자동 reset/unstage/force push는 없다.
현재 local origin/main 확인을 새 서버 조회나 push 완료로 쓰지 않는다.

## 8. 유지하는 상태와 STOP

이후 Main/Live 최소 selector, 거리 연동 관람 속도, 추가 지역 평가 등은 사용자가 다음 unit을
고른다. Main/Live selector·새 package/EXE·Stage4는 아직 미진행/미수용이다.
D0–D5 **FINAL ACCEPTANCE PASS / CLOSED**, **PHASE1_INCONCLUSIVE_TRANSFER**, effectiveness
**NOT ESTABLISHED**, Production K/Gate P 미승인, Extended **ACTIVE**·전체 종료 미결정을 유지한다.
ZiNi holdout2,010,000..2,010,099와 공식/formal evidence는 생성·열람·재실행하지 않았다.
이번에는 source/tests/fixture/viewer를 보존하고 문서·recovery 사본·Git 준비만 완료했다.
사용자 문서 검수와 Git 실행 직전에서 STOP한다.
