# Stage-3 V1 기록 안내

2026-10-10 (Asia/Seoul) 최종 판정: **FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED**.
동결 알고리즘·텔레메트리·공식 100k 검증 범위가 완료되었다.

- Qualified branch: `feature/stage3-implementation`
- Qualified implementation / official 100k 실행 commit: `611984133b83be11bcd2105f401ecdddcfd68a15`
- 이후 문서 정리 커밋은 위 실행 commit을 대체하지 않는다. 기존 DB·manifest·과거 보고서의 commit/status는 당시 기록 그대로 유지한다.

## 수용 결과와 한계

동결 Model C, 공식 `EXPERT_GENERAL_V1`, exact `[0,100000)`, 첫 클릭 `(0,0)` 기준이다.

| 항목 | 결과 |
| --- | ---: |
| WW / WL / LW / LL | 37,702 / 0 / 0 / 62,298 |
| WW Stage-2 modeled time-to-win 합계 | 2,069,761,852,010 µs |
| WW Stage-3 modeled time-to-win 합계 | 1,446,988,223,039 µs |
| WW ratio-of-totals 감소율 | 약 30.089144% |

승패·기록된 guess 시퀀스 동등성은 이번 corpus의 관찰 결과이며, 모든 보드의 동등성 정리나 미래 확장의 필수 회귀 불변식이 아니다. 감소율은 CPU 계산시간, benchmark wall time 또는 인간 플레이 시간의 30% 감소를 뜻하지 않는다. Model C는 같은 이동의 OPEN·FLAG·CHORD 비용을 구분하지 않는다. 전체 prefix 합계는 진단값이며 WW primary 지표와 구별한다.

## 판정·보존 자료

- [최종 판정문 원문](STAGE3_V1_FINAL_ADJUDICATION.md): Downloads 첨부의 bytes를 그대로 복사했다. 11,153 bytes, SHA-256 `e8c8d6a4126c82a03a0c3abd62342ce31dddde0402e057c3b2a3bfcb8f4bf427`.
- 외부 마감 보존 폴더: `C:\Users\User\Desktop\졸프\STAGE3_V1_CLOSEOUT_20261010`
  - [보존 설명](<../../../../STAGE3_V1_CLOSEOUT_20261010/README.md>)
  - [원본 위치·보존 상대경로·size·SHA index](<../../../../STAGE3_V1_CLOSEOUT_20261010/closeout-index.json>)
  - [문서 정리 계획](<../../../../STAGE3_V1_CLOSEOUT_20261010/doc-organization-plan.md>)
- 기존 G0–G5 evidence root: `C:\Users\User\Desktop\졸프\Minesweeper Project\stage3-official-100k-v1-6119841` ([로컬 폴더](<../../../stage3-official-100k-v1-6119841/>)). 기존 evidence/package/manifest는 수정하지 않는다.

외부 보존 자료는 Git 저장소와 별개이며 위 외부 링크는 현재 로컬 폴더 배치를 기준으로 한다.

| 감사 기록 | 보존 상태 |
| --- | --- |
| P1 | 원시 결과 **31/33 PASS · 2 probe failures**. CRLF summary parsing 결함 설명은 보존 README에 별도 기록하며 33/33으로 고쳐 쓰지 않는다. |
| P2 | 보고된 **37/37 PASS**. 실제 실행 script와 원시 결과 JSON을 보존하며 마감 작업에서 재실행하지 않았다. |
| P3 | **미실행**. 새 테스트 PASS를 부여하지 않는다. |

## 동결 기준과 다음 범위

- [동결 알고리즘 명세](../../STAGE3_ALGORITHM_SPEC_v1.md), [동결 텔레메트리·benchmark 명세](../../STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md), [명세 동결 판정](../../STAGE3_SPEC_FREEZE_ADJUDICATION.md)
- [물리 profile](../../calibration/stage3_physical_profile_v1.json), [calibration manifest](../../calibration/stage3_calibration_manifest_v1.json)
- [Extended backlog](../../STAGE3_EXTENSION_BACKLOG.md): 최종 감사 OPTIONAL FA-01~04는 비차단 **DEFER**이며, 이전 backlog까지 해결되었다는 의미는 아니다.

ZiNi 개선, Stage-3 `main.py` 통합, 시각 시뮬레이션, CPS/커서 속도 수동 설정, 알고리즘 확장은 별도 Extended 범위다. 기존 PENDING/NOT RUN 문서와 과거 판정은 당시 상태를 보존한다.
