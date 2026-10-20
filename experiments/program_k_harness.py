"""Program-K Slice-7 preregistration and qualification foundation.

The A-E4 values below are source-pinned public evidence, independent of K,
Stage 2 and both oracles.  Importing this module never computes a solver result.
Local A/C world counts describe independent public audits; they do not assert
that K reached its exact layer.  This module does not run P-8 on import.
"""

from dataclasses import dataclass


Coordinate = tuple[int, int]
Observation = tuple[tuple[int, ...], ...]
H, F = -2, -3
MANIFEST_ID = "PROGRAM_K_A_E4_SLICE7_V1"
MANIFEST_DERIVATION = (
    "Literal preregistration: direct clue algebra; independent stdlib-only "
    "coordinate assignment enumeration with itertools.combinations; closed-form "
    "binomial coefficients for the arithmetic fixture. No K, Stage-2, Oracle-A "
    "or Oracle-B import was used to derive these expected values."
)


def _manifest_need(condition, detail):
    if not condition:
        raise ValueError(detail)


def _manifest_cells(cells):
    _manifest_need(type(cells) is tuple and all(
        type(c) is tuple and len(c) == 2 and all(type(v) is int for v in c)
        and 0 <= c[0] < 30 and 0 <= c[1] < 16 for c in cells),
        "Manifest coordinates must be immutable (x,y) integer tuples.")
    _manifest_need(len(set(cells)) == len(cells), "Duplicate manifest coordinate.")


@dataclass(frozen=True)
class PublicPremise:
    """An earlier public local proof declaration, never a supplied answer."""

    observation: Observation
    clue: Coordinate
    target: Coordinate
    retained_mines: tuple[Coordinate, ...] = ()
    origin: str = "PUBLIC_LOCAL_ALL_MINES"

    def __post_init__(self):
        _manifest_cells((self.clue,))
        _manifest_cells((self.target,))
        _manifest_cells(self.retained_mines)
        _manifest_need(type(self.observation) is tuple and all(
            type(row) is tuple and all(type(v) is int for v in row)
            for row in self.observation), "Public premise must contain immutable public rows.")
        _manifest_need(self.origin == "PUBLIC_LOCAL_ALL_MINES", "Unsupported premise origin.")


@dataclass(frozen=True)
class FixtureExpectation:
    """Complete independent world evidence for one explicitly named M phase."""

    phase: str
    M: tuple[Coordinate, ...]
    Z: int
    mine_worlds: tuple[tuple[Coordinate, int], ...]
    frontier: tuple[Coordinate, ...]
    floating: tuple[Coordinate, ...]
    G0: tuple[Coordinate, ...]
    G1: tuple[Coordinate, ...]
    oracle_a_status: str = "ORACLE_A_EVALUATED"

    def __post_init__(self):
        _manifest_need(self.phase in ("A", "C", "D", "E"), "Unsupported fixture phase.")
        _manifest_need(type(self.Z) is int and self.Z >= 0, "Exact Z must be a true integer.")
        _manifest_need(type(self.mine_worlds) is tuple and all(
            type(item) is tuple and len(item) == 2 and type(item[1]) is int
            and 0 <= item[1] <= self.Z for item in self.mine_worlds),
            "All manifest numerators must be immutable exact true integers.")
        for cells in (self.M, self.frontier, self.floating, self.G0, self.G1,
                      tuple(c for c, _ in self.mine_worlds)):
            _manifest_cells(cells)
        _manifest_need(not set(self.frontier) & set(self.floating)
                       and set(self.frontier) | set(self.floating)
                       == {c for c, _ in self.mine_worlds}, "Incomplete manifest partition.")
        _manifest_need(self.oracle_a_status in (
            "ORACLE_A_EVALUATED", "ORACLE_A_NOT_EVALUATED"), "Missing Oracle-A coverage.")


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    observation: Observation
    width: int
    height: int
    num_mines: int
    intended_check: str
    expectations: tuple[FixtureExpectation, ...]
    local_mines: tuple[Coordinate, ...] = ()
    S_first: tuple[Coordinate, ...] = ()
    S_second_all: tuple[Coordinate, ...] = ()
    S_new: tuple[Coordinate, ...] = ()
    S_current: tuple[Coordinate, ...] = ()
    continuation: str | None = "EXACT_GUESS"
    error_code: str | None = None
    phase_e_status: str = "REACHED_NO_CHANGE"
    pre_acquisition_M: tuple[Coordinate, ...] = ()
    public_prefix: tuple[Observation, ...] = ()
    provenance: tuple[PublicPremise, ...] = ()
    transform: str = "IDENTITY"
    screen_order: tuple[Coordinate, ...] = ()
    tie_target: Coordinate | None = None
    cursor: Coordinate | None = None
    expected_category: str | None = None
    expected_target: Coordinate | None = None
    model_c_lookup: tuple[int, int, int] | None = None
    expected_latency_us: int | None = None
    expected_route: tuple[tuple[str, Coordinate], ...] | None = None
    rationale: str = ""

    def __post_init__(self):
        _manifest_need(type(self.fixture_id) is str and bool(self.fixture_id), "Missing fixture ID.")
        _manifest_need(all(type(v) is int for v in (self.width, self.height, self.num_mines))
                       and 1 <= self.width <= 30 and 1 <= self.height <= 16
                       and 0 <= self.num_mines <= self.width * self.height,
                       "Fixture dimensions/mine total must be supported exact integers.")
        for observation in (self.observation,) + self.public_prefix:
            _manifest_need(type(observation) is tuple and len(observation) == self.height
                           and all(type(row) is tuple and len(row) == self.width for row in observation)
                           and all(type(v) is int and (v in (H, F) or 0 <= v <= 8)
                                   for row in observation for v in row), "Invalid immutable public fixture.")
        _manifest_need(type(self.expectations) is tuple and bool(self.expectations)
                       and all(type(e) is FixtureExpectation for e in self.expectations)
                       and len({e.phase for e in self.expectations}) == len(self.expectations),
                       "Fixture phases must be present, immutable and unique.")
        for cells in (self.local_mines, self.S_first, self.S_second_all, self.S_new,
                      self.S_current, self.pre_acquisition_M, self.screen_order):
            _manifest_cells(cells)
        _manifest_need(type(self.public_prefix) is tuple and type(self.provenance) is tuple
                       and all(type(p) is PublicPremise for p in self.provenance),
                       "Public provenance must be immutable declarations.")
        _manifest_need(type(self.rationale) is str and bool(self.rationale), "Fixture needs rationale.")


def _phases(names, M, Z, counts, frontier, floating, G0=(), G1=(),
            oracle_a_status="ORACLE_A_EVALUATED"):
    """Copy literal counts into named phase records; never derive expected values."""
    return tuple(FixtureExpectation(name, M, Z, counts, frontier, floating, G0, G1,
                                    oracle_a_status) for name in names)


# Each literal count covers EVERY unresolved coordinate at the named phase.
_FRONTIER_COUNTS = (((0, 0), 1), ((2, 0), 1))
_FRONTIER = ((0, 0), (2, 0))
_HISTORICAL_A = (((1, 0), 1), ((3, 0), 0))
_HISTORICAL_C = (((3, 0), 0),)
_BASIS_A = (((1, 0), 2), ((2, 0), 1), ((3, 0), 1))
_BASIS_DE = (((2, 0), 1), ((3, 0), 1))
_G0_COUNTS = (((0, 0), 1), ((2, 0), 1), ((3, 0), 0), ((4, 0), 0))
_G1_COUNTS = (((0, 0), 1), ((2, 0), 1), ((3, 0), 2), ((4, 0), 2))
_BOTH_COUNTS = (((0, 0), 1), ((3, 0), 1), ((0, 1), 1),
                ((1, 1), 0), ((2, 1), 0), ((3, 1), 1))
_BOTH_FRONTIER = ((0, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1))
_BOTH_MINES = ((0, 0), (3, 0), (0, 1), (3, 1))
_BOTH_SAFE = ((1, 1), (2, 1))
_TIE_COUNTS = (((1, 0), 2), ((2, 0), 3), ((0, 1), 2), ((1, 1), 2), ((2, 1), 3))
_TIE_FRONTIER = ((1, 0), (0, 1), (1, 1))
_TIE_FLOATING = ((2, 0), (2, 1))
_BASIS_PREMISE = PublicPremise(((1, H, H, H),), (0, 0), (1, 0))
_HISTORICAL_PREMISE = PublicPremise(((1, H, 1, H),), (0, 0), (1, 0))

# C(60,27)=88004802264174740; C(59,26)=39602161018878633.
# Both integers change under binary64 conversion. The grid is supported 30x2;
# 60 unfixed variables explicitly exceed Oracle A's inclusive <=16 envelope.
_EXTREME_OBSERVATION = (
    (H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H),
    (H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H,H),
)
_EXTREME_CELLS = (
    (0,0),(1,0),(2,0),(3,0),(4,0),(5,0),(6,0),(7,0),(8,0),(9,0),
    (10,0),(11,0),(12,0),(13,0),(14,0),(15,0),(16,0),(17,0),(18,0),(19,0),
    (20,0),(21,0),(22,0),(23,0),(24,0),(25,0),(26,0),(27,0),(28,0),(29,0),
    (0,1),(1,1),(2,1),(3,1),(4,1),(5,1),(6,1),(7,1),(8,1),(9,1),
    (10,1),(11,1),(12,1),(13,1),(14,1),(15,1),(16,1),(17,1),(18,1),(19,1),
    (20,1),(21,1),(22,1),(23,1),(24,1),(25,1),(26,1),(27,1),(28,1),(29,1),
)
_EXTREME_COUNTS = (
    ((0,0),39602161018878633),((1,0),39602161018878633),((2,0),39602161018878633),
    ((3,0),39602161018878633),((4,0),39602161018878633),((5,0),39602161018878633),
    ((6,0),39602161018878633),((7,0),39602161018878633),((8,0),39602161018878633),
    ((9,0),39602161018878633),((10,0),39602161018878633),((11,0),39602161018878633),
    ((12,0),39602161018878633),((13,0),39602161018878633),((14,0),39602161018878633),
    ((15,0),39602161018878633),((16,0),39602161018878633),((17,0),39602161018878633),
    ((18,0),39602161018878633),((19,0),39602161018878633),((20,0),39602161018878633),
    ((21,0),39602161018878633),((22,0),39602161018878633),((23,0),39602161018878633),
    ((24,0),39602161018878633),((25,0),39602161018878633),((26,0),39602161018878633),
    ((27,0),39602161018878633),((28,0),39602161018878633),((29,0),39602161018878633),
    ((0,1),39602161018878633),((1,1),39602161018878633),((2,1),39602161018878633),
    ((3,1),39602161018878633),((4,1),39602161018878633),((5,1),39602161018878633),
    ((6,1),39602161018878633),((7,1),39602161018878633),((8,1),39602161018878633),
    ((9,1),39602161018878633),((10,1),39602161018878633),((11,1),39602161018878633),
    ((12,1),39602161018878633),((13,1),39602161018878633),((14,1),39602161018878633),
    ((15,1),39602161018878633),((16,1),39602161018878633),((17,1),39602161018878633),
    ((18,1),39602161018878633),((19,1),39602161018878633),((20,1),39602161018878633),
    ((21,1),39602161018878633),((22,1),39602161018878633),((23,1),39602161018878633),
    ((24,1),39602161018878633),((25,1),39602161018878633),((26,1),39602161018878633),
    ((27,1),39602161018878633),((28,1),39602161018878633),((29,1),39602161018878633),
)

