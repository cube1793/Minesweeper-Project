# Minesweeper Project

Python과 PyQt5로 개발한 지뢰찾기 졸업프로젝트입니다. 직접 플레이하면서 통계를 확인하고, Simple Algorithm으로 현재 수를 분석하거나 자동 진행할 수 있습니다. Replay 기록·재생·분석과 3BV/Ops, ZiNi 보드 분석까지 구현되어 있습니다.

## 핵심 기능

- **게임:** 초급·중급·상급·사용자 지정 난이도, OPEN·FLAG·CHORD, 화음 입력 방식과 셀 크기 조절
- **플레이 통계:** Time, Est Time, 3BV, 3BV/s, Ops, 클릭별 active/wasted 집계, CPS, Efficiency, IOE, Thrp, Corr, ZiNi, ZNE, ZNT
- **Simple Algorithm:** 확정 수와 최소 지뢰 확률 후보 표시, 확정 수 자동 진행, 선택적인 추측 실행
- **Replay:** JSON 저장·불러오기, 위치 이동과 자동 재생, 시점별 통계, 추천과 실제 다음 수 비교

## Simple Algorithm

사람에게 보이는 열린 숫자·닫힌 칸·깃발과 공개 총 지뢰 수를 사용해 수를 추천합니다. 실제 숨겨진 지뢰 배치를 정답으로 참조하지 않으며, **깃발은 지뢰라고 가정**합니다.

1. **Local deterministic inference:** 열린 숫자에서 인접 깃발 수를 뺀 값으로 확정 안전/지뢰를 찾습니다.
2. **Exact probability:** local 확정 수가 없을 때 공개 조건을 만족하는 전체 보드 경우의 수로 지뢰 확률을 계산합니다.
3. 확률이 정확히 0 또는 1이면 **certainty**, 그 사이이면 **guess**입니다. Guess에서는 최소 지뢰 확률의 칸을 추천하므로 패배할 수 있습니다.

| UI 항목 | 동작 |
| --- | --- |
| 현재 상태 분석 | 현재 보드를 한 번 분석해 추천만 표시 |
| 분석 표시 | Live에서는 행동 후, Replay에서는 위치 변경 후 분석 갱신 |
| 확정 수 자동 진행 | Live에서 한 번에 한 행동을 실행하고 새 observation으로 다시 분석 |
| 추측 허용 | 자동 진행이 guess도 실행하도록 허용. OFF이면 추측 직전에 대기 |
| 확률 표시 | 이미 계산된 확률의 표시만 전환. Local 추론만 한 경우 확률을 추가 계산하지 않음 |
| Reduction | 화면의 열린 숫자를 `N − 인접 깃발 수`로 표시. 원본 observation은 유지 |

