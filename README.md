# Minesweeper Project

Python과 PyQt5로 개발한 지뢰찾기 졸업프로젝트입니다.

기본적인 지뢰찾기 게임뿐 아니라 플레이 분석, Replay 기록 및 재생, 3BV/Ops 분석, ZiNi 계산과 제한된 고급 탐색 기능을 제공하는 것을 목표로 합니다.

## 주요 기능

### 지뢰찾기 게임

* 초급, 중급, 상급 및 사용자 지정 난이도
* 첫 클릭 이후 지뢰 배치
* 셀 열기, 깃발, 화음 기능
* 화음 작동 방식 설정
* 셀 크기 조절
* 승리 및 패배 상태 표시

### 플레이 통계

* Time 및 Est Time
* 3BV와 3BV/s
* Clicks, Left, Right, Chord
* CPS
* Efficiency 및 IOE
* Ops
* Thrp 및 Corr
* ZiNi, ZNE, ZNT

### Replay

* 현재 게임의 이벤트 기록
* JSON 형식 저장 및 불러오기
* Replay 저장과 다른 이름으로 저장
* 이전·다음 이벤트 및 처음·마지막 위치 이동
* Index 기반 자동 재생
* 실제 이벤트 시간을 사용하는 Time 기반 자동 재생
* 0.25배속부터 8배속까지 재생 속도 조절
* Replay 시점별 Counters 동기화
* 완료된 Replay와 미완료 Replay 구분

### 보드 및 ZiNi 분석

* 불변 `BoardSnapshot`
* 3BV 및 Ops 분석
* deterministic G.ZiNi
* bounded min-ties 탐색
* bounded neighborhood beam advanced search
* seeded-chain ranking policy
* 별도 subprocess를 사용한 ZiNi 지표 계산

Advanced ZiNi 탐색 결과는 전역 최적해나 최소 클릭 수를 보장하지 않습니다. 제한된 평가 범위 안에서 얻은 bounded best-so-far 결과로 취급합니다.

## 실행 방법

```powershell
pip install -r requirements.txt
python main.py
```

## 테스트

전체 자동 테스트를 실행합니다.

```powershell
python -m unittest discover -s tests
```

현재 `main` 기준으로 총 138개의 단위 및 회귀 테스트를 사용하고 있습니다.

## Benchmark

```powershell
python scripts/benchmark_zini_advanced.py --board board_c --mode quick
python scripts/benchmark_zini_advanced.py --board expert1003 --mode quick
```

Expert seed 1003 보드에서 다음 결과를 확인했습니다.

- deterministic G.ZiNi: 125 clicks
- standard_v1, 100 evaluations: 123 clicks
- standard_seeded_chain_v1, 500 evaluations: 121 clicks
- standard_seeded_chain_v1, 1000 evaluations: 120 clicks

120 clicks 결과는 Replay 유효성, 클릭 합계 및 깃발 유효성을 검증했으나 전역 최적 결과를 의미하지 않습니다.

## 주요 구조

```text
main.py
├─ core_engine.py
├─ ui_manager.py
├─ board_snapshot.py
├─ board_analyzer.py
├─ replay_model.py
├─ replay_recorder.py
├─ replay_json.py
├─ replay_player.py
├─ replay_statistics.py
├─ zini_core.py
├─ zini_min_ties.py
├─ zini_advanced.py
├─ zini_calculator.py
└─ zini_metric_worker.py
```

상세 설계와 모듈별 책임은 `ARCHITECTURE.md`에서 설명합니다.

## 개발 원칙

* UI와 게임 규칙 분리
* 게임 엔진의 PyQt5 비의존성 유지
* 분석 책임의 별도 모듈화
* 불변 데이터 구조 활용
* 공개 인터페이스 기반 모듈 연동
* 기능 추가 전후 회귀 테스트 수행
* 작은 작업 단위와 단계적 Git commit
* 정확히 보장되지 않은 결과를 최적해 또는 최소값으로 표현하지 않음
