# Main/Live K 현재 판 인수·Simple 준비·Replay UI closeout

> **7f15355까지 완료된 이전 checkpoint.** 여기의 wirev7·source107·미커밋32경로·LC0후속은 당시 상태다. 2026-11-04 현재 LC0 연결·wirev8·source111의 독립 검토/사용자 수용과 최신 NEXT는 [Main/Live LC0 closeout](STAGE3_MAIN_LIVE_K_LC0_CLOSEOUT.md)을 따른다. 원 검증·실패 기록을 소급 변경하지 않는다.

기준일: **2026-11-04 (Asia/Seoul)**. 상태: **범위 한정 독립 검토 완료, 필수 수정 0, 사용자 native 수용 / 문서 마감·사용자 commit·push 준비**.

이 문서는 a992892의 K 확정색 이후 누적된 현재 판 인수, 기존 FLAG 준비, ACK 중 수동 인계, Simple 준비, Replay UI와 단축키 보완의 최종 상태다. [이전 K-P0 closeout](STAGE3_MAIN_LIVE_K_P0_CLOSEOUT.md)과 [Simple/V1 closeout](STAGE3_MAIN_LIVE_SIMPLE_V1_CLOSEOUT.md)은 당시 bytes·수용·실패 이력을 보존하는 역사 문서다. 현재 계약은 이 문서와 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md)를 우선한다.

## 1. 사용자 수용과 정확한 범위

사용자는 앞선 주요 확인 요구가 충족됐다고 보고한 뒤 정책 선택 줄, Replay 알고리즘 사용 기록과 Space 동작을 추가 요청했다. 최초 UI 독립 검토에서 발견된 R1과 O1/O2/O3 보완 후, 최종 native 안내의 다섯 항목에 **“드디어! 전부 통과야.”**라고 확인했다.

최종 안내는 정책 줄 배치, 마우스로 정책 선택 후 Space/Return/Enter, 편집 위젯의 입력 보존, Replay 사용 기록·Space·Enter 동작, 정상 종료다. 이 수용은 현재 사용자 환경과 보고한 경로에 한정한다. 과거 체크리스트 전체를 최종 bytes에서 모두 다시 실행했다거나, 정확한 배율·preset별 완주 수·모든 OS/DPI·전체 suite가 확인됐다고 추정하지 않는다. 종료 실패 안내의 O3는 독립 offscreen fake 예외 검증이며 실제 worker 종료 실패를 새로 만들지 않았다.

알고리즘 이름의 **K-P0 (실험적)** 표시는 이번에 유지한다. 기능 수용은 Production K/Gate P 승인이 아니다. 나중에 라벨만 변경한다면 그 변경과 관련된 좁은 UI 확인으로 검토 범위를 정하며, 이름 변경 자체를 전체 worker 재검증 사유로 삼지 않는다.

## 2. 현재 사용자 동작

- 새 판은 수동 가능·Auto OFF·추측 허용 OFF다. 정책을 선택하기만 해서는 입력하지 않는다. 라벨·정책 선택·**선택 정책으로 새 게임** 버튼은 같은 줄 왼쪽에 인접한다.
- K-P0는 초급 9×9/10, 중급 16×16/40, 상급 30×16/99에서 새 판뿐 아니라 수동/Simple/V1로 진행한 현재 판을 인수하고, 정상 수동 인계 뒤 재인수한다. 기존 깃발을 사용자가 전부 해제할 필요는 없다. K/V1 custom과 Main LC0/LC1은 미지원이다.
- 기존 FLAG는 공개 정보로 확인한 지뢰만 유지하고, 나머지는 실제 FLAG 토글로 닫힌 칸으로 되돌린 뒤 진행한다. **미확인은 오답·안전 판정이 아니며 실제 지뢰의 깃발도 해제될 수 있다.** Simple/V1/K 안내에서 이 의미를 공유한다.
- Auto OFF는 유효 pending을 보관하는 일시정지다. 수동 입력은 Auto와 추측 허용을 끄고 원래 gesture를 처리한다. Simple도 수동 입력 뒤 자동으로 계속하지 않으며, 다시 Auto를 켜야 한다. 이는 사용자의 명시적 선택이다.
- **추천·계산 종료 버튼은 제거했다.** 일시정지는 Auto OFF, 수동 전환은 보드 입력을 사용한다. 정책 변경·새 게임·실패 뒤에는 추측 허용을 초기화한다.
- K 추측 숫자는 원 phase_e의 exact 확률, 초록은 원 selection_safe_cells의 HIDDEN 안전, 빨강은 preinput_m의 HIDDEN 논리 지뢰다. 확률 OFF는 숫자만 숨긴다. V1/K 가상 원형 커서는 표시 전용이며 승인 대기 때 실제 입력보다 먼저 도착할 수 있다.

