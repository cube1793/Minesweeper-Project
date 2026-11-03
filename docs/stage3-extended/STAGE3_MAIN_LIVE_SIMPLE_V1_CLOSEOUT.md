# Main/Live Simple·V1 Auto / 수동 재인수·FLAG 정리·UI closeout

> **2026-11-03 역사 checkpoint.** 당시 수용·실패·검증을 보존한다. 2026-11-04 현재 계약은 [K 인수·Simple 준비·Replay UI closeout](STAGE3_MAIN_LIVE_K_ADOPTION_UI_CLOSEOUT.md)을 따른다. K 현재 판 인수/FLAG 준비는 이제 지원되며, Simple 수동 입력도 Auto/guess를 끄고, 추천·계산 종료 버튼은 제거했다. 아래 K disabled·Simple 혼합 자동 계속·버튼 설명은 당시 동작이다.

기준일: **2026-11-03 (Asia/Seoul)**. 현재 source의 Main/Live 기능·UI는 **사용자 native 수용**으로 정리한다. 이번 작업은 문서·recovery 교체본·Git 절차 준비뿐이며 새 테스트/앱/worker/solver/pilot/build를 실행하지 않았다. stage/commit/push도 아직 하지 않았다.

## 사용자 수용과 남는 경계

사용자는 기존 수동↔V1·FLAG 정리·native 화면에 대해 **“전부 정상이긴한데 몇 가지 개선점”**이라고 확인하고 네 UI 개선을 요청했다. F 구현 뒤 새 Main 창에서 Simple/V1 hold, 설명과 보드 위치, 버튼/tooltip, 이름을 확인하도록 안내받은 다음 **“모두 정상인 것 같아.”**라고 최신 UI를 확인했다. 이 발언과 수용 범위는 이번 사용자 지시가 제공한 기록이다(메시지 raw export/hash나 추가 자동 native 실행으로 주장하지 않는다).

수용은 해당 환경의 Main/Live 기능·UI에 한정된다. 다른 OS/DPI, package/EXE, 전체 테스트, 모든 승패/추측 branch, 별도 Human 물리 모델 연구·Model C 재보정·알고리즘 효과성·Production K 승인으로 확대하지 않는다. 과거 보고서의 미실시/PENDING/FAIL/Claude 판정은 작성 시점 그대로 보존한다. 독립 F02는 **NOT_VERIFIED**이고 과거 Qt 공용 설정 보존은 **FAIL**이다.

## 당시 기능과 사용 순서

Main은 `main.py`로 실행하는 실제 Live 보드다. Simple을 유지하면서 공개 상태를 실제 frozen Stage3 V1에 전달해 첫 입력 하나씩 실행한다. 저장 trace viewer나 전체 runner 완료 결과의 재생이 아니다. K-P0/LC0/LC1 선택 실행은 계속 disabled·미지원이다. 지원 V1 preset은 Beginner9×9/10, Intermediate16×16/40, Expert30×16/99이며 custom은 미지원이다.

```powershell
Set-Location -LiteralPath 'C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:GIT_OPTIONAL_LOCKS='0'
$env:QT_QPA_PLATFORM='windows'
& 'C:\venvs\minesweeper\Scripts\python.exe' -B .\main.py
```

위는 사용 안내이며 이번 문서 작업에서 실행하지 않았다. 난이도와 Auto 알고리즘을 선택하고, 필요하면 **선택 정책으로 새 게임**을 누른다. 새 판은 바로 수동으로 플레이할 수 있다. **현재 상태 분석**은 추천/정리 필요 표시만 한다. 자동 진행을 명시적으로 켜면 선택 정책이 실행되며, guess OFF에서 추측은 대기한다. V1은 보드 클릭으로 수동 전환하고 다시 Auto를 켜서 현재 판을 재인수할 수 있다. Auto OFF는 잠시 멈추기, **추천·계산 종료**는 보관된 추천 폐기/계산 종료다.

