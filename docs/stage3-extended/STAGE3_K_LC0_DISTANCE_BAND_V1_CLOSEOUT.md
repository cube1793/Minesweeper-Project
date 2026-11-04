# K-LC0 / DISTANCE_BAND_V1 — source checkpoint closeout

> **별도 정책/전시 앱의 역사 checkpoint.** 이후 Main/Live LC0 연결도 2026-11-04 독립 검토와 사용자 native 수용을 마쳤다. 현재 Main 계약·wirev8·인수/인계·검증·Git NEXT는 [Main/Live LC0 closeout](STAGE3_MAIN_LIVE_K_LC0_CLOSEOUT.md)을 따른다. 아래 미연결/당시HEAD·실행 자료는 역사로 보존한다.

작성: 2026-11-02 (Asia/Seoul). **구현·focused 검증·Claude 독립 source 검토 PASS,
사용자 고정 경로 viewer 정상 동작 및 전반적 경로 개선 체감 확인**을 기록한다.
이는 실험적 source checkpoint다. K-LC0 freeze, 일반 개선 효과, production 승인이 아니다.
이 문서 작업에서는 source/tests를 수정하거나 tests·앱·solver·분석을 실행하지 않았다.

## 계보와 현재 authority

개발 계보는 **frozen V1 → K-P0 → 실험적 K-LC0**다. V1-LC0 구현은 생략했다.
V1도 CHORD를 사용하며 Stage2 Simple과 구별한다. 원래 K-P0와 K-LC0는 별도
policy/entry이고 Main/Live selector에는 아직 연결되지 않았다.

현재 committed 기준은 `3e9f3935f505ff36dd74b6fba668650ab5c1d41d`다.
기존 V1/K-P0 source 전시와 그 문서는 사용자가 이미 commit/push했다.
2026-11-02 문서 작업 시작 때 main / HEAD == local origin/main, ahead/behind 0/0,
tracked 변경 없음·index 비어 있음이었지만, **K-LC0 4개 + 새 비교 앱 9개 = 13개
untracked**가 있었다. clean 상태가 아니며 실행 identity를 HEAD만으로 나타낼 수 없다.
이번에는 허용 기존 문서 5개와 신규 closeout 2개를 준비했다. 새 commit SHA는 아직 없다.

구현 authority는 [policy](../../experiments/program_k_lc0_policy.py),
[runner](../../experiments/program_k_lc0_runner.py),
[tests](../../tests/test_program_k_lc0.py),
[후보 fixture](../../tests/fixtures/program_k_lc0_native_candidates.json)와 당시 evidence다.
네 파일은 원 NEW_FILES의 bytes를 유지한다. fixture의 CRLF를 정규화하지 않았다.
향후 Git LF blob과 실행 당시 worktree SHA-256은 달라질 수 있으며 과거 receipt를 바꾸지 않는다.

## 정책과 실행 경계

현재 공개 observation에 대해 기존 KLocalSession 분석 및 native `select_policy`를
각 한 번 호출한다. native가 만든 후보, exact_route 순서, (L,R) dominance와 survivors,
원래 선택 g를 유지한다. certainty에서 E=L/R이고 band는 정확한 정수식
`20 * L(p) * R(g) <= 21 * L(g) * R(p)`를 만족하는 **기존 survivor**뿐이다.
이 band에서 **D_route → 정확한 Fraction E → L → frozen final tie** 순으로 선택한다.
frozen tie는 terminal (y,x,action rank), 이어 setup (y,x) 순서다.

D_route는 현재 cursor에서 계획의 모든 FLAG와 terminal OPEN/CHORD까지의
Euclidean 구간을 math.hypot/math.fsum으로 더한 칸 단위 거리다. 첫 목표까지의 거리나
게임 전체 이동이 아니다. 원래 FLAG 순서를 재탐색하지 않는다. 반올림/isclose 없이
Python float ==로 거리 동률을 판정하며 수학적 동률과 항상 같다고 주장하지 않는다.

선택한 계획의 **첫 입력 하나만 실행하고 다음 공개 상태에서 재계획**한다.
guess·추론·M 유지 규칙·Model C는 그대로다. EXACT_GUESS는 native minimum-risk와
(y,x) tie/no-setup을 유지한다. SETUP_OPEN integrity failure를 전파하며 FLAG fallback은 없다.
fresh session, 빈 M, cursor(0,0), 첫 OPEN(0,0), 공개 port와 terminal status-first 경계를 쓴다.
M_before는 분석 전, preinput_M은 분석 후 실행 직전이며 물리 FLAG와 별도다.
terminal truth는 archive용이고 정책 추론으로 되돌리지 않는다.

5%는 고정 실험값이며 전체 비용 5% 보장이 아니다. 인근 확정 안전 칸의 즉시 처리,
지역 전체 마무리, 전체 이동 최소, 승률/일반 효과성 향상을 보장하지 않는다.
원래 dominance에서 제거된 더 가까운 후보도 되살리지 않는다.
Model C를 거리 penalty로 바꾸거나 band/guess/지역 heuristic을 tuning하지 않았다.