MANIFEST = (
    Fixture("no-new-m", ((H,1,H),), 3,1,1, "A/B/C no direct facts; exact tie",
            _phases(("A","D","E"), (), 2, _FRONTIER_COUNTS, _FRONTIER, ()),
            tie_target=(0,0), rationale="No direct equality/zero rule applies; two public worlds."),
    Fixture("historical-normalized-safe", ((1,H,1,H),), 4,1,1,
            "A/B/C hidden logical mine unlocks direct safe OPEN",
            _phases(("A",), (), 1, _HISTORICAL_A, ((1,0),(3,0)), (), ((3,0),), ((1,0),))
            + _phases(("C",), ((1,0),), 1, _HISTORICAL_C, ((3,0),), (), ((3,0),)),
            local_mines=((1,0),), S_second_all=((3,0),), S_new=((3,0),), S_current=((3,0),),
            continuation="LOCAL_SAFE", phase_e_status="NOT_REACHED", cursor=(0,0),
            expected_category="DIRECT_SAFE_OPEN", expected_target=(3,0),
            model_c_lookup=(3,0,227896), expected_latency_us=227896,
            expected_route=(("OPEN",(3,0)),),
            rationale="Clue x0 proves x1; clue x2 normalizes to zero without materializing x1."),
    Fixture("multiple-local-mines", ((H,2,H,H),), 4,1,2, "One clue acquires both mines simultaneously",
            _phases(("A",), (), 1, (((0,0),1),((2,0),1),((3,0),0)),
                    ((0,0),(2,0)), ((3,0),), ((3,0),), ((0,0),(2,0)))
            + _phases(("D","E"), ((0,0),(2,0)), 1, (((3,0),0),), (), ((3,0),), ((3,0),)),
            local_mines=((0,0),(2,0)), continuation="EXACT_SAFE",
            rationale="The first pass uses one pre-acquisition snapshot; floating safe needs exact global budget."),
    Fixture("simultaneous-local-acquisition", ((1,H,1,H,H,1,H,1),), 8,1,2,
            "Complete simultaneous first pass; both normalized safes",
            _phases(("A",), (), 1, (((1,0),1),((3,0),0),((4,0),0),((6,0),1)),
                    ((1,0),(3,0),(4,0),(6,0)), (), ((3,0),(4,0)), ((1,0),(6,0)))
            + _phases(("C",), ((1,0),(6,0)), 1, (((3,0),0),((4,0),0)),
                      ((3,0),(4,0)), (), ((3,0),(4,0))),
            local_mines=((1,0),(6,0)), S_second_all=((3,0),(4,0)),
            S_new=((3,0),(4,0)), S_current=((3,0),(4,0)),
            continuation="LOCAL_SAFE", phase_e_status="NOT_REACHED",
            rationale="Separated end clues prove x1 and x6 together; neither proof depends on its batch peer."),
    Fixture("safe-stays-unresolved", ((0,H,1,H),), 4,1,1, "No safe substitution/stronger inference",
            _phases(("A","C"), (), 1, (((1,0),0),((3,0),1)),
                    ((1,0),(3,0)), (), ((1,0),), ((3,0),)),
            S_first=((1,0),), S_second_all=((1,0),), S_current=((1,0),),
            continuation="LOCAL_SAFE", phase_e_status="NOT_REACHED",
            rationale="x1 is locally safe but remains unresolved; x3 is not a local acquisition or reached G1."),
    Fixture("safe-mine-coexistence", ((0,H,H,3),(H,H,H,H)), 4,2,3,
            "First-pass safe and mine facts coexist",
            _phases(("A",), (), 1, (((1,0),0),((2,0),1),((0,1),0),((1,1),0),((2,1),1),((3,1),1)),
                    ((1,0),(2,0),(0,1),(1,1),(2,1),(3,1)), (),
                    ((1,0),(0,1),(1,1)), ((2,0),(2,1),(3,1)))
            + _phases(("C",), ((2,0),(2,1),(3,1)), 1,
                      (((1,0),0),((0,1),0),((1,1),0)), ((1,0),(0,1),(1,1)), (),
                      ((1,0),(0,1),(1,1))),
            local_mines=((2,0),(2,1),(3,1)), S_first=((1,0),(0,1),(1,1)),
            S_second_all=((1,0),(0,1),(1,1)), S_current=((1,0),(0,1),(1,1)),
            continuation="LOCAL_SAFE", phase_e_status="NOT_REACHED",
            rationale="Disjoint zero and all-mines neighborhoods retain the original safe pool."),
    Fixture("zero-residual", ((0,H),), 2,1,0, "Direct zero residual",
            _phases(("A","C"), (), 1, (((1,0),0),), ((1,0),), (), ((1,0),)),
            S_first=((1,0),), S_second_all=((1,0),), S_current=((1,0),),
            continuation="LOCAL_SAFE", phase_e_status="NOT_REACHED",
            rationale="The unique zero-mine assignment is positive-world safe evidence."),
    Fixture("public-fixed-mine-basis", ((1,H,H,H),), 4,1,2,
            "Publicly derived local mine; exact floating remainder",
            _phases(("A",), (), 2, _BASIS_A, ((1,0),), ((2,0),(3,0)), (), ((1,0),))
            + _phases(("D","E"), ((1,0),), 2, _BASIS_DE, (), ((2,0),(3,0))),
            local_mines=((1,0),), tie_target=(2,0),
            rationale="Raw clue x0 proves x1 before removal; remaining budget one is shared by x2/x3."),
    Fixture("logical-fixed-mine", ((1,H,H,H),), 4,1,2, "Retained publicly proven M",
            _phases(("A","D","E"), ((1,0),), 2, _BASIS_DE, (), ((2,0),(3,0))),
            pre_acquisition_M=((1,0),), public_prefix=(((1,H,H,H),),),
            provenance=(_BASIS_PREMISE,), tie_target=(2,0),
            rationale="Replay the explicit earlier public local proof; no supplied unproved M."),
    Fixture("physical-logical-overlap", ((1,F,H,H),), 4,1,2,
            "P intersect M counts once; materialized exact reference",
            _phases(("A","D","E"), ((1,0),), 2, _BASIS_DE, (), ((2,0),(3,0))),
            pre_acquisition_M=((1,0),), public_prefix=(((1,H,H,H),),),
            provenance=(_BASIS_PREMISE,), tie_target=(2,0),
            rationale="Public-prefix proof supports the actual FLAG and retained M; union removes one mine."),
    Fixture("local-physical-logical-overlap", ((1,F,1,H),), 4,1,1,
            "Overlap preserves normalized local safety",
            _phases(("A","C"), ((1,0),), 1, _HISTORICAL_C, ((3,0),), (), ((3,0),)),
            S_first=((3,0),), S_second_all=((3,0),), S_current=((3,0),),
            continuation="LOCAL_SAFE", phase_e_status="NOT_REACHED",
            pre_acquisition_M=((1,0),), public_prefix=(((1,H,1,H),),),
            provenance=(_HISTORICAL_PREMISE,),
            rationale="Same supported identity contributes once to each clue and once to the budget."),
    Fixture("frontier-only", ((H,1,H),), 3,1,1, "Exact frontier-only counts",
            _phases(("A","D","E"), (), 2, _FRONTIER_COUNTS, _FRONTIER, ()),
            tie_target=(0,0), rationale="One 1-of-2 component; no floating weights."),
    Fixture("floating-only", ((H,H),), 2,1,1, "Exact floating-only counts",
            _phases(("A","D","E"), (), 2, (((0,0),1),((1,0),1)), (), ((0,0),(1,0))),
            tie_target=(0,0), rationale="C(2,1)=2 complete worlds; every floating numerator is one."),
    Fixture("frontier-floating", ((H,1,H,1,H,H,H),), 7,1,2,
            "Variable-total frontier with floating combinatorial weights",
            _phases(("A","D","E"), (), 3,
                    (((0,0),1),((2,0),2),((4,0),1),((5,0),1),((6,0),1)),
                    ((0,0),(2,0),(4,0)), ((5,0),(6,0))), tie_target=(0,0),
            rationale="a+b=1,b+c=1 gives total 1 or 2; weights C(2,1)+C(2,0)=3."),
    Fixture("multiple-components-floating", ((H,1,H,1,H,H,H,H,H,1,H,1,H),), 13,1,4,
            "Two variable-total components and all floating marginals",
            _phases(("A","D","E"), (), 10,
                    (((0,0),4),((2,0),6),((4,0),4),((5,0),4),((6,0),4),
                     ((7,0),4),((8,0),4),((10,0),6),((12,0),4)),
                    ((0,0),(2,0),(4,0),(8,0),(10,0),(12,0)), ((5,0),(6,0),(7,0))),
            tie_target=(0,0),
            rationale="Components {0,2,4}/{8,10,12} each have one total-1 and total-2 assignment; "
                      "Z=C(3,2)+2*C(3,1)+C(3,0)=10; outer/floating numerators 4, middle numerators 6."),
    Fixture("g0-only", ((H,1,H,H,H),), 5,1,1, "Global zero without new G1",
            _phases(("A","D","E"), (), 2, _G0_COUNTS, _FRONTIER, ((3,0),(4,0)), ((3,0),(4,0))),
            continuation="EXACT_SAFE", rationale="Frontier consumes the one mine; both floating cells are safe."),
    Fixture("g1-only", ((H,1,H,H,H),), 5,1,3, "Global ones followed by exact guess",
            _phases(("A","D"), (), 2, _G1_COUNTS, _FRONTIER, ((3,0),(4,0)), (), ((3,0),(4,0)))
            + _phases(("E",), ((3,0),(4,0)), 2, _FRONTIER_COUNTS, _FRONTIER, ()),
            phase_e_status="REACHED_CHANGED", tie_target=(0,0),
            rationale="Floating pair must be mines; restriction preserves the two frontier worlds."),
    Fixture("simultaneous-g1-g0", ((H,2,2,H),(H,H,H,H)), 4,2,4,
            "Simultaneous exact G1/G0 with no direct local fact",
            _phases(("A","D"), (), 1, _BOTH_COUNTS, _BOTH_FRONTIER, (), _BOTH_SAFE, _BOTH_MINES)
            + _phases(("E",), _BOTH_MINES, 1, (((1,1),0),((2,1),0)), _BOTH_SAFE, (), _BOTH_SAFE),
            continuation="EXACT_SAFE", phase_e_status="REACHED_CHANGED",
            rationale="The shared inner variables must be zero under total four; all four outer cells are mines."),
    Fixture("g1-restriction", ((H,1,H,H,H),), 5,1,3, "World-preserving E restriction; no second enumeration",
            _phases(("A","D"), (), 2, _G1_COUNTS, _FRONTIER, ((3,0),(4,0)), (), ((3,0),(4,0)))
            + _phases(("E",), ((3,0),(4,0)), 2, _FRONTIER_COUNTS, _FRONTIER, ()),
            phase_e_status="REACHED_CHANGED", tie_target=(0,0),
            rationale="Dedicated restriction obligation retains unreduced Z=2 and both surviving numerators=1."),
    Fixture("empty-g1", ((H,1,H),), 3,1,1, "Deterministic E REACHED_NO_CHANGE",
            _phases(("A","D","E"), (), 2, _FRONTIER_COUNTS, _FRONTIER, ()),
            tie_target=(0,0), rationale="D was reached; empty G1 cannot make E absent."),
    Fixture("exact-equal-risk-tie", ((1,H,H),(H,H,H)), 3,2,2, "Stored xy / reading-order yx tie",
            _phases(("A","D","E"), (), 6, _TIE_COUNTS, _TIE_FRONTIER, _TIE_FLOATING),
            screen_order=((1,0),(2,0),(0,1),(1,1),(2,1)), tie_target=(1,0),
            rationale="Complete minimum-risk set is {(1,0),(0,1),(1,1)}; yx selects (1,0)."),
    Fixture("empty-u-entry", ((0,),), 1,1,0, "PLAYING with empty U at decision entry",
            _phases(("A",), (), 1, (), (), ()), continuation=None,
            error_code="EMPTY_U_PLAYING", phase_e_status="NOT_REACHED",
            rationale="Synthetic inconsistent PLAYING marker; never synthesize terminal WIN."),
    Fixture("empty-u-local", ((1,H),), 2,1,1, "Local acquisition exhausts U while PLAYING",
            _phases(("A",), (), 1, (((1,0),1),), ((1,0),), (), (), ((1,0),)),
            local_mines=((1,0),), continuation=None, error_code="EMPTY_U_PLAYING",
            phase_e_status="NOT_REACHED", rationale="Local staged mine must not commit after totality failure."),
    Fixture("empty-u-global", ((H,H),), 2,1,2, "Exact G1 exhausts U while PLAYING",
            _phases(("A",), (), 1, (((0,0),1),((1,0),1)), (), ((0,0),(1,0)), (), ((0,0),(1,0))),
            continuation=None, error_code="EMPTY_U_PLAYING", phase_e_status="NOT_REACHED",
            rationale="Synthetic all-mines input fails after staged exact acquisition; no successful E record."),
    Fixture("zero-world", ((H,1,H),), 3,1,0, "Zero exact worlds despite individually valid bounds",
            _phases(("A",), (), 0, (((0,0),0),((2,0),0)), _FRONTIER, ()),
            continuation=None, error_code="ZERO_WORLDS", phase_e_status="NOT_REACHED",
            rationale="Residual 1-of-2 conflicts with global total zero; Z=0 is no certainty evidence."),
    Fixture("arithmetic-extreme", _EXTREME_OBSERVATION, 30,2,27,
            "Exact integers outside binary64 and Oracle-A envelope",
            _phases(("A","D","E"), (), 88004802264174740, _EXTREME_COUNTS, (), _EXTREME_CELLS,
                    oracle_a_status="ORACLE_A_NOT_EVALUATED"), tie_target=(0,0),
            rationale="Closed-form C(60,27) and C(59,26) literals; all 60 marginals pinned; risk 9/20; "
                      "Oracle B/K agreement is shared-kernel representation evidence only."),
    Fixture("reflect-historical", ((H,1,H,1),), 4,1,1,
            "Fresh reflected local target and physical cost",
            _phases(("A",), (), 1, (((0,0),0),((2,0),1)), ((0,0),(2,0)), (), ((0,0),), ((2,0),))
            + _phases(("C",), ((2,0),), 1, (((0,0),0),), ((0,0),), (), ((0,0),)),
            local_mines=((2,0),), S_second_all=((0,0),), S_new=((0,0),), S_current=((0,0),),
            continuation="LOCAL_SAFE", phase_e_status="NOT_REACHED", transform="REFLECT_X_OF_HISTORICAL",
            screen_order=((0,0),(2,0)), cursor=(0,0), expected_category="DIRECT_SAFE_OPEN",
            expected_target=(0,0), model_c_lookup=(0,0,126005), expected_latency_us=126005,
            expected_route=(("OPEN",(0,0)),),
            rationale="Fresh cursor is (0,0); direct OPEN is 126005us and strictly beats every setup alternative."),
    Fixture("transpose-historical", ((1,),(H,),(1,),(H,)), 1,4,1,
            "Fresh transposed dimensions and local route",
            _phases(("A",), (), 1, (((0,1),1),((0,3),0)), ((0,1),(0,3)), (), ((0,3),), ((0,1),))
            + _phases(("C",), ((0,1),), 1, (((0,3),0),), ((0,3),), (), ((0,3),)),
            local_mines=((0,1),), S_second_all=((0,3),), S_new=((0,3),), S_current=((0,3),),
            continuation="LOCAL_SAFE", phase_e_status="NOT_REACHED", transform="TRANSPOSE_OF_HISTORICAL",
            screen_order=((0,1),(0,3)), cursor=(0,0), expected_category="DIRECT_SAFE_OPEN",
            expected_target=(0,3), model_c_lookup=(0,3,227896), expected_latency_us=227896,
            expected_route=(("OPEN",(0,3)),),
            rationale="Independent lookup T[0][3]=227896; FLAG(0,1),CHORD(0,2) totals252010 with one reveal."),
    Fixture("reflect-tie", ((H,H,H),(1,H,H)), 3,2,2, "Fresh vertical-reflection tie winner",
            _phases(("A","D","E"), (), 6,
                    (((0,0),2),((1,0),2),((2,0),3),((1,1),2),((2,1),3)),
                    ((0,0),(1,0),(1,1)), ((2,0),(2,1))),
            transform="REFLECT_Y_OF_EXACT_TIE", screen_order=((0,0),(1,0),(2,0),(1,1),(2,1)),
            tie_target=(0,0), cursor=(0,0), expected_category="EXACT_MINIMUM_RISK_GUESS",
            expected_target=(0,0), model_c_lookup=(0,0,126005),
            rationale="Mapped old winner would be (1,1); freshly ordered minimum set selects (0,0). "
                      "No route or reveal plan exists for an exact guess."),
    Fixture("transpose-tie", ((1,H),(H,H),(H,H)), 2,3,2, "Fresh transposition tie winner",
            _phases(("A","D","E"), (), 6,
                    (((1,0),2),((0,1),2),((1,1),2),((0,2),3),((1,2),3)),
                    ((1,0),(0,1),(1,1)), ((0,2),(1,2))),
            transform="TRANSPOSE_OF_EXACT_TIE", screen_order=((1,0),(0,1),(1,1),(0,2),(1,2)),
            tie_target=(1,0), cursor=(0,0), expected_category="EXACT_MINIMUM_RISK_GUESS",
            expected_target=(1,0), model_c_lookup=(1,0,126005),
            rationale="Mapped old winner (0,1) is wrong; freshly ordered minimum set selects (1,0). "
                      "No route or reveal plan exists for an exact guess."),
)

REQUIRED_FIXTURE_IDS = (
    "no-new-m", "historical-normalized-safe", "multiple-local-mines",
    "simultaneous-local-acquisition", "safe-stays-unresolved", "safe-mine-coexistence",
    "zero-residual", "public-fixed-mine-basis", "logical-fixed-mine",
    "physical-logical-overlap", "local-physical-logical-overlap", "frontier-only",
    "floating-only", "frontier-floating", "multiple-components-floating", "g0-only",
    "g1-only", "simultaneous-g1-g0", "g1-restriction", "empty-g1", "exact-equal-risk-tie",
    "empty-u-entry", "empty-u-local", "empty-u-global", "zero-world", "arithmetic-extreme",
    "reflect-historical", "transpose-historical", "reflect-tie", "transpose-tie",
)

_manifest_need(tuple(f.fixture_id for f in MANIFEST) == REQUIRED_FIXTURE_IDS,
               "Source-pinned fixture identities/order changed or duplicated.")


# Qualification code below may read immutable expectations, never manufacture
# or repair them. All solver/oracle imports are deliberately below the manifest.
from dataclasses import fields, is_dataclass, replace
from enum import Enum
from fractions import Fraction
from functools import lru_cache
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import time
import unittest

from core_engine import Action, CellState, GameStatus
from experiments import program_k_capability as _capability
from experiments import program_k_oracles as _oracles
from experiments import program_k_policy as _policy
from experiments import program_k_runner as _runner
from experiments import program_k_evidence as _evidence
from experiments import program_k_evaluator as _evaluator
from simple_algorithm import build_constraints, infer_deterministic
from simple_decision import DecisionKind
from stage3_physical import load_timing_table, MODEL_C_V1_IDENTITY
from stage3_planner import Stage3PlanningError


class QualificationError(ValueError):
    """Invalid/missing evidence never acquires a qualification PASS."""


def _need(value, detail):
    if not value:
        raise QualificationError(detail)


def _positive(value, label):
    _need(type(value) is int and value > 0, label + " requires a positive true integer.")


def _sha(value):
    _need(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None,
          "Expected lowercase SHA-256 identity.")


# A closed serialization vocabulary. No pickle, arbitrary imports, Engine,
# callbacks, live sessions, hidden answer, float, or mutable mappings.
@lru_cache(maxsize=1)
def _record_types():
    import simple_algorithm
    import simple_probability
    import simple_decision
    import stage3_planner
    import stage3_runner
    modules = (sys.modules[__name__], _capability, _oracles, _policy, _runner,
               _evidence, _evaluator, simple_algorithm, simple_probability,
               simple_decision, stage3_planner, stage3_runner)
    found = {}
    for module in modules:
        for value in vars(module).values():
            if (isinstance(value, type) and is_dataclass(value)
                    and value.__module__ == module.__name__
                    and value.__dataclass_params__.frozen
                    and value is not _evaluator.HiddenAnswer):
                found[value.__module__ + "." + value.__qualname__] = value
    return found


def _encode(value):
    if type(value) in (Action, CellState, GameStatus, DecisionKind):
        return {"enum": type(value).__name__, "name": value.name}
    if type(value) in (str, int, bool, type(None)):
        return value
    if type(value) is Fraction:
        return {"fraction": [value.numerator, value.denominator]}
    if type(value) is tuple:
        return {"tuple": [_encode(child) for child in value]}
    if type(value) is frozenset:
        _need(all(type(cell) is tuple and len(cell) == 2
                  and all(type(n) is int for n in cell) for cell in value),
              "Only coordinate sets may enter qualification records.")
        return {"coordinate_set": [_encode(c) for c in sorted(value, key=lambda c: (c[1], c[0]))]}
    key = type(value).__module__ + "." + type(value).__qualname__
    _need(key in _record_types() and _record_types()[key] is type(value),
          "Unsupported mutable/live/hidden value in qualification evidence.")
    return {"record": key, "fields": {field.name: _encode(getattr(value, field.name))
                                      for field in fields(value)}}