새 판은 수동 가능·Auto OFF·guess OFF이며 정책 선택만으로 실행하지 않는다. Simple의 수동/Auto 혼합은 유지하고, V1은 첫 유효 board press에서 Auto를 끄고 원래 gesture를 이어간다. 실제 수동 입력 뒤 다음 V1 segment는 guess OFF이며, 이전 owner의 exit/reap/tree0/cleanup 뒤 같은 판의 현재 상태를 새 ADOPT owner로 인수한다.

V1 Auto OFF는 owner·유효 pending을 보관하는 일시정지다. **추천·계산 종료**는 pending을 버리고 worker를 종료한다(Simple에서는 비활성). 일시정지/간격/guess 변경만으로 유효 계획·FLAG 검토를 다시 계산하지 않는다. 정책 변경은 Auto OFF와 옛 owner retire 뒤 다음 명시 ON에 적용하며 보드·기록은 보존한다.

## FLAG 검토와 실행 계약

수동 중에는 깃발을 바꾸지 않는다. 새 V1 인수 때 현재 물리 FLAG **전부**를 HIDDEN으로 보는 detached 검증 view를 만든다. 실제 engine/화면/Replay는 view 생성만으로 변하지 않는다. 공개 숫자와 총 지뢰수만 쓰며 대상 FLAG나 다른 미검증 FLAG를 지뢰로 가정하지 않는다. hidden layout/adjacent truth, active/wasted FLAG 차이, 자동 FLAG라는 출처는 인증 근거가 아니다.

`live_flag_review.review_flags`의 범위는 `LOCAL_DIRECT_WITH_TOTAL_V1`: 기존 `build_constraints`/`infer_deterministic`의 **직접 zero/all + 전체수 zero/all**뿐이다. 전파·subset 확장·exact 열거·확률 반올림을 추가하지 않았다. 일반 local-first 경로는 지역 확정 수가 있으면 exact를 생략하며, 검토기는 이보다 보수적이다. 전체 만족가능성·모든 모순·최대 증명력은 보장하지 않는다.

- **PROVED_MINE**은 유지한다.
- **PROVED_SAFE / UNVERIFIED**는 준비 입력 `FLAG_REVIEW`에서 `engine.step(Action.FLAG)` 토글로 해제하고 닫아 둔다. 행 우선 `(y,x)` 순서다.
- **UNVERIFIED는 틀린 깃발·안전·50:50 판정이 아니다.** 실제 지뢰이거나 더 강한 추론으로 증명 가능한 지뢰도 해제될 수 있다. 해제는 OPEN/추측이 아니며 이후 V1 guess는 허용 설정을 따른다.

분할은 원 FLAG 집합과 공개 view identity에 결속된다. 탐지한 모순·분류 실패·timeout은 오류로 중단하며 전부 미검증으로 바꿔 성공 처리하지 않는다. 무거운 추론은 public-only worker에서 한다. 동일 owner의 제거 prefix와 공개 view가 같은 동안만 재사용하고 수동/run/generation 변경 시 폐기한다. 분석-only는 해제/실제 입력이나 HUMAN 변경이 없고, 검토 전 물리 FLAG를 신뢰한 V1 확정/확률을 표시하지 않는다.

준비 입력과 frozen V1 결정은 분리된다. 준비 ACK는 해당 FLAG 한 칸만 HIDDEN, 나머지 관측 불변을 요구한다. 일반 OPEN/FLAG/CHORD validator와 PLAYING HIDDEN 감소는 유지한다. 정리 뒤 **실제 현재 observation**으로 frozen `plan_position`을 결정당1회 호출하고 첫 입력1개, 실제 ACK 뒤 replan한다. 취소된 준비 입력 재사용이나 이미 해제한 FLAG 복원은 하지 않는다.

`CANONICAL_NEW`는 pristine provenance·placement 전·all-HIDDEN·revision0·cursor(0,0)·owner seq0에서만 OPEN(0,0) 특례다. 수동 FLAG→UNFLAG로 all-HIDDEN이 되어도 `ADOPT_CURRENT` seq0이다. owner input_seq와 게임 전체 input_revision/Replay event index를 분리하고, 수동/Auto/wasted 실제 입력은 revision과 마지막 입력 cell cursor에 반영한다. hover/pixel pointer나 press만 한 위치를 cursor로 쓰지 않는다.