## 3. K 세션·FLAG 준비·인계 계약

### 현재 판 인수

FLAG-free ADOPT는 현재 global revision·공개 판·실제 입력/Replay 이력·논리 cursor에 결속한 새 owner에서 빈 M으로 시작한다. 단순히 격자 모양만 같다고 입력 이력을 인정하지 않는다. 무분석 initial 입력은 canonical 새 판 경로에만 있다.

기존 FLAG 인수 정의는 `K_P0_PUBLIC_FLAG_ADOPT_LOCAL_BOOTSTRAP_V1`이며 현재 공통 wire는 **v7**다. 새 native KLocalSession이 모든 FLAG를 가린 detached 공개 관측에 `analyze_local`을 한 번 적용한다. 원 FLAG와 증명된 M의 교집합만 유지하고 나머지는 row-major로 해제한다. 같은 native session과 원 증명을 보관하며, V1 proof를 K M에 넣거나 외부에서 M을 주입하지 않는다. 가린 판의 graph로 실제 판 입력을 승인하지 않는다. 준비 후 실제 판에 대한 native 검증·정상 분석/선택으로 이어진다.

```text
공개 현재 판 + 실제 입력 이력 확인 → 새 K owner/session
→ 필요한 FLAG 확인·준비 입력(각 실제 입력 1회 / event 1회)
→ 정상 K pending 보관 → VALIDATE → ADMITTED
→ GUI 최종 비교 → token 소비 → 실제 입력 1회
→ 원 입력에 정확히 결속한 ACK → 다음 pending
```

최종 비교→token→step 사이에는 yield를 두지 않는다. 정상 K 입력 상한 480, FLAG 준비 상한 480, 합계 960이며 게임 전체 입력 revision을 480으로 제한하는 뜻은 아니다. pending당 VALIDATE 64, V1 seq 1921, 기존 K envelope 31681, FLAG 준비 포함 K envelope 63362, 메시지 2MiB와 compute/ACK/exit/drain 30/5/5/0.75초 경계를 유지한다.

### ACK 대기 중 수동 인계

첫 수동 press가 기존 예약·permit·표시 권한을 무효화하고 원래 gesture를 한 번 처리한다. 이미 발생한 K 입력은 불변 `_KInputReceipt`에 game·입력·Replay prefix·action을 결속한다. 원 ACK만 확인하고 새 수동 판의 M/cursor/revision을 과거 K 상태로 덮어쓰거나 NEXT를 보내지 않는다. 옛 owner의 종료·reap·tree0·private cleanup이 확인된 뒤에만 새 owner를 만든다.

정상 인계와 실제 실패를 구분한다. 누락·변조·중복 ACK, 실제 입력/Replay 이력 불일치나 정리 실패는 여전히 fail-closed다. 최초 원인을 보존하며 정책 왕복만으로 잠금을 풀지 않는다. 과거 사용자 사진의 원인을 확정한 것은 아니지만, ACK 대기 중 수동 입력이 정상 인계가 되는 새 경로를 검증했다.

