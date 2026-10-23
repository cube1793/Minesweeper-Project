"""I1 schema/codec qualification from manually supplied synthetic records only."""

from dataclasses import FrozenInstanceError, dataclass, fields, replace
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments import program_k_e2_records as r
from experiments import program_k_e2_store as store


SHA = "a" * 64
OID = "b" * 40
CELLS = ((1, 0), (2, 0), (0, 1), (1, 1))

# Captured before the additive I5 audit correction: the original eighteen kinds
# plus the accepted I4 decision kind. The original fixtures remain unchanged.
_OLD_RECORD_SHA256 = {
    "ProtocolIdentity": "d0f097aed672b80ba3ea9f7ce551dd52fa1e59cb095f2af1663091ee9363f247",
    "RuntimeIdentity": "a25cc2b34658f0e1efd71349a1521dd846bab4b26be56a970ab68f9e1bfa6902",
    "SourceBlobIdentity": "fd9ea14789fd5085d585d61f22ea6dbda654bd57cc5ae8568e06883abc529e1d",
    "CorpusIdentity": "69e8c2013c09263331093908bad1c32be636af0a07186575df81ab0f54378de6",
    "BoardIdentity": "bb5dcf9930862dded4bfbbd2f21c7e0484c2c5a181ae61804d37e0e9fb1c38cd",
    "ArmIdentity": "53eca4884e7e1cf01cba59d9228a3f8361338840c896ebe02d8e05b4175cd477",
    "PhysicalInputRecord": "f5b3bd591d3d4f83840107528991a616a5db2dd37c8c6abb9831bbea6acda5a1",
    "PublicEffectRecord": "35cfef25269e2a615b85c85ba4adbe19351a1e0e79109e5f5d11cd5e77acff15",
    "TerminalEffectRecord": "0f43ee70efca7218970a5b3796c953190d671e576bfde3f095062d0df8792021",
    "DecisionSpanRecord": "94bf15419caa5c0304a85796be597a22e8e48ca0960d64521db5d542d930fb7f",
    "GuessCheckpointRecord": "17d8b3cf003fa7a5fdbf3e81c0eccacfc2f1e7d101e77ed16419db0f0f695eeb",
    "ControlFlagProvenanceRecord": "6bec41f154680f6ca2256a81de1116d5be65fdafe7a8fd0102ad892db48ae1e7",
    "AcquisitionRecord": "b9d353b82b828f40e4d7529b4f5968231c3a33ee5fde0fdac658bb95f46ca90a",
    "EvaluatorRecord": "4e97f8f1f7f879e1911457fbafa583b67056df5bb65c4aacd90d182a8b9cecad",
    "PairComparisonRecord": "fa9a0740e171e2379ffe7659c077c3a341ddb253e18e01f94b2b6b57f1ab6551",
    "OperationEventRecord": "abaebef3991c6ed7cfe67755e3580c6e82edc7a4b8f0b77861d3af619c79f55d",
    "ResourceSampleRecord": "d4a3bacc04064f9020205e1aee4a627b5d3aac4c40df102ba89eed5eb4dd6d2e",
    "CompletionReceipt": "4896a4ad984ce1ea13299c7f48569dc8f2e4e3621ed6ca60ca7f68d714008be3",
    "ActionDecisionRecord": "d504dfdfcdf76eda70555b18964842d2cf03780559c242064cc45913fc8ba7c1",
}


def _wire(node):
    return json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _fixtures():
    board = r.BoardIdentity(107, "synthetic-fingerprint", 3, 2, 2, (0, 0), "supplied-generator", "supplied-spec")
    arm = r.ArmIdentity(r.Arm.K_P0, board, "synthetic-run", "synthetic-unit")
    guess = r.GuessCheckpointRecord(arm, 1, (((0, 0), 1),), (), ((2, 1),), CELLS, 1, 8,
                                    tuple((c, 2) for c in CELLS), tuple((c, Fraction(1, 4)) for c in CELLS),
                                    Fraction(1, 4), CELLS, (1, 0), r.Outcome.WIN)
    witness = r.ProductiveChordWitness(4, (1, 1), ((2, 1),), ((1, 0),))
    return (
        r.ProtocolIdentity("docs/synthetic.md", SHA, OID, "c" * 40),
        r.RuntimeIdentity("SyntheticPython", "0.0.1", "supplied-os", "supplied-platform", "supplied-arch", None),
        r.SourceBlobIdentity("experiments/synthetic.py", OID, SHA, 321),
        r.CorpusIdentity("SYNTHETIC", 100, 113, 3, (107, 100, 112), SHA, (105,)),
        board, arm,
        r.PhysicalInputRecord(0, r.Action.OPEN, (0, 0), (0, 0), 126005, 126005, r.Status.PLAYING),
        r.PublicEffectRecord(1, (r.PublicCellChange((0, 0), "HIDDEN", "CLUE_1"),
                                 r.PublicCellChange((1, 0), "FLAGGED", "HIDDEN"),
                                 r.PublicCellChange((2, 1), "HIDDEN", "FLAGGED")), r.Status.PLAYING, r.Status.PLAYING),
        r.TerminalEffectRecord(7, (r.TerminalCellChange((2, 1), r.TerminalPresentation.MINE),), r.Status.LOST),
        r.DecisionSpanRecord(0, r.DecisionScope.CONTROL_PLAN_POSITION, None),
        guess,
        r.ControlFlagProvenanceRecord(2, (2, 1), r.FlagCategory.CONTROL_FALLBACK_FLAG, None, None, None, witness),
        r.AcquisitionRecord(2, 1, (2, 1), r.AcquisitionSource.LOCAL, "certificate-1", SHA),
        r.EvaluatorRecord(arm, r.AssertionCategory.LOGICAL_M, ((2, 1),), r.EvaluationStatus.PASS, "VERIFIED", ""),
        r.PairComparisonRecord(board, r.Outcome.WIN, r.Outcome.WIN, r.P3Status.PASS, -126005,
                               r.G5ExposureSummary(1, 2, 3), "SUPPLIED_MATCH"),
        r.OperationEventRecord(r.Phase.VALIDATION, "synthetic-unit", r.EventKind.END, 12, 2, r.OperationStatus.COMPLETED),
        r.ResourceSampleRecord("synthetic-unit", r.ProcessRole.COMBINED, 12, 8, 20, "supplied-timestamp", 15, r.MemoryMethod.RSS),
        r.CompletionReceipt(SHA, SHA, SHA, SHA, (r.StreamDigest("actions", SHA, 120, 2),
                                                 r.StreamDigest("public", SHA, 150, 3)), r.CompletionState.COMPLETED),
    )


def _decision_fixture():
    return r.ActionDecisionRecord(
        _fixtures()[5], 3, "SETUP_CHORD", "LOCAL_SAFE", r.Action.FLAG, (2, 0),
        ((r.Action.FLAG, (2, 0)), (r.Action.FLAG, (1, 1)), (r.Action.CHORD, (1, 0))),
        400000, 2, ((2, 0), (1, 1)), ((0, 1), (2, 1)), ((2, 0),), ((2, 0), (1, 1)))