## 소유권·상한·기록

UI는 snapshot·run/generation/revision/policy/phase/seq/token을 최종 비교한 뒤 token을 소비하고 실제 step→Replay event→status-first ACK로 이어간다. 비교/소비/step 사이 modal/await/processEvents를 넣지 않는다. timer 예약 nonce와 captured identity로 old callback이 새 pending을 실행하지 못하게 한다. 수동 입력은 옛 proposal의 ACK가 아니다.

원래 press 전이와 실제 target을 확인한 뒤 hold 처리 전에 retire한다. `_invalidate_mouse_input`이나 synthetic click 재전송으로 첫 gesture를 잃지 않는다. LEFT release/RIGHT press/double click/BOTH 양순서/drag/outside·stale release와 RIGHT-first의 정당한 FLAG+CHORD를 유지한다. 정리 중 수동은 가능하지만 held gesture 또는 cleanup 미완료 상태에서 새 owner/명시적 분석·예약은 시작하지 않는다. cleanup 실패 소유권은 reset이나 새 job으로 우회하지 않는다. 불확실 입력/기록/ACK 뒤 자동 재시도는 없다.

| 경계 | 현재 계약 |
|---|---|
| board/overlay | 최대480 cells |
| 준비 phase | 입력≤초기FLAG수, 남은 제거 대상 엄격 감소 |
| 일반 V1 phase | 최대480 입력, 매 PLAYING ACK HIDDEN 감소 |
| owner 전체 | ≤480+초기FLAG수≤960 |
| wire | 명시 v2, sequence≤1921, message≤2MiB; type/bool/길이/순서/중복/token 엄격 검사 |
| 게임 전체 revision/event | 480 상한 적용하지 않음 |
| lifecycle | compute30초 / ACK5초 / 유효 FINISHED 뒤 exit-reap5초 / reap 뒤 고정 drain0.75초 |

P1은 reap 직후 원 ACK deadline 안에서 추가 strict read를 한다. **그 추가 read 한 번과 drain 중 일반 poll read는 별개**다. 이를 전체 lifecycle에서 읽기 총1회라고 쓰지 않는다. timeout/cancel/failure 뒤 성공 부활이나 cap/drain 연장은 없다. P2 종료 지연 표시는 첫 실패의 `FINISH_EXIT_TIMEOUT:` prefix로 구분한다.

첫 실제 자동 준비 UNFLAG도 `SOURCE_ALGORITHM`이다. 이후 수동을 반복해도 mixed game은 HUMAN/순수 V1 완주 근거가 아니다. 새 판은 SOURCE_HUMAN이다. 기존 Replay schema/codec/recorder로 실제 FLAG 토글 event를 기록하고, 과거 Replay나 schema에 없는 policy identity를 만들지 않는다. 정상 WIN 자동 flags는 실제 입력 수가 아니다.

준비 UNFLAG·일반 V1·전체 Auto 입력과 Model C 합계를 따로 기록한다. UNFLAG에도 마지막 실제 cell→target의 frozen 물리 FLAG 비용을 부과한다. 수동 구간·검토 compute wall·관람 간격은 Model C에서 제외한다. 재인수 cursor는 마지막 실제 수동 입력 cell이다. Main 속도는 기존 **ms 관람 간격**이며 Main Model C/CPS/거리 가변 속도 모드는 아직 없다.

## UI와 모듈 경계

hold만으로 분석/Auto의 enabled 외관을 깜박이게 하지 않되, 명시적 활성화의 실행 guard와 persistent blocked 조건을 유지한다. Simple은 실제 RIGHT 입력 후 hold 중 내부 재분석을 유지하고 완성된 release에서 예약한다. V1은 원래 클릭 인계/cleanup 뒤 재인수를 유지한다.