## 4. Simple FLAG 준비와 비용

`live_simple_preparation.py`는 모든 FLAG를 가린 공개 관측의 직접 zero/all·전체 지뢰 수 조건으로 기존 FLAG를 확인한다. 증명된 지뢰만 유지하며 안전/미확인은 row-major로 해제한다. 기존 Simple planner와 확률 계산은 바꾸지 않았다. 준비 epoch는 game/generation/revision/cursor/grid/counter/입력·Replay 이력에 결속하고 수동 입력 시 무효화한다. 자기 준비·정상 Auto 입력은 예상 이력을 갱신한다.

실제 준비 입력은 실제 event와 non-human source 표시를 만든다. Model C의 기존 표 안 이동은 정확한 비용을 기록한다. **dx≥30 또는 dy≥16인 표 밖 이동은 null/OUTSIDE_FROZEN_TABLE**로 남기며 0으로 바꾸지 않는다. `preparation_unmodeled_inputs`가 있으면 합계는 그 입력을 제외한 부분 합계다. Simple의 큰 custom 보드를 위해 frozen 표를 확장하거나 재보정하지 않았다.

Simple이 완전 열거로 만든 지뢰 FLAG가 이후 수동 입력으로 새 epoch에 들어가 직접 증명되지 않으면 해제됐다가 다시 FLAG될 수 있다. 유한한 추가 입력/비용이라는 기존 OPTIONAL을 보존한다. 무한 순환이나 새 필수 수정으로 판정하지 않았다.

## 5. Replay 기록·단축키·종료 안내

Replay JSON의 기존 `source_type`을 유지한다. 첫 실제 Auto 입력(준비 UNFLAG 포함)부터 `algorithm`으로 기록하고 이후 수동 입력·정책 변경이 있어도 되돌리지 않는다. 분석 표시나 Auto ON만으로 기록을 바꾸지 않는다. 알고리즘 이름 목록·event별 출처 같은 새 schema는 추가하지 않았다.

| 저장값 | Replay 표시 의미 |
| --- | --- |
| `human` | 알고리즘 사용 기록 없음 |
| `algorithm`, `ai` | 알고리즘 사용 기록 있음 |
| 데이터 없음 | 확인 불가 |

기존 loader는 옛 JSON에서 필드가 생략되면 `human`으로 읽는다. 따라서 “기록 없음”이 실제 과거 자동 입력이 절대 없었다는 증명은 아니다. Main은 `ai`를 새로 생성하지 않으며 호환 입력값으로 인정한다. Replay의 참고 분석 정책은 사용 기록과 별개다.

Live Space/Return/Enter는 새 게임을 한 번 실행한다. 마우스로 고른 비편집 정책 콤보에 focus가 남아 있어도 동작한다. 편집 가능한 콤보·일반 입력칸·spinbox는 입력/값 확정을 유지하며 popup/modal·키 반복 방어를 유지한다. Replay Space는 기존 재생/일시정지를 한 번 수행하고 끝/빈 Replay를 자동으로 되감지 않는다. Replay Return/Enter와 직접 reset 경로는 새 게임이나 상태 변경을 만들지 않는다.

종료 정리에 실패하면 기존 잠금·소유권 경계를 유지한 채 한 줄 안내와 전체 원인 tooltip/접근성 설명을 표시한다. 새 게임·정책·Auto 관련 제어는 비활성화하고, 저장과 Replay 참고 분석은 허용된 기존 경로를 유지한다. 새로운 강제 종료/자동 복구/worker를 추가하지 않았다.

## 6. 버전별 검증 근거

모든 경로의 공통 root는 `C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs`다. 아래 숫자는 **각 버전의 선택된 검사**다. 합산해서 전체 suite 또는 최종 bytes 한 번의 전체 실행으로 쓰지 않는다.

