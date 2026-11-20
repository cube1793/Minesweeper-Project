"""Experimental composition S3D23-A: ONE K-LC1 selection, then S3D2-A or S3D3-A by the kind of decision.

K-LC1 stays the baseline of every decision. One original K-LC1 selection record
is made per decision and handed, untouched, to exactly one accepted adapter:

    EXACT_GUESS             -> program_d3_lookahead_policy.apply_lookahead      (S3D3-A, stage 2)
    LOCAL_SAFE, EXACT_SAFE  -> program_d2_opening_policy.apply_proven_opening   (S3D2-A)

The two accepted ``select_*_policy`` entry points are NOT used here: each of
them makes its own K-LC1 selection, so calling both would build the original
selection twice for one decision. Nothing is inferred, enumerated, routed,
pruned, cached or kept between decisions in this module, and neither adapter's
rule, condition, constant or limit is changed. S3D1-A is not part of this.

The combined record keeps the original selection (``inner``), the branch, the
ONE record of that branch, and the input that will actually be sent together
with its category. The original K-LC1 input is ``inner.selected.move``; the
actual input may differ (an applied opening, a changed guess target), and then
it has no K-LC1 PolicySelection. Any other continuation, a record of the wrong
branch, a second record, or a record made from another original selection is
an error; an error is never turned into "keep the K-LC1 input".

The identifiers below name this experimental composition only. They are not
the product's display name and replace no K-LC1, S3D2-A or S3D3-A identifier.
Experimental copy only.
"""

from dataclasses import dataclass

from experiments import program_d2_opening_policy as d2
from experiments import program_d3_lookahead_policy as d3
from experiments.program_k_lc1_policy import SingletonSelection, select_singleton_policy
from experiments.program_k_policy import KPolicyIntegrityError
from simple_algorithm import SimpleMove


COMPOSITION_ID = "S3D23-A"
COMPOSITION_DEFINITION = "K_LC1_THEN_D2_CERTAIN_OR_D3_GUESS_V1"
BRANCH_CERTAIN, BRANCH_GUESS = "CERTAIN_D2", "GUESS_D3"
GUESS_CONTINUATION = "EXACT_GUESS"
CERTAIN_CONTINUATIONS = ("LOCAL_SAFE", "EXACT_SAFE")
PARTS = (
    (BRANCH_CERTAIN, d2.CANDIDATE_ID, d2.CANDIDATE_DEFINITION, None),
    (BRANCH_GUESS, d3.CANDIDATE_ID, d3.CANDIDATE_DEFINITION, d3.IMPLEMENTATION_SCOPE),
)


@dataclass(frozen=True)
class CombinedSelection:
    """The original K-LC1 record, the branch, that branch's ONE record and the actual input.

    ``opening`` is set only on the certain branch and ``guess`` only on the
    guess branch; the record that is set was made from ``inner`` itself.
    """

    inner: SingletonSelection
    branch: str
    opening: d2.OpeningSelection | None
    guess: d3.LookaheadSelection | None
    move: SimpleMove
    category: str

    @property
    def policy_id(self) -> str:
        return COMPOSITION_ID

    @property
    def policy_definition(self) -> str:
        return COMPOSITION_DEFINITION

    @property
    def record(self):
        """The one record of the branch."""
        return self.guess if self.branch == BRANCH_GUESS else self.opening

    @property
    def input_changed(self) -> bool:
        """Does the actual input differ from the original K-LC1 input?"""
        if self.branch == BRANCH_GUESS:
            return self.guess.target_changed
        return self.opening.applied is not None

    @property
    def selected(self):
        """The unchanged K-LC1 PolicySelection, or None when the actual input differs from it."""
        return None if self.input_changed else self.inner.selected


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise KPolicyIntegrityError("COMBINED_SELECTION", detail)


def branch_of(inner) -> str:
    """The branch of one K-LC1 record; any continuation outside the three known ones is an error."""
    _require(type(inner) is SingletonSelection, "Expected the K-LC1 selection record.")
    continuation = inner.native.continuation
    if continuation == GUESS_CONTINUATION:
        return BRANCH_GUESS
    _require(type(continuation) is str and continuation in CERTAIN_CONTINUATIONS,
             f"No branch for the continuation {continuation!r}.")
    return BRANCH_CERTAIN


def apply_combined(inner: SingletonSelection, table) -> CombinedSelection:
    """One K-LC1 record in, the record of its ONE branch out. The adapter validates ``inner``."""
    branch = branch_of(inner)
    if branch == BRANCH_GUESS:
        guess = d3.apply_lookahead(inner, table)
        return CombinedSelection(inner, branch, None, guess, guess.move, guess.category)
    opening = d2.apply_proven_opening(inner)
    return CombinedSelection(inner, branch, opening, None, opening.move, opening.category)


def select_combined_policy(evidence, cursor, table) -> CombinedSelection:
    """ONE K-LC1 selection (one native selection) of this decision, then its one branch."""
    return apply_combined(select_singleton_policy(evidence, cursor, table), table)


def check_combined_shape(result) -> None:
    """Branch, the one record, its origin and the actual input agree with each other.

    This is the structure only; the record itself is validated by its own
    accepted validator (``validate_combined_selection`` or the execution
    validator of its branch).
    """
    _require(type(result) is CombinedSelection, "Expected a combined selection record.")
    _require(type(result.branch) is str and result.branch in (BRANCH_CERTAIN, BRANCH_GUESS)
             and result.branch == branch_of(result.inner), "The branch is not that of the original decision.")
    if result.branch == BRANCH_GUESS:
        _require(result.opening is None and type(result.guess) is d3.LookaheadSelection,
                 "A guess decision carries exactly one S3D3-A record and no opening record.")
    else:
        _require(result.guess is None and type(result.opening) is d2.OpeningSelection,
                 "A certain decision carries exactly one S3D2-A record and no guess record.")
    record = result.record
    _require(record.inner is result.inner, "The branch record was not made from this original selection.")
    _require(type(result.move) is SimpleMove and type(record.move) is SimpleMove and result.move == record.move
             and type(result.category) is str and result.category == record.category,
             "The actual input or its category differs from the branch record.")


def validate_combined_selection(result, table) -> None:
    """Structure, then the accepted validator of the branch. No inference and no probability call."""
    check_combined_shape(result)
    if result.branch == BRANCH_GUESS:
        d3.validate_lookahead_selection(result.guess, table)
    else:
        d2.validate_opening_selection(result.opening)
