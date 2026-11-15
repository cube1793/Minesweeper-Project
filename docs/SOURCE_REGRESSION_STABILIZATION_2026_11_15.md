# UI 시험 및 전체 소스 회귀 안정화

착수: 2026-11-15 / 완료: 2026-11-16, Asia/Seoul. 시작 HEAD는
`b586062003107bbc2832a4fb0e3fd3b343521f0f`이며 시작 시 작업 트리는 clean이었다.
로컬 `main`, `origin/main`, 연결 GitHub의 `main` SHA가 같았다.

## 검증 상태

**보완한 표준 실행기의 전체 소스 회귀 `full_02`: PASS, 부모 종료 코드 0.**
검증 대상은 위 HEAD에 이번 수정을 적용한 작업 트리다. 검증을 마친 2026-11-16 01:53에는
미커밋 상태였고 새 커밋·푸시는 수행하지 않았다. 이후의 독립 검토·수용과 Git 반영의 관계는
아래 [독립 검토와 수용](#독립-검토와-수용-2026-11-16-보완) 절에 적는다.

| 항목 | 최종 결과 |
|---|---|
| 수집 / 검증 중복 / 고유 ID | 6,539 / 233 / 6,306 |
| 실행 구획 | 187 (정의 모듈 186개 + 별도 supervisor 클래스) |
| 선택 / START / STOP | 6,306 / 6,306 / 6,306 |
| PASS / 명시적 opt-in SKIP | 6,295 / 11 |
| FAIL / ERROR / 미시작 / 미완료 | 모두 0 |
| 실패·오류·fixture 사건 / 인프라·회계 오류 | 모두 0 |
| 소유 Job 종료 | 수집 포함 188개, 정리 후 활성 프로세스 모두 0 |
| 소스 / 수집 이행 검증 | Python 381개 실행 전후 해시 일치, 기존 수집 대비 누락 0 |
| 기존 UI 선정 / 과거 실패 대응 | UI 40건 PASS, 과거 131개 실패·오류 블록 모두 현재 PASS에 대응 |

Python 3.12.10 / PyQt 5.15.11 / Qt 5.15.2, 지정된 개발 Python과 offscreen Qt에서 검증했다.
전체 child 소요 시간 합은 3,761.680초이며 제품 성능 측정치가 아니다.

첫 전체 실행 `full_01`은 대형 R0 harness 구획의 외부 1,800초 제한 때문에 실패했다.
전체 6,272 PASS / 11 SKIP / 미완료 1 / 미시작 22 / 시험 FAIL·ERROR 사건 0이었다.
해당 구획은 341건을 통과한 상태였고, 나머지 186개 구획은 통과했다. 소유 Job 정리도 완료됐다.
외부 제한만 3,600초로 보완한 뒤 전체를 새 `full_02`에서 다시 실행했다. 해당 364건은
1,977.250초에 모두 통과했다. 개별 시험·제품의 시간·메모리 예산은 유지했다.
두 실행 사이에 해시가 달라진 Python 파일은 실행기 1개뿐이며, 각 실행 중 소스 해시는 유지됐다.
구현 기록은 그 변경을 외부 제한과 기록 항목으로 적는다. 다만 `full_01` 시점의 실행기 사본이
보존되지 않아 변경 내용 전체를 독립적으로 대조하지는 못했다(UV-01).

기존 Unit74 `FAILED_UNRESOLVED`와 이번 `full_01`의 실패 원시 기록은 보존한다.
이번 성공을 이들 과거 실행의 성공으로 소급하지 않는다.

## 수정 범위

제품 변경은 [ui_manager.py](../ui_manager.py)의 Simple 수동 인계 한 곳이다.
Auto가 켜졌거나 입력 예약이 있으면 기존처럼 즉시 중단한다. 순수 수동 플레이에서
press/drag 미리보기만 수행할 때는 아직 보드가 바뀌지 않았으므로 현재 분석을 보존한다.
실제 입력의 기존 분석 무효화·재분석 경로는 유지한다.
`test_ui_mouse_input.MouseInputTests.test_hidden_to_number_and_number_to_number_preview_is_pure`가
수정 전 실패와 수정 후 성공을 확인한다.

나머지는 시험 조건·대역과 [기존 실행기](../scripts/run_source_unittest_isolated.py)의 보완이다.
알고리즘, Stage3/4 계산, 자원 보호 한도, 같은 보드 비교의 알고리즘 선택 기능은 바꾸지 않았다.

| 증상 | 확인한 원인과 조치 |
|---|---|
| `test_live_presentation` 우클릭 후 재개 | 실제 경과 없이 500ms 타이머 호출. 시험 시계로 기한 1ns 전 무입력, 기한의 정확한 1회 입력, 취소·중복 콜백 무효를 확인한다. |
| 같은 모듈 상태줄 배치 | offscreen 800×600 화면과 요청 창 크기 충돌. 1920×1080 논리 화면을 명시하고 창·보드·상태줄·조작부 좌표를 비교한다. 제품 화면 맞춤은 유지한다. |
| mouse trace/Replay/V1 인계의 Auto 입력 누락 | 같은 기한 전 콜백 문제. 실제 입력을 확인할 시험은 제어된 시계를 기한으로 이동한다. |
| `test_live_pacing_clock` 종료 시간 초과 | 관측 래퍼가 추가된 `target` 인자를 받지 못해 Auto가 중단됨. 인자를 그대로 전달하고 타깃 일치도 확인한다. 실제 QPC·18입력·조기 입력 금지 기준은 유지한다. |
| `test_replay_statistics` 8 ERROR | `_TimerProbe.timerType` 누락 뒤 다른 UI 대역 누락도 확인. 엔진 소유권 fixture에 실제 Qt UI/타이머와 임시 QSettings를 사용한다. worker 시작만 차단한다. |
| 정책 수·초기값·수동 인계 기대 불일치 | 이미 반영된 8개 정책, 200ms 초기값, 수동 press 시 추측 해제 계약에 시험을 맞춘다. 기존 툴팁·제품 이력·다른 시험과 대조했다. |
| 큰 글꼴의 속도 편집기 배치 | 14pt 최소 너비보다 작은 offscreen 화면 제한. 충분한 논리 화면을 명시한다. |
| 전시 창의 보드 세로 스크롤 | 현재 PC의 native Windows는 9pt, offscreen 기본은 12pt. 기준 배치 시험에 9pt를 명시한다. 1920×1000 전체 보드와 900×700 개별 스크롤 검사는 유지한다. |
| 전시 worker 준비 PID가 빈 문자열 | 파일 생성과 쓰기 사이의 경쟁. 완성된 임시 파일을 원자적으로 공개한다. 실제 worker 종료 확인은 유지한다. |
| `PROFILE_ASCII_TEXT_REQUIRED` | 성공 fixture의 native 파일이 한글 TEMP 아래 생성됨. ASCII 소스 경로 아래의 고유 임시 폴더를 쓰고, 비ASCII 경로 거부 시험을 추가한다. |

## 실행기 계약

수집은 별도 프로세스에서 `tests.*` 패키지 이름으로 한다. `test_x`와 `tests.test_x`를
별도 모듈로 적재하던 중복을 제거하며, 같은 ID를 만났을 때도 클래스 객체·메서드 객체·
초기 상태·기본 unittest id/run의 동일성을 확인한 경우에만 하나로 합친다.
원시 occurrence, 고유 ID, 제거한 occurrence와 소스 해시를 모두 기록한다.

최종 소스의 수집은 6,539 occurrence / 고유 6,306 / 검증 후 합친 중복 233이다.
기존 이름 방식으로 같은 소스를 다시 수집하면 고유 문자열 ID는 6,510개지만,
소스 파일·클래스·메서드 위치로 대조하면 같은 6,306개에 대응하고 누락은 없다.
이번에 추가한 시험은 실행기 11개와 비ASCII 경로 보호 1개다. 과거 6,498이라는
문자열 ID 수를 현재 시험 수의 목표값으로 사용하지 않았다.

과거 6,498개를 `tests.` 이름으로 정규화하면 6,294개다. 이 집합과 현재 6,306개를 집합으로
대조하면 **추가 13개·제거 1개**다(독립 검토 FU-06의 문서 보완). 추가 13개 중 12개가 위의
이번 추가 시험이다. 나머지 추가 1개와 제거 1개는 기준 커밋 `b586062`에 이미 들어 있던
같은 시험의 개명이다.

- 이전: `tests.test_stage3_visualizer_launcher.Stage3MainUIIntegrationTests.test_counters_entry_preserves_existing_tools_statistics_action`
- 현재: `tests.test_stage3_visualizer_launcher.Stage3MainUIIntegrationTests.test_developer_menu_entry_preserves_statistics_and_zini_tools`

따라서 6,294 + 11 + 1 = 6,306은 개수로는 맞지만, 같은 6,294개 집합에 12개를 더한 것은 아니다.
이번 안정화에서 시험을 누락하거나 제거한 것이 아니며, 제거된 ID를 가리키는 과거 실패 블록도 없다.

부모는 시험을 import하지 않는다. 각 모듈은 새 Python 프로세스에서 실행하며,
`tests.test_program_k_harness.ProgramKSlice7SupervisorTests`는 별도 구획을 유지한다.
따라서 `test_live_cadence_measurement`가 설치한 영구 감사 훅은 다른 시험이나 부모의
후속 프로세스 기동에 영향을 주지 않는다. 훅은 유지했고 실제 차단 단언도 보강했다.

각 child를 suspend 상태로 소유 Windows Job에 등록한 뒤 실행한다. 추가 메모리 상한은
설정하지 않으며, 시험 내부의 원래 한도를 유지한다. 프로세스 종료와 소유 Job의 활성
프로세스 0을 확인한다. stdout/stderr, START/STOP/결과 JSONL, receipt, process 기록을 남긴다.

고유 시험 결과와 subTest·fixture 사건 수를 구분한다. 같은 시험의 failure/error가 함께
발생하면 고유 결과는 error이고 양쪽 사건은 모두 보존한다. setUpClass 오류로 시작되지
않은 시험은 `not_started`, 시작만 한 시험은 `unfinished`로 기록한다. skip은 PASS가 아니다.
시험 실패, 미시작, 미완료, fixture 오류, receipt 누락, 프로세스·회계 오류는 관문 실패다.
`run`/`completed`는 unittest의 START/STOP 기준이므로 SKIP도 포함하며, 시험 본문 통과 수는
`pass`로 따로 확인한다.

실행 예시와 옵션은 [BUILDING.md](../BUILDING.md)에 있다.
`--module` 결과는 `subset`으로 표시되며 전체 회귀 성공으로 확대하지 않는다.

## 근거와 해석 경계

새 근거 루트:
`C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/UI_UNIT74_STABILIZATION_2026-11-15/`

- `ui_before`, `ui_after`, `ui_related`: 최초 UI 2개 재현·수정과 관련 57개 시험.
- `ui_remaining_before`, `ui_remaining_after`: 추가 UI 실패 9개 재현과 관련 18개 확인.
- `diagnostic_01`~`diagnostic_03`, `runner_final_check`: 실패군별 격리 진단과 수정 결과.
- `profile_unicode_before`, `profile_unicode_after`: 한글 TEMP 원인 재현과 11개 보호 시험.
- `NATIVE_FONT.json`, `exhibition_before`, `exhibition_after`: 글꼴·배치 조건과 화면 기록.
- `DISCOVERY_MIGRATION_FULL_02.json`: 최종 소스의 기존/정규 수집 대응 및 누락 0 확인.
- `PREVIOUS_UI_SELECTION_CURRENT.json`: 이전 선정 UI 40건의 이번 전체 실행 결과.
- `HISTORICAL_FAILURE_MAPPING.json`: 과거 131개 블록별 시험 ID와 현재 결과. 분류는
  감사 훅 79 / 메모리 19 / TimerProbe 8 / ASCII 1 / 기타 24다.
- `FINAL_VERIFICATION.json`: 두 실행의 소스 해시, 소유 Job 종료, 원본 로그 보존 확인.
- `REPORT_KO.txt`: 최종 결과와 근거를 정리한 보고서.
- `FINDINGS_KO.txt`: 파일·시험별 원인과 조치 상세.
- `full_01`: 첫 전체 소스 회귀. 외부 1,800초 제한으로 실패한 기록을 보존한다.
- `full_02`: 외부 제한 보완 후 표준 실행기의 전체 소스 회귀.
- `FULL_01_TIMEOUT_FINDING_KO.txt`: 제한 시간 진단과 중단 시험 ID.

과거 stderr는 혼합 인코딩이므로 시험 ID와 분류 표지는 원시 바이트로 대조했다.
마지막 시험 뒤의 unittest 실행 요약과 별도 supervisor 기동 오류는 해당 시험 블록에서 분리했다.
`HISTORICAL_FAILURE_MAPPING_UNBOUNDED_PARSE.json`은 이 경계를 적용하기 전의 중간 산출물이며,
최종 분류·대응 근거는 위 `HISTORICAL_FAILURE_MAPPING.json`이다.

과거 E1 메모리 실패는 새 프로세스에서 원래 한도를 유지한 89개 시험이 통과했다.
이것을 과거 바깥 4GiB Job과 누적 메모리 각각의 기여율을 입증한 것으로 확대하지 않는다.
원 Unit74 전체 실패, Stage4 한정 14모듈·187시험 성공, 이번 전체 소스 회귀는 서로 다른 실행이다.

기존 봉인 출력, Stage3/4 수용·평가 결과와 금지된 평가 경계는 유지한다.
전시 기기 검증, 패키징, 성능 개선, 새 대규모 보드 평가는 이번 결과에 포함하지 않는다.

## 독립 검토와 수용 (2026-11-16 보완)

이 절은 검증 뒤에 추가했다. 위 본문의 검증 수치와 원시 근거는 바꾸지 않았다.

### 근거 문서

근거 루트의 `claude_review_01/` 아래에 있다. 이 문서 보완에서 수정하지 않았다.

- `REVIEW_KO.md`: 독립 검토 본문. 구현에 참여하지 않은 Claude Code 세션이 작성했다.
- `FINDINGS.json`: 후속 보완 FU-01~FU-08, 미확인 UV-01~UV-08의 원문.
- `EVIDENCE_CHECKS.json`: 변경 19개 파일의 SHA-256, 187개 구획 journal의 독립 재계산, ID 대조.
- `support/`: 독립 집계 스크립트 2개와 출력 전문.
- `REVIEW_SCOPE_CORRECTION_KO.md`: 검토 세션의 쓰기 범위 이탈과 기록 불일치 정정.

### 수용 범위

조율 판단(2026-11-16)에 따라 **검토된 코드와 offscreen Qt 소스 회귀 범위에서 수용**한다.

- 기존 선정 UI 시험 40건 PASS. 전체 회귀 6,295 PASS / 명시적 opt-in SKIP 11.
  FAIL·ERROR·미시작·미완료 0. 과거 131개 실패·오류 블록이 현재 PASS에 대응한다.
- 독립 검토의 수용 전 필수 수정은 0건이다. 후속 보완 8건과 미확인 8건은 아래에 유지한다.
- 독립 검토는 변경 19개 파일의 해시가 `full_02` 검증 스냅샷과 같음을 확인했다.
  Git 반영 직전에도 19개 모두 `EVIDENCE_CHECKS.json`의 기록과 일치했다. 그 뒤에 바꾼 것은
  수용 내용을 적은 이 문서와 `CURRENT_HANDOFF.md` 두 개뿐이며, Python 16개와 `BUILDING.md`는
  검토된 내용 그대로다.
- 문서 보완 뒤에 전체 회귀나 UI 시험을 다시 실행하지 않았다. 위 수치는 `full_02`의 재사용이다.
- 검증 당시 미커밋이던 안정화 변경과 수용 문서 보완은 커밋
  `7386e696cf848113a627b248effc059c89aecd11`로 origin의 `main`에 반영됐고 원격 조회로 확인됐다.
  근거는 근거 루트의 `acceptance_commit_01/REPORT_KO.md`다.

### 수용의 한계

- 현재 PASS 대응은 과거 실패 원인을 모두 개별 확정했다는 뜻이 아니다(UV-04).
- 과거 Unit74 `FAILED_UNRESOLVED`와 `full_01`의 실패 기록은 그대로 보존한다.
- `full_01`과 `full_02` 사이에 실행기 파일이 달라진 것은 확인됐다. `full_01` 시점의 실행기
  사본이 없어 변경 내용 전체를 독립적으로 대조하지는 못했다(UV-01).
- 전시 배치는 offscreen 12pt 조건의 1920×1000 창에서 보드 세로 스크롤 93px이 관측됐다.
  시험은 9pt를 명시하므로 이 글꼴 민감도는 회귀에서 드러나지 않는다(FU-05).
- ASCII 성공 fixture는 `tests` 폴더 아래에 임시 폴더를 만든다. 저장소 경로 자체가 비ASCII인
  환경에서는 이 fixture가 실패하며, 비정상 종료 시 미추적 폴더가 남을 수 있다(FU-07).
- native 화면, 다른 DPI·글꼴, 배포본은 확인하지 않았다. 별도 확인 대상이다(UV-02).
- 전체 성공 실행은 `full_02` 1회다(UV-05).

### 절차 정정

기술적 수용과 절차상 범위 이탈을 구분한다. 정정은 기술적 결론을 바꾸지 않는다.

- 검토 세션은 검토 폴더 밖의 Claude 메모리 파일 1개를 수정했고, 세션 임시 폴더에 작업 파일
  10개를 만들었다. 둘 다 당시 허용한 쓰기 위치를 벗어났다.
- 검토 폴더 안의 `support/` 산출물은 허용 범위였다.
- 정정 문서가 경로, 변경 내용, 보존 자료, 시점과 미확인 사항을 기록했으므로 정정 단계는
  완료로 처리한다. 기존 검토 파일과 외부 메모리는 다시 수정하지 않는다.
- 메모리 머리말 `modified` 값을 바꾼 주체, 백업 사본의 생성 시점, 세션 기록 시각의 절대 정확도,
  검토 세션 밖의 쓰기 여부는 정정 문서 6절대로 미확인이다.
- 검토 세션의 설정은 정정 문서가 세션 기록 파일의 필드로 확인한 범위다: 모델
  `claude-fable-5-2`, 노력 `high`, 권한 `auto`. 앱 설정 화면을 직접 확인한 값이 아니며,
  다른 세션의 설정으로 옮겨 적지 않는다.

### 후속 보완과 미확인 항목

원문은 `claude_review_01/FINDINGS.json`이다. 아래 항목은 현재 수용을 막는 필수 수정이 아니다.
"미처리"는 코드나 시험을 고치지 않았다는 뜻이다.

| ID | 내용 | 상태 |
|---|---|---|
| FU-01 | 부모 실행기가 성공 경로에서 journal과 receipt를 교차 확인하지 않음 | 처리([실행기 후속 보완](#실행기-후속-보완-2026-11-16-fu-01fu-02-일부)). 검증은 해당 모듈의 부분 검증 |
| FU-02 | 실행기의 timeout·receipt 누락 등 프로세스 경로에 자동 시험 없음 | 부분 보완. 부모 처리 경로만 대역으로 시험. 실제 프로세스 경로는 미처리 |
| FU-03 | skip 기대 목록과 opt-in 환경 변수 통제 없음 | 미처리 |
| FU-04 | 수동 입력의 엔진 예외 경로에서 이전 분석 표시가 남을 수 있음(추론, 미재현) | 미처리. 다음 UI 보완 후보 |
| FU-05 | 전시 배치 시험의 9pt 고정으로 글꼴 민감도가 회귀에서 보이지 않음 | 관측을 위 한계에 기록. native 확인은 미수행 |
| FU-06 | ID 대조 서술에 기준 커밋의 개명 1건 누락 | 이번 문서 보완으로 처리([실행기 계약](#실행기-계약)) |
| FU-07 | ASCII 성공 fixture가 소스 트리 아래 임시 폴더를 만듦 | 한계를 위에 기록. fixture는 미처리 |
| FU-08 | Replay 통계 시험의 창 크기 단언 약화 | 미처리. 다음 UI 보완 후보 |

| ID | 내용 | 상태 |
|---|---|---|
| UV-01 | `full_01` 시점 실행기 소스 미보존 | 미확인 유지 |
| UV-02 | native 화면·다른 배율에서의 동작 | 미확인 유지. 별도 확인 대상 |
| UV-03 | 2026-11-04 변경(press 시 분석 삭제)의 작성 의도 | 미확인 유지 |
| UV-04 | 과거 실패의 블록별 원인 | 미확인 유지 |
| UV-05 | 반복 안정성과 다른 부하 조건 | 미확인 유지 |
| UV-06 | Python 381개 밖의 불변성 | 미확인 유지 |
| UV-07 | `ui_manager.py` 수정이 승인 범위 안이었는지 | 확인. 조율 전달(2026-11-16)에 따르면 최초 사용자 요청의 "직접 관련된 최소 제품 수정" 승인에 해당한다 |
| UV-08 | 독립 검토의 로그 전문 열람 한계 | 유지 |

### 다음 순서

수용의 Git 반영(완료) → 작은 후속 보완을 관련성에 따라 처리(FU-01 처리, 다음 UI 보완 후보는
FU-04·FU-08) → 본래의 3·4단계 성능 개선 계획. 세부 방향은 `CURRENT_HANDOFF.md`의
"다음 작업과 승인 범위"에 있다. 후속 보완과 성능 개선은 이 문서로 승인하지 않으며 별도 전달 범위를 따른다.

## 실행기 후속 보완 (2026-11-16, FU-01·FU-02 일부)

수용과 Git 반영 뒤의 별도 변경이다. 위 본문의 검증 수치는 이 보완 전 실행기의 기록이며 바꾸지 않았다.
**이 수정 뒤 전체 회귀는 실행하지 않았다.** 아래 결과는 해당 모듈의 부분 검증이다.

### 변경

부모(`full_source`)는 구획마다 child가 실행 중에 남긴 `events.jsonl`을 성공 경로에서도 읽는다.
요청한 시험 ID와 journal로 receipt를 다시 만들고 child의 `receipt.json`과 대조한다.

- 대조 대상은 합계만이 아니다. 선택·시작·종료 ID 목록, 시험별 결과, 결과·subTest 사건,
  fixture 사건, 집계를 모두 비교하고 다른 항목 이름을 오류에 적는다.
- 다음은 구획 오류로 남고 전체 성공이 되지 않는다: journal 누락, 읽기 실패, 잘린 줄·JSON이 아닌 줄·
  기록 형식이 아닌 줄, receipt 누락이나 내부 불일치, 종료 코드와 receipt의 모순,
  내부적으로 유효한 receipt와 journal의 불일치.
- 문제가 있으면 journal 기준 결과를 `recovered_receipt.json`으로 따로 남기고 집계에 쓴다.
  child의 원본 `events.jsonl`과 `receipt.json`은 고쳐 쓰지 않는다. 복구 결과가 깨끗해 보여도
  오류가 남아 있으므로 구획은 성공이 되지 않는다.
- 복구 파일을 쓰지 못해도 그 사실을 오류로 더하고 `summary.json`은 기록한다.
- `summary.json`에 `journal_reconciled`(journal과 receipt가 일치한 구획 수)를 추가했고,
  구획 출력 줄 끝에 `journal=MATCH` 또는 `journal=RECOVERED`를 붙인다.
- 한 구획의 문제를 하나씩 모두 기록한다. 프로세스 오류 목록의 회계 오류 문구는
  `RuntimeError: Missing child receipt`에서 `Missing child receipt` 형식으로 바뀌었다.

수집 정규화, 모듈별 격리, 감사 훅 보호, Job 소유·정리, 제품·개별 시험의 자원 한도,
3,600초 기본 외부 제한, 결과 우선순위와 SKIP·fixture·subTest 집계 의미는 바꾸지 않았다.

### 수정 전 확인

journal에는 두 번째 시험의 failure가 있고 receipt는 2건 PASS, 종료 코드는 0인 최소 사례를
대역으로 공급했다. 수정 전 부모는 종료 코드 0과 `successful: true`를 냈다. 수정 후에는
종료 코드 1, `successful: false`, `Journal/receipt mismatch: outcomes, events, counts`를 남긴다.

### 검증 범위

- `tests.test_source_unittest_runner` 직접 실행: 18건(기존 11 + 신규 7) PASS.
  같은 시험을 수정 전 실행기에 돌리면 기존 11건은 통과하고 신규 7건은 모두 실패·오류였다.
- 표준 실행기로 그 모듈만 선택한 격리 부분 실행(`--module tests.test_source_unittest_runner`):
  선택·START·STOP 18/18/18, PASS 18, 부모 종료 코드 0, `scope: subset`, `journal_reconciled: 1`.
  실제로 만든 소유 프로세스 2개(수집, 구획)는 종료 코드 0, 정리 전후 활성 0이다.
  이 실행의 수집은 6,546 occurrence / 고유 6,313이었다.
- 전체 회귀, UI 시험, 제품 실행은 하지 않았다. 6,295 PASS는 보완 전 실행기의 `full_02` 기록이다.

### FU-02의 범위

신규 7건은 `launch`를 대역으로 바꾸고 `full_source`의 실제 분기를 지나 최종 종료 코드,
`summary.json`, 오류 기록, 부분 결과를 확인한다. 검증한 의미는 다음과 같다.

- journal·receipt·종료 코드가 일치하면 성공(SKIP·expected failure 포함)
- 유효한 receipt가 journal과 다르면 실패(합계가 같고 시험만 다른 경우, subTest·fixture 사건 누락 포함)
- 성공 receipt가 있어도 journal이 없거나 손상됐으면 실패
- receipt 없이 부분 journal만 있으면 미완료·미시작을 보존하고 실패
- 종료 코드와 receipt가 모순되면 실패
- child 실행 결과에 시간 초과·정리 실패 같은 기반 오류가 있으면 결과가 깨끗해도 실패
- 복구 파일을 쓰지 못해도 요약과 기존 파일을 보존

남은 범위는 실제 프로세스 경로다. 실제 child의 시간 초과와 강제 종료, 프로세스 기동 실패,
Job 정리 실패, 수집 child 실패 분기에는 자동 시험이 없다. 실제 프로세스로 확인한 것은 위의
정상 부분 실행 1회이고, 실제 시간 초과의 실측 근거는 여전히 `full_01`의 1건이다.

근거: 근거 루트의 `runner_followup_01/REPORT_KO.md`와 같은 폴더의 로그. 이 보완의 커밋 SHA와
원격 확인도 그 보고서에 기록한다.