초록은 확정 안전, 빨강은 확정 지뢰, 주황은 최소 위험 후보이며 테두리는 선택된 추천을 뜻합니다. 여러 추천을 queue해서 실행하지 않습니다. 새 게임의 첫 수는 별도 [FIRST_CLICK 정책](ARCHITECTURE.md#first-click)을 따릅니다.

## Replay / Replay Analysis

**Replay**는 보드와 실제 클릭 이벤트를 기록하고 같은 순서로 재생하는 기능입니다.

- `Replay 저장`과 `Replay 다른 이름으로 저장`으로 JSON을 저장하고, `Replay 불러오기`로 다시 열 수 있습니다. 지뢰 배치가 끝났다면 미완료 게임도 저장할 수 있습니다.
- 게임 종료 후 `이번 판 Replay`로 파일 저장 없이 바로 볼 수 있습니다.
- 처음·이전·다음·마지막 위치와 slider 이동, Index/Time 자동 재생을 지원합니다. Time 모드는 기록된 이벤트 시간을 사용하며 0.25배속부터 8배속까지 조절합니다.
- 완료된 Replay는 현재 위치에 맞는 Counters를 표시하고, 미완료 Replay의 Counters는 마스킹합니다.
- Replay 종료는 이전 Live 판을 이어가는 대신 저장해 둔 Live 난이도로 **새 게임**을 시작합니다.

**Replay Analysis**는 재생 중인 현재 position에서 Simple Algorithm의 추천을 구한 뒤 실제 다음 이벤트와 비교합니다. `현재 상태 분석`으로 한 번 분석하거나 `분석 표시`로 이동에 따라 갱신할 수 있습니다. 확률·Reduction 표시도 사용할 수 있습니다.

비교 결과는 추천과 일치, 동등 후보, 추천과 다름, 비교 대상 아님, 다음 실제 수 없음으로 구분합니다. **“추천과 다름”은 오답이나 실수 판정이 아닙니다.** 분석은 행동을 실행하지 않으며 Replay에서는 자동 진행·추측 허용이 비활성화됩니다. 위치와 비교의 정확한 의미는 [Replay index](ARCHITECTURE.md#replay-index)와 [비교 규칙](ARCHITECTURE.md#replay-comparison)을 참고하세요.

## ZiNi / 보드 분석

- **3BV/Ops:** opening 그룹과 고립 숫자 칸을 분석해 보드의 정적 지표와 플레이 진행량을 계산합니다.
- **ZiNi:** 실제 mine layout을 사용하는 board metric입니다. 위 Simple Algorithm과 정보 경계 및 목적이 다릅니다.
- deterministic G.ZiNi, maximum-Premium min-ties 탐색, neighborhood beam 및 seeded-chain 탐색을 제공합니다.
- 화면의 ZiNi는 별도 subprocess에서 계산한 **bounded best-so-far**입니다. 전역 최적해나 정확한 최소 클릭 수를 보장하지 않습니다.

계산 전략과 결과 해석은 [ZiNi 설계](ARCHITECTURE.md#zini-results)에 정리되어 있습니다.

## 실행 방법

Python 3.10 이상과 PyQt5가 필요합니다. Repository 루트에서 실행합니다.

```powershell
python -m pip install -r requirements.txt
python main.py
```

기본 보드는 상급 `30 × 16 / 99 mines`입니다. UI에서 난이도를 바꿀 수 있습니다.
Windows에서는 `main.py`가 Qt import 전에 설치된 PyQt5의 플랫폼 플러그인 경로를 설정합니다.

## 프로젝트 구조

아래는 역할별 파일 안내입니다. 실제 의존 방향은 [Architecture 구조도](ARCHITECTURE.md#dependencies)를 참고하세요.

```text
Minesweeper-Project/
├─ main.py                      # 진입점, engine 생성 및 UI 주입
├─ ui_manager.py                # PyQt5 화면, 입력, Live Auto, Replay 제어
├─ core_engine.py               # 게임 규칙, 상태, 시간·클릭 통계
├─ board_snapshot.py            # 불변 정적 보드 데이터
├─ board_analyzer.py            # 3BV/Ops 분석
├─ simple_algorithm.py          # local deterministic inference
├─ simple_probability.py        # exact probability와 확률 기반 선택
├─ simple_decision.py           # 순수 position 분석 및 decision 통합
├─ simple_runner.py             # UI 없이 동기 실행·중단·Replay 기록
├─ live_analysis.py             # 계산된 decision의 표시 모델과 Reduction
├─ replay_model.py              # Replay 데이터 계약
├─ replay_recorder.py           # 실제 이벤트와 확정 보드 기록
├─ replay_json.py               # JSON 변환·파일 입출력
├─ replay_player.py             # 독립 engine으로 재생
├─ replay_analysis.py           # 현재 position 추천과 다음 이벤트 비교
├─ replay_statistics.py         # 시점별 통계 timeline
├─ zini_calculator.py           # ZiNi 공개 API와 결과·설정 모델
├─ zini_core.py                 # 공통 시뮬레이션과 deterministic 정책
├─ zini_min_ties.py             # maximum-Premium 동점 탐색
├─ zini_advanced.py             # bounded neighborhood beam·chain 정책
├─ zini_metric_worker.py        # UI ZiNi 계산용 subprocess
├─ scripts/
│  └─ benchmark_zini_advanced.py
└─ tests/                       # unittest 기반 단위·회귀·UI 테스트
```

## 테스트

Repository 루트에서 실행합니다.

```powershell
python -m unittest discover -s tests -v
```

Engine, 보드 분석, Replay, Simple Algorithm, Live/Replay Analysis와 Auto, ZiNi를 검증합니다. 구체적인 파일과 검증 범위는 [테스트 전략](ARCHITECTURE.md#test-strategy)을 참고하세요. 일부 UI 테스트는 PyQt5가 없으면 skip되므로 UI까지 검증하려면 위 의존성을 설치해야 합니다.

Qt UI 테스트는 기본적으로 `offscreen` 플랫폼을 사용합니다. Windows에서 플랫폼 플러그인 탐색 오류가 발생하면 `QT_QPA_PLATFORM_PLUGIN_PATH`를 해당 Python의 실제 PyQt5 설치 경로 아래 `Qt5/plugins/platforms` 또는 `Qt/plugins/platforms`로 지정합니다.

## Benchmark

고정 보드에서 ZiNi 전략별 클릭 수, 탐색 종료 사유, 실행 시간과 trace 유효성을 비교합니다.

```powershell
python scripts/benchmark_zini_advanced.py --board board_c --mode quick
python scripts/benchmark_zini_advanced.py --board expert1003 --mode quick
```

`--mode full`은 더 많은 평가 예산과 seed를 사용하며 수 분이 걸릴 수 있습니다. `--csv results.csv`로 결과를 저장할 수 있습니다. Benchmark는 단위 테스트를 대체하지 않습니다.

Expert seed 1003의 알려진 **120-click trace**는 `tests/test_zini_core.py`의 회귀 fixture로 유지됩니다. 테스트는 해당 trace의 재현, 클릭 합계, 안전 칸 완료와 깃발 유효성을 확인합니다. 이는 모든 설정의 탐색이 같은 값을 찾는다는 뜻은 아닙니다.

## 주요 제한과 향후 방향

- 잘못 꽂은 깃발은 분석의 가정을 깨뜨릴 수 있습니다. 감지된 모순은 분석 불가로 표시하지만 모든 오답 깃발을 찾아내지는 못합니다.
- 큰 constraint component의 exact probability는 지수 시간이 걸릴 수 있습니다. 현재 Live/Replay 분석은 UI thread에서 동기 실행되어 화면이 지연될 수 있습니다.
- Simple Algorithm은 닫힌 칸의 OPEN/FLAG만 추천합니다. CHORD·UNFLAG는 추천 범위 밖입니다.
- Replay schema v1은 full-game과 continuation/suffix를 구분할 metadata가 없습니다. 중간부터 기록한 구간의 복원·분석에는 [schema v1 한계](ARCHITECTURE.md#replay-schema-v1)가 적용됩니다.
- 향후 후보는 UI controller/worker 관리 분리, 분석 성능 개선, Replay checkpoint, subprocess 실패·취소 검증 확대입니다. AI 학습 환경은 아직 구현하지 않았습니다.

설계 목표, 모듈별 책임, 데이터 흐름과 invariants는 **[ARCHITECTURE.md](ARCHITECTURE.md)**에서 설명합니다.

## 라이선스 / License

Copyright © 2026 cube1793

이 프로젝트는 GNU General Public License v3.0 only (`GPL-3.0-only`)에 따라 배포됩니다.  
소스 코드는 해당 라이선스의 조건에 따라 사용, 수정 및 재배포할 수 있습니다.  
자세한 내용은 [`LICENSE`](LICENSE) 파일을 참고하세요.

This project is licensed under the GNU General Public License v3.0 only (`GPL-3.0-only`).  
See [`LICENSE`](LICENSE) for details.