정책1줄·분석2줄의 상태 영역은 font metrics/여백과 font/DPI 변경에 맞춰 높이를 확보한다. 긴 문구는 핵심 오류·미검증 해제/실제 지뢰 가능성·추측 대기를 요약하고 전체 설명은 tooltip/접근성에 남긴다. 화면 이름은 **Stage3 V1**이며 `POLICY_V1`/`STAGE3_V1`·run identity·frozen core·Model C를 바꾸지 않는다.

- V1 Auto tooltip: “체크를 끄면 일시정지하며 현재 추천을 보관합니다. 보드를 클릭하면 수동으로 전환합니다.”
- 종료 tooltip: “보관된 추천을 버리고 계산을 종료합니다. 다시 Auto를 켜면 현재 보드에서 새로 계산합니다.”
- Simple은 기존 수동/Auto 혼합에 맞는 별도 안내를 사용한다.

```text
main.py → ui_manager.py → engine.step + 기존 Replay recorder
                  ├─ Simple 분석 → simple_decision → live_analysis 표시
                  └─ LivePolicyJob ↔ strict transport v2 ↔ live_policy_worker
                         public DTO / live_policy
                         ├─ live_flag_review (준비 검토)
                         └─ frozen stage3_planner / stage3_runner validator
```

Main Live와 별도 same-board 전시/저장 viewer는 경로와 수용을 구분한다. `experiments.k_lc0_exhibition`은 actual K-P0/K-LC0 전시이고 LC1 저장 viewer는8191/97의 저장 trace를 읽는다. Main에 K/LC 실행이 연결됐다는 뜻이 아니다.

## 버전별 근거 — 검사 수는 합산하지 않음

아래 A–F는 모두 `C:\Projects\GraduationProject` 아래 외부 root다. 각 manifest의 raw SHA는 당시 source/test 목록의 identity를 결속한다. 미래 commit SHA로 과거 실행 bytes를 대체하지 않는다.

| 근거/실행자 | 파일 버전·검증 범위 | 운영/native 범위·한계 |
|---|---|---|
| A Codex / Claude | initial267 unique, 누적521 methods/8 invocations. Claude267 재검토 PASS. 초기 Codex test 실행 hash 기록은 runtime 중심이어서 test bytes 근거 한계가 있고 Claude가 별도 결속 | 실제 Expert2착수. 첫237입력(OPEN39/FLAG98/CHORD100) 완주, 두 번째1입력 후 pause/takeover. 첫 완주 후 transport hardening만 변경; 최종 transport로 Expert 재완주0. 현재 D/F 버전의 완주로 소급하지 않음 |
| B Codex / Claude | 288 unique 근거 합성(223+65), 누적353; 최초 fixture6 subtest 실패 보존. Claude 두 모듈108 PASS, 나머지180은 Codex 기록 | ACK5와 유효 FINISHED 후 exit5 분리, 새 판 guess OFF·legacy ai 표시. 새 public/Expert0. 당시 fresh-only 재참가 제한은 이후 D가 변경 |
| C Codex | 읽기 전용 조건부 설계 GO, 실행0. owner/entry/클릭 설계 참고 | ‘모든 FLAG를 지뢰로 가정’ 권고 및 owner480 설명은 사용자 결정과 D의 FLAG-free 준비 phase/960 상한으로 대체됨 |
| D Codex | 최종380=F01 110+F02 6+F06 264 합성, 누적1167/역사 method실패1. 단일380 일괄 PASS 아님. 실제 synthetic worker6/시험 자손3 | 최초 Beginner1착수, 완료case0/V1 owner0/ZiNi 생성0. Windows command 문자열 helper 오류로 보조 launch1 차단, 운영 미완료 |
| E Codex | source/tests17은 D 그대로. helper 검사8 unique, 실행16. 기능 운영 도달 범위80 assertion PASS 중6개 중복 | 새 Beginner2 case, 실제 V1 owner3/ZiNi2. 공개7상태·Replay6event·Auto3(준비 UNFLAG1/일반 FLAG2)·수동3. Model C445066µs=126005+319061. 일반 Auto OPEN/CHORD·guess ON·WON/LOST·terminal-only Replay NOT_REACHED |
| E Claude | source 적합성 PASS/제품 REQUIRED_FIX 없음. F01 110+F06 264=374 PASS. 독립 proof5689상태/15957FLAG/위반0 | 저장 trace/비용 검산은 재관측 아님. F02 runner 문자열 오류6시도/생성0. 실제 Windows lifecycle 독립 검증 미완료 |
| E Claude F02 보충 | 첫1 method ERROR(CreateProcess gate 오류), 나머지5미실행, 생성0 | Claude F02 역사7 method실행/실제생성0. 독립 F02 NOT_VERIFIED; D의 Codex 실제6개 PASS와 구분. 원인 가설을 CPython 확정 결함으로 바꾸지 않음 |
| F Codex | 최종35=R03 34+R04 DPI1, 최종 runtime/test 동일 bytes; 누적102 method/186 subtest. R03 실행 plan/helper 사본과 이후 변경된 final helper/plan을 구분 | geometry42는 fixture SetNoConstraint/fixed-size1086×766/820×620. font9/15/21pt, paint-device96/144/192DPI는 실제 다른 OS/DPI 수용 아님. 실제worker/public pilot0 |
| 사용자2026-11-03 | D/E 계열 기능 정상 확인 후 F의 최신 UI에 “모두 정상인 것 같아.” | 해당 실제 환경의 기능/UI native 수용. 자동 전체 branch/모든 OS·DPI/package나 알고리즘 효과성 수용 아님 |

