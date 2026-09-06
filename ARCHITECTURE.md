# Architecture

## 1. 설계 목표

본 프로젝트는 단순히 실행 가능한 지뢰찾기를 만드는 것뿐 아니라, 이후 Replay 분석과 알고리즘 및 AI 기능을 확장할 수 있는 구조를 목표로 한다.

주요 설계 원칙은 다음과 같다.

* 분석과 알고리즘 및 AI 기능을 확장할 수 있는 구조를 목표로 한다.

주요 설계 원칙은 다음과 같다.

* UI와 게임 규칙을 분리한다.
* 핵심 게임 엔진은 PyQt5에 의존하지 않는다.
* UI는 엔진의 공개 인터페이스를 통해서만 게임 상태를 조회한다.
* 보드 분석, Replay 분석, ZiNi 계산은 게임 엔진과 분리한다.
* 모듈 간 전달 데이터는 가능한 한 불변 구조로 만든다.
* 동일한 상태를 여러 위치에서 중복 관리하지 않는다.
* 기능 추가 전에 회귀 테스트를 확보한다.
* 검증된 동작을 유지하며 작은 단위로 리팩터링한다.
* 제한된 탐색 결과를 전역 최적해 또는 정확한 최소값으로 표현하지 않는다.

## 2. 전체 구조

```text
main.py
   │
   ▼
ui_manager.py
   ├──────────────▶ core_engine.py
   ├──────────────▶ Replay modules
   ├──────────────▶ replay_statistics.py
   └──────────────▶ zini_metric_worker.py
                         │
                         ▼
                  ZiNi calculation modules
```

분석 모듈의 주요 의존 관계는 다음과 같다.

```text
core_engine.py ─────────────▶ board_snapshot.py

board_analyzer.py ──────────▶ board_snapshot.py

replay_statistics.py
   ├────────────────────────▶ replay_player.py
   └────────────────────────▶ board_analyzer.py

zini_calculator.py
   ├────────────────────────▶ zini_core.py
   ├────────────────────────▶ zini_min_ties.py
   └────────────────────────▶ zini_advanced.py
```

의존성은 UI에서 분석 및 도메인 계층으로 향하며, 분석 모듈이 UI를 역으로 참조하지 않도록 한다.

## 3. 모듈별 책임

### `main.py`

* `QApplication` 생성
* 게임 엔진 생성
* UI에 엔진 주입
* 프로그램 실행 시작

### `core_engine.py`

* 지뢰찾기 게임 규칙
* 지뢰 배치와 인접 지뢰 수 계산
* 셀 열기, 깃발, 화음
* 승리 및 패배 판정
* 게임 시간과 클릭 통계
* UI와 Replay 분석을 위한 공개 상태 제공

PyQt5에 의존하지 않는 핵심 도메인 모듈이다.

### `board_snapshot.py`

* 보드의 지뢰 위치와 인접 지뢰 수를 불변 데이터로 제공
* 엔진 내부의 가변 상태가 분석 모듈로 직접 노출되는 것을 방지

### `board_analyzer.py`

* 보드의 opening 및 숫자 셀 구조 분석
* 3BV 계산
* Ops 계산
* Replay 통계와 ZiNi 계산에 필요한 보드 분석 정보 제공

### `ui_manager.py`

* PyQt5 화면 구성
* 사용자 입력 처리
* 보드 렌더링
* 일반 게임 및 Replay Counters 표시
* Replay 재생 버튼과 slider 관리
* Index/Time 재생 상태 관리
* ZiNi subprocess 시작, polling, 취소 및 결과 수신

일반 게임의 기본 통계는 엔진에서 제공받고, Replay 통계는 `ReplayStatisticsAnalyzer`에서 제공받는다.

현재 일반 게임의 일부 ZiNi 기반 파생 지표 조합과 worker 생명주기 관리는 UI에 남아 있으며, 향후 별도 서비스로 분리할 수 있다.

## 4. Replay 구조

### `replay_model.py`

* Replay board, event 및 Replay data 구조
* Replay action 상수
* 저장 및 재생 모듈 사이의 공통 데이터 계약

### `replay_recorder.py`

* 실제 플레이 이벤트 기록
* 첫 지뢰 배치 이후 보드 정보 저장
* 현재 게임을 `ReplayData`로 변환

### `replay_json.py`

* `ReplayData`의 JSON 직렬화
* JSON 파일 저장과 불러오기
* 저장 형식 검증

### `replay_player.py`

* Replay board로 독립 게임 엔진 생성
* 이벤트를 순서대로 적용
* 이전·다음 및 특정 index 상태 재구성
* 현재 Replay 시간과 위치 제공

### `replay_statistics.py`

* Replay 전체 완료 여부 판정
* index별 불변 통계 timeline 생성
* action별 active 및 wasted 클릭 집계
* 현재 3BV와 Ops 계산
* 현재 index, Replay 시간 및 ZiNi 기준 통계 생성
* 미완료 Replay 통계 마스킹

