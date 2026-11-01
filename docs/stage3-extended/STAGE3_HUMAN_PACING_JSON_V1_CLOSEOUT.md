# HUMAN_PACING_JSON_V1 Closeout

Recorded: **2026-11-01 (Asia/Seoul)**. Non-frozen closeout record.

**기존 JSON presentation-pacing 분석 COMPLETE / technical PASS.**
Claude 독립 산술 감사 **PASS / REQUIRED_FIXES 없음**. 이 문서는 완료된 분석의
결과와 해석 경계를 기록하며, 원본 분석·검증을 다시 실행하거나 수정하지 않는다.

## 1. 범위와 authority

원본 canonical JSON, metadata와 replacement provenance가 입력 authority다.
정확한 정수·유리수 결과는 `summary.json`의 numerator/denominator 및 원본
frame/count/H를 따른다. 보고서·이 closeout·외부 recovery와 AI 해석은 이를 대체하지 않는다.

분석 root:
`C:\Projects\GraduationProject\HUMAN_PACING_JSON_V1_2026-11-01`.
분석 당시 committed baseline은
`6b26697b7986752966b67035ecf7e3ba73465f35`였다. 이후 전시 앱의 미커밋 source,
그 실행 receipt, D5 package source와 별개다.

분석은 `results/stage3_replay_validation/final/`의 **canonical 30게임**만 사용했다.
STANDARD 20 / NO_FLAG 10, **5,065 counter events / 5,035 transitions**다.
`final_audit` 30개가 표본이며 `validation_v1_1` mirror 30개는 byte 비교 전용이다.
mirror를 추가 게임으로 합산하지 않았다. metadata 30개와 source/recovery/provenance를
포함한 입력 manifest는 94파일이다. 이 수는 게임 수나 독립 표본 수가 아니다.

| 논리 slot | 기존 rank → 선택 rank |
| --- | --- |
| NF_R002 | 2 → 6 |
| STD_R006 | 6 → 13 |
| STD_R022 | 22 → 20 |
| STD_R023 | 23 → 19 |
| STD_R024 | 24 → 17 |

slot 이름과 selected_rank는 다르다. 이 5개 replacement는 기존
`REPLACEMENT_SELECTION.md`의 provenance를 유지한다. 공통 replacement_reason만으로
개별 실패 원인을 단정하지 않는다. STD_R024/NF_R002의 반복 event 누락 기록과
Standard rank 18 mobile-origin 제외의 후속 eligibility clarification 한계도 유지한다.
superseded·rank-15 pilot·영상·PNG는 분석 표본에 포함하지 않았다.

## 2. 시간·집계 정의

- N은 counter event 수, H는 사이트 표시 human time의 정수 µs다.
  게임 overall CPS는 `N × 1,000,000 / H_us`이며, ALL pooled는 `sum(N)/sum(H)`다.
- event-span rate는 `(N−1) × 120 / (F_N−F_1)`이다. 표시 H와 capture event span은
  시작·끝 기준이 다르며 서로 같도록 강제하거나 전체 영상 길이로 대체하지 않는다.
- event index는 1부터, capture frame은 0부터다. 120/1 fps frame의 정수 차이를
  사용하고, 시간·비율은 Fraction으로 계산했다. 6자리 decimal/CSV는 half-even 표시다.
- 분위수는 정렬된 n개 중 `ceil(p×n)`번째 **nearest-rank**다.
  짝수 표본의 두 중앙값 평균인 통상 median과 다르다.
- rolling은 W=60/120 frames, 모든 정수 `q=F_1+W..F_N`에서 **(q−W, q]**다.
  왼쪽 제외·오른쪽 포함이며 CPS=`count×120/W`; 최대 동률은 가장 이른 q다.
  span이 W보다 짧으면 N/A, 유효한 빈 window는 0이다.
- transition-pooled interval, frame-pooled rolling, 게임 동일 가중 통계는 서로
  다른 집계다. 겹치는 rolling window는 독립 표본이 아니며 긴 span의 게임이 더 기여한다.

## 3. 기록된 핵심 결과

아래는 기존 보고서/summary의 값을 옮긴 것으로, 이번 문서 작업의 새 계산이 아니다.

| 범주 | 게임 / events / transitions | sum(H), s | sum(N)/sum(H), CPS | 게임 CPS 단순 평균 | 게임 CPS P50 |
| --- | --- | ---: | ---: | ---: | ---: |
| STANDARD | 20 / 3,320 / 3,300 | 715.691000 | 4.638873 | 4.677538 | 4.486019 |
| NO_FLAG | 10 / 1,745 / 1,735 | 417.917000 | 4.175470 | 4.219602 | 4.075584 |
| ALL | 30 / 5,065 / 5,035 | 1,133.608000 | **4.468035** | **4.524893** | **4.294245** |

ALL transition-pooled interval: 평균 **225.170473 ms**, P50 **166.666667 ms**,
P95 **550.000000 ms**, min–max **33.333333–1,358.333333 ms**.
반면 게임별 interval 평균의 평균은 **226.948181 ms**다.