인증 profile SHA-256: `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b`.
table SHA-256: `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b`.

## 원 구현의 고정 3보드 / 6회 pilot

공개 EXPERT_GENERAL_V1의 11/97/2026에서 진단 `K-LC0-CONTROL` 각 1회와 active
K-LC0 각 1회를 실행했다. CONTROL은 LC0 runner에서 거리 선호만 끈 경로이며,
기존 frozen V1 shadow CONTROL과 다르다. CONTROL 3회의 458 actions/461 frames는
인증된 actual K-P0 capture와 동일함을 확인했다. 새 앱은 이 CONTROL로 실행을 대체하지 않는다.

| index | policy | outcome | 입력 | O/F/C | 종료 Model C µs | 실제 이동 칸 | ≥8칸 이동 |
| ---: | --- | --- | ---: | --- | ---: | ---: | ---: |
| 11 | CONTROL | LOST | 147 | 74/32/41 | 25,850,847 | 331.798693 | 7 |
| 11 | K-LC0 | LOST | 147 | 71/33/43 | 26,029,286 | 336.899580 | 7 |
| 97 | CONTROL | WON | 136 | 64/30/42 | 24,410,331 | 310.294110 | 4 |
| 97 | K-LC0 | WON | 136 | 64/30/42 | 24,118,721 | 300.744170 | 3 |
| 2026 | CONTROL | LOST | 175 | 71/44/60 | 31,297,480 | 409.217223 | 6 |
| 2026 | K-LC0 | LOST | 181 | 78/45/58 | 32,037,091 | 432.224205 | 6 |

실제 이동은 입력별 cursor→target 합이다. 긴 이동은 사전 고정한 한 입력 ≥8칸이다.
K-LC0−CONTROL 비용 차이는 11:+178,439µs, 97:−291,610µs, 2026:+739,611µs이며
이동 차이는 +5.100887 / −9.549940 / +23.006982칸이다. 2026은 입력도 +6이다.
LOST의 종료 비용은 time-to-win이 아니다. 97의 감소와 11·2026의 악화를 모두 보존한다.

총 6회, retry/timeout/native failure 0, 922 inputs/928 frames다.
각 run의 source/dirty 상태, worker containment·reap·cleanup receipt를 별도로 보존한다.
이 6회와 [새 비교 앱 5 pair](STAGE3_K_LC0_RANDOM_EXPERT_COMPARE_CLOSEOUT.md)는
별도 work unit/실행 identity다. 반복 CONTROL이나 같은 보드 재생을 독립 표본으로 합산하지 않는다.

같은-state 여부는 observation/cursor/M_before/preinput_M 전체로 판단한다.
Claude 검산에서 active 2026/52 ≡ CONTROL 51 ≡ 인증 capture 51이 확인됐다.
반면 같은 번호나 outcome만으로 동일 상태라 할 수 없고 분기 뒤 재합류도 가능하다.
2026의 마지막 추측 목표는 양쪽 O(28,14)이지만 출발점은 (29,14)와 (0,11)이다.
그 불리한 마지막 이동도 전체 합계에 포함했다. g는 해당 active 상태의 native 선택이다.

## 검증 이력과 사용자 경로 확인

| work unit / 주체 | 실제 기록 | 범위 |
| --- | --- | --- |
| 원 K-LC0 / Codex | 152 unique / 182 method 실행; 초기 29PASS·1FAIL, fixture 수정 후 152PASS | 새30 + 직접 의존122; 전체 suite 아님 |
| 원 K-LC0 / Claude | 새30개 1회 30PASS; 저장6회 독립 검산 PASS | 922 inputs/928 frames, 후보·band·순위·비용 대조; 기존122 재실행 없음 |
| 고정 경로 viewer / Codex | 29 unique / 85 method 실행; 27PASS·1FAIL → 28PASS → 29PASS | 작은 창 높이 수정 및 설명 범위 검사; 새 solver 0 |

원 K-LC0 초기 실패는 EXACT_SAFE가 남는 fixture에서 EXACT_GUESS를 기대한 테스트 설정
오류였고 정책 변경 없이 수정했다. 수정 전 test 원문은 보존되지 않았다는 Claude 한계도 남긴다.
고정 viewer 초기 실패는 작은 창 viewport 높이였으며 수정 전후 로그를 보존했다.
Claude 원 K-LC0 판정은 **PASS / REQUIRED_FIXES 없음**이다.
이는 고정 viewer 자체의 별도 Claude UI 감사나 사용자 수용을 대신하지 않는다.