def canonical_bytes(value):
    """Lossless integer JSON with tagged tuples/sets/enums and closed record types."""
    return json.dumps(_encode(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def content_digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _decode(value):
    if type(value) in (str, int, bool, type(None)):
        return value
    _need(type(value) is dict, "Malformed canonical node.")
    if set(value) == {"tuple"}:
        _need(type(value["tuple"]) is list, "Malformed tuple.")
        return tuple(_decode(child) for child in value["tuple"])
    if set(value) == {"coordinate_set"}:
        _need(type(value["coordinate_set"]) is list, "Malformed coordinate set.")
        cells = tuple(_decode(child) for child in value["coordinate_set"])
        _need(all(type(c) is tuple and len(c) == 2
                  and all(type(n) is int for n in c) for c in cells),
              "Malformed coordinate membership.")
        _need(cells == tuple(sorted(set(cells), key=lambda c: (c[1], c[0]))),
              "Sets must preserve (x,y), uniquely ordered by (y,x).")
        return frozenset(cells)
    if set(value) == {"fraction"}:
        pair = value["fraction"]
        _need(type(pair) is list and len(pair) == 2 and all(type(n) is int for n in pair)
              and pair[1] > 0, "Malformed exact rational.")
        return Fraction(*pair)
    if set(value) == {"enum", "name"}:
        types = {t.__name__: t for t in (Action, CellState, GameStatus, DecisionKind)}
        _need(value["enum"] in types and type(value["name"]) is str, "Unknown enum.")
        return types[value["enum"]][value["name"]]
    _need(set(value) == {"record", "fields"} and value["record"] in _record_types(),
          "Unknown record schema; arbitrary code reconstruction is forbidden.")
    cls = _record_types()[value["record"]]
    _need(type(value["fields"]) is dict
          and set(value["fields"]) == {f.name for f in fields(cls)}, "Missing/extra record fields.")
    return cls(**{name: _decode(child) for name, child in value["fields"].items()})


def reconstruct(data, *, expected_digest=None):
    _need(type(data) is bytes, "Reconstruction requires canonical bytes.")
    if expected_digest is not None:
        _sha(expected_digest)
        _need(hashlib.sha256(data).hexdigest() == expected_digest, "Content digest mismatch.")
    def unique_pairs(pairs):
        result = {}
        for name, value in pairs:
            _need(name not in result, "Duplicate JSON key.")
            result[name] = value
        return result
    try:
        decoded = _decode(json.loads(data, object_pairs_hook=unique_pairs))
        _need(canonical_bytes(decoded) == data, "Noncanonical or lossy reconstruction.")
        return decoded
    except (TypeError, KeyError, AttributeError, json.JSONDecodeError) as error:
        raise QualificationError("Corrupt qualification encoding.") from error


SPEC_PATH = "docs/stage3-extended/STAGE3_PROGRAM_K_RESEARCH_SPEC.md"
PROTOCOL_PATH = "docs/stage3-extended/STAGE3_PROGRAM_K_GATE_R_PROTOCOL.md"
FROZEN_SPEC_SHA256 = "3e26c5b36d590e90bbd34951ee869cf63ed4f89b6cd3657a059132d065669903"
FROZEN_PROTOCOL_SHA256 = "43504d42d6c921c8291ed6c2a61cf198d2c64aaec2fb1f443caa59fbd59a91af"
SOURCE_PATHS = (
    SPEC_PATH, PROTOCOL_PATH,
    "experiments/program_k_capability.py", "experiments/program_k_policy.py",
    "experiments/program_k_runner.py", "experiments/program_k_oracles.py",
    "experiments/program_k_evidence.py", "experiments/program_k_harness.py",
    "experiments/program_k_evaluator.py",
    "tests/test_program_k_semantics.py", "tests/test_program_k_policy.py",
    "tests/test_program_k_harness.py",
    "core_engine.py", "simple_algorithm.py", "simple_probability.py",
    "simple_decision.py", "stage3_physical.py", "stage3_planner.py", "stage3_runner.py",
    "calibration/stage3_physical_profile_v1.json",
)


@dataclass(frozen=True)
class SourceFileIdentity:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        _need(self.path in SOURCE_PATHS, "Unregistered qualification source.")
        _sha(self.sha256)
        _positive(self.size_bytes, "source size")


@dataclass(frozen=True)
class SourceIdentity:
    files: tuple[SourceFileIdentity, ...]
    protocol_sha256: str
    spec_sha256: str
    model_id: str
    profile_sha256: str
    table_sha256: str

    def __post_init__(self):
        _need(type(self.files) is tuple and all(type(f) is SourceFileIdentity for f in self.files)
              and tuple(f.path for f in self.files) == SOURCE_PATHS, "Incomplete ordered source identity.")
        hashes = {f.path: f.sha256 for f in self.files}
        _need(self.protocol_sha256 == hashes[PROTOCOL_PATH] == FROZEN_PROTOCOL_SHA256
              and self.spec_sha256 == hashes[SPEC_PATH] == FROZEN_SPEC_SHA256,
              "Frozen authority identity changed.")
        identity = MODEL_C_V1_IDENTITY
        _need((self.model_id, self.profile_sha256, self.table_sha256)
              == (identity.physical_model_id, identity.physical_profile_sha256,
                  identity.timing_table_sha256), "Frozen physical identity changed.")


def capture_source_identity():
    root = Path(__file__).resolve().parents[1]
    files = []
    for path in SOURCE_PATHS:
        raw = (root / path).read_bytes()
        files.append(SourceFileIdentity(path, hashlib.sha256(raw).hexdigest(), len(raw)))
    load_timing_table()  # Authenticate stored profile bytes and the complete table; no P-8 scan.
    identity = MODEL_C_V1_IDENTITY
    return SourceIdentity(tuple(files), FROZEN_PROTOCOL_SHA256, FROZEN_SPEC_SHA256,
                          identity.physical_model_id, identity.physical_profile_sha256,
                          identity.timing_table_sha256)


@dataclass(frozen=True)
class P8Gate:
    status: str
    classification: str
    evidence_digest: str | None
    reason: str


def check_p8_gate(result):
    """Consume and revalidate supplied evidence. Never invoke a P-8 checker."""
    if result is None:
        return P8Gate("INCOMPLETE", "MISSING_P8", None, "Full frozen P-8 is unexecuted or absent.")
    if type(result) is not _oracles.P8Result:
        return P8Gate("FAIL", "IMPLEMENTATION_IDENTITY_FAIL", None, "Invalid P-8 evidence type.")
    try:
        checked = replace(result)
        digest = checked.evidence_sha256
        expected_source = hashlib.sha256(Path(_oracles.__file__).read_bytes()).hexdigest()
        _need(checked.checker_source_sha256 == expected_source, "P-8 checker source identity changed.")
    except (ValueError, TypeError, AttributeError) as error:
        return P8Gate("FAIL", "IMPLEMENTATION_IDENTITY_FAIL", None, str(error))
    if checked.scope != "FROZEN_P8":
        return P8Gate("INCOMPLETE", "PRIVATE_CHECK_NOT_RESEARCH_EVIDENCE", digest,
                      "A private bounded check cannot satisfy the frozen research premise.")
    if checked.premise_failure:
        # P8Result reconstructs witnesses from authenticated frozen values. A
        # prefix counterexample survives interruption; no full scan is needed
        # to falsify a genuinely authenticated nonpositive witness.
        return P8Gate("FAIL", "PROGRAM_K_RESEARCH_FAIL", digest,
                      "Authenticated nonpositive frozen detour counterexample.")
    if (checked.authentication_status == "AUTHENTICATED"
            and checked.expected_triple_count == checked.visited_triple_count == 110361600
            and checked.completion_marker == "COMPLETE" and checked.status == "PASS"
            and checked.zero_gap_count == checked.negative_gap_count == 0):
        return P8Gate("PASS", "FROZEN_P8_COMPLETE", digest, "Authenticated exhaustive evidence.")
    return P8Gate("INCOMPLETE", "INTERRUPTED_P8", digest, "Frozen P-8 coverage is incomplete.")


@dataclass(frozen=True)
class ExternalFlagAudit:
    record: _evidence.ExternalV1FlagProvenance
    verification: _evidence.EvidenceComparison
    public_support: tuple  # checker-only proof views; NEVER K-owned acquisitions


@dataclass(frozen=True)
class AcquisitionAudit:
    """owned_M_after is this certificate's accepted set, not a batch snapshot.

    Actual simultaneous phase/boundary snapshots remain in DecisionAnalysis.
    External support views never enter either owned set.
    """
    certificate: object
    boundary: int
    prior_certificates: tuple
    external_flags: tuple[ExternalFlagAudit, ...]
    certificate_check: object | None
    status: str
    detail: str
    owned_M_before: frozenset
    owned_M_after: frozenset


def _flag_public_support(record):
    """Translate verified public V1 evidence for the existing proof checker.

    These proof views describe physical antecedents only. Their owning original
    ExternalV1FlagProvenance remains in the audit; no view is returned to K,
    added to M, or described as a K acquisition.
    """
    prior = []
    for ancestor in record.prior_flags:
        prior.extend(_flag_public_support(ancestor))
    target = (record.move.x, record.move.y)
    v1 = record.decision.evidence
    if v1.kind is DecisionKind.LOCAL_DETERMINISTIC:
        clue = next(c.source for c in v1.constraints
                    if target in c.hidden_cells and c.remaining_mines == len(c.hidden_cells))
        view = _oracles.LocalMineCertificate(record.observation, record.num_mines, clue,
                                             target, frozenset(), GameStatus.PLAYING)
    else:
        counts = v1.probability_result
        view = _oracles.ExactGlobalMineCertificate(
            record.observation, record.num_mines, target, frozenset(), GameStatus.PLAYING,
            counts.total_worlds, tuple((p.coordinate, p.mine_worlds) for p in counts.probabilities))
    return tuple(prior) + (view,)


def audit_acquisition(certificate, *, boundary, prior_certificates=(), external_flags=()):
    """Post-hoc ordered external-FLAG audit followed by the independent K check."""
    _need(type(boundary) is int and boundary >= 0, "Acquisition needs an input boundary.")
    _need(type(certificate) in (_oracles.LocalMineCertificate, _oracles.ExactGlobalMineCertificate),
          "Only raw public K acquisition certificates are accepted.")
    _need(type(prior_certificates) is tuple and type(external_flags) is tuple,
          "Ordered immutable antecedents are required.")
    before = certificate.retained_mines
    after = before | {certificate.target}
    audits = []
    def result(status, detail, check=None):
        return AcquisitionAudit(certificate, boundary, prior_certificates, tuple(audits),
                                check, status, detail, before, after)
    flags = frozenset((x, y) for y, row in enumerate(certificate.observation)
                      for x, glyph in enumerate(row) if glyph == CellState.FLAGGED)
    required = flags - before
    by_cell = {}
    try:
        for record in external_flags:
            _need(type(record) is _evidence.ExternalV1FlagProvenance, "Bare FLAG is not provenance.")
            cell = (record.move.x, record.move.y)
            _need(cell not in by_cell and cell in flags and record.input_index < boundary,
                  "External FLAG must uniquely precede this acquisition and still be physical.")
            _need(record.num_mines == certificate.num_mines
                  and len(record.observation) == len(certificate.observation)
                  and len(record.observation[0]) == len(certificate.observation[0])
                  and all(old == CellState.HIDDEN or old == certificate.observation[y][x]
                          for y, row in enumerate(record.observation) for x, old in enumerate(row)),
                  "External FLAG belongs to another public prefix.")
            check = _evidence.verify_v1_flag_provenance(record)
            support = _flag_public_support(record) if check.status == "PASS" else ()
            audits.append(ExternalFlagAudit(record, check, support))
            by_cell[cell] = record
            if check.status != "PASS":
                return result("NOT_EVALUATED" if check.status == "NOT_EVALUATED" else "FAIL",
                              "External V1 provenance: " + check.detail)
        if not required <= by_cell.keys():
            return result("INCOMPLETE", "Missing external V1 FLAG antecedent outside prior M.")
        support = list(prior_certificates)
        for audit in audits:
            support.extend(audit.public_support)
        unique = []
        for proof in support:
            if proof not in unique:
                unique.append(proof)
        # A chronological public extension can only expose additional cells.
        # Stable ordering preserves original proof order within one prefix.
        unique.sort(key=lambda p: sum(v != CellState.HIDDEN for row in p.observation for v in row))
        if type(certificate) is _oracles.LocalMineCertificate:
            check = _oracles.verify_local_certificate(certificate, prior_certificates=tuple(unique))
        else:
            check = _oracles.verify_exact_global_certificate(certificate, prior_certificates=tuple(unique))
        return result("PASS", "Public antecedents checked separately; only the K target enters M.", check)
    except (ValueError, TypeError, AttributeError, StopIteration) as error:
        return result("FAIL", str(error))


@dataclass(frozen=True)
class OracleCoverage:
    status: str
    variable_count: int
    envelope: int
    reason: str | None

    def __post_init__(self):
        _need(self.status in ("ORACLE_A_EVALUATED", "ORACLE_A_NOT_EVALUATED")
              and type(self.variable_count) is int and self.variable_count >= 0
              and type(self.envelope) is int and self.envelope == 16,
              "Invalid Oracle-A coverage record.")
        _need((self.reason is None) == (self.status == "ORACLE_A_EVALUATED"),
              "Unevaluated arithmetic needs a reason, never an equality claim.")


@dataclass(frozen=True)
class PhaseVerification:
    expectation: FixtureExpectation
    accounting: object | None
    oracle_a_coverage: OracleCoverage
    oracle_a: _oracles.OracleAResult | None
    oracle_b: _oracles.OracleBResult | None
    oracle_b_status: str
    materialized_observation: Observation
    local_constraints: tuple
    direct_safes: frozenset
    direct_mines: frozenset
    discrepancies: tuple[str, ...]

    @property
    def status(self):
        return "FAIL" if self.discrepancies else "PASS"


@dataclass(frozen=True)
class FixtureVerification:
    fixture: Fixture
    prefix_decisions: tuple
    decision: object | None
    selection: object | None
    phases: tuple[PhaseVerification, ...]
    acquisition_audits: tuple[AcquisitionAudit, ...]
    failure_code: str | None
    final_M: frozenset
    discrepancies: tuple[str, ...]

    @property
    def status(self):
        return ("PASS" if not self.discrepancies and all(p.status == "PASS" for p in self.phases)
                and all(a.status == "PASS" for a in self.acquisition_audits) else "FAIL")


def _public_premises(fixture):
    return tuple(_oracles.LocalMineCertificate(
        p.observation, fixture.num_mines, p.clue, p.target,
        frozenset(p.retained_mines), GameStatus.PLAYING) for p in fixture.provenance)


def _compare_worlds(actual, expected, discrepancies, name):
    if actual.total_worlds != expected.Z or actual.mine_worlds != expected.mine_worlds:
        discrepancies.append(name + ": exact Z/all numerators differ from literal preregistration.")
    if tuple(sorted(actual.G0, key=lambda c: (c[1], c[0]))) != expected.G0:
        discrepancies.append(name + ": G0 differs.")
    if tuple(sorted(actual.G1, key=lambda c: (c[1], c[0]))) != expected.G1:
        discrepancies.append(name + ": G1 differs.")


def verify_fixture(fixture):
    """Unit-integration verification of one sealed A-E4 fixture; no stage verdict.

    K only replays the explicitly registered public prefix. Oracle B directly
    invokes local helpers or exact calculation at the corresponding phase; a
    fresh Stage-2 scheduler is never phase evidence. A/C audit counts are not
    mislabeled as a K exact call. Expected negative K results are not research
    failures. The manifest remains untouched.
    """
    _need(type(fixture) is Fixture, "Expected a preregistered public fixture.")
    fixture = reconstruct(canonical_bytes(fixture))
    session = _capability.KLocalSession(fixture.width, fixture.height, fixture.num_mines)
    prefixes, audits, errors = [], [], []
    declared = _public_premises(fixture)
    for index, proof in enumerate(declared):
        _oracles.verify_local_certificate(proof, prior_certificates=declared[:index])
    proofs = declared
    for index, observation in enumerate(fixture.public_prefix):
        previous = session.analyze_decision(observation, status=GameStatus.PLAYING)
        prefixes.append(previous)
        for proof in previous.local.certificates + previous.exact_certificates:
            audit = audit_acquisition(proof, boundary=index, prior_certificates=proofs)
            audits.append(audit)
            if proof not in proofs:
                proofs += (proof,)
    if session.M != frozenset(fixture.pre_acquisition_M):
        errors.append("Public prefix did not reconstruct preregistered pre-acquisition M.")
    decision = selection = None
    failure = None
    before = session.M
    try:
        decision = session.analyze_decision(fixture.observation, status=GameStatus.PLAYING)
    except _capability.KIntegrityError as error:
        failure = error.code
    if failure != fixture.error_code:
        errors.append("K failure classification differs from preregistration.")
    if failure is not None and session.M != before:
        errors.append("Failed decision committed or repaired M.")
    if decision is not None:
        local = decision.local
        for name in ("S_first", "S_second_all", "S_new", "S_current"):
            if getattr(local, name) != frozenset(getattr(fixture, name)):
                errors.append("K local field " + name + " differs.")
        if local.acquired_mines != frozenset(fixture.local_mines):
            errors.append("Simultaneous local acquisition differs.")
        if (decision.continuation != fixture.continuation
                or decision.phase_e_status != fixture.phase_e_status
                or decision.guess_target != fixture.tie_target):
            errors.append("Reached phases/continuation/tie target differ.")
        local_proofs = proofs
        for proof in local.certificates:
            audits.append(audit_acquisition(proof, boundary=len(prefixes),
                                            prior_certificates=local_proofs))
            local_proofs += (proof,)
        exact_proofs = local_proofs
        for proof in decision.exact_certificates:
            audits.append(audit_acquisition(proof, boundary=len(prefixes),
                                            prior_certificates=exact_proofs))
            exact_proofs += (proof,)
        if fixture.cursor is not None:
            table = load_timing_table()
            selection = _policy.select_policy(decision, fixture.cursor, table)
            _runner.validate_k_p0_execution(
                fixture.observation, selection.move, status=GameStatus.PLAYING,
                num_mines=fixture.num_mines, cursor=fixture.cursor, current_mines=session.M,
                decision=decision, selection=selection)
            if (selection.category != fixture.expected_category
                    or (selection.move.x, selection.move.y) != fixture.expected_target):
                errors.append("Fresh transformed policy target/category differs.")
            if fixture.model_c_lookup is not None:
                dx, dy, cost = fixture.model_c_lookup
                if (dx, dy) != (abs(selection.move.x - fixture.cursor[0]),
                               abs(selection.move.y - fixture.cursor[1])) or table[dx][dy] != cost:
                    errors.append("Preregistered Model-C lookup differs.")
            if fixture.expected_route is not None:
                route = tuple((move.action.name, (move.x, move.y)) for move in selection.plan.actions)
                if route != fixture.expected_route or selection.plan.latency_us != fixture.expected_latency_us:
                    errors.append("Preregistered route/latency differs.")
            elif fixture.expected_category == "EXACT_MINIMUM_RISK_GUESS" and selection.plan is not None:
                errors.append("An exact guess must have no routed setup plan.")
    else:
        local_proofs = exact_proofs = proofs

    phase_records = []
    for expected in fixture.expectations:
        problems = []
        phase = expected.phase
        phase_proofs = proofs if phase == "A" else exact_proofs if phase == "E" else local_proofs
        accounting = None
        if decision is not None:
            accounting = (decision.local.before if phase == "A" else decision.after if phase == "E"
                          else decision.local.after)
            if accounting.M != frozenset(expected.M):
                problems.append("K M snapshot differs at phase " + phase)
        mines = frozenset(expected.M)
        materialized = tuple(tuple(F if value == H and (x, y) in mines else value
                                   for x, value in enumerate(row))
                             for y, row in enumerate(fixture.observation))
        constraints = build_constraints(materialized)
        direct = infer_deterministic(constraints)
        if accounting is not None:
            rows = tuple((c.source, c.rc, c.Uc) for c in accounting.constraints)
            reference = tuple((c.source, c.remaining_mines, c.hidden_cells) for c in constraints)
            if rows != reference:
                problems.append("Phase-matched Oracle-B local accounting differs.")
            fixed = frozenset((x, y) for y, row in enumerate(materialized)
                              for x, glyph in enumerate(row) if glyph == F)
            unresolved = frozenset((x, y) for y, row in enumerate(materialized)
                                   for x, glyph in enumerate(row) if glyph == H)
            if (accounting.J != fixed or accounting.U != unresolved
                    or accounting.b != fixture.num_mines - len(fixed)):
                problems.append("Physical/logical union/domain/budget accounting differs.")
            if phase == "A" and (direct.safe_cells != frozenset(fixture.S_first)
                                or direct.mine_cells != frozenset(fixture.local_mines)):
                problems.append("Oracle-B first direct pass differs.")
            if phase in ("C", "D") and (direct.safe_cells != frozenset(fixture.S_second_all)
                                       or direct.mine_cells):
                problems.append("Oracle-B second direct pass differs or acquired a new mine.")
        a = b = None
        b_status = "NOT_REACHED"
        try:
            a = _oracles.enumerate_public_worlds(
                fixture.observation, fixture.num_mines, status=GameStatus.PLAYING,
                logical_mines=mines, proofs=phase_proofs)
            coverage = OracleCoverage("ORACLE_A_EVALUATED", len(a.mine_worlds), 16, None)
            _compare_worlds(a, expected, problems, "Oracle A")
        except _oracles.OracleANotEvaluated as error:
            coverage = OracleCoverage(error.status, error.variable_count, error.envelope, error.reason)
        if coverage.status != expected.oracle_a_status:
            problems.append("Oracle-A actual coverage differs from preregistration.")
        if phase in ("D", "E"):
            b = _oracles.materialized_exact_reference(
                fixture.observation, fixture.num_mines, status=GameStatus.PLAYING,
                logical_mines=mines, proofs=phase_proofs)
            b_status = b.shared_kernel_evidence
            _compare_worlds(b, expected, problems, "Oracle B")
            if b.frontier_cells != expected.frontier or b.unconstrained_cells != expected.floating:
                problems.append("Oracle-B frontier/floating partition differs.")
            exact = None if decision is None else decision.phase_d if phase == "D" else decision.phase_e
            if exact is None:
                problems.append("K omitted a mandatory reached exact phase.")
            else:
                _compare_worlds(exact, expected, problems, "K")
                if exact.frontier_cells != expected.frontier or exact.unconstrained_cells != expected.floating:
                    problems.append("K frontier/floating partition differs.")
        hidden_order = tuple((x, y) for y, row in enumerate(materialized)
                             for x, glyph in enumerate(row) if glyph == H)
        frontier_set = frozenset(c for constraint in constraints for c in constraint.hidden_cells)
        if (tuple(c for c in hidden_order if c in frontier_set) != expected.frontier
                or tuple(c for c in hidden_order if c not in frontier_set) != expected.floating):
            problems.append("Preregistered complete frontier/floating partition differs.")
        if expected.Z == 0 and fixture.error_code != "ZERO_WORLDS":
            problems.append("Zero-world proof cannot support a positive fixture.")
        phase_records.append(PhaseVerification(expected, accounting, coverage, a, b, b_status,
                                              materialized, constraints, direct.safe_cells,
                                              direct.mine_cells, tuple(problems)))
    if fixture.screen_order and fixture.screen_order != tuple(
            c for c, _ in fixture.expectations[0].mine_worlds):
        errors.append("Fresh screen-reading order differs from preregistration.")
    return FixtureVerification(fixture, tuple(prefixes), decision, selection, tuple(phase_records),
                               tuple(audits), failure, session.M, tuple(errors))


@dataclass(frozen=True)
class ProbeSpec:
    gate_id: str
    test_classes: tuple[str, ...]
    purpose: str


# Fixed, source-identified executable obligations. Loading is late to avoid a
# harness/test import cycle; no caller-selected test or arbitrary callback is a
# qualification substitute. These tests include negative detection/containment.
_H = "tests.test_program_k_harness."
_S = "tests.test_program_k_semantics."
_P = "tests.test_program_k_policy."
PROBES = (
    ProbeSpec("A-E1/A-E2", (_H+"ProgramKSlice6InterfaceAndEffectsTests",),
              "Public interface sentinels, exact effects and terminal segregation"),
    ProbeSpec("A-E3", (_H+"ProgramKSlice6TimingAndContainmentTests",),
              "Planner-only and separate validation/diagnostic timing boundaries"),
    ProbeSpec("P-1/P-2/LOCAL/ACCOUNTING", (_S+"ProgramKLocalSemanticsTests",
              _S+"ProgramKIndependentCertificateTests", _S+"ProgramKOracleATests"),
              "Phase matching, certificates, overlap, normalization and independent arithmetic"),
    ProbeSpec("EXACT/TOTALITY/MATERIALIZATION", (_S+"ProgramKExactDecisionTests",),
              "Exact weighting, G0/G1, retained provenance, empty domains and zero worlds"),
    ProbeSpec("K-P0/POLICY/CHORD", (_P+"ProgramKPolicyTests",
              _H+"ProgramKExecutionValidatorTests"), "Frozen mechanics and separate physical validator"),
    ProbeSpec("EXECUTION/TERMINAL/DETERMINISM", (_H+"ProgramKTreatmentRunnerTests",),
              "One input, fresh replanning, M lifecycle, deterministic streams"),
    ProbeSpec("V1-AUTHORITY/P-5", (_H+"ProgramKControlRunnerTests",),
              "Frozen V1 authority, detached shadow, errors, watchdog and system abort"),
    ProbeSpec("O-4", (_H+"ProgramKSlice6O4ProjectionTests",),
              "Every ordered semantic field, negative omission and corruption controls"),
    ProbeSpec("P-3", (_H+"ProgramKSlice7GuessCheckpointTests",),
              "Ordinal-normalized CONTROL/K-P0 uncertain guesses and field/divergence faults"),
    ProbeSpec("SHADOW-SOUNDNESS/EXTERNAL-FLAG", (_H+"ProgramKSlice6SoundnessAndFlagEvidenceTests",
              _S+"ProgramKExternalPhysicalFlagTests"), "Public discrepancy and separate V1 FLAG provenance"),
    ProbeSpec("EVALUATOR", (_H+"ProgramKSlice7EvaluatorTests",),
              "One-way falsification, excluded noncertainty actions and no feedback"),
)


@dataclass(frozen=True)
class ExecutionArchive:
    case_id: str
    variant: str
    result: object


_ARCHIVE_CASE = _H + "ProgramKSlice6InterfaceAndEffectsTests.test_r_t_actual_control_and_shadow_capture_exact_effects_and_initial_final_coverage"
_TREATMENT_ARCHIVE_CASE = _H + "ProgramKSlice6InterfaceAndEffectsTests.test_s_later_terminal_archive_cannot_resume_k_shadow_or_public_comparison"
_GUESS_ARCHIVE_CASE = _H + "ProgramKSlice7GuessCheckpointTests.test_fixed_guess_pair"
# Public metadata of the fixed 5x1 comparator probe, independent of K counts.
_P3_NUM_MINES = 2



def _guess_cells(cells):
    _need(type(cells) in (tuple, frozenset), "Checkpoint coordinates must be immutable.")
    _need(all(type(c) is tuple and len(c) == 2
              and all(type(v) is int and v >= 0 for v in c) for c in cells)
          and len(set(cells)) == len(cells), "Malformed/duplicate checkpoint coordinates.")


@dataclass(frozen=True)
class GuessCheckpoint:
    """P-3 normalized semantics only; physical action indices are not pairing keys."""
    case_id: str
    guess_ordinal: int
    revealed_clues: tuple
    fixed_mines: frozenset
    unresolved: frozenset
    remaining_mines: int
    total_worlds: int
    mine_worlds: tuple
    probabilities: tuple
    minimum_risk: Fraction
    minimum_risk_cells: frozenset
    target: Coordinate
    terminal_outcome: GameStatus

    def __post_init__(self):
        _need(type(self.case_id) is str and bool(self.case_id), "Missing checkpoint case.")
        _positive(self.guess_ordinal, "uncertain-guess ordinal")
        _positive(self.total_worlds, "unreduced Z")
        _need(type(self.remaining_mines) is int and 0 < self.remaining_mines < len(self.unresolved),
              "Uncertain checkpoint requires a nontrivial exact remaining budget.")
        for cells in (self.fixed_mines, self.unresolved, self.minimum_risk_cells):
            _need(type(cells) is frozenset, "Checkpoint sets must be immutable.")
            _guess_cells(cells)
        _guess_cells((self.target,))
        for name in ("revealed_clues", "mine_worlds", "probabilities"):
            pairs = getattr(self, name)
            _need(type(pairs) is tuple and all(type(p) is tuple and len(p) == 2 for p in pairs),
                  "Missing ordered " + name)
            cells = tuple(c for c, _ in pairs)
            _guess_cells(cells)
            _need(cells == tuple(sorted(cells, key=lambda c: (c[1], c[0]))),
                  name + " must preserve screen order using stored (x,y).")
        clues = frozenset(c for c, _ in self.revealed_clues)
        _need(all(type(v) is int and 0 <= v <= 8 for _, v in self.revealed_clues)
              and not (clues & self.fixed_mines or clues & self.unresolved
                       or self.fixed_mines & self.unresolved), "Malformed normalized public partition.")
        domain = tuple(sorted(self.unresolved, key=lambda c: (c[1], c[0])))
        _need(tuple(c for c, _ in self.mine_worlds) == domain
              and tuple(c for c, _ in self.probabilities) == domain,
              "Exact evidence must cover every unresolved cell once.")
        _need(all(type(n) is int and 0 < n < self.total_worlds for _, n in self.mine_worlds),
              "Certainty is not exhausted or a numerator is malformed.")
        _need(sum(n for _, n in self.mine_worlds) == self.remaining_mines*self.total_worlds,
              "Complete marginal mine mass differs from the remaining public budget.")
        _need(all(type(p) is Fraction for _, p in self.probabilities)
              and self.probabilities == tuple((c, Fraction(n, self.total_worlds))
                                             for c, n in self.mine_worlds),
              "Probabilities must reconstruct from unreduced integer counts.")
        risk = min(p for _, p in self.probabilities)
        minima = frozenset(c for c, p in self.probabilities if p == risk)
        _need(type(self.minimum_risk) is Fraction and self.minimum_risk == risk
              and self.minimum_risk_cells == minima
              and self.target == min(minima, key=lambda c: (c[1], c[0])),
              "Minimum risk/set/target must retain exact frozen tie evidence.")
        _need(type(self.terminal_outcome) is GameStatus
              and self.terminal_outcome in (GameStatus.WON, GameStatus.LOST),
              "Eventual terminal outcome is mandatory.")


@dataclass(frozen=True)
class GuessCheckpointAudit:
    case_id: str
    variant: str
    num_mines: int
    archive_digest: str | None
    checkpoints: tuple[GuessCheckpoint, ...]
    incomplete: tuple[str, ...]

    def __post_init__(self):
        _need(type(self.case_id) is str and bool(self.case_id)
              and self.variant in ("CONTROL", "K-P0"), "Invalid P-3 case/variant.")
        _need(type(self.num_mines) is int and self.num_mines >= 0, "Explicit public mine total required.")
        if self.archive_digest is not None:
            _sha(self.archive_digest)
        _need(type(self.checkpoints) is tuple and all(type(c) is GuessCheckpoint for c in self.checkpoints),
              "Malformed checkpoint sequence.")
        _need(type(self.incomplete) is tuple and all(type(s) is str and bool(s) for s in self.incomplete),
              "Missing-evidence reasons must be immutable.")
        for ordinal, checkpoint in enumerate(self.checkpoints, 1):
            replace(checkpoint)
            _need(checkpoint.case_id == self.case_id and checkpoint.guess_ordinal == ordinal,
                  "Checkpoint correspondence requires contiguous within-case ordinals.")
            _need(checkpoint.remaining_mines == self.num_mines-len(checkpoint.fixed_mines),
                  "Checkpoint budget is not bound to its declared public mine total.")
        _need(bool(self.incomplete) or self.archive_digest is not None, "Complete evidence needs its archive identity.")

    @property
    def status(self):
        return "INCOMPLETE" if self.incomplete else "COMPLETE"


@dataclass(frozen=True)
class GuessComparison:
    control: GuessCheckpointAudit | None
    kp0: GuessCheckpointAudit | None
    status: str
    differences: tuple[str, ...]

    def __post_init__(self):
        _need(self.status in ("PASS", "FAIL", "INCOMPLETE")
              and type(self.differences) is tuple and all(type(s) is str for s in self.differences),
              "Malformed P-3 comparison result.")


def extract_guess_checkpoints(archive, *, num_mines):
    """Read sealed public records only: no scheduler, oracle, solver or truth call.

    CONTROL does not archive the public mine total. The caller supplies it from
    the fixed case declaration; it is retained explicitly and never inferred
    from K's budget or from probability counts.
    """
    _need(type(archive) is ExecutionArchive and archive.variant in ("CONTROL", "K-P0"),
          "P-3 requires an identified CONTROL or K-P0 execution archive.")
    _need(type(num_mines) is int and num_mines >= 0, "Explicit public mine total required.")
    checkpoints, digest = [], None
    try:
        archive = reconstruct(canonical_bytes(archive))
        digest = content_digest(archive)
        result = archive.result
        expected = _runner.ControlCaptureResult if archive.variant == "CONTROL" else _runner.KRunResult
        _need(type(result) is expected and bool(result.traces), "Missing complete execution traces.")
        effects = result.effects if archive.variant == "CONTROL" else tuple(t.public_effect for t in result.traces)
        _need(type(effects) is tuple and len(effects) == len(result.traces)
              and all(type(e) is _evidence.PublicEffectRecord for e in effects),
              "Missing status-gated preinput public effects.")
        _need(_evidence.validate_public_effect_stream(effects, complete=True).status == "PASS"
              and result.status in (GameStatus.WON, GameStatus.LOST)
              and result.status == effects[-1].status_after, "Physical stream/outcome is unreconstructable.")
        for index, (trace, effect) in enumerate(zip(result.traces, effects)):
            _need(effect.status_before is GameStatus.PLAYING and effect.input_index == index
                  and (trace.move.action, trace.move.x, trace.move.y) ==
                      (effect.move.action, effect.move.x, effect.move.y)
                  and trace.status_after is effect.status_after, "Trace/preinput effect binding differs.")
            observation = effect.before_observation
            flags = frozenset((x,y) for y,row in enumerate(observation) for x,v in enumerate(row) if v == F)
            hidden = frozenset((x,y) for y,row in enumerate(observation) for x,v in enumerate(row) if v == H)
            if index == 0:
                _need(trace.move.action is Action.OPEN and (trace.move.x,trace.move.y) == (0,0)
                      and len(hidden) == len(observation)*len(observation[0]),
                      "Missing canonical initial OPEN boundary.")
                _need(trace.decision is None if archive.variant == "CONTROL" else
                      trace.selection is None and trace.category == "POLICY_INITIAL_OPEN",
                      "Initial OPEN cannot carry inference/guess authority.")
                continue
            if archive.variant == "CONTROL":
                _need(trace.decision is not None, "Missing noninitial frozen CONTROL decision.")
                _runner._validate_execution(observation, trace.move, trace.decision)
                # Projection validates detached fields without recomputing a scheduler.
                v1 = _evidence.project_v1_decision(trace.decision)
                _need(v1.move == effect.move, "CONTROL selection/effect binding differs.")
                evidence = trace.decision.evidence
                if evidence.kind is not DecisionKind.PROBABILITY_GUESS:
                    # A present uncertain count cannot be hidden by relabeling its kind.
                    counts = evidence.probability_result
                    if counts is not None and trace.move.action is Action.OPEN:
                        selected = next((c for c in counts.probabilities
                                         if c.coordinate == (trace.move.x, trace.move.y)), None)
                        _need(selected is not None and selected.mine_worlds in (0, counts.total_worlds),
                              "Uncertain CONTROL OPEN is mislabeled as certainty.")
                    continue
                counts = evidence.probability_result
                _need(counts is not None and trace.decision.plan is None
                      and trace.move == evidence.move and trace.move.action is Action.OPEN
                      and not evidence.deterministic_result.safe_cells
                      and not evidence.deterministic_result.mine_cells,
                      "CONTROL uncertain OPEN lacks complete certainty-exhausted evidence.")
                Z = counts.total_worlds
                _need(all(c.total_worlds == Z for c in counts.probabilities), "CONTROL denominators differ.")
                numbers = tuple((c.coordinate,c.mine_worlds) for c in counts.probabilities)
                fixed, unresolved = flags, hidden
                budget = num_mines-len(fixed)
                probabilities = tuple((c.coordinate,c.probability) for c in counts.probabilities)
                risk = min(p for _,p in probabilities)
                minima = frozenset(c for c,p in probabilities if p == risk)
            else:
                selection = trace.selection
                _need(selection is not None and selection.category == trace.category
                      and selection.move == trace.move, "Missing/mislabeled K-P0 selection.")
                decision = selection.evidence
                _need(type(decision) is _capability.DecisionAnalysis
                      and decision.observation == observation and decision.num_mines == num_mines
                      and decision.after.M == trace.preinput_M and decision.after.P == flags,
                      "K-P0 decision is not bound to the current public checkpoint.")
                _runner.validate_k_p0_execution(observation, trace.move, status=GameStatus.PLAYING,
                    num_mines=num_mines, cursor=trace.cursor_before, current_mines=trace.preinput_M,
                    decision=decision, selection=selection)
                _need((trace.category == "EXACT_MINIMUM_RISK_GUESS") ==
                      (decision.continuation == "EXACT_GUESS"), "K-P0 uncertain branch was relabeled.")
                if trace.category != "EXACT_MINIMUM_RISK_GUESS":
                    continue
                exact = decision.phase_e
                _need(exact is not None and decision.phase_d is not None
                      and decision.phase_e_status in ("REACHED_CHANGED", "REACHED_NO_CHANGE")
                      and trace.move.action is Action.OPEN and selection.plan is None
                      and not decision.selection_safe_cells and not decision.local.S_current
                      and not exact.G0 and not exact.G1,
                      "K-P0 uncertain OPEN lacks complete certainty-exhausted Phase E.")
                fixed, unresolved = flags | trace.preinput_M, hidden-trace.preinput_M
                budget = num_mines-len(fixed)
                _need(decision.after.J == fixed and decision.after.U == unresolved and decision.after.b == budget
                      and tuple(exact.unresolved_cells) == tuple(c for c,_ in exact.mine_worlds),
                      "K-P0 normalized partition/budget/exact domain differs.")
                Z, numbers = exact.total_worlds, exact.mine_worlds
                probabilities = tuple((c,Fraction(n,Z)) for c,n in numbers)
                risk, minima = exact.minimum_risk, exact.minimum_risk_cells
                _need(decision.guess_target == (trace.move.x,trace.move.y),
                      "K-P0 selection differs from the archived exact guess target.")
            clues = tuple(((x,y),v) for y,row in enumerate(observation) for x,v in enumerate(row) if 0 <= v <= 8)
            checkpoints.append(GuessCheckpoint(archive.case_id, len(checkpoints)+1, clues,
                fixed, unresolved, budget, Z, numbers, probabilities, risk, minima,
                (trace.move.x,trace.move.y), result.status))
        return GuessCheckpointAudit(archive.case_id, archive.variant, num_mines, digest, tuple(checkpoints), ())
    except (ValueError, TypeError, AttributeError, IndexError, KeyError, StopIteration,
            ZeroDivisionError, _runner.Stage3RunnerError, Stage3PlanningError) as error:
        return GuessCheckpointAudit(archive.case_id, archive.variant, num_mines, digest,
                                    tuple(checkpoints), (str(error) or type(error).__name__,))


def compare_guess_checkpoints(control, kp0):
    """Pure ordinal comparison. Divergence is FAIL, never a research diagnosis."""
    try:
        _need(type(control) is GuessCheckpointAudit and type(kp0) is GuessCheckpointAudit,
              "Missing typed P-3 checkpoint evidence.")
        replace(control)
        replace(kp0)
        _need(control.variant == "CONTROL" and kp0.variant == "K-P0"
              and control.case_id == kp0.case_id, "P-3 correspondence requires the same case and named variants.")
        _need(control.status == kp0.status == "COMPLETE", "Required checkpoint evidence is incomplete.")
    except (ValueError, TypeError, AttributeError, IndexError) as error:
        return GuessComparison(control if type(control) is GuessCheckpointAudit else None,
                               kp0 if type(kp0) is GuessCheckpointAudit else None,
                               "INCOMPLETE", (str(error),))
    differences = []
    if control.num_mines != kp0.num_mines:
        differences.append("public num_mines differs")
    if len(control.checkpoints) != len(kp0.checkpoints):
        differences.append("actual uncertain-guess count differs (extra/missing checkpoint)")
    for left, right in zip(control.checkpoints, kp0.checkpoints):
        for field in fields(GuessCheckpoint):
            if getattr(left, field.name) != getattr(right, field.name):
                differences.append("guess[" + str(left.guess_ordinal) + "]." + field.name + " differs")
    return GuessComparison(control, kp0, "FAIL" if differences else "PASS", tuple(differences))


@dataclass(frozen=True)
class ProbeVerification:
    gate_id: str
    source_digest: str
    required_tests: tuple[str, ...]
    executed_tests: tuple[str, ...]
    failures: tuple[tuple[str, str], ...]
    errors: tuple[tuple[str, str], ...]
    skips: tuple[tuple[str, str], ...]
    unexpected_successes: tuple[str, ...]
    expected_failures: tuple[tuple[str, str], ...]
    execution_archives: tuple[ExecutionArchive, ...] = ()

    @property
    def status(self):
        if self.failures or self.errors or self.unexpected_successes:
            return "FAIL"
        if (not self.required_tests or self.required_tests != self.executed_tests
                or self.skips or self.expected_failures):
            return "INCOMPLETE"
        return "PASS"


def _probe_suite(spec):
    _need(type(spec) is ProbeSpec and spec in PROBES, "Only the frozen probe catalog is allowed.")
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    names = []
    for name in spec.test_classes:
        module_name, cls_name = name.rsplit(".", 1)
        cls = getattr(importlib.import_module(module_name), cls_name)
        _need(isinstance(cls, type) and issubclass(cls, unittest.TestCase), "Missing registered test class.")
        methods = loader.getTestCaseNames(cls)
        _need(bool(methods), "A mandatory probe class contains no executable checks.")
        for method in methods:
            case = cls(method)
            names.append(case.id())
            suite.addTest(case)
    return suite, tuple(names)


def verify_probe(spec, source_identity):
    """Run registered unit/fault checks only; this does not issue an E0 verdict."""
    _need(type(source_identity) is SourceIdentity, "Probe needs exact source identity.")
    _need(capture_source_identity() == source_identity, "Source changed before verification.")
    suite, names = _probe_suite(spec)
    class Recorder(unittest.TestResult):
        def __init__(self):
            super().__init__()
            self.executed = []
            self.archives = []
            self.previous_profile = None
        def startTest(self, test):
            self.executed.append(test.id())
            self.previous_profile = sys.getprofile()
            if test.id() in (_ARCHIVE_CASE, _TREATMENT_ARCHIVE_CASE, _GUESS_ARCHIVE_CASE):
                def capture(frame, event, value):
                    if self.previous_profile is not None:
                        self.previous_profile(frame, event, value)
                    if event == "return":
                        for function, variant, cls in (
                            (_runner.run_control_capture, "CONTROL", _runner.ControlCaptureResult),
                            (_runner.run_k_control, "K-CONTROL", _runner.KControlRunResult),
                            (_runner.run_k_p0, "K-P0", _runner.KRunResult),
                        ):
                            if frame.f_code is function.__code__ and type(value) is cls:
                                self.archives.append(ExecutionArchive(test.id(), variant, value))
                sys.setprofile(capture)
            super().startTest(test)
        def stopTest(self, test):
            sys.setprofile(self.previous_profile)
            super().stopTest(test)
    result = Recorder()
    suite.run(result)
    _need(capture_source_identity() == source_identity, "Source changed during verification.")
    pairs = lambda items: tuple((test.id(), detail) for test, detail in items)
    return ProbeVerification(
        spec.gate_id, content_digest(source_identity), names, tuple(result.executed),
        pairs(result.failures), pairs(result.errors), pairs(result.skipped),
        tuple(t.id() for t in result.unexpectedSuccesses), pairs(result.expectedFailures),
        tuple(result.archives))



PINNED_MANIFEST_SHA256 = "a1f8e91dca6657c978810c99db2a65807e5d3f99305c581ec4e1423c3da6f4d3"


@dataclass(frozen=True)
class OperatingEnvelope:
    """Caller-declared containment, in integer milliseconds and bytes.

    No effectiveness threshold, substitute action, machine default or zero cap.
    The execution supervisor checks deadlines independently of worker progress.
    Shadow-only expiry remains the frozen runner's P-5 path.
    """
    runtime_identity: str
    machine_identity: str
    python_identity: str
    max_decision_wall_ms: int
    max_case_wall_ms: int
    max_job_wall_ms: int
    shadow_timeout_ms: int
    max_physical_inputs_per_case: int
    memory_cap_bytes: int
    archive_cap_bytes: int
    monitor_interval_ms: int
    monitoring_policy: str
    rationale: str

    def __post_init__(self):
        strings = {"runtime_identity", "machine_identity", "python_identity",
                   "monitoring_policy", "rationale"}
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in strings:
                _need(type(value) is str and bool(value.strip()), "Explicit " + field.name + " required.")
            else:
                _positive(value, field.name)
                _need(value <= sys.maxsize, field.name + " exceeds supported exact runtime units.")
        _need(self.monitor_interval_ms <= self.max_decision_wall_ms <= self.max_case_wall_ms
              <= self.max_job_wall_ms
              and self.shadow_timeout_ms <= min(60000, self.max_case_wall_ms),
              "Invalid operating-envelope duration relationships.")


def require_envelope(envelope):
    _need(type(envelope) is OperatingEnvelope, "An explicit operating envelope is mandatory.")
    return replace(envelope)


@dataclass(frozen=True)
class ResourceSample:
    case_elapsed_ns: int
    job_elapsed_ns: int
    decision_elapsed_ns: int
    physical_inputs: int
    memory_bytes: int
    archive_bytes: int
    shadow_elapsed_ns: int

    def __post_init__(self):
        _need(all(type(getattr(self, f.name)) is int and getattr(self, f.name) >= 0
                  for f in fields(self)), "Resource samples require nonnegative exact integers.")


def check_operating_limits(envelope, sample):
    env = require_envelope(envelope)
    _need(type(sample) is ResourceSample, "A typed monitoring sample is required.")
    sample = replace(sample)
    checks = (
        (sample.job_elapsed_ns >= env.max_job_wall_ms * 1000000, "SYSTEM_JOB_TIMEOUT"),
        (sample.case_elapsed_ns >= env.max_case_wall_ms * 1000000, "SYSTEM_CASE_TIMEOUT"),
        (sample.decision_elapsed_ns >= env.max_decision_wall_ms * 1000000, "SYSTEM_DECISION_TIMEOUT"),
        (sample.physical_inputs > env.max_physical_inputs_per_case, "SYSTEM_INPUT_CAP"),
        (sample.memory_bytes > env.memory_cap_bytes, "SYSTEM_MEMORY_CAP"),
        (sample.archive_bytes > env.archive_cap_bytes, "SYSTEM_ARCHIVE_CAP"),
        (sample.shadow_elapsed_ns >= env.shadow_timeout_ms * 1000000, "SHADOW_ONLY_TIMEOUT_P5"),
    )
    return next((name for failed, name in checks if failed), "WITHIN_ENVELOPE")


@dataclass(frozen=True)
class Preflight:
    status: str
    reasons: tuple[str, ...]
    p8_gate: P8Gate


def preflight_e0(*, envelope, source_identity, p8):
    """Refuse actual E0 before work if any prerequisite/monitor is unavailable."""
    import platform
    env = require_envelope(envelope)
    reasons = []
    if type(source_identity) is not SourceIdentity or source_identity != capture_source_identity():
        reasons.append("SOURCE_IDENTITY_MISMATCH")
    if content_digest(MANIFEST) != PINNED_MANIFEST_SHA256:
        reasons.append("MANIFEST_IDENTITY_MISMATCH")
    if (env.runtime_identity, env.machine_identity, env.python_identity) != (
            platform.platform(), platform.node(), sys.version):
        reasons.append("MACHINE_RUNTIME_IDENTITY_NOT_PINNED")
    if sys.platform != "win32" or env.monitoring_policy != "WINDOWS_JOB_MEMORY_AND_BOUNDARY_WATCHDOG_V1":
        reasons.append("ENFORCEABLE_MONITOR_UNAVAILABLE")
    if env.shadow_timeout_ms < 1000:
        reasons.append("FIXED_CATALOG_SHADOW_BOUND_EXCEEDS_ENVELOPE")
    gate = check_p8_gate(p8)
    if gate.status != "PASS":
        reasons.append(gate.classification)
    return Preflight("READY" if not reasons else "INCOMPLETE", tuple(reasons), gate)


def seal_execution_archive(archive, *, run_id):
    """Project archived K assertions, before the separate evaluator sees truth."""
    _need(type(archive) is ExecutionArchive and (
        (archive.variant == "K-P0" and type(archive.result) is _runner.KRunResult)
        or (archive.variant == "K-CONTROL" and type(archive.result) is _runner.KControlRunResult)),
        "Expected a sealed public K treatment or shadow execution archive.")
    result = archive.result
    _need(bool(result.traces) and all(t.public_effect is not None for t in result.traces),
          "Evaluator sealing needs complete actual effects.")
    effects = tuple(t.public_effect for t in result.traces)
    _need(_evidence.validate_public_effect_stream(effects, complete=True).status == "PASS",
          "Incomplete physical stream cannot be sealed as complete.")
    assertions = []
    for trace in result.traces:
        assertions.append(_evaluator.ArchivedAssertion("LOGICAL_M", trace.input_index, trace.preinput_M))
        if archive.variant == "K-CONTROL":
            # The shadow owns only its M assertions. V1's physical action is
            # never relabeled as a K-owned certainty selection.
            continue
        cell = (trace.move.x, trace.move.y)
        if trace.category in ("POLICY_INITIAL_OPEN", "EXACT_MINIMUM_RISK_GUESS"):
            assertions.append(_evaluator.ArchivedAssertion(trace.category, trace.input_index, (cell,)))
        elif trace.move.action is Action.OPEN:
            assertions.append(_evaluator.ArchivedAssertion("CERTAINTY_OPEN", trace.input_index, (cell,)))
        elif trace.move.action is Action.CHORD:
            effect = trace.public_effect
            opened = tuple((x, y) for y, row in enumerate(effect.before_observation)
                           for x, glyph in enumerate(row) if glyph == H
                           and (0 <= effect.after_observation.rows[y][x] <= 8
                                or effect.after_observation.rows[y][x] == CellState.EXPLODED))
            assertions.append(_evaluator.ArchivedAssertion("CERTAINTY_CHORD_OPENED",
                                                            trace.input_index, opened))
    first = effects[0].before_observation
    return _evaluator.SealedEvaluatorInput(archive.case_id + ":" + archive.variant, run_id, len(first[0]), len(first),
                                          tuple(assertions), content_digest(archive))


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    status: str
    details: tuple[str, ...] = ()

    def __post_init__(self):
        _need(type(self.gate_id) is str and bool(self.gate_id)
              and self.status in ("PASS", "FAIL", "INCOMPLETE")
              and type(self.details) is tuple and all(type(v) is str for v in self.details),
              "Invalid mandatory gate record.")


@dataclass(frozen=True)
class ExecutionVerification:
    archives: tuple[ExecutionArchive, ...]
    effect_checks: tuple
    o4_comparisons: tuple
    acquisition_audits: tuple
    timing_coverage: tuple
    discrepancies: tuple[str, ...]
    incomplete: tuple[str, ...]
    guess_comparisons: tuple[GuessComparison, ...] = ()

    @property
    def status(self):
        p3 = verify_retained_guess_comparisons(self)
        return ("FAIL" if self.discrepancies or p3.status == "FAIL" else
                "INCOMPLETE" if self.incomplete or p3.status == "INCOMPLETE" else "PASS")


def verify_retained_guess_comparisons(execution):
    """Require retained, reconstructable P-3 evidence without running inference."""
    try:
        _need(type(execution) is ExecutionVerification, "Missing execution evidence.")
        retained = execution.guess_comparisons
        _need(type(retained) is tuple and len(retained) == 1
              and type(retained[0]) is GuessComparison, "Missing/malformed mandatory P-3 comparison.")
        pair = tuple(a for a in execution.archives if a.case_id == _GUESS_ARCHIVE_CASE)
        _need(len(pair) == 2 and {a.variant for a in pair} == {"CONTROL", "K-P0"},
              "Missing fixed P-3 public archive pair.")
        control = next(a for a in pair if a.variant == "CONTROL")
        kp0 = next(a for a in pair if a.variant == "K-P0")
        expected = compare_guess_checkpoints(extract_guess_checkpoints(control, num_mines=_P3_NUM_MINES),
                                            extract_guess_checkpoints(kp0, num_mines=_P3_NUM_MINES))
        _need(expected.status != "INCOMPLETE", "P-3 public checkpoint evidence is unreconstructable.")
        _need(bool(expected.control.checkpoints) or bool(expected.kp0.checkpoints),
              "Fixed P-3 probe did not reach any uncertain-guess checkpoint.")
        stored = retained[0]
        _need(type(stored.control) is GuessCheckpointAudit and type(stored.kp0) is GuessCheckpointAudit,
              "Missing retained checkpoint projections.")
        checked = compare_guess_checkpoints(stored.control, stored.kp0)
        _need(checked.status != "INCOMPLETE", "Malformed retained checkpoint projections.")
        if canonical_bytes(stored) != canonical_bytes(expected):
            return GateResult("P-3-RETAINED", "FAIL", ("Retained P-3 evidence differs from its actual public archives.",))
        return GateResult("P-3-RETAINED", expected.status, expected.differences)
    except (ValueError, TypeError, AttributeError, IndexError, KeyError, StopIteration) as error:
        return GateResult("P-3-RETAINED", "INCOMPLETE", (str(error),))


def verify_execution_archives(archives):
    """Reconstruct real effects, O-4 and K public facts without hidden answers."""
    failures, missing, effects_checks, o4, audits, timing = [], [], [], [], [], []
    _need(type(archives) is tuple and all(type(a) is ExecutionArchive for a in archives),
          "Expected immutable public execution archives.")
    expected_keys = ((_ARCHIVE_CASE, "CONTROL"), (_ARCHIVE_CASE, "K-CONTROL"),
                     (_TREATMENT_ARCHIVE_CASE, "K-P0"), (_TREATMENT_ARCHIVE_CASE, "K-CONTROL"),
                     (_GUESS_ARCHIVE_CASE, "CONTROL"), (_GUESS_ARCHIVE_CASE, "K-P0"))
    keys = tuple((a.case_id, a.variant) for a in archives)
    if len(set(keys)) != len(keys) or any(k not in expected_keys for k in keys):
        failures.append("Unknown/duplicate registered execution archive.")
    if set(keys) != set(expected_keys):
        missing.append("Missing mandatory execution capture.")
    by_key = {(a.case_id, a.variant): a for a in archives}
    for archive in archives:
        result = archive.result
        cls = {"CONTROL": _runner.ControlCaptureResult, "K-CONTROL": _runner.KControlRunResult,
               "K-P0": _runner.KRunResult}.get(archive.variant)
        if cls is None or type(result) is not cls or not result.traces:
            missing.append("Invalid/empty " + archive.variant + " archive.")
            continue
        effects = result.effects if archive.variant == "CONTROL" else tuple(t.public_effect for t in result.traces)
        if (type(effects) is not tuple or len(effects) != len(result.traces)
                or any(e is None for e in effects)):
            missing.append("Mandatory physical effect record is absent.")
            continue
        if archive.variant == "CONTROL" and len(result.timings) != len(result.traces):
            missing.append("Mandatory timing record is absent.")
            continue
        check = _evidence.validate_public_effect_stream(effects, complete=True)
        effects_checks.append(check)
        if check.status != "PASS":
            (failures if check.status == "FAIL" else missing).append("Incomplete/corrupt public effects.")
            continue
        proofs, previous_m, executed_flags = (), frozenset(), ()
        session = None
        for index, trace in enumerate(result.traces):
            effect = effects[index]
            table = load_timing_table()
            if (trace.move.action, trace.move.x, trace.move.y) != (
                    effect.move.action, effect.move.x, effect.move.y):
                failures.append("Trace/effect action binding differs.")
            if (trace.cursor_before != effect.cursor_before
                    or trace.modeled_action_us != effect.modeled_action_us
                    or trace.status_after != effect.status_after
                    or effect.modeled_action_us != table[abs(effect.move.x-effect.cursor_before[0])][
                        abs(effect.move.y-effect.cursor_before[1])]):
                failures.append("Trace/effect cost/cursor/status binding differs.")
            span = result.timings[index] if archive.variant == "CONTROL" else trace.timings
            if span is None:
                missing.append("Mandatory timing span is absent.")
                continue
            _evidence.DecisionTimings(**{f.name: getattr(span, f.name) for f in fields(span)})
            timing.append((archive.case_id, archive.variant, index, span))
            if archive.variant == "CONTROL":
                if span.v1_plan_position_ns != trace.decision_compute_ns:
                    failures.append("CONTROL planner-only timing identity differs.")
                if index and span.v1_plan_position_ns is None:
                    missing.append("CONTROL planner timing unmeasured.")
                continue
            if trace.public_effect_status != "CAPTURED":
                failures.append("Required public effects are not marked captured.")
            if trace.input_index != index or trace.M_before != previous_m or not trace.M_before <= trace.preinput_M:
                failures.append("M lifecycle/input boundary does not reconstruct.")
            previous_m = trace.preinput_M
            if archive.variant == "K-P0":
                if span.k_execution_validation_ns is None or (index and span.k_analysis_planning_ns is None):
                    missing.append("K-P0 required comparable timing span missing.")
                decision = None if trace.selection is None else trace.selection.evidence
                if index:
                    if decision is None or decision.observation != effect.before_observation:
                        failures.append("K decision not bound to its public preinput.")
                        continue
                    if trace.category != trace.selection.category:
                        failures.append("Policy category was relabeled after selection.")
                    _runner.validate_k_p0_execution(
                        effect.before_observation, trace.move, status=GameStatus.PLAYING,
                        num_mines=decision.num_mines, cursor=trace.cursor_before,
                        current_mines=trace.preinput_M, decision=decision, selection=trace.selection)
                elif trace.category != "POLICY_INITIAL_OPEN" or trace.selection is not None or trace.preinput_M:
                    failures.append("Canonical initial input mislabeled as inference.")
                external = ()
            else:
                if index and span.v1_plan_position_ns is None:
                    missing.append("K-CONTROL planner-only span missing.")
                decision = trace.shadow.decision
                external = trace.external_flag_antecedents
                if external != executed_flags:
                    failures.append("External FLAG antecedents differ from the executed public prefix.")
                if trace.move.action is Action.FLAG:
                    flag = trace.external_flag
                    if (flag is None or flag.observation != effect.before_observation
                            or flag.move != _evidence.MoveProjection(trace.move.action, trace.move.x, trace.move.y)
                            or flag.input_index != index or flag.prior_flags != executed_flags):
                        failures.append("Executed V1 FLAG lacks its exact public provenance.")
                    else:
                        verified = _evidence.verify_v1_flag_provenance(flag)
                        if verified.status != "PASS":
                            (failures if verified.status == "FAIL" else missing).append(
                                "Executed V1 FLAG provenance: " + verified.status)
                        executed_flags += (flag,)
                elif trace.external_flag is not None:
                    failures.append("Non-FLAG input has a FLAG provenance record.")
                if index and trace.shadow.failure is None and (
                        decision is None or not trace.shadow.enabled or not trace.shadow.evidence_valid
                        or trace.shadow.last_valid_boundary != index
                        or trace.shadow.last_valid_M != trace.preinput_M):
                    missing.append("Healthy shadow lacks its current decision/checkpoint evidence.")
                if trace.shadow.failure is not None:
                    (missing if trace.shadow.failure.failure_class == "SHADOW_TIMEOUT" else failures).append(
                        "Natural shadow stream invalidated: " + trace.shadow.failure.failure_class)
                if index and trace.decision is None:
                    missing.append("Missing noninitial V1 decision.")
            if decision is not None:
                if session is None:
                    session = _capability.KLocalSession(len(effect.before_observation[0]),
                        len(effect.before_observation), decision.num_mines)
                admission = None
                if archive.variant == "K-CONTROL":
                    admission = _capability.CurrentPhysicalFlagAdmission(
                        effect.before_observation, frozenset((f.move.x, f.move.y) for f in external))
                replay = session.analyze_decision(effect.before_observation, status=GameStatus.PLAYING,
                                                 physical_flag_admission=admission)
                if canonical_bytes(replay) != canonical_bytes(decision):
                    failures.append("K phase/certificate evidence differs from its public-prefix replay.")
                if archive.variant == "K-P0" and canonical_bytes(
                        _policy.select_policy(replay, trace.cursor_before, table)) != canonical_bytes(trace.selection):
                    failures.append("K policy/route evidence differs from its frozen public replay.")
                if decision.after.M != trace.preinput_M or decision.local.before.M != trace.M_before:
                    failures.append("K phase snapshots differ from the action archive.")
                for certificate in decision.local.certificates + decision.exact_certificates:
                    audit = audit_acquisition(certificate, boundary=index, prior_certificates=proofs,
                                                external_flags=external)
                    audits.append(audit)
                    if audit.status != "PASS":
                        (failures if audit.status == "FAIL" else missing).append(audit.detail)
                    proofs += (certificate,)
            if index == len(result.traces)-1 and result.final_M != trace.preinput_M:
                failures.append("Terminal archive repaired or extended M.")
        if result.status != effects[-1].status_after:
            failures.append("Run outcome differs from the final public effect.")
    control = by_key.get((_ARCHIVE_CASE, "CONTROL"))
    shadow = by_key.get((_ARCHIVE_CASE, "K-CONTROL"))
    if control is not None and shadow is not None:
        left, right = control.result, shadow.result
        if len(left.traces) != len(right.traces):
            failures.append("CONTROL/K-CONTROL streams differ in length.")
        for index, (a, b) in enumerate(zip(left.traces, right.traces)):
            if index >= len(left.effects) or left.effects[index] is None or b.public_effect is None:
                missing.append("CONTROL/K-CONTROL effect comparison lacks a mandatory record.")
                continue
            comparison = _evidence.compare_public_effects(left.effects[index], b.public_effect)
            effects_checks.append(comparison)
            if comparison.status != "PASS":
                (failures if comparison.status == "FAIL" else missing).append("CONTROL/K-CONTROL public effects differ.")
            if index:
                comparison = _evidence.compare_v1_decisions(a.decision, b.decision, boundary=index)
                o4.append(comparison)
                if comparison.status != "PASS":
                    (failures if comparison.status == "FAIL" else missing).append("O-4 comparison failed/incomplete.")
        if left.status != right.status or left.moves != right.moves or left.total_modeled_us != right.total_modeled_us:
            failures.append("Frozen V1 physical stream authority differs.")
    control = by_key.get((_GUESS_ARCHIVE_CASE, "CONTROL"))
    kp0 = by_key.get((_GUESS_ARCHIVE_CASE, "K-P0"))
    guesses = compare_guess_checkpoints(
        None if control is None else extract_guess_checkpoints(control, num_mines=_P3_NUM_MINES),
        None if kp0 is None else extract_guess_checkpoints(kp0, num_mines=_P3_NUM_MINES))
    return ExecutionVerification(archives, tuple(effects_checks), tuple(o4), tuple(audits),
                                 tuple(timing), tuple(failures), tuple(missing), (guesses,))


@dataclass(frozen=True)
class QualificationRecord:
    run_id: str
    purpose: str
    authorization_reference: str | None
    source_identity: SourceIdentity
    operating_envelope: OperatingEnvelope
    manifest_id: str
    manifest_digest: str
    manifest: tuple[Fixture, ...]
    fixture_results: tuple[FixtureVerification, ...]
    probe_results: tuple[ProbeVerification, ...]
    execution_evidence: ExecutionVerification
    evaluator_findings: tuple[_evaluator.FalsificationResult, ...]
    p8_reference: _oracles.P8Result | None
    interruptions: tuple[str, ...]
    diagnosed_implementation_defects: tuple[str, ...]
    operational_receipts: tuple = ()

    def __post_init__(self):
        _need(type(self.run_id) is str and re.fullmatch("[A-Za-z0-9][A-Za-z0-9_-]{0,79}", self.run_id),
              "Run identity must be a safe single path component.")
        _need(self.purpose in ("IMPLEMENTATION_UNIT_READINESS", "E0_QUALIFICATION"),
              "No E1/later dispatch exists in this harness.")
        _need(self.authorization_reference is None or (
            type(self.authorization_reference) is str and bool(self.authorization_reference.strip())),
              "Malformed authorization reference.")
        require_envelope(self.operating_envelope)
        _need(type(self.source_identity) is SourceIdentity, "Missing source identity.")
        for name, cls in (("manifest", Fixture), ("fixture_results", FixtureVerification),
                          ("probe_results", ProbeVerification), ("evaluator_findings", _evaluator.FalsificationResult)):
            value = getattr(self, name)
            _need(type(value) is tuple and all(type(item) is cls for item in value), "Malformed " + name)
        _need(type(self.execution_evidence) is ExecutionVerification, "Missing reconstructable execution evidence.")
        _need(self.p8_reference is None or type(self.p8_reference) is _oracles.P8Result, "Malformed P-8 reference.")
        for value in (self.interruptions, self.diagnosed_implementation_defects):
            _need(type(value) is tuple and all(type(v) is str and bool(v) for v in value),
                  "Failure/incomplete diagnosis must be explicit immutable text.")
        _sha(self.manifest_digest)
        _need(type(self.operational_receipts) is tuple
              and all(type(r) is OperationReceipt for r in self.operational_receipts),
              "Operational receipts must be immutable typed monitoring evidence.")


@dataclass(frozen=True)
class QualificationAssessment:
    verdict: str
    readiness: str
    gates: tuple[GateResult, ...]
    p8_gate: P8Gate

    @property
    def progression_allowed(self):
        return self.verdict == "E0_PASS"



def verify_operational_receipts(record):
    """Bind monitored work to the fixed roster and retained evidence, not labels."""
    env = require_envelope(record.operating_envelope)
    expected = (tuple(("FIXTURE", f.fixture_id) for f in MANIFEST)
                + tuple(("PROBE", p.gate_id) for p in PROBES)
                + (("AUDIT", "PUBLIC_EXECUTION_ARCHIVES"),))
    receipts = record.operational_receipts
    actual = tuple((r.kind, r.operation_id) for r in receipts)
    if actual != expected:
        return GateResult("OPERATING-EXECUTION", "INCOMPLETE"
            if actual == expected[:len(actual)] else "FAIL",
            ("Missing, interrupted, duplicate or out-of-order monitored work.",))
    results = {("FIXTURE", r.fixture.fixture_id): r for r in record.fixture_results}
    results.update({("PROBE", r.gate_id): r for r in record.probe_results})
    results[("AUDIT", "PUBLIC_EXECUTION_ARCHIVES")] = record.execution_evidence
    elapsed, storage = 0, 0
    for receipt in receipts:
        replace(receipt)
        if receipt.source_digest != content_digest(record.source_identity) or receipt.envelope_digest != content_digest(env):
            return GateResult("OPERATING-EXECUTION", "FAIL", ("Receipt source/envelope identity differs.",))
        if receipt.status != "COMPLETE":
            return GateResult("OPERATING-EXECUTION", "INCOMPLETE", (receipt.reason,))
        payload = results.get((receipt.kind, receipt.operation_id))
        if payload is None:
            return GateResult("OPERATING-EXECUTION", "INCOMPLETE", ("Receipt has no retained result.",))
        raw = canonical_bytes(payload)
        if content_digest(payload) != receipt.result_digest or len(raw) != receipt.result_size_bytes:
            return GateResult("OPERATING-EXECUTION", "FAIL", ("Receipt/result integrity differs.",))
        inputs, active, finished = 0, None, False
        for event in receipt.events:
            if finished or event.elapsed_ns > receipt.elapsed_ns:
                return GateResult("OPERATING-EXECUTION", "FAIL", ("Event occurs after worker completion.",))
            if event.event == "STARTED" and event.sequence != 0:
                return GateResult("OPERATING-EXECUTION", "FAIL", ("Duplicate operation start.",))
            if event.event == "DECISION_START":
                if active is not None:
                    return GateResult("OPERATING-EXECUTION", "FAIL", ("Overlapping decision evidence.",))
                active = event.elapsed_ns
            elif event.event == "DECISION_END":
                if active is None:
                    return GateResult("OPERATING-EXECUTION", "FAIL", ("Missing decision-start evidence.",))
                if event.elapsed_ns-active >= env.max_decision_wall_ms*1000000:
                    return GateResult("OPERATING-EXECUTION", "INCOMPLETE", ("Decision exceeded declared limit.",))
                active = None
            elif event.event == "BEFORE_INPUT":
                inputs += 1
            elif event.event == "FINISHED":
                finished = True
            elif event.event == "WORKER_ABORT":
                return GateResult("OPERATING-EXECUTION", "INCOMPLETE", ("Worker aborted its physical stream.",))
            if event.physical_inputs != inputs:
                return GateResult("OPERATING-EXECUTION", "FAIL", ("Physical-input admissions do not reconstruct.",))
        if active is not None or receipt.physical_inputs != inputs:
            return GateResult("OPERATING-EXECUTION", "FAIL", ("Incomplete decision/input accounting.",))
        elapsed += receipt.elapsed_ns
        storage += len(raw) + len(canonical_bytes(receipt))
        if (receipt.elapsed_ns >= env.max_case_wall_ms*1000000
                or elapsed >= env.max_job_wall_ms*1000000
                or inputs > env.max_physical_inputs_per_case
                or storage > env.archive_cap_bytes):
            return GateResult("OPERATING-EXECUTION", "INCOMPLETE", ("Operational containment exceeded.",))
    return GateResult("OPERATING-EXECUTION", "PASS",
        ("Fixed dispatch/result/monitor receipts reconstruct; actual P-8 and evaluator gates remain separate.",))


def _readiness_for_verdict(verdict, *, purpose, nonexecution_complete):
    """Map an already determined verdict to its distinct readiness label.

    This pure label mapping does not qualify evidence or authorize execution.
    READY_EXCEPT_EXECUTION belongs only to clean implementation unit readiness.
    """
    _need(verdict in ("IMPLEMENTATION_IDENTITY_FAIL", "PROGRAM_K_RESEARCH_FAIL",
                      "INCOMPLETE", "E0_PASS"), "Unknown qualification verdict.")
    _need(purpose in ("IMPLEMENTATION_UNIT_READINESS", "E0_QUALIFICATION")
          and type(nonexecution_complete) is bool, "Malformed readiness context.")
    if verdict == "E0_PASS":
        return "E0_QUALIFIED"
    if (verdict == "INCOMPLETE" and purpose == "IMPLEMENTATION_UNIT_READINESS"
            and nonexecution_complete):
        return "READY_EXCEPT_EXECUTION"
    return "NEEDS_CORRECTION"


def assess_qualification(record):
    """Reconstruct mandatory coverage; no caller-supplied PASS flag is trusted."""
    _need(type(record) is QualificationRecord, "Expected a sealed qualification record.")
    record = reconstruct(canonical_bytes(record))
    gates = []
    def gate(name, status, *details):
        gates.append(GateResult(name, status, tuple(details)))
    source_ok = record.source_identity == capture_source_identity()
    gate("SOURCE/PROTOCOL", "PASS" if source_ok else "FAIL", "Live source/config/authority identity binding.")
    manifest_ok = (record.manifest == MANIFEST and record.manifest_id == MANIFEST_ID
                   and record.manifest_digest == content_digest(record.manifest) == PINNED_MANIFEST_SHA256)
    gate("A-E4-MANIFEST", "PASS" if manifest_ok else "FAIL", "Independent source-pinned preregistration.")
    fixture_ids = tuple(r.fixture.fixture_id for r in record.fixture_results)
    if fixture_ids != REQUIRED_FIXTURE_IDS:
        gate("A-E4-COVERAGE", "INCOMPLETE" if len(set(fixture_ids)) == len(fixture_ids)
             and set(fixture_ids) <= set(REQUIRED_FIXTURE_IDS) else "FAIL", "Missing/duplicate/unknown fixtures.")
    else:
        for result in record.fixture_results:
            registered = next(f for f in MANIFEST if f.fixture_id == result.fixture.fixture_id)
            if result.fixture != registered:
                gate("FIXTURE:"+result.fixture.fixture_id, "FAIL", "Fixture differs from the pinned manifest.")
                continue
            if type(result.phases) is not tuple or any(type(p) is not PhaseVerification for p in result.phases) or tuple(p.expectation for p in result.phases) != result.fixture.expectations:
                gate("FIXTURE:"+result.fixture.fixture_id, "INCOMPLETE", "Missing mandatory phase coverage.")
                continue
            # Independent count/certificate replay from retained PUBLIC premises
            # also detects corrupt K, oracle, partition or audit records.
            try:
                # Research results were already produced/replayed in the
                # supervised fixed workers. Their mandatory receipt digests
                # bind every field below; never run new solver work outside
                # the declared execution envelope while assessing a record.
                replay = verify_fixture(result.fixture) if record.purpose == "IMPLEMENTATION_UNIT_READINESS" else result
                good = canonical_bytes(replay) == canonical_bytes(result) and result.status == "PASS"
                gate("FIXTURE:"+result.fixture.fixture_id, "PASS" if good else "FAIL")
            except (ValueError, TypeError, AttributeError) as error:
                gate("FIXTURE:"+result.fixture.fixture_id, "FAIL", str(error))
    expected_probe_ids = tuple(p.gate_id for p in PROBES)
    actual_ids = tuple(p.gate_id for p in record.probe_results)
    if actual_ids != expected_probe_ids:
        gate("MANDATORY-PROBES", "INCOMPLETE" if len(set(actual_ids)) == len(actual_ids)
             and set(actual_ids) <= set(expected_probe_ids) else "FAIL", "Missing/duplicate/unknown probes.")
    for probe in record.probe_results:
        spec = next((p for p in PROBES if p.gate_id == probe.gate_id), None)
        if spec is None:
            continue
        _, tests = _probe_suite(spec)
        if probe.source_digest != content_digest(record.source_identity):
            gate(probe.gate_id, "FAIL", "Probe source digest differs.")
        elif probe.required_tests != tests:
            gate(probe.gate_id, "INCOMPLETE", "A passing subset cannot replace the registered test roster.")
        else:
            gate(probe.gate_id, probe.status)
    try:
        archives = tuple(a for p in record.probe_results for a in p.execution_archives)
        execution = (verify_execution_archives(archives)
                     if record.purpose == "IMPLEMENTATION_UNIT_READINESS" else record.execution_evidence)
        if (canonical_bytes(execution) != canonical_bytes(record.execution_evidence)
                or canonical_bytes(execution.archives) != canonical_bytes(archives)):
            gate("EXECUTION-RECONSTRUCTION", "FAIL", "Archived effects/O-4/timing/audits were altered or omitted.")
        else:
            gate("EXECUTION-RECONSTRUCTION", execution.status,
                 *(execution.discrepancies + execution.incomplete))
    except (ValueError, TypeError, AttributeError) as error:
        gate("EXECUTION-RECONSTRUCTION", "FAIL", str(error))
        archives = ()
    gates.append(verify_retained_guess_comparisons(record.execution_evidence))
    treatment_archives = tuple(a for a in archives if a.variant in ("K-P0", "K-CONTROL"))
    try:
        expected_seals = tuple(seal_execution_archive(a, run_id=record.run_id) for a in treatment_archives)
    except (ValueError, TypeError, AttributeError, IndexError) as error:
        expected_seals = ()
        gate("EVALUATOR-ARCHIVE-INCOMPLETE", "INCOMPLETE", str(error))
    supplied = tuple(f.sealed_input for f in record.evaluator_findings)
    if not expected_seals or supplied != expected_seals:
        gate("EVALUATOR-SEALED-COVERAGE", "INCOMPLETE", "Missing or unbound post-hoc findings.")
    elif any(f.classification == "G1_FALSIFICATION" for f in record.evaluator_findings):
        gate("EVALUATOR-FALSIFICATION", "FAIL", "G1 FAIL; progression stopped pending diagnosis, no repair.")
    elif any(f.classification == "NOT_EVALUATED" for f in record.evaluator_findings):
        gate("EVALUATOR-SEALED-COVERAGE", "INCOMPLETE", "No certainty coordinates were actually compared.")
    else:
        gate("EVALUATOR-SEALED-COVERAGE", "PASS", "No counterexample only; public-proof gates remain separate.")
    if record.interruptions:
        gate("OPERATION", "INCOMPLETE", *record.interruptions)
    if record.diagnosed_implementation_defects:
        gate("DIAGNOSIS", "FAIL", *record.diagnosed_implementation_defects)
    if record.purpose == "E0_QUALIFICATION":
        gates.append(verify_operational_receipts(record))
        if record.authorization_reference is None:
            gate("EXECUTION-AUTHORIZATION", "INCOMPLETE", "Actual E0 requires separate explicit authorization.")
        preflight = preflight_e0(envelope=record.operating_envelope,
                                 source_identity=record.source_identity, p8=record.p8_reference)
        # Missing P-8 is classified separately below.
        non_p8 = tuple(r for r in preflight.reasons if r != preflight.p8_gate.classification)
        if non_p8:
            gate("OPERATING-PREFLIGHT", "INCOMPLETE", *non_p8)
    p8 = check_p8_gate(record.p8_reference)
    any_fail = any(g.status == "FAIL" and g.gate_id != "EVALUATOR-FALSIFICATION" for g in gates) or p8.classification == "IMPLEMENTATION_IDENTITY_FAIL"
    incomplete = any(g.status == "INCOMPLETE" or g.gate_id == "EVALUATOR-FALSIFICATION" for g in gates)
    if any_fail:
        verdict = "IMPLEMENTATION_IDENTITY_FAIL"
    elif p8.classification == "PROGRAM_K_RESEARCH_FAIL":
        verdict = "PROGRAM_K_RESEARCH_FAIL"
    elif (incomplete or p8.status != "PASS" or record.purpose != "E0_QUALIFICATION"
          or record.authorization_reference is None):
        verdict = "INCOMPLETE"
    else:
        verdict = "E0_PASS"
    readiness = _readiness_for_verdict(verdict, purpose=record.purpose,
                                      nonexecution_complete=not any_fail and not incomplete)
    gate("P-8", p8.status, p8.reason)
    return QualificationAssessment(verdict, readiness, tuple(gates), p8)


def collect_unit_readiness(*, run_id, envelope):
    """Implementation/unit integration only. No research E0 or P-8 execution.

    Post-hoc evaluator findings are attached separately after this public bundle
    is sealed. This function never receives an answer and never selects cases
    using evaluator output. Actual E0 uses the supervised entry point below.
    """
    env = require_envelope(envelope)
    identity = capture_source_identity()
    fixtures = tuple(verify_fixture(f) for f in MANIFEST)
    probes = tuple(verify_probe(p, identity) for p in PROBES)
    execution = verify_execution_archives(tuple(a for p in probes for a in p.execution_archives))
    return QualificationRecord(
        run_id, "IMPLEMENTATION_UNIT_READINESS", None, identity, env, MANIFEST_ID,
        PINNED_MANIFEST_SHA256, MANIFEST, fixtures, probes, execution, (), None, (), ())


@dataclass(frozen=True)
class ArtifactReceipt:
    run_id: str
    content_sha256: str
    size_bytes: int
    source_digest: str
    config_digest: str
    protocol_sha256: str
    verdict: str
    completion_marker: str = "COMPLETE"

    def __post_init__(self):
        for digest in (self.content_sha256, self.source_digest, self.config_digest, self.protocol_sha256):
            _sha(digest)
        _positive(self.size_bytes, "artifact size")
        _need(self.completion_marker == "COMPLETE", "Missing completed-write marker.")


def persist_qualification(record, *, repository_root=None):
    """Publish once under results/program_k_research/<run-id>/ only.

    COMPLETE marks complete artifact publication, including FAIL/INCOMPLETE
    qualification attempts; it never substitutes for the assessment verdict.
    An interrupted write remains visible and is never overwritten or repaired.
    repository_root is the private temporary-root seam used by unit tests.
    """
    assessment = assess_qualification(record)
    data = canonical_bytes(record)
    receipt = ArtifactReceipt(record.run_id, hashlib.sha256(data).hexdigest(), len(data),
                              content_digest(record.source_identity),
                              content_digest(record.operating_envelope),
                              record.source_identity.protocol_sha256, assessment.verdict)
    encoded_receipt = canonical_bytes(receipt)
    _need(len(data) + len(encoded_receipt) <= record.operating_envelope.archive_cap_bytes,
          "Declared archive cap would be exceeded; do not write a partial replacement.")
    root = Path(__file__).resolve().parents[1] if repository_root is None else Path(repository_root).resolve()
    destination = root / "results" / "program_k_research" / record.run_id
    _need(destination.resolve().is_relative_to(root / "results" / "program_k_research"),
          "Artifact destination escapes the authorized research subtree.")
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "qualification.json").open("xb") as stream:
        stream.write(data)
    with (destination / "COMPLETE.json").open("xb") as stream:
        stream.write(encoded_receipt)
    return receipt


def read_qualification_artifact(directory):
    directory = Path(directory)
    receipt = reconstruct((directory / "COMPLETE.json").read_bytes())
    _need(type(receipt) is ArtifactReceipt, "Invalid completion marker.")
    data = (directory / "qualification.json").read_bytes()
    _need(len(data) == receipt.size_bytes, "Artifact size mismatch.")
    record = reconstruct(data, expected_digest=receipt.content_sha256)
    _need(type(record) is QualificationRecord and directory.name == record.run_id == receipt.run_id,
          "Artifact run identity mismatch.")
    assessment = assess_qualification(record)
    _need(receipt.source_digest == content_digest(record.source_identity)
          and receipt.config_digest == content_digest(record.operating_envelope)
          and receipt.protocol_sha256 == record.source_identity.protocol_sha256
          and receipt.verdict == assessment.verdict, "Artifact identity/verdict does not reconstruct.")
    return record, receipt, assessment


# Actual E0 remains separately authorized. Nothing below executes on import or
# in the Slice-7 tests. Each source-registered operation owns a disposable
# process; the parent, not a solver timeout, decides operational containment.
OPERATIONAL_MONITOR_ID = "WINDOWS_JOB_MEMORY_AND_BOUNDARY_WATCHDOG_V1"


@dataclass(frozen=True)
class OperationalEvent:
    sequence: int
    event: str
    elapsed_ns: int
    physical_inputs: int

    def __post_init__(self):
        _need(self.event in ("STARTED", "DECISION_START", "DECISION_END",
                            "BEFORE_INPUT", "FINISHED", "WORKER_ABORT"),
              "Unknown operational event.")
        _need(all(type(n) is int and n >= 0 for n in
                  (self.sequence, self.elapsed_ns, self.physical_inputs)),
              "Operational event counters must be nonnegative true integers.")


@dataclass(frozen=True)
class OperationReceipt:
    kind: str
    operation_id: str
    source_digest: str
    envelope_digest: str
    status: str
    reason: str | None
    events: tuple[OperationalEvent, ...]
    elapsed_ns: int
    physical_inputs: int
    result_digest: str | None
    result_size_bytes: int
    exit_code: int | None
    monitor_identity: str = OPERATIONAL_MONITOR_ID

    def __post_init__(self):
        registered = (REQUIRED_FIXTURE_IDS if self.kind == "FIXTURE"
                      else tuple(p.gate_id for p in PROBES) if self.kind == "PROBE"
                      else ("PUBLIC_EXECUTION_ARCHIVES",) if self.kind == "AUDIT" else ())
        _need(self.operation_id in registered, "Only the fixed E0 operation catalog is allowed.")
        _sha(self.source_digest)
        _sha(self.envelope_digest)
        _need(self.monitor_identity == OPERATIONAL_MONITOR_ID, "Unknown enforcement identity.")
        _need(self.status in ("COMPLETE", "INCOMPLETE")
              and (self.reason is None if self.status == "COMPLETE"
                   else type(self.reason) is str and bool(self.reason)),
              "Operational completion/abort reason is inconsistent.")
        _need(type(self.events) is tuple and all(type(e) is OperationalEvent for e in self.events)
              and tuple(e.sequence for e in self.events) == tuple(range(len(self.events)))
              and all(a.elapsed_ns <= b.elapsed_ns for a, b in zip(self.events, self.events[1:])),
              "Operational events must preserve their exact chronological sequence.")
        _need(all(type(n) is int and n >= 0 for n in
                  (self.elapsed_ns, self.physical_inputs, self.result_size_bytes))
              and (self.exit_code is None or type(self.exit_code) is int),
              "Invalid exact operational counters.")
        previous_inputs = 0
        for event in self.events:
            replace(event)
            _need(event.physical_inputs == previous_inputs + (event.event == "BEFORE_INPUT"),
                  "Physical admissions do not reconstruct from ordered events.")
            previous_inputs = event.physical_inputs
        _need(previous_inputs == self.physical_inputs
              and (not self.events or self.events[-1].elapsed_ns <= self.elapsed_ns),
              "Final operational counters differ from their event stream.")
        if self.result_digest is not None:
            _sha(self.result_digest)
        _need(self.status != "COMPLETE" or (
            self.exit_code == 0 and self.result_digest is not None and self.result_size_bytes > 0
            and self.events and self.events[0].event == "STARTED"
            and self.events[-1].event == "FINISHED"), "Incomplete worker cannot claim completion.")


def _attach_memory_job(pid, memory_cap_bytes):
    """Enforce aggregate worker-tree memory and kill-on-close using Windows API."""
    import ctypes
    from ctypes import wintypes
    class Basic(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                    ("flags", wintypes.DWORD), ("minimum_ws", ctypes.c_size_t),
                    ("maximum_ws", ctypes.c_size_t), ("active", wintypes.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                    ("scheduling", wintypes.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
    class Extended(ctypes.Structure):
        _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                    ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                    ("peak_job", ctypes.c_size_t)]
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
        "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                     wintypes.DWORD], wintypes.BOOL),
        "QueryInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                        wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
        "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
        "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (arguments, returns) in signatures.items():
        getattr(api, name).argtypes, getattr(api, name).restype = arguments, returns
    job = api.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = Extended()
        limits.basic.flags = 0x200 | 0x2000  # JOB_MEMORY | KILL_ON_JOB_CLOSE
        limits.job_memory = memory_cap_bytes
        if not api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        process = api.OpenProcess(0x100 | 0x1, False, pid)  # SET_QUOTA | TERMINATE
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not api.AssignProcessToJobObject(job, process):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            api.CloseHandle(process)
        def peak_memory():
            current = Extended()
            if not api.QueryInformationJobObject(job, 9, ctypes.byref(current),
                                                 ctypes.sizeof(current), None):
                raise ctypes.WinError(ctypes.get_last_error())
            return current.peak_job
        return api, job, peak_memory
    except BaseException:
        api.CloseHandle(job)
        raise


def _coordinator_private_bytes():
    """Current private committed memory; no machine-wide memory claim is made."""
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "peak_ws", "ws", "peak_paged", "paged", "peak_nonpaged", "nonpaged",
                "pagefile", "peak_pagefile", "private")]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = Counters()
    counters.size = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.size):
        raise ctypes.WinError(ctypes.get_last_error())
    return counters.private