E의 V1 owner 3개는 각 reaped/tree0/cleanup receipt가 있고 root launcher5(V1 3+ZiNi2)와 관측 자손8의 종료가 기록돼 있다. 이는 저장 운영 근거이며 이번에 재실행하지 않았다. 이전 D Beginner1과 E Beginner2는 역사 누계3이며 별도 A Expert와 합쳐 ‘현재 최종판 검증 수’로 쓰지 않는다.

Coordinator는 독립 F02 추가 재실행을 새 의무 gate로 두지 않고 한계 공개와 native 수용으로 마무리하도록 권고했다(이번 사용자 지시에 제공된 조정 기록). 새 검증을 수행했다고 주장하지 않는다.

## 남은 실패·optional과 재사용 금지

E의 Qt 공용 `QtProject/OrganizationDefaults/FileDialog` 설정 보존 **FAIL**을 유지한다. 정확한 이전 값은 없고 복원 판정도 없다. 이후 값/last-write 차이의 주체·원인은 미확인이다. 사용자가 정상 native 대화상자를 열어 history가 변하는 동작과 자동화의 보존 계약 실패는 구분한다. 이번에는 레지스트리/설정에 접근해 수정하거나 복원을 시도하지 않았다.

**E의 실제 대화상자 운영 helper는 R1 수정 전 재사용 금지**다. 이번에 수정/재실행하지 않았다. 미래 자동화는 실제 대화상자를 피하거나 정확한 격리 계약을 먼저 정해야 한다. 과거 snapshot 없이 원상복구를 추정하지 않는다.

offscreen PNG의 글자/숫자/FLAG glyph 누락은 남는다. 사용자 native 수용은 현재 실제 환경의 근거일 뿐 과거 PNG 정상화나 범용 DPI 검증이 아니다. optional O1(blocked→cancelling 표시), O2(P1 추가 read와 일반 drain poll), O3(옛 F06 plan counts262/74 vs 실제264/76, assertion80 중6중복)는 원 기록으로 남긴다. bytecode148/149 차이는 명명 cache 범위 차이였다. UI polish를 이 job optional의 수정으로 확대하지 않는다.

## 현재 raw source identity

현재 main/HEAD=local origin/main=`d1201e481da7199a46b4ab80eaf5c303e77db10a`, ahead/behind0/0, staged0. source/tests18 + 문서6 = **미커밋24경로(M13/U11)**이며 clean/commit/push 완료가 아니다. 기존 LC1의10경로 Git은 d1201e4에서 이미 완료됐다. 이번 새 Git 대상은 아래 현재18개와 문서6개뿐이다.

