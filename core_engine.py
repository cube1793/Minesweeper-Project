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


class ZiniSolver:
    """
    ZiNi(Zimmerman-Nikolaus) 가상 솔버.

    역할:
        지뢰 위치가 완전히 확정된(UPK; Unfair Prior Knowledge) 보드에 대해,
        보드를 모두 푸는 데 필요한 '최소 클릭 추정치'를 시뮬레이션으로 구한다.
        G.ZiNi(Greedy)와 H.ZiNi(Human) 두 변종을 지원한다.

    아키텍처 원칙 (가상 솔버 안전장치):
        - 이 클래스는 엔진의 정적 분석 결과(지뢰 배치/인접 지뢰 수/오프닝 그룹
          ID)를 '읽기 전용 스냅샷'으로만 참조한다.
        - revealed/flagged 등 모든 가변 상태는 이 인스턴스가 자체적으로 새로
          할당한 2D 배열이며, 실제 게임 엔진의 멤버 변수(_revealed, status 등)를
          절대 건드리지 않는다. (관심사 분리 + 부작용 차단)
        - solve()는 한 번 호출되면 가상 보드를 끝까지 진행시켜 클릭 수를 반환하고
          폐기되는 1회용 객체로 사용한다(상태 누수 방지).

    좌표 규약: 엔진과 동일하게 (x, y), 내부 2D 배열은 [y][x].

    Premium 공식 (명세서 정의):
        Premium(uncovered / 3BV) = (인접한 닫힌 3BV 단위 수)
                                   - (인접한 미깃발 지뢰 수) - 1
        Premium(covered non-3BV) = Premium(uncovered) - 1
        여기서 '인접한 닫힌 3BV 단위 수'는, 대상 셀 주변 8칸을 보아
            * 닫힌 비오프닝 숫자 칸: 각각 1개로 계수
            * 닫힌 오프닝 칸: 같은 오프닝 그룹은 묶어서 1개로 계수
        한 값이다.

    G.ZiNi 절차 (명세서 기반):
        1) Premium이 가장 높은 셀을 선택한다.
        2) 동점이면 top-leftmost(작은 y, 그다음 작은 x) 셀을 택한다(Selection Bias).
        3) 선택 셀의 Premium이 0 이상이고 '열린' 셀이면 → 인접 미깃발 지뢰를
           모두 깃발 꽂고 그 셀을 화음한다.
        4) 선택 셀이 '닫힌' 셀이면 → 먼저 그 셀을 클릭(오픈)한다.
        5) 최고 Premium이 음수면 → top-leftmost 닫힌 안전 칸을 그냥 클릭한다.
        6) 매 수마다 보드를 갱신하고, 모든 안전 칸이 열릴 때까지 반복한다.

    H.ZiNi 차이점:
        - 시뮬레이션 시작 시 모든 오프닝(그룹)을 먼저 한 번씩 클릭해 열어둔 뒤,
          위 Greedy 루프를 동일하게 진행한다.
    """

    def __init__(self, width, height, mines, adjacent, opening_id):
        """
        Args:
            width, height : 보드 크기
            mines         : 지뢰 좌표 집합 (읽기 전용으로만 사용)
            adjacent      : [y][x] 인접 지뢰 수 (읽기 전용)
            opening_id    : [y][x] 오프닝 그룹 ID(비오프닝 -1) (읽기 전용)

        주의:
            전달받은 mines/adjacent/opening_id는 참조만 하고 변경하지 않는다.
            가변 상태(revealed/flagged)는 여기서 독립적으로 새로 만든다.
        """
        self.w = width
        self.h = height
        self.adj = adjacent
        self.opening_id = opening_id

        # 빠른 조회를 위해 지뢰 여부를 2D bool로, 이웃 좌표를 사전 계산한다.
        # (이 둘 모두 이 인스턴스 전용 파생 데이터이며 원본을 오염시키지 않는다.)
        self.is_mine = [
            [(x, y) in mines for x in range(width)] for y in range(height)
        ]
        self.nbrs = {}
        for y in range(height):
            for x in range(width):
                lst = []
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            lst.append((nx, ny))
                self.nbrs[(x, y)] = lst

        # 가상 보드 상태 (엔진과 완전히 분리된 독립 배열)
        self.revealed = [[False] * width for _ in range(height)]
        self.flagged = [[False] * width for _ in range(height)]
        self.clicks = 0
        self._revealed_count = 0
        self.total_safe = width * height - sum(row.count(True) for row in self.is_mine)

    def _flood_open(self, x, y):
        """
        가상 보드에서 한 칸을 연다. 빈칸(0)이면 BFS로 오프닝 전체를 확장한다.
        UPK 솔버이므로 지뢰 칸은 절대 열지 않는다(안전장치).
        """
        if self.revealed[y][x] or self.flagged[y][x] or self.is_mine[y][x]:
            return
        queue = deque([(x, y)])
        while queue:
            cx, cy = queue.popleft()
            if self.revealed[cy][cx] or self.flagged[cy][cx]:
                continue
            self.revealed[cy][cx] = True
            self._revealed_count += 1
            if self.adj[cy][cx] == 0:
                for nx, ny in self.nbrs[(cx, cy)]:
                    if not self.revealed[ny][nx] and not self.is_mine[ny][nx]:
                        queue.append((nx, ny))

    def _premium(self, x, y):
        """대상 셀의 Premium 값을 명세서 공식대로 계산한다."""
        covered_3bv = 0
        unflagged_mines = 0
        seen_groups = None
        for nx, ny in self.nbrs[(x, y)]:
            if self.is_mine[ny][nx]:
                if not self.flagged[ny][nx]:
                    unflagged_mines += 1
                continue
            if self.revealed[ny][nx]:
                continue
            gid = self.opening_id[ny][nx]
            if gid >= 0:
                # 오프닝 칸: 같은 그룹은 한 번만 계수
                if seen_groups is None:
                    seen_groups = set()
                if gid not in seen_groups:
                    seen_groups.add(gid)
                    covered_3bv += 1
            else:
                # 비오프닝 숫자 칸: 각각 1개
                covered_3bv += 1

        premium = covered_3bv - unflagged_mines - 1
        if not self.revealed[y][x]:
            premium -= 1  # covered non-3BV 보정
        return premium

    def _chord(self, x, y):
        """
        인접 미깃발 지뢰를 모두 깃발 꽂은 뒤, 주변 닫힌 안전 칸을 모두 연다.
        (화음 1회는 호출부에서 클릭 1로 계수한다.)
        """
        for nx, ny in self.nbrs[(x, y)]:
            if self.is_mine[ny][nx] and not self.flagged[ny][nx]:
                self.flagged[ny][nx] = True
        for nx, ny in self.nbrs[(x, y)]:
            if not self.revealed[ny][nx] and not self.is_mine[ny][nx]:
                self._flood_open(nx, ny)

    def _first_covered_safe(self):
        """top-leftmost 순서로 첫 번째 '닫힌 안전 칸'을 찾는다(없으면 None)."""
        for y in range(self.h):
            for x in range(self.w):
                if not self.is_mine[y][x] and not self.revealed[y][x]:
                    return (x, y)
        return None

    def solve(self, pre_open_all_openings=False):
        """
        가상 보드를 끝까지 진행시켜 사용한 총 클릭 수를 반환한다.

        Args:
            pre_open_all_openings:
                True면 H.ZiNi(시작 시 모든 오프닝을 먼저 클릭), False면 G.ZiNi.

        Returns:
            int: 보드를 모두 푸는 데 든 가상 클릭 수(= ZiNi 값).
        """
        if self.total_safe == 0:
            return 0

        # H.ZiNi: 모든 오프닝 그룹을 먼저 한 번씩 클릭해 열어둔다.
        if pre_open_all_openings:
            opened = set()
            for y in range(self.h):
                for x in range(self.w):
                    if self.is_mine[y][x]:
                        continue
                    gid = self.opening_id[y][x]
                    if gid >= 0 and gid not in opened:
                        opened.add(gid)
                        self._flood_open(x, y)
                        self.clicks += 1

        # 무한 루프 방지용 안전장치(정상적으로는 도달하지 않음).
        guard = 0
        max_guard = self.w * self.h * 4 + 10

        while self._revealed_count < self.total_safe:
            guard += 1
            if guard > max_guard:
                raise RuntimeError("ZiNi 시뮬레이션이 수렴하지 않았습니다.")

            # 1)~2) 최고 Premium 셀 탐색. 순회 순서가 top-leftmost이고
            # 'p > best_prem'(엄격 비교)이므로 동점 시 먼저 만난 좌상단이 유지된다.
            best = None
            best_prem = None
            for y in range(self.h):
                row_mine = self.is_mine[y]
                row_rev = self.revealed[y]
                row_adj = self.adj[y]
                for x in range(self.w):
                    if row_mine[x]:
                        continue
                    # 이미 열린 빈칸(0)은 더 열 것이 없어 후보에서 제외
                    if row_rev[x] and row_adj[x] == 0:
                        continue
                    p = self._premium(x, y)
                    if best_prem is None or p > best_prem:
                        best_prem = p
                        best = (x, y)

            # 5) 최고 Premium이 음수거나 후보가 없으면 top-leftmost 클릭
            if best is None or best_prem < 0:
                fallback = self._first_covered_safe()
                if fallback is None:
                    break
                self._flood_open(*fallback)
                self.clicks += 1
                continue

            bx, by = best
            if not self.revealed[by][bx]:
                # 4) 닫힌 셀 → 먼저 클릭
                self._flood_open(bx, by)
            else:
                # 3) 열린 셀 & Premium >= 0 → 깃발 + 화음
                self._chord(bx, by)
            self.clicks += 1

        return self.clicks


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

        # --- ZiNi 추정치 (지뢰 배치 직후 1회 계산되는 정적 값) ---
        # 가상 솔버(ZiniSolver)가 UPK 보드를 끝까지 풀어 산출한 최소 클릭 추정치.
        # 지뢰 미배치(첫 액션 전) 상태에서는 None으로 두고, get_stats에서 마스킹.
        self._gzini = None            # G.ZiNi 값
        self._hzini = None            # H.ZiNi 값

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

        # ZiNi 추정치 초기화 (다음 지뢰 배치 시점에 다시 계산됨)
        self._gzini = None
        self._hzini = None

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
            - "efficiency"   : Efficiency 항목 (정수 백분율 "NN%" 또는 "-")
            - "ioe"          : IOE 항목 (소수 4자리 또는 "-")
            - "thrp"         : ThrP 항목 (소수 4자리 또는 "-")
            - "corr"         : Corr 항목 (소수 4자리 또는 "-")
            - "zini"         : G.ZiNi 추정치 (정수 또는 "-")
            - "hzini"        : H.ZiNi 추정치 (정수 또는 "-")
            - "zne"          : ZiNi Efficiency = G.ZiNi/Clicks (소수 4자리 또는 "-")
            - "hzne"         : H.ZiNi Efficiency = H.ZiNi/Clicks (소수 4자리 또는 "-")
            - "znt"          : ZiNi Throughput = G.ZiNi/Active (소수 4자리 또는 "-")
            - "rqp"          : RQP = (Time+1)/(3BV/s) (소수 4자리 또는 "-")

        효율 지표(efficiency/ioe/thrp/corr)의 분자/분모 정의:
            - 분자 3BV   : 플레이어가 실제 달성한 작업량인 유효 3BV
              (_effective_3bv)를 사용한다. WON에서는 총 3BV와 같고,
              LOST에서는 그때까지 드러낸 만큼만 반영된다(3BV/s와 동일 기준).
            - Clicks      : 총 클릭(active + wasted).
            - Active Clicks: 활성 클릭(active)만.
            모든 지표는 분모가 0일 때 ZeroDivision 없이 0 기반 기본값을
            반환하도록 방어한다.

        ZiNi 파생 지표(zne/hzne/znt)의 분자/분모 정의:
            - 분자        : 보드 전체의 정적 추정치인 총 ZiNi(_gzini/_hzini).
              (효율 지표와 달리 보드 난이도 대비 클릭 효율을 보는 값이므로
               '유효'가 아닌 보드 전체 ZiNi를 분자로 둔다.)
            - 분모        : zne/hzne는 총 클릭, znt는 활성 클릭.
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
                "efficiency": "-",
                "ioe": "-",
                "thrp": "-",
                "corr": "-",
                "zini": "-",
                "hzini": "-",
                "zne": "-",
                "hzne": "-",
                "znt": "-",
                "rqp": "-",
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

        # 효율 지표 4종(efficiency/ioe/thrp/corr) 계산.
        # 분자=유효 3BV, 분모=총 클릭 또는 활성 클릭. (ZeroDivision 방어)
        eff_str, ioe_str, thrp_str, corr_str = self._compute_efficiency_metrics()

        # RQP = (Time + 1) / (3BV/s). 3BV/s가 0이면 "0.0000"으로 방어.
        rqp_str = self._compute_rqp(elapsed, bbbv_per_sec)

        # ZiNi 추정치 및 파생 지표(zne/hzne/znt) 계산.
        zini_str = str(self._gzini) if self._gzini is not None else "0"
        hzini_str = str(self._hzini) if self._hzini is not None else "0"
        zne_str, hzne_str, znt_str = self._compute_zini_metrics()

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
            "efficiency": eff_str,
            "ioe": ioe_str,
            "thrp": thrp_str,
            "corr": corr_str,
            "zini": zini_str,
            "hzini": hzini_str,
            "zne": zne_str,
            "hzne": hzne_str,
            "znt": znt_str,
            "rqp": rqp_str,
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
    # 효율 지표 계산 헬퍼
    # ------------------------------------------------------------------
    def _compute_efficiency_metrics(self):
        """
        종료(WON/LOST) 상태에서 효율 지표 4종을 계산해 문자열 튜플로 반환한다.

        Returns:
            (efficiency_str, ioe_str, thrp_str, corr_str)

        정의 (분자 3BV = 유효 3BV = self._effective_3bv):
            - efficiency = 3BV / Clicks * 100   → 정수 백분율 "NN%"
            - ioe        = 3BV / Clicks         → 소수 4자리
            - thrp       = 3BV / Active Clicks  → 소수 4자리
            - corr       = Active Clicks / Clicks → 소수 4자리

        분모(Clicks 또는 Active Clicks)가 0인 극초반/특수 상황에서는
        ZeroDivisionError 없이 0 기반 기본 포맷("0%" / "0.0000")을 반환한다.
        """
        bbbv = self._effective_3bv
        total_clicks = self._active_clicks["total"] + self._wasted_clicks["total"]
        active_clicks = self._active_clicks["total"]

        # efficiency = 3BV / Clicks * 100 (정수 백분율)
        if total_clicks > 0:
            efficiency_str = f"{round(bbbv / total_clicks * 100)}%"
        else:
            efficiency_str = "0%"

        # ioe = 3BV / Clicks (소수 4자리)
        if total_clicks > 0:
            ioe_str = f"{bbbv / total_clicks:.4f}"
        else:
            ioe_str = "0.0000"

        # thrp = 3BV / Active Clicks (소수 4자리)
        if active_clicks > 0:
            thrp_str = f"{bbbv / active_clicks:.4f}"
        else:
            thrp_str = "0.0000"

        # corr = Active Clicks / Clicks (소수 4자리)
        if total_clicks > 0:
            corr_str = f"{active_clicks / total_clicks:.4f}"
        else:
            corr_str = "0.0000"

        return efficiency_str, ioe_str, thrp_str, corr_str

    def _compute_rqp(self, elapsed: float, bbbv_per_sec: float) -> str:
        """
        RQP(Rapport Qualité Prix) = (Time + 1) / (3BV/s) 를 계산해
        소수 4자리 문자열로 반환한다.

        Args:
            elapsed      : 최종 경과 시간(초).
            bbbv_per_sec : 최종 3BV/s 값(이미 ZeroDivision 방어된 값).

        예외 처리:
            3BV/s가 0이면(극초반/첫 수 폭사 등) 나눗셈이 불가능하므로
            ZeroDivisionError 없이 "0.0000"을 반환한다.
        """
        if bbbv_per_sec <= 0.0:
            return "0.0000"
        try:
            rqp = (elapsed + 1.0) / bbbv_per_sec
        except ZeroDivisionError:
            return "0.0000"
        return f"{rqp:.4f}"

    def _compute_zini_metrics(self):
        """
        ZiNi 파생 지표 3종(zne/hzne/znt)을 계산해 문자열 튜플로 반환한다.

        Returns:
            (zne_str, hzne_str, znt_str)

        정의:
            - zne  = G.ZiNi / Clicks         → 소수 4자리
            - hzne = H.ZiNi / Clicks         → 소수 4자리
            - znt  = G.ZiNi / Active Clicks  → 소수 4자리 (Wasted 제외)

        분모(Clicks 또는 Active Clicks)가 0이거나 ZiNi 값이 아직 없으면
        ZeroDivision 없이 "0.0000"을 반환한다.
        """
        total_clicks = self._active_clicks["total"] + self._wasted_clicks["total"]
        active_clicks = self._active_clicks["total"]
        gz = self._gzini if self._gzini is not None else 0
        hz = self._hzini if self._hzini is not None else 0

        # zne = G.ZiNi / Clicks
        if total_clicks > 0:
            zne_str = f"{gz / total_clicks:.4f}"
        else:
            zne_str = "0.0000"

        # hzne = H.ZiNi / Clicks
        if total_clicks > 0:
            hzne_str = f"{hz / total_clicks:.4f}"
        else:
            hzne_str = "0.0000"

        # znt = G.ZiNi / Active Clicks
        if active_clicks > 0:
            znt_str = f"{gz / active_clicks:.4f}"
        else:
            znt_str = "0.0000"

        return zne_str, hzne_str, znt_str

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

        # 지뢰 배치가 확정된 직후, 3BV/Ops 정적 분석을 수행한다.
        self._analyze_board()

    def _compute_adjacency(self):
        """모든 칸의 주변 지뢰 수를 미리 계산한다."""
        for (mx, my) in self._mines:
            for nx, ny in self._neighbors(mx, my):
                self._adjacent[ny][nx] += 1

    def _analyze_board(self):
        """
        지뢰 배치 직후 보드 전체를 분석하여 안전 칸을 분류하고,
        총 3BV/Ops 분모를 계산한다.

        절차:
            1) 안전한 빈칸(adjacent==0)들을 BFS로 묶어 '오프닝 그룹'을 식별하고
               각 칸에 그룹 ID(_opening_id)를 부여한다. (대각 인접 포함)
            2) 안전한 숫자 칸(adjacent>0)을 순회하며, 주변 8칸 중 하나라도
               오프닝 내부 칸이면 BORDER, 아니면 ISOLATED 로 분류한다.
            3) 총 Ops = 오프닝 그룹 수.
               총 3BV = 오프닝 그룹 수 + 고립 숫자 칸 수.
        """
        # 초기화 (reset에서 이미 비워지지만 재배치 안전을 위해 다시 정리)
        self._opening_id = [[-1] * self.width for _ in range(self.height)]
        self._cell_class = [[None] * self.width for _ in range(self.height)]

        # 1) 오프닝 그룹 식별 (빈칸 BFS)
        group_id = 0
        for y in range(self.height):
            for x in range(self.width):
                if (x, y) in self._mines:
                    continue
                if self._adjacent[y][x] != 0:
                    continue
                if self._opening_id[y][x] != -1:
                    continue
                # 새 오프닝 그룹 발견 → BFS 확장
                self._flood_mark_opening(x, y, group_id)
                group_id += 1

        self._total_ops = group_id

        # 2) 숫자 칸 분류 (BORDER / ISOLATED)
        isolated_count = 0
        for y in range(self.height):
            for x in range(self.width):
                if (x, y) in self._mines:
                    self._cell_class[y][x] = None
                    continue
                if self._adjacent[y][x] == 0:
                    self._cell_class[y][x] = self.CELL_OPENING
                    continue
                # 숫자 칸: 오프닝 내부 칸과 인접하면 테두리, 아니면 고립
                touches_opening = any(
                    self._adjacent[ny][nx] == 0 and (nx, ny) not in self._mines
                    for nx, ny in self._neighbors(x, y)
                )
                if touches_opening:
                    self._cell_class[y][x] = self.CELL_BORDER
                else:
                    self._cell_class[y][x] = self.CELL_ISOLATED
                    isolated_count += 1

        # 3) 총 3BV = 오프닝 그룹 수 + 고립 숫자 칸 수
        self._total_3bv = self._total_ops + isolated_count

        # 4) ZiNi 추정치 계산.
        #    완전 정보(UPK)가 확보된 지금 시점에 G.ZiNi / H.ZiNi를 각각
        #    독립된 가상 솔버로 1회 계산해 정적 멤버에 저장한다.
        self._compute_zini()

    def _compute_zini(self):
        """
        G.ZiNi / H.ZiNi를 각각 독립 ZiniSolver 인스턴스로 시뮬레이션해
        self._gzini / self._hzini 에 저장한다.

        가상 솔버 안전장치:
            - 두 솔버는 엔진의 정적 데이터(_mines/_adjacent/_opening_id)를
              읽기 전용으로만 참조하고, 각자 독립된 가상 보드에서 동작한다.
            - 따라서 실제 게임의 _revealed/_flagged/status 등은 전혀 변하지 않는다.
            - 솔버 인스턴스는 계산 후 지역 변수로 폐기된다(상태 누수 방지).
        """
        g_solver = ZiniSolver(
            self.width, self.height, self._mines,
            self._adjacent, self._opening_id,
        )
        self._gzini = g_solver.solve(pre_open_all_openings=False)

        h_solver = ZiniSolver(
            self.width, self.height, self._mines,
            self._adjacent, self._opening_id,
        )
        self._hzini = h_solver.solve(pre_open_all_openings=True)

    def _flood_mark_opening(self, start_x: int, start_y: int, group_id: int):
        """빈칸(adjacent==0)을 BFS로 묶어 group_id를 부여한다(대각 포함)."""
        queue = deque([(start_x, start_y)])
        self._opening_id[start_y][start_x] = group_id
        while queue:
            x, y = queue.popleft()
            for nx, ny in self._neighbors(x, y):
                if (nx, ny) in self._mines:
                    continue
                if self._adjacent[ny][nx] != 0:
                    continue
                if self._opening_id[ny][nx] != -1:
                    continue
                self._opening_id[ny][nx] = group_id
                queue.append((nx, ny))

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