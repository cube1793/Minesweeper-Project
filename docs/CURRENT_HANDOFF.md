# Current Project Handoff

Updated: **2026-11-05 (Asia/Seoul)** — Main/Live 관람 속도·고정 CPS·정밀 입력 UI의 구현, 범위 한정 독립 검토, 사용자 native 수용 완료. 문서/Git 마감 단계.

## 현재 authority와 기능

현재 계약과 전체 실패/수정 계보는 [속도/CPS closeout](stage3-extended/STAGE3_MAIN_LIVE_PACING_CLOSEOUT.md)을 따른다. [LC1/표시 closeout](stage3-extended/STAGE3_MAIN_LIVE_K_LC1_DISPLAY_CLOSEOUT.md)은68c272e까지의 이전 checkpoint다. 사용자는 최신 UI 확인 뒤 **“좋아, 전부 통과인 것 같아.”**라고 수용했다. 현재 환경/안내 항목에 한정하며 모든 OS/DPI·preset 완주·전체 suite·고부하 처리량을 뜻하지 않는다.

- 기본 고정200ms/목표5CPS, Auto/guess OFF. 고정 모드에는 간격·목표 CPS, Model C에는 배속만 표시한다. 모드별 설정을 reset/정책/Replay 뒤에도 유지한다.
- FixedPeriod.period_ns가 유일한 고정 실행 주기다. CPS6은166,666,667ns이며 표시6과166.667ms가 보존된다. 반올림 표시 재입력/같은 주기 재확정은 phase·nonce를 변경하지 않는다.
- 고정 주기의 작은 지연(P/10 이하)은 예정 목표를 유지한다. 큰 지연은 실제 입력+P로 시작하며 backlog를 몰아 실행하지 않는다. 최소 간격0.9P, 입력은 자체 예정 목표보다 이르지 않다. 계산이 늦으면 실측 CPS는 내려간다.
- QPC perf_counter_ns와 고정 PreciseTimer, Model C의 기존 timer type을 분리한다. 원 Model C 비용/배속 관람 지연·비용 기록·정책/worker 경계는 유지한다. 원형은 perf_counter 초 단위다.
- K의 이른 VALIDATE/permit 보관 후 due 재검증→token→step1→정확ACK→NEXT를 유지한다. 수동 첫 press는 모든 정책의 Auto/guess를 끄며 원 gesture를 처리한다. 옛 owner 정리 후 명시ON으로 재인수한다.
- Simple/V1/K-P0/K-LC0/K-LC1, 세 preset의 K 새 판/FLAG-free/FLAG 준비 인수·재인수, wirev9, exact 확률·확정색·가상 커서, Replay source_type/녹화입력/참고분석 분리와 키보드 계약은 유지한다. V1/K custom은 미지원이다.
- 세 K 정책의 Main 콤보/현재 정책/분석 줄에서 “(실험적)”을 제거했다. 정책 freeze·effectiveness·Production 승인 변화는 없다.
- Human trace는 유효한 수동 판이 끝난 뒤 표시한다. 실제 Auto/준비 입력1회면 그 판의 human trace는 무효다. 단순 AutoON/정책 선택/분석만으로는 무효가 아니다.

## 근거와 남은 한계

- 최종 source327 SHA256: **a700d67dfabc6df4a9ed597c2bf0e4d228a7f4ed830bcd8a0f6495c7d78fc228**.
- 최종 독립 검토: **105 methods/1,084 subtests**, **3owner/96 Auto 입력**, probe32, 필수수정0. owner 정리, 조기입력0, 최소간격 위반0을 확인했다.
- 독립 LC1 기본5CPS 60입력 **4.903573 CPS**. V1 세10입력 구간은6CPS→5.974007,250ms→4.000381,6CPS→5.971516이다. 높은 CPS/모든 부하의 보장이 아니다.
- 주 성능지표는 (N−1)/(마지막−첫 Auto 입력 시각). 왼쪽 Counters는 기존 전체클릭/게임시간이다. 수동 prefix가 든 옛 지표를 수용 기준으로 다시 쓰지 않는다. 4.75–5.25 범위와10% 보정은 coordinator 기준이다.
- coarse clock RV-R1 FAIL은 QPC 보충에서 CLOSED. 과거 profiling/PreciseTimer LC1 성능 FAIL과 최종 UI 제품결함 D01/시험누락 D03 수정 이력을 보존한다. 옛/새 검증 숫자를 합쳐 전체 suite로 쓰지 않는다.
- OPTIONAL: editor setValue의 둥근 값 비교 의미, 부하 시 위상 재시작, 지역변수 이름에 결합된 harness. 이전 tooltip/focus/pause/초기화 및 기타 권고·절차 이탈도 각 버전 기록을 보존한다.
- **F02 NOT_VERIFIED, Qt shared FileDialog FAIL, 과거 TEMP NOT_VERIFIED** 유지. 전역TEMP 검색이나 옛 검증 루프를 재개하지 않는다.

## Git / 다음 단계

작성 기준 main/HEAD=local origin/main=**68c272e7272032cdfe9774a36d41c3686a8f375e**,0/0,staged0. source/tests22(M9/U13)+문서6의 **28경로(M14/U14)** 미커밋 단위다. 조율 root: **MAIN_LIVE_PACING_DOC_CLOSEOUT_2026-11-05/coordinator_01**.

**NEXT: 사용자 단일 USER_GIT_STEPS_KO.ps1 → 실제 receipt/부모/28경로/blob/push/clean 확인 → 새 commit에 결속한 recovery2개 → 사용자 Desktop 교체.** 이 문서의 SHA는 작성 당시 기준이며, 완료 SHA는 후속 실제 receipt/recovery/live Git을 따른다. postcommit 문구만 바꾸는 추가 commit은 만들지 않는다.

그 뒤 후보는 **같은 보드 다시 플레이**, **최대/burst CPS 측정 후 필요한 최적화**, **거리별 관람 속도 보정**이다. 같은 보드의 진행 중 허용 여부 등 세부 UX는 후속 단위에서 정한다. 아직 구현되지 않은 기능을 완료로 간주하거나, 다음 구현을 여기서 자동 시작하지 않는다.

## 영구 경계

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE. Phase2/R0-B/ActualE2 미승인/미실행. frozen 정책·Model C·holdout **2,010,000..2,010,099**·공식/formal evidence를 유지한다. 새 package/Stage4/연구 자동 시작 권한이 아니다.

구현은 별도 Codex, 독립 검토는 Claude Code, 현재 채팅은 조율·문서 마감이다. 제품 source/tests·프로젝트 Python/Qt/worker·Git 쓰기·Desktop 교체를 여기서 실행하지 않는다.
