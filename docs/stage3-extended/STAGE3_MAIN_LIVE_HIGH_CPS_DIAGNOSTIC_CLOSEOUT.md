# Main/Live 고속 CPS 제한 진단 closeout

기준일: **2026-11-05 (Asia/Seoul)**. 실제 측정·수용 source는 `main` / **cd8ee2ef23a2753f858f8945d7a9bff1580369fb**, source333이다. 이 문서의 후속 문서 commit을 과거 실행 HEAD로 소급하지 않는다. 현재 Git 마감 상태는 실제 receipt와 live Git을 우선한다.

## 1. 판정과 범위

**COMPLETE_BOUNDED_DIAGNOSTIC / 독립 검토 수용**, 필수 증거 수정 0, 제품 결함 0이다. 환경 복구, 외부 관측 도구 보완, V1/K-LC1의 0ms 여섯 run, 원시 산술 및 정리의 한 묶음에 한정한다. 제품 source/tests·정책·wire·시계·timer·Model C는 변경하지 않았고 최적화는 **NOT_PERFORMED**다.

이 결과는 합성 공개 저부하 fixture와 공통 하네스 아래의 관측이다. 자연 판 처리량, 순수 제품의 안정 CPS 상한, native paint/실제 표시 지연, effectiveness 또는 Production 승인이 아니다. 기존 [속도/CPS 계약](STAGE3_MAIN_LIVE_PACING_CLOSEOUT.md)과 [같은 보드/Replay 기능](STAGE3_MAIN_LIVE_SAME_BOARD_CLOSEOUT.md)은 유지한다.

사용자 지시에 따라 작은 환경/도구 수정마다 독립 검토를 요구하지 않았다. Codex가 이 단위를 마친 뒤 Claude가 원시 자료와 도구를 한 번에 검토했다. 이후에도 관련 결과가 모였거나 큰 단위가 완료됐을 때 묶어서 검토한다.

## 2. 실행과 실패 보존

- 이전 Unit1은 Python 시작시도 1/exit101, policy owner 0, 보수 실패 4/요청상한 2로 **PARTIAL**이었다. 당시 command/tree **NOT_VERIFIED**를 현재 결과로 덮지 않는다.
- RESUME은 승인된 실행 경계에서 P00을 통과했다. 이는 그 경로의 실행 가능성 확인이며 이전 exit101 원인의 완전한 인과 증명이 아니다.
- P01은 무owner 검증을 통과했지만 repo를 먼저 import 경로에 넣어 실제 sitecustomize 시작 순서 공백을 놓쳤다. C01 뒤 P01을 다시 실행한 것으로 소급하지 않는다.
- **C01**: 첫 `R01_V1_MIN1`은 worker bootstrap import 오류였다. 원 proposal까지 나왔으나 Auto 전 observer-ready 확인에서 멈춰 actual/ACK 0이었다. 원 reap/tree0/channel/handle 정리 뒤 경로를 보완하고 `R01_V1_MIN1_C01` 한 번만 대체했다. 성공 여섯 run은 모두 C01 이후 같은 timed signature다.
- **C02**: 마감 PowerShell owner 집계가 없는 필드를 참조한 오류다. 한 번 보정했으며 추가 Python/owner/입력은 0이다. 최초 실패는 합쳐진 도구 출력이라는 capture 한계를 보존한다.
- 실제 경과 **44.060분**, Python **10/12**, policy owner **7/8**(실패 actual0 1회+성공 6회), C 보정 **2/2**, 동시 owner 1이다. 성공 측정의 Auto-span 합 48.5448004초와 전체 경과를 구분한다.
- owner 7개 모두 원 reap/tree0/channel 삭제/Job·process handle 닫힘, top-level launcher 10개 handle dispose를 확인했다. 정상 ACK62 뒤 bounded retire의 worker CANCELLED/exit1은 top-level helper 실패와 다르다. 모든 일시적 OS spawn, conhost parent/command와 산술 Python의 base image를 완전 확인했다고 주장하지 않는다.