고정 viewer는 **당시 source snapshot에 묶인 역사적 검토 도구**다. review_data.py의
load_review()는 과거 manifest·세 index에 더해 원 LAUNCH_IDENTITY의316파일 전체에 대해
현재 raw SHA-256 일치를 요구한다. 문서도 인증 대상이며, 이번 문서 수정 뒤에는311개 일치/
5개 불일치다. 불일치는 README.md, ARCHITECTURE.md, docs/CURRENT_HANDOFF.md,
docs/README.md, docs/stage3-extended/README.md다. 따라서 **현재 checkout에서 새로 로딩하면
인증 실패로 거부한다**. 이 결론은 source 텍스트와 raw hash 비교로 확인했으며 load_review(),
앱·solver를 실행하지 않았다. 인증 제한을 풀거나 snapshot 복원/우회를 구현하지 않았다.
아래 viewer 동작·검증·수용 설명은 당시 snapshot에서의 역사다.
기존 PublicBoard/TracePanel/AbsoluteSeekSlider/ExhibitionPlayback에 작은 immutable
ReviewTrace/ReviewPlayer adapter를 연결했다. 인증 제한을 풀지 않았고 임의 pickle 열기는 없다.
완료 frame의 M/observation/flags/누적 비용/완료 route만 보이며 pending 중 다음 지식을 공개하지 않는다.
g/선택 설명은 ‘다음 선택의 기록’이고 계획 suffix를 완료 route로 그리지 않는다.

사용자는 당시 이 viewer가 정상 동작하고 전반적으로 경로가 더 개선되어 보임을 확인했다.
이전 보고서의 ‘사용자 검토 대기’는 당시 상태로 보존한다. 이후 새 앱에 대한
2026-11-02 발언 **“확인했고 다 괜찮은 것 같아.”**는 별도 수용이며 다음 문서에서 다룬다.
사용자가 말하지 않은 횟수/index/DPI/OS별 receipt는 만들지 않는다.

## 실행 대상 구분

현재 K-P0/K-LC0 비교에는 **새 비교 앱**을 사용한다. 일반 Windows native PowerShell과
기존 승인 venv용 안내이며 이번 문서 작업에서는 실행하지 않았다.

```powershell
Set-Location -LiteralPath 'C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:QT_QPA_PLATFORM='windows'
# 새 공개 보드 actual K-P0 / active K-LC0 앱 (시작만으로 계산하지 않음)
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m experiments.k_lc0_exhibition
```

새 앱의 `--index 314`는 다음 요청 입력란만 채운다. 저장/열기 명령은
[새 앱 closeout](STAGE3_K_LC0_RANDOM_EXPERT_COMPARE_CLOSEOUT.md)에 있다.
기존 frozen V1/K-P0 앱은 [별도 전시 closeout](STAGE3_RANDOM_EXPERT_EXHIBITION_V1_CLOSEOUT.md)의
용도/명령을 따른다. 옛 review_viewer.py는 현재 사용 앱과 나란히 실행하도록 안내하지 않는다.
원 저장11/97/2026 CONTROL/K-LC0 trace와 새 앱의 actual K-P0/K-LC0 실행·저장 pair는
각각 다른 work unit의 evidence다. 새 앱으로 옛 trace를 읽거나 같은 실행으로 취급한다고
주장하지 않는다. 원 기록과 viewer는 보존하며 이 정정으로 새 재생 기능을 추가하지 않는다.

## 보존 evidence와 다음 작업

로컬 원 구현 root: `C:\Projects\GraduationProject\K_LC0_DISTANCE_MIN_IMPLEMENTATION_2026-11-01`.
그 안의 `REPORT_KO.md`, `NEW_FILES.json`, `MANIFEST.json`, `TEST_SUMMARY.json`,
`PILOT_COMPARISON.json`, `POSTHOC_VALIDATION.json`, `review_claude/CLAUDE_K_LC0_REVIEW_KO.md`,
`review_claude/crosscheck.json`이 원 기록이다. 고정 viewer root는
`C:\Projects\GraduationProject\K_LC0_USER_PATH_REVIEW_2026-11-01`이며
`REPORT_KO.md`, `AUTHORITY.json`, `PROJECTION_RECEIPT.json`, `TEST_SUMMARY.json`,
`MANIFEST.json`과 native receipt를 보존한다. 과거 도구를 재실행하여 복구하지 않는다.

현재 문서·recovery/명시적 commit 준비는 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md)를 따른다.
문서 정정 output codex_20261102_02가 _01의 COMMIT_PLAN/USER_GIT_STEPS를 교체한다.
_01 산출물은 그대로 보존하고, 같은20경로의 문서 hash/예상 staged blob만 갱신했다.
다음 정책 개선은 다른 보드 경로 검토를 바탕으로 필요한 인근 확정 안전 수 처리 등을
사용자가 별도로 선택한다. 이번에 자동 착수하지 않는다.
D0–D5 **FINAL ACCEPTANCE PASS / CLOSED**, **PHASE1_INCONCLUSIVE_TRANSFER**,
effectiveness **NOT ESTABLISHED**, Production K/Gate P **미승인**을 유지한다.
Stage3 Extended 전체 종료·Stage4·새 package 수용을 선언하지 않는다.
