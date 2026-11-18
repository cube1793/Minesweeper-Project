"""Display-only certainty supplement for Live K-LC1 (experiment candidate KLC1_INFO_D1).

Worker only; the parent never imports this module.

The K owner makes its decision first, exactly as before. This module then reads
the finished, immutable KProposal -- its public grid, the public mine total, and
the two fact sets the decision already owns -- and asks one more question for
the same public state: which other HIDDEN cells are already proven safe or mine?
The answer leaves in a KProposalInfo beside the proposal. It is never written
to the owner, its session M, safe_cells, preinput_m, candidates or ranking, and
it grants no input.

  * engine     -- live_policy_info.CertaintyEngine, unchanged. The V1
    InfoSupplement is not used: it reads frozen V1 evidence K does not have.
  * grid       -- the proposal's public observation as it is. M is passed as
    already-proven cells, never painted onto the grid as flags.
  * LOCAL_SAFE -- one bounded pass (live_k_policy.K_INFO_NODE_BUDGET nodes).
  * exact      -- no search; the decision's own facts are only noted (NOT_RUN).
  * failure    -- a contradiction, or anything that cannot be confined to the
    engine call, is raised and ends the owner run through the worker's existing
    error path. Only an ordinary exception inside the engine call, after the
    binding was fixed, becomes a FAILED record. A failed engine is never reused.
    An unusable return value or a post-processing error is outside that call:
    it is raised as SENDER_INVALID and the proposal is not published.
"""

import sys
from time import perf_counter_ns

import live_k_policy as k
from live_policy_info import COMPLETE, PARTIAL, CertaintyEngine, Outcome
from simple_algorithm import InconsistentObservationError


class KInfoSupplement:
    """Owned by one K-LC1 worker run; consulted once per finished proposal."""

    def __init__(self):
        self._engine = None
        self._owner = None
        self._step = None

    def discard(self):
        self._engine = self._owner = self._step = None

    def describe(self, proposal):
        """KProposalInfo for a K-LC1 decision proposal, else None."""
        if not k.info_required(proposal):
            return None
        started = perf_counter_ns()
        s = proposal.snapshot
        try:
            facts_safe, facts_mines, digest = k.info_basis(proposal)
            route = k.INFO_ROUTES[proposal.continuation]
        except Exception as exc:
            self.discard()
            raise k.info_error("SENDER_INVALID", f"basis {type(exc).__name__}: {exc}") from exc

        owner = (s.run_id, s.board_generation, s.policy_id, s.width, s.height, s.num_mines)
        step = (s.input_seq, s.input_revision)
        if (self._engine is None or owner != self._owner
                or step != (self._step[0] + 1, self._step[1] + 1)):
            self._engine = CertaintyEngine()   # nothing carried across a gap
        self._owner, self._step = owner, step

        # Only the engine call itself is inside this try. An ordinary exception
        # raised by analyze / note_facts is a supplement-only failure (FAILED).
        outcome, failed = None, None
        try:
            if route == "local":
                outcome = self._engine.analyze(
                    s.observation, s.num_mines, node_budget=k.K_INFO_NODE_BUDGET,
                    facts=(facts_safe, facts_mines))
            else:
                self._engine.note_facts(s.observation, s.num_mines, facts_safe, facts_mines)
        except InconsistentObservationError as exc:
            # The source cannot be told apart from a contaminated decision basis.
            self.discard()
            raise k.info_error("CONTRADICTION", f"{type(exc).__name__}: {exc}") from exc
        except MemoryError:
            self.discard()
            raise
        except Exception as exc:
            self.discard()   # next proposal starts from a new engine
            failed = type(exc).__name__[:64]
            print(f"{k.INFO_CANDIDATE_ID}:FAILED {proposal.token} {failed}", file=sys.stderr, flush=True)

        # Everything from here on is outside the engine call: reading the returned
        # value, deriving the extra cells, building and checking the record. An
        # error here is an integrity error, never FAILED; nothing is published.
        try:
            status, error, nodes, skipped, safe, mines = "NOT_RUN", "", 0, 0, (), ()
            if failed is not None:
                status, error = "FAILED", failed
            elif route == "local":
                if type(outcome) is not Outcome:
                    raise TypeError(f"engine returned {type(outcome).__name__}, not Outcome")
                if type(outcome.safe) is not frozenset or type(outcome.mines) is not frozenset:
                    raise TypeError("engine outcome cells are not frozensets")
                status, nodes, skipped = outcome.status, outcome.nodes, outcome.skipped
                if status not in (COMPLETE, PARTIAL):
                    raise ValueError(f"unexpected engine status {status!r}")
                safe = k._ordered(outcome.safe - set(facts_safe))
                mines = k._ordered(outcome.mines - set(facts_mines))
            info = k.KProposalInfo(
                k.INFO_CANDIDATE_ID, proposal.token, digest, route, status, error,
                k.K_INFO_NODE_BUDGET, nodes, skipped, perf_counter_ns() - started, safe, mines)
            return k.validate_info(proposal, info)
        except Exception as exc:
            self.discard()
            raise k.info_error("SENDER_INVALID", f"record {type(exc).__name__}: {exc}") from exc