## 3. 측정 설계와 주요 값

기존 `cadence_fixture` 그대로 30×16/99, mine Random(7305), numbered hidden-safe75 Random(19), wasted 수동 CHORD prefix1을 썼다. 숨은 layout은 GUI fixture 구성에만 사용했고 worker에는 원 public DTO만 보냈다. ordinary Qt event loop/offscreen/ui.show, analysis·확률·가상 원형 ON, Reduction·guess OFF, fixed0ms, ZiNi/dialog/QSettings 격리를 공통 적용했다.

각 정책은 **MIN1 → TRACE → MIN2**, 매 run 새 game/run/owner다. 여섯 성공 run 각각 **actual/Replay/ACK 62/62/62**, 총 Auto 372다. 처음 2개는 warmup, 나머지 60개 내부 59gap으로 steady를 계산한다. 주 CPS는 `(N−1)×QPC frequency/(last−first)`이며 Counters 전체click/게임시간과 다르다.

| run | steady CPS | mean gap ms | P95 ms | max ms |
| --- | ---: | ---: | ---: | ---: |
| R01_V1_MIN1_C01 | 9.768297 | 102.371986 | 130.025640 | 160.501900 |
| R02_V1_TRACE | 9.615057 | 104.003541 | 129.308410 | 140.666100 |
| R03_V1_MIN2 | 9.834821 | 101.679534 | 126.192250 | 130.284800 |
| R04_LC1_MIN1 | 6.101223 | 163.901573 | 190.868900 | 194.243100 |
| R05_LC1_TRACE | 6.109656 | 163.675332 | 191.147060 | 220.273500 |
| R06_LC1_MIN2 | 6.209501 | 161.043541 | 191.043600 | 191.535300 |

`baseline=(g1+g2)/2`, `drift=abs(g2−g1)/baseline`, `observed_trace_change=gt/baseline−1`다.

| 정책 | baseline gap ms | drift | 관측 TRACE 변화 |
| --- | ---: | ---: | ---: |
| V1 | 102.025760 | 0.678704% | +1.938511% |
| K-LC1 | 162.472557 | 1.759086% | +0.740295% |

5%는 coordinator의 잠정 진단 기준이며 사용자 요구·제품 수용치가 아니다. 세 번의 순차 관측으로 시간 drift와 인과 overhead를 완전히 분리하지 못한다. MIN에도 audit hook, start/Popen/acknowledge/input wrapper, QSettings/ZiNi/dialog 격리, worker completion hook 등이 공통으로 있다. 따라서 MIN CPS는 **하네스 아래 MIN CPS**다. 공통 조건이 있다는 사실을 모든 영향의 정확한 상쇄 증명으로 쓰지 않는다.

완전 `(q−W,q]` 창의 .5/1초 peak는 V1 12/11, LC1 8/7 CPS였고 warmup은 span 부족으로 N/A다. 이산 `+1/W` 편향 때문에 주 CPS/안정 상한으로 해석하지 않는다. 0ms의 유한 target·0.9P 판정은 N/A다.

## 4. 시간 구분과 해석

두 TRACE 각각 59/59 gap에서 **부모 단일 process anchor 합이 raw gap과 정확히 같다.** ACK/NEXT/(K VALIDATE) 왕복 bucket 평균은 V1 70.882136ms, LC1 122.350707ms(68.15%/74.75%)다. worker 계산·검증·transport와 부모 발견/처리가 안에 중첩되므로 순수 IPC/poll 비중이 아니다.

| 중첩 설명용 평균 ms | V1 | K-LC1 |
| --- | ---: | ---: |
| worker plan_snapshot / KOwner.propose 전체 | 6.407242 | 9.159059 |
| 원 stored compute_ns 소계 | 4.705081 | 8.740917 |
| K validate / acknowledge | 해당 없음 | 2.067447 / 1.243532 |
| render_board | 21.627415 | 22.238483 |
| 성공 read_next 합 / steady gap | 27.068 | 40.811 |

