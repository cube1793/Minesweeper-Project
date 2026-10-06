# Stage-3 Algorithm Spec v1 — 최종 동결 판정

판정일: 2026-10-06

## 1. 최종 판정

**A. STAGE-3 ALGORITHM SPECIFICATION v1 — FROZEN**

| 분류 | 건수 |
|---|---:|
| BLOCKER | 0 |
| REQUIRED BEFORE FREEZE | 0 |
| r1에 추가로 요구하는 OPTIONAL algorithm finding | 0 |

추가적인 알고리즘 의미 변경 없이 implementation 단계로 진행할 수 있다.
이 판정은 알고리즘 명세의 동결이다. Production 구현 완료, UI 완료, 모든 가능한
보드의 형식 검증, Stage-2 대비 성능 우위까지 승인했다는 뜻은 아니다.

## 2. 심사·승격 파일의 식별

심사 대상: `STAGE3_ALGORITHM_SPEC_v1_FREEZE_CANDIDATE_r1.md`

심사 대상 SHA-256:

```text
88d5a6e0066e3bdc68327b58ea7bb147a16f7671158645121356764f58cdbcdd
```

업로드된 `(1)` 사본의 실제 bytes로 위 SHA-256을 확인했다.
이전 candidate와 비교한 r1의 변경은 보고된 두 명확화뿐이다.

승격본: `STAGE3_ALGORITHM_SPEC_v1.md`

승격본 SHA-256:

```text
6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33
```

승격본은 제목·§0·§32 끝부분·§34의 상태 및 승격 기록만 변경했다.
§1–31 및 §33은 텍스트가 그대로 보존되었는지 직접 비교했다.
§34의 알고리즘 정의와 주장하지 않는 사항도 변경하지 않았다.
심사 원본은 수정하지 않았으며, 승격본은 별도 파일이다.

## 3. 이번 판정에서 직접 확인한 범위

기반 자료는 r1 전체, 이전에 제공된 Stage-2·planner·pilot source, focused test source,
calibration session/trials/manifest 원자료, 사용자가 전달한 Codex 독립 audit다.
사용자 컴퓨터의 현재 Git 저장소에 직접 접속하거나 그 작업 트리를 변경하지 않았다.

| 직접 확인 | 결과 |
|---|---|
| r1 실제 파일 해시 | 지정 SHA-256과 일치 |
| 이전 candidate → r1 차이 | 보고된 두 명확화만 존재 |
| 제공된 Stage-2 source 6개의 CRLF 정규화 해시 | pilot의 qualified-source pin과 모두 일치 |
| 기존 분석 코드·원시 calibration으로 profile 재생성 | frozen profile 및 table SHA-256과 일치 |
| Calibration sample count | warmup 24 / official 384 / invalid 73 |
| 명세의 대표 timing tick | 9개 모두 재생성 table과 일치 |
| 0–7 FLAG exact route 대 permutation 전수 oracle | 64건, 불일치 0 |
| Fraction 기반 선택 및 독립적인 all-pairs dominance 검사 | 1,000 candidate set, 불일치 0 |
| 동일 `(L,R)`와 제3의 strict dominator | 두 확인 모두 PASS |
| 첫 칸이 안전한 소형 보드 | 337 layouts / 1,011 trajectory runs |
| 위 경로의 candidate 생성·비용·안전성 | 1,424 candidate sets / 2,328 plans, 불일치 0 |
| 위 경로의 실제 실행 | 초기 OPEN 이후 3,478 actions; certainty 패배·비종료 무진전 없음 |
| 위 경로의 guess checkpoints 및 terminal | E-FIRST / L-FIRST / 기존 Stage-2 decision loop 일치 |
| 보고된 E/L 10k 합계·차이·action 합 | 산술 일치 |

소형 보드의 reference는 수정하지 않은 `analyze_position`을 실제 Engine의 최소 실행
루프에서 호출했다. 전체 `run_simple` instrumentation 경로를 다시 실행한 것은 아니다.

이번 추가 실행 환경은 CPython 3.13.5다. 공식 CPython 3.12.14 benchmark reference
환경의 재인증으로 표현하지 않는다.