class AdditiveDecisionRecordTests(unittest.TestCase):
    def test_all_preexisting_kinds_keep_their_captured_canonical_hashes(self):
        fixtures = _fixtures() + (_decision_fixture(),)
        self.assertEqual({type(value).__name__ for value in fixtures}, set(_OLD_RECORD_SHA256))
        self.assertEqual(len(fixtures), 19)
        self.assertEqual(r.SCHEMA_VERSION, 1)
        for value in fixtures:
            with self.subTest(kind=type(value).__name__):
                encoded = r.encode(value)
                self.assertEqual(hashlib.sha256(encoded).hexdigest(), _OLD_RECORD_SHA256[type(value).__name__])
                self.assertEqual(r.encode(r.decode(encoded)), encoded)

    def test_initial_control_and_kp0_rules_round_trip(self):
        for kind, category in ((r.Arm.CONTROL, "CONTROL_INITIAL_OPEN"), (r.Arm.K_P0, "POLICY_INITIAL_OPEN")):
            arm = replace(_fixtures()[5], arm=kind)
            value = r.ActionDecisionRecord(arm, 0, category, "INITIAL", r.Action.OPEN,
                                            arm.board.first_click, (), None, None, (), (), (), ())
            self.assertEqual(r.decode(r.encode(value)), value)
            for changes in (dict(category="wrong initial category"), dict(semantic_kind="LOCAL_SAFE"),
                            dict(action=r.Action.FLAG), dict(target=(1, 0)), dict(plan_model_us=1),
                            dict(plan_safe_reveals=0), dict(setup_cells=((1, 0),)),
                            dict(reveal_cells=((1, 0),)), dict(logical_mines_after=((1, 0),)),
                            dict(plan_actions=((r.Action.OPEN, (0, 0)),), plan_model_us=1, plan_safe_reveals=0)):
                with self.subTest(kind=kind, changes=changes), self.assertRaises(r.RecordError):
                    replace(value, **changes)

    def test_postinitial_control_retains_selected_plan_without_logical_m(self):
        value = _decision_fixture()
        control = replace(value, arm=replace(value.arm, arm=r.Arm.CONTROL),
                          category="LOCAL_DETERMINISTIC", semantic_kind="LOCAL_DETERMINISTIC",
                          setup_cells=(), reveal_cells=(), logical_mines_before=(), logical_mines_after=())
        self.assertEqual(r.decode(r.encode(control)), control)
        for changes in (dict(logical_mines_after=((2, 0),)),
                        dict(logical_mines_before=((2, 0),), logical_mines_after=((2, 0),))):
            with self.assertRaises(r.RecordError):
                replace(control, **changes)

    def test_plan_order_is_preserved_without_candidate_graphs(self):
        value = _decision_fixture()
        encoded = r.encode(value)
        self.assertEqual(r.decode(encoded), value)
        self.assertEqual(json.loads(encoded)["fields"]["plan_actions"],
                         [["FLAG", [2, 0]], ["FLAG", [1, 1]], ["CHORD", [1, 0]]])
        changed = replace(value, plan_actions=(value.plan_actions[0], value.plan_actions[2], value.plan_actions[1]))
        self.assertEqual(r.decode(r.encode(changed)).plan_actions, changed.plan_actions)
        self.assertNotEqual(r.encode(changed), encoded)
        self.assertFalse(hasattr(value, "__dict__"))
        self.assertEqual(tuple(field.name for field in fields(value)), (
            "arm", "action_ordinal", "category", "semantic_kind", "action", "target", "plan_actions",
            "plan_model_us", "plan_safe_reveals", "setup_cells", "reveal_cells",
            "logical_mines_before", "logical_mines_after"))
        with self.assertRaises(FrozenInstanceError):
            value.category = "changed"

    def test_no_plan_has_no_metrics_or_candidate_cells(self):
        value = replace(_decision_fixture(), category="EXACT_MINIMUM_RISK_GUESS", semantic_kind="EXACT_GUESS",
                        action=r.Action.OPEN, target=(0, 1), plan_actions=(), plan_model_us=None,
                        plan_safe_reveals=None, setup_cells=(), reveal_cells=())
        self.assertEqual(r.decode(r.encode(value)), value)
        for changes in (dict(plan_model_us=1), dict(plan_safe_reveals=0), dict(setup_cells=((2, 0),)),
                        dict(reveal_cells=((0, 1),)), dict(semantic_kind="INITIAL")):
            with self.assertRaises(r.RecordError):
                replace(value, **changes)

    def test_exact_ownership_and_scalar_types(self):
        class IntSubclass(int):
            pass
        class TextSubclass(str):
            pass
        class ArmSubclass(r.ArmIdentity):
            pass
        class RecordSubclass(r.ActionDecisionRecord):
            pass
        value = _decision_fixture()
        arm_subclass = ArmSubclass(value.arm.arm, value.arm.board, value.arm.run_id, value.arm.unit_id)
        invalid = {
            "arm": (None, {}, arm_subclass, replace(value.arm, arm=r.Arm.K_CONTROL)),
            "action_ordinal": (True, -1, 1.0, IntSubclass(3)),
            "category": ("", "bad\ncategory", None, {}, TextSubclass("SETUP_CHORD")),
            "semantic_kind": ("", None, {"kind": "LOCAL_SAFE"}, 1, TextSubclass("LOCAL_SAFE")),
            "action": ("FLAG", 1, True, None),
            "target": ([2, 0], (True, 0), (2.0, 0), (3, 0), (0, 2)),
        }
        for name, values in invalid.items():
            for invalid_value in values:
                with self.subTest(field=name, value=invalid_value), self.assertRaises(r.RecordError):
                    replace(value, **{name: invalid_value})
        subclass = RecordSubclass(*(getattr(value, field.name) for field in fields(value)))
        with self.assertRaises(r.RecordError):
            r.encode(subclass)

    def test_plan_entries_first_input_and_metrics_are_strict(self):
        value = _decision_fixture()
        for plan in (list(value.plan_actions), ([r.Action.FLAG, (2, 0)],),
                     (("FLAG", (2, 0)),), ((r.Action.FLAG, [2, 0]),),
                     ((r.Action.FLAG, (3, 0)),), ((r.Action.FLAG, (2, 0), "extra"),),
                     ((r.Action.OPEN, (2, 0)),), ((r.Action.FLAG, (1, 0)),)):
            with self.subTest(plan=plan), self.assertRaises(r.RecordError):
                replace(value, plan_actions=plan)
        for name, bad_values in (("plan_model_us", (None, 0, -1, True, 1.0, 1 << 64)),
                                 ("plan_safe_reveals", (None, -1, True, 1.0, 1 << 64))):
            for bad in bad_values:
                with self.subTest(field=name, value=bad), self.assertRaises(r.RecordError):
                    replace(value, **{name: bad})
        self.assertEqual(replace(value, plan_safe_reveals=0).plan_safe_reveals, 0)

    def test_all_setlike_cells_are_owned_unique_reading_order_and_in_board(self):
        value = _decision_fixture()
        for name in ("setup_cells", "reveal_cells", "logical_mines_before", "logical_mines_after"):
            for cells in ([], {(2, 0)}, ((2, 0), (2, 0)), ((1, 1), (2, 0)),
                          ((3, 0),), ((0, 2),), ((True, 0),), ([2, 0],)):
                with self.subTest(field=name, cells=cells), self.assertRaises(r.RecordError):
                    replace(value, **{name: cells})
        with self.assertRaises(r.RecordError):
            replace(value, logical_mines_after=())
        retained = replace(value, logical_mines_after=value.logical_mines_before)
        self.assertEqual(r.decode(r.encode(retained)), retained)

    def test_explicit_new_wire_schema_is_canonical(self):
        value = _decision_fixture()
        node = {"kind": "action_decision", "version": 1, "fields": {
            "arm": json.loads(r.encode(value.arm)), "action_ordinal": 3,
            "category": "SETUP_CHORD", "semantic_kind": "LOCAL_SAFE", "action": "FLAG", "target": [2, 0],
            "plan_actions": [["FLAG", [2, 0]], ["FLAG", [1, 1]], ["CHORD", [1, 0]]],
            "plan_model_us": 400000, "plan_safe_reveals": 2,
            "setup_cells": [[2, 0], [1, 1]], "reveal_cells": [[0, 1], [2, 1]],
            "logical_mines_before": [[2, 0]], "logical_mines_after": [[2, 0], [1, 1]],
        }}
        self.assertEqual(r.encode(value), _wire(node))
        self.assertEqual(r.decode(_wire(node)), value)

    def test_unknown_missing_extra_and_nested_wrong_record_fields_rejected(self):
        original = r.encode(_decision_fixture())
        for field in json.loads(original)["fields"]:
            node = json.loads(original)
            del node["fields"][field]
            with self.subTest(missing=field), self.assertRaises(r.RecordError):
                r.decode(_wire(node))
        for changes in ({"candidate_graph": []}, {"__class__": "PolicySelection"}, {"hidden_truth": {}}):
            node = json.loads(original)
            node["fields"].update(changes)
            with self.assertRaises(r.RecordError):
                r.decode(_wire(node))
        node = json.loads(original)
        node["kind"] = "unregistered_decision"
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))
        node = json.loads(original)
        node["fields"]["arm"] = json.loads(r.encode(_fixtures()[4]))
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))

    def test_malformed_new_plan_wire_and_float_authority_are_rejected(self):
        original = r.encode(_decision_fixture())
        for bad in (None, {}, ["FLAG"], [["FLAG", [2, 0], "extra"]],
                    [["INVALID", [2, 0]]], [[True, [2, 0]]], [["FLAG", [True, 0]]],
                    [["FLAG", [2.0, 0]]], [["FLAG", [3, 0]]]):
            node = json.loads(original)
            node["fields"]["plan_actions"] = bad
            with self.subTest(plan=bad), self.assertRaises(r.RecordError):
                r.decode(_wire(node))
        for field in ("action_ordinal", "plan_model_us", "plan_safe_reveals"):
            for bad in (True, 1.0, float("nan"), float("inf")):
                node = json.loads(original)
                node["fields"][field] = bad
                with self.subTest(field=field, value=bad), self.assertRaises(r.RecordError):
                    r.decode(_wire(node))

    def test_encoder_revalidates_new_record_and_nested_arm(self):
        value = _decision_fixture()
        object.__setattr__(value, "plan_actions", list(value.plan_actions))
        with self.assertRaises(r.RecordError):
            r.encode(value)
        value = _decision_fixture()
        object.__setattr__(value.arm.board, "width", True)
        with self.assertRaises(r.RecordError):
            r.encode(value)


class CodecRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = _fixtures()

    def test_all_eighteen_families_canonical_round_trip(self):
        self.assertEqual(len(self.fixtures), 18)
        kinds = set()
        for original in self.fixtures:
            with self.subTest(family=type(original).__name__):
                encoded = r.encode(original)
                rebuilt = r.decode(encoded)
                self.assertEqual(rebuilt, original)
                self.assertIs(type(rebuilt), type(original))
                self.assertEqual(r.encode(rebuilt), encoded)
                node = json.loads(encoded)
                self.assertEqual(node["version"], 1)
                kinds.add(node["kind"])
                self.assertNotIn(b"NaN", encoded)
        self.assertEqual(len(kinds), 18)

    def test_golden_canonical_bytes(self):
        self.assertEqual(r.encode(self.fixtures[9]),
                         b'{"fields":{"action_ordinal":0,"duration_ns":null,"scope":"CONTROL_PLAN_POSITION"},"kind":"decision_span","version":1}')

    def test_all_record_fields_are_frozen_and_slotted(self):
        for value in self.fixtures:
            with self.subTest(family=type(value).__name__):
                self.assertFalse(hasattr(value, "__dict__"))
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, fields(value)[0].name, None)
                with self.assertRaises((TypeError, AttributeError)):
                    value.unexpected = "payload"

    def test_nested_ownership_is_immutable(self):
        guess = self.fixtures[10]
        with self.assertRaises(TypeError):
            guess.mine_counts[0] = ((1, 0), 3)
        with self.assertRaises(FrozenInstanceError):
            guess.arm.board.width = 99
        with self.assertRaises(FrozenInstanceError):
            self.fixtures[7].changes[0].after = "MINE"
        with self.assertRaises(FrozenInstanceError):
            self.fixtures[17].streams[0].record_count = 100
        for changes in (dict(unresolved=list(CELLS)), dict(physical_p=set()), dict(mine_counts=list(guess.mine_counts))):
            with self.assertRaises(r.RecordError):
                replace(guess, **changes)

    def test_raw_counts_preserved_separately_from_reduced_fractions(self):
        value = r.decode(r.encode(self.fixtures[10]))
        self.assertEqual(value.unreduced_z, 8)
        self.assertEqual(tuple(m for _, m in value.mine_counts), (2, 2, 2, 2))
        self.assertTrue(all(type(p) is Fraction and p == Fraction(1, 4) for _, p in value.probabilities))
        node = json.loads(r.encode(value))["fields"]
        self.assertEqual(node["unreduced_z"], {"integer_hex": "0x8"})
        self.assertEqual(node["minimum_risk"], {"fraction": [{"integer_hex": "0x1"}, {"integer_hex": "0x4"}]})

    def test_unbounded_exact_world_counts_beyond_decimal_parser_limit(self):
        count = 1 << 20000
        value = replace(self.fixtures[10], unreduced_z=4 * count, mine_counts=tuple((c, count) for c in CELLS))
        rebuilt = r.decode(r.encode(value))
        self.assertEqual(rebuilt.unreduced_z, 4 * count)
        self.assertEqual(rebuilt.mine_counts, value.mine_counts)

    def test_unicode_supplied_labels(self):
        value = replace(self.fixtures[1], host="합성 호스트")
        self.assertEqual(r.decode(r.encode(value)), value)

    def test_none_span_and_zero_are_distinct(self):
        na = self.fixtures[9]
        zero = replace(na, duration_ns=0)
        self.assertIsNone(r.decode(r.encode(na)).duration_ns)
        self.assertEqual(r.decode(r.encode(zero)).duration_ns, 0)
        self.assertNotEqual(r.encode(na), r.encode(zero))

    def test_every_owned_enum_member_used_in_valid_context(self):
        for arm in r.Arm:
            value = replace(self.fixtures[5], arm=arm)
            self.assertEqual(r.decode(r.encode(value)), value)
        for action in r.Action:
            value = replace(self.fixtures[6], action=action)
            self.assertEqual(r.decode(r.encode(value)), value)
        for status in r.Status:
            self.assertEqual(r.decode(r.encode(replace(self.fixtures[6], after_status=status))).after_status, status)
        for scope in r.DecisionScope:
            self.assertEqual(r.decode(r.encode(replace(self.fixtures[9], scope=scope))).scope, scope)
        for assertion in r.AssertionCategory:
            for status in r.EvaluationStatus:
                value = replace(self.fixtures[13], assertion=assertion, status=status)
                self.assertEqual(r.decode(r.encode(value)), value)
        for state in r.CompletionState:
            value = replace(self.fixtures[17], state=state)
            self.assertEqual(r.decode(r.encode(value)), value)
        for source in r.AcquisitionSource:
            value = replace(self.fixtures[12], source=source)
            self.assertEqual(r.decode(r.encode(value)), value)
        for presentation in r.TerminalPresentation:
            value = replace(self.fixtures[8], changes=(r.TerminalCellChange((2, 1), presentation),))
            self.assertEqual(r.decode(r.encode(value)), value)


class MalformedCodecTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = _fixtures()

    def test_unknown_kind_version_extra_missing_fields_every_family(self):
        for record in self.fixtures:
            for corruption in ("kind", "version", "extra", "missing", "envelope"):
                with self.subTest(family=type(record).__name__, corruption=corruption):
                    node = json.loads(r.encode(record))
                    if corruption == "kind":
                        node["kind"] = "os.system"
                    elif corruption == "version":
                        node["version"] = 2
                    elif corruption == "extra":
                        node["fields"]["unexpected"] = 0
                    elif corruption == "missing":
                        del node["fields"][next(iter(node["fields"]))]
                    else:
                        node["module"] = "subprocess"
                    with self.assertRaises(r.RecordError):
                        r.decode(_wire(node))

    def test_versions_never_coerce_bool_or_float(self):
        for version in (True, False, 1.0, "1", None, -1, 1 << 64):
            node = json.loads(r.encode(self.fixtures[0]))
            node["version"] = version
            with self.assertRaises(r.RecordError):
                r.decode(_wire(node))

    def test_duplicate_json_keys_in_envelope_and_nested_fields(self):
        raw = r.encode(self.fixtures[9])
        for corrupt in (raw.replace(b'"version":1', b'"version":1,"version":1'),
                        raw.replace(b'"duration_ns":null', b'"duration_ns":null,"duration_ns":null')):
            with self.assertRaises(r.RecordError):
                r.decode(corrupt)

    def test_noncanonical_bytes_utf8_and_exact_input_type(self):
        raw = r.encode(self.fixtures[9])
        node = json.loads(raw)
        for bad in (raw + b"\n", b" " + raw, json.dumps(node, indent=2).encode(),
                    raw.replace(b'"action_ordinal":0', b'"action_ordinal":-0'),
                    raw.replace(b'"scope"', b'"scop\\u0065"'), b"\xff", b"\xef\xbb\xbf" + raw,
                    raw.decode(), bytearray(raw), memoryview(raw), b"[]", b"null", b"{}", b"{"):
            with self.subTest(bad=type(bad).__name__), self.assertRaises(r.RecordError):
                r.decode(bad)
        # Also reject key reordering, even though it is semantically valid JSON.
        reordered = {"kind": node["kind"], "version": 1, "fields": node["fields"]}
        with self.assertRaises(r.RecordError):
            r.decode(json.dumps(reordered, separators=(",", ":")).encode())

    def test_arbitrary_class_module_injection(self):
        for field in ("__class__", "__module__", "module", "class", "pickle", "mine_layout", "hidden_truth"):
            node = json.loads(r.encode(self.fixtures[7]))
            node["fields"][field] = "subprocess.Popen"
            with self.assertRaises(r.RecordError):
                r.decode(_wire(node))

    def test_encoder_rejects_arbitrary_dataclasses_subclasses_and_spoofs(self):
        @dataclass(frozen=True)
        class Spoof:
            kind: str = "protocol_identity"
        class ProtocolSubclass(r.ProtocolIdentity):
            pass
        subclass = ProtocolSubclass("docs/a.md", SHA, OID, OID)
        for value in (Spoof(), subclass, {"kind": "protocol_identity"}, (), [], object(), 1, True, Fraction(1, 2)):
            with self.subTest(type=type(value).__name__), self.assertRaises(r.RecordError):
                r.encode(value)

    def test_encoder_revalidates_corrupted_records_and_nested_records(self):
        value = replace(self.fixtures[6])
        object.__setattr__(value, "input_us", True)
        with self.assertRaises(r.RecordError):
            r.encode(value)
        arm = replace(self.fixtures[5], board=replace(self.fixtures[4]))
        object.__setattr__(arm.board, "mines", 0.5)
        with self.assertRaises(r.RecordError):
            r.encode(arm)
        receipt = replace(self.fixtures[17], streams=(r.StreamDigest("actions", SHA, 12, 1),))
        object.__setattr__(receipt.streams[0], "record_count", True)
        with self.assertRaises(r.RecordError):
            r.encode(receipt)

    def test_all_integer_fields_reject_bool_float_nan_infinity_string(self):
        for value in self.fixtures:
            for field in fields(value):
                if type(getattr(value, field.name)) is int:
                    for invalid in (True, False, 1.0, float("nan"), float("inf"), -float("inf"), "1"):
                        with self.subTest(family=type(value).__name__, field=field.name, invalid=invalid):
                            with self.assertRaises(r.RecordError):
                                replace(value, **{field.name: invalid})

    def test_json_numbers_reject_floats_and_nonfinite_tokens(self):
        raw = r.encode(self.fixtures[9])
        for token in (b"0.0", b"1e0", b"NaN", b"Infinity", b"-Infinity", b"true"):
            with self.assertRaises(r.RecordError):
                r.decode(raw.replace(b'"duration_ns":null', b'"duration_ns":' + token))

    def test_fraction_tag_rejects_lossy_or_noncanonical_numbers(self):
        base = json.loads(r.encode(self.fixtures[10]))
        bad_pairs = ((True, {"integer_hex": "0x4"}),
                     ({"integer_hex": "0x2"}, {"integer_hex": "0x8"}),
                     ({"integer_hex": "0x1"}, {"integer_hex": "0x0"}),
                     ({"integer_hex": "0x1"}, {"integer_hex": "-0x4"}),
                     ({"integer_hex": "0x01"}, {"integer_hex": "0x4"}),
                     ({"integer_hex": "0X1"}, {"integer_hex": "0x4"}))
        for pair in bad_pairs:
            node = json.loads(_wire(base))
            node["fields"]["minimum_risk"] = {"fraction": list(pair)}
            with self.assertRaises(r.RecordError):
                r.decode(_wire(node))
        for probability in (0.25, True, "1/4", {"numerator": 1, "denominator": 4}):
            node = json.loads(_wire(base))
            node["fields"]["minimum_risk"] = probability
            with self.assertRaises(r.RecordError):
                r.decode(_wire(node))

    def test_nested_wrong_record_kind_rejected(self):
        node = json.loads(r.encode(self.fixtures[5]))
        node["fields"]["board"] = json.loads(r.encode(self.fixtures[0]))
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))


class SchemaInvariantTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = _fixtures()

    def test_paths_and_digests(self):
        for path in ("/absolute", "C:/a", "../a", "a/../b", "a//b", "a\\b", "./a", "a/"):
            with self.assertRaises(r.RecordError):
                replace(self.fixtures[2], path=path)
        for sha in ("A" * 64, "z" * 64, "a" * 63, b"a" * 64):
            with self.assertRaises(r.RecordError):
                replace(self.fixtures[0], sha256=sha)
        with self.assertRaises(r.RecordError):
            replace(self.fixtures[0], blob_id="b" * 39)

    def test_str_subclasses_and_integer_subclasses_rejected(self):
        class S(str):
            pass
        class I(int):
            pass
        with self.assertRaises(r.RecordError):
            replace(self.fixtures[1], host=S("host"))
        with self.assertRaises(r.RecordError):
            replace(self.fixtures[4], width=I(3))

    def test_coordinates_and_board_bounds(self):
        for cell in ((-1, 0), (True, 0), (0.0, 0), (0,), [0, 0], (0, 1 << 64), ("0", 0)):
            with self.assertRaises(r.RecordError):
                replace(self.fixtures[6], target=cell)
        for changes in (dict(first_click=(3, 0)), dict(first_click=(0, 2)), dict(width=0),
                        dict(height=-1), dict(mines=6), dict(game_index=1 << 64)):
            with self.assertRaises(r.RecordError):
                replace(self.fixtures[4], **changes)
        with self.assertRaises(r.RecordError):
            replace(self.fixtures[13], targets=((9, 9),))

    def test_physical_cost_local_constraints(self):
        for changes in (dict(input_us=-1), dict(cumulative_us=-1), dict(cumulative_us=126004),
                        dict(cumulative_us=126006), dict(action_ordinal=-1), dict(input_us=1 << 64)):
            with self.assertRaises(r.RecordError):
                replace(self.fixtures[6], **changes)
        value = replace(self.fixtures[6], action_ordinal=1, cumulative_us=252010)
        self.assertEqual(r.decode(r.encode(value)), value)

    def test_invalid_action_status_arm_provenance_and_scope(self):
        for value, field in ((self.fixtures[6], "action"), (self.fixtures[6], "after_status"),
                             (self.fixtures[5], "arm"), (self.fixtures[11], "category"), (self.fixtures[9], "scope")):
            for bad in ("UNREGISTERED", getattr(value, field).value, True, 0, None):
                with self.assertRaises(r.RecordError):
                    replace(value, **{field: bad})
        for index, field in ((6, "action"), (6, "after_status"), (5, "arm"), (11, "category")):
            node = json.loads(r.encode(self.fixtures[index]))
            node["fields"][field] = "UNREGISTERED"
            with self.assertRaises(r.RecordError):
                r.decode(_wire(node))

    def test_public_terminal_segregation_in_memory_and_on_wire(self):
        public, terminal = self.fixtures[7], self.fixtures[8]
        self.assertNotEqual(json.loads(r.encode(public))["kind"], json.loads(r.encode(terminal))["kind"])
        for changes in (terminal.changes, (r.TerminalCellChange((1, 0), r.TerminalPresentation.EXPLODED_MINE),)):
            with self.assertRaises(r.RecordError):
                replace(public, changes=changes)
        with self.assertRaises(r.RecordError):
            replace(terminal, changes=public.changes)
        for state in ("MINE", "EXPLODED_MINE", "WRONG_FLAG", "CORRECT_FLAG", -1, True):
            with self.assertRaises(r.RecordError):
                r.PublicCellChange((0, 0), "HIDDEN", state)
        node = json.loads(r.encode(terminal))
        node["kind"] = "public_effect"
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))
        node = json.loads(r.encode(public))
        node["fields"]["changes"][0]["mine"] = True
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))

    def test_public_clues_flags_unflags_and_status_transitions(self):
        for clue in range(9):
            value = replace(self.fixtures[7], changes=(r.PublicCellChange((0, 0), "HIDDEN", "CLUE_" + str(clue)),),
                            after_status=r.Status.WON)
            self.assertEqual(r.decode(r.encode(value)), value)
        for before, after in (("CLUE_1", "HIDDEN"), ("CLUE_1", "CLUE_2"), ("HIDDEN", "HIDDEN"), ("FLAGGED", "CLUE_1")):
            with self.assertRaises(r.RecordError):
                r.PublicCellChange((0, 0), before, after)
        with self.assertRaises(r.RecordError):
            replace(self.fixtures[7], before_status=r.Status.WON)
        with self.assertRaises(r.RecordError):
            replace(self.fixtures[8], terminal_status=r.Status.PLAYING)

    def test_duplicate_and_unsorted_cells_rejected_before_canonicalization(self):
        for cells in (((2, 1), (2, 1)), ((1, 1), (1, 0))):
            with self.assertRaises(r.RecordError):
                replace(self.fixtures[13], targets=cells)
        for index, field in ((10, "unresolved"), (10, "minimum_ties"), (10, "effective_p_union_m"), (13, "targets")):
            node = json.loads(r.encode(self.fixtures[index]))
            node["fields"][field].append(node["fields"][field][0])
            with self.assertRaises(r.RecordError):
                r.decode(_wire(node))
        with self.assertRaises(r.RecordError):
            replace(self.fixtures[7], changes=(self.fixtures[7].changes[0],) * 2)

    def test_guess_checkpoint_exact_local_premises(self):
        guess = self.fixtures[10]
        cases = (dict(guess_ordinal=0), dict(unreduced_z=0), dict(unreduced_z=9),
                 dict(mine_budget=0), dict(mine_budget=2), dict(physical_p=((0, 0),)),
                 dict(effective_p_union_m=()), dict(unresolved=CELLS[:-1]),
                 dict(public_clues=(((0, 0), 9),)), dict(public_clues=(((1, 0), 1),)),
                 dict(mine_counts=guess.mine_counts[:-1]), dict(probabilities=guess.probabilities[:-1]),
                 dict(mine_counts=tuple((c, 1) for c in CELLS)),
                 dict(probabilities=tuple((c, Fraction(1, 3)) for c in CELLS)),
                 dict(minimum_risk=Fraction(1, 3)), dict(minimum_risk=0.25),
                 dict(minimum_ties=CELLS[:-1]), dict(chosen_target=(2, 1)),
                 dict(eventual_outcome="WIN"))
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(r.RecordError):
                replace(guess, **changes)

    def test_guess_certainty_zero_one_and_duplicate_maps_rejected(self):
        guess = self.fixtures[10]
        for count in (0, 8, True, 2.0, -1):
            with self.assertRaises(r.RecordError):
                replace(guess, mine_counts=((CELLS[0], count),) + guess.mine_counts[1:])
        for field in ("public_clues", "mine_counts", "probabilities"):
            node = json.loads(r.encode(guess))
            node["fields"][field].append(node["fields"][field][0])
            with self.assertRaises(r.RecordError):
                r.decode(_wire(node))

    def test_nonuniform_minimum_tie_completeness(self):
        guess = self.fixtures[10]
        counts = (1, 1, 2, 4)
        value = replace(guess, mine_counts=tuple(zip(CELLS, counts)),
                        probabilities=tuple((c, Fraction(m, 8)) for c, m in zip(CELLS, counts)),
                        minimum_risk=Fraction(1, 8), minimum_ties=CELLS[:2])
        self.assertEqual(r.decode(r.encode(value)), value)
        with self.assertRaises(r.RecordError):
            replace(value, minimum_ties=CELLS[:1])

    def test_guess_target_must_be_first_tie_in_reading_order(self):
        guess = self.fixtures[10]
        self.assertEqual(guess.minimum_ties, ((1, 0), (2, 0), (0, 1), (1, 1)))
        self.assertEqual(guess.chosen_target, guess.minimum_ties[0])
        for target in guess.minimum_ties[1:]:
            with self.subTest(target=target):
                with self.assertRaises(r.RecordError):
                    replace(guess, chosen_target=target)
                node = json.loads(r.encode(guess))
                node["fields"]["chosen_target"] = list(target)
                with self.assertRaises(r.RecordError):
                    r.decode(_wire(node))
        # (x, y) sorting must not be silently repaired to the frozen (y, x) order.
        wrong_order = tuple(sorted(guess.minimum_ties))
        with self.assertRaises(r.RecordError):
            replace(guess, minimum_ties=wrong_order, chosen_target=wrong_order[0])
        node = json.loads(r.encode(guess))
        node["fields"]["minimum_ties"] = wrong_order
        node["fields"]["chosen_target"] = wrong_order[0]
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))

    def test_only_kp0_checkpoint_may_augment_physical_p(self):
        guess = self.fixtures[10]
        self.assertNotEqual(guess.physical_p, guess.effective_p_union_m)
        self.assertEqual(r.decode(r.encode(guess)), guess)
        for arm_kind in (r.Arm.CONTROL, r.Arm.K_CONTROL):
            with self.subTest(arm=arm_kind):
                arm = replace(guess.arm, arm=arm_kind)
                with self.assertRaises(r.RecordError):
                    replace(guess, arm=arm)
                node = json.loads(r.encode(guess))
                node["fields"]["arm"]["fields"]["arm"] = arm_kind.value
                with self.assertRaises(r.RecordError):
                    r.decode(_wire(node))
                valid = replace(guess, arm=arm, physical_p=guess.effective_p_union_m)
                self.assertEqual(r.decode(r.encode(valid)), valid)

    def test_all_control_provenance_categories_and_optional_witness(self):
        fallback = self.fixtures[11]
        self.assertEqual(r.decode(r.encode(replace(fallback, witness=None))).witness, None)
        for category, action in ((r.FlagCategory.CONTROL_SETUP_CHORD_FLAG, r.Action.CHORD),
                                 (r.FlagCategory.CONTROL_FLAG_TO_OPEN_SETUP, r.Action.OPEN)):
            value = replace(fallback, category=category, selected_plan_ref="selected-plan",
                            terminal_reveal=action, terminal_target=(1, 1))
            self.assertEqual(r.decode(r.encode(value)), value)
        for changes in (dict(selected_plan_ref="not-none"), dict(terminal_reveal=r.Action.OPEN),
                        dict(terminal_target=(1, 1)), dict(flag_ordinal=4), dict(cell=(0, 0)),
                        dict(category=r.FlagCategory.CONTROL_SETUP_CHORD_FLAG)):
            with self.assertRaises(r.RecordError):
                replace(fallback, **changes)

    def test_witness_cannot_claim_unproductive_or_nonadjacent_chord(self):
        witness = self.fixtures[11].witness
        for changes in (dict(directly_opened_safe_cells=()), dict(physical_flag_neighbors=((9, 9),)),
                        dict(directly_opened_safe_cells=((2, 1),)), dict(physical_flag_neighbors=((2, 1), (2, 1)))):
            with self.assertRaises(r.RecordError):
                replace(witness, **changes)

    def test_non_ww_pair_cannot_have_ww_delta(self):
        pair = self.fixtures[14]
        for control in r.Outcome:
            for kp0 in r.Outcome:
                if control is r.Outcome.WIN and kp0 is r.Outcome.WIN:
                    continue
                for delta in (-126005, 0, 126005):
                    with self.subTest(control=control, kp0=kp0, delta=delta):
                        with self.assertRaises(r.RecordError):
                            replace(pair, control_outcome=control, kp0_outcome=kp0, ww_delta_us=delta)
                        node = json.loads(r.encode(pair))
                        node["fields"].update(control_outcome=control.value, kp0_outcome=kp0.value, ww_delta_us=delta)
                        with self.assertRaises(r.RecordError):
                            r.decode(_wire(node))
                value = replace(pair, control_outcome=control, kp0_outcome=kp0, ww_delta_us=None)
                self.assertEqual(r.decode(r.encode(value)), value)
        with self.assertRaises(r.RecordError):
            replace(pair, ww_delta_us=Fraction(1, 2))

    def test_ww_pair_requires_exact_delta_including_valid_zero(self):
        pair = self.fixtures[14]
        with self.assertRaises(r.RecordError):
            replace(pair, ww_delta_us=None)
        node = json.loads(r.encode(pair))
        node["fields"]["ww_delta_us"] = None
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))
        for delta in (-126005, 0, 126005):
            value = replace(pair, ww_delta_us=delta)
            rebuilt = r.decode(r.encode(value))
            self.assertEqual(rebuilt, value)
            self.assertIs(type(rebuilt.ww_delta_us), int)

    def test_g5_exposure_uses_only_two_qualifying_categories(self):
        self.assertEqual(tuple(c.value for c in r.FlagCategory),
                         ("CONTROL_SETUP_CHORD_FLAG", "CONTROL_FALLBACK_FLAG", "CONTROL_FLAG_TO_OPEN_SETUP"))
        for diagnostic, fallback, flag_to_open, exposed in (
                (5, 0, 0, False), (0, 1, 0, True), (0, 0, 1, True),
                (0, 0, 0, False), (5, 1, 1, True)):
            with self.subTest(counts=(diagnostic, fallback, flag_to_open)):
                summary = r.G5ExposureSummary(diagnostic, fallback, flag_to_open)
                self.assertIs(summary.is_exposed, exposed)
                pair = replace(self.fixtures[14], g5=summary)
                rebuilt = r.decode(r.encode(pair))
                self.assertEqual(rebuilt.g5.diagnostic_setup_chord_flags, diagnostic)
                self.assertIs(rebuilt.g5.is_exposed, exposed)

    def test_g5_codec_rejects_old_or_malformed_count_fields(self):
        for current, old in (("diagnostic_setup_chord_flags", "qualifying_setup_chord_flags"),
                             ("qualifying_flag_to_open_setup_flags", "qualifying_flag_to_open_flags")):
            for keep_current in (False, True):
                node = json.loads(r.encode(self.fixtures[14]))
                g5 = node["fields"]["g5"]
                g5[old] = g5[current]
                if not keep_current:
                    del g5[current]
                with self.assertRaises(r.RecordError):
                    r.decode(_wire(node))
        node = json.loads(r.encode(self.fixtures[14]))
        node["fields"]["g5"]["is_exposed"] = True
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))

    def test_p3_status_vocabulary_is_exactly_pass_fail_incomplete(self):
        self.assertEqual(tuple(r.P3Status.__members__), ("PASS", "FAIL", "INCOMPLETE"))
        self.assertFalse(hasattr(r.P3Status, "NOT_EVALUATED"))
        for status in r.P3Status:
            value = replace(self.fixtures[14], p3_status=status)
            self.assertEqual(r.decode(r.encode(value)), value)
        for invalid in ("NOT_EVALUATED", "MATCH", "DIVERGENCE", "NOT_APPLICABLE"):
            node = json.loads(r.encode(self.fixtures[14]))
            node["fields"]["p3_status"] = invalid
            with self.assertRaises(r.RecordError):
                r.decode(_wire(node))

    def test_corpus_count_exclusions_order_and_ownership(self):
        corpus = self.fixtures[3]
        for changes in (dict(n=2), dict(ordered_indices=(107, 107, 112)), dict(ordered_indices=(107, 99, 112)),
                        dict(exclusions=(107,)), dict(exclusions=(105, 105)), dict(exclusions=(106, 105)),
                        dict(ordered_indices=[107, 100, 112]), dict(low=113), dict(frame_label="한글")):
            with self.assertRaises(r.RecordError):
                replace(corpus, **changes)

    def test_resource_sample_exact_totals(self):
        for changes in (dict(combined_bytes=19), dict(worker_bytes=-1), dict(elapsed_ns=-1), dict(method="RSS")):
            with self.assertRaises(r.RecordError):
                replace(self.fixtures[16], **changes)

    def test_completion_is_not_a_research_verdict(self):
        receipt = self.fixtures[17]
        for state in ("PASS", "RESEARCH_PASS", r.EvaluationStatus.PASS, True):
            with self.assertRaises(r.RecordError):
                replace(receipt, state=state)
        node = json.loads(r.encode(receipt))
        node["fields"]["verdict"] = "RESEARCH_PASS"
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))
        for streams in ((receipt.streams[0],) * 2, receipt.streams[::-1], list(receipt.streams)):
            with self.assertRaises(r.RecordError):
                replace(receipt, streams=streams)
        with self.assertRaises(r.RecordError):
            r.StreamDigest("actions", SHA, 1, -1)