| source/test 경로 | raw bytes | SHA256 |
|---|---:|---|
| `live_analysis.py` | 7417 | `bfcc50aa552c51097ef65f1b83957766291eab35def3eb30f0cc42715fb157c9` |
| `live_flag_review.py` | 10874 | `ea62a228409aa0c13f8108ecb730cc24db44d834ab94a3150fbd105cda9557a9` |
| `live_policy.py` | 27693 | `36a85e095ef1338f746bd43d466b236c98e94c7e32d053838e3bca7fc1e1832a` |
| `live_policy_job.py` | 22493 | `adfa3f6c2f3dd0992ff306dba7a61cda02ac43d09f0cc1c531b59999b71145a3` |
| `live_policy_transport.py` | 4857 | `b180b6c9d6ee5893af62e899083550512db4786f3c689dce695bebbce183c419` |
| `live_policy_worker.py` | 3979 | `4d0d4668ee987f159655addabfe450ed3581fb66a18d44235367a7c56191b4f7` |
| `main.py` | 1776 | `c962f61c58937999df0fcd1bf346359429667221a8e1689ffdddb6508571be0e` |
| `tests/fixtures/live_policy_worker.py` | 1623 | `4dcddf5c1751c9cb26adbf45ecf47003a0ce3b5b683c8597d5038ce1386a11c1` |
| `tests/test_live_analysis.py` | 34409 | `588c89403cb3b6bbec5809ad31b8482575b0b01ec2632e948c9cf9597020734e` |
| `tests/test_live_auto.py` | 92129 | `54c8a8265c10d19c8efee6cd1e693e6d821348e6888a67181633dc14f52dd980` |
| `tests/test_live_flag_review.py` | 14328 | `cdc67a12444fb7618097aadf9ba352a3c6d3fe6213ff71901b1526991bb2f97d` |
| `tests/test_live_policy.py` | 35109 | `251be609e7aa08f7b1de5073d84f065084d3fcb830947daa79eaf83a57c47a70` |
| `tests/test_live_policy_job.py` | 42079 | `77a5d21149e1edf5a5a56eeafe46105fecb9b6a5a0e2b436421d3e43897a4b2a` |
| `tests/test_mouse_trace_ui.py` | 81282 | `3afb11e9faa7c317163da915f9777048e67eaf6bab8278744bb576bb59f757b0` |
| `tests/test_same_board_main_ui.py` | 24893 | `468ac02931cc56d6ad3456bcccc01aa5b035c6e6bff33f5787433b4a2d789e68` |
| `tests/test_ui_mouse_input.py` | 71316 | `5f3bebf9e502372104b387f3f13c3b9fbb9b7ad7d791ddff045e6147e7e83027` |
| `ui_manager.py` | 172143 | `ed63f459a39ee48f7e1533d5aff9989b01e6fa0d07a73c008ff02106abc22473` |
| `tests/test_live_presentation.py` | 18135 | `9ab6e9976533203eb8c956fb9474314e2f4789ca23a0491c5933f9b8486bb5ec` |

## 외부 근거 위치와 manifest identity