**검증 범위의 한계:** Codex가 보고한 529개 테스트와 전체 10k JSONL 재검산을 이번에
다시 수행하지 않았다. 전체 10k 원본 JSONL은 이 검토 runtime에 없었다. 해당 전수
검증은 사용자가 제공한 Codex audit의 실행 근거로 구분해 사용했다. 영상 재추출도
수행하지 않았다. 소형·유한 검증은 모든 Expert 상태에 대한 증명을 대신하지 않는다.

## 4. 알고리즘 계약별 판정

### 4.1 Risk 및 current/virtual evidence — PASS

§3–7·§23은 local-first / exact-probability 경계, certainty-before-guess,
Stage-2 exact minimum 및 `(y,x)` guess 선택을 보존한다.

Stage-2의 certainty FLAG-before-OPEN 순서를 Stage-3가 바꾸는 것은 명세상 허용된
변경이다. 이미 증명된 safe/mine 행동의 순서 변경과 uncertain guess policy 변경은
서로 다르다. 후자는 V1에서 금지한다.

Virtual evidence는 현재 실행 가능한 첫 action의 순위를 평가하는 근거일 뿐이다.
Virtual-only safe OPEN을 곧바로 실행하지 않는다. 실제 FLAG 뒤의 새 observation에서
다시 추론해야 한다. 따라서 planning evidence와 execution authority가 섞이지 않는다.

### 4.2 Candidate soundness 및 V1 범위의 completeness — PASS

숫자 N, 기존 physical flag 수 F, hidden 집합 H에 대해 현재 확정 지뢰 집합과 H의
교집합을 K라 하자. `|K|=N-F`이면 남은 지뢰 수가 모두 K에 있으므로 `H-K`는 safe다.
이는 solver-generated flags가 올바르다는 기존 계약에 조건부인 결론이며, hidden
answer를 읽어 안전성을 확인하는 방식이 아니다.

`H-K`가 비어 있지 않으면 해당 setup 뒤 OPEN 또는 positive-clue CHORD를 평가할
수 있다. Direct OPEN, direct CHORD, setup→OPEN, setup→CHORD가 명확히 정의된다.
중복 제거는 terminal만이 아니라 전체 physical action sequence를 기준으로 한다.

Completeness는 명세가 정의한 V1 candidate families 안에서의 완전성이다.
모든 상상 가능한 안전한 action plan이나 global-optimal route를 포함한다는 뜻은 아니다.

숫자칸의 이웃은 최대 8개이고 reveal할 칸이 최소 1개 남아야 하므로 setup은 최대
7개다. N=8이 범위에 들어 있어도 flags==N 및 남은 hidden reveal 조건과 양립하지
않아 자연스럽게 제외된다. Zero-clue CHORD와 빈 CHORD도 선택하지 않는다.

### 4.3 Routing·E 비교·dominance·동률 처리 — PASS

L은 양의 정수 cost의 합이며 R은 양의 정수다. 따라서 E는 정수 cross-product로
정확하게 비교할 수 있고 epsilon이 필요 없다.

A가 B를 strict하게 dominate하면 `L_A/R_A < L_B/R_B`다. 따라서 해당 B를 제거해도
E-FIRST의 최종 winner는 바뀌지 않는다. 동일 `(L,R)`끼리는 서로 제거 근거가 아니며,
제3의 dominator가 있으면 둘 다 제거되는 r1 문구가 정확하다.

Held-Karp는 terminal input까지 포함해 table cost 합을 최소화한다. 동일 비용 route의
`(y,x)` lexicographic tie가 정의되어 있다. 최종 terminal `(y,x,action rank)`와 setup
sequence는 중복되지 않은 plan을 구분한다. Action-count 최소화라는 별도 목적함수는
추가하지 않는다.

### 4.4 Fallback·실행 진전·재계획 — PASS

Current-safe가 있으면 direct OPEN candidate가 있으므로 reveal plan이 전혀 없을 때
current certainty가 남았다면 FLAG fallback의 대상인 current-certain mine이 있다.
Fallback은 `(table cost,y,x)` 최소다. Certainty가 없으면 Stage-2 guess를 그대로 쓴다.

