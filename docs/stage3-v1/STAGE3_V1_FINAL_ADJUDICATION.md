# Stage-3 V1 — 최종 판정

- 판정일: 2026-10-10 (Asia/Seoul)
- 판정 대상: Minesweeper Project의 동결 Stage-3 V1 알고리즘·텔레메트리·공식 100k 검증 범위
- Qualified branch: `feature/stage3-implementation`
- Qualified commit: `611984133b83be11bcd2105f401ecdddcfd68a15`

## 1. Verdict

```text
FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED

BLOCKER = 0
REQUIRED BEFORE V1 ACCEPTANCE = 0
FINAL-AUDIT OPTIONAL FINDINGS = 4
```

이 판정은 아래 고정된 구현과 공식 artifact를 V1 기준선으로 수용한다. 모든 향후 보드·실제 인간 플레이·다른 물리 모델에 대한 우월성을 보장하거나, UI 통합·ZiNi 개선·Extended 구현까지 완료됐다고 선언하는 판정은 아니다. main 병합·commit/push·기존 evidence 수정·추가 구현은 이 문서 작성으로 수행되거나 자동 승인되지 않는다.

## 2. 근거와 이번 확인 범위

### 직접 대조한 자료

1. GitHub의 위 commit에 고정된 `stage3_planner.py`, `stage3_physical.py`, 관련 planner 테스트와 algorithm spec §§22–26.
2. 업로드된 `stage3_benchmark_runner(1).py`, `stage3_telemetry.py`, `benchmark_modeled_time.py`, `benchmark_comparison.py`, 관련 telemetry/benchmark/model tests 및 동결 telemetry/benchmark spec.
3. 위 업로드 중 관련 8종 파일의 raw SHA가 G0의 `g0-inputs-before.json`에 기록된 qualified 입력과 일치하는지 대조했다. 이전 업로드 `stage3_benchmark_runner.py`와 최종 `(1)` 파일을 구분했고, manifest와 일치하는 `(1)`을 사용했다. 사용자 PC의 104개 파일을 이 세션에서 직접 다시 해시한 것은 아니다.
4. 동결 Candidate r2의 G4 검증·비교 요구, 시간 지표 분리, §13 evidence 보존 요구, G0–G5 gate 정의.
5. 제출된 P1/P2 probe 코드와 Claude의 독립 최종 감사 보고서. P1의 CRLF 정규식 실패는 보고서에 제시된 두 summary 문자열을 이용한 최소 재현으로 확인했다. WW 합계 차이·정확한 Fraction·감소율을 별도로 계산했다.

### 실행 결과의 출처

- G1 357/1276 테스트 완료, G3 세션·원본/사본 보존, G4/G5 결과 및 P2 37/37 실행 결과는 제출된 실행 보고·이전 evidence 검토를 근거로 인수한다.
- 이번 ChatGPT 판정에서 공식 100k DB나 scratchpad DB를 새로 SQLite-open하거나, P2 및 전체 unittest를 재실행하지 않았다. 독립 최종 보고서에 기재된 P2 실행 결과와 원시 `p2-result.json`을 이 환경에서 직접 읽은 것은 구별한다.
- 새 최종 보고서는 `붙여넣은 텍스트(1)(20261010-062104).txt`이며, 받은 파일의 raw SHA-256은 `e85c082ff2bf0773273db0c76cec4e9113c31ee83b94b62e417054585d453ed4`이다.

## 3. 수용하는 공식 결과와 해석 한계

대상은 `EXPERT_GENERAL_V1`, exact `[0,100000)`, 동일 고정 첫 클릭 `(0,0)`, frozen Model C이다.

| 항목 | 수용 결과 |
|---|---:|
| WW | 37,702 |
| WL | 0 |
| LW | 0 |
| LL | 62,298 |
| Stage-2 승/패 | 37,702 / 62,298 |
| Stage-3 승/패 | 37,702 / 62,298 |
| 양쪽 정확한 승률 | 18851/50000 = 37.702% |
| WW Stage-2 modeled time 합계 | 2,069,761,852,010 µs |
| WW Stage-3 modeled time 합계 | 1,446,988,223,039 µs |
| Delta: Stage-3 − Stage-2 | −622,773,628,971 µs |
| Ratio of totals | 1446988223039/2069761852010 |
| Reduction | 622773628971/2069761852010 |
| 감소율 | 약 30.089144234937% |
| WW Stage-3 빠름 / Stage-2 빠름 / 동률 | 37,702 / 0 / 0 |