PyQt5와 subprocess에 의존하지 않는 순수 분석 모듈이다.

## 5. Replay 처리 흐름

### 기록

```text
사용자 입력
→ UI
→ MinesweeperEngine.step()
→ ReplayRecorder.record_event()
→ ReplayData
→ JSON 저장
```

### 재생

```text
Replay JSON
→ ReplayData
→ ReplayPlayer
→ 독립 MinesweeperEngine
→ 특정 index 상태 복원
→ UI 렌더링
```

### 통계

```text
ReplayData
→ ReplayStatisticsAnalyzer.analyze()
→ ReplayCounterTimeline
→ statistics_at(index, time, zini)
→ UI Counters
```

## 6. ZiNi 구조

### `zini_core.py`

* deterministic G.ZiNi의 공통 계산 구조
* Replay 가능한 클릭 sequence 생성
* ZiNi 계산에 필요한 상태와 평가 로직

### `zini_min_ties.py`

* 동점 후보를 제한된 범위에서 탐색
* deterministic 결과와 분리된 bounded search 제공

### `zini_advanced.py`

* neighborhood beam 기반 advanced search
* ranking policy 및 evaluation budget 적용
* seeded-chain 등 확장 정책 제공

### `zini_calculator.py`

* 외부에서 사용하는 ZiNi 계산 진입점
* deterministic, min-ties 및 advanced 전략 연결
* 기존 호출 인터페이스 유지

### `zini_metric_worker.py`

* UI가 멈추지 않도록 ZiNi 계산을 별도 subprocess에서 실행
* 임시 입력 및 결과 파일을 통한 데이터 전달
* token을 이용해 오래된 계산 결과 무시

## 7. ZiNi 결과 해석

본 프로젝트의 deterministic G.ZiNi는 정의된 deterministic 정책이 생성한 결과이다.

Advanced search는 제한된 evaluation budget 안에서 더 나은 클릭 sequence를 탐색한다. 따라서 결과는 bounded best-so-far이며 다음을 보장하지 않는다.

* 전역 최적해
* 이론적인 최소 클릭 수
* 모든 탐색 정책 중 최선의 결과

Expert seed 1003에서 120 clicks 결과를 얻었지만, 이는 해당 설정과 탐색 범위에서 발견한 검증 가능한 결과로 해석한다.

## 8. 테스트 구조

`tests/`는 다음 영역을 검증한다.

* 게임 엔진 회귀
* 불변 BoardSnapshot
* BoardAnalyzer와 3BV/Ops
* Replay model 및 JSON 변환
* Replay recorder와 player
* Replay 통계 공식 및 UI 연동
* deterministic G.ZiNi
* min-ties 및 advanced search
* Replay 유효성과 클릭 합계

전체 회귀 테스트는 다음 명령으로 실행한다.

```powershell
python -m unittest discover -s tests -v
```

Benchmark는 단위 테스트를 대체하지 않으며, 고정 보드에서 탐색 결과와 실행 동작의 회귀를 확인하는 용도로 사용한다.

## 9. 현재 한계와 기술 부채

* 일반 게임의 일부 ZiNi 기반 파생 통계 조합이 UI에 남아 있다.
* ZiNi worker의 subprocess 생명주기 관리가 UI에 포함되어 있다.
* Replay의 재생 시간, slider 및 button 상태 관리가 하나의 UI 클래스에 집중되어 있다.
* Replay 통계는 진입 시 모든 이벤트를 재생해 timeline을 생성하므로 비용이 이벤트 수에 비례한다.
* 실제 PyQt 이벤트 루프와 subprocess 실패·취소 시나리오는 일부 수동 검증에 의존한다.
* Advanced ZiNi 탐색은 전역 최적 결과를 보장하지 않는다.

이러한 항목은 현재 기능의 즉각적인 결함이라기보다, 향후 확장성과 자동 검증 범위를 개선하기 위한 기술 부채로 관리한다.

## 10. 향후 개선 후보

* 일반 게임 파생 통계 계산기 분리
* ZiNi worker 관리 서비스 분리
* Replay controller 분리
* 계산 결과 모델과 화면 Formatter 분리
* PyQt `QTest` 기반 UI 통합 테스트
* subprocess 실패·취소·종료 테스트
* Replay timeline checkpoint 또는 lazy evaluation
* 다양한 보드와 seed를 사용하는 benchmark 확대

## 11. Stage 2-3 Decision Analyzer와 Runner

```text
observation + num_mines
        │
        ▼
simple_decision.analyze_position()
        ├── simple_algorithm: local inference 우선
        └── simple_probability: local move가 없을 때만 exact probability
        │
        ▼
불변 SimpleDecision
        ├── 향후 Live UI / Replay Analysis에서 표시용으로 재사용
        └── simple_runner.run_simple() → engine.step() 한 번
                                           │
                                           ├── fresh observation → 다시 분석
                                           └── ReplayRecorder → ReplayData
```

