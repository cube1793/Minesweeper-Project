# Stage 4 — 공개 정보 효율 계획

Stage 4는 일반 플레이처럼 제한된 공개 정보만 사용해 최종 Efficiency/IOE를 높이는 별도 개발 범위다. 실제 숨은 배치와 ZiNi 해답은 정책 입력이 아니며, 속도·이동 거리·Model C 시간도 선택 목표가 아니다.

세 방식은 **안전성 유지(S), 평균 성과(M), 목표 기록(R)**다. 공통 추론·비용 모델을 공유하며 위험 조건과 목적 점수를 다르게 적용한다. 작은 계획기·평가기, 공개 계수기·후보 근거, 제한 rollout 선택기, Unit7 색인 P0, Unit 8 Q/G에 이어 Unit 10의 독립 합산 계수기를 추가했다. Unit 11은 Q/G API에 합산 계수기를 명시적 선택 옵션으로 연결했다.

## 최근 연결과 실험

[Unit33 통신·ACK 복구 마감](STAGE4_LIVE_TRANSPORT_RECOVERY_UNIT33_CLOSEOUT.md). Unit33은 Stage4 메시지 게시 경합, 모델 사용 이력 결속, ACK 미수신 회복과 종료 표시를 보완했다. 최종 동일 바이트의 고유 시험 47개가 통과했고 독립 검토의 필수 보완은 0건이다. 현재 PC의 사용자 native 확인을 수용했다. 원 사용자 판의 원인은 미확정이며, F-02 시계 통일과 비차단 표시·기록·정리 권고는 후속이다.

[Units30–32 연결 마감](STAGE4_MAIN_WORKER_REPLAY_UNITS30_32_CLOSEOUT.md). Units30–32에서는 메인화면의 Stage4 S/M/R, 공개 정보 worker, 단일 입력 permit/ACK와 Replay 왕복을 final v02 범위에서 연결했다. 독립 검토의 지정 필수 결함은 0건이며 현재 PC의 사용자 핵심 native 확인을 수용했다. 시험은 42회·고유 27개로, v02 17회와 영향 없는 v01 10개 이월을 구분한다. F-01/F-02 권고와 보충 시험 공백은 후속으로 남겼다. 전체 Stage4 완료·일반 효율·전시 노트북·Production 승인은 별도다. 아래의 미연결 상태는 과거 단위의 기록이다.

[Units28–29 고정 F·실전 평가 마감](STAGE4_FIXED_F_FRESH_PILOT_UNITS28_29_CLOSEOUT.md). Units28–29에서는 kernel 한도 100,000의 `indexed_k100k`를 명시적 F 옵션으로 한정 수용했다. C36의 완료는 9/18→15/18, 완료 퇴행 0으로 등록 가용성 기준을 충족했다. 새 상급판 8회는 4승·2패·2미완료여서 Unit29는 PARTIAL을 유지한다. 기본 indexed와 모델 기본값은 그대로이며 일반 효과성과 R의 엄격한 목적 차이는 미확립이다. Main/worker/Replay는 다음 연결 범위다.

[Unit27 고정 F 프로파일 마감](STAGE4_FIXED_F_PROFILE_UNIT27_CLOSEOUT.md). Unit27은 기존 모델의 계산 폭을 비교했다. B0(8×4)는 3/18, P1(8×2)은 6/18, P2(4×2)는 9/18 완료했다. 독립 산술·실행 검토는 통과했으며 필수 보완은 0건이다. 세 프로파일의 가용성과 모델 정보 조건은 미충족이므로 후속 후보는 NONE이다. 실행·산술의 한정 수용과 실전 효율·운영 통합 보류를 분리한다.