| ALL rolling | frame-window 수 | P50 / P90 / P95, CPS | 최대, CPS |
| --- | ---: | --- | ---: |
| 0.5초 / W60 | 134,278 | 4 / 6 / 8 | **12** |
| 1초 / W120 | 132,478 | 4 / 6 / 7 | **10** |

0.5초 burst는 W60 rolling 최대다. 긴 간격은 ≥0.5초 335, ≥1초 11,
≥2초 0이며 중첩 임계값이다. delta≤18 frames가 3회 이상 연속인 maximal fast run은
158개다. 이를 손의 무동작·판단 시간·신체 한계로 해석하지 않는다.

## 4. 검증 이력과 한계

| 단계 | 기존 기록의 결과 | 범위 |
| --- | --- | --- |
| Codex 분석 | canonical 30개 검사 PASS, mirror byte 동일, 입력 전후 hash 동일 | JSON 산술·경계·합성 검사 |
| 같은 세션의 별도 `independent_verify.py` | PASS; 기록된 assertions 2,481,970 | rolling 266,756행, interval 5,035행, gap/run 493행, 게임 30 및 집계 대조 |
| Claude 독립 산술 감사 | PASS; 기록된 비교 2,511,559, 실패 0; REQUIRED_FIXES 없음 | 별도 정수/Fraction 계산, CSV/summary/보고서 및 경계·변이 대조 |
| 이번 문서 closeout | 기존 기록 읽기·명명 파일 hash 보존 확인만 | 분석·검증 스크립트 재실행 없음 |

검사 수는 각 기록의 값이며 합산해 새 독립 검증 수로 발표하지 않는다.
같은 Codex 세션의 별도 구현은 Claude 독립 감사나 인간 감사와 구분한다.
초기 rolling 합성 기대값 오류와 수정은 `execution.log` 및 Claude 보고서 §5.1에
보존돼 있다. 최종 정확 산술 대조 PASS가 그 이력을 없애지 않는다.
Claude optional 8건은 수치 결함으로 판정되지 않았으며 원본을 후속 전시에 맞춰 고치지 않았다.

30개 모두 **RECONSTRUCTED**, completeness difference 0, unresolved 0,
review_flags=[]로 확인된 기록이다. CFR COMPATIBLE 16개, 허용 terminal-tail 14개,
cursor fallback 46개를 제외하거나 event_frame을 이동하지 않았다.
이는 사이트 replay의 **화면 counter 증가 시각**이다. 실제 손 입력·판단 시간의
직접 측정이 아니며 120Hz capture를 원래 입력 기록의 해상도로 동일시하지 않는다.
±1 frame은 capture quantization 계약이지 전체 생리적·통계적 불확실성이 아니다.

모든 action_type은 UNKNOWN / NOT_CLASSIFIED다. OPEN/FLAG/CHORD별 physical pacing,
NO_FLAG→OPEN 재분류, 버튼 down/up, continuous cursor path·속도·가속도는 산출하지 않았다.
선택된 leaderboard replay는 일반 인간이나 관람객의 대표 표본이 아니다.
대표성·인과·유의성·최적 관람 속도·human-equivalent Model C를 입증하지 않는다.

## 5. 전시 앱으로의 제한된 사용

**250 ms=4 CPS** 기본, **200 ms=5 CPS / 500 ms=2 CPS** 후보는 관람용 균등 간격이다.
분석 자체는 앱 기본값을 변경하지 않았고, 후속
[Random Expert source 전시 기능](STAGE3_RANDOM_EXPERT_EXHIBITION_V1_CLOSEOUT.md)이
이 관람 설정과 수동 입력을 구현했다. 고정 간격은 원래 burst/gap 변동을 없앤다.
2026-11-01 사용자의 후속 native 수용은 그 source UI 수용이며 이 표본의 대표성,
최적 속도 또는 Model C calibration의 수용으로 확장하지 않는다.

## 6. 보존·복구와 STOP

위 analysis root의 `REPORT_KO.md`, `summary.json`, `input_manifest.json`,
`output_manifest.json`, `verification.json`, `independent_verification.json`,
`execution.log`, `independent_execution.log` 및
`review_claude/CLAUDE_REVIEW_KO.md`, `review_claude/crosscheck.json`이 상세 출처다.
CSV와 스크립트의 identity는 기존 manifest를 따른다.
`analysis.py`와 `independent_verify.py`는 기존 결과를 다시 쓰므로 **복구를 위해 실행하지 않는다**.
영상 재분석·project tests·solver·benchmark·calibration을 이번 문서 작업에서 수행하지 않았다.

Program K D0–D5 **FINAL ACCEPTANCE PASS / CLOSED**,
**PHASE1_INCONCLUSIVE_TRANSFER**, effectiveness **NOT ESTABLISHED**를 유지한다.
Production K/Gate P 미승인, Phase 2/R0-B/Actual E2/추가 profiling 재개 없음.
ZiNi final holdout `2,010,000..2,010,099`는 생성·열람·사용 금지다.
Extended 전체 종료와 Stage 4 전환은 결정하지 않았다.
현재 복구는 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md)를 따르고, 다음 work unit은 사용자가 선정한다.
