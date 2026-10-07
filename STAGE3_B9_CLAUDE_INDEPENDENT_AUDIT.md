# Stage-3 Slice B — B9 Independent Claude Code Audit

> **감사자:** Claude Code (Opus 5.5) — B9 독립 감사
> **감사일:** 2026-10-08 (Asia/Seoul)
> **대상:** `cube1793/Minesweeper-Project` · `feature/stage3-implementation` · HEAD `de9d1dccd8eb30d6efa71805032546d260cd671a` 위의 **미커밋 Slice-B 작업트리**
> **최종 판정:** **PASS** — BLOCKER 0 / REQUIRED 0 / OPTIONAL 3
> **수정 · commit · push:** 하지 않음

---

## 1. Audit scope

- 근거 지침: `C:\Users\User\Desktop\졸프\STAGE3_B9_CLAUDE_INDEPENDENT_AUDIT_PROMPT.md` §0–§38 전부.
- 대상: Slice-B 소스(수정 7, 미추적 14), 테스트, 동결 스펙, 자격 아티팩트(`stage3-qualification-20261007`), 1회용 qualification 드라이버 5종(원본과 보관본).
- 방법:
  1. 소스와 테스트 정독(읽기 전용)
  2. 사용자가 승인한 읽기 전용 프로브 7종 실행: A, B, C, E/F, H, G selected, G full
  3. 회귀 테스트 5종
  4. 사후 보존 검증(Z)
