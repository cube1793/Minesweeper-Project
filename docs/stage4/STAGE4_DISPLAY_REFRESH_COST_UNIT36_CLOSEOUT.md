# Unit36 — 창 크기 유지 W 수용과 표시 D 미채택

작성: 2026-11-09 (Asia/Seoul). W는 등록 시험 9/9, 독립 검토 필수 수정 0건과 현재 PC의 사용자 native 확인 범위에서 수용한다. D는 기능·회귀 86 PASS이나 정·역순 비용 기준을 모두 충족하지 못해 미채택이다. 저장소에는 W만 남긴다.

## 기준선과 마감 상태

- 출발 main/HEAD/local origin/main: `676fe5912030ed29dcbc3c902bf7132ccf8e6a6c`. Units34–35는 이 commit과 Desktop destination 검증까지 완료됐다.
- W 제품·시험 변경은 `ui_manager.py`, `tests/test_stage4_live_ui.py` 두 경로다. 이번 마감 문서는 6경로이며 총 8경로를 사용자 commit/push 대상으로 준비한다. source384를 유지하고 tracked473→474를 예상한다.
- 이 문서는 commit 전에 작성됐다. 최종 commit·remote·Desktop 완료 여부는 사용자 영수증과 조율의 사후 검증으로 확정한다. 조율은 제품 실행과 Git 쓰기, Desktop 교체를 하지 않는다.

## W의 동작과 native 확인

보드 fitting은 사용자가 늘린 창 크기를 보존하고, 최대화·전체 화면 상태에서는 일반 창의 resize/minimum-size 적용을 건너뛴다. 일반 창의 최소 크기는 사용 가능한 화면 용량으로 제한한다. 화면 변경과 DPI 신호는 fitting을 예약하며 종료 중에는 이를 수행하지 않는다. 셀 크기, 좌표, 입력 권한, Auto/guess, owner/ACK, Replay의 의미는 변경하지 않았다.

독립 검토 RV36-NB1은 작은 화면에서 조작부가 최소 레이아웃보다 압축될 수 있다는 정적 위험을 native gate로 남겼다. 사용자는 평소 1920×1080·Windows 100%에서 1024×768·100%로 잠시 바꿔 확인한 뒤 원래 설정으로 복구했다.

| 항목 | 확인 결과와 근거 범위 |
| --- | --- |
| 작은 화면 조작부, 정책 8개, Replay | 사용자 직접 확인으로 정상. NB1 gate는 이 환경에서 충족했다. 스크린샷은 Simple 화면만 보여 주며, 8정책·Replay 범위는 사용자 진술이다. |
| 작은 화면 보드 스크롤 | 스크롤을 관찰했다. 30×16·28px 보드와 조작부가 화면 용량을 넘을 때 허용되는 동작이다. 모든 셀의 동시 표시는 수용 조건이 아니다. |
| 1920×1080·100% 복원 | 사용자가 “복원했고 여전히 정상이야”라고 보고했다. |
| 수동 확대 후 정책·Replay 전환 | 창 크기 유지 확인. |
| 최대화 중 정책·보드 변경 후 최대화 해제 | 정상 확인. NB3/NB4의 우려는 이 수동 경로에서 재현되지 않았다. 모든 복원 순서의 증명은 아니다. |
| 상급→초급에서 큰 창 유지 | 사용자가 동작을 확인하고 수용했다. NB5의 UX 선택을 수용한다. |
| 실제 hide/show, 다중 모니터, 다른 Windows 배율, 첫 표시 장식 포함 정밀 치수 | 별도 확인되지 않았다. 정상 보고를 이 범위의 PASS로 확대하지 않는다. |

마지막 세 창 동작에 대한 사용자의 답은 “세 항목 모두 확인했고 수용함”이다. N-2와 보고된 N-5/N-6 경로를 수용하고 N-1/N-3/N-4의 미확인 부분을 남긴다. 제품 전체·모든 화면/DPI·전시 노트북 검증 완료를 뜻하지 않는다.

NB2의 `_board_fit_record` 초기화 후 `hasattr`가 항상 참인 점과 NB7의 닫힌 창 화면 신호 연결은 비차단 검토 사항으로 보존한다. NB6에 따라 offscreen fixture의 화면과 실제 native 화면을 구별한다. 이번 수용을 위해 추가 제품 수정은 하지 않았다.

## 시험·원시·종료 회계

- W 최종 기능·회귀 9/9 PASS. 초기 W run01의 6 PASS + 3 FAIL은 보존한다.
- D 기능·회귀 86 PASS는 기존 B72 ∪ W9(중복 3개)에 신규 8개를 더한 집합이다. 95개로 합산하지 않는다.
- 전체 실행 기록은 108회 = 102 PASS + 5 FAIL + 1 ERROR, 고유 ID 88개다. 이는 최종 W의 고유 통과 수가 아니다.
- 표시만을 위한 추가 counter/model 호출은 통제 시험에서 0/0이다. 실제 통합 실행의 모델 호출 7회와 구분한다.
- 5회 실행 모두 필수 요청 owner의 신원·종료·handle 회수 사슬과 성공한 빈 Job 조회 2회를 충족했다. 이번 census는 6/6, 6/6, 2/2, 16/16, 2/2로 모두 COMPLETE다.
- 총계는 supervisor 5, 보수 Python 16, 실제 worker 11, engine 330, 모델 7, 부모 memory 30이며 worker를 포함한 구조 상한은 41이다.
- EXECUTED_BYTES 273개는 재해시가 일치했다. run03 probe는 사후 정확 복원 사본이며 실행 당시 증거는 시작 hash 영수증이다.
- run04 추가 진단은 primary 종료 후 경로 충돌 WinError 183 ERROR가 났다. primary 원시를 변경하지 않았고 오류를 보존했다. 최종 추가 6단계 진단 완료로 쓰지 않는다.