def _fixed_e0_worker(kind, operation_id, identity_bytes, envelope_bytes, archive_bytes, connection, barrier):
    """Fixed catalog, detached public inputs, no answer or arbitrary callback.

    sys.settrace observes entry before a physical input; it is separate from the
    existing tests' sys.setprofile timing instrumentation. Nested port/Engine
    calls count once. Physical admissions are conservative across an entire
    registered probe group, including its deliberate fault cases.
    """
    import threading
    barrier.wait()  # Parent installs OS memory containment before any work.
    envelope = reconstruct(envelope_bytes)
    connection_lock = threading.Lock()
    def emit(event, payload=None):
        encoded = canonical_bytes((event, payload))
        if len(encoded) > envelope.archive_cap_bytes:
            raise MemoryError("Evidence payload exceeds declared storage cap.")
        with connection_lock:
            connection.send_bytes(encoded)
            if connection.recv_bytes(16) != b"CONTINUE":
                raise RuntimeError("Supervisor did not permit continuation.")
    previous_trace = sys.gettrace()
    previous_thread_trace = threading.gettrace()
    monitor_active = True
    try:
        identity = reconstruct(identity_bytes)
        _need(capture_source_identity() == identity, "Source changed before worker execution.")
        from core_engine import MinesweeperEngine
        physical_codes = {_runner._PublicEnginePort.apply.__code__, MinesweeperEngine.step.__code__}
        analysis_code = _capability.KLocalSession.analyze_decision.__code__
        policy_code, runner_code = _policy.select_policy.__code__, _runner.run_k_p0.__code__
        decision_codes = {analysis_code, policy_code, _runner.plan_position.__code__}
        thread_state = threading.local()
        def trace(frame, event, value):
            if not monitor_active:
                return None
            if not hasattr(thread_state, "physical_frames"):
                thread_state.physical_frames, thread_state.decision_frames = set(), set()
                thread_state.combined_runner = None
            physical_frames, decision_frames = thread_state.physical_frames, thread_state.decision_frames
            if event == "call" and frame.f_code in physical_codes:
                if not physical_frames:
                    emit("BEFORE_INPUT")  # Wait for acknowledgment BEFORE Engine/port input.
                physical_frames.add(id(frame))
            elif event == "return" and id(frame) in physical_frames:
                physical_frames.remove(id(frame))
            # P-5 already owns shadow-only timeouts. Its detached inference is
            # not a physical decision span; physical inputs remain monitored.
            if threading.current_thread().name == "program-k-shadow":
                return trace
            if event == "call" and frame.f_code in decision_codes:
                if not decision_frames and thread_state.combined_runner is None:
                    emit("DECISION_START")
                decision_frames.add(id(frame))
                if frame.f_code is analysis_code and frame.f_back.f_code is runner_code:
                    thread_state.combined_runner = id(frame.f_back)
            elif event == "return" and id(frame) in decision_frames:
                decision_frames.remove(id(frame))
                if thread_state.combined_runner is not None and (
                        value is None or frame.f_code is policy_code):
                    thread_state.combined_runner = None
                if not decision_frames and thread_state.combined_runner is None:
                    emit("DECISION_END")
            elif event == "return" and frame.f_code is runner_code and (
                    thread_state.combined_runner == id(frame)):
                thread_state.combined_runner = None
                if not decision_frames:
                    emit("DECISION_END")
            return trace
        sys.settrace(trace)
        threading.settrace(trace)
        emit("STARTED")
        if kind == "FIXTURE":
            item = next(f for f in MANIFEST if f.fixture_id == operation_id)
            result = verify_fixture(item)
        elif kind == "PROBE":
            item = next(p for p in PROBES if p.gate_id == operation_id)
            result = verify_probe(item, identity)
        elif kind == "AUDIT" and operation_id == "PUBLIC_EXECUTION_ARCHIVES":
            result = verify_execution_archives(reconstruct(archive_bytes))
        else:
            raise QualificationError("Unregistered E0 operation kind.")
        monitor_active = False
        sys.settrace(previous_trace)
        threading.settrace(previous_thread_trace)
        _need(capture_source_identity() == identity, "Source changed during worker execution.")
        emit("FINISHED", result)
    except BaseException as error:
        monitor_active = False
        sys.settrace(previous_trace)
        threading.settrace(previous_thread_trace)
        try:
            emit("WORKER_ABORT", f"{type(error).__name__}:{error}")
        except (OSError, EOFError):
            pass
    finally:
        monitor_active = False
        sys.settrace(previous_trace)
        threading.settrace(previous_thread_trace)
        connection.close()