성공 read_next는 회당 약6.5–7ms, JSON decode는0.19ms 이하였고 성공 read 합은 gap의 약26.0%/24.9%였다. envelope 검증 외의 경로 검사/open/read/close 중 어느 부분이 지배하는지는 미측정이다. syscall·백신·정확한 스케줄러 원인으로 귀속하지 않는다. 위 소계들을 부모 budget에 다시 더하지 않는다.

QPC는 같은 host의 정수10MHz다. 부모/worker 시작·끝 bracket과 방향별 게시→수신 쌍 **248/372**(왕복 **124/186**)에 인과 충돌은0이었다. 음수 lower bound는 span 겹침으로 보존했다. source origin이 다른 clock을 빼지 않았다. native paint/compositor, stream.write/flush/close 각각, 정확한 가시화 순간·scheduler wake·순수 poll 대기는 **NOT_MEASURED**다.

최종 comparison→token 소비→실제step1 사이 다른 이벤트는0, 정확 ACK 뒤 NEXT를 유지했다. 원 송신 deadline을 저장했으며 ACK 수신 때5초를 다시 주지 않았다. 완전한 atomic complete/receipt의 run/seq/ACK62/bytes/hash를 검증한 뒤 원 deadline보다 약4.95초 앞서 회수·retire했다. 마지막 flush는 Auto-span 밖이며 atexit/finally에 의존하지 않았다.

## 5. 독립 검토와 문구 정정

Claude는 약27.915분, 제품 Python/import/Qt/worker·owner·새 timing·source/helper 수정·Git/Desktop 쓰기 모두0으로 검토했다. 독립 Node/PowerShell 산술 도구 오류2/2건(PATH의 Node 부재, probe 버그)은 각각 한 번 보정하고 원본을 보존했다. 관측 모델은 claude-opus-5-5, effort max/auto mode였으며 Fast는 **UNCONFIRMED**다.

정확한 CROSSCHECK 구성은 **205행 = 정확 일치201 + 보고값 없는 참고2 + 비교 문자열 주석 문제2**다. 마지막2행의 실제 값은 원 보고서와 일치해 수용을 막지 않았다. 검토 manifest는 **자기 제외16파일 / 포함17파일**이다. 요약의 개수 표현만 정정하며 원 보고서·CROSSCHECK·manifest를 덮지 않는다.

- **E1 정정**: 원 보고서의 `timer type1`은 Auto 시작 전 setup의 기본값 관측이다. 실행 중 type을 직접 채집한 것은 아니다. 원 `_start_auto_pacing`은 고정 모드에서 **Qt.PreciseTimer**를 설정하며 기존 계약과 같다. 0ms 수치 영향이나 timer 회귀의 근거는 없다.
- **E2 명확화**: `_apply_live_action`과 Engine.step 표는 `[step anchor, ACK posted]`로 잘라낸 구간 값이다. 전체 inclusive span과 구분한다. 다른 중첩 항목도 더하지 않는다.
- **M1/M2 선택 유지보수**: observer 보조 오류가 원 호출 흐름으로 전파될 가능성, sitecustomize 선행 import와 실제 `-m` 시작 순서 검증 공백은 향후 kit 보완 후보다. 이번 예외/drop/open0과 정상 runtime 경로 수용을 취소하지 않으며 cold-start 지표로 확대하지 않는다.
- **M3 명확화**: 공통 seam을 포함한 하네스 MIN이라는 해석을 유지한다.

## 6. 추가 실행 없는 poll 구간 분석

독립 검토 뒤 coordinator가 **기존 R02/R05 TRACE만** 읽어 steady59gap의 ACK/NEXT/(K VALIDATE) 구간을 재구성했다. 새 제품 실행·owner는0이며 이 보충 분석은 Claude가 새로 독립 검토한 결과로 부르지 않는다.