def _named_change(values, name, value):
    return tuple((key, value if key == name else current) for key, current in values)


def _certificate_audit_fixture(source="LOCAL"):
    # Literal public evidence only; no certificate verifier, solver or runner.
    observation = ((1, -2),) if source == "LOCAL" else ((1, -2, -2),)
    premises = (("source", source), ("observation", observation), ("num_mines", 1),
                ("target", (1, 0)), ("retained_mines", ()), ("status", "PLAYING"))
    if source == "LOCAL":
        premises += (("clue", (0, 0)),)
        facts = (("target", (1, 0)), ("clue", (0, 0)), ("clue_value", 1),
                 ("physical_flags", ()), ("logical_mines", ()), ("unresolved", ((1, 0),)),
                 ("residual", 1), ("antecedents", ()))
    else:
        premises += (("total_worlds", 1), ("mine_worlds", (((1, 0), 1), ((2, 0), 0))),
                     ("exact_reached", True))
        facts = (("target", (1, 0)), ("total_worlds", 1), ("mine_worlds", 1),
                 ("antecedents", ()), ("oracle_a_status", "PASS"),
                 ("oracle_a_variable_count", 2), ("oracle_a_envelope", 18),
                 ("oracle_a_reason", None), ("arithmetic_evidence", "SYNTHETIC_EXACT_PUBLIC_COUNTS"))
    digest = r.certificate_premises_digest(premises)
    acquisition = r.AcquisitionRecord(2, 1, (1, 0), r.AcquisitionSource[source], "sha256:" + digest, digest)
    return r.CertificateAuditRecord(2, acquisition, premises, (), r.AuditStatus.PASS, "PASS",
                                    "SYNTHETIC_PUBLIC_PROOF", (), ((1, 0),), facts)