[Units24–26 실험용 S/M/R와 F1 마감](STAGE4_RUNTIME_SMR_UNITS24_26_CLOSEOUT.md). Units24–26과 F1 보완을 검토된 미연결 실험 코드로 보존한다. F1_FIXED_BOUNDED는 수용됐으며, 가용성 AVAILABILITY_NOT_MET·통합 INTEGRATION_NOT_READY·효율과 실전 목적 차이 NOT_ESTABLISHED를 유지한다. 커널 388/857과 퇴행 3건, 모델 원 4/18·엄격 3/18, 실전 16패를 보존한다. 보완 후 큰 모델은 미측정이며 Stage4 NOT_MERGED다.

[Units21–23 공개 추론·안전 비용 마감](STAGE4_PUBLIC_CORE_UNITS21_23_CLOSEOUT.md). Units21–23은 공개 부분집합 추론과 여러 안전 성분의 비용 API를 추가했다. 순수 API는 BOUNDED_ACCEPT, output 전달은 harness 한정 LIMITED_ACCEPT다. 개발 승리 합계336→328, V8 승리4=4·matched-win C657→666으로 전체 정책은 MIXED/NOT_ADOPTED다. 신규 순수 API와 시험4파일은 미연결 실험 모듈이다. 독립 proof/계획/엔진 재생과 커널 미완료·기한 한계를 분리 기록한다.

[Unit20 그룹 경계 재계획 마감](STAGE4_GROUP_REPLAN_UNIT20_CLOSEOUT.md). Unit20은 그룹마다 재계획하는 후보를 비교했다. 전달은 ACCEPT_BOUNDED, 저장 재사용은 조건부 수용이며 신규 E02는 WON/C173·IOE177/173으로 Unit18과 같아 NO_IMPROVEMENT다. 후보는 NOT_ADOPTED로 마감한다. AST14/A279/B34와 새 C 한 판을 묶었고, 비차단6건 및 원 실패를 보존한다.

[Units18–19 및 R1 마감](STAGE4_EFFICIENCY_EXPERIMENTS_UNITS18_19_CLOSEOUT.md)에 두 후보와 공유 FLAG 방어를 기록했다. Unit18은 등록 네 판에서 1클릭 제한 개선, Unit19는 E01 −5/E02 +2로 MIXED다. 수학·완료 사건·관측 경로를 독립 재현했으며 R1은 통제된 합법 엔진 수순에서 해결됐다. 실제 정책의 상급판 도달성은 UNCONFIRMED이고 제품은 미반영이다.

H1은 새 helper의 최종 저장까지 확인했다. [Units12–17](STAGE4_EFFICIENCY_EXPERIMENTS_UNITS12_17_CLOSEOUT.md)의 원 PARTIAL·MIXED와 Unit18 oracle UNKNOWN/부분 회계, Unit19 subset 재구성 표시를 보존한다.

## 현재 수용

- [Unit 11 Q/G 합산 계수기 연결](./STAGE4_QG_COUNTER_INTEGRATION_UNIT11_CLOSEOUT.md)은 등록 범위에서 연결·회계 수용, 필수 보완 0건이다. 기본 UNIT4_LEGACY와 API opt-in UNIT10_SUMMED를 두고 검토 네 파일 반영 뒤 A 48개 통과를 확인했다.
- hard D/M/분수 321칸 일치, 작은 엔진 24 trial, 큰 요청 36개 반환과 READY 3개를 구분한다. READY는 기본 0/18·확대 3/18로 이전과 같다. 실전 효율은 NOT_ESTABLISHED다.
- 원 실패·PARTIAL과 U01의 당시 판정은 별도로 기록한다. 조율의 줄 해시 36/36과 반영 A의 새 실행 1회는 추가 확인이다.

- [Unit 10 독립 정확 계수기](STAGE4_STANDALONE_COUNTS_UNIT10_CLOSEOUT.md): 제품/API·수학과 과금·중단·메모 ACCEPT_BOUNDED, 제품/근거 필수0. 신규3파일·source365, 기존362는 불변이다.
- 합산200,000 work/협력2초, component 메모와 store skip, 호출 간 캐시0. API10시험·독립28문제/918 mask·새FDP8문제 D/M·원시272합계가 일치했다. hard 각3/3과 기존6관측18/18을 확인했다.
- 원 §7C 출처 충돌 PARTIAL, v1.1 사양 정정, 콘솔 표시 보정과 누적incident3/raw4를 보존한다. 비차단5/정보1은 개별 처분이며 재귀·oversized DTO 한계와 부모 units_total 차감 조건을 유지한다. 실전 효율·G 완료율·UI는 이번 수용 범위 밖이다.