| 기존 TRACE의 관측 | V1 | K-LC1 |
| --- | ---: | ---: |
| parent poll 진입 간격 mean / median ms | 31.385794 / 30.340700 | 37.192834 / 30.835850 |
| poll callback 포함시간 mean ms | 6.501841 | 15.043271 |
| callback이 설정25ms보다 긴 표본 | 0/195 | 59/259 |
| worker 부재 read 반환→같은 seq 다음 read 진입 mean ms | 10.194602 | 10.235673 |

parent의 설정25ms는 실제 callback 진입 간격이 아니다. callback 밖에는 다른 UI/timer 작업·스케줄링도 있을 수 있다. worker source의 `sleep(.01)` 구간도 loop/check/scheduling을 포함한다. 예를 들어 NEXT 응답 게시→성공 parent poll 진입의 평균 bounds는 V1 13.777027..14.159731ms, LC1 21.379595..22.104705ms였다. 이는 순수 timer/idle 대기 확정값이 아니며 기존 budget에 더하지 않는다.

원시 signed bounds, 게시 span 전체가 관측 gap 안에 들어간 엄격한 부분집합의 개수, read 비용을 따로 보존했다. 추가 자료는 외부 `MAIN_LIVE_HIGH_CPS_REVIEW_CLOSEOUT_2026-11-05/coordinator_01/POLL_PHASE_{RAW,SUMMARY}.json`과 분석 코드에 있다. 다음 후보는 성공 read_next의 외부 sub-span, render_board 내부, 이 poll 구간의 제한 해석이며 **단독 병목·최적화는 미확정/미수행**이다.

## 7. 근거·Git·영구 경계

외부 root: `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs`.

| 근거 | SHA256 / 범위 |
| --- | --- |
| MAIN_LIVE_HIGH_CPS_DIAGNOSTIC_RESUME_2026-11-05/codex_01/OUTPUT_MANIFEST.json | 47392102d4edf658fd14ae9f583e3c3d6af693ff21b658bb5403ba0ce02f6ef7 / 2159파일 |
| 같은 root review_claude_01/OUTPUT_MANIFEST.json | 9f2199b3499d07995f99f9e600d7006a2e177d8fb1887788a47a3653b00ef66f / 16파일 |
| accepted source333 manifest | 07feed55cdfd2979c4022efd3c90b5b6fe1a541de175df13f2965ced729676e5 |

문서/Git 준비 root는 `MAIN_LIVE_HIGH_CPS_REVIEW_CLOSEOUT_2026-11-05/coordinator_01`이다. 출발 main/HEAD=local origin/main=cd8ee2e, staged0, index `e7825f54…4ba`이며 source/tests 변경0과 **문서6경로**를 사용자 한 번의 commit/push로 마감하도록 준비한다. 실제 완료 SHA·push/clean은 후속 실제 receipt/live Git을 따른다. 완료된 옛 script를 재실행하거나 postcommit 문구만의 추가 commit을 만들지 않는다. recovery 사본은 실제 Git 마감 뒤 새 authority에 결속한다.

기존 B40행과 함수별 NOT_MEASURED/최적화 NOT_TRIGGERED는 당시 단위의 이력이다. 이번 제한된 함수 관측으로 과거 기록을 덮지 않는다. **B1 NOT_SATISFIED / 이번 OUT_OF_SCOPE**를 유지한다. 동일 owner 여러 판 합산이나 유한 fixture 확대를 하지 않았다.

**D0–D5 CLOSED/FINAL ACCEPTANCE PASS**, PHASE1_INCONCLUSIVE_TRANSFER, **effectiveness NOT ESTABLISHED**, **Production K/Gate P 미승인**, V1 CLOSED/FROZEN, Extended ACTIVE. Phase2/R0-B/ActualE2 미승인/미실행, frozen 정책·Model C·holdout **2,010,000..2,010,099**·금지 formal evidence 경계를 유지한다. C30판/5,035전이/24player 분석, 새 거리 profile, Stage4/package/연구를 열지 않았다. **F02 NOT_VERIFIED / 과거 Qt shared FileDialog FAIL / 이전 TEMP NOT_VERIFIED** 및 모든 이전 실패·권고도 유지한다.
