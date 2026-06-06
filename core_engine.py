"""
core_engine.py
지뢰찾기 핵심 게임 엔진 (UI 비의존, 순수 파이썬)

PyQt5 등 어떤 UI 라이브러리에도 의존하지 않는다.
엔진은 UI의 정책(화음 모드 등)을 알지 못하며,
전달받은 액션을 그대로 해석해 상태를 갱신할 뿐이다.
향후 강화학습(Gymnasium) 환경 확장을 위해
step() / reset() / get_observation() 인터페이스를 제공한다.

[1.5단계] 3BV / Ops 정밀 계산:
    - 지뢰 배치가 끝난 직후 보드를 분석하여 모든 안전 칸을 세 부류로
      마킹한다:
        (a) 오프닝 내부 칸 : 주변 지뢰 수가 0인 빈칸. BFS로 인접한 빈칸들을
            하나의 '오프닝 그룹'으로 묶어 그룹 ID를 부여한다.
        (b) 오프닝 테두리 숫자 칸 : 주변 지뢰 수가 1 이상이면서, 적어도
            하나의 오프닝 내부 칸과 인접한 숫자 칸.
        (c) 고립된 숫자 칸 : 주변 지뢰 수가 1 이상이면서, 어떤 오프닝
            내부 칸과도 인접하지 않은 숫자 칸.
    - 총 Ops = 오프닝 그룹의 개수.
    - 총 3BV = 오프닝 그룹의 개수 + 고립된 숫자 칸의 개수.

    동적 분자(유효 점수) 규칙:
        - 오프닝 내부 칸이 '그룹 단위로 최초로' 열리면 유효 3BV +1, 유효 Ops +1.
        - 고립된 숫자 칸이 최초로 열리면 유효 3BV +1.
        - 오프닝 테두리 숫자 칸을 플레이어가 직접 클릭/화음으로 열어도
          분자에 포함하지 않는다(연쇄 오픈으로 들어오는 그룹 점수와의
          중복을 피하기 위함).
        - 패배(LOST)를 유발한 화음 루프 안에서 드러난 칸이라도 위 유효
          조건을 만족하면 데이터 수집을 위해 정밀하게 누적한다.

[정밀 타이머 및 파생 지표]:
    - time.perf_counter() 기반 절대 시각으로 경과 시간을 측정한다.
      첫 액션(좌클릭 OPEN 또는 우클릭 FLAG)이 발생하는 순간 시작 시각을
      기록하고, 게임 종료(WON/LOST) 시점에 종료 시각을 고정(freeze)한다.
      reset() 시 모든 시간 상태를 초기화한다.
    - 3BV/s = 최종 유효 3BV / 최종 경과 시간.
    - Estimated time = 총 3BV / 최종 3BV/s. (ZeroDivision 예외 처리)

    마스킹 및 소수점 포맷 규칙(get_stats):
        - PLAYING:
            * Time : f"{elapsed:.1f}" (실시간 한 자리)
            * 3BV/Ops : "-/-", 3BV/s/Est time : "-" 로 마스킹.
        - LOST:
            * Time : f"{elapsed:.3f}" (세 자리)
            * 3BV/Ops : 실제 "유효/총", 3BV/s : f"{:.4f}", Est time : f"{:.3f}".
              (단, 3BV/s가 0.0이거나 ZeroDivision이면 Est time은 "-"로 마스킹)
        - WON:
            * Time : f"{elapsed:.3f}" (세 자리)
            * 3BV/Ops : 실제 "유효/총"(유효=총), 3BV/s : f"{:.4f}",
              Est time : 요구사항상 표시하지 않으므로 "-".

[2단계] 마우스 클릭 분석(Active vs Wasted):
    - 액션별(left/right/chord) 활성(Active) 및 초과(Wasted) 클릭을 추적한다.
      관심사 분리 원칙에 따라 엔진은 UI의 화음 모드를 알 필요가 없으며,
      오직 step(x, y, action)으로 들어오는 '액션 타입'과 실행 전/후의
      '보드 상태 변화량(Snapshot Delta)'만으로 활성/초과를 판정한다.

    초과 클릭(Wasted Clicks) 7대 기준:
        1) [OPEN]  이미 열려 있는 칸에 OPEN          → wasted_left
        2) [FLAG]  깃발이 꽂힌 칸에 FLAG(=해제됨)     → wasted_right
        3) [FLAG]  지뢰 없는 안전 칸에 FLAG(=오답 깃발) → wasted_right
        4) [CHORD] 숫자 != 주위 깃발 수인데 CHORD 시도 → wasted_chord
        5) [CHORD] 화음 실행 전후 열린 칸 수 변화 0    → wasted_chord
        6) [OPEN]  깃발 꽂힌 칸에 OPEN(가드로 무반응)  → wasted_left
        7) [FLAG]  이미 열린 칸에 FLAG(가드로 무반응)  → wasted_right

    위 7대 기준에 해당하지 않으면서 보드 전진(3BV 전진, 올바른 지뢰 위
    깃발 배치 등)에 실질적으로 기여한 클릭은 해당 active 카운터를 올린다.
    각 사전의 "total"은 left + right + chord 의 합과 항상 일치한다.

    CPS = (총 활성 클릭 + 총 초과 클릭) / 경과 시간. (f"{:.4f}")

    Clicks / Left / Right / Chord 표기 규칙:
        - PLAYING : 항목별 (active + wasted) 정수만 실시간 노출.
        - WON/LOST: "X + Y" (X=활성, Y=초과). 단 Y==0이면 "+ Y"를
          완전히 생략하고 "X" 정수만 노출한다.
"""