P2 실행 보고는 100,000개 fingerprint의 독립 재생성 일치, 공식 Stage-3의 13,813,494개 이벤트에 대한 명시된 구조·메타데이터·summary 검사, 두 Stage의 게임별 guess 좌표·확률 시퀀스 일치를 보고한다. P2는 production comparison 함수를 다시 호출한 것이 아니라 저장된 이벤트와 동결 정수 table로 비용을 독립 합산한 검증이다. 모든 solver 결정을 처음부터 다시 계산하거나 보드를 action-by-action으로 완전 재실행한 검증으로 확대하지 않는다.

수용하는 성능 주장:

> 동결 Model C를 적용한 공식 EXPERT_GENERAL_V1 100,000보드 중 두 알고리즘이 모두 승리한 37,702게임에서, Stage-3 V1의 modeled time-to-win 합계는 Stage 2보다 약 30.089144% 감소했다. 이 corpus에서 두 알고리즘의 보드별 승패와 기록된 guess 시퀀스는 일치했고, 모든 WW 게임에서 Stage 3의 modeled time이 더 작았다.

한정 조건:

- 이 값은 CPU 연산시간, benchmark wall time, 실제 인간 플레이 시간의 30% 단축을 뜻하지 않는다.
- Model C는 같은 이동에 대해 OPEN·FLAG·CHORD를 별도 action별 비용으로 구분하지 않는다. action별 timing/CPS를 도입한 확장판에서는 결과를 다시 평가해야 한다.
- 전체 prefix 합계 3,541,557,042,287 / 2,495,947,402,601 µs는 diagnostic이다. 빠른 패배를 primary speed 개선에 섞지 않는다.
- 승패/guess 시퀀스 동등성은 이 corpus의 관찰 결과이다. 모든 보드에서의 동등성 정리나 미래 확장판의 필수 회귀 불변식으로 승격하지 않는다.

## 4. Findings 최종 처리

| ID | 최종 처리 | 판정 이유 |
|---|---|---|
| FA-01 | OPTIONAL / DEFER | G4 일회성 실행 driver·전체 명령의 패키지 내 미보존은 재현성 부채다. §13이 요구하는 reviewed verifier/comparison source와 결과는 보존됐다는 감사 결과, 원본/사본 identity, 별도 P2의 수치 재현을 함께 고려하면 현 V1 결과를 무효화할 사유는 아니다. 과거 코드를 추정 재작성해 당시 실행본이라고 표시하지 않는다. |
| FA-02 | OPTIONAL / DEFER | parent-wait 중단 lifecycle 부채다. 이번 G3는 해당 사고 없이 알려진 정상 종료를 기록했고, rev2는 불완전 capture를 정상 evidence로 수용하지 않는 경계를 갖는다. |
| FA-03 | OPTIONAL / DEFER | 게임 단위 validator의 certainty target 중복 검증은 부족하지만, actual-target을 검사하고 정확한 0/1·1/1을 만드는 adapter와 관련 테스트가 존재한다. P2는 이번 공식 artifact의 해당 필드를 별도로 확인했다고 보고했다. 일반적인 방어 강화를 완료했다고 보지는 않는다. |
| FA-04 | OPTIONAL / DEFER | planner 진입마다 timing-table 인증을 반복하는 것은 실제 코드에 존재한다. compute/운영 비용 문제이며, frozen action 선택과 모델 합계의 정확성 문제는 아니다. 최적화 시 측정과 행동 동등성 검증이 필요하다. |
| FA-05 | NOTE 유지 | G0 판정 근거의 package 외부 위치는 추적성 한계로 기록한다. 최종 기록에 출처를 연결하되 기존 G0 evidence를 고치지 않는다. |
| FA-06 | NOTE 유지 | G3 outer parent exit의 근거는 운영자 화면/보고이고, child exit와 capture 완결성은 세션 파일이다. 서로 다른 증거 수준을 유지한다. |
| FA-07 | KEEP | OPT-1은 해석 조항으로 유지한다. 실제 G3에 continuation이 없었다는 사실이 해당 계약 전체의 삭제 근거는 아니다. |
| FA-08 | 이번 수치 주장에 대해 해소 | P2가 production comparison 모듈을 호출하지 않고 동일 outcome·합계·paired deltas를 재현했다고 보고했다. 물리 모델 자체의 외부 타당성까지 증명한 것은 아니다. |
| FA-09 | 최종 주장에 필수 한정 | WW 조건부 modeled time, 고정 물리 모델, action별 비용 가정을 함께 명시한다. |
| FA-10 | 관찰 결과로 유지 | guess 시퀀스 일치는 이 corpus의 증거이며 보편적 invariant가 아니다. certainty-closure 설명을 일반 정리의 증명으로 취급하지 않는다. |
| FA-11 | 미실행 유지 | P3는 실행하지 않았다. G1 raw 테스트 evidence와 동일 source identity를 근거로 인수하며 새 test PASS를 만들지 않는다. |

