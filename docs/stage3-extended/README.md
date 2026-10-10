# Stage 3 Extended

## Status

Stage-3 V1은 **FINAL ADJUDICATION PASS — STAGE-3 V1 CLOSED** 상태이며, Extended의 immutable baseline으로 취급한다.

- [V1 최종 판정](../stage3-v1/STAGE3_V1_FINAL_ADJUDICATION.md)
- [Frozen V1 algorithm specification](../../STAGE3_ALGORITHM_SPEC_v1.md)
- [Frozen V1 telemetry and benchmark specification](../../STAGE3_TELEMETRY_BENCHMARK_SPEC_v1.md)
- [기존 extension backlog](../../STAGE3_EXTENSION_BACKLOG.md)
- [Project documentation index](../README.md)

## Extended boundary

Extended는 accepted V1 위에 추가되는 별도 scope다. V1의 미완료 작업으로 취급하지 않으며, V1 수용을 다시 열기 위한 전제도 아니다.

V1의 공식 100k 결과, frozen Model C, 기존 audit·evidence·qualification을 소급 변경하지 않는다. 새 물리 모델이나 새 알고리즘 버전은 V1과 구분되는 identity/version으로 기록하고 평가한다.

이 README는 backlog / planning의 출발점이다. 아래 후보의 최종 우선순위, 구현 사양 또는 구현 착수를 확정하지 않는다. 기존 backlog의 우선순위 표기도 당시 제안으로 보존하며, 실제 작업 순서와 검증 조건은 별도 계획에서 결정한다.

## Current candidate workstreams

다음 A/B/C는 후보를 구분하는 세 작업 축이며, 실행 우선순위를 뜻하지 않는다.

### A. Existing-feature stabilization

- ZiNi performance profiling / improvement: 성능 병목을 측정하고 개선 후보를 검토한다.

### B. Stage-3 application / visualization

- Stage-3 execution integration into application.
- Unified execution / replay / visualizer surface.
- Cursor path 및 OPEN / FLAG / CHORD visualization.
- Same-board comparison support.
- Representative-board demonstration.
- 필요에 따른 timeline / analytics expansion.

녹화 기능은 앱 자체 기능으로 우선 구현하지 않는다. 발표·전시 영상은 외부 screen-recording tool 사용을 기본으로 한다.

### C. Stage-3 Extended algorithm / physical model

- Algorithm version selection: V1, 향후 별도로 정의할 V2/V3 등.
- Physical-model configuration은 algorithm version과 분리한다.
- Playback/presentation settings는 planning inputs와 분리한다.

V1에서 deferred된 후보는 다음과 같다.

- Nearest equal-risk guess: 동일한 최소 위험 후보 사이의 물리 비용 기반 선택.
- Logical-known-mine / no-flag execution.
- Action-specific timing.
- Anisotropy.
- CPS / burst constraints.
- Longer-horizon or richer planning: 별도 사양이 정의된 경우에만 검토한다.

각 후보의 채택 여부, 순서, 모델 파라미터와 평가 계약은 후속 planning 문서에서 근거와 함께 결정한다.

## Versioning rule

| 구분 | 식별하는 대상 |
| --- | --- |
| Application version | 앱 기능·통합·배포 버전 |
| Stage-3 algorithm version | V1 또는 향후 V2/V3의 의사결정·실행 semantics |
| Physical model/profile version | 비용 모델, calibration/profile 및 planning에 사용되는 물리 입력 |
| Playback/display settings | 재생 속도, 표시와 시각화 설정 |

V1을 선택한 실행에서는 frozen V1 semantics와 사용한 Model C/profile identity를 각각 명시한다. Application version이 달라졌다는 이유로 algorithm이나 physical model의 version이 바뀐 것으로 취급하지 않는다.

다른 물리 모델·profile을 적용한 결과는 기존 frozen Model C의 공식 V1 결과와 구분한다. Playback/display 설정 변경은 planning 입력이나 기록된 benchmark 지표를 바꾸지 않는다.

## Documentation rule

새 Extended 문서는 기본적으로 `docs/stage3-extended/` 또는 필요한 하위 디렉터리에 생성한다.

기존 V1 문서는 Extended 작업 때문에 이동하거나 수정하지 않는다. Frozen spec과 audit·evidence·qualification 경로 및 공식 100k artifact root도 현재 위치와 identity를 유지한다. 새 설계·검증은 별도 문서로 작성하고 기존 기준선에 링크한다.
