"""Thin recording layer over the unchanged S3D3-A stage-2 runner (GUESS_OUTCOME_RECORD_V1).

``run_recorded`` calls ``run_s3d3_stage2`` exactly once, with
capture_effects=False, and then turns the returned in-memory result into a
guess outcome record. The selection loop is not copied or reordered: first
input, certain decisions, forced-pair pre-emption, tie look-ahead, the 8-cell
and 72-call limits, both validators, guess OFF, the input cap and the stop
right after a terminal status are all the stage-2 runner's own.

Recording adds no inference and no probability call. It never reads the
Engine again: the base result comes from the run result's status, and every
piece of evidence was fixed by stage 2 BEFORE the input it belongs to. The
file, if any, is written after the run has ended; nothing is written to disk
input by input, and there is no resume. A save failure is returned as a state
and never re-runs or relabels the game. Experimental copy only.
"""

from dataclasses import dataclass

from core_engine import GameStatus
from experiments import program_d3_guess_record as record
from experiments.program_d3_lookahead_policy import IMPLEMENTATION_SCOPE, LookaheadSelection
from experiments.program_d3_lookahead_runner import LookaheadRunResult, run_s3d3_stage2
from simple_algorithm import SimpleMove


@dataclass(frozen=True)
class RecordedRun:
    """The untouched stage-2 result, its record, and the save state (never a game result)."""

    run: LookaheadRunResult
    record: record.GuessOutcomeRecord
    save: record.SaveOutcome


@dataclass(frozen=True)
class SegmentInput:
    """One actual input after a prefix state: the move, the status after it, and the
    stage-2 selection record that was fixed before it."""

    move: SimpleMove
    status_after: GameStatus
    choice: LookaheadSelection


def _need(condition, code, detail):
    if not condition:
        raise record.GuessRecordError(code, detail)


def evidence_of(choice) -> record.GuessEvidence:
    """Copy the pre-input evidence of one stage-2 guess selection; nothing is computed."""
    _need(type(choice) is LookaheadSelection and choice.evidence is not None and choice.premises is not None
          and choice.inner is not None, "RECORD_EVIDENCE", "Expected a stage-2 guess selection of a real decision.")
    evidence, premises, kept = choice.evidence, choice.premises, choice.inner.selected.move
    values = tuple(record.CandidateValue(
        cell=value.cell, mine_worlds=value.mine_worlds, total_worlds=value.total_worlds,
        mine_neighbors=value.mine_neighbors, unresolved_neighbors=value.unresolved_neighbors,
        calls=value.calls,
        outcomes=tuple(record.NumberOutcome(o.number, o.worlds, o.q_kind, o.q, o.minimum_mine_worlds,
                                            o.safe_cells, o.flood) for o in value.outcomes),
        flood_worlds=value.flood_worlds, s_v=value.s_v, s_c=value.s_c) for value in choice.lookaheads)
    proofs = tuple(record.PairBasis(p.a, p.b, p.verdict, p.failed, p.bases, p.distinguishing,
                                    p.mine_worlds, p.total_worlds) for p in choice.pair_proofs)
    state = record.PublicState(
        premises.observation, premises.num_mines,
        tuple(sorted(premises.mines, key=lambda cell: (cell[1], cell[0]))), premises.cursor,
        premises.total_worlds, premises.mine_worlds)
    return record.GuessEvidence(
        kind=evidence.kind, selection_reason=choice.selection_reason, target=evidence.target,
        risk=evidence.risk, risk_kind=evidence.risk_kind, original_target=evidence.original_target,
        original_risk=evidence.original_risk, is_minimum_risk=evidence.is_minimum_risk,
        target_changed=choice.target_changed, pair=evidence.pair, category=choice.category,
        k_lc1_move=(kept.action.name, kept.x, kept.y), lookahead_status=choice.lookahead_status,
        lookahead_set=choice.lookahead_set, rank_basis=choice.rank_basis,
        lookahead_cells=choice.lookahead_cells, outside_set_lookahead=choice.outside_set_lookahead,
        planned_calls=choice.planned_calls, actual_calls=choice.actual_calls,
        target_s_c=evidence.target_s_c, original_s_v=evidence.original_s_v, values=values,
        ranking=choice.ranking, pair_proofs=proofs, independence=choice.independence, public_state=state)


