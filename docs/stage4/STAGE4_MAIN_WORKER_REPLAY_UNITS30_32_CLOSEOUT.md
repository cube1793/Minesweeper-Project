# Stage 4 Units30–32 메인화면·worker·Replay 연결 마감

## 현재 수용 범위

2026-11-08에 final v02의 메인화면·worker·실제 입력·Replay 연결을 한정 수용했다. 독립 검토에서 지정 필수 범주의 제품 결함은 0건이었고, 사용자가 현재 PC의 핵심 native 동작을 수용했다. 일반 효율·고효율 기록·안정 실행 시간·전시 노트북·frozen 패키지·Production은 별도 미확인 범위다.

이번 수용은 `LIVE_INTEGRATION_ACCEPTED_BOUNDED`로 기록한다. 구현 중의 `NOT_MERGED`, 읽기·명령 보정 4/2 초과와 과거 단위의 PARTIAL은 당시 판정으로 보존한다. 전체 Stage 4 완료 판정은 내리지 않았다. 문서 작성 시 Git commit/push와 Desktop recovery는 사용자 실행 및 영수증 확인을 기다린다.

## 연결과 설정

- 기존 Main에 Stage4 안전성 S·평균 효율 M·목표 기록 R 선택을 연결했다. 기본은 indexed, 표본 8개와 후보 4개다. 제한 K100K는 명시 선택이며 표본 4개와 후보 2개를 사용한다.
- worker는 공개 관측·전체 지뢰 수·공개 입력 원장만 받는다. 실제 숨은 배치·정답·분리된 유효/낭비 입력·진행 3BV를 정책에 전달하지 않는다.
- 원자 입력은 현재 관측과 proposal/permit identity를 확인한 뒤 정상 엔진 진입점에 전달하고 ACK로 기록한다. 모델 사용 이력은 작업 전에 저장하며 중단·재시작으로 예산을 새로 주지 않는다.
- 제안 없는 RESOURCE_LIMIT와 F_TIME_RESERVATION은 Auto와 예약을 중단한다. 현재 보드·Replay·중단 사유를 보존하며 같은 상태를 자동 재요청하지 않는다.
- Replay 진입은 진행 중 입력의 ACK와 worker 정리를 확인한다. Replay 중 정책 실행을 차단하고 Live 복귀 때 Auto OFF와 설정을 유지하는 경로를 연결했다.
- 현재 R은 양의 목표 IOE 백분율을 명시적으로 받아 그 목표 달성 확률을 우선한다. 목표값 없이 최고 기록을 추구하는 방식은 후속 설계 항목이다.

## 검증 근거

| 범위 | 확인 결과 |
|---|---|
| 후보 | 기존 3파일과 신규 9파일, 합계 12파일이 final v02와 일치 |
| 구현자 시험 | 실행 42회, 고유 27개. final v02 17회와 영향 없는 v01 10개 이월을 구분 |
| 실제 worker | S/M/R의 첫 선택 MODEL_SELECTED, M의 둘째 선택 EXACT_Q. 고유 ACK 10개 |
| 독립 재생 | Node 엔진 20 step에서 ACK 뒤 관측과 공개 규칙 불일치 0 |
| Main 자동 시험 | offscreen. 현재 PC의 사용자 native 확인과 구분 |
| 사용자 native | M 승리 화면, 같은 창의 새 게임·다른 정책 실행·Replay 전환 정상. 지속 ACK/정리 차단과 PERMIT/HISTORY 오류 없음으로 추가 확인 |
| 결속 | 구현 산출물 529파일 / 3,482,560 bytes, 독립 검토 20파일 / 192,774 bytes 전수 대조 |

사용자의 처음 보고는 ‘통과인 것 같고 개선점과 사소한 부분은 나중에 수정’이었다. 후속 질문에 ‘모두 정상적으로 가능했고 해당 오류도 없었음’으로 답했다. 이를 현재 PC의 핵심 전환 수용으로 기록하며, 개별 S/R 완주·Replay 두 종료 경로의 항목별 전사나 모든 장애 경로 시험으로 확대하지 않는다.

## 남겨 둔 권고와 검증 공백

필수로 승격된 발견은 0건이다. 사용자가 경미한 사항을 후속으로 처리하도록 정했고, 현재 native에서 해당 장애가 보고되지 않아 아래 권고는 이번 final v02에 추가 반영하지 않았다.