- **A**: `C:\Projects\GraduationProject\MAIN_LIVE_SIMPLE_V1_IMPLEMENTATION_2026-11-02\codex_20261102_01` — `REPORT_KO.md`; `SOURCE_MANIFEST_FINAL.json` SHA256 `e07df0f89e07c5fb69e6c44f47826a7701d4c669a389de8b5758b9b6f552867b`.
- **B**: `C:\Projects\GraduationProject\MAIN_LIVE_SIMPLE_V1_FINISH_POLISH_2026-11-02\codex_20261102_01` — `REPORT_KO.md`; `SOURCE_MANIFEST_FINAL.json` SHA256 `88e16e3a4805c23984616c2640e5864e08b4cfb860119a8af90381ffbe62c0cb`.
- **C**: `C:\Projects\GraduationProject\MAIN_LIVE_MANUAL_AUTO_HANDOFF_DESIGN_AUDIT_2026-11-02\codex_20261102_01` — `REPORT_KO.md`; `INPUT_MANIFEST.json` SHA256 `39a6fbe18357193e7243d5c071626be2007ec22fd586642b120ebfa776d4365a`.
- **D**: `C:\Projects\GraduationProject\MAIN_LIVE_MANUAL_AUTO_HANDOFF_V1_2026-11-03\codex_20261103_02` — `REPORT_KO.md`; `SOURCE_MANIFEST_FINAL.json` SHA256 `3dbaa32d09112fa89d64ad824ea123225b0c494b2b9c0e06210bbb795b442158`.
- **E**: `C:\Projects\GraduationProject\MAIN_LIVE_MANUAL_AUTO_HANDOFF_V1_OPERATIONS_RECOVERY_2026-11-03\codex_20261103_01` — `REPORT_KO.md`; `SOURCE_MANIFEST_FINAL.json` SHA256 `fe86cf1525cbdeb3726eeca8682403977a10b8a6b4c9fb9d8e2e7852c4e7c65b`.
- **F**: `C:\Projects\GraduationProject\MAIN_LIVE_UI_POLISH_V1_2026-11-03\codex_20261103_01` — `REPORT_KO.md`; `SOURCE_MANIFEST_FINAL.json` SHA256 `38149ae69118ba0f80b6c4ff27980c012318742b441847fc2bdb40eb58b89b26`.

A/B/E의 `review_claude` 보고서·manifest와 E의 `review_claude_f02_supplement_01/F02_SUPPLEMENT_REVIEW_KO.md`를 별도 판정으로 읽는다. F REPORT SHA256 `79de155389dff72f667eba18802f3d331c7a8d829796bf8a968e3d466e7db0e1`, OUTPUT_MANIFEST SHA256 `f94d489d5babd409d9b361fba1901110c96afd1f94c06c5601fe41c203984d35`다. 이번 외부 `EVIDENCE_IDENTITY.json`은 보고서/manifest의 명명 hash를 결속한다.

## 문서·Git·recovery NEXT

문서6개는 README.md, ARCHITECTURE.md, docs/CURRENT_HANDOFF.md, docs/README.md, docs/stage3-extended/README.md와 이 신규 closeout이다. 외부 output: `C:\Projects\GraduationProject\MAIN_LIVE_SIMPLE_V1_DOC_CLOSEOUT_2026-11-03\codex_20261103_02`.

**NEXT: 문서/COMMIT_PLAN 검수 → 사용자의 stage·commit·push → 실제 새 SHA로 외부 postcommit recovery2개 갱신 → K 연결 첫 단위 준비.** 이번 USER_GIT_STEPS.ps1은 실행하지 않았다. raw 실행 hash와 core.autocrlf/attributes가 정규화한 예상 index blob을 구분한다. 외부 output/helper/recovery/이미지/results는24경로에 포함하지 않는다.

Desktop 원본2개는 읽기만 했고, 같은 basename의 외부 교체용2개는2026-11-03 내용의 **precommit** 사본이다. 사용자 Git 후 실제 SHA로 postcommit 사본을 작성한 다음 사용자가 Desktop을 교체한다. 현재 clean/새 SHA/push 완료를 만들지 않는다.

K의 지속 세션/M/FLAG/ACK·재인수 계약은 V1과 별도이며 이번에 범위를 확정하거나 구현하지 않는다. Main Model C/CPS/거리 가변 속도, package 검증, 후속 알고리즘 연구·Stage4는 남은 별도 작업이다. 대규모 영상 분석/재평가를 새 필수 선행 gate로 만들지 않는다.

D0–D5 **FINAL ACCEPTANCE PASS / CLOSED**, **PHASE1_INCONCLUSIVE_TRANSFER**, effectiveness **NOT ESTABLISHED**, Production K/Gate P **미승인**, Stage3 V1 core **CLOSED/FROZEN**, Extended **ACTIVE** 유지. holdout2,010,000..2,010,099와 공식 evidence는 열거나 실행하지 않았다. 사용자 검수와 Git 실행 전에 **STOP**한다.
