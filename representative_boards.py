"""Pure deterministic category exemplars, not a statistical representative sample.

The caller owns evidence authentication and pairing. Selection uses only the
supplied outcomes and exact WW deltas, without loading or reconstructing games.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Literal


@dataclass(frozen=True)
class PairedGameFact:
    """One paired game's selection facts, with no source identity claim.

    For WW only, delta_us = Stage3_model_c_us - Stage2_model_c_us, in exact
    integer microseconds. Negative favors Stage 3; positive favors Stage 2.
    Non-WW requires None: termination-cost differences are not time-to-win facts.
    """

    game_index: int
    stage2_outcome: Literal["WIN", "LOSS"]
    stage3_outcome: Literal["WIN", "LOSS"]
    delta_us: int | None = None

    def __post_init__(self) -> None:
        if type(self.game_index) is not int or self.game_index < 0:
            raise ValueError("game_index must be a nonnegative integer, excluding bool.")
        for name in ("stage2_outcome", "stage3_outcome"):
            value = getattr(self, name)
            if type(value) is not str or value not in ("WIN", "LOSS"):
                raise ValueError(f"{name} must be exactly WIN or LOSS.")
        if self.stage2_outcome == self.stage3_outcome == "WIN":
            if type(self.delta_us) is not int:
                raise ValueError("WW requires integer delta_us, excluding bool.")
        elif self.delta_us is not None:
            raise ValueError("Non-WW requires delta_us=None; termination cost is not time-to-win.")


class ExemplarCategory(Enum):
    """Stable category identities in the accepted contract's display order."""

    MAX_STAGE3_WW_ADVANTAGE = "max_stage3_ww_advantage"
    MEDIAN_DELTA_WW = "median_delta_ww"
    CLOSEST_TO_ZERO_STAGE3_WW_ADVANTAGE = "closest_to_zero_stage3_ww_advantage"
    STAGE2_WW_ADVANTAGE = "stage2_ww_advantage"
    EXACT_WW_TIE = "exact_ww_tie"
    WL = "wl"
    LW = "lw"
    LL = "ll"


@dataclass(frozen=True)
class CategoryExemplar:
    """One category's original selected fact, or None for an EMPTY category."""

    category: ExemplarCategory
    game: PairedGameFact | None


def select_exemplars(games: Iterable[PairedGameFact]) -> tuple[CategoryExemplar, ...]:
    """Return all eight categories in contract order, including EMPTY entries.

    Duplicate game_index values are invalid even for identical records. Input
    order cannot affect selection. Each category is independent: a game may
    retain multiple memberships and is never replaced for visual variety.
    WL/LW/LL use Stage 2 as the first outcome letter and Stage 3 as the second.
    Invalid records/duplicates raise ValueError; no source or corpus is inferred.
    """
    try:
        records = tuple(games)
    except TypeError as exc:
        raise ValueError("games must be an iterable of PairedGameFact objects.") from exc
    seen = set()
    for game in records:
        if not isinstance(game, PairedGameFact):
            raise ValueError("Every game must be a PairedGameFact.")
        if game.game_index in seen:
            raise ValueError(f"Duplicate game_index: {game.game_index}.")
        seen.add(game.game_index)

    ww = sorted(
        (game for game in records if game.stage2_outcome == game.stage3_outcome == "WIN"),
        key=lambda game: (game.delta_us, game.game_index),
    )
    negative = tuple(game for game in ww if game.delta_us < 0)
    positive = tuple(game for game in ww if game.delta_us > 0)
    selections = [
        CategoryExemplar(ExemplarCategory.MAX_STAGE3_WW_ADVANTAGE,
                         negative[0] if negative else None),
        CategoryExemplar(ExemplarCategory.MEDIAN_DELTA_WW,
                         ww[(len(ww) - 1) // 2] if ww else None),
        CategoryExemplar(ExemplarCategory.CLOSEST_TO_ZERO_STAGE3_WW_ADVANTAGE,
                         min(negative, key=lambda game: (-game.delta_us, game.game_index), default=None)),
        CategoryExemplar(ExemplarCategory.STAGE2_WW_ADVANTAGE,
                         min(positive, key=lambda game: (-game.delta_us, game.game_index), default=None)),
        CategoryExemplar(ExemplarCategory.EXACT_WW_TIE,
                         next((game for game in ww if game.delta_us == 0), None)),
    ]
    for category, stage2, stage3 in (
        (ExemplarCategory.WL, "WIN", "LOSS"),
        (ExemplarCategory.LW, "LOSS", "WIN"),
        (ExemplarCategory.LL, "LOSS", "LOSS"),
    ):
        game = min(
            (game for game in records if (game.stage2_outcome, game.stage3_outcome) == (stage2, stage3)),
            key=lambda game: game.game_index, default=None,
        )
        selections.append(CategoryExemplar(category, game))
    return tuple(selections)
