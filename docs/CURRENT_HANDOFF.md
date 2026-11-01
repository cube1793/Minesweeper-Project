# Current Project Handoff

Updated: **2026-11-02 (Asia/Seoul)** — K-LC0 user native acceptance / documentation precommit snapshot.
실제 source/tests와 실행 당시 evidence가 구현/실행 authority이고, 이 문서와 외부 recovery는
복구 안내다. 사용자 보고는 사용자 수용의 근거이며 새 자동 검증/package receipt가 아니다.

## 1. Current state and next work

**실험적 K-LC0 및 새 K-P0/K-LC0 비교 source 앱: 구현·개발 검증·Claude 독립 검토 완료,
사용자 native 수용.** 2026-11-02 사용자 최신 발언: **“확인했고 다 괜찮은 것 같아.”**
직전 안내한 새 index/추첨·표시 identity/저장, 저장8191의 Model C0.5배·독립/공통 재생·seek,
저장 열기·취소 후 재실행·닫기에 대한 수용이다. 구체적으로 보고하지 않은 횟수/index/DPI/OS,
항목별 receipt를 추정하지 않는다. 이전 고정3보드 viewer의 당시 정상 동작·전반적 경로 개선
체감은 별도 역사적 확인이다. 이 viewer는 원316파일 raw hash에 묶여 있으며 문서5개가 달라진
현재 checkout에서는 새 로딩이 인증 실패로 거부된다. 현재 실행 앱으로 안내하지 않는다.
K-LC0 freeze·일반 효과성·production 승인은 아니다.

- [K-LC0 정책·고정 경로 viewer closeout](stage3-extended/STAGE3_K_LC0_DISTANCE_BAND_V1_CLOSEOUT.md)
  — 원3보드6회 혼합 결과, Codex152unique/182회와 Claude30/30, viewer29unique/85회·새solver0.
- [새 Expert 비교 앱 closeout](stage3-extended/STAGE3_K_LC0_RANDOM_EXPERT_COMPARE_CLOSEOUT.md)
  — actual K-P0→active K-LC0, 저장/재생,5 pair, Codex107unique/179회, Claude 최종54/54,
  R-1 정정 및 이번 사용자 수용.
- [기존 V1/K-P0 전시 closeout](stage3-extended/STAGE3_RANDOM_EXPERT_EXHIBITION_V1_CLOSEOUT.md),
  [Human pacing closeout](stage3-extended/STAGE3_HUMAN_PACING_JSON_V1_CLOSEOUT.md)
  — 사용자 source 수용과 commit/push 완료한 이전 work unit. 그 문서의 precommit NEXT는 과거다.
- [D0–D5 closeout](stage3-extended/STAGE3_PROGRAM_K_RESEARCH_DEMO_CLOSEOUT.md)
  — 별도 preserved-E1 viewer/package **FINAL ACCEPTANCE PASS / CLOSED**, packaged A–H PASS.

**CURRENT NEXT: 사용자가 이번 문서 결과를 검수한 뒤 정확한20경로로 stage/commit/push를
수행할 준비가 됐다. 이번 작업은 Git 쓰기를 하지 않는다. 다음 실행 work unit은 사용자 선택이다.**
큰 수용 단위마다 docs/recovery를 함께 정리하고 Git 절차를 한 번에 전달한다.
과거 PENDING/실패/정정 전 보고서를 소급 수정하거나 오래된 NEXT를 재실행하지 않는다.

다음 선택 후보는 다른 보드 경로 기반 인근 확정 안전 수 처리 개선, 짧은 영상 pilot 후 전체
분석 필요성 판단, Main/Live 최소 알고리즘 선택 통합이다. 영상/정책 개선은 Main 통합의
무조건적인 선행 gate가 아니다. 거리 연동 기준CPS UI는 선택 개선이며 독립50/50 조기 처리/
일반guess 변경은 별도 후순위다. 어떤 후보도 이번에 자동 시작하지 않는다.
Extended 전체는 ACTIVE, milestones1–9는 CLOSED이며 전체 종료/Stage4는 미결정이다.