| 단위 / output 폴더 | Codex | 독립 검토와 판정 |
| --- | --- | --- |
| K FLAG-free 인수 `MAIN_LIVE_K_ADOPT_UNIT1_2026-11-03` | 353 method / 481 subtest, 실제 5사례·6 owner | review_01 정적 검토만; review_02가 누락 실행 353/481·5/6와 AST/이력 probe 완료. 필수 0 |
| 기존 FLAG 인수 `MAIN_LIVE_K_FLAG_ADOPT_UNIT2_2026-11-04` | codex_02 413/677, 실제 6사례·7 owner | review_01 동일 선택 413/677·6/7, probe 49/49. 필수 0 |
| ACK 수동 인계·Simple 준비 `MAIN_LIVE_NATIVE_FEEDBACK_2026-11-04` | 최종 R04 443/731, 실제 6사례·7 owner | review_01 443/731·6/7, probe 45/45. 필수 0 |
| Replay UI 최초 `MAIN_LIVE_REPLAY_UI_POLISH_2026-11-04` codex_01 | 340/476, worker 0 | review_01 340/476 PASS지만 독립 probe에서 R1 발견. **이 버전 미수용** |
| Replay R1·O1/O2/O3 보완, 같은 폴더 codex_02 | 최종 R02 345/479, worker 0 | review_02 345/479, probe 4/4. R1·O1/O2/O3 CLOSED, 필수 0. O3 fake 예외 한정 |

실제 worker를 실행한 각 단위는 해당 실행의 소유 PID·reap·tree0·private cleanup을 기록했다. final UI 보완은 worker를 다시 실행하지 않았으며 이전 worker 결과를 새 실행으로 세지 않는다. 전체 suite·모든 preset 진행판·보편적 실마우스/DPI 검증은 아니다.

최종 source identity:

- `codex_02/SOURCE_MANIFEST_FINAL.json` = `R02_SOURCE.json`, 107파일, SHA256 **848cbdc1423479fa2f65b2da5c915b033b5af075b111bef78007c3cd2077e5b2**.
- `ui_manager.py` raw SHA256 **9036fa48d95c1983f57322a916397e8ce5ef5de6517936122b3ae6ea15ac36b0**.
- `tests/test_replay_ui_polish.py` raw SHA256 **bf16fb3cff497c420998c0f63895e0a6ed26c3bc2ff3f066d6030c420fd8e206**.
- 최종 Codex output manifest 403개(자기 자신 제외), SHA256 **68691ff58cbf1c1180d21e035383d2a21fb63669f4c71497b29067ba8bffe615**.
- 최종 Claude output manifest 39개(자기 자신 제외), SHA256 **917ff957a1dc6f4985e32aa0480c80b780e587de236f82e16f5c5500cef2b03a**.

최종 보고서는 [Codex 보완 보고서](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/MAIN_LIVE_REPLAY_UI_POLISH_2026-11-04/codex_02/REPORT_KO.md>), [Claude 보충 검토](<C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/MAIN_LIVE_REPLAY_UI_POLISH_2026-11-04/review_claude_02/CLAUDE_REPLAY_UI_SUPPLEMENT_KO.md>)다. 사용자 최종 안내는 `MAIN_LIVE_REPLAY_UI_FINAL_NATIVE_2026-11-04/coordinator_01/NATIVE_GUIDE_KO.txt`다. 작성 당시의 PENDING 파일을 소급 수정하지 않고 이 수용 기록으로 후속 상태를 나타낸다.

## 7. 실패·정정·선택 권고 보존

