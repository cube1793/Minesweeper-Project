# Stage 4 — 공개 정보 효율 계획

Stage 4는 일반 플레이처럼 제한된 공개 정보만 사용해 최종 Efficiency/IOE를 높이는 별도 개발 범위다. 실제 숨은 배치와 ZiNi 해답은 정책 입력이 아니며, 속도·이동 거리·Model C 시간도 선택 목표가 아니다.

사용자 관점의 세 방식은 **안전성 유지(S), 평균 성과(M), 목표 기록(R)**다. 공통 추론·비용 모델을 공유하며 위험 조건과 목적 점수를 다르게 적용한다. 현재는 작은 상태의 순수 모듈이며 Main 메뉴에 연결하지 않았다.

## 현재 수용

- [오프닝·계획 기반 closeout](STAGE4_OPENING_PLANNING_FOUNDATION_CLOSEOUT.md): Unit 1 ACCEPT_BOUNDED, Unit 2 A/B ACCEPT_BOUNDED 및 D ACCEPT_BOUNDED_WITH_C01_RETAINED.
- Unit 1의 오프닝 D/M/Z와 Unit 2의 공개 분기·원자 비용·S/M/R 선택을 등록된 작은 상태에서 검증했다.
- 구현자 PARTIAL, C01 최초 Git 조회 전 기록 공백, 과거 실패·미확인과 후보군 제한을 보존한다.
- 아직 일반 상급판 지원, 세 방식의 실전 우열, UI/native, 전체 Stage 4 완료는 평가하지 않았다.

## 다음 작업

Main 연결 전의 평가 harness를 우선한다. 각 시도의 WON/LOST/GUESS_BLOCKED/UNRESOLVED와 수순 score/실제 재계획 결과를 구분하고, 비교 상태·시도 수를 사전 등록한다. 준비 도중 INSUFFICIENT가 되면 UNRESOLVED로 기록한다. 그 이후 일반 보드 지원과 화면 연결을 별도 설계한다.

현재 Git와 recovery는 [CURRENT_HANDOFF](../CURRENT_HANDOFF.md)를 따른다. Stage 3 V1/frozen 정책·Model C·Program K 연구/holdout 경계는 이 개발로 바뀌지 않는다.