def _oracle_snapshot_fixture():
    cells = ((1, 0), (0, 1), (1, 1))
    return r.OracleBExactSnapshot(cells, cells, (), 3, tuple((cell, 1) for cell in cells),
                                  (), (), Fraction(1, 3), cells,
                                  "SYNTHETIC_SHARED_EVIDENCE", "SYNTHETIC_KERNEL", ((1, -2), (-2, -2)))


def _oracle_audit_fixture():
    snapshot = _oracle_snapshot_fixture()
    digest = r.oracle_b_snapshot_digest(snapshot)
    return r.OracleBAuditRecord(2, "D", (), ((1, -2), (-2, -2)), (), SHA, digest, digest,
                                r.AuditStatus.PASS, (), snapshot, snapshot)


def _determinism_summary_fixtures():
    return (r.DeterminismAuditRecord(False, None, None, None, None),
            r.DeterminismAuditRecord(True, SHA, None, r.AuditStatus.INCOMPLETE, None),
            r.DeterminismAuditRecord(True, SHA, SHA, r.AuditStatus.PASS, None),
            r.DeterminismAuditRecord(True, SHA, "c" * 64, r.AuditStatus.FAIL, "acquisitions[0].cell"))


class DurableCertificateAuditTests(unittest.TestCase):
    def test_local_and_exact_full_named_premises_roundtrip(self):
        for source in ("LOCAL", "EXACT_GLOBAL"):
            with self.subTest(source=source):
                original = _certificate_audit_fixture(source)
                encoded = r.encode(original)
                rebuilt = r.decode(encoded)
                self.assertIs(type(rebuilt), r.CertificateAuditRecord)
                self.assertEqual(rebuilt, original)
                self.assertEqual(r.encode(rebuilt), encoded)
                self.assertEqual(rebuilt.acquisition.certificate_sha256,
                                 r.certificate_premises_digest(rebuilt.certificate_premises))
                self.assertEqual(rebuilt.certificate_premises, original.certificate_premises)
                self.assertEqual(rebuilt.verifier_facts, original.verifier_facts)

    def test_source_specific_named_fields_reject_missing_extra_unknown_and_order(self):
        for source in ("LOCAL", "EXACT_GLOBAL"):
            value = _certificate_audit_fixture(source)
            for field in ("certificate_premises", "verifier_facts"):
                named = getattr(value, field)
                bad = [named[:i] + named[i + 1:] for i in range(len(named))]
                bad += [named + (("extra", 0),), (("unknown", named[0][1]),) + named[1:],
                        named[::-1], named + (named[-1],)]
                for candidate in bad:
                    with self.subTest(source=source, field=field, candidate=candidate), self.assertRaises(r.RecordError):
                        replace(value, **{field: candidate})
            foreign = (("total_worlds", 1),) if source == "LOCAL" else (("clue", (0, 0)),)
            with self.assertRaises(r.RecordError):
                replace(value, certificate_premises=value.certificate_premises + foreign)

    def test_named_evidence_and_nested_payloads_reject_mutable_containers(self):
        value = _certificate_audit_fixture()
        for field in ("certificate_premises", "verifier_facts", "prior_certificate_sha256s",
                      "owned_m_before", "owned_m_after"):
            for bad in ([], {}, set()):
                with self.subTest(field=field, bad=type(bad)), self.assertRaises(r.RecordError):
                    replace(value, **{field: bad})
        for name, bad in (("target", [1, 0]), ("observation", [[1, -2]]),
                          ("observation", ([1, -2],)), ("retained_mines", {(1, 0)}),
                          ("clue", {"x": 0, "y": 0})):
            with self.subTest(name=name), self.assertRaises(r.RecordError):
                replace(value, certificate_premises=_named_change(value.certificate_premises, name, bad))
        with self.assertRaises(r.RecordError):
            replace(value, verifier_facts=(list(value.verifier_facts[0]),) + value.verifier_facts[1:])

    def test_certificate_integer_bool_text_and_coordinate_types_are_exact(self):
        for source in ("LOCAL", "EXACT_GLOBAL"):
            value = _certificate_audit_fixture(source)
            cases = (("num_mines", True), ("num_mines", 1.0), ("num_mines", "1"),
                     ("target", (True, 0)), ("target", (1.0, 0)), ("target", (-1, 0)),
                     ("status", r.Status.PLAYING), ("source", r.AcquisitionSource.LOCAL))
            if source == "EXACT_GLOBAL":
                cases += (("total_worlds", True), ("total_worlds", 1.0),
                          ("mine_worlds", (((1, 0), True),)), ("exact_reached", 1))
            for name, bad in cases:
                with self.subTest(source=source, name=name, bad=bad), self.assertRaises(r.RecordError):
                    replace(value, certificate_premises=_named_change(value.certificate_premises, name, bad))
            integer_names = ("clue_value", "residual") if source == "LOCAL" else (
                "total_worlds", "mine_worlds", "oracle_a_variable_count", "oracle_a_envelope")
            for name in integer_names:
                for bad in (True, 1.0, "1"):
                    with self.subTest(source=source, field=name, bad=bad), self.assertRaises(r.RecordError):
                        replace(value, verifier_facts=_named_change(value.verifier_facts, name, bad))

    def test_certificate_cells_reject_duplicates_wrong_order_and_bad_observations(self):
        value = _certificate_audit_fixture()
        for cells in (((1, 0), (1, 0)), ((0, 1), (1, 0)), ([1, 0],), ((True, 0),)):
            with self.subTest(cells=cells), self.assertRaises(r.RecordError):
                replace(value, certificate_premises=_named_change(value.certificate_premises, "retained_mines", cells))
            for name in ("physical_flags", "logical_mines", "unresolved", "antecedents"):
                with self.subTest(name=name, cells=cells), self.assertRaises(r.RecordError):
                    replace(value, verifier_facts=_named_change(value.verifier_facts, name, cells))
        for observation in ((), ((),), ((1, -2), (1,)), ((True, -2),), ((1.0, -2),),
                            ((-1, -2),), ((9, -2),), (("1", -2),)):
            with self.subTest(observation=observation), self.assertRaises(r.RecordError):
                replace(value, certificate_premises=_named_change(value.certificate_premises, "observation", observation))

    def test_acquisition_boundary_source_target_ref_and_full_premise_digest_are_bound(self):
        value = _certificate_audit_fixture()
        for changes in (dict(action_ordinal=3), dict(cell=(2, 0)),
                        dict(source=r.AcquisitionSource.EXACT_GLOBAL), dict(certificate_ref="unbound"),
                        dict(certificate_sha256=SHA, certificate_ref="sha256:" + SHA)):
            with self.subTest(changes=changes), self.assertRaises(r.RecordError):
                replace(value, acquisition=replace(value.acquisition, **changes))
        changed = _named_change(value.certificate_premises, "num_mines", 2)
        self.assertNotEqual(r.certificate_premises_digest(changed), value.acquisition.certificate_sha256)
        with self.assertRaises(r.RecordError):
            replace(value, certificate_premises=changed)
        for changes in (dict(action_ordinal=3), dict(owned_m_before=((0, 0),)), dict(owned_m_after=())):
            with self.assertRaises(r.RecordError):
                replace(value, **changes)

    def test_verifier_facts_target_clue_counts_and_status_are_bound(self):
        for source in ("LOCAL", "EXACT_GLOBAL"):
            value = _certificate_audit_fixture(source)
            cases = (("target", (2, 0)),)
            cases += (("clue", (1, 0)), ("clue_value", 2)) if source == "LOCAL" else (
                ("total_worlds", 2), ("mine_worlds", 2))
            for name, bad in cases:
                with self.subTest(source=source, name=name), self.assertRaises(r.RecordError):
                    replace(value, verifier_facts=_named_change(value.verifier_facts, name, bad))
        value = _certificate_audit_fixture()
        failed = replace(value, status=r.AuditStatus.FAIL, verifier_status="FAIL")
        self.assertEqual(r.decode(r.encode(failed)), failed)
        missing = replace(failed, verifier_facts=())
        self.assertEqual(r.decode(r.encode(missing)), missing)
        for status in (r.AuditStatus.PASS, r.AuditStatus.INCOMPLETE):
            with self.assertRaises(r.RecordError):
                replace(failed, status=status)
        for status in ("FAIL", "INCOMPLETE", "DEFER", True):
            with self.assertRaises(r.RecordError):
                replace(value, verifier_status=status)
        with self.assertRaises(r.RecordError):
            replace(value, verifier_facts=())
        incomplete = replace(value, status=r.AuditStatus.INCOMPLETE, detail="PRIOR_AUTHORITY_MISSING")
        self.assertEqual(r.decode(r.encode(incomplete)), incomplete)


