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
| FU-04 | 수동 입력의 엔진 예외 경로에서 이전 분석 표시가 남을 수 있음(검토 당시 추론, 미재현) | 처리([UI 후속 보완](#ui-후속-보완-2026-11-16-fu-04fu-08)). 예외 주입으로 재현 후 수정. 검증은 5개 모듈의 부분 검증 |
| FU-05 | 전시 배치 시험의 9pt 고정으로 글꼴 민감도가 회귀에서 보이지 않음 | 관측을 위 한계에 기록. native 확인은 미수행 |
| FU-06 | ID 대조 서술에 기준 커밋의 개명 1건 누락 | 이번 문서 보완으로 처리([실행기 계약](#실행기-계약)) |
| FU-07 | ASCII 성공 fixture가 소스 트리 아래 임시 폴더를 만듦 | 한계를 위에 기록. fixture는 미처리 |
| FU-08 | Replay 통계 시험의 창 크기 단언 약화 | 처리([UI 후속 보완](#ui-후속-보완-2026-11-16-fu-04fu-08)). 시험 보완, 제품 변경 없음 |

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

### 후속 보완 처리 (2026-11-21, G — UI 변경 없음, 원격 반영은 EFG Git 마감 보고서)

| ID | 처리 | 상태 | 근거 |
|---|---|---|---|
| FU-02 | 실제 프로세스 경로 자동 시험 추가(`tests.test_source_unittest_runner.RealProcessPathTests`). 시험 모듈은 시스템 TEMP의 임시 폴더에 만든다. (1) 실제 child 시간 초과와 Job 강제 종료, (2) 존재하지 않는 Python 경로로 실제 기동 실패, (3) 소유 Job 정리: 실제 하위 프로세스가 남은 경우의 정리와, 종료 권한이 없는 Job 핸들로 `TerminateJobObject`를 불러 OS가 실제로 거부하는 정리 실패(뒤이은 Job 닫기로 하위 프로세스 종료 확인), (4) 실제 수집 child 시간 초과로 구획 실행 전 중단 | 완료 | 네 분기 모두 실제 프로세스로 시험. 단 (3)의 정리 실패는 권한 없는 핸들로 조건을 유도한 것이며 자연 발생 상황을 재현한 것은 아니다 |
| FU-03 | 실행기가 기대 opt-in SKIP 목록(`EXPECTED_OPT_IN_SKIPS`, full_02의 11개)을 가진다. 선택 범위 안에서 목록 밖 SKIP과 목록에 있지만 SKIP되지 않은 시험을 `summary.json`의 `skip_gate`로 드러내고, 둘 중 하나라도 있으면 실행 실패다. child 환경에서 opt-in·증거 경로·진단 변수 15개(`OPT_IN_ENVIRONMENT`)를 항상 해제하고 `process.json`에 해제 목록과 부모에 있던 이름을 기록한다 | 완료 | 실행기 시험(관문 4사례, 실제 child 환경 확인)과 G4 전체 회귀의 `skip_gate` |
| FU-07 | ASCII 성공 fixture를 소스 트리 밖 시스템 TEMP로 옮기고, 실제(resolve) 경로가 ASCII인지와 저장소 밖인지를 시험에서 확인한다. 비정상 종료 때 남을 수 있는 폴더는 TEMP에만 생긴다. TEMP가 ASCII가 아니면 다른 위치를 만들지 않고 시험이 실패로 드러낸다 | 완료 | 이 PC의 TEMP `C:\Users\User\AppData\Local\Temp`(ASCII)에서 통과 |
| FU-05 | 처리하지 않음(H에서 전시 기기 화면 확인과 함께) | 미처리 | 이번 범위 밖 |

위 표(2026-11-16 상태)는 지우지 않고 그대로 둔다. 2026-11-21 처리 뒤 FU-02·FU-03·FU-07은 완료, FU-05는 미처리, UV 항목은 기존 상태(UV-07 확인, UV-08 유지, 나머지 미확인) 그대로다.

#### 새 전체 소스 회귀 (2026-11-21~22, `full_01` of EFG — 위 `full_02`와 별개)

표준 실행기(`full_source`, 구획당 외부 제한 3,600초)로 1회 실행했다. 대상은 E 커밋 `20772f2`와 F 커밋 `0be1fad` 위에 G의 미커밋 코드·시험 변경(G1~G3)을 더한 작업 트리다(문서 변경은 실행 뒤).

| 항목 | 결과 |
|---|---|
| 수집 / 검증 중복 / 고유 ID | 7,043 / 233 / 6,810 |
| 실행 구획 | 209 |
| 선택 / START / STOP | 6,810 / 6,810 / 6,810 |
| PASS / opt-in SKIP | 6,799 / 11 (기대 목록과 정확히 같음, `skip_gate` PASS) |
| FAIL / ERROR / 미시작 / 미완료 / fixture 사건 / 인프라·회계 오류 | 모두 0 |
| 소유 Job | 수집 포함 210개 child, 정리 후 활성 프로세스 모두 0 |
| 소스 해시 | Python 428개 실행 전후 동일 |
| 수집 누락 | 0 (선택 = 수집. `full_02` 대비 빠진 ID 1개는 E에서 이름을 바꾼 시험 1개이며 새 이름으로 포함) |

child 소요 시간 합 3,706.288초(최대 `test_program_k_e2_r0_harness` 1,885.391초), 시작 2026-11-21 23:25, 끝 2026-11-22 00:27(Asia/Seoul). 제품 성능 측정치가 아니다. 과거 시험 수(6,306)를 목표값으로 쓰지 않았다. 이 실행은 그 시점 작업 트리의 결과이며 이후 커밋·보완 커밋에 소급하지 않는다. 근거: `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/EFG_SEQUENCE_2026-11-21/G_01/full_01/`, `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/EFG_SEQUENCE_2026-11-21/G_01/REPORT_KO.md`.

### 다음 순서

수용의 Git 반영(완료) → 작은 후속 보완을 관련성에 따라 처리(FU-01·FU-04·FU-08 처리, FU-02 부분 보완)
→ 본래의 3·4단계 성능 개선 계획. 남은 보완은 위 표에 유지한다. 공통 병목과 Stage3 정보 갱신 진단의
다음 범위는 조율에서 정하며, 세부 방향은 `CURRENT_HANDOFF.md`의 "다음 작업과 승인 범위"에 있다.
후속 보완과 성능 개선은 이 문서로 승인하지 않으며 별도 전달 범위를 따른다.

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

## UI 후속 보완 (2026-11-16, FU-04·FU-08)

실행기 후속 보완(커밋 `02eadc162d38e699ce32489e796bf84af846531f`, origin의 `main` 반영과 원격 조회 확인)
뒤의 별도 변경이다. **이 수정 뒤 전체 회귀, native 화면·DPI 확인은 하지 않았다.**
아래 결과는 관련 5개 모듈의 부분 검증이며, 6,295 PASS는 이 수정 전 코드의 `full_02` 기록이다.

### FU-04: 수동 입력 예외와 분석 표시

**재현.** 제어된 예외 주입이다. 실제 사용 중 이 예외가 관측된 것은 아니다.
Simple 정책, Auto 꺼짐, 분석 결과가 화면에 있는 상태에서 press 미리보기 뒤 수동 입력을 넣고
`engine.step`이 예외를 내게 했다. 분석을 버튼으로 한 번 실행한 경우와 분석 표시를 켠 경우,
보드를 바꾸기 전에 실패한 경우와 실제 입력 뒤에 실패한 경우를 조합한 네 사례다.

- 수정 전에는 네 사례 모두 `_analysis_result`, 셀 표시 8칸, 확률 문구, 툴팁, 상태 문구가 그대로 남았다.
- 예외는 호출자에게 그대로 전달됐고 `_live_input_uncertain`이 켜졌다. Auto 예약, 재분석,
  추가 입력은 없었다. Replay 이벤트와 입력 기록은 늘지 않았고 출처는 `human`으로 유지됐다.
  이 부분은 수정 전부터 올바르게 동작했다.

**원인.** 순수 수동 미리보기는 분석을 보존한다. 그 뒤 분석을 지우는 곳은 입력 성공 뒤의
`_refresh_live_board`뿐이어서, `engine.step`이 예외를 내면 지우는 지점에 도달하지 않는다.

**수정.** [ui_manager.py](../ui_manager.py)의 `_apply_live_action` 예외 처리에서, 수동 입력일 때
`_clear_live_analysis`로 분석 결과와 셀 표시를 지우고 "실제 입력·기록을 확인할 수 없습니다" 문구를 남긴 뒤
원래 예외를 그대로 다시 전달한다. 정상 경로의 무효화가 정책과 무관하듯 이 처리도 정책과 무관하다.
자동 입력 분기는 바꾸지 않았다.

보존한 계약: 보드가 변하지 않은 순수 press/drag 미리보기의 분석 보존, Auto 중단·추측 해제·취소된
콜백 무효화, 정상 OPEN·FLAG·CHORD 뒤의 무효화와 조건부 재분석, 예외를 삼키지 않는 전달,
불확실한 입력 상태에서 추가 입력·재분석을 시작하지 않는 동작, 자동 입력의 예외 처리와 Replay 출처 보호.

**시험.** `tests/test_live_analysis.py`에 2건, `tests/test_live_auto.py`에 1건을 추가했다.

- OPEN·FLAG·CHORD × 분석 방식 2 × 실패 시점 2의 12개 사례에서 분석 결과, 셀 표시, 확률 문구,
  툴팁이 모두 지워지고, 재분석·Auto 예약이 없으며, Replay와 입력 기록이 늘지 않음을 확인한다.
- 실패 뒤의 정상 수동 입력이 분석이나 Auto를 다시 시작하지 않음을 확인한다.
- Stage3 V1 정책(합성 Job 대역)에서도 소유자 인계가 정상 수동 입력과 같고, ACK와 새 요청이 없음을 확인한다.
- 세 시험은 수정 전 `ui_manager.py`에 대해 실패하고 수정 후 통과한다.

**한계.**

- 시험은 셀 신호에 연결된 슬롯(`on_left_click` 등)을 직접 호출한다. 예외가 Qt 신호를 거쳐 전달될 때
  앱 프로세스가 어떻게 되는지는 확인하지 않았다.
- 실제 입력 뒤에 실패한 사례에서 보드 버튼은 다시 그려지지 않는다. 엔진은 칸을 열었지만 화면은 이전
  표시로 남는다. 이번 범위는 분석 무효화이며 이 관찰은 고치지 않았다. 그 입력은 Replay에 기록되지 않고
  `_live_input_uncertain`으로 자동 진행이 차단되는 기존 동작이 유지된다.
- UV-03(2026-11-04 변경의 작성 의도)은 여전히 미확인이다.

### FU-08: Replay 창 크기의 실제 결과

대상은 `tests.test_replay_statistics.MinesweeperUIEngineOwnershipTests.test_replay_grid_render_size_and_mine_counter_use_replay_engine`이다.

**기존 조건의 약점.** 실제 위젯으로 측정하니 10px 셀의 2×2 Replay 보드(20×20)와 Live 4×3 보드(40×30)는
창 크기가 1497×531로 같았다. 조작부 최소 크기가 보드를 가리기 때문이다.
이 조건에서는 창 크기를 단언해도 어느 엔진의 치수를 썼는지 구분하지 못한다.

**보완.** 기존 단언(버튼 집합, grid 수, 보드 컨테이너 크기, 맞춤 기록의 보드 치수, 렌더 호출,
지뢰 표시, 엔진 동일성)은 그대로 두고 뒤에 실제 창 검사를 더했다.

- 가상 화면 6000×4500을 명시하고, `showNormal()` 뒤 최대화·전체 화면이 아님을 확인한다.
- 셀을 1000px로 키워 Replay 보드가 2000×2000이 되게 한다. 같은 조건에서 Live 보드는 4000×3000이다.
- 맞춤 전의 실제 창이 보드보다 작음을 먼저 확인한다. 따라서 실제 resize가 없으면 통과할 수 없다.
- 맞춤과 이벤트 처리 뒤 실제 `ui.size()`가 가로·세로 모두 커졌는지, 스크롤 영역의 표시 범위가
  Replay 보드와 정확히 같은지, 스크롤이 0인지, 창이 Live 보드 치수보다 작고 가상 화면 안인지 확인한다.
- 맞춤 기록은 마지막에 실제 크기와 일치하는지만 대조한다.

시험 안에서 제품을 일시 변형해 민감도를 확인했다. resize를 무력화하면 실패하고, Replay 맞춤의
resize만 요청보다 크게 만들어 기록은 맞고 실제 창만 틀리게 해도 실패한다.

제품 코드는 바꾸지 않았다. 화면 맞춤, 큰 사용자 창 유지, 화면 한도 처리는 그대로이며
별도의 배치 결함은 발견하지 못했다.

### 검증 범위

보완된 표준 실행기로 5개 모듈만 선택해 격리 실행했다(지정 Python, 바이트코드 방지, offscreen Qt,
시험별 임시 QSettings, opt-in 변수 없음).

| 모듈 | 선택·START·STOP | PASS |
|---|---|---|
| `tests.test_live_analysis` | 32 | 32 |
| `tests.test_live_auto` | 77 | 77 |
| `tests.test_live_presentation` | 9 | 9 |
| `tests.test_replay_statistics` | 19 | 19 |
| `tests.test_ui_mouse_input` | 65 | 65 |
| 합계 | 202 | 202 |

FAIL·ERROR·SKIP·미시작·미완료는 0이다. 부모 종료 코드 0, `scope: subset`, journal·receipt 일치 5/5,
인프라·회계 오류 0이다. 실행기가 만든 child 6개(수집 1, 구획 5)는 종료 코드 0, 정리 전후 활성 0이다.

근거: 근거 루트의 `ui_followup_01/REPORT_KO.md`와 같은 폴더의 로그. 이 보완의 커밋 SHA와
원격 확인도 그 보고서에 기록한다.