- FLAG-free 최초 Claude receipt의 H alias 충돌·CP949 경로 오류로 실행이 중단됐다. 후속 새 실행 보충에서 누락 검사를 완료했다. 보충 중 API 500은 명령이 실행되지 않는 통신 중단이었으며 이미 성공한 단계를 재실행하지 않았다.
- FLAG Unit2 codex_01 중단본은 미완료다. 원 미커밋 11경로/raw93 복원과 후보를 보존한 뒤 codex_02를 실제 구현 근거로 삼는다. 실패를 성공으로 덮어쓰지 않는다.
- 이후 Codex fixture·기대값·Qt 순서 실패와 helper 복구, Claude probe 오탐·정정 및 절차 이탈은 각 원장에 남긴다. Unit2의 미등록 version 명령/전역 TEMP 파일, Native Feedback 검토의 전역 TEMP/scratch 파일·봉합 오류도 보존한다. 기술 적합성을 전체 절차 무결점으로 쓰지 않는다.
- UI 최초 R1은 실제 정책 콤보 focus 결함이었다. 보완 후 통과는 새 bytes 판정이며 옛 R1 FAIL을 지우지 않는다. O2의 누락된 PNG 기록 블록도 보완 내역에 포함했고, Claude 최종 보고서의 20분→약 13분 정정 이력을 보존한다.
- Native Feedback의 이전 OPTIONAL(terminal receipt 거부 시 ACKED 표시, 유한 Simple 재FLAG, 종료 판 문구, 분석 OFF의 guess 해제, 긴 이력 성능 등)은 이번 범위에서 필수로 승격하지 않는다. 마지막 S1(종료 실패 시 일부 무반응 제어의 외관), S2(그 실패 상태에서 focus 위젯의 키 반응)도 낮은 우선순위로 보류한다. 보충 과정에서 합의한 R1/O1/O2/O3만 CLOSED다.
- **F02 NOT_VERIFIED / 과거 Qt 공유 FileDialog 보존 FAIL / 과거 중단 focused temp 정리 NOT_VERIFIED**를 그대로 유지한다. 제한 registry/private INI 검사를 사용자 전체 설정 보존 PASS로 확대하지 않는다. 과거 F02 runner 복구·재검증 루프를 재개하지 않는다.

## 8. Git·recovery와 다음 단위

이 문서 작성 기준은 **main / HEAD = local origin/main = a9928921e873f11c72283d35a6d0d9847eacd8e3 / ahead·behind 0·0 / staged 0**이다. 현재 수용된 source/tests **24경로(M15/U9)**와 이번 문서 **8경로(기존 7·신규 1)**를 합친 **32경로(M22/U10)**는 아직 미커밋이다. 107파일의 raw 실행 identity와 Git CRLF 정규화 blob identity를 구분한다.

조율 산출물은 `MAIN_LIVE_K_ADOPTION_UI_DOC_CLOSEOUT_2026-11-04/coordinator_01`에 둔다. 원 source·기존 evidence·다른 문서·index·Desktop을 보존하고 문서 8개만 갱신한다. 한 번의 사용자용 script가 정확한 plan/raw/index 확인, 32경로 stage·commit·push, 결과 receipt 기록을 수행하도록 준비한다. 실제 실행 전에는 push 완료라고 쓰지 않는다.

**NEXT:** 사용자 일괄 Git 실행 → 실제 commit/원격 결과 확인 → 그 SHA에 맞춘 recovery 두 파일 교체본 준비 → 사용자 Desktop 교체 확인 → 기존 설계와 현재 source를 대조해 **Main/Live LC0 연결, 이어 LC1 연결**을 구현 단위로 확정한다. postcommit 문구만을 위해 별도 문서 commit을 만들지 않으며, 실행 시점의 Git receipt/recovery를 현재 SHA의 authority로 사용한다. 이 문서 마감은 LC 구현을 시작하지 않는다.

D0–D5 CLOSED / FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE다. Phase2와 R0-B/ActualE2는 미승인/미실행이다. frozen 정책·Model C·holdout **2,010,000..2,010,099**·공식/formal evidence를 열거나 변경하지 않는다. 별도 LC0 비교 앱·LC1 저장 viewer의 수용은 Main 연결이나 새 package/Stage4 승인과 별개다.