- 증거 우선순위(§1): 실제 소스 > 실제 테스트 > 직접 실행 > 동결 스펙 > raw 아티팩트 > 생성 보고서 > AI 해석.
- 감사용 산출물은 `stage3-qualification-20261007\b9-temp\` 아래에만 있다(§24 표 참조).

## 2. Independence declaration

> **ChatGPT B8 adjudication/report and prior AI verdicts were not read or used before B9 findings and final verdict were completed.**

준수 상세:

- `STAGE3_SLICE_B_B8_ADJUDICATION.md`, `STAGE3_B8_REVIEW_EVIDENCE.zip`: 열지도, 검색하지도 않았다. 저장소 루트와 qualification 디렉터리의 비재귀 목록에도 없었다.
- `STAGE3_SPEC_FREEZE_ADJUDICATION.md`: 내용을 열지 않았다. 다만 source manifest의 파일 목록에 들어 있어서 프로브 A가 manifest 해시 검증 과정에서 이 파일의 **바이트 SHA-256만** 계산했다(내용 해석이나 표시는 없음).
- §5.5 문서 4종(DRAFT v1.1, KO 번역, BACKLOG, SLICE_A 보고서)과 §5.3 역사 문서 3종은 열지 않았다. 동결 계약과 소스만으로 모든 쟁점이 풀렸다.
- **노출 공개:** 세션 시작 시 하네스가 Claude auto-memory 색인(MEMORY.md)을 자동으로 불러왔다. 여기에 이전 단계(Pre-Stage3 배치 감사, Slice A 감사 등) Claude 판정의 한 줄 요약이 있었다. 해당 결과 파일은 열지 않았다. 이 요약들은 Slice B나 B8과 무관한 이전 단계 판정이고, 본 판정의 근거로 쓰지 않았다. 읽은 메모리는 절차 규칙 3개(감사 workflow, 프로브 실행 승인 규칙, 광범위 파일 검색 금지)뿐이다.
- B7/B7-C 보고서와 qualification JSON의 `PASS`, `BLOCKER=0` 문구는 **검증 대상 주장**으로만 다뤘다. 모든 핵심 수치는 raw DB, raw 샘플, 현재 소스로 다시 계산했다.
- subagent는 쓰지 않았다(금지 문서 접근 위험 차단).
- 독립성 영향 평가: **영향 없음.**

## 3. Repository branch / HEAD / status

| 항목 | 감사 시작 (S0) | 감사 종료 (Z) |
|---|---|---|
| branch | `feature/stage3-implementation` | 동일 |
| HEAD | `de9d1dccd8eb30d6efa71805032546d260cd671a` ("docs: freeze stage3 telemetry benchmark spec v1") | 동일 |
| `git status --short` | M 7 / ?? 14 (예상과 동일) | 바이트 동일 |
| `git diff --check` | 빈 출력, exit 0 | 동일 |
| `git diff --binary HEAD` SHA-256 | `de52bf85374d30dd2bf715af275ebdf3002a7306f47e0af1a90a9bf45b37596e` | 동일 |
| `.git/index` SHA-256 | `c5c14e44c86e63e64ce05545fb889f7b37308310437b63a555b06346e8223dcd` | 동일 |

- **수정(M) 7개:** `benchmark_runner.py`, `benchmark_statistics.py`, `telemetry_model.py`, `telemetry_schema.py`, `tests/test_benchmark_statistics.py`, `tests/test_simple_telemetry.py`, `tests/test_telemetry_collector.py`
- **미추적(??) 14개:** `STAGE3_B7C_COMPUTE_DIAGNOSTICS.md`, `STAGE3_B7_PILOT_REPORT.md`, `benchmark_comparison.py`, `benchmark_modeled_time.py`, `stage3_benchmark_runner.py`, `stage3_compute_diagnostics.py`, `stage3_telemetry.py`, `tests/test_benchmark_comparison.py`, `tests/test_benchmark_modeled_time.py`, `tests/test_benchmark_pairing_sources.py`, `tests/test_stage3_benchmark_continuation.py`, `tests/test_stage3_benchmark_runner.py`, `tests/test_stage3_compute_diagnostics.py`, `tests/test_stage3_telemetry.py`

**설명되지 않는 drift: 없음.** 프로브 A로 확인한 내용:

- tracked 변경은 정확히 위 7개다.
- HEAD 대비 Slice-A planner/runner/physical/profile과 두 동결 스펙에 변경이 없다.
- Stage-2 solver 계층(simple_*, core_engine, benchmark_board, board_analyzer, telemetry_collector, telemetry_repository)은 Stage-2 기준 커밋 `30b5057` 대비, 작업트리를 포함해도 변경이 없다. 골든 테스트와 fixture가 추가됐을 뿐이다.

## 4. Frozen contract identities

| Identity | 동결값 | 독립 검증 |
|---|---|---|
| Algorithm spec version | `1` | 스펙과 코드 상수 일치 |
| Algorithm canonical LF SHA-256 | `6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33` | 작업트리 CRLF→LF 정규화 SHA와 HEAD blob SHA가 **모두** 일치 |
| Model ID | `overlap_floor_log2_distance_v1` | 프로파일 metadata, 코드 상수, DB config 일치 |
| Profile version | `1` | 프로파일 `physical_profile_version = 1`(whole-file SHA로 고정) |
| Profile SHA-256 | `52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b` | raw bytes 일치 |
| Timing-table SHA-256 | `7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b` | 독립 재인코딩(ASCII, 콤마, dx-major) 일치. §16의 대표 tick 9개(T(0,0)=126005 … T(29,15)=578005) 일치 |
| Timing unit | `us` (tick `1_us`) | 일치 |
| Initial cursor | `(0,0)` | `run_stage3`, `ModelCEvaluation`, 저장된 config 일치 |

Production은 `stage3_physical.load_timing_table()`과 `validate_timing_table()`로 **저장된 정수 테이블만** 쓰고, fitted 계수나 공식으로 테이블을 다시 만들지 않는다(`stage3_physical.py`에 log2·계수 사용 없음). 프로파일에도 `runtime_cost_source = "timing_table_us; do not regenerate from fitted parameters"`로 명시되어 있다.

## 5. Documentation access policy actually followed

| 분류 | 문서 | 처리 |
|---|---|---|
| §5.1 권위 | `STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md`, `STAGE3_ALGORITHM_SPEC_v1.md`, `STAGE3_HANDOFF.md`, `README.md`, `ARCHITECTURE.md` | 전문 정독 |
| §5.1 권위 | `PRE_STAGE3_TELEMETRY_SPEC_v2.md` | Slice B 관련 절(§10–§38, §47–§48) 정독 |
| §5.2 실행 증거 | `STAGE3_B7_PILOT_REPORT.md`, `STAGE3_B7C_COMPUTE_DIAGNOSTICS.md` | 주장으로만 취급. 생성 스크립트와 raw 증거로 검증 |
| §5.3 역사 | REPLAY_V1_1 amendment, BUILDING, E_L pilot 보고서 | 열지 않음(필요 없음) |
| §5.4 금지 | B8 adjudication, B8 evidence zip, SPEC_FREEZE_ADJUDICATION | 열지 않음(§2 참조) |
| §5.5 생략 | DRAFT v1.1, KO v2, BACKLOG, SLICE_A 보고서 | 열지 않음 |
| 그 밖 | 실제 소스와 테스트, qualification JSON 증거, 드라이버, calibration 프로파일(코드로 파싱) | 정독 및 실행 검증 |

## 6. Provenance / hash-chain audit — Probe A: **50/50 PASS**

| 검증 항목 | 결과 |
|---|---|
| source manifest SHA `567d1f09…` | = protocol `approved_source_manifest_sha256` |
| manifest 파일 목록(tracked 전체 + 관련 untracked) | 현재 해시 **전부** 일치. untracked impl/tests 10개도 일치 |
| tracked diff SHA `de52bf85…` | 현재 = manifest = protocol = final_verification = crosscheck |
| B1–B6 source/test 해시 | manifest와 일치 |
| B7-C 진단 소스/테스트 `c345cb56…` / `70c9dd94…` | 측정 **전에** 선언된 protocol = final = 현재 |
| 진단 드라이버 `e8491dc8…` | protocol = repo 사본 = 보관 사본 |
| orchestration `qualification.py` `05b30bfc…` | manifest = repo 사본 = 보관 사본(드라이버 5종 모두 두 사본 동일) |
| protocol SHA `01521da1…` | = `b7c_results.protocol_sha256` |
| raw sample SHA `8506f2ad…` | = `b7c_results.samples_sha256` |
| game equality `7454a1e8…` 등 증거 14종 | = `final_verification.evidence_sha256` |
| 보고서 SHA | B7 `30496b98…`(314줄), B7-C `5a3e40d2…`(203줄) = final `new_reviewable_files` = crosscheck before/after |
| Stage-3 100 DB `260e8833…` / 1000 DB `5eb0c754…` | = execution = audit before/after (1000은 protocol `reference`와도 일치) |
| Stage-2 original / analysis copy `8b2adbe2…` | raw bytes 일치. 골든 fixture source, HANDOFF, 텔레메트리 스펙, crosscheck 기록과 일치 |
| status 진화 | manifest→protocol: B7 보고서와 진단 소스/테스트만 추가. protocol→final: B7-C 보고서만 추가 |
| 연대기(엄격 증가) | manifest 23:11:31 → baseline audit 23:12:42 → pilot100 23:13:00–23:13:44 → audit100 23:14:06 → pilot1000 23:14:36–23:21:40 → audit1000 23:22:41 → prefix 23:22:45 → B7-C protocol 23:34:25 → 측정 23:34:56–23:43:46 → final 23:48:32 → crosscheck 00:06:58–00:07:01(+1일) |
| DB 내부 run timestamp(UTC) | 각 실행 창(KST) 안에 있음. `elapsed_ns`가 timestamp 차이와 일치 |
| final 증거 목록에 없는 파일 | `baseline_aggregate_crosscheck.json`(이후 생성), `final_verification.json`(자기 자신)뿐이며 둘 다 정상 |

`"status": "PASS"` 필드는 신뢰 근거로 쓰지 않았다. 위 연결은 모두 실제 바이트 해시와 timestamp로 확인했다.

## 7. Stage-2 accepted baseline revalidation — Probe B: **35/35 PASS**

**접근 방식:**

- 원본은 raw SHA만 읽었다.
- SQLite는 분석 사본만 `mode=ro&immutable=1`로 열고 SELECT 전용 authorizer를 붙였다(쓰기 PRAGMA, ATTACH, DML 거부).
- 사이드카 파일은 생기지 않았고, 원본과 사본의 SHA는 전후로 같다.

| 항목 | 기대 | 독립 재계산 |
|---|---:|---:|
| games | 100,000 | 100,000 |
| WIN / LOSS | 37,702 / 62,298 | 37,702 / 62,298 |
| action_events (파일 전체 = run 1) | 20,143,304 | 20,143,304 |
| SUM(total_actions) | 20,143,304 | 20,143,304 |
| SUM(local_deterministic_count) | 18,504,755 | 18,504,755 |
| SUM(global_certainty_count) | 1,169,157 | 1,169,157 |
| SUM(probability_guess_count) | 369,392 | 369,392 |
| SUM(had_probability_guess) | 94,943 | 94,943 (= guess>0 게임 수) |
| SUM(board_3bv) / SUM(board_ops) | 17,386,388 / 1,335,630 | 동일 |
| avg 3BV / avg Ops | 173.86388 / 13.35630 | 4346597/25000 = **173.86388** / 133563/10000 = **13.35630** |

**Run identity와 lifecycle:**

- 파일에 run은 1개뿐이다.
- semantic V1 / `STAGE_2` / `SIMPLE_MINIMUM_RISK` / `{"accept_guesses":true,"initial_open":[0,0]}`
- EXPERT_GENERAL_V1, 30×16/99, `FIRST_CLICK_FIXED_0_0`, V1
- COMPLETED, requested = processed = 100,000, `git_dirty=0`, failure NULL, commit `30b5057…`
- 정확히 `[0,100000)`를 덮고, 모든 게임에서 seed = index이고 첫 클릭은 (0,0)이다.
- 따라서 **official-eligible**이다.

**합계 등식:** local + global + guess + 게임당 정책 OPEN 1회(100,000) = 20,143,304 = 전체 행동 수 = action event 행 수.

**게임 단위 검사(전수):** 모든 게임에서 행 수 = total_actions = local + global + guess + 1 = open + flag + chord.

**이벤트 단위 검사:**

- 카테고리 분포: NULL 100,000 / LOCAL 18,504,755 / GLOBAL 1,169,157 / GUESS 369,392.
- NULL 이벤트는 모두 index 0의 무시간 정책 `OPEN(0,0)`이다.
- 분석된 이벤트는 모두 count, target, timing이 non-null이다(Stage-2 V1 strictness).
- guess는 모두 OPEN이고 target과 minimum이 같다.
- certainty는 OPEN이 0/1, FLAG가 1/1이다.
- CHORD는 0건이다.

**추가 교차 확인:** 골든 fixture의 게임 0과 1(행동당 11개 필드)이 수용된 DB 행과 정확히 같다.

## 8. B1 findings — telemetry model / Stage-3 adapter

**BLOCKER/REQUIRED 없음.** 관련 OPTIONAL은 O-2(§25).

**Generic model** (`telemetry_model.py:63–84`): §5.1과 정확히 일치한다.

- Unanalyzed 이벤트는 metadata 4개와 timing이 모두 None이어야 한다.
- Analyzed 이벤트:
  - `inference_category`는 필수다.
  - `decision_compute_ns`는 bool을 제외한 non-negative int여야 한다.
  - `selection_candidate_count`는 None이거나 1 이상의 int다.
  - `target_mine_probability`는 None이거나 [0,1] 범위의 Fraction이고, GUESS에서는 필수다.
  - GUESS는 minimum도 필수이고, non-guess의 minimum은 None이어야 한다.
- `target == minimum` 같은 solver 고유 선택 의미는 generic 모델에 추가되지 않았다(올바름).

**Stage-2 adapter:** `simple_telemetry.py`는 30b5057 이후 변경이 없다(엄격 의미 유지). diff에서 테스트에 non-null int count와 Fraction target 단언이 추가되었다(`tests/test_simple_telemetry.py`).

**Stage-3 adapter** (`stage3_telemetry.py:51–124`):

- 카테고리는 `evidence.kind`로 매핑하고, candidate count는 항상 None이다.
- certainty는 **실제 실행된 `decision.move`**를 `certainty_pool(evidence)`에 대조한다. OPEN은 `0/1`, FLAG는 `1/1`이다. GLOBAL이 local 사실을 우회하면 거부한다.
- guess:
  - OPEN이 Stage-2 `evidence.move`와 같아야 하고 plan이 없어야 한다.
  - Stage-2 selector 자기검증(`decision_to_telemetry`)을 재사용해 exact minimum과 `(y,x)` tie-break를 확인한다.
  - 그 전에 좌표 유일성을 강제해 dict collapse를 막는다.
- CHORD는 LOCAL, plan 존재, 단일 zero-remaining clue, hidden ⊆ safe를 요구하고 target/min은 NULL/NULL이다. 양수 clue 값 검사는 runner가 맡는다(`stage3_runner.py:107–114`).
- 정책 OPEN은 `OPEN(0,0)`이고 timing None이면 메타데이터를 모두 NULL로 둔다.
- import 경계에는 Action, SimpleMove, DecisionKind, Stage-2 adapter, `certainty_pool`, InferenceCategory만 있다. solver 재실행, 엔진, hidden 데이터 접근은 없다.

**실행 확인:** 프로브 C가 두 pilot의 Stage-3 이벤트 158,145행(15,187 + 142,958)을 전수 검사했다. candidate NULL, OPEN `0/1`, FLAG `1/1`, guess target = min(정규 분수), CHORD NULL/NULL, event 0 전부 NULL이 모두 위반 0건이다. `tests.test_stage3_telemetry`도 통과했다.

## 9. B2 findings — Stage-2 drift protection

**BLOCKER/REQUIRED/OPTIONAL 없음.**

- 골든 fixture SHA는 `fee9f837b7bd4977e5a910feeeed987bd4c941ce895cdae449e82046cd8a49ff`로 일치하고, fixture와 테스트 모두 HEAD 대비 변경이 없다. 골든 테스트는 3/3 통과했고, fixture 내용이 수용된 DB와 독립적으로 일치한다(§7).
- `git diff --name-only 30b5057 -- <Stage-2 solver/collector/repository 10개 파일>`(작업트리 포함)의 결과는 골든 파일 2개 추가뿐이다.
- 따라서 `run_simple`, `analyze_position`, exact probability, FLAG 우선, `(y,x)` tie-break, "한 행동 → 실행 → fresh observation → 재분석" 루프는 소스 수준에서 바뀌지 않았다.

## 10. B3 findings — shared benchmark lifecycle seam

**BLOCKER/REQUIRED/OPTIONAL 없음.**

- **공개 API 시그니처 보존** (`benchmark_runner.py:373–409`): `run_benchmark(database, requested_games, *, spec, official, stop_requested, progress, repository_root)`와 `continue_benchmark(database, run_id, *, stop_requested, progress)`는 HEAD와 같다. 이제 Stage-2 `_benchmark_identity`/`_play_game`을 명시적으로 넘기는 얇은 래퍼다.
- **private seam의 범위:** `_run_benchmark`, `_continue_benchmark`, `_execute_running_run(…, play_game=…)`은 lifecycle, provenance, prefix, 실패, 진행만 맡는다. registry, plugin, DI framework는 없고 callable 두 개만 주입한다.
- **유일한 순서 변경:** identity를 writer 연결 **전에** 만든다(`:351–353`). Stage-2 identity는 순수 함수라 동작 차이가 없다.
- **예외 처리:** `except Exception`이므로 KeyboardInterrupt와 SystemExit는 FAILED로 바뀌지 않고 RUNNING이 유지된다(Stage-2와 Stage-3 테스트 모두 확인). stop은 게임 시작 전에만 확인한다. progress는 commit 후 절대 카운트로 보고한다. 실패 코드 체계는 바뀌지 않았다.

## 11. B4 findings — Stage-3 benchmark + continuation

**BLOCKER/REQUIRED 없음.** 관련 OPTIONAL은 O-2.

**Identity** (`stage3_benchmark_runner.py:45–72`):

- `telemetry_schema_version=2`, `STAGE_3`, `E_FIRST_FIRST_REVEAL_V1`, §4의 정규 config 9개 키.
- `load_timing_table()` 인증 **후에** 상수로 만든다.
- 공개 API에는 identity나 timing override가 없다(테스트 확인).

**게임 단위 경로** (`:148–197`)는 §12와 같다:

1. `generate_board`(game_index == seed 확인)
2. fresh engine, `reset_with_mines`
3. snapshot의 크기, 배치, fingerprint 확인
4. (0,0) 안전 확인
5. `analyze_board`
6. `run_stage3(engine, observer)`
7. `trace_to_telemetry`
8. Collector
9. terminal 상태와 trace 스트림 일치 확인
10. `_validate_stage3_game`
11. `reconstruct_game(record, events)` 총합이 `result.total_modeled_us`와 같은지 확인
12. lifecycle의 원자적 persistence

**Continuation preflight** (`benchmark_runner.py:250–293`): writer를 열기 전에 다음을 모두 확인한다.

- path 존재(연결 생성 전), read-only 연결, schema 검증, run 존재
- RUNNING, `git_dirty=0`, `failure_code` NULL, `finished_at` NULL
- processed/requested의 타입과 범위, 저장된 prefix가 정확한지
- module-root clean tree와 같은 commit
- identity 전체 필드(config JSON 문자열 동등성, 프로파일/테이블 인증 포함. finalize-only에서도 수행)
- 환경 JSON 동등성

그다음에만 `mode=rw` writer를 연다(없는 파일은 만들 수 없음).

**테스트 커버리지** (`tests/test_stage3_benchmark_continuation.py`):

- 거부의 무부작용: SQL trace가 SELECT와 허용된 PRAGMA뿐이고, `total_changes=0`, DB 바이트와 iterdump가 같다.
- 없는 파일을 만들지 않는다.
- Stage-2↔Stage-3 run을 서로 거부한다.
- 모든 identity 필드와 config 타입(`true`/`1`/`1.0`)을 엄격히 검사한다. 프로파일이나 테이블이 변조되면 거부한다.
- dirty, commit, 환경 불일치와 비-RUNNING 5상태를 거부한다. prefix 손상 7종을 거부한다.
- finalize-only에서도 전체 preflight를 수행한다.
- commit된 행은 보존되고, 미commit 게임은 rollback 후 그 게임만 다시 실행한다.
- requested는 확장되지 않는다.
- 중단 후 이어간 실행과 중단 없는 실행이 의미상 같다.

## 12. Physical-schema findings

**BLOCKER/REQUIRED/OPTIONAL 없음.**

- `PHYSICAL_SCHEMA_VERSION = 1`, Stage-2 `TELEMETRY_SCHEMA_VERSION = 1`(유지), `TELEMETRY_SCHEMA_VERSION_STAGE_3 = 2`(추가).
- `telemetry_schema.py`의 diff는 상수 3개를 추가할 뿐 삭제가 없다. DDL은 30b5057 이후 변경이 없다(프로브 A).
- 두 Stage-3 DB 모두 `user_version=1`이고, `sqlite_master` DDL이 수용된 Stage-2 사본과 공백 정규화 후 동일하다. `modeled_action_us`, `game_total_modeled_us`, `cursor_before`, 하위 단계 timing 컬럼은 없다(프로브 C).

## 13. B5 findings — modeled-time reconstruction

**BLOCKER/REQUIRED 없음.** 관련 OPTIONAL은 O-3(중복 인증 비용).

**`ModelCEvaluation`** (`benchmark_modeled_time.py:24–54`):

- 실제 프로파일 바이트의 SHA, 필수 metadata, 30×16 양의 정수 테이블, 테이블 SHA, `us` 단위를 인증한다.
- identity 필드는 `init=False`라 생성자나 `replace`로 덮어쓸 수 없다.
- `_require_evaluation`이 정확한 타입을 요구하므로 subclass 우회가 막힌다.
- 호출자가 경로를 넘길 수는 있지만 바이트가 동결 해시와 같아야 하므로, 임의의 identity나 테이블을 주입할 수 없다.

**`_reconstruct`** (`:141–190`)의 fail-closed 검사:

- 결과는 WIN/LOSS, `total_actions`는 0보다 커야 하고, 행 수 = `total_actions`
- index가 정확히 0..N-1
- action은 {1,2,3}, status는 {1,2,3}, bool을 제외한 int, 좌표 범위
- 첫 행동이 `OPEN(0,0)`이고 run과 game의 첫 클릭이 (0,0)
- 마지막 전까지 PLAYING, 마지막은 결과에 맞는 WON/LOST, terminal 이후 행동 없음

비용은 `T[|dx|][|dy|]`이고 커서는 (0,0)에서 시작한다. trace 비용, plan 지연, 자동 깃발, flood, solver 재실행, hidden layout은 쓰지 않는다.

**Stage별 처리:**

- Stage-2는 명시적 **post-hoc 평가**다. 저장된 config를 backfill하지 않고, 정규 Stage-2 config 문자열을 엄격히 검사한다.
- Stage-3는 저장된 선언 config가 인증된 평가 identity와 같아야 한다(`:96–138`).
- persisted 경로는 같은 연결에서 run identity를 다시 검증한다. 다른 소스의 handle은 거부된다.

**Runner ↔ reconstruction:** `_play_game`이 persistence **전에** `reconstruct_game(record, events)` 총합과 `run_stage3().total_modeled_us`가 같은지 확인한다. 재구성은 ActionEvent의 (x, y)만 쓰고 `trace.modeled_action_us`는 쓰지 않는다.

`tests/test_benchmark_modeled_time.py`의 `ExecutionEqualityTests`가 확인하는 것:

- trace, ActionEvent, DB 다시 읽기 사이의 순서 있는 `(action_type,x,y)` 동일성, 그리고 총합 3중 일치
- 총합이 다르면 persistence 전에 FAILED
- 자동 승리 깃발과 flood 깃발 해제가 비용에서 빠지는지
- 비용이 같아도 대상이나 순서가 다르면 구별되는지

**실행 확인:** 프로브 C의 독립 validator와 비용 계산으로 Stage-2 1,100개와 Stage-3 1,100개 스트림을 검사했다. 모두 유효하고, production 비교 결과와 audit JSON과 일치한다.

## 14. B6 findings — pairing / higher-level comparison / outcome-aware statistics

**BLOCKER/REQUIRED/OPTIONAL 없음.**

**Low-level pairing** (`benchmark_statistics.py:127, 322–374`):

- semantic version 쌍은 정확히 {(1,1),(1,2),(2,1),(2,2)}이고 int 타입이어야 한다. 모르는 버전은 거부한다.
- run 필드 6개(set id, width, height, mines, first-click policy, generator)는 엄격히 같아야 한다.
- 양쪽을 따로 읽어 정확히 `[0,N)`이 아니면 오류를 낸다(inner join으로 행이 사라지지 않음).
- 게임별로 seed, fingerprint, `first_click_x`, `first_click_y`가 같아야 한다.
- 연결은 호출자 소유이고 SELECT만 쓴다. ATTACH, transaction, 설정 변경은 없다(authorizer 테스트로 확인).

**Higher-level 비교** (`benchmark_comparison.py:88–184`):

- source label은 서로 달라야 하고 비어 있으면 안 된다. 둘 다 `run_id=1`이어도 구별된다.
- LEFT는 V1, `STAGE_2`, `SIMPLE_MINIMUM_RISK`, 정규 config여야 하고, RIGHT는 V2, `STAGE_3`, `E_FIRST_FIRST_REVEAL_V1`, 동결 config여야 한다.
- 역할을 뒤집으면 거부한다. 실제 아티팩트로도 확인했다(프로브 C).
- WW 분류 **전에** 모든 게임의 양쪽 스트림을 완전 재구성한다. WL/LW/LL의 손상 스트림 하나만으로도 비교 전체가 실패한다(테스트로 확인).

**공식 확인:**

| 항목 | 구현 |
|---|---|
| 1차 모집단 | WW만 |
| 합계 | S2 = ΣC2(g), S3 = ΣC3(g) |
| 차이 | delta = C3 − C2, total_delta = S3 − S2 |
| ratio | `Fraction(S3,S2)`(합계 비율이지 게임별 비율의 평균이 아님) |
| reduction | 1 − ratio(clamp 없음, 음수 유지) |
| faster/slower/tie | 부호로 판정, epsilon 없음 |
| WW = 0 | ratio와 reduction 모두 None |
| whole-prefix 합계 | 진단용만 |
| compute 시간, candidate count | 비교 지표에 없음 |

**테스트 독립성:** 손으로 계산한 Fraction(3/7, 4/7, 8/11, 7/4, −1, −3/2)과 명시적 테이블 인덱스 `T[29][15]+T[22][12]+T[5][6]`로 검증한다.

**실행 확인:** 두 pilot 모두 production 비교 결과가 독립 재계산과 **완전히 같다**(프로브 C).

## 15. B7 100-game independent recomputation — Probe C

**접근 방식:**

- `stage3_100.sqlite3`와 Stage-2 분석 사본을 `mode=ro&immutable=1`, SELECT 전용으로 열었다.
- 테이블은 프로파일 JSON에서 독립적으로 로드했다.
- 비용과 스트림 검증은 production 코드를 쓰지 않는 B9 자체 구현이다.

| 항목 | 독립 재계산 (= pilot_100_audit.json = production 비교) |
|---|---|
| lifecycle / identity | run 1개, COMPLETED, requested = processed = 100, failure NULL, V2 / STAGE_3 / E_FIRST_FIRST_REVEAL_V1, 정규 config 문자열 일치, commit `de9d1dc`, `git_dirty=1`(비공식) |
| coverage / pairing | 정확히 `[0,100)`. seed, fingerprint, first click(+ 정적 3BV/Ops)이 Stage-2와 같다. fingerprint는 동결 generator V1과 같다 |
| 완전 스트림 | Stage-2와 Stage-3 각 100개 모두 유효 |
| WW / WL / LW / LL | 38 / 0 / 0 / 62 |
| win rate | Stage-2 38/62 (19/50), Stage-3 38/62 (19/50) |
| WW 합계 (µs) | S2 2,055,912,119 / S3 1,427,225,227 / Δ −628,686,892 |
| ratio / reduction | 1427225227/2055912119 / 628686892/2055912119 (**30.579463%**) |
| 게임별 | Stage-3 빠름 38, Stage-2 빠름 0, tie 0. Δ 범위 −21,704,118 … −11,127,365 µs. 순서 있는 delta 목록이 audit과 완전히 같다 |
| whole-prefix (진단용) | S2 3,918,158,487 / S3 2,744,970,747 |
| 행동 / CHORD / guess 행 | Stage-2 22,199 / 0 / 396. Stage-3 15,187 / 5,893 / 396 |

## 16. B7 1000-game independent recomputation — Probe C

| 항목 | 독립 재계산 (= pilot_1000_audit.json = production 비교) |
|---|---|
| lifecycle / identity | 100게임과 같은 조건, requested = processed = 1000 |
| coverage / pairing | 정확히 `[0,1000)`, 모두 일치, generator V1과 같다 |
| 완전 스트림 | Stage-2와 Stage-3 각 1000개 모두 유효 |
| WW / WL / LW / LL | 405 / 0 / 0 / 595 |
| win rate | 두 Stage 모두 405/595 (81/200) |
| WW 합계 (µs) | S2 22,190,613,910 / S3 15,531,739,386 / Δ −6,658,874,524 |
| ratio / reduction | 7765869693/11095306955 / 3329437262/11095306955 (**30.007617%**) |
| 게임별 | Stage-3 빠름 405, Stage-2 빠름 0, tie 0. Δ 범위 −23,904,622 … −9,593,503 µs |
| whole-prefix (진단용) | S2 36,691,007,550 / S3 25,829,890,996 |
| 행동 / CHORD / guess 행 | Stage-2 208,720 / 0 / 3,635. Stage-3 142,958 / 55,743 / 3,635 |

**공식 모드 거부:** 두 pilot 모두 `require_official=True`가 "not official-eligible"로 거부된다. dirty Stage-3 자격 run이 공식 결과로 승격되지 않는다는 뜻이다. 프롬프트 §23(B7 qualification scope)과 일치한다. 수용된 Stage-2 사본은 official-eligible이고, Stage-3 pilot은 `official=False`, `git_dirty=true`인 비공식 자격 아티팩트다. 따라서 이 수치는 최종 100k 성능 주장이 아니다.

**참고(불변식 아님):** 두 prefix 모두 Stage-2와 Stage-3의 결과 라벨이 같고(WL = LW = 0), 모든 게임에서 guess 시퀀스(좌표와 정확 확률)가 같다. 스펙 §17.1에 따라 이것은 감사 증거일 뿐 회귀 불변식으로 요구하지 않는다.

## 17. First-100 reproducibility

- 비교 대상: `stage3_100.sqlite3 [0,100)` 대 `stage3_1000.sqlite3 [0,100)`
- 비교 항목: game_index, seed, fingerprint, 결과, 모든 비-timing GameRecord 필드, 순서 있는 행동 행(type, x, y, category, target/min 정확 분수, delta), 독립 재구성 modeled 합계
- 제외: elapsed timing, run provenance, DB surrogate ID
- 결과: **100/100 결정적 동일.** 이는 같은 Stage-3끼리의 재현성이지, Stage2↔Stage3 결과 동일성의 불변식이 아니다.

## 18. B7-C instrumentation source audit

**BLOCKER/REQUIRED/OPTIONAL 없음.**

| 요구 | 소스 근거 (`stage3_compute_diagnostics.py`) |
|---|---|
| forwarding/관찰만 | wrapper가 `original(*args, **kwargs)`를 그대로 반환한다(`:183–219`). solver 2회 실행, 행동 선택, tie-break, timeout, route heuristic, 검증 생략, DB 접근 없음(import는 `simple_decision`, `stage3_planner`, `stage3_runner`만) |
| 실제 production alias | `stage3_runner.plan_position`(complete), `stage3_planner.analyze_position`(analysis), `simple_decision.infer_deterministic`(local), `simple_decision.calculate_probabilities`(probability), `stage3_planner.generate_reveal_plans`(candidate), `stage3_planner.exact_route`(routing) (`:143–155`). 각 호출부가 실행 시점에 모듈 전역을 해석함을 확인했다(`stage3_runner.py:154`, `stage3_planner.py:220,238`, `simple_decision.py:76,87`, `stage3_planner.py:152`) |
| 7개 모집단 | complete, analysis, local_inference, probability_analysis, planner_only, candidate_generation, exact_routing |
| 중첩 fail-closed | 두 번째 context는 거부한다(`:136–137`). complete 중첩을 거부한다(`:187–188`). parent 불일치 nested 호출을 거부한다(`:207–208`). analysis와 local은 정확히 1회, probability와 candidate는 최대 1회(`:225–228`) |
| thread 가정 | `get_ident()`로 단일 진단 thread를 강제한다(`:174–176`). docstring에 명시 |
| alias 복원 | ExitStack을 `__exit__`의 finally에서 정리한다. 부분 진입 실패도 복원한다(`:156–158`). Exception과 BaseException 모두 복원(테스트로 확인). 프로브 G에서 1000게임 뒤 6개 alias 모두 원래 객체임을 확인 |
| 부재와 0 구분 | 호출이 없으면 sample이 추가되지 않고 `DecisionTiming`에 None이 들어간다. 실제 0 ns는 0으로 기록된다 |
| 동일 호출 귀속 | `planner_only = complete − analysis`(같은 invocation). 음수는 clamp하지 않고 예외로 처리한다(`:229–232`) |
| 포함 관계 라벨 | candidate가 routing을 포함한다. 합산 금지를 docstring과 protocol에 명시 |
| 초기 정책 OPEN | `plan_position`을 호출하지 않으므로 모집단에 들어가지 않는다(테스트로 확인) |
| production 경계 | complete가 원래 `plan_position` 전체(동결 테이블 검증 포함)를 감싼다(테스트로 확인) |

**동결 계약 대조(Algorithm §26, Telemetry §9/§9.1):**

- 다음이 모두 제공된다: complete, local, 실제 probability, planner-only(포함 작업 명시), candidate/routing timing, P50/P90/P95/P99/max.
- protocol이 측정 **전에** 선언되었다(23:34:25 < 23:34:56).
- 정확한 corpus `EXPERT_GENERAL_V1 [0,1000)`, 환경/소스/모델 identity, 포함/중첩 라벨, 동일 실행 귀속, 비계측 기준과의 의미 동등성(§20)이 있다.
- 역사적 Stage-2 compute 비교 주장이 없고, SQL 하위 단계 timing 컬럼이 없다.
- 결론: §9.1 B7-C 의무가 충족된다.

## 19. Raw sample independent recomputation — Probe E/F

**입력과 검사 내용:**

- `b7c_samples_ns.json.gz` SHA는 `8506f2ad…`로 일치한다.
- 키는 정확히 7개 모집단이고, 모든 sample이 bool을 제외한 non-negative int다.
- 백분위는 B9 자체 구현으로 계산했다: rank = `ceil(Fraction(p,100)·N)`(exact rational), production `summarize_samples` 미사용.

| Population | count | P50 | P90 | P95 | P99 | max (ns) |
|---|---:|---:|---:|---:|---:|---:|
| complete | 141,958 | 1,347,300 | 2,168,800 | 3,176,600 | 6,945,300 | 1,325,712,600 |
| analysis | 141,958 | 957,000 | 1,739,800 | 2,863,500 | 5,834,000 | 1,325,540,700 |
| local_inference | 141,958 | 19,100 | 27,100 | 30,300 | 44,600 | 76,764,700 |
| probability_analysis | 15,052 | 1,668,400 | 4,119,100 | 7,775,600 | 68,343,300 | 1,324,483,900 |
| planner_only | 141,958 | 303,000 | 658,800 | 802,900 | 1,117,500 | 165,826,100 |
| candidate_generation | 138,323 | 174,000 | 506,100 | 641,800 | 939,200 | 165,507,800 |
| exact_routing | 1,993,100 | 5,700 | 14,600 | 22,800 | 52,700 | 165,122,300 |

**7개 모집단 모두 `b7c_results.json`과 정확히 같다.** 빈 모집단 규약(count 0, None/N/A)도 확인했다.

**구조 검사(26/26):**

- len(complete) = len(analysis) = len(planner_only) = len(local) = 141,958 = decision_invocations.
- 모든 i에서 `complete[i] − analysis[i] == planner_only[i]`, `planner_only[i] ≥ 0`, `local[i] ≤ analysis[i]`.
- 참조 DB의 이벤트 카테고리 시퀀스와 대조했다:
  - 분석 이벤트 141,958 = complete 수
  - GLOBAL + GUESS 이벤트 15,052 = probability 수
  - non-guess 이벤트 138,323 = candidate 수
- 결정 단위로 정렬했을 때 모든 결정에서 `local + probability ≤ analysis`, `candidate ≤ planner_only`.
- 최대 tail은 게임 45의 guess 결정(complete 1.326 s, probability 경로)이다.

## 20. Instrumented / reference semantic-equality audit

**원장 구조** (`b7c_game_equality.json`):

- 정확히 1000개 항목, index 0..999가 순서대로, 중복이나 누락 없음.
- 결과 도메인 WIN/LOSS, 양의 int 행동 수와 비용, 64자리 소문자 hex digest.
- 참조 DB에서 다시 만든 digest(드라이버의 `event_tuple` 형식과 같은 JSON), 결과, 행동 수, B9 독립 비용이 **1000/1000 같다.**

**현재 소스로 재실행**(프로브 G; DB 쓰기 없음. 게임마다 비계측 1회, `ComputeDiagnostics` 하 계측 1회):

| seed (선정 이유) | 결과 | 행동 | modeled µs | 4중 비교 |
|---|---|---:|---:|---|
| 0 | WIN | 227 | 39,987,084 | 일치 |
| 5 (최단 패배) | LOSS | 2 | 306,609 | 일치 |
| 45 (진단 최대 tail) | LOSS | 83 | 15,051,393 | 일치 |
| 612 (최장 승리 = 최고 modeled 비용) | WIN | 254 | 45,356,920 | 일치 |
| 763 (guess 최다) | WIN | 239 | 42,338,729 | 일치 |
| 914 (CHORD 최다) | WIN | 225 | 39,317,489 | 일치 |
| 999 | WIN | 207 | 37,231,451 | 일치 |

4중 비교는 비계측 = 계측 = 참조 DB = B7-C 원장이다. 대상은 digest, 결과, 행동 수, modeled 비용, 비-timing GameRecord이며, 진단 호출 수가 결정 카테고리와 맞는지도 함께 확인했다.

**전체 `[0,1000)` 재실행**(단독 실행, 849 s, exit 0):

- **1000/1000 4중 일치.**
- 결정적 호출 수 {complete 141,958; analysis 141,958; local 141,958; probability 15,052; planner_only 141,958; candidate 138,323; routing 1,993,100}가 B7-C 모집단 수와 **정확히 같다.**
- 이 결정 구조로 B7-C routing sample 1,993,100개를 결정별로 정렬했을 때, 모든 결정에서 `Σrouting ≤ candidate_generation`이다.
- elapsed timing 값은 실행이나 머신 사이에서 비교하지 않았다.

## 21. Hidden-information boundary audit

**BLOCKER/REQUIRED/OPTIONAL 없음.** import, 호출 인자, 실제 흐름을 확인했다.

- **planner 입력** (`stage3_planner.plan_position:209–250`): observation, `num_mines`(공개 총 지뢰 수), cursor, table뿐이다. `analyze_position(observation, num_mines)`만 호출한다.
- **runner** (`stage3_runner.run_stage3:117–179`): 엔진의 공개 API(`status`, `width`/`height`/`num_mines`, `get_observation`, `step`)만 쓴다. `get_observation`은 PLAYING 중 HIDDEN/FLAGGED/숫자만 노출한다(`core_engine.py:377–398`). snapshot, 지뢰 배치, fingerprint 접근은 없다.
- **benchmark** (`stage3_benchmark_runner._play_game:148–197`):
  - hidden layout은 엔진 설치, 크기/배치/fingerprint 검증, (0,0) 안전 확인, 정적 3BV/Ops 계산에만 쓰고, 모두 `run_stage3` **전**이다.
  - `run_stage3`에는 engine과 observer(collector 기록 closure)만 넘긴다.
  - fingerprint와 3BV/Ops는 사후 record 필드로만 쓴다.
- **adapter / 재구성 / 비교 / 진단:**
  - adapter는 trace만 받는다.
  - 재구성은 action target, status, 결과만 쓴다.
  - 비교는 DB SELECT만 한다.
  - 진단은 공개 호출을 forwarding만 한다.
  - 모두 import에 hidden 데이터 모듈이 없다. 테스트의 AST, `runpy` 격리, snapshot 차단 검사로도 확인했다.
- 금지 입력(지뢰 배치, BoardSnapshot, fingerprint oracle, 정적 3BV/Ops, 미래 terminal 정보, 사후 평가 사실)이 행동 선택에 들어가는 경로는 없다.

## 22. Test-quality audit

"테스트 수가 많다 = 정확하다"로 보지 않았다. 핵심 영역별로 기대값이 production 로직을 반복해서 만들어지는지(self-proving 위험)를 평가했다.

| 영역 | 평가 |
|---|---|
| Stage-3 telemetry adapter | 손으로 작성한 증거와 기대 Fraction(1/3, 0/1, 1/1, 10^400 규모)을 쓴다. certainty, guess, CHORD, 정책, 타입, 중복 좌표 등 음성 fixture가 많다. `runpy` 격리로 solver, 엔진, DB, float 접근을 차단한다. **독립적** |
| continuation preflight | sqlite connect를 계측하고 SQL trace, `total_changes`, iterdump, DB 바이트를 비교한다. 거부 경로 20여 종이 있다. **독립적** |
| modeled-time 재구성 | 기대 합계를 명시적 인덱스(`T[0][0]+T[2][1]+2·T[1][1]`)로 만든다. §17.6 음성 fixture 전부와 비용은 같고 순서가 다른 경우까지 다룬다. **독립적** |
| cross-source pairing | 합성 fixture, SELECT 전용 authorizer와 trace로 caller 소유를 증명한다. **독립적** |
| WW 통계 | ratio·reduction·mean-of-ratios를 손 계산 Fraction으로 확인한다. fixture의 `persist()` 비용 helper는 production과 같은 공식을 반복하지만, 결론을 좌우하는 단언은 T[0][0]의 배수 비율과 명시적 인덱스 테스트에 의존한다. 위험 **낮음** |
| B7-C 계측 | 명시적 tick 시퀀스의 fake clock과 `wraps` spy로 실제 호출 수를 대조하고, 계측과 비계측 runner를 비교한다. **독립적** |

**B7-C 테스트 이력**("초기 24개 → 21 PASS/2 FAIL/1 ERROR, 수정 후 24/24"):

- 실패했던 원본 테스트는 **보존되어 있지 않아** 역사적 diff를 검토할 수 없다(§27).
- 현재 소스와 테스트로 본 설명의 개연성은 높다.
  - `[[0, H]]` fixture에서 직접 safe OPEN과 0-clue의 remaining OPEN이 각각 `add()` → `exact_route`를 호출한다. dedup은 그 뒤(`setdefault`)에 일어나므로 실제 routing 호출은 **2회**다(`stage3_planner.py:151–167`).
  - 그래서 현재 fake clock에는 tick이 정확히 12개 필요하다(complete 2 + analysis 2 + local 2 + candidate 2 + routing 4). routing 1회를 가정하면 tick이 모자라고, 이것이 "clock fixture가 짧았다"는 설명과 맞는다.
- 수정된 테스트 해시(`70c9dd94…`)는 측정 **전에** 선언된 protocol(23:34:25)에 기록되어 있다. 따라서 수정은 측정보다 앞섰다.
- "테스트 기대값만 고쳤다"는 주장은 원본 소스 해시가 없어 직접 증명할 수 없다. 다만 현재 소스는 24/24 통과하고, 측정 전 선언 해시와 같다.

## 23. Regression execution

**실행 조건:**

- `.venv` CPython 3.12.14, SQLite 3.53.1(저장된 환경과 같음)
- 공통 환경 변수: `GIT_OPTIONAL_LOCKS=0`, `PYTHONDONTWRITEBYTECODE=1`, `python -B`
- 로그 위치: `b9-temp\t*.log`

| # | 명령 | 결과 |
|---|---|---|
| T1 | `-m unittest tests.test_stage2_semantic_golden -v` | **Ran 3, OK** (0.436 s) |
| T2 | `-m unittest tests.test_stage3_compute_diagnostics -v` | **Ran 24, OK** (0.032 s) |
| T3 | B1–B7 통합: final_verification의 INTEGRATED 19모듈 + `tests.test_stage3_compute_diagnostics` | **Ran 548, OK** (32.9 s). 기록된 B1–B6 524에 24를 더한 값과 맞다 |
| T4 | 확장 non-UI 41모듈(프롬프트 §31 목록 그대로) | **Ran 1120, OK** (58.3 s). 기록값 1120과 같다 |
| T5 | 전체 discovery `-m unittest discover -s tests -v` (`QT_QPA_PLATFORM=offscreen`, `QT_QPA_PLATFORM_PLUGIN_PATH=<venv>\Lib\site-packages\PyQt5\Qt5\plugins\platforms`) | **Ran 1276, OK** (62.2 s). FAIL / ERROR / SKIP 0 |

- **제외 모듈 없음.** 이전 B7 qualification에서 제외했던 UI 모듈 7개(`test_benchmark_statistics_ui`, `test_live_analysis`, `test_live_auto`, `test_replay_analysis_ui`, `test_replay_statistics`, `test_stage3_calibration_tool`, `test_zini_worker_dispatch`)도 이 환경에서는 플러그인 경로만 지정하면 통과한다.
- UI 소스, 테스트, 의존성은 바꾸지 않았다(환경 변수는 해당 프로세스에만 적용).
- 전체 discovery까지 실제로 완료했으므로, 이 작업트리에 대해 **전체 스위트 1276/1276 PASS**라고 말할 수 있다.

## 24. Artifact / source preservation

사전 스냅샷(S0)과 사후 스냅샷(Z)을 비교했다. Z는 G full 프로세스가 끝난 것(exit 0, `b9_g_full.json` 생성)을 확인한 뒤에 실행했다. 6종 모두 **바이트 동일**이다.

| 스냅샷 | 내용 | 결과 |
|---|---|---|
| `worktree.tsv` | `.git`과 `.venv`를 뺀 저장소 전체 파일(경로, 크기, mtime), 1,040개 | 동일 (`__pycache__`, ignored 경로 포함, 신규/변경 0) |
| `gittop.tsv` | `.git` 최상위 파일(크기, mtime) | 동일 |
| `hashes.txt` | `.git/index`, 원본 DB, qualification JSON/gz/sqlite 전부, 드라이버 10개 | 동일 |
| `changed_files.txt` | status의 21개 파일 SHA-256 | 동일 |
| `status.txt` / `diffsha.txt` | `git status --short`, `git diff --binary HEAD` SHA | 동일 |

- 최종 `git diff --check`: 빈 출력, exit 0. 최종 `git status --short`: 감사 시작과 동일(§3).
- 핵심 해시(전후 동일):
  - 원본/분석 사본 `8b2adbe2…`
  - stage3_100 `260e8833…`, stage3_1000 `5eb0c754…`
  - `b7c_samples_ns.json.gz` `8506f2ad…`, `b7c_game_equality.json` `7454a1e8…`, `b7c_protocol.json` `01521da1…`, `b7c_results.json` `6f21cf07…`
  - `final_verification.json` `3d8f8b8f…`, `source_manifest_b7.json` `567d1f09…`
- SQLite 사이드카(-wal, -shm, -journal)는 생기지 않았다. 감사 후 남은 프로브 프로세스는 없다.
- **B9가 새로 만든 영속 파일:** `b9-temp\`(프로브 스크립트 7개와 기대 SHA 목록, 결과 JSON/JSONL, 로그, 스냅샷), 그리고 본 보고서 1개뿐이다. Claude 메모리, 색인, 기존 문서, 소스, 테스트, 증거, Git metadata는 수정하지 않았다.
- 실행한 프로브 스크립트 SHA-256(승인된 계획에서 기계적으로 추출하고 검증함):

```text
7795c00e211a30fc99e1778f504f2d723a94b291d2eb6f02de6eb7edcf4cdba2  b9_common.py
fc7cedffa87fe2f994d070ec7c0ab81c78a9cb391c76a19800b58ca2801c9930  b9_probe_a_provenance.py
0c132b945d25d5b5f8d5ecb2c09425818c22f997786ef580ed4fa775f3b40c98  b9_probe_b_stage2.py
cc0c04f3726dff53de59cbf9e900663d66d7a6454afd9ae76f7d7f1bc73dd43b  b9_probe_c_stage3.py
8cc2463036c017c99e9db69b309606b28bdca3307ee6d02a1f9c8da545628289  b9_probe_ef_b7c.py
7e4eae638aae8f2505542c07c59fcda8a6784a9bff29781b195b3c10af4c4a14  b9_probe_h_auth_cost.py
30cdac3721cdc93f38f321edd3166d896f7dbf8d74f8051603a87b029d91e226  b9_probe_g_rerun.py
```

- 실행 절차상 공개할 사항: 첫 G full 백그라운드 실행은 셸 exit code가 Python exit code를 보존하지 않는 형태(`; echo`)였다. 사용자 지시에 따라 이를 중단했고, 남은 python 프로세스가 0개임을 확인한 뒤 exit code를 보존하는 형태로 **단독 재실행**했다. 결과(exit 0)는 이 재실행분이다. 중단된 실행은 b9-temp 안의 자체 로그만 남겼고, 그것도 재실행에서 덮어썼다.

## 25. Findings

**BLOCKER: 없음.**

- hidden 정답 oracle, 잘못된 주 속도 지표, 기준선 손상, 무효 스트림 수용, 동결 알고리즘 위반의 증거가 없다.
- §6–§24의 독립 재계산, 재실행, 소스 추적이 모두 반증 없이 일치했다.

**REQUIRED: 없음.**

- 필수 검증 누락, 미구현 동결 계약, 오해를 부르는 자격 증거, 의미 있는 회귀 보호 공백을 찾지 못했다.

**OPTIONAL: 3건.**

### B9-O-1 — 자격 테스트 결과가 기계적으로 캡처되지 않고 전사됨

- **ID:** B9-O-1
- **Classification:** OPTIONAL (증거 위생)
- **Affected files:** `results/stage3_b7_qualification/finalize_reports.py`(보관본 `qualification_drivers/finalize_reports.py`), `final_verification.json`의 `test_runs`, 두 B7 보고서의 "Verification appendix"
- **Evidence:**
  - `finalize_reports.py:14–20`이 테스트 결과(count/pass/fail/error/skip/seconds)를 **리터럴 상수** `RUNS`로 정의한다. `:37–39`는 이 값을 "Actual unittest-reported runs" 표제 아래에 출력한다.
  - qualification 디렉터리에 unittest 원 출력 로그나 그 해시가 남아 있지 않다.
  - 초기 B7-C 실행(21/2/1)의 실패 출력도 남아 있지 않다.
- **Contract:**
  - 프롬프트 §31("Record actual unittest counts")
  - Telemetry spec §9.1, §17.9의 증거 보존 취지
  - 증거 우선순위상 raw가 생성 보고서보다 앞선다.
- **Why it matters:** 보고된 테스트 증거는 사람이나 에이전트가 옮겨 적은 값이다. 전사 오류가 있어도 아티팩트만으로는 찾아낼 수 없다.
- **Executable confirmation:**
  - B9 재실행 결과: golden 3/3, diagnostics 24/24, 통합 548(= 524 + 24), 확장 non-UI 1120/1120. **현재 주장된 수치는 정확하다.**
  - 초기 실패 이력(21/2/1)은 검증할 수 없다(§22, §27).
- **Minimum required fix:** Slice-B 수용을 위해서는 필요 없다. 이후 자격 게이트(예: 최종 100k)에서는 unittest stdout/stderr 원 로그와 SHA-256을 아티팩트 디렉터리에 보존하고, 수치를 로그에서 파생하거나 "전사됨"이라고 표시하기를 권장한다.
- **Acceptance impact:** 없음(정확성이나 진실성 결함이 아니고 수치가 재현됨).

### B9-O-2 — certainty 행동의 위험 메타데이터 값을 adapter만 강제함 (심층 방어 공백)

- **ID:** B9-O-2
- **Classification:** OPTIONAL (hardening)
- **Affected files:** `stage3_benchmark_runner.py:105–125`(`_validate_stage3_game`), `benchmark_runner.py:100–120`(`_validate_baseline_game`)
- **Evidence:**
  - Stage-3 게임 불변식은 다음을 검사한다: 정책 이벤트, 분석 여부와 candidate NULL, guess의 exact minimum OPEN, CHORD NULL/NULL.
  - 그러나 **non-guess OPEN의 target이 `0/1`, FLAG의 target이 `1/1`, minimum이 NULL인지**는 다시 검사하지 않는다. generic `ActionEvent`는 §5.1 의도대로 non-guess target NULL을 허용한다.
  - Stage-2도 마찬가지다. 의도된 generic 완화 뒤에는 분석 이벤트의 count/target non-null을 integration 수준에서 다시 검사하는 곳이 없다. adapter(`simple_telemetry`), 그 단위 테스트, `[0,2)` 골든이 막고 있다.
- **Contract:** Telemetry spec §6.2의 의미 정의와 §5.2. §8 불변식 목록은 게임 수준 재검사를 요구하지 않으므로 **계약 위반은 아니다.**
- **Why it matters:** adapter가 회귀해서 certainty 행동에 NULL target을 내보내면, generic 모델은 그것을 받아들이고 게임 불변식도 놓친다. 그 경우 단위 테스트나 골든에서만 잡힌다.
- **Executable confirmation:** 위반 사례는 없다.
  - 프로브 C가 두 pilot DB의 Stage-3 158,145행과 Stage-2 prefix 행을 전수 검사했다.
  - 프로브 B가 수용된 100k 데이터를 전수 검사했다.
  - 어디에도 위반이 없었다.
- **Minimum required fix:** 선택 사항이다. `_validate_stage3_game`에 certainty OPEN `0/1`, FLAG `1/1`, minimum NULL 단언을 추가하고, 원하면 Stage-2 baseline 불변식에 count/target non-null 단언을 추가한다. 의미 변경은 없다.
- **Acceptance impact:** 없음.

### B9-O-3 — 결정마다 반복되는 동결 테이블 재검증 비용 (격리 측정됨)

- **ID:** B9-O-3
- **Classification:** OPTIONAL (performance, DEFER)
- **Affected files:**
  - `stage3_planner.py:219`(`plan_position`마다 `validate_timing_table`)
  - `stage3_runner.py:137`(게임마다 `load_timing_table`)
  - `stage3_benchmark_runner.py:189–192`(게임마다 `authenticate_model_c`)
  - `:52`(run마다 identity 인증)
- **Evidence:** 프로브 H, 같은 머신에서 잰 참고용 마이크로벤치다.
  - `validate_timing_table`: 중앙값 **82.5 µs/호출**(p90 83.9)
  - `load_timing_table`: 234.4 µs
  - `authenticate_model_c`: 236.5 µs
  - 1000게임당 결정적 호출 수는 각각 141,958 / 1,000 / 1,000이다.
  - 따라서 결정마다 하는 재검증은 B7-C planner_only P50(303 µs)의 약 27%, complete P50(1.347 ms)의 약 6%, 1000게임당 약 11.7 s다.
  - 게임마다 하는 인증 두 종류는 1000게임당 약 0.47 s로, pilot wall time(약 423 s)의 0.1% 수준이다.
- **Contract:**
  - Algorithm §25: 시작 시 프로파일과 테이블 SHA를 검증한다.
  - Telemetry §9: complete 경계에 `plan_position`의 테이블 검증이 포함되며 따로 빼지 않는다.
  - Telemetry §10.2: 재구성 경계에서 실제 프로파일 바이트를 인증한다.
- **Why it matters:** B7 보고서들은 중복 인증 비용을 "격리 측정하지 않았다"고 적었다. 이번 측정으로 두 가지가 정량화됐다. B5 평가기 인증은 무시할 수준이지만, planner 내부에서 결정마다 하는 재해시는 planner-only compute의 상당 부분을 차지한다.
- **Executable confirmation:** 프로브 H(`b9-temp\b9_h_auth_cost.json`)와 B7-C planner_only 분포(§19).
- **Minimum required fix:** Slice B에는 없다. §26 표에 따라 **지금은 모두 KEEP**한다. 결정마다 하는 재검증의 최적화(예: 한 번 인증한 불변 테이블 타입)는 **DEFER**한다. 별도로 버전을 매긴 compute 최적화 변경으로, 새로 선언한 B7-C형 protocol과 의미 동등성 재검증을 거쳐 다루는 것이 맞다. B9에서는 최적화하지 않았다.
- **Acceptance impact:** 없음.

## 26. Optional observations (집계하지 않음)

### 26.1 중복처럼 보이는 설계 요소 (프롬프트 §33)

| 요소 | 중복처럼 보이는 이유 | 제거 시 잃는 것 | 측정 비용 | 권고 |
|---|---|---|---|---|
| `plan_position` 안에서 결정마다 하는 `validate_timing_table` | 같은 게임에서 `run_stage3`가 이미 검증했다 | 공개 planner API가 어떤 호출자의 테이블이든 동결 identity를 보장하는 성질. 동결 §9 compute 경계의 의미(바꾸면 Slice-A planner와 timing 경계 변경) | 약 82.5 µs/호출 | **KEEP**(V1/Slice B). 최적화는 **DEFER** |
| `run_stage3(table=None)`에서 게임마다 하는 `load_timing_table` | run 시작 시 identity 인증이 같은 파일을 읽었다 | 게임 사이에 프로파일이 바뀌는 경우까지 매 게임 런타임 테이블을 인증하는 성질 | 약 0.23 ms/게임 | **KEEP** |
| `_play_game`에서 게임마다 하는 `authenticate_model_c` | runner가 같은 테이블을 이미 로드했다 | 재구성 경계의 독립 인증(§10.2). runner↔reconstruction 동등성 검사가 코드 경로상 독립이라는 성질 | 약 0.24 ms/게임 | **KEEP** |
| config의 `physical_model_id`/version과 hash 동시 보유 | identity 정보가 겹친다 | 사람이 읽을 수 있는 식별자, 또는 정확한 아티팩트 identity(§4) | 없음 | **KEEP** |
| config `initial_open`과 run first-click 필드 | 겹친다 | 실행 정책의 명시성과 Stage-2 패턴과의 일관성(§4) | 없음 | **KEEP** |
| `Stage3ActionTrace.cursor_before`, `modeled_action_us` | target에서 재구성할 수 있다 | runner와 재구성 사이의 독립 동등성 증거(§10). DB에는 저장하지 않음 | 메모리만 | **KEEP** |

### 26.2 기타 관찰

- 전체 discovery가 Qt 플러그인 경로만 지정하면 1276/1276 통과한다. 이전에 UI를 제외한 것은 이 환경에서는 필요하지 않았다.
- 두 pilot에서 결과 라벨이 같고(WL = LW = 0) guess 시퀀스도 같은 것은 증거일 뿐, 스펙 §17.1에 따라 불변식으로 만들지 않는다.
- README와 ARCHITECTURE의 모듈 및 테스트 목록에 Pre-Stage3와 Stage-3 모듈이 없는 문서 drift는 Slice B 이전부터 있던 부채다. HANDOFF §11이 연기 항목으로 분류해 두었으므로 집계하지 않는다.

## 27. Limitations

1. **B7-C 초기 실패 원본이 보존되지 않았다.** 실패했던 테스트 버전과 그 당시 소스 해시가 없으므로, "테스트 기대값만 고쳤다"는 주장은 직접 증명할 수 없다. 현재 코드로 개연성을 평가했고, 수정이 측정 전에 이뤄졌다는 것만 해시와 연대기로 확인했다(§22).
2. **B7-C 측정 환경 통제는 사후 검증이 불가능하다.** "동시 테스트 없음"이나 호스트 활동은 확인할 수 없다. elapsed 분포는 기록된 값을 썼고, 대신 내부 정합성(동일 호출 산술, 중첩, 개수, DB 구조와의 정렬, 결정적 호출 수)을 전수 검증했다. elapsed 값 자체는 다시 측정하거나 비교하지 않았다.
3. **프로브 H는 참고용이다.** warm cache 상태에서 감사 시점에 같은 머신으로 잰 마이크로벤치이며, B7-C 모집단이나 성능 주장이 아니다.
4. **일부 검증은 production 코드를 실행한다.** 프로브 G와 테스트가 그렇다. 독립성은 불변 참조 DB, B7-C 원장, B9 자체 digest와 비용 구현과의 대조로 확보했다.
5. **원본 Stage-2 DB는 해시만 확인했다.** 바이트가 같은 분석 사본으로 모든 SQLite 검증을 수행했다.
6. **단일 환경이다.** qualification과 같은 머신과 환경(CPython 3.12.14, SQLite 3.53.1)에서만 실행했고, 다른 플랫폼에서의 재현성은 시험하지 않았다.
7. **Slice B가 바꾸지 않은 기존 동작은 다시 감사하지 않았다.** 예를 들어 Stage-2 solver 내부, repository writer 설정, 읽기 전용 연결의 WAL 사이드카 동작이 그렇다. Slice B가 의존하는 범위만 확인했다.
8. **독립성 노출이 있었다.** auto-memory 색인의 이전 단계 요약을 보았다(§2). 근거로는 쓰지 않았다.

## 28. Final verdict

```text
PASS

BLOCKER  = 0
REQUIRED = 0
OPTIONAL = 3   (B9-O-1 증거 위생, B9-O-2 심층 방어, B9-O-3 성능 DEFER)
```

**근거 요약:**

- 실제 소스와 테스트 정독, 직접 실행, 동결 스펙, raw 아티팩트가 서로 모순 없이 일치한다.
- Stage-2 기준선 100k를 독립 재계산한 값이 정확히 같다.
- Stage-3 100/1000 pilot의 lifecycle, identity, 완전 스트림, pairing, WW 통계를 원시 행에서 다시 계산한 값이 audit JSON과 production 비교 결과와 같다.
- 첫 100게임 재현성 100/100.
- B7-C raw 샘플 통계가 정확히 같고 동일 호출 귀속이 성립한다.
- 계측/비계측 의미 동등성이 전체 1000게임에서 4중 일치하고, 결정적 호출 수가 같다.
- hidden 정보 경계 위반이 없다.
- 전체 테스트 1276/1276 통과.
- 아티팩트, 소스, Git 상태가 바이트 단위로 보존되었다.

B9는 수정, commit, push를 하지 않았다. B9 이후의 조치(finding adjudication, commit 여부)는 사용자와 후속 절차가 결정한다.
