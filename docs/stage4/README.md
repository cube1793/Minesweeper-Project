# Stage 4 — 공개 정보 효율 계획

Stage 4는 일반 플레이처럼 제한된 공개 정보만 사용해 최종 Efficiency/IOE를 높이는 별도 개발 범위다. 실제 숨은 배치와 ZiNi 해답은 정책 입력이 아니며, 속도·이동 거리·Model C 시간도 선택 목표가 아니다.

세 방식은 **안전성 유지(S), 평균 성과(M), 목표 기록(R)**다. 공통 추론·비용 모델을 공유하며 위험 조건과 목적 점수를 다르게 적용한다. 현재는 작은 계획기·평가기, 공개 계수기·후보 근거와 제한 rollout 선택기, Unit 7 색인 P0를 구현했고 Main 메뉴에는 연결하지 않았다.

## 현재 수용

- [Unit 7 색인 P0 closeout](STAGE4_INDEXED_P0_UNIT7_CLOSEOUT.md): 의미/work와 제한 모델 평가를 독립 수용했다. 제품/helper 필수 수정 0, 속도·실제 효율 개선 미확립이다.
- 기본 10M은 6/18 완료·12 fallback, 완료 6건 모두 전 후보 점수 0이다. 확대 30M은 18/18 완료·9건 전 후보 점수 0이다. 12요청이 10M을 넘으며 기본값은 유지했다.
- 354건(고유 150) 의미/work, 가상 3,456행과 실제 10경로가 재현됐다. 34 PASS는 5+29 별도 실행이다. 수치 한도 30.0/"30"의 동등성과 policy request_id 차이를 구분한다.
- U7-R01과 Unit 6 PARTIAL/U6-R02 및 모든 실패·비차단 한계를 보존한다. 현재 공통 P0는 밀도 휴리스틱이며 S/M/R별 정밀 후속 정책은 아직 구현하지 않았다.

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

Unit 7 문서·Git·recovery 마감 뒤 정밀 확률과 S/M/R별 후속 선택을 새 계약으로 설계한다. 확률 정확도 개선과 목적 선택 변경을 구분한다. S는 막힘 상황의 안전 수·최소 위험을, M/R은 안전 수가 있을 때도 효율 경쟁 후보를 검토한다. 공개 정보 경계·원자 비용·미완료와 자원 한도를 유지하고 기존 실패 trace와 비교한다. 실제 효율·기본 aggregate 한도 변경·전체 실전 평가와 Main/Live·worker 연결은 자동으로 포함되지 않는다.

현재 Git와 recovery는 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md)를 따른다. 순수 계산 모듈의 이번 수용에는 추가 native가 필요하지 않다. 같은 인스턴스의 미적용 입력 복구와 BUSY, 전시 노트북 PENDING, Stage 3 V1/frozen 정책·Model C·Program K 연구/holdout 경계는 그대로다.