## 2. Live Git and source identity

repo: `C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project`.
2026-11-02 문서 작업 **시작** snapshot: main, HEAD == local origin/main ==
`3e9f3935f505ff36dd74b6fba668650ab5c1d41d`, ahead/behind0/0,
tracked 변경 없음·index 비어 있음, **기존 K-LC0 4개 + 새 비교 앱 9개 = 13 untracked**.
현재 문서5수정/2신규가 더해졌다. clean이 아니고 HEAD만으로 미커밋 실행을 식별하지 않는다.

`3e9f3935...`는 사용자가 기존 V1/K-P0 source 전시의 stage/commit/push를 완료한 기준이다.
`6b26697b7986752966b67035ecf7e3ba73465f35`는 그 이전 D5 docs/개발 baseline이다.
이번 새 commit SHA/push 완료는 아직 없다. 로컬 origin/main 확인은 새 fetch를 뜻하지 않는다.
향후 사용자 Git 뒤에는 branch/HEAD/local origin/main/ahead·behind/worktree/index와 실제 새
commit 메시지·포함 경로를 다시 확인해 recovery를 갱신한다. 기억한 SHA로 reset하지 않는다.

원4/새9의 NEW_FILES bytes는 그대로다. pilot UI c03b7c75, TEST_04 UI f770d4f0,
최종UI5b04577c는 서로 다른 실행 identity다. **Codex가 최종9파일 전체 bytes로 tests를
실행했다고 주장하지 않는다.** 최종 새54 tests 근거는 Claude54/54와 tooltip 해제 probe다.
기존 fixture CRLF SHA와 core.autocrlf=true에서 예상되는 staged LF blob을 COMMIT_PLAN에서
구분한다. stage 전 예상과 다르면 재검토하며 설정 변경/renormalize/과거 receipt 갱신은 하지 않는다.

D5 package source는 `fb59d5fa253f04f50ea57c6a9e863aa1999a517e`, root는
`results/program-k-trace-demo-final-acceptance/20261031-230251/`로 그대로다.
어떤 새 commit도 과거 pilot/package 실행 hash를 소급 대체하지 않는다.

## 3. Source use and display boundary

계보는 frozen V1 → K-P0 → 실험적 K-LC0이며 V1-LC0는 구현하지 않았다.
V1도 CHORD를 사용한다. Stage2 Simple, 원 K-P0, K-LC0는 구별하며 Main/Live selector는 미통합이다.
현재 K-P0/K-LC0 비교는 기존 승인 Python/PyQt5 환경에서 새 비교 앱을 사용한다.

```powershell
Set-Location -LiteralPath 'C:\Projects\GraduationProject\Minesweeper Project\Minesweeper-Project'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:QT_QPA_PLATFORM='windows'
# 새 actual K-P0 / active K-LC0: 시작/--index는 자동 실행하지 않음
& 'C:\venvs\minesweeper\Scripts\python.exe' -B -m experiments.k_lc0_exhibition
```

새 앱 `--open '<pair.json 경로>'`는 solver/보드 재생성/planner 없는 저장 재생,
`--small`은900×760이다. 실제8191 열기 전체 명령은 새 비교 앱 closeout에 있다.
기본 사용자 root `C:\Projects\GraduationProject\K_LC0_RANDOM_EXPERT_COMPARE_RUNS`는
고정 pilot 산출물 manifest와 별개이며 과거 외부 산출물은 새 앱의 필수 의존성이 아니다.
기존 V1/K-P0 앱의 용도/명령은 그 별도 closeout을 따른다. 옛 고정3보드 viewer는
review_data.py의 load_review()에서 원 LAUNCH_IDENTITY316파일을 검사하는 역사적 도구다.
현재311일치/문서5불일치를 raw hash만으로 확인했다. 기존 저장3보드 trace는 원 CONTROL/
K-LC0 실행 evidence이며 새 앱의 actual K-P0/K-LC0 실행이나 JSON으로 대체·재라벨하지 않는다.