class DurableOracleBAuditTests(unittest.TestCase):
    def test_pass_exact_snapshot_fraction_and_materialized_observation_roundtrip(self):
        original = _oracle_audit_fixture()
        encoded = r.encode(original)
        rebuilt = r.decode(encoded)
        self.assertIs(type(rebuilt), r.OracleBAuditRecord)
        self.assertEqual(rebuilt, original)
        self.assertEqual(r.encode(rebuilt), encoded)
        self.assertIs(type(rebuilt.expected), r.OracleBExactSnapshot)
        self.assertIs(type(rebuilt.actual.minimum_risk), Fraction)
        self.assertEqual(rebuilt.actual.minimum_risk, Fraction(1, 3))
        self.assertEqual(rebuilt.actual.materialized_observation, ((1, -2), (-2, -2)))
        self.assertEqual(rebuilt.expected.shared_kernel_evidence, "SYNTHETIC_SHARED_EVIDENCE")
        self.assertEqual(rebuilt.expected.kernel, "SYNTHETIC_KERNEL")
        self.assertEqual(len(fields(rebuilt.expected)), 12)
        self.assertEqual(json.loads(encoded)["fields"]["expected"]["minimum_risk"],
                         {"fraction": [{"integer_hex": "0x1"}, {"integer_hex": "0x3"}]})
        with self.assertRaises(r.RecordError):
            r.encode(rebuilt.expected)

    def test_full_snapshot_mismatch_and_digest_collision_cannot_pass(self):
        value = _oracle_audit_fixture()
        changed = replace(value.actual, kernel="DIFFERENT_KERNEL")
        with self.assertRaises(r.RecordError):
            replace(value, actual=changed, actual_digest=r.oracle_b_snapshot_digest(changed))
        with patch.object(r, "oracle_b_snapshot_digest", return_value=SHA):
            with self.assertRaises(r.RecordError):
                replace(value, actual=changed, expected_digest=SHA, actual_digest=SHA)
        failed = replace(value, actual=changed, actual_digest=r.oracle_b_snapshot_digest(changed),
                         status=r.AuditStatus.FAIL, differences=("kernel",))
        self.assertEqual(r.decode(r.encode(failed)), failed)
        self.assertEqual(r.decode(r.encode(failed)).actual.kernel, "DIFFERENT_KERNEL")

    def test_nonpassing_requires_reason_and_actual_presence_matches_digest(self):
        value = _oracle_audit_fixture()
        for changes in (dict(actual=None), dict(actual_digest=None),
                        dict(actual=None, actual_digest=None), dict(status=r.AuditStatus.FAIL),
                        dict(status=r.AuditStatus.INCOMPLETE)):
            with self.subTest(changes=changes), self.assertRaises(r.RecordError):
                replace(value, **changes)
        incomplete = replace(value, actual=None, actual_digest=None, status=r.AuditStatus.INCOMPLETE,
                             differences=("PUBLIC_PREREQUISITE_MISSING",))
        self.assertEqual(r.decode(r.encode(incomplete)), incomplete)

    def test_nonpositive_world_counts_retained_only_as_failed_evidence(self):
        value = _oracle_audit_fixture()
        for worlds in (0, -1):
            snapshot = replace(value.expected, total_worlds=worlds)
            digest = r.oracle_b_snapshot_digest(snapshot)
            changes = dict(expected=snapshot, actual=snapshot, expected_digest=digest, actual_digest=digest)
            with self.subTest(worlds=worlds), self.assertRaises(r.RecordError):
                replace(value, **changes)
            failed = replace(value, **changes, status=r.AuditStatus.FAIL,
                             differences=("POSITIVE_EXACT_INTEGER_WORLD_COUNT",))
            self.assertEqual(r.decode(r.encode(failed)), failed)
        for worlds in (True, False, 1.0, Fraction(1), "1"):
            with self.subTest(worlds=worlds), self.assertRaises(r.RecordError):
                replace(value.expected, total_worlds=worlds)

    def test_snapshot_closed_types_and_order_reject_mutable_float_and_bool(self):
        value = _oracle_snapshot_fixture()
        for field in ("unresolved_cells", "frontier_cells", "unconstrained_cells", "G0", "G1", "minimum_risk_cells"):
            for cells in ([], set(), {}, ((1, 0), (1, 0)), ((0, 1), (1, 0)), ((True, 0),)):
                with self.subTest(field=field, cells=cells), self.assertRaises(r.RecordError):
                    replace(value, **{field: cells})
        for counts in ([], {"cell": 1}, (((1, 0), True),), (((1, 0), 1.0),),
                       (((1, 0), 1), ((1, 0), 1)), (((0, 1), 1), ((1, 0), 1))):
            with self.subTest(counts=counts), self.assertRaises(r.RecordError):
                replace(value, mine_worlds=counts)
        for risk in (True, 0.5, (1, 2), "1/2", {"fraction": [1, 2]}):
            with self.assertRaises(r.RecordError):
                replace(value, minimum_risk=risk)
        for observation in ([[1, -2]], ((1, -2), (1,)), ((True,),), ((1.0,),), ((-1,),)):
            with self.assertRaises(r.RecordError):
                replace(value, materialized_observation=observation)
        for field in ("shared_kernel_evidence", "kernel"):
            for bad in (None, "", [], True):
                with self.assertRaises(r.RecordError):
                    replace(value, **{field: bad})

    def test_oracle_identity_phase_digests_observation_and_reasons_are_strict(self):
        value = _oracle_audit_fixture()
        bad_by_field = {
            "action_ordinal": (0, -1, True, 2.0), "phase": ("A", "d", None, True),
            "logical_mines": ([], ((1, 0), (1, 0)), ((0, 1), (1, 0))),
            "public_observation": ([[1]], (), ((True,),), ((1.0,),)),
            "prior_certificate_sha256s": ([], ("A" * 64,), (b"a" * 64,)),
            "status": ("PASS", r.P3Status.PASS, None), "differences": ([], {}, ("",)),
            "expected": (None, {}, ()), "actual": ({}, ()),
        }
        for field, bad_values in bad_by_field.items():
            for bad in bad_values:
                with self.subTest(field=field, bad=bad), self.assertRaises(r.RecordError):
                    replace(value, **{field: bad})
        for field in ("input_digest", "expected_digest", "actual_digest"):
            for bad in ("A" * 64, "g" * 64, "a" * 63, b"a" * 64, True):
                with self.subTest(field=field, bad=bad), self.assertRaises(r.RecordError):
                    replace(value, **{field: bad})
        for field in ("expected_digest", "actual_digest"):
            with self.assertRaises(r.RecordError):
                replace(value, **{field: SHA})