def _supervise_operation(kind, operation_id, envelope, identity, *, job_started_ns,
                         archive_used_bytes, archives=()):
    """Private unit seam and fixed dispatch; abort preserves partial receipts.

    Worker-tree committed memory has a hard OS limit. Coordinator private
    memory plus peak worker-tree use is sampled each interval/boundary and
    aborts on their combined cap. Coordinator transients between samples are
    outside this interval-based policy; this is not a complete-machine cap.
    """
    envelope = require_envelope(envelope)
    _need(type(archives) is tuple and (kind == "AUDIT" or not archives),
          "Only the fixed public archive audit accepts archive input.")
    import multiprocessing
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    barrier = context.Event()
    process = context.Process(target=_fixed_e0_worker, args=(
        kind, operation_id, canonical_bytes(identity), canonical_bytes(envelope),
        canonical_bytes(archives), child, barrier))
    started = time.monotonic_ns()
    api = job = None
    events, result = [], None
    reason = None
    decision_started = None
    inputs = received = result_size = 0
    result_hash = None
    def record(event):
        events.append(OperationalEvent(len(events), event, time.monotonic_ns()-started, inputs))
    try:
        process.start()
        child.close()
        worker_budget = envelope.memory_cap_bytes - _coordinator_private_bytes()
        _need(worker_budget > 0, "SYSTEM_MEMORY_CAP: coordinator already consumes cap.")
        api, job, peak_memory = _attach_memory_job(process.pid, worker_budget)
        barrier.set()
        while True:
            now = time.monotonic_ns()
            if _coordinator_private_bytes() + peak_memory() > envelope.memory_cap_bytes:
                reason = "SYSTEM_MEMORY_CAP"
                break
            deadlines = [(job_started_ns + envelope.max_job_wall_ms*1000000, "SYSTEM_JOB_TIMEOUT"),
                         (started + envelope.max_case_wall_ms*1000000, "SYSTEM_CASE_TIMEOUT")]
            if decision_started is not None:
                deadlines.append((decision_started + envelope.max_decision_wall_ms*1000000,
                                  "SYSTEM_DECISION_TIMEOUT"))
            deadline, expiry = min(deadlines)
            if now >= deadline:
                reason = expiry
                break
            if not process.is_alive():
                process.join()
                if result is None or process.exitcode != 0:
                    reason = "SYSTEM_PROCESS_ABORT"
                break
            wait_ns = min(envelope.monitor_interval_ms*1000000, 60000000000, deadline-now)
            if result is not None:
                # The pipe can close just before process exit. A completed
                # payload waits for the actual clean exit without reading EOF.
                process.join(timeout=wait_ns/1000000000)
                continue
            if not parent.poll(wait_ns/1000000000):
                continue
            remaining = envelope.archive_cap_bytes - archive_used_bytes - received
            if remaining <= 0:
                reason = "SYSTEM_ARCHIVE_CAP"
                break
            raw = parent.recv_bytes(remaining)
            received += len(raw)
            message = reconstruct(raw)
            if time.monotonic_ns() >= deadline:
                reason = expiry
                break
            _need(type(message) is tuple and len(message) == 2, "Malformed worker event.")
            event, payload = message
            _need(result is None, "Worker continued after its sealed result.")
            if event == "STARTED":
                _need(not events and payload is None, "Worker start boundary is malformed.")
            elif event == "DECISION_START":
                _need(events and decision_started is None and payload is None,
                      "Overlapping/malformed decision start.")
                decision_started = time.monotonic_ns()
            elif event == "DECISION_END":
                _need(decision_started is not None and payload is None, "Missing decision start.")
                decision_started = None
            elif event == "BEFORE_INPUT":
                _need(events and payload is None, "Input lacks an operation boundary.")
                if inputs >= envelope.max_physical_inputs_per_case:
                    reason = "SYSTEM_INPUT_CAP"
                    break
                inputs += 1
            elif event == "FINISHED":
                _need(events and decision_started is None, "Unclosed decision boundary.")
                expected = (FixtureVerification if kind == "FIXTURE" else ProbeVerification
                            if kind == "PROBE" else ExecutionVerification)
                _need(type(payload) is expected, "Worker result has the wrong evidence type.")
                actual_id = (payload.fixture.fixture_id if kind == "FIXTURE" else payload.gate_id
                             if kind == "PROBE" else "PUBLIC_EXECUTION_ARCHIVES")
                _need(actual_id == operation_id, "Worker returned another operation's evidence.")
                result = payload
                result_size, result_hash = len(canonical_bytes(result)), content_digest(result)
            elif event == "WORKER_ABORT":
                _need(type(payload) is str and bool(payload), "Missing abort diagnosis.")
                reason = "UNRESOLVED_WORKER_ABORT:" + payload
                record(event)
                break
            else:
                raise QualificationError("Unknown worker boundary.")
            record(event)
            parent.send_bytes(b"CONTINUE")
    except (Exception, KeyboardInterrupt) as error:
        reason = f"SUPERVISION_INCOMPLETE:{type(error).__name__}:{error}"
    finally:
        if job is not None:
            if reason is not None:
                api.TerminateJobObject(job, 1)
            api.CloseHandle(job)  # Also removes any late shadow descendants.
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
        parent.close()
        child.close()
    receipt = OperationReceipt(kind, operation_id, content_digest(identity), content_digest(envelope),
        "COMPLETE" if reason is None else "INCOMPLETE", reason, tuple(events),
        time.monotonic_ns()-started, inputs, result_hash, result_size, process.exitcode)
    return receipt, result, received