공개 EXPERT_GENERAL_V1 index0..99999의 같은 layout/두 fresh session으로 child에서
K-P0→active LC0를 실행한다. native survivors/정확21/20 band/D→E→L→tie와 첫 입력 후
재계획을 유지한다. guess·추론·M·Model C 변경이나 지역 완료 보장은 없다.
현재 pair identity와 다음 요청 입력란, 전체 비용/입력과 현재 누적값을 구별한다.
공통 재생이 같은 번호/진행률을 강제하지 않는다. 완료 frame만 M/board/route/cost를 갱신한다.
수동20..10000ms/0.1..50CPS, 기본250ms·200/500ms 및 Model C 배율을 재사용한다.
관람 CPS·합성 cursor는 인간 시간/움직임 측정이 아니다. LOST 비용은 승리 시간이 아니다.

## 4. Preserved scientific / production boundary

- D0–D5 **FINAL ACCEPTANCE PASS / CLOSED**; 이 source checkpoint와 별도다.
- **PHASE1_INCONCLUSIVE_TRANSFER**, effectiveness **NOT ESTABLISHED**.
  현재 de-dup profiling **STOP / DEFER — UNBOUNDED_RESEARCH_RISK**.
- Phase2 **NOT AUTHORIZED**; R0-B/ActualE2 **NOT RUN / NOT AUTHORIZED**.
  complete R0 adjudication 및 final E2 N/concurrency/envelope는 미완료/미선정이다.
- Production K **NOT STARTED**, GateP **NOT PASSED / NOT AUTHORIZED**.
- Stage1/2/Pre-Stage3 CLOSED, Stage3 V1 CLOSED/FROZEN, ZiNi CLOSED/V1 RETAINED.
  ZiNi holdout `2,010,000..2,010,099`는 unopened/excluded다.

이는 PHASE1_NO_GO, ActualE2 failure, 비효과성 증명이 아니다.
E0/E1/R0/Phase1/E2/공식100k를 안심용으로 재실행하지 않는다.
새 package 수용·Extended 전체 종료·Stage4 시작을 선언하지 않는다.
[Extended history](stage3-extended/README.md#current-program-k-boundary)의 frozen authority를 유지한다.

## 5. Documentation output and recovery

이번 소유 output:
`C:\Projects\GraduationProject\K_LC0_DOC_CLOSEOUT_2026-11-02\codex_20261102_02`.
이는 옛 viewer 안내 정정판이다. 기존 codex_20261102_01 산출물은 보존했으며 그 COMMIT_PLAN과
USER_GIT_STEPS는 **교체됨(superseded)** 상태다. 커밋20경로는 같지만 문서 hash와 예상 staged
blob이 달라졌으므로 _02 계획/절차를 사용한다.
REPORT_KO.md, DOCUMENTATION_CLOSEOUT.json, SOURCE_SNAPSHOT.json, COMMIT_PLAN.json과
명명 보존/diff/링크·경로 확인 기록을 둔다. Desktop recovery 두 원본은 수정하지 않고
같은 파일명의 **교체용 전체 문서 사본**만 output에 제공한다. RECOVERY_CURRENT_KO.txt도 참고한다.

이번 검증은 문서 링크/경로/수치/identity/명명 hash와 Git diff/whitespace의 읽기 전용 확인이다.
source/tests13개 및 허용5문서 밖 보호 파일, 과거 산출물·Desktop 원본·Git index를 보존한다.
tests·앱·solver·영상·분석·build 실행, stage/commit/push/fetch/stash/reset/설정 변경은 없다.
복구 때 과거 실행 스크립트를 돌리지 말고 현재 source와 관련 저장 evidence만 읽는다.
검증 강도는 주장과 위험에 비례하며 일반 UI/구현에 불필요한 R0/E2급 gate를 추가하지 않는다.