1. F-01. ACK를 기다리던 worker가 ACK 없이 종료되면 `expected_ack`가 남아 새 게임에서도 Auto·Replay가 막힐 수 있다. 당시 게임의 실패 기록을 유지하면서 정리 완료 뒤 stale ACK 상태를 해제하는 보완과 회복 시험이 필요하다. 정상 경로에서 관측된 현상은 아니다.
2. F-02. worker의 `perf_counter_ns`와 부모의 `monotonic`이 서로 다른 시간 기준을 사용한다. 현재 PC에서는 수락됐지만 다른 환경에서 모든 permit이 거절될 가능성이 있다. 같은 시간 기준을 사용하도록 보완한다. PERMIT_EXPIRED/DEADLINE이 native에서 나타나면 필수 수정으로 승격한다.
3. F-03. 이력과 proposal 읽기 사이의 경합은 HISTORY 정지를 일으킬 수 있다. 이력을 다시 읽는 보완을 권고하며 현재 native에서는 보고되지 않았다.
4. F-04/F-05. 성공한 메시지의 `.part` 이름 잔존과 신규 시험의 혼합 줄끝은 후속 정리 항목이다.
5. G-01/G-02/G-03. 분석 중 Auto가 같은 owner를 이어받는 직접 시험, terminal ACK 뒤 Main→Replay 직접 시험, 수정된 runtime에 대한 기존 `test_stage4_runtime_policy.py` 전체 재실행은 후속 표적 검증으로 남긴다. 사용자 Replay 전환 보고와 시험 공백을 합치지 않는다.

현재 자연 worker에서 PUBLIC_KERNEL 선택은 미관측이다. 모델 CHORD·공유 FLAG는 통제 선택이며 Q 한도는 저장된 공개 DTO 주입 근거다. 일반 보드 효과성의 증거로 확대하지 않는다.

## 사용자 후속 개선 요청

- 계산과 실제 진행 속도 개선.
- 최종 Efficiency/IOE 향상. 현 결과로 120%·150%·160%를 보장하지 않는다.
- Stage4 제어 행 추가 뒤 상급 30×16·28px 보드에 생긴 스크롤을 창 크기나 배치로 해소.
- R의 명시 목표값 요구와 사용자가 원하는 자동 최고 기록 추구의 차이 재설계.

효율 가이드의 CHORD·깃발 비용·공개 패턴 추론·공유 깃발은 구현돼 있다. 미래 flood와 새 숫자를 제외한 정적 비용 및 제한된 모델 때문에 오프닝 선행과 장기 순서 최적화는 부분적이다. 기본 전략을 모든 국면에서 충분히 활용한다고 평가하지 않는다.

## 이력과 실행 경계

원 구현의 읽기·명령 4/2 초과, helper 2/2, 제품 보완 1/3, incident 7/8, Python 15/24, image 30/48, owner 15/16을 보존한다. run02의 외부 TerminateJobObject 호출 1회는 멤버 exit code에 따른 실제 종료 0과 구분한다. 원 manifest 합계 0 실패본과 취소로 인한 native_passed=false도 보존한다.

조율은 제품 Python·시험·worker·native를 추가 실행하지 않았다. 파일·원시 대조와 문서 작성, index 변경을 금지한 Git 읽기만 수행한다. 구현·검토의 과거 판정을 소급 PASS로 바꾸지 않는다.

## 기준선과 경로

- 시작 HEAD와 당시 local origin/main은 `b79d7a3e52877152ee159095fe5f134415575e2e`다. 시작 tracked 461개, source 375개였다.
- final v02 source는 384개다. 통합 후보 12경로와 문서 6경로를 함께 기록하며, 신규 10경로를 포함한 commit 후 tracked 예상 수는 471개다.
- 구현 근거는 `outputs/STAGE4_MAIN_WORKER_REPLAY_UNITS30_32_2026-11-08/codex_01`이다.
- 독립 검토는 같은 root의 `review_claude_01`, 사용자 최초 확인은 `user_native_01`, 후속 확인과 조율 대조는 `coordinator_04`다.
- Git 마감 준비는 `outputs/STAGE4_UNITS30_32_CLOSEOUT_2026-11-08/coordinator_01`이다. commit/push 성공 영수증과 별도 Desktop destination 검증 전에는 그 절차의 완료를 선언하지 않는다.
