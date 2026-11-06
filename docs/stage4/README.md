# Stage 4 — 공개 정보 효율 계획

Stage 4는 일반 플레이처럼 제한된 공개 정보만 사용해 최종 Efficiency/IOE를 높이는 별도 개발 범위다. 실제 숨은 배치와 ZiNi 해답은 정책 입력이 아니며, 속도·이동 거리·Model C 시간도 선택 목표가 아니다.

세 방식은 **안전성 유지(S), 평균 성과(M), 목표 기록(R)**다. 공통 추론·비용 모델을 공유하며 위험 조건과 목적 점수를 다르게 적용한다. 현재는 작은 상태의 계획기와 평가기이고 Main 메뉴에는 연결하지 않았다.

## 현재 수용

- [Unit 1·2 기반 closeout](STAGE4_OPENING_PLANNING_FOUNDATION_CLOSEOUT.md): Unit 1 ACCEPT_BOUNDED, Unit 2 A/B ACCEPT_BOUNDED 및 D ACCEPT_BOUNDED_WITH_C01_RETAINED.
- [Unit 3 평가기 closeout](STAGE4_EVALUATION_UNIT3_CLOSEOUT.md): 제품 ACCEPT_BOUNDED, 근거 ACCEPT_BOUNDED_WITH_NONBLOCKING_DEFECTS, 필수 수정 0. 신규 시험 17개와 독립 실제 정책 174시도 재생.
- 최종 36설정 MATCH. 123건은 동결 후 신규 113 + 동결 전 완료 재사용 10이며, 4설정은 전량 재사용이다. 낮은 depth의 FLAG 후 미완료와 기본 depth 대조를 분리한다.
- S/M 및 M/R의 엄격한 차이는 목적에 맞게 고른 작은 witness에서 확인됐다. E[X]는 실패를 0으로 둔 무조건부 효용이다. 일반 성능·실전 우열·추천 설정의 근거가 아니다.
- 각 구현자의 PARTIAL, Unit 2 C01·H01, Unit 3 U3-H01과 비차단 한계를 보존한다. 전체 Stage 4 완료는 아직 판정하지 않았다.

## 다음 작업

Unit 3을 문서·Git·recovery에 마감한 뒤 일반 보드 지원에 필요한 계산 범위와 검증을 설계한다. 현재 전체 64칸/닫힘 8칸 제한을 일반 상급판 지원으로 오인하지 않는다. 근사 정책과 Main/Live 화면 연결은 별도 범위로 정한다.

현재 Git와 recovery는 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md)를 따른다. 이번 순수 평가기 단위에는 추가 native 확인이 필요하지 않다. 기존 전시 노트북 PENDING, Stage 3 V1/frozen 정책·Model C·Program K 연구/holdout 경계는 그대로다.