class DurableDeterminismSummaryTests(unittest.TestCase):
    def test_all_four_states_are_exact_canonical_roundtrips(self):
        for original in _determinism_summary_fixtures():
            with self.subTest(status=original.status):
                encoded = r.encode(original)
                self.assertEqual(r.decode(encoded), original)
                self.assertEqual(r.encode(r.decode(encoded)), encoded)
                self.assertEqual({field.name for field in fields(original)},
                                 {"selected", "first_digest", "repeat_digest", "status", "first_difference_path"})
        self.assertEqual(tuple(r.AuditStatus.__members__), ("PASS", "FAIL", "INCOMPLETE"))

    def test_unselected_has_no_status_digests_or_divergence(self):
        value = _determinism_summary_fixtures()[0]
        for field, bad in (("first_digest", SHA), ("repeat_digest", SHA),
                           ("status", r.AuditStatus.PASS), ("first_difference_path", "physical_inputs")):
            with self.assertRaises(r.RecordError):
                replace(value, **{field: bad})
        for selected in (0, 1, None, "yes"):
            with self.assertRaises(r.RecordError):
                replace(value, selected=selected)

    def test_selected_missing_repeat_requires_incomplete_first_digest_and_no_path(self):
        value = _determinism_summary_fixtures()[1]
        for changes in (dict(first_digest=None), dict(status=None), dict(status=r.AuditStatus.PASS),
                        dict(status=r.AuditStatus.FAIL), dict(first_difference_path="input"),
                        dict(repeat_digest=SHA)):
            with self.subTest(changes=changes), self.assertRaises(r.RecordError):
                replace(value, **changes)

    def test_complete_pass_requires_equal_digests_fail_requires_explicit_difference(self):
        passed, failed = _determinism_summary_fixtures()[2:]
        for changes in (dict(repeat_digest="c" * 64), dict(status=None),
                        dict(status=r.AuditStatus.INCOMPLETE), dict(first_difference_path="input")):
            with self.assertRaises(r.RecordError):
                replace(passed, **changes)
        for path in (None, "", 0, True, (), {}):
            with self.assertRaises(r.RecordError):
                replace(failed, first_difference_path=path)
        collision = replace(failed, repeat_digest=failed.first_digest)
        self.assertIs(r.decode(r.encode(collision)).status, r.AuditStatus.FAIL)
        for value in (passed, failed):
            for field in ("first_digest", "repeat_digest"):
                for bad in ("A" * 64, "a" * 63, b"a" * 64, True):
                    with self.assertRaises(r.RecordError):
                        replace(value, **{field: bad})


class DurableAuditCodecAndTransportTests(unittest.TestCase):
    def fixtures(self):
        oracle = _oracle_audit_fixture()
        incomplete = replace(oracle, actual=None, actual_digest=None, status=r.AuditStatus.INCOMPLETE,
                             differences=("PUBLIC_PREREQUISITE_MISSING",))
        changed = replace(oracle.actual, shared_kernel_evidence="DIFFERENT_SHARED_EVIDENCE")
        failed = replace(oracle, actual=changed, actual_digest=r.oracle_b_snapshot_digest(changed),
                         status=r.AuditStatus.FAIL, differences=("shared_kernel_evidence",))
        return (_certificate_audit_fixture(), _certificate_audit_fixture("EXACT_GLOBAL"),
                oracle, incomplete, failed) + _determinism_summary_fixtures()

    def test_new_top_level_fields_reject_unknown_missing_extra_and_research_verdict(self):
        for value in self.fixtures():
            original = r.encode(value)
            for field in json.loads(original)["fields"]:
                node = json.loads(original)
                del node["fields"][field]
                with self.subTest(kind=type(value).__name__, missing=field), self.assertRaises(r.RecordError):
                    r.decode(_wire(node))
            for field in ("payload", "research_verdict", "e3_trigger", "__class__"):
                node = json.loads(original)
                node["fields"][field] = "PASS"
                with self.assertRaises(r.RecordError):
                    r.decode(_wire(node))
            node = json.loads(original)
            node["kind"] = "unknown_audit_kind"
            with self.assertRaises(r.RecordError):
                r.decode(_wire(node))

    def test_nested_snapshot_and_named_evidence_wire_shapes_are_closed(self):
        original = r.encode(_oracle_audit_fixture())
        for field in json.loads(original)["fields"]["expected"]:
            node = json.loads(original)
            del node["fields"]["expected"][field]
            with self.subTest(missing=field), self.assertRaises(r.RecordError):
                r.decode(_wire(node))
        node = json.loads(original)
        node["fields"]["expected"]["hidden_truth"] = []
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))
        for source in ("LOCAL", "EXACT_GLOBAL"):
            original = r.encode(_certificate_audit_fixture(source))
            for field in ("certificate_premises", "verifier_facts"):
                for mutation in ("missing", "extra", "unknown", "order", "map"):
                    node = json.loads(original)
                    named = node["fields"][field]
                    if mutation == "missing":
                        named.pop()
                    elif mutation == "extra":
                        named.append(["extra", 0])
                    elif mutation == "unknown":
                        named[0][0] = "unknown"
                    elif mutation == "order":
                        named.reverse()
                    else:
                        node["fields"][field] = dict(named)
                    with self.subTest(source=source, field=field, mutation=mutation), self.assertRaises(r.RecordError):
                        r.decode(_wire(node))

    def test_wire_fraction_and_exact_count_encodings_reject_bool_float_and_noncanonical(self):
        original = r.encode(_oracle_audit_fixture())
        for field in ("total_worlds", "minimum_risk"):
            for bad in (True, 1.0, {"integer_hex": "0x01"}, {"arbitrary": 1}):
                node = json.loads(original)
                node["fields"]["expected"][field] = bad
                with self.subTest(field=field, bad=bad), self.assertRaises(r.RecordError):
                    r.decode(_wire(node))
        node = json.loads(original)
        node["fields"]["expected"]["minimum_risk"] = {
            "fraction": [{"integer_hex": "0x2"}, {"integer_hex": "0x6"}]}
        with self.assertRaises(r.RecordError):
            r.decode(_wire(node))

    def test_new_records_are_deeply_frozen_and_encoder_revalidates_corruption(self):
        for value in self.fixtures():
            self.assertFalse(hasattr(value, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)
        oracle = _oracle_audit_fixture()
        with self.assertRaises(FrozenInstanceError):
            oracle.expected.kernel = "changed"
        with self.assertRaises(TypeError):
            oracle.expected.materialized_observation[0][0] = 0
        object.__setattr__(oracle.expected, "total_worlds", True)
        with self.assertRaises(r.RecordError):
            r.encode(oracle)
        certificate = _certificate_audit_fixture()
        object.__setattr__(certificate.acquisition, "certificate_sha256", SHA)
        with self.assertRaises(r.RecordError):
            r.encode(certificate)

    def test_unchanged_i2_store_transports_every_new_record_and_all_summary_states(self):
        values = self.fixtures()
        canonical = tuple(r.encode(value) for value in values)
        self.assertEqual({json.loads(data)["kind"] for data in canonical},
                         {"certificate_audit", "oracle_b_audit", "determinism_audit"})
        self.assertEqual(tuple(r.decode(data) for data in canonical), values)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            writer = store.StreamWriter(root, "audits")
            try:
                for index, value in enumerate(values):
                    writer.append((index,), value)
                checkpoint = writer.checkpoint()
                sealed = writer.seal()
                self.assertEqual((checkpoint.stream_name, checkpoint.sha256, checkpoint.byte_length, checkpoint.record_count),
                                 (sealed.name, sealed.sha256, sealed.byte_length, sealed.record_count))
                self.assertEqual(checkpoint.last_key, (len(values) - 1,))
                visited = []
                scanned = store.scan_stream(root, "audits", visit=lambda key, value: visited.append((key, value)))
                self.assertEqual(scanned, sealed)
                self.assertEqual(visited, [((index,), value) for index, value in enumerate(values)])
                self.assertEqual(tuple(r.encode(value) for _, value in visited), canonical)
                expected = b"".join(_wire([index]) + b"\t" + data + b"\n"
                                    for index, data in enumerate(canonical))
                self.assertEqual(writer.path.read_bytes(), expected)
                self.assertEqual(sealed.sha256, hashlib.sha256(expected).hexdigest())
                self.assertEqual(sealed.record_count, len(values))
            finally:
                writer.close()


if __name__ == "__main__":
    unittest.main()