def execute_e0(*, run_id, envelope, source_identity, p8, authorization_reference):
    """Future separately authorized orchestration. Slice-7 tests never call it.

    P-8 is consumed, never executed. Findings must subsequently be attached by
    the isolated evaluator after this public record has been sealed. A whole
    worker/Engine/V1 abort preserves its partial receipt and stops dispatch;
    no substitute action or alternate-case retry is available.
    """
    _need(type(authorization_reference) is str and bool(authorization_reference.strip()),
          "Actual E0 needs a separately supplied explicit authorization reference.")
    preflight = preflight_e0(envelope=envelope, source_identity=source_identity, p8=p8)
    _need(preflight.status == "READY", "E0 execution refused: " + "; ".join(preflight.reasons))
    env = require_envelope(envelope)
    _need(env.shadow_timeout_ms >= 1000,
          "Fixed normal probes use the frozen 1000ms shadow limit; declare at least that limit.")
    _need(type(run_id) is str and re.fullmatch("[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id),
          "Invalid execution run identity.")
    fixtures, probes, receipts, interruptions = [], [], [], []
    started, storage = time.monotonic_ns(), 0
    catalog = tuple(("FIXTURE", f.fixture_id) for f in MANIFEST) + tuple(("PROBE", p.gate_id) for p in PROBES)
    for kind, operation_id in catalog:
        receipt, result, received = _supervise_operation(
            kind, operation_id, env, source_identity, job_started_ns=started, archive_used_bytes=storage)
        receipts.append(receipt)
        storage += received + len(canonical_bytes(receipt))
        if result is not None:
            (fixtures if kind == "FIXTURE" else probes).append(result)
        if receipt.status != "COMPLETE":
            interruptions.append(receipt.reason)
            break
        if result.status != "PASS":
            interruptions.append("STOPPED_AFTER_FAILED_OR_INCOMPLETE_OPERATION:" + operation_id)
            break
    archives = tuple(a for probe in probes for a in probe.execution_archives)
    execution = ExecutionVerification(archives, (), (), (), (), (), ("Public archive audit unexecuted.",))
    if not interruptions:
        receipt, result, received = _supervise_operation(
            "AUDIT", "PUBLIC_EXECUTION_ARCHIVES", env, source_identity, job_started_ns=started,
            archive_used_bytes=storage, archives=archives)
        receipts.append(receipt)
        storage += received + len(canonical_bytes(receipt))
        if result is not None:
            execution = result
        if receipt.status != "COMPLETE":
            interruptions.append(receipt.reason)
    record = QualificationRecord(
        run_id, "E0_QUALIFICATION", authorization_reference, source_identity, env, MANIFEST_ID,
        PINNED_MANIFEST_SHA256, MANIFEST, tuple(fixtures), tuple(probes), execution, (), p8,
        tuple(interruptions), (), operational_receipts=tuple(receipts))
    if max(storage, len(canonical_bytes(record))) > env.archive_cap_bytes:
        record = replace(record, interruptions=record.interruptions + ("SYSTEM_ARCHIVE_CAP",))
    if time.monotonic_ns() - started >= env.max_job_wall_ms*1000000:
        record = replace(record, interruptions=record.interruptions + ("SYSTEM_JOB_TIMEOUT",))
    return record