### 순수 position 분석

`analyze_position(observation, num_mines) -> SimpleDecision | None`은 입력을
변경하거나 행동을 실행하지 않는다. Engine 객체, BoardSnapshot, ReplayData,
실제 지뢰 배치는 받지 않는다. 같은 공개 입력에는 같은 결과를 반환한다.

`SimpleDecision`은 `kind`, `move`, `constraints`, `deterministic_result`,
`probability_result`를 보존하는 frozen dataclass다. `DecisionKind`는 다음과 같다.

* `LOCAL_DETERMINISTIC`: Stage 2-1 선택. Probability solver를 호출하지 않으며
  `probability_result`는 `None`이다.
* `GLOBAL_CERTAINTY`: local move가 없고 Stage 2-2에서 선택된 셀의
  `mine_worlds`가 0 또는 `total_worlds`와 같다. 기존 selector가 OPEN/FLAG를 정한다.
* `PROBABILITY_GUESS`: 선택된 셀의 `0 < mine_worlds < total_worlds`인 OPEN이다.

확정 여부에 float을 사용하지 않는다. Stage 2-2를 실행한 결과는 그대로 보존한다.
완전 미오픈 observation도 fixed-layout 확률로 분석한다. 깃발은 두 core와
동일하게 지뢰로 가정한다. Solver의 입력/모순 오류는 전파하며, local 추론 전에
공개 FLAGGED/HIDDEN 수로 `0 <= num_mines - flag_count <= hidden_count`를 검증한다.
전체 보드의 probability enumeration은 Stage 2-2 경로에서만 수행한다.

### 실행과 중단

`run_simple(engine, *, accept_guesses=False) -> SimpleRunResult`는 현재 게임을
동기적으로 진행한다. 시작 observation이 전부 HIDDEN이면 첫 행동으로
`OPEN (0, 0)`을 실행하고 기록한다. Fresh random game의 첫 OPEN 안전성은
기존 엔진이 보장한다. Fixed board는 주어진 배치를 유지한다.
Opened/flagged 셀이 있으면 현재 observation을 바로 분석하며, 이미 WON/LOST인
엔진에는 분석이나 추가 행동을 수행하지 않는다.

`accept_guesses=False`는 local/global 확정 행동을 계속 실행하고 실제 guess
직전에 멈춘다. `True`이면 guess도 실행해 WON/LOST까지 진행한다. 이전 결과의
여러 셀을 queue하지 않고, 항상 선택된 `SimpleMove` 하나를 그대로 `step()`에
적용한 뒤 fresh observation을 다시 분석한다.

`SimpleRunResult`는 `status`, `stop_reason`, 실제 `moves` tuple, `replay_data`,
`pending_decision`, `started_from_hidden`을 가진 frozen dataclass다.
`StopReason`은 `WON`, `LOST`, `GUESS_REQUIRED`다. Guess 대기 시 status는
PLAYING이며 실행하지 않은 추천을 `pending_decision`에 보존한다.

PLAYING에서 move가 없거나, 선택된 셀이 HIDDEN이 아니거나, 비종료 행동 후
HIDDEN 수가 감소하지 않으면 `SimpleRunnerError`를 발생시킨다. 각 행동의
단조 진행을 검사하므로 임의 step 제한이나 random/approximate fallback은 없다.

### Replay 기록과 범위

기존 UI와 같이 `step()` 이후 `engine.get_elapsed_time()`으로 이벤트를 기록한
다음, 지뢰가 배치된 board를 한 번 capture한다. Source는 `SOURCE_ALGORITHM`이고,
이벤트는 이번 호출의 실제 physical moves와 개수·좌표·action·순서가 일치한다.
승리 시 엔진의 자동 깃발은 별도 physical action으로 기록하지 않는다.
Snapshot은 recorder로만 전달되며 분석이나 move 선택으로 전달되지 않는다.

ReplayData v1은 종료를 요구하지 않는다. 미오픈 보드에서 시작했다면 완료 기록과
GUESS_REQUIRED partial 기록 모두 기존 ReplayPlayer와 JSON 경로로 재현된다.

**중간 합류의 한계:** 엔진은 이전 클릭 이력을 제공하지 않고 ReplayData v1은
시작 observation을 저장하지 않는다. 따라서 `started_from_hidden=False` 결과의
`replay_data`는 이번 실행 구간만 포함하며, 단독으로 기존 시작 상태를 재현할 수
없다. 이전 게임의 기록을 보존했다면 같은 board와 실제 시간 순서를 유지하여
`previous.events + result.replay_data.events`로 전체 ReplayData를 구성할 수 있다.
Runner는 가짜 초기화 클릭을 추가하지 않는다. 이미 종료된 게임에 붙으면
추가 moves/events는 비어 있다. Replay schema와 Player는 변경하지 않는다.

이번 단계는 위 두 모듈과 책임별 테스트까지만 제공하며 UI 연동은 포함하지 않는다.