import random
import time
from collections import deque
from enum import IntEnum

from board_analyzer import BoardAnalysis, analyze_board
from board_snapshot import BoardSnapshot


class CellState(IntEnum):
    """get_observation()이 반환하는 가시적 셀 상태 코드."""
    HIDDEN = -2       # 닫힌 칸
    FLAGGED = -3      # 깃발이 꽂힌 칸 (정상)
    EXPLODED = -4     # 플레이어가 밟아 폭발한 지뢰
    MINE = -5         # 게임오버 시 드러나는 (밟지 않은) 지뢰
    FALSE_FLAG = -6   # 패배 시: 지뢰가 없는데 잘못 꽂은 깃발(오답)
    # 0 ~ 8 : 열린 칸 주변 지뢰 수


class GameStatus(IntEnum):
    """게임 진행 상태."""
    PLAYING = 0
    WON = 1
    LOST = 2


class Action(IntEnum):
    """
    step()에 전달되는 액션 정의.

    원칙: 엔진은 UI 정책을 모른다.
    - OPEN  : 닫힌 칸을 연다. 이미 열린 칸이면 아무 동작도 하지 않는다.
    - FLAG  : 깃발 토글.
    - CHORD : 명시적 화음. UI가 화음을 발동시키기로 결정했을 때만 보낸다.
    """
    OPEN = 0
    FLAG = 1
    CHORD = 2