- [Unit 9 보존 후보 검증·미채택](STAGE4_EXACT_COMPLETION_UNIT9_CLOSEOUT.md): 수학·등록 실측은 재현됐지만 확대 채택 기준 미달로 PARTIAL_IMPROVEMENT와 원복이 정당하다. 현재 제품에는 후보가 없다. 필수0·선택11·미확인5를 보존한다.
- 기본0→3/18, 확대3→3/18이며 같은 시간·명목 cap 조건이다. 별도 auxiliary는 G 합계에 미과금이다. hard 2상태 D/M과 완료11G/1056행을 독립 재현했고 미완료부분행·전체hit 전수 재계산은 아니다.

- [Unit 8 공개 정밀 후속 closeout](STAGE4_EXACT_OBJECTIVE_PILOT_UNIT8_CLOSEOUT.md): 제품 ACCEPT_BOUNDED, 제품 필수 0. 원 전체 PARTIAL/U8-H05·manifest 부재·R02/R03 공백을 유지한다.
- Q 15/G 14 별도 시험, 작은 G 102건과 engine 24 trial의 독립 재현. 후보 뒤 Q 모델의 점수와 실제 매 입력 반복 G 성과는 구분한다.
- 큰 평가는 기본 0/18·확대 3/18 완료이며 효율 향상은 미확립이다. 개별 exact cap 200,000과 부모 30초는 확대 profile에서도 남았다. 미완료를 0점이나 개선 없음으로 바꾸지 않는다.
- H1은 별도 보정 템플릿의 합산만 PS 5.1/7.6.9에서 확인했으며 원 실행을 재수행하지 않았다. 큰 Q의 결정 정합성과 큰 base 자체 재계수 여부도 구분한다.

- [Unit 7 색인 P0 closeout](STAGE4_INDEXED_P0_UNIT7_CLOSEOUT.md): 의미/work와 제한 모델 평가를 독립 수용했다. 제품/helper 필수 수정 0, 속도·실제 효율 개선 미확립이다.
- 기본 10M은 6/18 완료·12 fallback, 완료 6건 모두 전 후보 점수 0이다. 확대 30M은 18/18 완료·9건 전 후보 점수 0이다. 12요청이 10M을 넘으며 기본값은 유지했다.
- 354건(고유 150) 의미/work, 가상 3,456행과 실제 10경로가 재현됐다. 34 PASS는 5+29 별도 실행이다. 수치 한도 30.0/"30"의 동등성과 policy request_id 차이를 구분한다.
- U7-R01과 Unit 6 PARTIAL/U6-R02 및 모든 실패·비차단 한계를 보존한다. Unit 6/7의 공통 P0는 밀도 휴리스틱으로 유지하며 Unit 8의 정확 확률 Q/G는 별도 프로토타입이다.

- [Unit 6 rollout 선택 정책 closeout](STAGE4_ROLLOUT_POLICY_UNIT6_CLOSEOUT.md): 독립 **ACCEPT_BOUNDED**, 제품/helper 필수 수정 0. 구현자 PARTIAL/U6-R02는 유지한다. 정확 posterior·공개 P0·한 입력과 인스턴스 내 continuation을 제공한다.
- W1: 실제 fallback 입력 29(필드상 32 중 비READY 3 제외). W2: MODEL_SELECTED 69는 합성 4+가상 rollout 65(실제 폐루프 43). W3: A 13/B 11(v01)+추가 B 4(v02) 별도 실행.
- 실제 작은 25시도는 13승/10패/추측 금지 1/미완료 1이다. Unit 6 당시 큰 18호출은 모두 fallback이며 model-selected는 UNVERIFIED였다. 그 후 Unit 7의 확대 profile에서 완료를 확인했으나 Unit 6의 과거 판정은 그대로다.