## D 비용 판정

단위는 ms. Δ는 같은 창 크기 유지 W가 적용된 W_ON 대비 D_ON의 비용 증가다. D_OFF는 보조 비교이며 주 판정 기준이 아니다. 아래 숫자는 원시 `wall_ns/inputs` 재계산과 일치한다.

| 순서 | 보드 | median Δ / 한도 | batch P95 Δ / 한도 | 판정 |
| --- | --- | --- | --- | --- |
| 정방향 | 9×9 | −1.938275 / 1 | 1.46364 / 3 | PASS |
| 정방향 | 16×16 | −0.382640625 / 1 | 3.4778375 / 3 | FAIL |
| 정방향 | 30×16 | 4.06076875 / 1.18102640625 | 8.66338125 / 3 | FAIL |
| 역방향 | 9×9 | −1.8454375 / 1 | −0.9994925 / 3 | PASS |
| 역방향 | 16×16 | 2.124734375 / 1 | 3.241928125 / 3 | FAIL |
| 역방향 | 30×16 | 4.398940625 / 1 | 5.609128125 / 3 | FAIL |

batch P95는 9개 배치별 입력당 평균값 중 최대값이다. 개별 입력 지연 전체의 P95가 아니다. 블록 순서 교대, 역방향 새 프로세스, warmup과 cycles 10/8/8의 등록·실행이 일치했다. D_OFF도 producer·디스크 wire·수신 검증 비용을 포함한다. 이는 통제 표시 경로 비용으로, 일반 정책 효율·모델 지연 개선을 입증하지 않는다.

D snapshot과 patch는 `codex_01/candidates/D_UNACCEPTED` 등에 보존한다. `live_reference_analysis.py`와 `tests/test_live_reference_analysis.py`는 저장소에 없다. 입력별 안전칸·지뢰칸·확률 상시 갱신은 계속 미채택이다.

## 근거와 검토 한계

외부 근거 root: `C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\STAGE4_DISPLAY_REFRESH_COST_UNIT36_2026-11-09`.

- 구현: `codex_01/REPORT_KO.md`, `REVIEW_HANDOFF_KO.txt`, 원시·candidates·`OUTPUT_MANIFEST.json`. Manifest는 12,672파일, 합계 78,923,462 bytes이며 manifest 자체 SHA256은 `774b4fa88a96ed865624b4240ec59cae4850cf0e089c1436306c6aa39a7e3e22`다.
- 조율 대조: `coordinator_02`의 실행·비용 재계산과 source/tracked manifest. `coordinator_03/REVIEW_VERIFICATION_EFFECTIVE.json`을 유효 판정으로 사용한다. 원 검증의 경로 구분자·manifest 크기 해석 오류와 보정은 별도 보존한다.
- 독립 검토: `review_claude_01/REVIEW_REPORT_KO.md`, `FINDINGS.json`, `OUTPUT_MANIFEST.json`. 약 24분, 필수 수정 0, 비차단 7. Manifest는 22파일·369,525 bytes이며 자체 SHA256은 `44eebc0f29aaa2c9f4ab3b447ea4d35b26b6c09d8d1b0dc634f352dce250a400`이다.
- Native: `coordinator_05/native_small_screen.png`, `coordinator_06/USER_NATIVE_N2_RESULT.json`, `coordinator_07/USER_NATIVE_REPORT.json`, `coordinator_07/COORDINATOR_ACCEPTANCE.json`.
- Git 준비·사후 영수증: 별도 `STAGE4_UNIT36_CLOSEOUT_2026-11-09` root. 현재 source 2파일은 W hash `f8b1f30e…`와 `bccff0a9…`에 결속한다.

독립 검토는 D 전체 diff, wire 5,832개 메시지의 내용 재생, 승인 계약의 조항별 재대조, 현재 OS 프로세스 조회를 하지 않았다. 메시지 수는 파일 수로 확인했다. 조율에서 금지된 제품 실행을 추가하지 않았고, 미확인 범위를 성공으로 바꾸지 않는다. 요청된 구현 설정은 GPT-6 Astra/Max/standard이며 실제 미노출 설정은 UNCONFIRMED다. 검토는 Opus 5.5/Max가 관측됐고 Auto/Fast는 UNCONFIRMED다.

## 보존과 다음 범위

과거 A의 **302 PASS + 보호 FAIL 1**, 기존 B_COST_FAIL, INCOMPLETE_CENSUS, run01 16/14 및 과거 35/34 FAIL, helper 원문 공백과 모든 미채택 기록을 유지한다. 이번 census COMPLETE나 W native 수용으로 과거 실패를 덮지 않는다.

다음 마감은 사용자 Git commit/push → 조율의 commit/tree/원격 영수증 검증 → 실제 commit에 결속한 Desktop 교체 준비 → 사용자 교체와 destination 검증 순서다. 이후 초기·단순 국면의 무거운 모델 호출 선별, 고효율 Replay 해체 분석, 새 보드 S/M/R 비교, R 목표 UX와 전시 노트북 검증을 별도 범위로 준비한다. D 비용 개선은 미채택 후속 후보로 남는다.

S/M/R 목적·추측 규칙·프로파일, frozen 정책·Model C·holdout 2,010,000..2,010,099·금지 formal evidence와 Production 미승인 경계는 유지한다. 일반 효율·Stage4 전체 효과성은 미확립이다. 11월10일 18시는 노트북 대여 신청 시작이며 수령 시각은 미정이다.