OPTIONAL 4는 이번 최종 감사의 FA-01~04 집계다. 보고서가 별도로 언급한 이전 Slice-A 입력검사 순서, 반복성 연구, UI/ZiNi 등 기존 backlog를 삭제하거나 모두 해결했다는 뜻은 아니다.

## 5. P1의 실패 2건과 보고 표현

P1 원문은 `splitlines()`로 최종 줄을 검사하면서도 `Ran ...` 정규식은 원래 CRLF text에 적용했다. `^Ran (\d+) tests? in [0-9.]+s$`는 제시된 `...s\r\n` 문자열에서 기대한 줄을 찾지 못한다. 같은 문자열에 줄바꿈만 정규화한 parsing view를 적용하면 각각 `357`, `1276`을 찾는 것을 이번 세션에서 최소 재현했다.

따라서 이 두 결과는 공식 구현·G1 테스트 실패가 아니라 audit probe의 parsing 결함으로 분류한다. 원래 P1 결과는 **31/33 PASS, 2 probe failures** 그대로 보존하며, 이를 소급해 33/33 PASS로 바꾸지 않는다. 기존 보고서의 read-only 표현도 **기존 repo/DB/evidence 비변경**으로 해석해야 한다. scratchpad script·DB 사본·결과 파일 생성은 실제 쓰기였고 보고서에도 별도로 기재됐다.

## 6. Artifact identity

| Artifact | SHA-256 |
|---|---|
| Frozen protocol Candidate r2 | `45b451cebb97a1ac64e4a9e7844211741644e6f7df86f7137f09e6f5f6da10c4` |
| Accepted tooling rev2 manifest | `637631dba97a06b50e84ae658f2a12524cd1c3d0d927edf3a5079f04af4f59e4` |
| Official Stage-3 DB / accepted analysis copy | `b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e` |
| Accepted Stage-2 DB / analysis copy | `8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f` |
| G4 comparison | `f31226a660eda02a804ee41c66f233513fd950cac6f6123f36bf62578fbf5979` |
| G4 result | `09f228ee9a8ec96a934dbb94656a7cd6f03c7987640df267f5fd6818dd007cc0` |
| G5 result | `53b3dbf2a34bf16bf10c5006e55713c3cdf55f8d0656ad4f152912e93f050e68` |
| G5 evidence index | `4594bbfbaaeb049d38bfc04a1c367ea74115443c219109d905c7b806785c3ca6` |
| G5 package manifest | `2c686a92b2d5f71399dd0f154b21a2737bb21e7835662a01697305bface09a8f` |

Stage-3 main size: 473,845,760 bytes. Stage-2 main size: 712,728,576 bytes. DB identity와 G4/G5 artifact identity의 재확인 결과는 제출된 운영·독립 감사 보고를 인수한 것이다.

## 7. 마감과 다음 작업의 경계

추가 benchmark, G0–G5 반복 실행, P3 재실행, 새 독립 감사는 이번 수용 조건으로 요구하지 않는다.

남은 것은 기록 보존이다. 최종 독립 보고서, 이 판정문, 실제 실행 P1/P2 script 및 결과 JSON을 TEMP 밖의 새 archive에 바이트 그대로 복사하고 상대경로·size·SHA를 기록한다. 기존 G5 package와 report를 덮어쓰지 않는다. P1의 실패 결과와 정정 설명도 함께 남긴다. scratchpad의 1.19 GB DB 사본은 증거 보존 완료 전 임의로 지우지 않고, 이후 별도 정리 승인으로 다룬다.

V1 기술적 수용은 여기서 종료한다. 이후 ZiNi 성능 개선, Stage-3 main.py 통합, 녹화 가능한 시각 시뮬레이션, CPS/커서 속도 수동 설정, P0/P1/P2 알고리즘 확장은 별도 Extended scope에서 계획한다. 이 판정은 해당 backlog의 우선순위를 임의로 삭제하거나 바꾸지 않는다.