- [Unit 5 후보 수순 근거 closeout](STAGE4_CANDIDATE_EVIDENCE_UNIT5_CLOSEOUT.md): ACCEPT_BOUNDED_CANDIDATE_EVIDENCE, 필수 제품/helper 수정 0. 전체 입력 비용·공동 생존·0 사건·위험 eligibility를 제공하며 최종 수는 고르지 않는다.
- 새 시험 A 25/B 1, 작은 24관측, engine 339 macro, 큰 6관측의 고유 사건 4,699개를 독립 재현했다. 코드로만 확인된 방어·backend 내부 중단·최초 controller 과거 부재 등 한계는 개별 기록한다.

- [Unit 4 공개 계수기 closeout](STAGE4_PUBLIC_COUNTS_UNIT4_CLOSEOUT.md): ACCEPT_BOUNDED, 필수 수정 0. 공개 D/M/공동 사건 W와 한도·취소·원자적 확정. 새 시험 A 17개/B 4개, 작은 32관측·분석해 7요청·Replay 6관측의 독립 계수 일치.
- 480칸/사건 16/work 200,000/협력 시간 2초는 계수기의 상한이다. 기존 계획기는 여전히 전체 64칸/닫힘 8칸 범위이며 일반 상급판 실용성·안정 시간·효율은 미판정이다.
- Unit 4의 EXACT 37은 W=0 19/W=D 7/중간값 11이다. 예상 UTC 원시 오류, 약 15.6 ms 시계 해상도·비중단 구간 등 5개 비차단 발견을 개별 보존한다.

- [Unit 1·2 기반 closeout](STAGE4_OPENING_PLANNING_FOUNDATION_CLOSEOUT.md): Unit 1 ACCEPT_BOUNDED, Unit 2 A/B ACCEPT_BOUNDED 및 D ACCEPT_BOUNDED_WITH_C01_RETAINED.
- [Unit 3 평가기 closeout](STAGE4_EVALUATION_UNIT3_CLOSEOUT.md): 제품 ACCEPT_BOUNDED, 근거 ACCEPT_BOUNDED_WITH_NONBLOCKING_DEFECTS, 필수 수정 0. 신규 시험 17개와 독립 실제 정책 174시도 재생.
- 최종 36설정 MATCH. 123건은 동결 후 신규 113 + 동결 전 완료 재사용 10이며, 4설정은 전량 재사용이다. 낮은 depth의 FLAG 후 미완료와 기본 depth 대조를 분리한다.
- S/M 및 M/R의 엄격한 차이는 목적에 맞게 고른 작은 witness에서 확인됐다. E[X]는 실패를 0으로 둔 무조건부 효용이다. 일반 성능·실전 우열·추천 설정의 근거가 아니다.
- 각 구현자의 PARTIAL, Unit 2 C01·H01, Unit 3 U3-H01과 비차단 한계를 보존한다. 전체 Stage 4 완료는 아직 판정하지 않았다.

## 다음 작업

Main/worker/Replay 연결과 Unit33 복구는 현재 PC에서 한정 수용했다. 사용자 Git과 Desktop 마감 뒤 보드 배치·Auto 설정·R 목표 UX·입력별 확정 표시와 성능 비용을 다룬다. 계산 지연·일반 효율·고효율 Replay 분석은 별도 검증하며, 전시 노트북과 패키지도 별도로 수용한다.

현재 Git와 recovery는 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md)를 따른다. 이번 연결 수용에는 현재 PC 사용자 native 보고를 사용했다. 장애 주입 복구·BUSY의 전체 조합, 전시 노트북과 frozen 패키지는 후속이다. Stage 3 V1/frozen 정책·Model C·Program K 연구/holdout 경계는 유지한다.