def _input_of(index, move, status_after, choice) -> record.RecordedInput:
    """One actual input with the evidence of THAT input (taken from its own selection record)."""
    _need(type(move) is SimpleMove and type(status_after) is GameStatus, "RECORD_INPUTS",
          "An actual input needs its move and the status after it.")
    if choice is None:
        _need(index == 0, "RECORD_LINK", "Only the initial input has no selection record.")
        decision, evidence = record.INITIAL_OPEN, None
    else:
        _need(type(choice) is LookaheadSelection and move == choice.move, "RECORD_LINK",
              "The selection record of an input must be the one that chose that input.")
        if choice.evidence is None:
            decision, evidence = record.CERTAIN, None
        else:
            decision, evidence = record.GUESS, evidence_of(choice)
    return record.RecordedInput(index, move.action.name, move.x, move.y, status_after.name, decision, evidence)


def record_of_run(result, width, height, num_mines, allow_guess) -> record.GuessOutcomeRecord:
    """Record of a full run from the first input, from the stage-2 run result alone."""
    _need(type(result) is LookaheadRunResult and result.implementation_scope == IMPLEMENTATION_SCOPE
          == record.SELECTION_SCOPE, "RECORD_FIELD", "Expected a stage-2 run result.")
    inputs = []
    for position, trace in enumerate(result.traces):
        _need(trace.action.input_index == position
              and trace.evidence is (None if trace.choice is None else trace.choice.evidence),
              "RECORD_LINK", "A trace must carry the evidence of its own input.")
        inputs.append(_input_of(position, trace.action.move, trace.action.status_after, trace.choice))
    blocked = None
    if result.blocked is not None:
        proposal = result.blocked
        _need(proposal.evidence is proposal.choice.evidence, "RECORD_LINK",
              "A blocked proposal must carry its own evidence.")
        move = proposal.choice.move
        blocked = record.BlockedProposal(proposal.input_index, proposal.cursor, move.action.name, move.x,
                                         move.y, evidence_of(proposal.choice))
    return record.make_record(
        record_scope=record.FULL_RUN, width=width, height=height, num_mines=num_mines,
        allow_guess=allow_guess, prefix_inputs=(), inputs=tuple(inputs), blocked=blocked,
        final_status=result.status.name, stop_reason=result.stop_reason)


def record_of_segment(width, height, num_mines, prefix_inputs, steps) -> record.GuessOutcomeRecord:
    """Record of the actual inputs that followed a prefix state.

    The caller performed the decision, both validations and the input with the unchanged
    stage-2 functions; this only writes down what was fixed before each input and the
    status after it. Not a run from the first input.
    """
    _need(all(type(move) is SimpleMove for move in prefix_inputs)
          and all(type(step) is SegmentInput and step.choice is not None for step in steps),
          "RECORD_INPUTS", "A segment needs its public prefix inputs and decided inputs.")
    prefix = tuple((move.action.name, move.x, move.y) for move in prefix_inputs)
    inputs = tuple(_input_of(len(prefix) + position, step.move, step.status_after, step.choice)
                   for position, step in enumerate(steps))
    _need(bool(inputs), "RECORD_INPUTS", "A segment needs at least one actual input.")
    final = inputs[-1].status_after
    return record.make_record(
        record_scope=record.SEGMENT, width=width, height=height, num_mines=num_mines, allow_guess=True,
        prefix_inputs=prefix, inputs=inputs, blocked=None, final_status=final,
        stop_reason=record.SEGMENT_END if final == record.PLAYING else record.TERMINAL)


def run_recorded(engine, *, allow_guess, table=None, save_path=None) -> RecordedRun:
    """Run stage 2 once, unchanged, then record it; optionally save the record afterwards.

    Only public board metadata is read from the Engine, before the run. An error of the
    run propagates and leaves no record. A failed save is reported in ``save`` and changes
    neither the run result nor the record.
    """
    width, height, num_mines = engine.width, engine.height, engine.num_mines
    result = run_s3d3_stage2(engine, allow_guess=allow_guess, table=table, capture_effects=False)
    outcome = record_of_run(result, width, height, num_mines, allow_guess)
    if save_path is None:
        save = record.SaveOutcome(record.NOT_SAVED, None, None, None, None, None, None)
    else:
        save = record.save_record(outcome, save_path)
    return RecordedRun(result, outcome, save)