정상적인 비종료 실행에서 OPEN/CHORD는 적어도 한 hidden safe cell을 공개하고 FLAG는
한 hidden mine을 physical flag로 바꾼다. UNFLAG는 없고 이미 완료된 action을 pending
queue로 반복하지 않는다. 그러므로 이 계약하에서는 재계획만 반복하는 무진전 순환이
생기지 않는다. WON/LOST 뒤에는 더 이상 action을 실행하지 않는다.

### 4.5 Physical Model C와 첫/마지막 input 경계 — PASS

Runtime authority는 검증된 integer table이다. Logarithm·coefficient 재계산이나
validation 결과에 맞춘 refit을 하지 않는다.

원자료 재생성으로 확인한 profile SHA-256:

```text
52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b
```

Table SHA-256:

```text
7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b
```

실제 target sequence를 a1…an이라 하면 solver total은
`T(0,0) + sum(i=2..n) T(a[i-1],a[i])`다.
Replay P는 첫 `T(0,0)` 없이 연속 target transition만 합산한다.
두 측정 경계의 차이가 r1에 명시되었다. Aggregate P/H는 `sum(P)/sum(H)`다.
Auto-win flagging은 별도 물리 입력이 아니므로 비용을 더하지 않는다.

### 4.6 E-FIRST 선택 근거 — 명시된 범위에서 PASS

보고된 exact total 249438903381 및 263685929334 microseconds는
`E-L=-14247025953` 및 L 대비 `5.403028515394875%` 감소와 일치한다.
Primary criterion은 실제 action-stream total이지, 재계획에서 겹치는 predicted L의
합이나 latency percentile이 아니다.

10k 전체는 E/L paired 비교이고 실제 `run_simple` reference 범위는 첫 1,000게임이다.
이를 Stage-2 reference 10k 전수 검증으로 확대하지 않는다.

이 결과는 development corpus에서 E-FIRST를 L-FIRST보다 우선 선택하는 근거다.
Global optimum, Stage-2 대비 5.403% 향상, 실제 사람보다 5.403% 빠름, 모든 보드의
동일 승패를 증명하지 않는다.

### 4.7 Information 및 단계 경계 — PASS

Hidden layout, answer-sensitive snapshot/counter, fingerprint, 3BV/Ops, 미래 replay 및
terminal 정보와 evaluator feedback이 decision 입력에서 배제된다. Cursor는 마지막
실제 input target으로 충분히 정의된다.

Stage-4의 click-efficiency objective 및 advanced guessing은 V1에 들어가지 않는다.
No-flag retained state와 nearest-minimum guess도 현재 동결 알고리즘에 추가하지 않는다.

### 4.8 Implementation feasibility — PASS

§33이 executor/identity/telemetry/timing/pairing 및 acceptance 작업을 다음 단계로
명시적으로 이관한다. 이 부분을 이미 구현·해결된 것으로 간주하지 않는다.

정의된 planner action을 구현하지 못하게 하는 미정의 정책이나 상충 계약은 확인되지
않았다. Experimental harness는 production acceptance를 받은 코드가 아니며 그대로
production에 import하는 방식으로 승격하면 안 된다.

## 5. 동결 후에도 남는 작업

- Stage-3 planner/runner/telemetry/benchmark의 최소 통합 계약 확정.
- 공유 benchmark execution 변경 전에 accepted Stage-2 semantic-action golden 추가.
- 기존 immutable Stage-2 baseline 보존 및 실제 policy에 맞는 identity 부여.
- 구현 및 source/test review, controlled production benchmark 수행.
- Physical modeled time, compute time, wall time, action count, outcome 분리.
- Model C의 reference-operator 및 PASS WITH LIMITATION 해석 유지.

위 작업은 algorithm freeze를 다시 여는 이유가 아니라 §33이 정한 구현·acceptance
의무다. 본 판정은 추가 algorithm semantic revision을 요구하지 않는다.
다만 향후 재현 가능한 correctness 반례가 확인되면 FROZEN을 이유로 무시하지 말고,
영향 범위·버전·기존 evidence를 명시해 별도로 판정해야 한다.