class MinesweeperEngine:
    """
    지뢰찾기 게임 엔진.

    좌표 규약: (x, y) 에서 x는 열(column, 가로), y는 행(row, 세로).
    내부 2D 배열은 [y][x] 로 접근한다.

    첫 클릭 안전 규칙:
        - 게임에서 '첫 좌클릭(OPEN)'이 발생하는 순간에만 지뢰를 배치하며,
          이때 클릭한 칸과 주변 8칸을 안전지대로 비운다.
        - 만약 그 전에 '깃발(FLAG)'이 먼저 들어오면, 그 시점에 즉시
          (안전지대 없이) 지뢰를 배치한다. 따라서 첫 액션이 우클릭이었다면
          이후 첫 좌클릭이라도 지뢰를 밟을 수 있다.

    화음 규칙:
        - 화음으로 주변 칸을 열다가 지뢰를 밟더라도 루프를 중단하지 않고,
          대상 8칸의 안전한 칸과 지뢰 칸을 모두 연 뒤 LOST로 전이한다.
          (통계/AI 학습을 위해 한 액션의 영향력을 보드에 전부 표현)

    타이머 규칙:
        - 첫 액션(OPEN 또는 FLAG)이 들어오는 순간 perf_counter() 시작 시각 기록.
        - WON/LOST로 전이하는 순간 종료 시각 고정.
        - 경과 시간은 (종료시각 or 현재시각) - 시작시각 으로 계산.

    클릭 분석 규칙:
        - 각 step() 호출은 정확히 하나의 물리적 클릭으로 간주한다.
        - 한 번의 step()은 active 또는 wasted 중 정확히 한 쪽에만,
          그리고 액션 타입에 대응하는 단 하나의 카테고리(left/right/chord)에만
          +1 을 기여한다. (이중 집계 방지)
    """

    # 안전 칸 분류 코드 (내부 마킹 전용)
    CELL_OPENING = 0      # 오프닝 내부 칸 (adjacent == 0)
    CELL_BORDER = 1       # 오프닝 테두리 숫자 칸
    CELL_ISOLATED = 2     # 고립된 숫자 칸

    def __init__(self, width: int = 30, height: int = 16, num_mines: int = 99):
        if num_mines >= width * height:
            raise ValueError("지뢰 수는 전체 칸 수보다 적어야 합니다.")

        self.width = width
        self.height = height
        self.num_mines = num_mines

        self._mines = None
        self._adjacent = None
        self._revealed = None
        self._flagged = None
        self._exploded_cells = None  # 폭발한 지뢰 좌표 집합

        # --- 3BV / Ops 분석용 정적 데이터 ---
        self._opening_id = None       # [y][x]: 오프닝 그룹 ID, 비오프닝은 -1
        self._cell_class = None       # [y][x]: CELL_OPENING / BORDER / ISOLATED, 지뢰는 None
        self._total_3bv = 0           # 총 3BV 분모
        self._total_ops = 0           # 총 Ops 분모

        # --- 3BV / Ops 동적 추적용 ---
        self._opened_groups = None    # 이미 점수에 반영된 오프닝 그룹 ID 집합
        self._opened_isolated = None  # 이미 점수에 반영된 고립 숫자 칸 좌표 집합
        self._effective_3bv = 0       # 유효 3BV 분자
        self._effective_ops = 0       # 유효 Ops 분자

        # --- 정밀 타이머 상태 ---
        self._timer_started = False   # 첫 액션으로 타이머가 시작되었는가
        self._start_time = None       # perf_counter() 시작 절대 시각
        self._end_time = None         # 종료(WON/LOST) 시 고정된 절대 시각

        # --- 마우스 클릭 분석 카운터 ---
        # 액션별 활성/초과 클릭. total은 left+right+chord의 합과 항상 일치.
        self._active_clicks = {"total": 0, "left": 0, "right": 0, "chord": 0}
        self._wasted_clicks = {"total": 0, "left": 0, "right": 0, "chord": 0}

        self.status = GameStatus.PLAYING
        self._mines_placed = False
        self._cells_to_reveal = 0

        self.reset()

    # ------------------------------------------------------------------
    # 공개 인터페이스
    # ------------------------------------------------------------------
    def reset(self):
        """게임 상태를 초기화하고 첫 관측값을 반환한다."""
        self._mines = set()
        self._adjacent = [[0] * self.width for _ in range(self.height)]
        self._revealed = [[False] * self.width for _ in range(self.height)]
        self._flagged = [[False] * self.width for _ in range(self.height)]
        self._exploded_cells = set()

        # 3BV / Ops 정적 데이터 초기화
        self._opening_id = [[-1] * self.width for _ in range(self.height)]
        self._cell_class = [[None] * self.width for _ in range(self.height)]
        self._total_3bv = 0
        self._total_ops = 0

        # 3BV / Ops 동적 추적 초기화
        self._opened_groups = set()
        self._opened_isolated = set()
        self._effective_3bv = 0
        self._effective_ops = 0

        # 정밀 타이머 초기화
        self._timer_started = False
        self._start_time = None
        self._end_time = None

        # 마우스 클릭 분석 카운터 초기화
        self._active_clicks = {"total": 0, "left": 0, "right": 0, "chord": 0}
        self._wasted_clicks = {"total": 0, "left": 0, "right": 0, "chord": 0}

        self.status = GameStatus.PLAYING
        self._mines_placed = False
        self._cells_to_reveal = self.width * self.height - self.num_mines

        return self.get_observation()

    def reset_with_mines(
        self,
        width: int,
        height: int,
        num_mines: int,
        mine_positions,
    ):
        """
        저장된 지뢰 배치로 게임 상태를 초기화하고 첫 관측값을 반환한다.

        리플레이 재현을 위한 public API이다. 랜덤 지뢰 배치를 수행하지 않고,
        전달받은 mine_positions를 확정 보드로 사용한다.
        """
        if width <= 0 or height <= 0:
            raise ValueError("보드 크기는 양수여야 합니다.")
        if num_mines >= width * height:
            raise ValueError("지뢰 수는 전체 칸 수보다 적어야 합니다.")

        mines = set()
        for position in mine_positions:
            try:
                x, y = position
            except (TypeError, ValueError) as exc:
                raise ValueError("지뢰 좌표는 (x, y) 쌍이어야 합니다.") from exc
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError("지뢰 좌표가 보드 범위를 벗어났습니다.")
            mines.add((x, y))

        if len(mines) != num_mines:
            raise ValueError("지뢰 좌표 수가 num_mines와 일치해야 합니다.")

        self.width = width
        self.height = height
        self.num_mines = num_mines
        self.reset()

        self._mines = mines
        self._compute_adjacency()
        self._mines_placed = True
        self._apply_board_analysis(analyze_board(self.get_board_snapshot()))

        return self.get_observation()

    def step(self, x: int, y: int, action: int):
        """
        하나의 액션(=하나의 물리적 클릭)을 적용하고 결과를 반환한다.
        (Gymnasium 스타일)

        Returns:
            observation, reward, terminated, truncated, info
            (info에는 항상 마스킹 규칙이 적용된 'stats' 딕셔너리를 포함한다.)

        클릭 분석:
            - 게임이 이미 종료된 상태(WON/LOST)에서 들어오는 입력은
              물리적 클릭으로 보지 않고 카운트하지 않는다(게임은 멈춰 있음).
            - 좌표 범위를 벗어난 입력 역시 유효 클릭으로 보지 않는다.
            - 그 외에는 액션별 핸들러가 active/wasted 중 한 쪽으로 분류한다.
        """
        if self.status != GameStatus.PLAYING:
            return (
                self.get_observation(), 0.0, True, False,
                {"status": self.status, "stats": self.get_stats()},
            )

        if not self._in_bounds(x, y):
            return (
                self.get_observation(), 0.0, False, False,
                {"invalid": True, "stats": self.get_stats()},
            )

        # 첫 유효 액션(OPEN/FLAG) 진입 시점에 타이머 시작.
        # CHORD는 반드시 이미 열린 숫자 칸에서만 발동하므로,
        # 단독 첫 액션이 될 수 없어 타이머 시작 트리거에서 제외한다.
        if action in (Action.OPEN, Action.FLAG):
            self._start_timer_if_needed()

        # 액션별 핸들러로 위임. 각 핸들러는 보드 상태를 변경하고
        # 동시에 active/wasted 클릭 카운터를 정확히 1회 갱신한다.
        if action == Action.FLAG:
            self._handle_flag_action(x, y)
        elif action == Action.CHORD:
            self._handle_chord_action(x, y)
        elif action == Action.OPEN:
            self._handle_open_action(x, y)
        else:
            return (
                self.get_observation(), 0.0, False, False,
                {"invalid_action": True, "stats": self.get_stats()},
            )

        self._update_status()

        # 종료로 전이했다면 종료 시각을 고정한다.
        if self.status != GameStatus.PLAYING:
            self._freeze_timer()

        terminated = self.status != GameStatus.PLAYING
        reward = self._compute_reward()
        info = {"status": self.status, "stats": self.get_stats()}
        return self.get_observation(), reward, terminated, False, info

    def get_observation(self):
        """
        현재 보드의 가시적 상태를 2D 리스트로 반환한다.
        -2=닫힘, -3=깃발, -4=폭발지뢰, -5=드러난지뢰, -6=오답깃발, 0~8=주변지뢰수.

        게임오버(LOST) 시:
            - 밟은 칸(들)은 EXPLODED.
            - 지뢰 위에 정확히 꽂은 깃발은 FLAGGED(정답) 유지.
            - 지뢰가 없는데 잘못 꽂은 깃발은 FALSE_FLAG(오답)로 가공.
            - 깃발 없는 미오픈 지뢰는 MINE으로 노출.
        """
        lost = self.status == GameStatus.LOST
        obs = [[CellState.HIDDEN.value] * self.width for _ in range(self.height)]

        for y in range(self.height):
            for x in range(self.width):
                is_mine = (x, y) in self._mines

                if (x, y) in self._exploded_cells:
                    obs[y][x] = CellState.EXPLODED.value
                elif self._revealed[y][x]:
                    obs[y][x] = self._adjacent[y][x]
                elif self._flagged[y][x]:
                    # 패배 시 지뢰 없는 칸의 깃발은 오답으로 구분
                    if lost and not is_mine:
                        obs[y][x] = CellState.FALSE_FLAG.value
                    else:
                        obs[y][x] = CellState.FLAGGED.value
                elif lost and is_mine:
                    obs[y][x] = CellState.MINE.value
                else:
                    obs[y][x] = CellState.HIDDEN.value
        return obs

    def get_board_snapshot(self) -> BoardSnapshot:
        """
        분석 모듈이 사용할 수 있는 읽기 전용 보드 스냅샷을 반환한다.

        지뢰가 아직 배치되지 않은 새 게임 상태에서는 mines_placed=False,
        mines=frozenset(), adjacent=현재 0 배열 형태로 반환한다. 즉, 호출은
        항상 가능하지만 ZiNi/3BV 같은 확정 보드 분석은 mines_placed를 먼저
        확인해야 한다.
        """
        return BoardSnapshot(
            width=self.width,
            height=self.height,
            num_mines=self.num_mines,
            mines_placed=self._mines_placed,
            mines=frozenset(self._mines),
            adjacent=tuple(tuple(row) for row in self._adjacent),
        )

    def count_flags(self):
        """현재 꽂힌 깃발 수 (지뢰 카운터 표시용)."""
        return sum(row.count(True) for row in self._flagged)

    def get_elapsed_time(self) -> float:
        """
        현재 경과 시간(초)을 부동소수점으로 반환한다.
        - 타이머 미시작: 0.0
        - 진행 중: 현재 시각 - 시작 시각
        - 종료(WON/LOST): 고정된 종료 시각 - 시작 시각
        UI의 실시간 표시(고주파 폴링)를 위해 공개 메서드로 제공한다.
        """
        if not self._timer_started or self._start_time is None:
            return 0.0
        end = self._end_time if self._end_time is not None else time.perf_counter()
        return end - self._start_time

    def get_stats(self) -> dict:
        """
        UI 표시용 통계 딕셔너리를 상태별 마스킹/소수점 규칙에 맞춰 반환한다.

        반환 키:
            - "time"         : Time 항목 문자열
            - "bbbv"         : 3BV 항목 ("유효/총" 또는 "-/-")
            - "ops"          : Ops 항목 ("유효/총" 또는 "-/-")
            - "bbbv_per_sec" : 3BV/s 항목 (소수 4자리 또는 "-")
            - "est_time"     : Estimated time 항목 (소수 3자리 또는 "-")
            - "clicks"       : 총 클릭 (PLAYING: 정수, 종료: "X + Y" 또는 "X")
            - "left"         : 좌클릭 (동일 규칙)
            - "right"        : 우클릭 (동일 규칙)
            - "chord"        : 화음   (동일 규칙)
            - "cps"          : CPS 항목 (소수 4자리 또는 "-")
        """
        elapsed = self.get_elapsed_time()

        if self.status == GameStatus.PLAYING:
            # 진행 중: Time만 실시간 한 자리, 3BV류는 마스킹.
            # 클릭류는 (active+wasted) 합산 정수만 실시간 노출.
            return {
                "time": f"{elapsed:.1f}",
                "bbbv": "-/-",
                "ops": "-/-",
                "bbbv_per_sec": "-",
                "est_time": "-",
                "clicks": self._format_click_playing("total"),
                "left": self._format_click_playing("left"),
                "right": self._format_click_playing("right"),
                "chord": self._format_click_playing("chord"),
                "cps": "-",
            }

        # 종료 상태 공통: 3BV/Ops 실제값, Time 세 자리.
        bbbv_str = f"{self._effective_3bv}/{self._total_3bv}"
        ops_str = f"{self._effective_ops}/{self._total_ops}"

        # 3BV/s = 최종 유효 3BV / 최종 경과 시간 (ZeroDivision 방어)
        try:
            bbbv_per_sec = self._effective_3bv / elapsed
        except ZeroDivisionError:
            bbbv_per_sec = 0.0
        bbbv_s_str = f"{bbbv_per_sec:.4f}"

        # CPS = (총 활성 + 총 초과) / 경과 시간 (ZeroDivision 방어)
        total_clicks = self._active_clicks["total"] + self._wasted_clicks["total"]
        try:
            cps = total_clicks / elapsed
        except ZeroDivisionError:
            cps = 0.0
        cps_str = f"{cps:.4f}"

        if self.status == GameStatus.LOST:
            # Estimated time = 총 3BV / 최종 3BV/s.
            # 첫 수 폭사 등으로 3BV/s가 0.0이거나 ZeroDivision이면 "-"로 마스킹.
            if bbbv_per_sec <= 0.0:
                est_str = "-"
            else:
                try:
                    est_time = self._total_3bv / bbbv_per_sec
                    est_str = f"{est_time:.3f}"
                except ZeroDivisionError:
                    est_str = "-"
        else:
            # WON: Estimated time은 표시하지 않는다.
            est_str = "-"

        return {
            "time": f"{elapsed:.3f}",
            "bbbv": bbbv_str,
            "ops": ops_str,
            "bbbv_per_sec": bbbv_s_str,
            "est_time": est_str,
            "clicks": self._format_click_final("total"),
            "left": self._format_click_final("left"),
            "right": self._format_click_final("right"),
            "chord": self._format_click_final("chord"),
            "cps": cps_str,
        }

    # ------------------------------------------------------------------
    # 클릭 표기 포맷 헬퍼
    # ------------------------------------------------------------------
    def _format_click_playing(self, key: str) -> str:
        """
        PLAYING 중 클릭 항목 표기: (active + wasted) 합산 정수.
        key는 "total"/"left"/"right"/"chord" 중 하나.
        """
        total = self._active_clicks[key] + self._wasted_clicks[key]
        return str(total)

    def _format_click_final(self, key: str) -> str:
        """
        WON/LOST 종료 후 클릭 항목 표기: "X + Y" (X=활성, Y=초과).
        단, Y == 0 이면 "+ Y"를 완전히 생략하고 "X" 정수만 반환한다.
        """
        active = self._active_clicks[key]
        wasted = self._wasted_clicks[key]
        if wasted == 0:
            return str(active)
        return f"{active} + {wasted}"

    # ------------------------------------------------------------------
    # 클릭 분석 카운터 헬퍼
    # ------------------------------------------------------------------
    def _record_active(self, category: str):
        """활성 클릭 +1. category는 'left'/'right'/'chord'."""
        self._active_clicks[category] += 1
        self._active_clicks["total"] += 1

    def _record_wasted(self, category: str):
        """초과 클릭 +1. category는 'left'/'right'/'chord'."""
        self._wasted_clicks[category] += 1
        self._wasted_clicks["total"] += 1

    # ------------------------------------------------------------------
    # 액션 핸들러 (보드 변경 + 클릭 분석을 함께 책임진다)
    # ------------------------------------------------------------------
    def _handle_open_action(self, x: int, y: int):
        """
        OPEN 액션 처리 및 클릭 분석.

        초과 기준:
            (1) 이미 열린 칸에 OPEN → wasted_left
            (6) 깃발 꽂힌 칸에 OPEN(가드로 무반응) → wasted_left
        그 외 닫힌 안전 칸/지뢰 칸을 실제로 여는 경우 → active_left.
        (지뢰를 밟아 폭발하는 클릭도 '보드를 전진시킨 실제 동작'이므로
         active로 집계한다. 초과 기준 7대 항목에 폭사는 포함되지 않는다.)
        """
        # 기준 (1): 이미 열린 칸
        if self._revealed[y][x]:
            self._record_wasted("left")
            return

        # 기준 (6): 깃발 꽂힌 칸 (시스템 가드)
        if self._flagged[y][x]:
            self._record_wasted("left")
            return

        # 실제 오픈 수행 (첫 좌클릭이면 안전지대로 지뢰 배치)
        if not self._mines_placed:
            self._place_mines(safe_x=x, safe_y=y)

        self._reveal_single(x, y)
        self._record_active("left")

    def _handle_flag_action(self, x: int, y: int):
        """
        FLAG 액션 처리 및 클릭 분석.

        초과 기준:
            (7) 이미 열린 칸에 FLAG(가드로 무반응) → wasted_right
            (2) 깃발 꽂힌 칸에 FLAG(=해제됨)       → wasted_right
            (3) 지뢰 없는 안전 칸에 FLAG(=오답 깃발) → wasted_right
        그 외(닫힌 '지뢰' 칸에 새 깃발을 올바르게 꽂는 경우) → active_right.
        """
        # 기준 (7): 이미 열린 칸 (시스템 가드)
        if self._revealed[y][x]:
            self._record_wasted("right")
            return

        # 첫 액션이 깃발이면 이 시점에 (안전지대 없이) 지뢰 배치
        if not self._mines_placed:
            self._place_mines(safe_x=None, safe_y=None)

        if self._flagged[y][x]:
            # 기준 (2): 깃발 해제
            self._flagged[y][x] = False
            self._record_wasted("right")
            return

        # 새로 깃발을 꽂는 경우: 지뢰 위면 active, 안전 칸이면 wasted(오답)
        self._flagged[y][x] = True
        if (x, y) in self._mines:
            self._record_active("right")
        else:
            # 기준 (3): 지뢰 없는 안전 칸에 잘못된 깃발
            self._record_wasted("right")

    def _handle_chord_action(self, x: int, y: int):
        """
        CHORD 액션 처리 및 클릭 분석.

        초과 기준:
            - 닫힌/깃발 칸에서 화음 시도(열린 숫자 칸이 아님)   → wasted_chord
            - 숫자 0인 칸에서 화음 시도(열 대상 없음)          → wasted_chord
            (4) 숫자 != 주위 깃발 수인데 화음 시도            → wasted_chord
            (5) 화음 실행 전후 열린 칸 수 변화 0(공치기)      → wasted_chord
        실제로 한 칸 이상 새로 열려 보드를 전진시키면         → active_chord.
        """
        # 화음은 '열린 숫자 칸'에서만 의미가 있다.
        if not self._revealed[y][x]:
            self._record_wasted("chord")
            return

        number = self._adjacent[y][x]
        if number == 0:
            # 숫자 0(빈칸)에서는 열 대상이 없으므로 공치기와 동일.
            self._record_wasted("chord")
            return

        flag_count = sum(
            1 for nx, ny in self._neighbors(x, y) if self._flagged[ny][nx]
        )
        # 기준 (4): 숫자와 주위 깃발 수 불일치 → 화음 미발동
        if flag_count != number:
            self._record_wasted("chord")
            return

        # 화음 발동: 실행 전후 열린 칸 수의 변화량으로 active/wasted 판정.
        before = self._count_revealed()
        for nx, ny in self._neighbors(x, y):
            if not self._revealed[ny][nx] and not self._flagged[ny][nx]:
                self._reveal_single(nx, ny)
        after = self._count_revealed()

        # 기준 (5): 변화 0(공치기) → wasted, 한 칸이라도 열렸으면 active
        if after - before > 0:
            self._record_active("chord")
        else:
            self._record_wasted("chord")

    # ------------------------------------------------------------------
    # 타이머 내부 헬퍼
    # ------------------------------------------------------------------
    def _start_timer_if_needed(self):
        """첫 액션 진입 시 한 번만 시작 시각을 기록한다."""
        if not self._timer_started:
            self._timer_started = True
            self._start_time = time.perf_counter()
            self._end_time = None

    def _freeze_timer(self):
        """종료 시 종료 시각을 한 번만 고정한다."""
        if self._timer_started and self._end_time is None:
            self._end_time = time.perf_counter()

    # ------------------------------------------------------------------
    # 내부 로직
    # ------------------------------------------------------------------
    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def _neighbors(self, x: int, y: int):
        """주변 8칸 좌표 제너레이터."""
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self._in_bounds(nx, ny):
                    yield nx, ny

    def _place_mines(self, safe_x=None, safe_y=None):
        """
        지뢰 배치. safe 좌표가 주어지면 그 칸과 주변 8칸을 안전지대로 비운다.
        safe 좌표가 None이면(첫 액션이 깃발인 경우) 안전지대 없이 배치한다.
        배치가 끝나면 인접 지뢰 수를 계산하고 3BV/Ops 정적 분석을 수행한다.
        """
        if safe_x is not None and safe_y is not None:
            safe_zone = {(safe_x, safe_y)}
            safe_zone.update(self._neighbors(safe_x, safe_y))
        else:
            safe_zone = set()

        candidates = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in safe_zone
        ]

        if len(candidates) < self.num_mines:
            if safe_x is not None and safe_y is not None:
                candidates = [
                    (x, y)
                    for y in range(self.height)
                    for x in range(self.width)
                    if (x, y) != (safe_x, safe_y)
                ]
            else:
                candidates = [
                    (x, y)
                    for y in range(self.height)
                    for x in range(self.width)
                ]

        self._mines = set(random.sample(candidates, self.num_mines))
        self._compute_adjacency()
        self._mines_placed = True

        # 지뢰 배치가 확정된 직후, 별도 분석 모듈로 3BV/Ops 정적 분석을 수행한다.
        self._apply_board_analysis(analyze_board(self.get_board_snapshot()))

    def _compute_adjacency(self):
        """모든 칸의 주변 지뢰 수를 미리 계산한다."""
        for (mx, my) in self._mines:
            for nx, ny in self._neighbors(mx, my):
                self._adjacent[ny][nx] += 1

    def _apply_board_analysis(self, analysis: BoardAnalysis):
        """
        분석 모듈의 불변 결과를 기존 엔진 내부 필드 구조에 반영한다.

        _account_reveal()과 get_stats()의 기존 흐름을 유지하기 위해
        _opening_id, _cell_class, _total_3bv, _total_ops 필드는 그대로 둔다.
        """
        self._opening_id = [list(row) for row in analysis.opening_id]
        self._cell_class = [
            [None if cls is None else int(cls) for cls in row]
            for row in analysis.cell_class
        ]
        self._total_3bv = analysis.total_3bv
        self._total_ops = analysis.total_ops

    def _account_reveal(self, x: int, y: int):
        """
        칸 하나가 '실제로 새로 열리는' 순간 호출되어 유효 3BV/Ops를 누적한다.

        규칙:
            - 오프닝 내부 칸(CELL_OPENING)이면 소속 그룹이 처음 열리는
              경우에 한해 유효 3BV +1, 유효 Ops +1.
            - 고립 숫자 칸(CELL_ISOLATED)이 처음 열리면 유효 3BV +1.
            - 테두리 숫자 칸(CELL_BORDER)은 분자에 포함하지 않는다.

        주의:
            반드시 self._revealed[y][x] = True 로 만들기 직전/직후에,
            '이전에 닫혀 있던 칸'에 대해서만 호출되어야 한다.
            (중복 호출 방지는 _opened_groups / _opened_isolated 집합이 담당)
        """
        cls = self._cell_class[y][x]
        if cls == self.CELL_OPENING:
            gid = self._opening_id[y][x]
            if gid not in self._opened_groups:
                self._opened_groups.add(gid)
                self._effective_3bv += 1
                self._effective_ops += 1
        elif cls == self.CELL_ISOLATED:
            if (x, y) not in self._opened_isolated:
                self._opened_isolated.add((x, y))
                self._effective_3bv += 1
        # CELL_BORDER: 직접 클릭이든 연쇄든 분자 기여 없음

    def _reveal_single(self, x: int, y: int):
        """
        칸 하나를 연다. 지뢰면 폭발 집합에 추가하고 LOST로 표시(중단하지 않음).
        안전한 빈칸이면 BFS Flood Fill을 수행한다.
        화음/단일클릭 공통으로 쓰는 저수준 헬퍼.
        """
        if self._revealed[y][x] or self._flagged[y][x]:
            return

        if (x, y) in self._mines:
            self._revealed[y][x] = True
            self._exploded_cells.add((x, y))
            self.status = GameStatus.LOST
            return

        self._flood_fill(x, y)

    def _flood_fill(self, start_x: int, start_y: int):
        """
        큐 기반 BFS로 빈칸(0) 영역을 연속 오픈.
        자동 확장 도중 만나는 깃발은 무시하고 자동으로 연다.
        칸이 실제로 새로 열리는 순간마다 _account_reveal로 유효 점수를 누적한다.
        """
        queue = deque([(start_x, start_y)])
        while queue:
            x, y = queue.popleft()
            if self._revealed[y][x]:
                continue
            self._revealed[y][x] = True
            self._flagged[y][x] = False
            self._account_reveal(x, y)

            if self._adjacent[y][x] == 0:
                for nx, ny in self._neighbors(x, y):
                    if not self._revealed[ny][nx]:
                        queue.append((nx, ny))

    def _count_revealed(self) -> int:
        return sum(row.count(True) for row in self._revealed)

    def _update_status(self):
        """승리 조건 확인 및 승리 시 미발견 지뢰 자동 깃발 처리."""
        if self.status == GameStatus.LOST:
            return
        if self._mines_placed and self._count_revealed() >= self._cells_to_reveal:
            self.status = GameStatus.WON
            self._auto_flag_remaining_mines()

    def _auto_flag_remaining_mines(self):
        """승리 시 깃발 없는 지뢰칸에 자동으로 깃발을 꽂는다."""
        for (mx, my) in self._mines:
            if not self._flagged[my][mx]:
                self._flagged[my][mx] = True

    def _compute_reward(self) -> float:
        """RL용 단순 보상 (단계 확장 시 정교화 예정)."""
        if self.status == GameStatus.WON:
            return 1.0
        if self.status == GameStatus.LOST:
            return -1.0
        return 0.01
