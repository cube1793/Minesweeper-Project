"""Bounded R0 harness fixtures. No actual R0 or production bootstrap workload."""

from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
import inspect
import base64
from hashlib import shake_256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments import program_k_e2_r0_harness as h
from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_records as records
from experiments import program_k_e2_execution as execution
from experiments import program_k_e2_operational as operational
from experiments import program_k_e2_readiness as readiness
from experiments import program_k_e2_physical as physical


# RECEIPT_TESTS_BEGIN
# Exact accepted operational receipt bytes, embedded solely as a portable test fixture.
_ACCEPTED_RECEIPT_FIXTURE = (
    b"{\"accepted_i8_ancestor\":\"9071469e2e4a884722ea02e2faea3441d916876c\",\"actual_e2_run\":false,\"ahead\":0,\"amendment_"
    b"byte_length\":58052,\"amendment_sha256\":\"5a833132c884b6cdbe822c8a7cc40f52342e03df6557b39025e91e34b6d7b6bf\",\"base"
    b"_protocol_blob\":\"3351017f0f0116be00917be3ff95312120f43117\",\"base_protocol_byte_length\":57841,\"base_protocol_fr"
    b"eeze_commit\":\"6d3eb456d72632d24e9cab14bdeea0cffd279092\",\"base_protocol_sha256\":\"10b1055a6e1bcab8e03ab504755c9c"
    b"9d655d5457800318396afb6e31497ba2fa\",\"behind\":0,\"board_generation\":false,\"classification\":\"non-research operati"
    b"onal evidence\",\"committed_candidate_blobs\":{\"experiments/program_k_e2_analysis.py\":\"509a5e7641525df5b3e2cb3a6a"
    b"2cd4f0f4bcff40\",\"experiments/program_k_e2_audit.py\":\"1570ae60bce658257bf3e7afe0a34cddbbf49335\",\"experiments/pr"
    b"ogram_k_e2_execution.py\":\"0f584fcdc268177007ac16ab57226c8225cfd39d\",\"experiments/program_k_e2_operational.py\":"
    b"\"91c4fb34573b1e0918652d506007c99f2bb0cf8a\",\"experiments/program_k_e2_qualification.py\":\"94bfeb71d754f671ab44e8"
    b"7523c8c44ed8462d4e\",\"experiments/program_k_e2_readiness.py\":\"5fea5c48b7ce4dfdbdc1de04df95d3e27180042f\",\"tests/"
    b"test_program_k_e2_analysis.py\":\"1fa09dd0516dbad7a7436c139e57c0edf2680791\",\"tests/test_program_k_e2_audit.py\":\""
    b"04b295651f3a4bdd3de9f778a8bd840b6b78224a\",\"tests/test_program_k_e2_execution.py\":\"076b1a85db669466f7a4793bbb6e"
    b"04af9447613b\",\"tests/test_program_k_e2_operational.py\":\"3c280b84c10fd2147a83e1a3963b50c5c8f1848b\",\"tests/test_"
    b"program_k_e2_qualification.py\":\"662754030c3b4187e38e3a1d7edf7fd1322e711b\",\"tests/test_program_k_e2_readiness.p"
    b"y\":\"c7c60b5e19ab134917137c6b2ae06289d0bd8a09\"},\"committed_readiness_blob\":\"5fea5c48b7ce4dfdbdc1de04df95d3e2718"
    b"0042f\",\"domain_hygiene\":{\"accepted_i7_reserved_rejected_domain_disjoint\":true,\"committed_domain_guard\":\"readin"
    b"ess._synthetic_domain\",\"contiguous\":true,\"frozen_section_5_3_all_registry_ranges_and_items_disjoint\":true,\"ord"
    b"ered_unique_indices\":10000,\"primary_frame_disjoint\":true,\"rehearsal_frame_disjoint\":true,\"status\":\"PASS\",\"zini"
    b"_final_holdout_disjoint\":true},\"dominance_margins\":{\"i_od\":2,\"i_ok\":1,\"u_kd\":1},\"fact_scope\":\"OUTCOME-BLIND SE"
    b"LECTOR-MEMBERSHIP FACTS ONLY\",\"fingerprints_generated\":false,\"git_branch\":\"main\",\"git_head\":\"cdba3513c23df77ba"
    b"44449af1e551889a6954768\",\"git_parent\":\"a7727ae1f8493f79aa3ac526e9e7bd538064225e\",\"git_parents\":[\"a7727ae1f8493"
    b"f79aa3ac526e9e7bd538064225e\"],\"git_subject\":\"feat: conform Program K R0 readiness to frozen amendment\",\"git_tr"
    b"ee\":\"3ad37277a01bc91be072cdcef327aaffc1a6ea04\",\"holdout_accessed\":false,\"observational_search_timing\":{\"clock\""
    b":\"time.perf_counter_ns\",\"deterministic_repeat_wall_duration_ns\":30439900,\"scope\":\"Observed execution durations"
    b"; excluded from corpus identity and selection\",\"search_wall_duration_ns\":33698900,\"stage_wall_durations_ns\":[4"
    b"116200,29499100]},\"open_findings\":{\"blocker\":[],\"defer\":[\"Separately reviewed R0 harness materialization, payl"
    b"oad/stream validation and execution qualification. Selection-only I7 validation does not authenticate any gene"
    b"rated board.\"],\"optional\":[],\"required\":[]},\"origin_main\":\"cdba3513c23df77ba44449af1e551889a6954768\",\"other_re"
    b"al_n_computed\":[],\"outcomes_read\":false,\"project_git_mutation\":false,\"protocol_seed\":\"10b1055a6e1bcab8e03ab504"
    b"755c9c9d655d5457800318396afb6e31497ba2fa\",\"purpose\":\"Program K E2 R0 synthetic-corpus selection\",\"real_candida"
    b"te_identity\":{\"candidate_count\":10000,\"digest_owner\":\"identity.corpus_digest\",\"digest_validation_owner\":\"readi"
    b"ness.validate_final_corpus_digest\",\"domain_high_exclusive\":1001000000,\"domain_low\":1000000000,\"exclusion_set\":"
    b"\"identity.E2_PRIMARY_EXCLUSION_SET (empty)\",\"label\":\"PROGRAM_K_E2_PRIMARY_V1\",\"order\":\"frozen rejection-sampli"
    b"ng acceptance order, counter starts at zero\",\"owner\":\"identity.select_indices\",\"postcount_digest_validation\":\""
    b"PASS with the single real target_counts result\",\"precount_digest_validation\":\"PASS using a digest-only SubsetC"
    b"ounts carrier with neutral legal cardinality bounds; these fields were not computed or released as real counts"
    b"\"},\"real_corpus_digest\":\"b712aa0733c5ad458ea01838b35589926184cc0892da6a33844df60b6ae31167\",\"real_r0_run\":false"
    b",\"real_target_count_invocations\":1,\"real_target_counts\":{\"i_od\":2,\"i_ok\":3,\"u_kd\":505},\"real_target_n\":10000,\""
    b"repository_preservation\":{\"ignored_inventory_file_count_before_receipt\":68185,\"ignored_inventory_sha256_before"
    b"_receipt\":\"9f8fb21bd3f83ac4dac46fa0debb7bf88ae8eb00befae0a24274111963b78cfe\",\"ignored_output_inventory\":\"Compl"
    b"ete SHA-256 computed in process before receipt and rechecked after subtracting the sole receipt path\",\"initial"
    b"_inventory_transport_note\":\"The initial full ignored-path listing exceeded tool output limits; it was not used"
    b" as a complete baseline. Selection was pure and performed no file writes. Complete compact inventory hashes we"
    b"re taken before the receipt write.\",\"only_authorized_file_write\":\"The one selection-receipt.json in its unique"
    b" ignored run directory\",\"tracked_identity_and_status\":\"Verified at entry, before selection, before receipt, an"
    b"d after receipt\"},\"schema\":\"program-k-e2-r0-synthetic-selection-receipt/v1\",\"selector_identity\":{\"count_owner\""
    b":\"readiness.target_counts / readiness.subset_counts\",\"d_cap\":256,\"d_label\":\"PROGRAM_K_E2_DETERMINISM_V1\",\"k_ca"
    b"p\":256,\"k_label\":\"PROGRAM_K_E2_KCONTROL_V1\",\"o_cap\":128,\"o_label\":\"PROGRAM_K_E2_ORACLEB_V1\",\"owner\":\"identity."
    b"select_subset_positions\"},\"solver_execution\":false,\"static_call_path\":{\"committed_source_import_closure_files\""
    b":30,\"counts_path\":\"target_counts -> subset_counts -> _memberships -> corpus_digest / select_subset_positions -"
    b"> hashes and set cardinalities\",\"no_artifact_io_or_generation_on_invoked_paths\":true,\"search_path\":\"search_syn"
    b"thetic_corpus -> synthetic_candidate_indices / _synthetic_domain / subset_counts\",\"status\":\"PASS\"},\"status\":\"S"
    b"ELECTION_CANDIDATE_PENDING_CHATGPT_ADJUDICATION\",\"structural_coverage\":{\"o_intersect_d\":4,\"o_intersect_k\":4},\""
    b"synthetic_corpus_digest\":\"b78485dc50dc051d42645059bb86c39c1d4ca9db6cc3ba3be9d9290413831efb\",\"synthetic_counts\""
    b":{\"i_od\":4,\"i_ok\":4,\"u_kd\":506},\"synthetic_rule\":{\"auxiliary_d_repeat\":false,\"auxiliary_k_bind\":false,\"corpus_"
    b"size\":10000,\"domain_high_exclusive\":2001000000000,\"domain_low\":2000000000000,\"enumeration\":\"contiguous non-ove"
    b"rlapping blocks, ordinal zero first\",\"production_search_limit\":100000,\"selected_end_exclusive\":2000000060000,\""
    b"selected_ordinal\":5,\"selected_start\":2000000050000,\"selection\":\"first match\"},\"synthetic_search\":{\"determinist"
    b"ic_repeat\":\"PASS\",\"independent_count_recomputation\":\"PASS\",\"operational_attempt_ceiling\":10000,\"owner\":\"readin"
    b"ess.search_synthetic_corpus\",\"stages\":[{\"attempt_limit\":1,\"candidate_ordinals_examined\":1,\"match_found\":false}"
    b",{\"attempt_limit\":10,\"candidate_ordinals_examined\":6,\"match_found\":true}],\"successful_call_attempt_limit\":10,\""
    b"successful_call_candidate_ordinals_examined\":6},\"tracked_source_changes\":false,\"work_plan_validation\":{\"chain\""
    b":[\"execution.make_work_plan\",\"execution.revalidate_work_plan\",\"readiness.SyntheticWorkload\",\"readiness.validat"
    b"e_synthetic_work_plan\",\"qualification._plan\",\"operational.validate_work_plan\",\"execution.revalidate_work_plan\""
    b"],\"deferred\":\"Future R0 harness materialization, payload/stream validation and execution qualification remain "
    b"outside this work unit\",\"identity_scope\":\"Unmaterialized selection-only synthetic metadata; fingerprint field "
    b"is a literal non-fingerprint label; no board fingerprint calculated or authenticated\",\"status\":\"PASS\"}}\n"
)

def _accepted_receipt_bytes():
    data = _ACCEPTED_RECEIPT_FIXTURE
    if (type(data) is not bytes or len(data) != 7364
            or h.sha256(data).hexdigest() !=
            "72ea48582d3eb2c4eff82172b58fe88460a8a3747eee910efe5fc8a2deb6337c"):
        raise AssertionError("Embedded accepted receipt fixture identity drift")
    return data


class SelectionReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = _accepted_receipt_bytes()

    @classmethod
    def tearDownClass(cls):
        if _accepted_receipt_bytes() != cls.raw:
            raise AssertionError("Embedded receipt fixture must remain unchanged")

    def node(self):
        return json.loads(self.raw)

    def test_embedded_receipt_fixture_requires_no_filesystem_reads(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("No operational input reads")):
            self.assertEqual(_accepted_receipt_bytes(), self.raw)
            self.assertIs(type(_accepted_receipt_bytes()), bytes)

    def test_exact_bytes_public_loader_and_immutable_accepted_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operator-supplied-receipt.json"
            path.write_bytes(self.raw)
            receipt = h.load_selection_receipt(path)
            self.assertEqual(receipt.path, str(path.resolve()))
            self.assertEqual(receipt.canonical_bytes, self.raw)
            self.assertEqual(len(receipt.canonical_bytes), 7364)
            self.assertEqual(h.sha256(receipt.canonical_bytes).hexdigest(),
                "72ea48582d3eb2c4eff82172b58fe88460a8a3747eee910efe5fc8a2deb6337c")
            self.assertEqual(receipt.selection_source_head, "cdba3513c23df77ba44449af1e551889a6954768")
            self.assertEqual((receipt.target.n, receipt.target.u_kd, receipt.target.i_od, receipt.target.i_ok),
                             (10000, 505, 2, 3))
            selection, workload = receipt.selection, receipt.workload
            self.assertEqual((selection.ordinal, selection.counts.u_kd, selection.counts.i_od,
                              selection.counts.i_ok), (5, 506, 4, 4))
            self.assertEqual(workload.target, receipt.target)
            self.assertEqual(workload.selection, selection)
            self.assertFalse(workload.auxiliary_k_bind_complete)
            self.assertFalse(workload.auxiliary_d_repeat_complete)
            for value in (receipt, receipt.target, selection, selection.counts, workload):
                self.assertFalse(hasattr(value, "__dict__"))
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, fields(value)[0].name, None)
            with self.assertRaises(TypeError):
                receipt.canonical_bytes[0] = 0
            detached = h._json_bytes(receipt.canonical_bytes)
            detached["real_target_counts"]["u_kd"] = 0
            self.assertEqual(receipt.target.u_kd, 505)
            self.assertEqual(path.read_bytes(), self.raw)

    def test_public_loader_rejects_size_hash_and_byte_different_semantic_equivalence(self):
        changed = self.raw.replace(b'"ahead":0', b'"ahead":1', 1)
        self.assertEqual(len(changed), len(self.raw))
        malformed_same_size = b"!" + self.raw[1:]
        equivalents = (json.dumps(self.node(), indent=2).encode("ascii") + b"\n",
                      self.raw[:-1] + b" ")
        for data, reason in ((self.raw[:-1], "SIZE"), (self.raw + b"\n", "SIZE"),
                             (changed, "SHA256"), (malformed_same_size, "SHA256")):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "receipt.json"
                path.write_bytes(data)
                with self.assertRaisesRegex(h.HarnessError, "SELECTION_RECEIPT_" + reason):
                    h.load_selection_receipt(path)
        for data in equivalents:
            self.assertEqual(json.loads(data), self.node())
            with self.subTest(size=len(data)), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "receipt.json"
                path.write_bytes(data)
                with self.assertRaises(h.HarnessError):
                    h.load_selection_receipt(path)

    def test_public_loader_uses_only_supplied_path(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                h.load_selection_receipt(Path(directory) / "missing.json")
            with self.assertRaisesRegex(h.HarnessError, "FILE_REQUIRED"):
                h.load_selection_receipt(directory)
            with self.assertRaisesRegex(h.HarnessError, "ABSOLUTE_RECEIPT_PATH_REQUIRED"):
                h.AcceptedSelectionReceipt("relative.json", self.raw)

    def test_json_rejects_malformed_duplicate_noncanonical_and_noninteger_numbers(self):
        cases = ((b"{\n", "INVALID_JSON"), (b"\xff\n", "INVALID_JSON"),
                 (b'{"a":1,"a":2}\n', "DUPLICATE_JSON_FIELD"),
                 (b'{"a": {"b":1,"b":2}}\n', "DUPLICATE_JSON_FIELD"),
                 (b'{"a":1.5}\n', "NONINTEGER_JSON_NUMBER"),
                 (b'{"a":NaN}\n', "NONINTEGER_JSON_NUMBER"),
                 (b'{"a":Infinity}\n', "NONINTEGER_JSON_NUMBER"),
                 (b'{ "a":1}\n', "NONCANONICAL_JSON"),
                 (b'{"a":1}', "NONCANONICAL_JSON"))
        for data, reason in cases:
            with self.subTest(data=data), self.assertRaisesRegex(h.HarnessError, reason):
                h._json_bytes(data)
        self.assertEqual(h._json_bytes(self.raw), self.node())

    def test_semantics_rejects_wrong_authority_identity_classification_and_population(self):
        changes = (("schema", "unknown/v1"), ("purpose", "other"),
            ("classification", "effectiveness evidence"), ("fact_scope", "other"),
            ("git_head", "0" * 40), ("origin_main", "0" * 40),
            ("amendment_sha256", "0" * 64), ("amendment_byte_length", 58051),
            ("base_protocol_sha256", "0" * 64), ("base_protocol_blob", "0" * 40),
            ("base_protocol_freeze_commit", "0" * 40),
            ("protocol_seed", "0" * 64), ("committed_readiness_blob", "0" * 40),
            ("real_target_n", 9999), ("real_target_n", True),
            ("real_corpus_digest", "0" * 64), ("synthetic_corpus_digest", "0" * 64),
            ("real_target_count_invocations", 2))
        for key, value in changes:
            node = self.node()
            node[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(h.HarnessError):
                h._selection_semantics(node)
        self.assertEqual(h._selection_semantics(self.node()), self.node())

    def test_semantics_rejects_real_synthetic_counts_dominance_and_structure_changes(self):
        groups = (("real_target_counts", {"u_kd": 504, "i_od": 1, "i_ok": 2}),
                  ("synthetic_counts", {"u_kd": 505, "i_od": 3, "i_ok": 3}),
                  ("dominance_margins", {"u_kd": -1, "i_od": -1, "i_ok": -1}),
                  ("structural_coverage", {"o_intersect_d": 0, "o_intersect_k": 0}))
        for group, changes in groups:
            for key, value in changes.items():
                node = self.node()
                node[group][key] = value
                with self.subTest(group=group, key=key), self.assertRaises(h.HarnessError):
                    h._selection_semantics(node)

    def test_semantics_rejects_changed_selected_bounds_ordinal_rule_and_auxiliary_flags(self):
        changes = (("domain_low", 1), ("domain_high_exclusive", 2001000000001),
            ("corpus_size", 9999), ("production_search_limit", 100001),
            ("selected_ordinal", 6), ("selected_start", 2000000060000),
            ("selected_end_exclusive", 2000000060001), ("selection", "last match"),
            ("auxiliary_d_repeat", True), ("auxiliary_k_bind", True))
        for key, value in changes:
            node = self.node()
            node["synthetic_rule"][key] = value
            with self.subTest(key=key), self.assertRaises(h.HarnessError):
                h._selection_semantics(node)

    def test_semantics_rejects_forbidden_activity_other_targets_and_missing_fields(self):
        flags = ("actual_e2_run", "real_r0_run", "board_generation", "fingerprints_generated",
                 "outcomes_read", "solver_execution", "holdout_accessed", "project_git_mutation",
                 "tracked_source_changes")
        for flag in flags:
            for invalid in (True, 0):
                node = self.node()
                node[flag] = invalid
                with self.subTest(flag=flag, invalid=invalid), self.assertRaises(h.HarnessError):
                    h._selection_semantics(node)
        node = self.node()
        node["other_real_n_computed"] = [1000]
        with self.assertRaisesRegex(h.HarnessError, "OTHER_TARGETS"):
            h._selection_semantics(node)
        for parent in (None, "real_target_counts", "synthetic_counts", "synthetic_rule", "structural_coverage"):
            for operation in ("missing", "unknown"):
                node = self.node()
                target = node if parent is None else node[parent]
                if operation == "missing":
                    del target[next(iter(target))]
                else:
                    target["unknown_field"] = 0
                with self.subTest(parent=parent, operation=operation), self.assertRaises(h.HarnessError):
                    h._selection_semantics(node)


class SelectedWorkPlanTests(unittest.TestCase):
    def test_selected_metadata_plan_is_exact_pure_and_uses_accepted_validation_chain(self):
        raw = _accepted_receipt_bytes()
        original_select = identity.select_indices
        def synthetic_positions_only(label, seed, low, high, count, *args, **kwargs):
            self.assertNotIn(label, (identity.PRIMARY_LABEL, identity.REHEARSAL_LABEL))
            self.assertEqual((low, high), (0, 10000))
            return original_select(label, seed, low, high, count, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_bytes(raw)
            receipt = h.load_selection_receipt(path)
            with patch("benchmark_board.generate_board", side_effect=AssertionError("No board generation")), \
                    patch.object(readiness, "search_synthetic_corpus", side_effect=AssertionError("No search")), \
                    patch.object(readiness, "target_counts", side_effect=AssertionError("No real recount")), \
                    patch.object(identity, "select_indices", side_effect=synthetic_positions_only), \
                    patch.object(execution, "make_work_plan", wraps=execution.make_work_plan) as made, \
                    patch.object(execution, "revalidate_work_plan", wraps=execution.revalidate_work_plan) as revalidated, \
                    patch.object(readiness, "validate_synthetic_work_plan", wraps=readiness.validate_synthetic_work_plan) as synthetic, \
                    patch.object(h.qualification, "_plan", wraps=h.qualification._plan) as qualified, \
                    patch.object(operational, "validate_work_plan", wraps=operational.validate_work_plan) as operational_plan:
                plan = h.build_selected_work_plan(receipt, "synthetic-i7-r0-selected-metadata-fixture")
                workload = receipt.workload
                self.assertTrue(all(spy.called for spy in (made, revalidated, synthetic, qualified, operational_plan)))
                self.assertIs(readiness.validate_synthetic_work_plan(plan, workload), plan)
            indices = tuple(item.board.game_index for item in plan)
            self.assertIs(type(plan), tuple)
            self.assertEqual(indices, tuple(range(2000000050000, 2000000060000)))
            self.assertEqual(len(indices), len(set(indices)))
            self.assertEqual(len(indices), 10000)
            self.assertEqual(tuple(item.position for item in plan), tuple(range(10000)))
            self.assertEqual(identity.corpus_digest(plan[0].protocol_seed, len(plan), indices).hex(),
                "b78485dc50dc051d42645059bb86c39c1d4ca9db6cc3ba3be9d9290413831efb")
            self.assertGreaterEqual(min(indices), readiness.SYNTHETIC_INDEX_LOW)
            self.assertLess(max(indices), readiness.SYNTHETIC_INDEX_HIGH)
            self.assertTrue(all(not (identity.PRIMARY_LOW <= index < identity.REHEARSAL_HIGH
                                     or 2010000 <= index < 2010100) for index in indices))
            self.assertEqual((workload.target.u_kd, workload.target.i_od, workload.target.i_ok), (505, 2, 3))
            self.assertEqual((workload.selection.counts.u_kd, workload.selection.counts.i_od,
                              workload.selection.counts.i_ok), (506, 4, 4))
            self.assertEqual(sum(item.oracle_b_selected and item.determinism_selected for item in plan), 4)
            self.assertEqual(sum(item.oracle_b_selected and item.k_control_selected for item in plan), 4)
            self.assertEqual(sum(item.determinism_selected or item.k_control_selected for item in plan), 506)
            self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(_accepted_receipt_bytes(), raw)
# RECEIPT_TESTS_END


# R0A_TESTS_BEGIN
def _r0a_adapter_fixture(concurrency=1, *, seed=None):
    plan = readiness.build_r0a_plan(b"bounded-r0a-adapter-fixture-seed" if seed is None else seed)
    envelope = operational.OperatingEnvelope(
        concurrency=concurrency, max_decision_wall_ms=30_000, max_arm_wall_ms=420_000,
        max_case_wall_ms=840_000, max_job_wall_ms=900_000, max_launcher_wall_ms=43_200_000,
        shadow_timeout_ms=1_000, max_physical_inputs=50_000,
        worker_memory_cap_bytes=4_294_967_296, coordinator_memory_cap_bytes=4_294_967_296,
        memory_cap_bytes=4_294_967_296, archive_cap_bytes=17_179_869_184,
        monitor_interval_ms=1, max_payload_bytes=67_108_864, max_ipc_frame_bytes=65_536,
        aggregation_wall_ms=43_200_000, validation_wall_ms=43_200_000,
        publication_wall_ms=43_200_000, readback_wall_ms=43_200_000, report_wall_ms=43_200_000)
    work = tuple(operational.R0Work(position,
        records.BoardIdentity(index, "inert-fixture-" + str(position), 2, 1, 1, (0, 0),
                              "synthetic-generator", "synthetic-spec"),
        plan.protocol_seed, "R0-adapter-fixture-c" + str(concurrency))
        for position, index in enumerate(plan.ordered_indices))
    setup_routes = dict((kind, route) for route, kind in h._R0A_REFERENCE_COMPONENTS)
    components = []
    for ordinal, kind in enumerate(operational.R0Component):
        setup_observation = operational._R0Observation(100 + ordinal, 200 + ordinal,
            300 + 2 * ordinal, 2, 5, 1, 1, (0, 0, 0, ()), True, True, True)
        target = replace(setup_observation, worker_memory=500 + ordinal,
            coordinator_memory=600 + ordinal, combined_memory=1100 + 2 * ordinal,
            decision_wall=20, arm_wall=50, shadow_wall=10, physical_inputs=5,
            prior_binding_intervals=((1, 3),) if kind is operational.R0Component.ORACLE_K_BIND else ())
        has_setup = kind in setup_routes
        units = tuple(operational.R0UnitMeasurement(item, kind, records.AuditStatus.PASS, (),
            100 + position, 0 if kind is operational.R0Component.ORACLE_K_BIND else 30 + ordinal + position,
            20 if has_setup else 0, 700 + position if has_setup else 0, 80,
            (setup_observation, target) if has_setup else (target,),
            10 + ordinal + position if has_setup else 0, 11, 800 + position)
            for position, item in enumerate(work))
        setups = []
        if has_setup:
            for wave, offset in enumerate(range(0, len(work), concurrency)):
                batch = work[offset:offset + concurrency]
                setups.append(operational.R0SetupMeasurement(setup_routes[kind],
                    wave * 10_000 + 1, wave * 10_000 + 1001 + wave,
                    tuple(operational.UnitReceipt(item.position, execution.WorkerKind.PRIMARY,
                        records.AuditStatus.PASS, "ADMITTED", 20, 0) for item in batch),
                    tuple(setup_observation for _ in batch), tuple(500 + item.position for item in batch),
                    2000 + ordinal, 3000 + ordinal, 2, True))
        components.append(operational.R0ComponentMeasurement(kind, concurrency, units,
            1_000_000 + ordinal, 10_000 + ordinal, 2_000_000 + ordinal, 20_000 + ordinal, tuple(setups)))
    components = tuple(components)
    traces = tuple(tuple((unit, position + 1, len(work)) for position, unit in enumerate(component.units))
                   for component in components)
    return plan, envelope, work, components, traces


class R0AAdapterTests(unittest.TestCase):
    def adapt(self, fixture=None):
        return h.adapt_r0a_concurrency(*(_r0a_adapter_fixture() if fixture is None else fixture))

    def replace_component(self, fixture, kind, component):
        plan, envelope, work, components, traces = fixture
        offset = tuple(operational.R0Component).index(kind)
        components = components[:offset] + (component,) + components[offset + 1:]
        trace = tuple((unit, index + 1, len(work)) for index, unit in enumerate(component.units))
        traces = traces[:offset] + (trace,) + traces[offset + 1:]
        return plan, envelope, work, components, traces

    def test_exact_six_components_four_references_and_eight_containment_routes(self):
        fixture = _r0a_adapter_fixture(2)
        value = self.adapt(fixture)
        by_kind = {component.component: component for component in fixture[3]}
        mapping = (("primary", operational.R0Component.PRIMARY),
            ("k_control", operational.R0Component.K_CONTROL),
            ("determinism", operational.R0Component.DETERMINISM),
            ("oracle_primary", operational.R0Component.ORACLE_B),
            ("oracle_d_repeat", operational.R0Component.ORACLE_D_REPEAT))
        for name, kind in mapping:
            observed, raw = getattr(value, name), by_kind[kind]
            self.assertEqual((observed.wall_ns, observed.durable_bytes, observed.max_unit_bytes,
                              observed.completed_units),
                (raw.wall_ns, sum(unit.durable_bytes for unit in raw.units),
                 max(unit.durable_bytes for unit in raw.units), 64))
        self.assertEqual(value.oracle_k_bind,
            readiness.WallRouteMeasurement(by_kind[operational.R0Component.ORACLE_K_BIND].wall_ns, 64))
        self.assertEqual(tuple(v.route for v in value.containment), readiness.CALIBRATION_ROUTES)
        self.assertEqual(tuple(v.route for v in value.references), ("K", "D", "O_K_SETUP", "O_D_SETUP"))
        for reference, (route, kind) in zip(value.references, h._R0A_REFERENCE_COMPONENTS):
            component = by_kind[kind]
            self.assertEqual(reference, readiness.ReferenceMeasurement(route,
                sum(unit.reference_bytes for unit in component.units),
                max(unit.reference_bytes for unit in component.units), 64))
            self.assertNotEqual(reference.durable_bytes, sum(unit.setup_bytes for unit in component.units))
        for name in h._R0A_MAXIMA:
            self.assertEqual(getattr(value, name), max(getattr(route, name) for route in value.containment))
        self.assertIs(type(value.primary_pairs_per_hour), Fraction)
        with self.assertRaises(FrozenInstanceError):
            value.concurrency = 4

    def test_target_spikes_never_contaminate_either_setup_route(self):
        for kind in (operational.R0Component.ORACLE_K_BIND, operational.R0Component.ORACLE_D_REPEAT):
            fixture = _r0a_adapter_fixture(4)
            before = self.adapt(fixture)
            raw = next(value for value in fixture[3] if value.component is kind)
            units = tuple(replace(unit, observations=(unit.observations[0],
                replace(unit.observations[1], worker_memory=9000, coordinator_memory=19000,
                    combined_memory=28000, decision_wall=200, arm_wall=500, shadow_wall=50,
                    physical_inputs=99)), max_case_wall_ns=800, max_payload_bytes=5000)
                for unit in raw.units)
            changed = replace(raw, units=units, coordinator_memory_bytes=19000,
                              combined_memory_bytes=28000, complete_wall_ns=raw.complete_wall_ns + 10**12)
            after = self.adapt(self.replace_component(fixture, kind, changed))
            setup_name = "O_K_SETUP" if kind is operational.R0Component.ORACLE_K_BIND else "O_D_SETUP"
            first, second = dict((v.route, v) for v in before.containment), dict((v.route, v) for v in after.containment)
            self.assertEqual(first[setup_name], second[setup_name])
            self.assertNotEqual(first[kind.value], second[kind.value])
            self.assertEqual(second[setup_name].launcher_wall_ns, raw.setup_wall_ns)
            self.assertLess(second[setup_name].launcher_wall_ns,
                            raw.setup_measurements[-1].finished_ns - raw.setup_measurements[0].started_ns)
            self.assertEqual(second[setup_name].max_payload_bytes, 563)
            self.assertEqual(second[kind.value].max_payload_bytes, 5000)

    def test_setup_peak_changes_remain_independently_visible(self):
        fixture = _r0a_adapter_fixture()
        raw = next(v for v in fixture[3] if v.component is operational.R0Component.ORACLE_K_BIND)
        changed = replace(raw, setup_measurements=(replace(raw.setup_measurements[0],
            coordinator_memory_bytes=8000, combined_memory_bytes=9000),) + raw.setup_measurements[1:])
        before = self.adapt(fixture)
        after = self.adapt(self.replace_component(fixture, raw.component, changed))
        self.assertEqual(before.containment[-1], after.containment[-1])
        self.assertEqual(after.containment[-2].max_coordinator_memory_bytes, 8000)
        self.assertEqual(after.containment[-2].max_combined_memory_bytes, 9000)

    def test_zero_row_oracles_are_complete_and_binding_has_no_byte_family(self):
        fixture = _r0a_adapter_fixture()
        for kind in (operational.R0Component.ORACLE_B, operational.R0Component.ORACLE_D_REPEAT):
            raw = next(v for v in fixture[3] if v.component is kind)
            fixture = self.replace_component(fixture, kind, replace(raw,
                units=tuple(replace(unit, durable_bytes=0) for unit in raw.units)))
        result = self.adapt(fixture)
        for oracle in (result.oracle_primary, result.oracle_d_repeat):
            self.assertEqual((oracle.durable_bytes, oracle.max_unit_bytes, oracle.completed_units), (0, 0, 64))
        raw = next(v for v in fixture[3] if v.component is operational.R0Component.ORACLE_K_BIND)
        changed = replace(raw, units=(replace(raw.units[0], durable_bytes=1),) + raw.units[1:])
        with self.assertRaisesRegex(ValueError, "BIND_HAS_NO_BYTE_FAMILY"):
            self.adapt(self.replace_component(fixture, raw.component, changed))

    def test_missing_reordered_wrong_concurrency_and_work_identity_rejected(self):
        fixture = _r0a_adapter_fixture()
        for components in (fixture[3][:-1], fixture[3][::-1],
                (replace(fixture[3][0], concurrency=2),) + fixture[3][1:]):
            with self.subTest(components=len(components)), self.assertRaises(ValueError):
                self.adapt(fixture[:3] + (components, fixture[4]))
        raw = fixture[3][0]
        unit = replace(raw.units[0], work=replace(raw.units[0].work, run_id="R0-wrong"))
        with self.assertRaisesRegex(ValueError, "WORK_IDENTITY"):
            self.adapt(self.replace_component(fixture, raw.component,
                replace(raw, units=(unit,) + raw.units[1:])))
        with self.assertRaisesRegex(ValueError, "WORK_IDENTITY"):
            self.adapt((readiness.build_r0a_plan(b"different-bounded-fixture-seed!!"),) + fixture[1:])

    def test_progress_missing_wrong_order_identity_and_noninteger_rejected(self):
        fixture = _r0a_adapter_fixture()
        trace = fixture[4][0]
        for invalid in (trace[:-1], trace[::-1],
                ((trace[0][0], True, 64),) + trace[1:],
                ((trace[0][0], 1, 63),) + trace[1:],
                ((fixture[3][1].units[0], 1, 64),) + trace[1:]):
            with self.subTest(length=len(invalid)), self.assertRaises(ValueError):
                self.adapt(fixture[:4] + ((invalid,) + fixture[4][1:],))

    def test_setup_missing_observation_sample_readback_and_completion_rejected(self):
        fixture = _r0a_adapter_fixture()
        raw = next(v for v in fixture[3] if v.component is operational.R0Component.ORACLE_K_BIND)
        first = raw.setup_measurements[0]
        changes = (replace(first, observations=(None,)), replace(first, memory_sample_count=0),
            replace(first, readback_complete=False),
            replace(first, observations=(replace(first.observations[0], cleanup_complete=False),)),
            replace(first, observations=(replace(first.observations[0], watchdogs_complete=False),)),
            replace(first, observations=(replace(first.observations[0], resources_complete=False),)))
        for setup in changes:
            with self.subTest(setup=setup), self.assertRaisesRegex(ValueError, "SETUP_INCOMPLETE"):
                self.adapt(self.replace_component(fixture, raw.component,
                    replace(raw, setup_measurements=(setup,) + raw.setup_measurements[1:])))
        with self.assertRaises(ValueError):
            replace(raw, setup_measurements=raw.setup_measurements[:-1])
        with self.assertRaises(ValueError):
            replace(raw, setup_measurements=raw.setup_measurements[::-1])

    def test_target_failure_and_missing_observations_cannot_become_readiness(self):
        fixture = _r0a_adapter_fixture()
        raw = fixture[3][1]
        for unit in (replace(raw.units[0], status=records.AuditStatus.FAIL, reasons=("AUDIT_FAIL",)),
                     replace(raw.units[0], observations=()),
                     replace(raw.units[0], observations=(raw.units[0].observations[0],
                        replace(raw.units[0].observations[1], cleanup_complete=False)))):
            with self.subTest(status=unit.status), self.assertRaises(ValueError):
                self.adapt(self.replace_component(fixture, raw.component,
                    replace(raw, units=(unit,) + raw.units[1:])))
        self.assertEqual(sum(v.completed_units for v in raw.setup_measurements), 64)

    def test_raw_memory_omission_and_missing_binding_interval_rejected(self):
        fixture = _r0a_adapter_fixture()
        raw = fixture[3][0]
        with self.assertRaisesRegex(ValueError, "COMPONENT_MEMORY_OMITTED"):
            self.adapt(self.replace_component(fixture, raw.component,
                replace(raw, coordinator_memory_bytes=1)))
        raw = next(v for v in fixture[3] if v.component is operational.R0Component.ORACLE_K_BIND)
        changed = replace(raw.units[0], observations=(raw.units[0].observations[0],
            replace(raw.units[0].observations[1], prior_binding_intervals=())))
        with self.assertRaisesRegex(ValueError, "BINDING_OBSERVATION_MISSING"):
            self.adapt(self.replace_component(fixture, raw.component,
                replace(raw, units=(changed,) + raw.units[1:])))

    def test_exact_plan_and_provenance_authentication_stay_pure(self):
        fixture = _r0a_adapter_fixture()
        with patch("benchmark_board.generate_board", side_effect=AssertionError("No boards")), \
                patch.object(operational, "measure_r0_component", side_effect=AssertionError("No workers")):
            values = tuple(self.adapt(_r0a_adapter_fixture(c)) for c in (1, 2, 4))
            self.assertEqual(readiness.validate_r0a_measurements(values), values)
            self.assertEqual(tuple(v.plan for v in values), (fixture[0],) * 3)
            with self.assertRaises(ValueError):
                replace(fixture[0], ordered_indices=fixture[0].ordered_indices[::-1])
        broken = replace(fixture[0].provenance)
        object.__setattr__(broken, "sha256", "0" * 64)
        with self.assertRaises(ValueError):
            replace(fixture[0], provenance=broken)

    def test_private_orchestration_retains_raw_facts_and_uses_all_routes_once(self):
        fixtures = tuple(_r0a_adapter_fixture(c) for c in (1, 2, 4))
        calls = []
        def measure(work, kind, root, envelope, *, progress):
            calls.append((envelope.concurrency, kind, root))
            fixture = fixtures[(1, 2, 4).index(envelope.concurrency)]
            component = fixture[3][tuple(operational.R0Component).index(kind)]
            self.assertEqual(work, fixture[2])
            for position, unit in enumerate(component.units):
                progress(unit, position + 1, len(work))
            return component
        with tempfile.TemporaryDirectory() as directory, \
                patch("benchmark_board.generate_board", side_effect=AssertionError("No boards")):
            root = Path(directory) / "r0a-fixture"
            values, raw, traces = h._measure_r0a(fixtures[0][0], tuple(v[2] for v in fixtures),
                tuple(v[1] for v in fixtures), root, measure=measure)
            self.assertEqual(raw, tuple(v[3] for v in fixtures))
            self.assertEqual(traces, tuple(v[4] for v in fixtures))
            self.assertEqual(tuple(v.concurrency for v in values), (1, 2, 4))
            self.assertEqual(tuple((c, kind) for c, kind, _ in calls),
                tuple((c, kind) for c in (1, 2, 4) for kind in operational.R0Component))
            with self.assertRaises(FileExistsError):
                h._measure_r0a(fixtures[0][0], tuple(v[2] for v in fixtures),
                    tuple(v[1] for v in fixtures), root, measure=measure)
        self.assertEqual(len(calls), 18)

    def test_private_orchestration_validates_before_creating_root(self):
        fixtures = tuple(_r0a_adapter_fixture(c) for c in (1, 2, 4))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "must-not-exist"
            with self.assertRaises(ValueError):
                h._measure_r0a(fixtures[0][0], tuple(v[2] for v in fixtures),
                    tuple(v[1] for v in fixtures)[::-1], root,
                    measure=lambda *args, **kwargs: self.fail("No measurement permitted"))
            self.assertFalse(root.exists())
# R0A_TESTS_END


# SYNTHETIC_TESTS_BEGIN
class SyntheticMaterializationTests(unittest.TestCase):
    @staticmethod
    def plan(n=1):
        runtime = records.RuntimeIdentity(h.platform.python_implementation(), h.platform.python_version(),
            os.name, h.platform.platform(), h.platform.machine(), None)
        return execution.make_work_plan(tuple(h.synthetic_board_identity(2_000_000_050_000 + i) for i in range(n)),
            protocol_seed=bytes.fromhex(identity.PROTOCOL_SHA256), run_id="synthetic-i7-r0b-fixture", runtime=runtime)

    @staticmethod
    def envelope(**changes):
        value = operational.OperatingEnvelope(1, 30000, 420000, 840000, 900000, 43200000,
            1000, 480, 4294967296, 4294967296, 4294967296, 17179869184, 1, 67108864, 65536,
            10000, 10000, 10000, 10000, 10000)
        return replace(value, **changes)

    @staticmethod
    def sizes(oracle=8000):
        return readiness.ComponentSizes(20000, 30000, oracle, oracle, 50000, 10000)

    def bundles(self, sizes=None):
        work = self.plan()[0]
        sizes = self.sizes() if sizes is None else sizes
        primary = h.build_synthetic_bundle(work, execution.WorkerKind.PRIMARY, sizes, max_payload_bytes=67108864)
        return work, sizes, (primary,) + tuple(h.build_synthetic_bundle(work, kind, sizes, primary,
            max_payload_bytes=67108864) for kind in operational._kinds(work)[1:])

    def test_manual_six_family_payloads_reconstruct_with_exact_copied_priors(self):
        from stage3_physical import load_timing_table
        with patch.object(execution, "_materialize_board", side_effect=AssertionError("No board generation")), \
             patch.object(execution.runner, "run_k_p0", side_effect=AssertionError("No solver")), \
             patch.object(execution.runner, "run_k_control", side_effect=AssertionError("No solver")):
            work, sizes, bundles = self.bundles()
        observed = set()
        for bundle in bundles:
            self.assertEqual(execution.decode_bundle(execution.encode_bundle(bundle)), bundle)
            restored = h.qualification._reconstruct(work, bundle.kind, dict(bundle.streams),
                                                    load_timing_table(), self.envelope())
            self.assertEqual(restored, bundle)
            for name, size in h.synthetic_bundle_family_bytes(bundle):
                observed.add(name)
                self.assertGreaterEqual(size, getattr(sizes, name))
            operational._bind_prior_bundle(bundle,
                None if bundle.kind is execution.WorkerKind.PRIMARY else execution.encode_bundle(bundles[0]),
                work, bundle.kind, self.envelope())
        self.assertEqual(observed, set(h._SYNTHETIC_FAMILIES))
        self.assertEqual(tuple(name for name, _ in h.synthetic_bundle_family_bytes(bundles[0])),
                         ("primary", "reference", "oracle_primary"))
        self.assertEqual(tuple(name for name, _ in h.synthetic_bundle_family_bytes(bundles[1])),
                         ("determinism", "oracle_repeat"))
        self.assertEqual(tuple(name for name, _ in h.synthetic_bundle_family_bytes(bundles[2])), ("k_control",))

    def test_zero_oracle_keeps_selected_coverage_and_empty_audit_streams(self):
        _, _, bundles = self.bundles(self.sizes(oracle=0))
        for bundle, name in ((bundles[0], "oracle_b"), (bundles[1], "repeat_oracle_b")):
            values = dict(bundle.streams)
            self.assertEqual(values[name + "_audits"], ())
            coverage = records.decode(values[name + "_coverage"][0])
            self.assertTrue(coverage.selected)
            self.assertEqual(coverage.applicable, ())
        self.assertEqual(dict(h.synthetic_bundle_family_bytes(bundles[0]))["oracle_primary"], 0)
        self.assertEqual(dict(h.synthetic_bundle_family_bytes(bundles[1]))["oracle_repeat"], 0)

    def test_payload_minimum_and_encoded_overflow_fail_closed(self):
        work = self.plan()[0]
        with self.assertRaisesRegex(h.HarnessError, "MINIMUM_PAYLOAD_CAP"):
            h.build_synthetic_bundle(work, execution.WorkerKind.PRIMARY, self.sizes(), max_payload_bytes=37999)
        with self.assertRaises((h.HarnessError, execution.E2ExecutionError)):
            h.build_synthetic_bundle(work, execution.WorkerKind.PRIMARY,
                readiness.ComponentSizes(1, 1, 0, 0, 1, 1), max_payload_bytes=100)

    def test_factory_rejects_real_identity_and_missing_or_wrong_prior(self):
        work = self.plan()[0]
        with self.assertRaisesRegex(h.HarnessError, "NON_BOARD_IDENTITY"):
            h.build_synthetic_bundle(replace(work, board=replace(work.board, fingerprint="pretend-board")),
                execution.WorkerKind.PRIMARY, self.sizes(), max_payload_bytes=67108864)
        with self.assertRaisesRegex(h.HarnessError, "PRIOR_REQUIRED"):
            h.build_synthetic_bundle(work, execution.WorkerKind.DETERMINISM, self.sizes(), max_payload_bytes=67108864)
        _, sizes, bundles = self.bundles()
        with self.assertRaises(execution.E2ExecutionError):
            h.build_synthetic_bundle(replace(work, position=1), execution.WorkerKind.K_CONTROL,
                sizes, bundles[0], max_payload_bytes=67108864)

    def _identity(self, root, plan):
        # A bounded seal fixture. Full source/corpus identity is tested by the
        # provenance/validation integration tests, not fabricated by this helper.
        with h.store.StreamWriter(root, h.qualification.IDENTITY_STREAM) as writer:
            writer.append((0,), plan[0].runtime)
            return writer.seal()

    def test_materialization_seals_all_streams_and_exact_events_and_resource_owners(self):
        plan, updates = self.plan(2), []
        with tempfile.TemporaryDirectory() as directory:
            seal = self._identity(directory, plan)
            with patch.object(operational.harness, "_coordinator_private_bytes", return_value=100):
                result = h.materialize_synthetic(plan, self.sizes(), self.envelope(), directory, seal,
                                                 progress=lambda done, total: updates.append((done, total)))
            self.assertEqual(result.coordinator.status, records.AuditStatus.PASS)
            self.assertEqual(dict(result.family_counts), dict(primary=2, k_control=2, oracle_primary=2,
                oracle_repeat=2, determinism=2, reference=2))
            self.assertEqual(updates, [(i, 6) for i in range(7)])
            self.assertTrue(result.readback_complete and result.cleanup_complete and result.synthetic_non_evidence)
            self.assertEqual(result.max_coordinator_memory_bytes, 100)
            self.assertEqual(sum(v for _, v in result.family_totals), sum(v.byte_length
                for v in result.coordinator.streams if v.name in execution.STREAM_NAMES))
            for digest in result.coordinator.streams:
                self.assertEqual(h.store.scan_stream(directory, digest.name), digest)
            entries = []
            h.store.scan_stream(directory, "operations", visit=lambda key, value: entries.append((key, value)))
            class Lane:
                def peek(self):
                    return entries[0] if entries else None
                def pop(self):
                    return entries.pop(0)
            h.qualification._receipt_plan(plan, result.coordinator)
            h.qualification._events(Lane(), result.coordinator, set(range(2)))
            samples = []
            h.store.scan_stream(directory, "resources", visit=lambda key, value: samples.append(value))
            self.assertEqual(len(samples), 6)
            self.assertTrue(all(v.worker_bytes == 0 and v.coordinator_bytes == v.combined_bytes == 100
                and v.method is records.MemoryMethod.PRIVATE_BYTES for v in samples))
            with self.assertRaisesRegex(h.HarnessError, "FRESH_STREAM_ROOT"):
                h.materialize_synthetic(plan, self.sizes(), self.envelope(), directory, seal)
            with self.assertRaises(FrozenInstanceError):
                result.cleanup_complete = False

    def test_identity_seal_omission_or_drift_prevents_stream_creation(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(h.HarnessError, "IDENTITY_SEAL_REQUIRED"):
                h.materialize_synthetic(plan, self.sizes(), self.envelope(), directory, None)
            seal = self._identity(directory, plan)
            with self.assertRaisesRegex(h.HarnessError, "IDENTITY_READBACK"):
                h.materialize_synthetic(plan, self.sizes(), self.envelope(), directory,
                    replace(seal, sha256="0" * 64))
            self.assertEqual(len(tuple(Path(directory).iterdir())), 1)

    def test_materialization_failure_closes_writers_and_retains_partial_evidence(self):
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            seal = self._identity(directory, plan)
            writers = []
            original = h.store.StreamWriter
            def capture(*args, **kwargs):
                value = original(*args, **kwargs)
                writers.append(value)
                return value
            with patch.object(h.store, "StreamWriter", side_effect=capture), \
                 patch.object(operational.harness, "_coordinator_private_bytes", return_value=101), \
                 self.assertRaisesRegex(h.HarnessError, "MEMORY_CAP"):
                h.materialize_synthetic(plan, self.sizes(), self.envelope(coordinator_memory_cap_bytes=100),
                                        directory, seal)
            self.assertTrue(writers)
            self.assertTrue(all(v._closed for v in writers))
            self.assertTrue((Path(directory) / "operations.jsonl").exists())
            events = []
            h.store.scan_stream(directory, "operations", visit=lambda key, value: events.append(value))
            self.assertEqual(events[-1].status, records.OperationStatus.INCOMPLETE)
            self.assertEqual(events[-1].unit_id, "coordinator:SYNTHETIC_MATERIALIZATION_INCOMPLETE")
            self.assertFalse((Path(directory) / "COMPLETE.json").exists())

    def test_lower_constructor_does_not_select_or_change_production_constants(self):
        before = identity.BOOTSTRAP_REPLICATES
        with patch.object(readiness, "search_synthetic_corpus", side_effect=AssertionError("No search")), \
             patch.object(readiness, "target_counts", side_effect=AssertionError("No target recount")):
            self.bundles()
        self.assertEqual(identity.BOOTSTRAP_REPLICATES, before)
        self.assertEqual(before, 10000)
# SYNTHETIC_TESTS_END


# POSTPROCESS_TESTS_BEGIN
from contextlib import contextmanager
from hashlib import sha256
import platform
import threading


def _bounded_postprocess_analyze(rows, **kwargs):
    """Fixture-only bootstrap summary; no sampling loop or production workload."""
    def bootstrap(actual, seed, digest, *, progress):
        if actual != rows:
            raise AssertionError("Fixture rows changed")
        for completed in range(identity.BOOTSTRAP_REPLICATES + 1):
            progress(completed, identity.BOOTSTRAP_REPLICATES)
        defined = h.analysis.BootstrapMetric((Fraction(0), Fraction(0)), 10_000, 0, 0, 0)
        empty = h.analysis.BootstrapMetric(None, 0, 10_000, 10_000, 0)
        return h.analysis.BootstrapSummary(10_000, len(rows) * 10_000, 0,
            h.analysis.bootstrap_seed(seed, digest).hex(), empty, defined, defined)
    with patch.object(h.analysis, "_shared_bootstrap", new=bootstrap):
        return h.analysis.analyze_effectiveness(rows, **kwargs)


class R0BPostprocessingTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        runtime = records.RuntimeIdentity(platform.python_implementation(), platform.python_version(),
            os.name, platform.platform(), platform.machine(), None)
        plan = execution.make_work_plan((h.synthetic_board_identity(2_000_000_050_000),),
            protocol_seed=bytes.fromhex(identity.PROTOCOL_SHA256), run_id="synthetic-i7-r0b-postprocess",
            runtime=runtime)
        envelope = _r0a_adapter_fixture()[1]
        indices = tuple(v.board.game_index for v in plan)
        expected = (records.ProtocolIdentity(h.qualification._PROTOCOL, identity.PROTOCOL_SHA256,
            h.qualification._BLOB, h.qualification._FREEZE), records.CorpusIdentity("SYNTHETIC_I7",
            min(indices), max(indices) + 1, len(plan), indices,
            identity.corpus_digest(plan[0].protocol_seed, len(plan), indices).hex(), ()), runtime,
            records.SourceBlobIdentity("synthetic/postprocess.py", "a" * 40, "b" * 64, 1))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "streams"
            root.mkdir()
            with h.store.StreamWriter(root, h.qualification.IDENTITY_STREAM) as writer:
                for ordinal, value in enumerate(expected):
                    writer.append((ordinal,), value)
                identity_seal = writer.seal()
            with patch.object(operational.harness, "_coordinator_private_bytes", return_value=100):
                material = h.materialize_synthetic(plan, readiness.ComponentSizes(1, 1, 0, 0, 1, 1),
                    envelope, root, identity_seal)
            yield dict(plan=plan, coordinator_result=material.coordinator, identity_seal=identity_seal,
                root=root, envelope=envelope, output_root=Path(directory) / "postprocess",
                expected_identity=expected, source_recheck=lambda: expected, _analyze=_bounded_postprocess_analyze)

    def execute(self, fixture, **changes):
        return h._postprocess_r0b(**(fixture | changes))

    def reseal(self, fixture, name, change):
        values = []
        h.store.scan_stream(fixture["root"], name, visit=lambda key, value: values.append((key, value)))
        entries = change(values)
        data = b"".join(h.store._key_bytes(key) + b"\t" + records.encode(value) + b"\n"
                        for key, value in entries)
        (fixture["root"] / (name + ".jsonl")).write_bytes(data)
        seal = records.StreamDigest(name, sha256(data).hexdigest(), len(data), len(entries))
        if name == h.qualification.IDENTITY_STREAM:
            fixture["identity_seal"] = seal
        else:
            original = fixture["coordinator_result"]
            streams = tuple(seal if v.name == name else v for v in original.streams)
            fixture["coordinator_result"] = replace(original, streams=streams,
                archive_bytes=sum(v.byte_length for v in streams))

    def test_five_exact_phases_once_analysis_full_constant_and_separate_progress(self):
        with self.fixture() as fixture:
            events, calls = [], []
            def analyze(rows, **kwargs):
                calls.append((rows, kwargs))
                return _bounded_postprocess_analyze(rows, **kwargs)
            with patch.object(h.store, "scan_stream", wraps=h.store.scan_stream) as scanner:
                result = self.execute(fixture, _analyze=analyze, progress=events.append)
            self.assertEqual(len(calls), 1)
            self.assertEqual(tuple(v.phase for v in result.phases), readiness.POSTPROCESS_PHASES)
            self.assertEqual(events[0].phase, records.Phase.VALIDATION)
            self.assertTrue(all(v.complete and v.progress_bounded and v.processed == v.total
                                and v.wall_ns > 0 for v in result.phases))
            self.assertGreaterEqual(result.complete_wall_ns, sum(v.wall_ns for v in result.phases))
            self.assertEqual((result.bootstrap_replicates, result.bootstrap_n,
                              result.bootstrap_progress_count), (10_000, 1, 10_001))
            self.assertEqual(identity.BOOTSTRAP_REPLICATES, 10_000)
            self.assertIsNone(result.analysis_result.overall)
            self.assertIn("NOT_EFFECTIVENESS_EVIDENCE", result.analysis_result.context[0])
            for field in ("shared_bootstrap_complete", "compact_scalar_bootstrap", "streaming_reconstruction",
                          "readback_complete", "progress_bounded", "qualification_complete", "cleanup_complete"):
                self.assertTrue(getattr(result, field))
            self.assertEqual({p.name for p in fixture["root"].iterdir()},
                {v.name + ".jsonl" for v in result.streams})
            for seal in result.streams:
                self.assertEqual(sum(call.args[:2] == (fixture["root"], seal.name)
                    for call in scanner.call_args_list), 2)
            for artifact in result.artifacts:
                data = (fixture["output_root"] / artifact.name).read_bytes()
                self.assertEqual((len(data), sha256(data).hexdigest()),
                                 (artifact.byte_length, artifact.sha256))
            with self.assertRaises(FrozenInstanceError):
                result.readback_complete = False
            with self.assertRaises(FileExistsError):
                self.execute(fixture)

    def test_missing_supporting_stream_identity_and_unexpected_files_fail_before_analysis(self):
        for missing in ("operations", "resources", "qualification_identity", "control_decisions", "extra"):
            with self.subTest(missing=missing), self.fixture() as fixture:
                if missing == "extra":
                    (fixture["root"] / "unexpected.json").write_bytes(b"{}")
                else:
                    (fixture["root"] / (missing + ".jsonl")).unlink()
                with self.assertRaises(ValueError):
                    self.execute(fixture, _analyze=lambda *a, **k: self.fail("No invalid analysis"))

    def test_identity_seal_bytes_and_plan_drift_are_rejected(self):
        for mutation in ("bytes", "seal", "identity", "plan"):
            with self.subTest(mutation=mutation), self.fixture() as fixture:
                if mutation == "bytes":
                    path = fixture["root"] / "boards.jsonl"
                    path.write_bytes(path.read_bytes() + b"\n")
                elif mutation == "seal":
                    fixture["identity_seal"] = replace(fixture["identity_seal"], sha256="0" * 64)
                elif mutation == "identity":
                    self.reseal(fixture, "qualification_identity",
                        lambda entries: entries[:-1])
                else:
                    bad = (fixture["expected_identity"][0],
                        replace(fixture["expected_identity"][1], frame_label="WRONG")) + fixture["expected_identity"][2:]
                    fixture["expected_identity"], fixture["source_recheck"] = bad, lambda: bad
                with self.assertRaises(ValueError):
                    self.execute(fixture, _analyze=lambda *a, **k: self.fail("No invalid analysis"))

    def test_receipt_status_count_and_terminal_progress_cannot_be_upgraded(self):
        for mutation in ("fail", "incomplete", "count", "progress"):
            with self.subTest(mutation=mutation), self.fixture() as fixture:
                original = fixture["coordinator_result"]
                if mutation in ("fail", "incomplete"):
                    fixture["coordinator_result"] = replace(original,
                        status=records.AuditStatus.FAIL if mutation == "fail" else records.AuditStatus.INCOMPLETE)
                elif mutation == "count":
                    fixture["coordinator_result"] = replace(original, durable_units=original.durable_units + 1)
                else:
                    self.reseal(fixture, "operations", lambda entries:
                        [(key, replace(value, unit_id="durable_primary_count:2")
                          if value.unit_id.startswith("durable_primary_count:") else value) for key, value in entries])
                with self.assertRaises(ValueError):
                    self.execute(fixture, _analyze=lambda *a, **k: self.fail("No invalid analysis"))

    def test_resource_identity_missing_samples_and_caps_fail_closed(self):
        for mutation in ("owner", "method", "role", "missing", "extra", "cap"):
            with self.subTest(mutation=mutation), self.fixture() as fixture:
                def change(entries):
                    key, value = entries[0]
                    if mutation == "missing":
                        return []
                    if mutation == "extra":
                        return [((i,), value) for i in range(4)]
                    value = replace(value, **({"unit_id": "missing"} if mutation == "owner" else
                        {"method": records.MemoryMethod.RSS} if mutation == "method" else
                        {"process_role": records.ProcessRole.WORKER} if mutation == "role" else
                        {"coordinator_bytes": fixture["envelope"].coordinator_memory_cap_bytes + 1,
                         "combined_bytes": fixture["envelope"].coordinator_memory_cap_bytes + 1}))
                    return [(key, value)] + entries[1:]
                self.reseal(fixture, "resources", change)
                with self.assertRaises(ValueError):
                    self.execute(fixture, _analyze=lambda *a, **k: self.fail("No invalid analysis"))

    def test_validation_timeout_and_progress_exception_join_scanner_threads(self):
        for mutation in ("clock", "observer"):
            with self.subTest(mutation=mutation), self.fixture() as fixture:
                ticks = iter(range(0, 10 ** 16, 10 ** 12))
                def observer(fact):
                    if fact.processed:
                        raise RuntimeError("fixture progress failed")
                changes = ({"clock": lambda: next(ticks),
                            "envelope": replace(fixture["envelope"], validation_wall_ms=1)}
                           if mutation == "clock" else {"progress": observer})
                with self.assertRaises((ValueError, RuntimeError)):
                    self.execute(fixture, **changes,
                        _analyze=lambda *a, **k: self.fail("No invalid analysis"))
                self.assertFalse(any(t.is_alive() and t.name.startswith("i7-scan-")
                                     for t in threading.enumerate()))

    def test_each_later_phase_deadline_prevents_completion(self):
        for phase in (records.Phase.AGGREGATION, records.Phase.PUBLICATION,
                      records.Phase.READBACK, records.Phase.REPORT):
            with self.subTest(phase=phase), self.fixture() as fixture:
                offset = [0]
                def clock():
                    return h.time.perf_counter_ns() + offset[0]
                def observe(fact):
                    if fact.phase is phase:
                        offset[0] += 2_000_000
                envelope = replace(fixture["envelope"], **{phase.value.lower() + "_wall_ms": 1})
                with self.assertRaisesRegex(ValueError, "POSTPROCESS_PHASE_TIMEOUT"):
                    self.execute(fixture, clock=clock, progress=observe, envelope=envelope)
                self.assertFalse((fixture["output_root"] / "COMPLETE.json").exists())

    def test_raw_failure_dominates_prior_incomplete_and_never_reaches_analysis(self):
        with self.fixture() as fixture:
            fixture["coordinator_result"] = replace(fixture["coordinator_result"],
                status=records.AuditStatus.INCOMPLETE)
            self.reseal(fixture, "pairs", lambda entries:
                [(key, replace(value, p3_status=records.P3Status.FAIL)) for key, value in entries])
            with self.assertRaisesRegex(ValueError, "PRIOR_OR_DURABLE_FAILURE"):
                self.execute(fixture, _analyze=lambda *a, **k: self.fail("No failed analysis"))

    def test_source_recheck_before_validation_and_after_analysis(self):
        for fail_at in (1, 2, 3):
            with self.subTest(fail_at=fail_at), self.fixture() as fixture:
                calls = []
                def check():
                    calls.append(None)
                    return () if len(calls) == fail_at else fixture["expected_identity"]
                with self.assertRaisesRegex(ValueError, "SOURCE_CHANGED"):
                    self.execute(fixture, source_recheck=check)
                if fail_at == 1:
                    self.assertFalse(fixture["output_root"].exists())

    def test_missing_wrong_or_out_of_order_bootstrap_progress_rejected(self):
        for counts in ((), ((0, 9999),), ((0, 10000), (2, 10000)), ((0, 10000), (True, 10000))):
            with self.subTest(counts=counts), self.fixture() as fixture:
                def analyze(rows, **kwargs):
                    observe = kwargs.pop("bootstrap_progress")
                    for done, total in counts:
                        observe(done, total)
                    kwargs["bootstrap_progress"] = lambda *_: None
                    return _bounded_postprocess_analyze(rows, **kwargs)
                with self.assertRaisesRegex(ValueError, "BOOTSTRAP"):
                    self.execute(fixture, _analyze=analyze)

    def test_readback_drift_and_report_failure_never_return_success(self):
        for mutation in ("readback", "report"):
            with self.subTest(mutation=mutation), self.fixture() as fixture:
                if mutation == "readback":
                    def observe(fact):
                        if fact.phase is records.Phase.READBACK and fact.processed == 0:
                            path = fixture["output_root"] / "analysis.json"
                            path.write_bytes(path.read_bytes() + b" ")
                    with self.assertRaisesRegex(ValueError, "READBACK|PROGRESS_RANGE"):
                        self.execute(fixture, progress=observe)
                else:
                    with patch.object(h.report, "render_report_html", side_effect=RuntimeError("fixture report failed")):
                        with self.assertRaises(RuntimeError):
                            self.execute(fixture)
                self.assertFalse((fixture["output_root"] / "COMPLETE.json").exists())

    def test_production_default_calls_accepted_analyzer_once_and_keeps_frozen_count(self):
        with self.fixture() as fixture:
            original = h.analysis.analyze_effectiveness
            def bounded(rows, **kwargs):
                # Explicit test replacement of the production boundary, never
                # a production bootstrap-count argument or constant mutation.
                with patch.object(h.analysis, "analyze_effectiveness", new=original):
                    return _bounded_postprocess_analyze(rows, **kwargs)
            with patch.object(h.analysis, "analyze_effectiveness", side_effect=bounded) as invoked:
                result = self.execute(fixture, _analyze=None)
            invoked.assert_called_once()
            self.assertEqual(result.bootstrap_replicates, 10_000)
            self.assertEqual(identity.BOOTSTRAP_REPLICATES, 10_000)

    def test_callbacks_cannot_change_phases_and_input_directory_cannot_hold_outputs(self):
        with self.fixture() as fixture:
            with self.assertRaisesRegex(ValueError, "SEPARATE_OUTPUT"):
                self.execute(fixture, output_root=fixture["root"] / "nested")
            with self.assertRaisesRegex(ValueError, "SOURCE_RECHECK"):
                self.execute(fixture, source_recheck=None)
# POSTPROCESS_TESTS_END


# EVIDENCE_ACCOUNTING_TESTS_BEGIN
class R0AEvidenceSerializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures = tuple(_r0a_adapter_fixture(c) for c in (1, 2, 4))
        cls.measurements = tuple(h.adapt_r0a_concurrency(*value) for value in fixtures)
        cls.components = tuple(value[3] for value in fixtures)
        cls.traces = tuple(value[4] for value in fixtures)

    def test_roundtrip_preserves_all_raw_routes_setup_and_readiness_for_every_concurrency(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "r0a.json"
            h.write_r0a_evidence(path, self.measurements, self.components, self.traces)
            observed = h.read_r0a_evidence(path)
            self.assertEqual(observed, (self.measurements, self.components, self.traces))
            self.assertEqual(tuple(v.concurrency for v in observed[0]), (1, 2, 4))
            for measured, raw in zip(observed[0], observed[1]):
                self.assertEqual(tuple(v.route for v in measured.references), ("K", "D", "O_K_SETUP", "O_D_SETUP"))
                self.assertEqual(tuple(v.component for v in raw), tuple(operational.R0Component))
                self.assertTrue(raw[-2].setup_measurements)
                self.assertTrue(raw[-1].setup_measurements)
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                h.write_r0a_evidence(path, self.measurements, self.components, self.traces)
            self.assertEqual(path.read_bytes(), before)

    def test_missing_route_and_independent_raw_setup_tampering_reject_readback(self):
        baseline = h._r0a_evidence_node(self.measurements, self.components, self.traces)
        def missing_route(node):
            node["operational"][0].pop()
        def setup_memory(node):
            setup = node["operational"][0][-2]["fields"]["setup_measurements"][0]["fields"]
            setup["combined_memory_bytes"] += 1
        def setup_readback(node):
            node["operational"][0][-1]["fields"]["setup_measurements"][0]["fields"]["readback_complete"] = False
        def missing_progress(node):
            node["progress"][0][-1].pop()
        with tempfile.TemporaryDirectory() as directory:
            for index, mutate in enumerate((missing_route, setup_memory, setup_readback, missing_progress)):
                node = json.loads(h._canonical(baseline))
                mutate(node)
                path = Path(directory) / (str(index) + ".json")
                path.write_bytes(h._canonical(node))
                with self.subTest(mutation=index), self.assertRaises((h.HarnessError, readiness.ReadinessError,
                        operational.OperationalError)):
                    h.read_r0a_evidence(path)

    def test_closed_metadata_rejects_unknown_types_fields_and_reflective_payloads(self):
        from dataclasses import dataclass
        @dataclass(frozen=True)
        class Unregistered:
            value: int
        with self.assertRaisesRegex(h.HarnessError, "UNSUPPORTED_R0_METADATA"):
            h._fact_node(Unregistered(1))
        bad = (
            {"fact": "pathlib.Path", "fields": {"path": "outside"}},
            {"fact": "__import__", "fields": {"name": "os"}},
            {"enum": "os.system", "value": "never-run"},
            {"fact": "ComponentSizes", "fields": {"primary": 1}},
            {"fraction": [2, 4]}, {"fraction": [True, 1]},
            {"bytes": "AB"},
            {"record": records.encode(records.OperationEventRecord(records.Phase.VALIDATION,
                "fixture", records.EventKind.START, 0, 0, records.OperationStatus.RUNNING)).decode("ascii")},
        )
        for value in bad:
            with self.subTest(value=value), self.assertRaises((h.HarnessError, ValueError, TypeError)):
                h._fact_read(value)
        exact = (Fraction(7, 3), b"\x00\xff", records.AuditStatus.PASS,
                 readiness.ComponentSizes(1, 2, 0, 0, 3, 4))
        self.assertEqual(h._fact_read(h._fact_node(exact)), exact)


class R0BReadinessAdapterEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Existing I8 pure observation fixtures use their synthetic seed, not
        # real target counting, Nmax materialization, or bootstrap execution.
        from tests import test_program_k_e2_readiness as fixtures
        cls.measurements = fixtures._measurements()
        cls.expected = replace(fixtures._r0b(cls.measurements), complete_wall_ns=6)
        _, (k_positions, _, d_positions) = readiness._memberships(
            cls.expected.workload.selection.protocol_seed, cls.expected.workload.selection.ordered_indices)
        cls.receipts = tuple(operational.UnitReceipt(position, kind, records.AuditStatus.PASS,
            "SYNTHETIC_MATERIALIZED", 1, 0)
            for position in range(identity.CANDIDATE_MAX)
            for kind in ((execution.WorkerKind.PRIMARY,)
                + ((execution.WorkerKind.DETERMINISM,) if position in d_positions else ())
                + ((execution.WorkerKind.K_CONTROL,) if position in k_positions else ())))

    def facts(self):
        expected = self.expected
        supports = expected.supporting.streams
        coordinator = operational.CoordinatorResult(self.receipts, supports[:2], 10512, 10000,
            sum(v.byte_length for v in supports[:2]), records.AuditStatus.PASS)
        counts = tuple(zip(h._SYNTHETIC_FAMILIES, expected.workload.unit_counts))
        totals = tuple((name, count * getattr(expected.unit_bytes, name)) for name, count in counts)
        material = h.SyntheticMaterialization(coordinator, supports[2], expected.unit_bytes, totals, counts,
            expected.realized_max_unit_payload_bytes, 200, True, True)
        post = h.PostprocessingResult(expected.phases, None, supports, (),
            records.StreamDigest("postprocessing_operations", "a" * 64, 1, 1),
            expected.complete_wall_ns - 1, expected.bootstrap_replicates, expected.bootstrap_n,
            expected.bootstrap_replicates + 1, True, True, True, True, True, True, True)
        attributed = sum(v for _, v in totals)
        accounting = h.ArchiveAccounting((h.FileFact("bundle-bytes", attributed, "a" * 64),
            h.FileFact("supporting-bytes", expected.realized_fixed_allowance_bytes, "b" * 64)),
            attributed, expected.realized_fixed_allowance_bytes, expected.archive_bytes)
        return material, post, accounting

    def adapt(self, material=None, post=None, accounting=None, **changes):
        original = self.facts()
        material, post, accounting = tuple(old if new is None else new
            for old, new in zip(original, (material, post, accounting)))
        return h.adapt_r0b(self.measurements, self.expected.workload, material, post, accounting,
            **(dict(complete_wall_ns=self.expected.complete_wall_ns,
                max_combined_memory_bytes=self.expected.max_combined_memory_bytes,
                containment_complete=True, finalization=_finalization_fixture(accounting.archive_bytes)) | changes))

    def test_exact_immutable_observations_reach_existing_readiness_without_recalculation(self):
        result = self.adapt()
        self.assertEqual(result, self.expected)
        self.assertEqual(result.bootstrap_replicates, identity.BOOTSTRAP_REPLICATES)
        self.assertEqual(result.workload.selection.counts, self.expected.workload.selection.counts)
        self.assertEqual(result.workload.target, self.expected.workload.target)
        with self.assertRaises(FrozenInstanceError):
            result.realized_fixed_allowance_bytes = 0

    def test_support_stream_omission_phase_omission_and_incomplete_flags_fail_closed(self):
        material, post, accounting = self.facts()
        cases = [dict(post=replace(post, streams=tuple(v for v in post.streams if v.name != missing)))
                 for missing in ("operations", "resources", h.qualification.IDENTITY_STREAM)]
        cases += [dict(post=replace(post, phases=post.phases[:-1])),
                  dict(post=replace(post, streams=post.streams + (post.streams[0],))),
                  dict(post=replace(post, streams=(replace(post.streams[0], sha256="b" * 64),) + post.streams[1:])),
                  dict(material=replace(material, coordinator=replace(material.coordinator, receipts=self.receipts[:-1]))),
                  dict(material=replace(material, coordinator=replace(material.coordinator,
                      receipts=(replace(self.receipts[0], status=records.AuditStatus.INCOMPLETE),) + self.receipts[1:]))),
                  dict(material=replace(material, readback_complete=False)),
                  dict(material=replace(material, cleanup_complete=False)),
                  dict(material=replace(material, synthetic_non_evidence=False)),
                  dict(post=replace(post, qualification_complete=False)),
                  dict(post=replace(post, cleanup_complete=False)),
                  dict(post=replace(post, readback_complete=False)),
                  dict(post=replace(post, progress_bounded=False)),
                  dict(containment_complete=False)]
        for index, changes in enumerate(cases):
            with self.subTest(case=index), self.assertRaises((h.HarnessError, readiness.ReadinessError,
                    KeyError, ValueError)):
                self.adapt(**changes)

    def test_realized_count_swap_and_bootstrap_reduction_are_rejected(self):
        material, post, _ = self.facts()
        counts = dict(material.family_counts)
        counts["reference"] -= 1
        with self.assertRaisesRegex(h.HarnessError, "REALIZED_FAMILY_COUNTS"):
            self.adapt(material=replace(material, family_counts=tuple(counts.items())))
        for changed in (replace(post, bootstrap_replicates=9999), replace(post, bootstrap_n=9999),
                        replace(post, bootstrap_progress_count=10000),
                        replace(post, shared_bootstrap_complete=False),
                        replace(post, compact_scalar_bootstrap=False), replace(post, streaming_reconstruction=False)):
            with self.subTest(post=changed), self.assertRaises((readiness.ReadinessError, h.HarnessError)):
                self.adapt(post=changed)
        self.assertEqual(identity.BOOTSTRAP_REPLICATES, 10000)

    def test_fixed_allowance_exact_cap_passes_cap_plus_one_and_memory_archive_limits_fail(self):
        _, _, accounting = self.facts()
        limit = identity.FIXED_REPORT_RECEIPT_ALLOWANCE
        def accounting_with(fixed, attributed=accounting.attributable_bytes):
            return h.ArchiveAccounting((h.FileFact("bundle-bytes", attributed, "a" * 64),
                h.FileFact("supporting-bytes", fixed, "b" * 64)), attributed, fixed, attributed + fixed)
        result = self.adapt(accounting=accounting_with(limit))
        self.assertEqual(result.realized_fixed_allowance_bytes, limit)
        with self.assertRaisesRegex(readiness.ReadinessError, "FIXED_ALLOWANCE_CAP"):
            self.adapt(accounting=accounting_with(limit + 1))
        with self.assertRaisesRegex(readiness.ReadinessError, "ARCHIVE_CAP"):
            material, _, _ = self.facts()
            totals = dict(material.family_totals)
            totals["primary"] += identity.MAX_ARCHIVE_BYTES - accounting.attributable_bytes
            self.adapt(material=replace(material, family_totals=tuple(totals.items())),
                       accounting=accounting_with(4, identity.MAX_ARCHIVE_BYTES))
        with self.assertRaisesRegex(readiness.ReadinessError, "MEMORY_CAP"):
            self.adapt(max_combined_memory_bytes=identity.MAX_COMBINED_MEMORY_BYTES)
from contextlib import contextmanager as _accounting_contextmanager


class ClosedExperimentArchiveAccountingTests(unittest.TestCase):
    @_accounting_contextmanager
    def fixture(self):
        from tests import test_program_k_e2_readiness as readiness_fixtures
        plan = SyntheticMaterializationTests.plan()
        envelope = SyntheticMaterializationTests.envelope()
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as inputs:
            root = Path(directory)
            streams, outputs = root / "streams", root / "postprocessing"
            streams.mkdir()
            indices = tuple(v.board.game_index for v in plan)
            expected_identity = (records.ProtocolIdentity(h.qualification._PROTOCOL, identity.PROTOCOL_SHA256,
                h.qualification._BLOB, h.qualification._FREEZE), records.CorpusIdentity("SYNTHETIC_I7",
                min(indices), max(indices) + 1, len(plan), indices,
                identity.corpus_digest(plan[0].protocol_seed, len(plan), indices).hex(), ()), plan[0].runtime,
                records.SourceBlobIdentity("synthetic/archive.py", "a" * 40, "b" * 64, 1))
            with h.store.StreamWriter(streams, h.qualification.IDENTITY_STREAM) as writer:
                for ordinal, value in enumerate(expected_identity):
                    writer.append((ordinal,), value)
                identity_seal = writer.seal()
            with patch.object(operational.harness, "_coordinator_private_bytes", return_value=100):
                material = h.materialize_synthetic(plan, readiness.ComponentSizes(1, 1, 0, 0, 1, 1),
                    envelope, streams, identity_seal)
            post = h._postprocess_r0b(plan, material.coordinator, identity_seal, streams, envelope, outputs,
                expected_identity=expected_identity, source_recheck=lambda: expected_identity,
                _analyze=_bounded_postprocess_analyze)
            (root / "additional-support.txt").write_bytes(b"Every archive-local byte counts.\n")
            source = records.SourceBlobIdentity(h._HARNESS_PATH, "a" * 40, "b" * 64, 1)
            provenance = h.RunProvenance(h.SELECTION_SOURCE_HEAD, "c" * 40, (source,),
                ((source.path, source.sha256, source.byte_length, False),), plan[0].runtime,
                h.sys.executable, True)
            raw = _accepted_receipt_bytes()
            path = Path(inputs) / "selection-receipt.json"
            path.write_bytes(raw)
            receipt = h.load_selection_receipt(path)
            # Pure archive-closure fixture: it does not claim Nmax readiness.
            accounting = h._close_experiment_archive(root, material, post, receipt, provenance,
                                                     readiness_fixtures._workload())
            yield root, material, accounting

    def test_every_inner_file_counted_once_including_manifest_receipt_and_extra_support(self):
        with self.fixture() as (root, material, accounting):
            expected_files = {v.relative_to(root).as_posix(): v.stat().st_size
                              for v in root.rglob("*") if v.is_file()}
            self.assertEqual({v.path: v.byte_length for v in accounting.files}, expected_files)
            owned = {"streams/" + name + ".jsonl" for name in execution.STREAM_NAMES}
            self.assertEqual(accounting.attributable_bytes, sum(expected_files[name] for name in owned))
            self.assertEqual(accounting.fixed_allowance_bytes,
                             sum(size for name, size in expected_files.items() if name not in owned))
            self.assertEqual(accounting.archive_bytes, sum(expected_files.values()))
            self.assertIn("manifest.json", expected_files)
            self.assertIn("COMPLETE.json", expected_files)
            self.assertIn("additional-support.txt", expected_files)
            self.assertEqual(h.account_experiment_archive(root, material), accounting)
            decoded = h._fact_read(h._json_bytes((root / "coordinator.json").read_bytes()))
            self.assertEqual(decoded, material.coordinator)

    def test_required_stream_and_support_file_omissions_fail_closed(self):
        with self.fixture() as (root, material, accounting):
            required = ("streams/operations.jsonl", "streams/resources.jsonl",
                "streams/qualification_identity.jsonl", "streams/boards.jsonl", "coordinator.json",
                "status.json", "manifest.json", "COMPLETE.json", "postprocessing/analysis.json",
                "postprocessing/report.html", "postprocessing/postprocessing_operations.jsonl")
            for missing in required:
                observed = tuple(v for v in accounting.files if v.path != missing)
                with self.subTest(missing=missing), patch.object(h, "_inventory", return_value=observed), \
                     self.assertRaises(h.HarnessError):
                    h.account_experiment_archive(root, material)

    def test_stream_report_status_and_completion_tampering_cannot_pass_accounting(self):
        with self.fixture() as (root, material, _):
            for name in ("streams/resources.jsonl", "postprocessing/report.html", "status.json"):
                path = root / name
                original = path.read_bytes()
                try:
                    path.write_bytes(original + b" ")
                    with self.subTest(name=name), self.assertRaises((h.HarnessError, h.store.StoreError)):
                        h.account_experiment_archive(root, material)
                finally:
                    path.write_bytes(original)
            path = root / "COMPLETE.json"
            receipt = h.store.read_completion_receipt(root)
            path.write_bytes(records.encode(replace(receipt, manifest_sha256="0" * 64)) + b"\n")
            with self.assertRaisesRegex(h.HarnessError, "ARCHIVE_NOT_CLOSED"):
                h.account_experiment_archive(root, material)

    def test_actual_fixed_allowance_at_cap_passes_and_one_more_byte_fails_without_large_files(self):
        with self.fixture() as (root, material, accounting):
            limit = identity.FIXED_REPORT_RECEIPT_ALLOWANCE
            receipt = next(v for v in accounting.files if v.path == "COMPLETE.json")
            other_fixed = accounting.fixed_allowance_bytes - receipt.byte_length
            for increment in (0, 1):
                injected = tuple(replace(v, byte_length=limit - other_fixed + increment)
                    if v.path == "COMPLETE.json" else v for v in accounting.files)
                # The scanner observation is injected; no large file or changed
                # limit is needed. COMPLETE is outside its own hash inventory.
                with patch.object(h, "_inventory", return_value=injected):
                    if increment:
                        with self.assertRaisesRegex(h.HarnessError, "FIXED_ALLOWANCE_CAP"):
                            h.account_experiment_archive(root, material)
                    else:
                        observed = h.account_experiment_archive(root, material)
                        self.assertEqual(observed.fixed_allowance_bytes, limit)
                        self.assertEqual(observed.archive_bytes, observed.attributable_bytes + limit)

    def test_completion_receipt_cannot_omit_streams_or_rebind_protocol_source_and_corpus(self):
        with self.fixture() as (root, material, _):
            original = h.store.read_completion_receipt(root)
            changes = (dict(streams=tuple(v for v in original.streams if v.name != "resources")),
                       dict(protocol_sha256="0" * 64), dict(source_sha256="0" * 64),
                       dict(corpus_sha256="0" * 64))
            for change in changes:
                (root / "COMPLETE.json").write_bytes(records.encode(replace(original, **change)) + b"\n")
                with self.subTest(change=change), self.assertRaises(h.HarnessError):
                    h.account_experiment_archive(root, material)
class R0BLauncherAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures = tuple(_r0a_adapter_fixture(c, seed=bytes.fromhex(identity.PROTOCOL_SHA256))
                         for c in (1, 2, 4))
        cls.measurements = tuple(h.adapt_r0a_concurrency(*value) for value in fixtures)

    @_accounting_contextmanager
    def fixture(self, *, postprocess_failure=False):
        from contextlib import ExitStack
        with _provenance_fixture() as (repository, receipt, _), ExitStack() as stack:
            provenance = h.capture_run_provenance(receipt)
            prior_root = repository / "bounded-prior-r0a"
            prior_root.mkdir()
            prior_bytes = b"bounded authenticated prior manifest fixture\n"
            (prior_root / "manifest.json").write_bytes(prior_bytes)
            root = repository / "results" / "bounded-r0b-assembly"
            envelope = self.measurements[0].envelope
            workload = receipt.workload
            sizes = readiness.derive_r0b_sizing_plan(self.measurements).unit_bytes
            seals = tuple(records.StreamDigest(name, "a" * 64, 1, 1)
                for name in ("operations", "resources", h.qualification.IDENTITY_STREAM))
            counts = tuple(zip(h._SYNTHETIC_FAMILIES, workload.unit_counts))
            totals = tuple((name, count * getattr(sizes, name)) for name, count in counts)
            coordinator = operational.CoordinatorResult((), seals[:2], 10512, 10000, 2, records.AuditStatus.PASS)
            material = h.SyntheticMaterialization(coordinator, seals[2], sizes, totals, counts,
                max(v[3] for v in readiness.synthetic_unit_payloads(workload, sizes)), 128, True, True)
            phases = tuple(readiness.PhaseMeasurement(phase, 1, 1, 1, 1, True, True)
                           for phase in readiness.POSTPROCESS_PHASES)
            post = h.PostprocessingResult(phases, None, seals, (),
                records.StreamDigest("postprocessing_operations", "b" * 64, 1, 1),
                5, 10000, 10000, 10001, True, True, True, True, True, True, True)
            attributable = sum(v for _, v in totals)
            accounting = h.ArchiveAccounting((h.FileFact("attributed", attributable, "a" * 64),
                h.FileFact("support", 4, "b" * 64)), attributable, 4, attributable + 4)
            sentinel_plan, finish_result, calls = object(), {"bounded_fixture_complete": True}, []
            source_checks, adapted, finalized = [], [], []
            class Monitor:
                reason = None
                combined = 512
                active = False
                exited = False
                def __enter__(self):
                    self.active = True
                    calls.append("monitor_enter")
                    return self
                def check(self):
                    if not self.active or self.exited:
                        raise AssertionError("Monitor checked after being reaped")
                    calls.append("monitor_check")
                def __exit__(self, *error):
                    self.active, self.exited = False, True
                    calls.append("monitor_exit")
            monitor = Monitor()
            def authorize(value, expected):
                self.assertIs(type(value), FixtureAuthorization)
                self.assertEqual((value.mode, expected.name), ("R0_B", "R0_B"))
                calls.append("authorize_fixture")
            def build(actual_receipt, run_id):
                self.assertIs(actual_receipt, receipt)
                self.assertTrue(run_id.startswith("synthetic-i7-r0b-"))
                self.assertTrue(monitor.active)
                calls.append("plan")
                return sentinel_plan
            def identity_writer(path, plan):
                self.assertEqual(path, root / "experiment" / "streams")
                self.assertIs(plan, sentinel_plan)
                calls.append("identity")
                return seals[2]
            def materialize(plan, actual_sizes, actual_envelope, path, seal, *, progress):
                self.assertIs(plan, sentinel_plan)
                self.assertEqual((actual_sizes, actual_envelope, seal), (sizes, envelope, seals[2]))
                self.assertEqual(path, root / "experiment" / "streams")
                progress(0, 1)
                progress(1, 1)
                calls.append("materialize")
                return material
            def postprocess(plan, actual_coordinator, seal, path, actual_envelope, output, *, progress):
                self.assertIs(plan, sentinel_plan)
                self.assertIs(actual_coordinator, coordinator)
                self.assertEqual((seal, actual_envelope), (seals[2], envelope))
                self.assertEqual(output, root / "experiment" / "postprocessing")
                progress(None)
                calls.append("postprocess")
                if postprocess_failure:
                    raise RuntimeError("bounded postprocessing fixture failure")
                return post
            def close(path, actual_material, actual_post, actual_receipt, actual_provenance,
                      actual_workload, *, check, progress):
                self.assertEqual(path, root / "experiment")
                self.assertIs(actual_material, material)
                self.assertIs(actual_post, post)
                self.assertEqual((actual_receipt, actual_provenance, actual_workload),
                                 (receipt, provenance, workload))
                self.assertTrue(monitor.active)
                check()
                progress("writes", 0, 4)
                for value in range(1, 5):
                    progress("writes", value, 4)
                for stage, total in (("manifest_inventory", accounting.archive_bytes - 1),
                                     ("accounting_inventory", accounting.archive_bytes)):
                    progress(stage, 0, total)
                    progress(stage, total, total)
                calls.append("close_archive")
                return accounting
            def recheck(actual_receipt, actual_provenance):
                self.assertEqual((actual_receipt, actual_provenance), (receipt, provenance))
                source_checks.append(monitor.active)
                return provenance
            def adapt(measured, actual_workload, actual_material, actual_post, actual_accounting, **kwargs):
                self.assertTrue(monitor.exited)
                self.assertFalse(monitor.active)
                self.assertIs(measured, self.measurements)
                self.assertEqual(actual_workload, workload)
                self.assertIs(actual_material, material)
                self.assertIs(actual_post, post)
                self.assertIs(actual_accounting, accounting)
                finalization = kwargs["finalization"]
                self.assertTrue(finalization.complete)
                self.assertEqual(finalization.stages, _finalization_fixture(accounting.archive_bytes).stages)
                self.assertGreaterEqual(kwargs["complete_wall_ns"], post.complete_wall_ns + finalization.wall_ns)
                self.assertEqual(kwargs["max_combined_memory_bytes"], 512)
                self.assertTrue(kwargs["containment_complete"])
                supporting = readiness.SupportingStreams(seals, True, True, True, True, True, True)
                value = readiness.R0BMeasurement(sizing_seed := self.measurements[0].plan.protocol_seed,
                    10000, kwargs["complete_wall_ns"], phases, 10000, 10000,
                    True, True, True, True, True, True, sizes, accounting.archive_bytes, workload,
                    supporting, accounting.fixed_allowance_bytes, material.max_unit_payload_bytes,
                    kwargs["max_combined_memory_bytes"], True)
                self.assertEqual(sizing_seed, bytes.fromhex(identity.PROTOCOL_SHA256))
                adapted.append((value, finalization))
                calls.append("adapt_after_reap")
                return value
            def finish(actual_root, mode, actual_receipt, actual_provenance, details, digest, *, final_check):
                self.assertEqual((actual_root, mode), (root, "R0_B"))
                self.assertEqual((actual_receipt, actual_provenance), (receipt, provenance))
                self.assertTrue(monitor.exited)
                value, finalization = adapted[-1]
                self.assertEqual(h._fact_read(details["r0b"]), value)
                self.assertEqual(h._fact_read(details["finalization"]), finalization)
                self.assertEqual(h._fact_read(details["accounting"]), accounting)
                self.assertEqual(h._fact_read(details["r0a"]), self.measurements)
                self.assertEqual(details["r0a_source_manifest"], h.sha256(prior_bytes).hexdigest())
                self.assertEqual(digest, workload.selection.counts.corpus_digest.hex())
                before = len(source_checks)
                final_check()
                self.assertEqual(len(source_checks), before + 1)
                finalized.append(details)
                calls.append("finish")
                return finish_result
            for name, replacement in (("_authorize", authorize), ("build_selected_work_plan", build),
                    ("materialize_synthetic", materialize), ("_postprocess_r0b", postprocess),
                    ("_close_experiment_archive", close), ("_recheck_provenance", recheck),
                    ("adapt_r0b", adapt), ("_finish_run", finish)):
                stack.enter_context(patch.object(h, name, side_effect=replacement))
            stack.enter_context(patch.object(h, "load_selection_receipt", return_value=receipt))
            stack.enter_context(patch.object(h, "capture_run_provenance", return_value=provenance))
            stack.enter_context(patch.object(h, "validate_existing_run", return_value={"mode": "R0_A",
                "provenance": h._fact_node(provenance)}))
            stack.enter_context(patch.object(h, "read_r0a_evidence", return_value=(self.measurements, (), ())))
            stack.enter_context(patch.object(h.qualification, "write_identity", side_effect=identity_writer))
            stack.enter_context(patch.object(operational, "_R0MemoryMonitor", return_value=monitor))
            stack.enter_context(patch("benchmark_board.generate_board", side_effect=AssertionError("No boards")))
            stack.enter_context(patch.object(h.analysis, "analyze_effectiveness", side_effect=AssertionError("No bootstrap")))
            yield dict(receipt=receipt, root=root, prior=prior_root, envelope=envelope,
                monitor=monitor, calls=calls, source_checks=source_checks, finalized=finalized,
                finish_result=finish_result)

    def test_public_r0b_connects_frozen_inputs_finalization_reaped_monitor_and_final_source_check(self):
        with self.fixture() as fixture:
            result = h.launch_r0b(fixture["receipt"].path, fixture["root"], fixture["prior"], fixture["envelope"],
                                 authorization=FixtureAuthorization("R0_B"))
            self.assertIs(result, fixture["finish_result"])
            self.assertEqual(fixture["source_checks"], [True, False, False])
            self.assertEqual(len(fixture["finalized"]), 1)
            meaningful = [v for v in fixture["calls"] if v != "monitor_check"]
            self.assertEqual(meaningful, ["authorize_fixture", "monitor_enter", "plan", "identity",
                "materialize", "postprocess", "close_archive", "monitor_exit", "adapt_after_reap", "finish"])
            self.assertTrue((fixture["root"] / "INCOMPLETE.json").exists())
            self.assertFalse((fixture["root"] / "FAILED.json").exists())

    def test_public_r0b_exception_reaps_monitor_and_preserves_failure_without_finalization(self):
        with self.fixture(postprocess_failure=True) as fixture:
            with self.assertRaisesRegex(RuntimeError, "bounded postprocessing fixture failure"):
                h.launch_r0b(fixture["receipt"].path, fixture["root"], fixture["prior"], fixture["envelope"],
                             authorization=FixtureAuthorization("R0_B"))
            self.assertTrue(fixture["monitor"].exited)
            self.assertEqual(fixture["finalized"], [])
            self.assertNotIn("adapt_after_reap", fixture["calls"])
            self.assertTrue((fixture["root"] / "INCOMPLETE.json").exists())
            self.assertEqual(h._json_bytes((fixture["root"] / "FAILED.json").read_bytes()),
                             {"state": "FAILED_OR_INCOMPLETE"})
            self.assertFalse((fixture["root"] / "COMPLETE.json").exists())
# EVIDENCE_ACCOUNTING_TESTS_END


# FINALIZATION_TESTS_BEGIN
def _finalization_fixture(archive_bytes=2, wall_ns=1):
    return h.FinalizationFact((("writes", 4, 4),
        ("manifest_inventory", archive_bytes - 1, archive_bytes - 1),
        ("accounting_inventory", archive_bytes, archive_bytes),
        ("source_recheck", 1, 1), ("cleanup", 1, 1)), wall_ns, wall_ns, 10, True)


class R0BFinalizationTests(unittest.TestCase):
    def test_inventory_exposes_exact_bytes_with_bounded_chunks_and_no_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.bin").write_bytes(b"a" * 65_537)
            (root / "b.bin").write_bytes(b"bbb")
            (root / "empty").write_bytes(b"")
            (root / "excluded").write_bytes(b"excluded")
            events, checks = [], []
            result = h._inventory(root, exclude=("excluded",),
                check=lambda: checks.append(None), progress=lambda done, total: events.append((done, total)))
            self.assertEqual(events[0], (0, 65_540))
            self.assertEqual(events[-1], (65_540, 65_540))
            self.assertTrue(all(total == 65_540 for _, total in events))
            self.assertTrue(all(0 <= later[0] - first[0] <= 65_536
                                for first, later in zip(events, events[1:])))
            self.assertEqual(sum(v.byte_length for v in result), 65_540)
            self.assertEqual({p.name for p in root.iterdir()}, {"a.bin", "b.bin", "empty", "excluded"})
            self.assertGreaterEqual(len(checks), len(result))

    def test_inventory_detects_growth_shrink_and_propagates_callback_failure(self):
        for mode in ("grow", "shrink", "callback"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "input"
                path.write_bytes(b"initial")
                def observe(done, total):
                    if done == 0:
                        if mode == "callback":
                            raise RuntimeError("fixture observer failed")
                        path.write_bytes(b"expanded input" if mode == "grow" else b"x")
                with self.assertRaises((h.HarnessError, RuntimeError)):
                    h._inventory(directory, progress=observe)

    def test_fixed_closure_stages_and_cleanup_produce_immutable_external_fact(self):
        observed, checks = [], []
        original = h._close_experiment_archive
        def close(*args, **kwargs):
            observer = h._FinalizationObserver(lambda: checks.append(None))
            observed.append(observer)
            return original(*args, **kwargs, progress=observer.observe)
        fixture = ClosedExperimentArchiveAccountingTests()
        with patch.object(h, "_close_experiment_archive", side_effect=close), \
                fixture.fixture() as (root, _, accounting):
            before = h._inventory(root)
            observer, = observed
            for stage in ("source_recheck", "cleanup"):
                observer.observe(stage, 0, 1)
                observer.observe(stage, 1, 1)
            fact = observer.finish()
            self.assertTrue(fact.complete)
            self.assertEqual(fact.stages[0], ("writes", 4, 4))
            self.assertEqual(fact.stages[2], ("accounting_inventory", accounting.archive_bytes, accounting.archive_bytes))
            excluded = sum(v.byte_length for v in accounting.files if v.path in ("manifest.json", "COMPLETE.json"))
            self.assertEqual(fact.stages[1][1], accounting.archive_bytes - excluded)
            self.assertLessEqual(fact.max_progress_gap_ns, fact.wall_ns)
            self.assertGreaterEqual(fact.progress_events, 10)
            self.assertEqual(h._inventory(root), before)
            self.assertEqual(h._fact_read(h._fact_node(fact)), fact)
            self.assertGreaterEqual(len(checks), fact.progress_events)
            with self.assertRaises(FrozenInstanceError):
                fact.complete = False

    def test_missing_progress_and_regression_cannot_produce_complete_fact(self):
        ticks = iter(range(1, 100))
        observer = h._FinalizationObserver(lambda: None, clock=lambda: next(ticks))
        observer.observe("writes", 0, 4)
        observer.observe("writes", 2, 4)
        for args in (("writes", 1, 4), ("writes", 2, 5), ("source_recheck", 1, 1),
                     ("unknown", 0, 1), ("cleanup", True, 1)):
            with self.subTest(args=args), self.assertRaises(h.HarnessError):
                observer.observe(*args)
        with self.assertRaisesRegex(h.HarnessError, "FINALIZATION_PROGRESS_INCOMPLETE"):
            observer.finish()
        value = _finalization_fixture()
        for changes in (dict(stages=value.stages[:-1]), dict(max_progress_gap_ns=2),
                        dict(progress_events=1), dict(stages=(("writes", 3, 4),) + value.stages[1:])):
            with self.subTest(changes=changes), self.assertRaises(h.HarnessError):
                replace(value, **changes)

    def test_adapter_requires_complete_finalization_and_includes_residual_wall(self):
        fixture = R0BReadinessAdapterEvidenceTests()
        fixture.setUpClass()
        material, post, accounting = fixture.facts()
        finalization = _finalization_fixture(accounting.archive_bytes)
        for changes in (dict(finalization=None), dict(finalization=replace(finalization, complete=False)),
                        dict(complete_wall_ns=post.complete_wall_ns),
                        dict(finalization=_finalization_fixture(accounting.archive_bytes + 1))):
            with self.subTest(changes=changes), self.assertRaises(h.HarnessError):
                fixture.adapt(**changes)
        self.assertEqual(fixture.adapt().complete_wall_ns, post.complete_wall_ns + finalization.wall_ns)
# FINALIZATION_TESTS_END


# EVIDENCE_TESTS_BEGIN
from contextlib import contextmanager as _evidence_contextmanager, ExitStack as _EvidenceExitStack


@_evidence_contextmanager
def _provenance_fixture():
    """Only Git observations are fabricated; production provenance checks run."""
    q = h.qualification
    original_root = q._ROOT
    receipt_bytes = _accepted_receipt_bytes()
    paths = tuple(sorted(set(q._PROTECTED + ("benchmark_board.py", q._PROTOCOL, q._REPAIR_TEST)
                             + q._E2 + q._R0_SOURCE_PATHS)))
    committed = {path: b"bounded committed source fixture\n" for path in paths}
    for path in (q._PROTOCOL, q._AMENDMENT):
        committed[path] = (original_root / path).read_bytes()
    state = {"head": "a" * 40, "status": b"", "calls": [], "committed": committed,
             "ancestor_failure": None, "ignored": True, "head_reads": 0, "head_after": None}
    def git(*args, data=None):
        state["calls"].append(args)
        if args == ("rev-parse", "HEAD"):
            state["head_reads"] += 1
            head = state["head"]
            if state["head_after"] is not None and state["head_reads"] >= state["head_after"]:
                head = "b" * 40
            return head.encode("ascii") + b"\n"
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return state["status"]
        if args == ("ls-files", "--", q._E2[-1]):
            return q._E2[-1].encode("ascii") + b"\n"
        if args[:2] == ("merge-base", "--is-ancestor"):
            if args[2] == state["ancestor_failure"]:
                raise q.QualificationError("SOURCE_IDENTITY_UNAVAILABLE")
            return b""
        if args[:2] == ("check-ignore", "--"):
            return args[2].encode("ascii") + b"\n" if state["ignored"] else b""
        raise AssertionError("Unexpected read-only Git query: " + repr(args))
    def blobs(refs):
        return tuple((q._BLOB if path == q._PROTOCOL else "1" * 40, committed[path])
                     for _, path in (ref.split(":", 1) for ref in refs))
    with tempfile.TemporaryDirectory(prefix="bounded-r0-provenance-") as directory, _EvidenceExitStack() as stack:
        root = Path(directory)
        for path, data in committed.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (root / "results").mkdir()
        receipt_path = root / "accepted-receipt-copy.json"
        receipt_path.write_bytes(receipt_bytes)
        receipt = h.load_selection_receipt(receipt_path)
        stack.enter_context(patch.object(q, "_ROOT", root))
        stack.enter_context(patch.object(q, "_git", side_effect=git))
        stack.enter_context(patch.object(q, "_blobs", side_effect=blobs))
        yield root, receipt, state


class RunProvenanceTests(unittest.TestCase):
    def test_current_source_head_is_separate_from_selection_and_both_ancestors_checked(self):
        with _provenance_fixture() as (root, receipt, state):
            value = h.capture_run_provenance(receipt)
            self.assertEqual(value.selection_source_head, h.SELECTION_SOURCE_HEAD)
            self.assertEqual(value.r0_harness_source_head, "a" * 40)
            self.assertNotEqual(value.selection_source_head, value.r0_harness_source_head)
            for ancestor in (h.SELECTION_SOURCE_HEAD, h.SETUP_REPAIR_HEAD):
                self.assertIn(("merge-base", "--is-ancestor", ancestor, "a" * 40), state["calls"])
            self.assertIn(h._HARNESS_PATH, {item.path for item in value.sources})
            self.assertEqual(tuple(v[0] for v in value.working_files), tuple(v.path for v in value.sources))
            self.assertTrue(value.dont_write_bytecode)
            self.assertEqual(h._fact_read(h._fact_node(value)), value)

    def test_dirty_index_worktree_and_missing_ancestor_rejected(self):
        for status in (b" M experiments/program_k_e2_r0_harness.py\n",
                       b"M  experiments/program_k_e2_r0_harness.py\n", b"?? unexpected.py\n"):
            with self.subTest(status=status), _provenance_fixture() as (_, receipt, state):
                state["status"] = status
                with self.assertRaisesRegex(h.HarnessError, "COMMITTED_CLEAN_SOURCE_REQUIRED"):
                    h.capture_run_provenance(receipt)
        for ancestor in (h.SELECTION_SOURCE_HEAD, h.SETUP_REPAIR_HEAD):
            with self.subTest(ancestor=ancestor), _provenance_fixture() as (_, receipt, state):
                state["ancestor_failure"] = ancestor
                with self.assertRaises(h.qualification.QualificationError):
                    h.capture_run_provenance(receipt)

    def test_working_bytes_allow_only_proven_crlf_normalization(self):
        with _provenance_fixture() as (root, receipt, state):
            path = root / h._HARNESS_PATH
            data = state["committed"][h._HARNESS_PATH]
            path.write_bytes(data.replace(b"\n", b"\r\n"))
            value = h.capture_run_provenance(receipt)
            fact = next(v for v in value.working_files if v[0] == h._HARNESS_PATH)
            self.assertEqual(fact, (h._HARNESS_PATH, h.sha256(path.read_bytes()).hexdigest(),
                                    len(path.read_bytes()), True))
            path.write_bytes(data + b"changed semantic source\n")
            with self.assertRaisesRegex(h.HarnessError, "WORKING_SOURCE_IDENTITY_DRIFT"):
                h.capture_run_provenance(receipt)

    def test_frozen_working_authorities_reject_crlf_even_with_valid_committed_lf(self):
        for authority in (h.qualification._PROTOCOL, h.qualification._AMENDMENT):
            with self.subTest(authority=authority), _provenance_fixture() as (root, receipt, state):
                committed = state["committed"][authority]
                self.assertNotIn(b"\r\n", committed)
                self.assertIn(b"\n", committed)
                (root / authority).write_bytes(committed.replace(b"\n", b"\r\n"))
                with self.assertRaisesRegex(ValueError, "(?i)(protocol|amendment)"):
                    h.capture_run_provenance(receipt)

    def test_receipt_protocol_amendment_and_head_drift_fail_closed(self):
        with _provenance_fixture() as (_, receipt, _):
            Path(receipt.path).write_bytes(receipt.canonical_bytes + b"\n")
            with self.assertRaisesRegex(h.HarnessError, "SELECTION_RECEIPT_SIZE"):
                h.capture_run_provenance(receipt)
        for authority, expected in ((h.qualification._PROTOCOL, "PROTOCOL"),
                                    (h.qualification._AMENDMENT, "AMENDMENT")):
            with self.subTest(authority=authority), _provenance_fixture() as (_, receipt, state):
                state["committed"][authority] += b"\n"
                with self.assertRaisesRegex(ValueError, "(?i)" + expected):
                    h.capture_run_provenance(receipt)
        with _provenance_fixture() as (_, receipt, state):
            state["head_after"] = 4
            with self.assertRaisesRegex(h.HarnessError, "SOURCE_CHANGED_DURING_CAPTURE"):
                h.capture_run_provenance(receipt)

    def test_recheck_rejects_new_clean_head_and_changed_working_source(self):
        with _provenance_fixture() as (root, receipt, state):
            value = h.capture_run_provenance(receipt)
            self.assertIs(h._recheck_provenance(receipt, value), value)
            state["head"] = "b" * 40
            with self.assertRaisesRegex(h.HarnessError, "SOURCE_CHANGED_DURING_RUN"):
                h._recheck_provenance(receipt, value)
            state["head"] = "a" * 40
            (root / h._HARNESS_PATH).write_bytes(b"changed while run was active\n")
            with self.assertRaisesRegex(h.HarnessError, "WORKING_SOURCE_IDENTITY_DRIFT"):
                h._recheck_provenance(receipt, value)

    def test_provenance_rejects_forged_working_links_and_environment(self):
        with _provenance_fixture() as (_, receipt, _):
            value = h.capture_run_provenance(receipt)
            first = value.working_files[0]
            for bad in (("wrong-path",) + first[1:], (first[0], "x" * 64, first[2], first[3]),
                        (first[0], first[1], -1, first[3])):
                with self.subTest(bad=bad), self.assertRaises(h.HarnessError):
                    replace(value, working_files=(bad,) + value.working_files[1:])
            with self.assertRaises(h.HarnessError):
                replace(value, executable="")
            with patch.dict(os.environ, {"PYTHONDONTWRITEBYTECODE": "0"}):
                with self.assertRaisesRegex(h.HarnessError, "PYTHONDONTWRITEBYTECODE_REQUIRED"):
                    h.capture_run_provenance(receipt)


class FixtureAuthorization:
    """Test-only authorization identity; never an actual operator enum token."""
    def __init__(self, mode):
        self.mode = mode


@_evidence_contextmanager
def _fake_r0a_launch(*, measure_failure=None, recheck_failure=False):
    with _provenance_fixture() as (root, receipt, state), _EvidenceExitStack() as stack:
        fixtures = tuple(_r0a_adapter_fixture(c, seed=bytes.fromhex(identity.PROTOCOL_SHA256))
                         for c in (1, 2, 4))
        calls = []
        def authorize(value, expected):
            if type(value) is not FixtureAuthorization or value.mode != expected.name:
                raise AssertionError("Only explicit bounded fixture authorization is allowed")
        def materialize(plan, envelope, run_id):
            fixture = fixtures[(1, 2, 4).index(envelope.concurrency)]
            if plan != fixture[0]:
                raise AssertionError("Frozen R0-A plan changed")
            return fixture[2]
        def measure(work, kind, path, envelope, *, progress):
            calls.append((envelope.concurrency, kind))
            if measure_failure is not None:
                raise measure_failure
            fixture = fixtures[(1, 2, 4).index(envelope.concurrency)]
            value = fixture[3][tuple(operational.R0Component).index(kind)]
            if work != fixture[2]:
                raise AssertionError("Supplied fixture work changed")
            path.mkdir()
            h._exclusive_bytes(path / "fixture.txt", b"bounded injected observation only\n")
            for index, unit in enumerate(value.units):
                progress(unit, index + 1, len(work))
            return value
        original_measure = h._measure_r0a
        stack.enter_context(patch.object(h, "_authorize", side_effect=authorize))
        stack.enter_context(patch.object(h, "_materialize_r0a_work", side_effect=materialize))
        stack.enter_context(patch.object(h, "_measure_r0a", side_effect=lambda *args:
            original_measure(*args, measure=measure)))
        stack.enter_context(patch("benchmark_board.generate_board", side_effect=AssertionError("No boards")))
        stack.enter_context(patch.object(operational, "measure_r0_component", side_effect=AssertionError("No workers")))
        if recheck_failure:
            stack.enter_context(patch.object(h, "_recheck_provenance",
                                            side_effect=h.HarnessError("SOURCE_CHANGED_DURING_RUN")))
        yield root, receipt, fixtures, calls


class OperatorEvidenceTests(unittest.TestCase):
    def test_public_launch_requires_exact_authorization_before_any_io_or_workers(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(h, "load_selection_receipt", side_effect=AssertionError("No receipt IO")), \
                patch.object(h, "_materialize_r0a_work", side_effect=AssertionError("No materialization")), \
                patch.object(h, "materialize_synthetic", side_effect=AssertionError("No R0-B")):
            root = Path(directory) / "must-not-exist"
            for authorization in (None, "AUTHORIZE_ACTUAL_PROGRAM_K_E2_R0_A", FixtureAuthorization("R0_A")):
                with self.subTest(authorization=authorization), self.assertRaisesRegex(h.HarnessError, "AUTHORIZATION"):
                    h.launch_r0a("missing.json", root, (), authorization=authorization)
                with self.assertRaisesRegex(h.HarnessError, "AUTHORIZATION"):
                    h.launch_r0b("missing.json", root, "missing-r0a", None, authorization=authorization)
            with self.assertRaisesRegex(h.HarnessError, "AUTHORIZATION"):
                h.launch_r0a("missing.json", root, (), authorization=h.ActualRunAuthorization.R0_B)
            with self.assertRaisesRegex(h.HarnessError, "AUTHORIZATION"):
                h.launch_r0b("missing.json", root, "missing-r0a", None,
                             authorization=h.ActualRunAuthorization.R0_A)
            self.assertFalse(root.exists())

    def test_fresh_ignored_root_and_exclusive_writes(self):
        with _provenance_fixture() as (root, receipt, state):
            first, second = root / "results" / "first", root / "results" / "second"
            self.assertEqual(h._fresh_ignored_root(first), first)
            self.assertEqual(h._fresh_ignored_root(second), second)
            self.assertNotEqual(first, second)
            provenance = h.capture_run_provenance(receipt)
            h._begin_run(first, "R0_A", receipt, provenance)
            initial = (first / "INCOMPLETE.json").read_bytes()
            with self.assertRaises(h.HarnessError):
                h._fresh_ignored_root(first)
            with self.assertRaises(FileExistsError):
                h._begin_run(first, "R0_A", receipt, provenance)
            with self.assertRaises(FileExistsError):
                h._exclusive_bytes(first / "INCOMPLETE.json", b"replacement")
            self.assertEqual((first / "INCOMPLETE.json").read_bytes(), initial)
            with self.assertRaises(h.HarnessError):
                h._fresh_ignored_root(root / "outside-results")
            state["ignored"] = False
            with self.assertRaisesRegex(h.HarnessError, "IGNORED_RUN_ROOT_REQUIRED"):
                h._fresh_ignored_root(second)

    def test_worker_boundary_failure_preserves_explicit_failed_root_without_manifest(self):
        with _fake_r0a_launch(measure_failure=RuntimeError("bounded measurement failure")) as (root, receipt, fixtures, calls):
            output = root / "results" / "failed-fixture"
            with self.assertRaisesRegex(RuntimeError, "bounded measurement failure"):
                h.launch_r0a(receipt.path, output, tuple(v[1] for v in fixtures),
                             authorization=FixtureAuthorization("R0_A"))
            self.assertTrue((output / "INCOMPLETE.json").is_file())
            self.assertTrue((output / "FAILED.json").is_file())
            self.assertFalse((output / "manifest.json").exists())
            self.assertFalse((output / "COMPLETE.json").exists())
            self.assertEqual(len(calls), 1)
            with self.assertRaisesRegex(h.HarnessError, "RUN_FAILED_OR_INCOMPLETE"):
                h.validate_existing_run(output, receipt)

    def test_initial_marker_write_failure_still_marks_created_root_failed(self):
        with _fake_r0a_launch() as (root, receipt, fixtures, calls):
            output = root / "results" / "initial-write-failure"
            original = h._exclusive_bytes
            def write(path, data):
                if Path(path).name == "INCOMPLETE.json":
                    raise OSError("bounded initial marker failure")
                return original(path, data)
            with patch.object(h, "_exclusive_bytes", side_effect=write), self.assertRaises(OSError):
                h.launch_r0a(receipt.path, output, tuple(v[1] for v in fixtures),
                             authorization=FixtureAuthorization("R0_A"))
            self.assertTrue((output / "FAILED.json").is_file())
            self.assertFalse((output / "manifest.json").exists())
            self.assertEqual(calls, [])

    def test_source_change_after_measurement_cannot_publish_manifest(self):
        with _fake_r0a_launch(recheck_failure=True) as (root, receipt, fixtures, _):
            output = root / "results" / "source-drift"
            with self.assertRaisesRegex(h.HarnessError, "SOURCE_CHANGED_DURING_RUN"):
                h.launch_r0a(receipt.path, output, tuple(v[1] for v in fixtures),
                             authorization=FixtureAuthorization("R0_A"))
            self.assertTrue((output / "r0a-observations.json").is_file())
            self.assertTrue((output / "FAILED.json").is_file())
            self.assertFalse((output / "manifest.json").exists())

    def test_final_source_check_failure_cannot_publish_completion_receipt(self):
        with _fake_r0a_launch() as (root, receipt, fixtures, _):
            output = root / "results" / "final-source-check-failure"
            original, checks = h._recheck_provenance, []
            def recheck(receipt, provenance):
                checks.append(len(checks) + 1)
                if len(checks) == 2:
                    self.assertTrue((output / "manifest.json").is_file())
                    self.assertFalse((output / "COMPLETE.json").exists())
                    raise h.HarnessError("FINAL_SOURCE_DRIFT")
                return original(receipt, provenance)
            with patch.object(h, "_recheck_provenance", side_effect=recheck), \
                    self.assertRaisesRegex(h.HarnessError, "FINAL_SOURCE_DRIFT"):
                h.launch_r0a(receipt.path, output, tuple(v[1] for v in fixtures),
                             authorization=FixtureAuthorization("R0_A"))
            self.assertEqual(checks, [1, 2])
            self.assertTrue((output / "manifest.json").is_file())
            self.assertTrue((output / "FAILED.json").is_file())
            self.assertFalse((output / "COMPLETE.json").exists())
            with self.assertRaisesRegex(h.HarnessError, "RUN_FAILED_OR_INCOMPLETE"):
                h.validate_existing_run(output, receipt)

    def test_completion_is_last_after_full_readback_manifest_validation_and_final_check(self):
        with _fake_r0a_launch() as (root, receipt, fixtures, _):
            output = root / "results" / "ordered-final-publication"
            events = []
            original_read = h.read_r0a_evidence
            original_inventory = h._inventory
            original_validate = h._validate_run_manifest
            original_recheck = h._recheck_provenance
            original_write = h.store.write_completion_receipt
            def record(name):
                self.assertFalse((output / "COMPLETE.json").exists(),
                                 "No fallible archive/source validation after final publication")
                events.append(name)
            def read(*args, **kwargs):
                result = original_read(*args, **kwargs)
                record("observations_readback")
                return result
            def inventory(*args, **kwargs):
                result = original_inventory(*args, **kwargs)
                record("inventory_validated")
                return result
            def validate(*args, **kwargs):
                result = original_validate(*args, **kwargs)
                record("manifest_validated")
                return result
            def recheck(*args, **kwargs):
                result = original_recheck(*args, **kwargs)
                record("source_checked")
                return result
            def write(*args, **kwargs):
                self.assertIn("observations_readback", events)
                self.assertIn("inventory_validated", events)
                self.assertIn("manifest_validated", events)
                self.assertEqual(events[-2:], ["manifest_validated", "source_checked"])
                record("completion_write")
                return original_write(*args, **kwargs)
            with patch.object(h, "read_r0a_evidence", side_effect=read), \
                    patch.object(h, "_inventory", side_effect=inventory), \
                    patch.object(h, "_validate_run_manifest", side_effect=validate), \
                    patch.object(h, "_recheck_provenance", side_effect=recheck), \
                    patch.object(h.store, "write_completion_receipt", side_effect=write):
                h.launch_r0a(receipt.path, output, tuple(v[1] for v in fixtures),
                             authorization=FixtureAuthorization("R0_A"))
            self.assertEqual(events[-1], "completion_write")
            self.assertEqual(events.count("completion_write"), 1)
            self.assertGreater(events.index("manifest_validated"),
                               max(i for i, value in enumerate(events) if value == "observations_readback"))
            self.assertTrue((output / "COMPLETE.json").is_file())

    def test_fake_r0a_success_retains_real_codec_readiness_manifest_and_readback(self):
        with _fake_r0a_launch() as (root, receipt, fixtures, calls):
            output = root / "results" / "complete-fixture"
            manifest = h.launch_r0a(receipt.path, output, tuple(v[1] for v in fixtures),
                                   authorization=FixtureAuthorization("R0_A"))
            self.assertEqual(len(calls), 18)
            self.assertEqual(manifest, h.validate_existing_run(output, receipt))
            self.assertEqual(manifest["classification"], "OPERATIONAL_NON_EFFECTIVENESS_R0_EVIDENCE")
            self.assertEqual(manifest["provenance"]["fields"]["selection_source_head"], h.SELECTION_SOURCE_HEAD)
            self.assertEqual(manifest["provenance"]["fields"]["r0_harness_source_head"], "a" * 40)
            path = output / "r0a-observations.json"
            values, raw, traces = h.read_r0a_evidence(path)
            self.assertEqual(raw, tuple(v[3] for v in fixtures))
            self.assertEqual(traces, tuple(v[4] for v in fixtures))
            self.assertEqual(readiness.validate_r0a_measurements(values), values)
            original = path.read_bytes()
            node = h._json_bytes(original)
            node["readiness"][0]["fields"]["primary"]["fields"]["wall_ns"] += 1
            path.write_bytes(h._canonical(node))
            with self.assertRaisesRegex(h.HarnessError, "R0A_EVIDENCE_ADAPTER_MISMATCH"):
                h.read_r0a_evidence(path)
            with self.assertRaisesRegex(h.HarnessError, "RUN_ARCHIVE_DRIFT"):
                h.validate_existing_run(output, receipt)
            path.write_bytes(original)
            (output / "unreported.txt").write_bytes(b"unexpected supporting bytes")
            with self.assertRaisesRegex(h.HarnessError, "RUN_ARCHIVE_DRIFT"):
                h.validate_existing_run(output, receipt)
            (output / "unreported.txt").unlink()
            h._fail_run(output)
            with self.assertRaisesRegex(h.HarnessError, "RUN_FAILED_OR_INCOMPLETE"):
                h.validate_existing_run(output, receipt)

    def test_resealed_manifest_cannot_change_classification_status_or_forbidden_claims(self):
        with _fake_r0a_launch() as (root, receipt, fixtures, _):
            output = root / "results" / "metadata-tampering"
            h.launch_r0a(receipt.path, output, tuple(v[1] for v in fixtures),
                         authorization=FixtureAuthorization("R0_A"))
            manifest_path, completion_path = output / "manifest.json", output / "COMPLETE.json"
            original_manifest, original_completion = manifest_path.read_bytes(), completion_path.read_bytes()
            completion = h.store.read_completion_receipt(output)
            changes = (("classification", "EFFECTIVENESS_EVIDENCE"), ("status", "FINAL_ENVELOPE_ADMITTED"),
                       ("forbidden_actions", {"actual_e2": True}))
            for key, changed in changes:
                node = h._json_bytes(original_manifest)
                node[key] = changed
                data = h._canonical(node)
                manifest_path.write_bytes(data)
                completion_path.unlink()
                h.store.write_completion_receipt(output, replace(completion, manifest_sha256=h.sha256(data).hexdigest()))
                with self.subTest(key=key), self.assertRaises(h.HarnessError):
                    h.validate_existing_run(output, receipt)
                manifest_path.write_bytes(original_manifest)
                completion_path.write_bytes(original_completion)

    def test_metadata_codec_is_closed_and_canonical(self):
        self.assertEqual(h._fact_read(h._fact_node(Fraction(7, 3))), Fraction(7, 3))
        for node in ({"fact": "UnregisteredType", "fields": {}},
                     {"enum": "UnregisteredEnum", "value": "anything"},
                     {"fraction": [2, 4]}, {"bytes": "AB"}):
            with self.subTest(node=node), self.assertRaises(h.HarnessError):
                h._fact_read(node)
# EVIDENCE_TESTS_END


class V1MetadataSeamCompatibilityTests(unittest.TestCase):
    """Pre-Slice-1B wire nodes from the committed codec; no live run or I/O."""

    @staticmethod
    def _local_golden_facts():
        file = h.FileFact("fixture.bin", 7, "a" * 64)
        file_node = {"fact": "FileFact", "fields": {
            "path": "fixture.bin", "byte_length": 7, "sha256": "a" * 64}}
        accounting = h.ArchiveAccounting((file,), 3, 4, 7)
        accounting_node = {"fact": "ArchiveAccounting", "fields": {
            "files": [file_node], "attributable_bytes": 3,
            "fixed_allowance_bytes": 4, "archive_bytes": 7}}
        stages = (("writes", 1, 4), ("manifest_inventory", 0, 1),
                  ("accounting_inventory", 0, 1), ("source_recheck", 0, 1), ("cleanup", 0, 1))
        finalization = h.FinalizationFact(stages, 13, 5, 2, False)
        finalization_node = {"fact": "FinalizationFact", "fields": {
            "stages": [["writes", 1, 4], ["manifest_inventory", 0, 1],
                       ["accounting_inventory", 0, 1], ["source_recheck", 0, 1], ["cleanup", 0, 1]],
            "wall_ns": 13, "max_progress_gap_ns": 5, "progress_events": 2, "complete": False}}
        path = "experiments/program_k_e2_r0_harness.py"
        source = records.SourceBlobIdentity(path, "b" * 40, "c" * 64, 17)
        runtime = records.RuntimeIdentity("FixturePython", "0", "fixture-os", "fixture-platform",
                                          "fixture-arch", None)
        provenance = h.RunProvenance("cdba3513c23df77ba44449af1e551889a6954768", "e" * 40,
            (source,), ((path, "d" * 64, 19, True),), runtime, "synthetic-python", True)
        # Literal canonical embedded-record strings pin their historical wrapping
        # independently of either the harness wrapper or the new evidence codec.
        source_wire = ('{"fields":{"blob_id":"' + "b" * 40 + '","byte_length":17,"path":"'
                       + path + '","sha256":"' + "c" * 64
                       + '"},"kind":"source_blob_identity","version":1}')
        runtime_wire = ('{"fields":{"architecture":"fixture-arch","host":null,"os":"fixture-os",'
                        '"platform":"fixture-platform","python_implementation":"FixturePython",'
                        '"python_version":"0"},"kind":"runtime_identity","version":1}')
        provenance_node = {"fact": "RunProvenance", "fields": {
            "selection_source_head": "cdba3513c23df77ba44449af1e551889a6954768",
            "r0_harness_source_head": "e" * 40, "sources": [{"record": source_wire}],
            "working_files": [[path, "d" * 64, 19, True]], "runtime": {"record": runtime_wire},
            "executable": "synthetic-python", "dont_write_bytecode": True}}
        return ((file, file_node), (accounting, accounting_node),
                (finalization, finalization_node), (provenance, provenance_node))

    def test_four_harness_public_fact_names_keep_literal_v1_nodes_and_exact_types(self):
        pairs = self._local_golden_facts()
        self.assertEqual({type(value) for value, _ in pairs},
                         {h.RunProvenance, h.FileFact, h.ArchiveAccounting, h.FinalizationFact})
        for value, expected in pairs:
            with self.subTest(fact=type(value).__name__):
                self.assertEqual(h._fact_node(value), expected)
                rebuilt = h._fact_read(expected)
                self.assertIs(type(rebuilt), type(value))
                self.assertEqual(rebuilt, value)
                self.assertEqual(h._fact_node(rebuilt), expected)
                self.assertEqual(h._canonical(h._fact_node(value)),
                    json.dumps(expected, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n")
                with self.assertRaises(FrozenInstanceError):
                    setattr(rebuilt, fields(rebuilt)[0].name, None)
        accounting = h._fact_read(pairs[1][1])
        self.assertIs(type(accounting.files), tuple)
        self.assertIs(type(accounting.files[0]), h.FileFact)
        provenance = h._fact_read(pairs[3][1])
        self.assertIs(type(provenance.sources[0]), records.SourceBlobIdentity)
        self.assertIs(type(provenance.runtime), records.RuntimeIdentity)

    def test_wrapper_call_shapes_and_representative_scalar_wire_remain_exact(self):
        self.assertEqual(tuple(inspect.signature(h._fact_node).parameters), ("value",))
        self.assertEqual(tuple(inspect.signature(h._fact_read).parameters), ("node",))
        value = (None, "literal", 7, True, False, b"\x00\xff", Fraction(-7, 3),
                 records.AuditStatus.INCOMPLETE)
        node = [None, "literal", 7, True, False, {"bytes": "00ff"},
                {"fraction": [-7, 3]}, {"enum": "AuditStatus", "value": "INCOMPLETE"}]
        self.assertEqual(h._fact_node(value), node)
        restored = h._fact_read(node)
        self.assertEqual(restored, value)
        self.assertEqual(tuple(type(item) for item in restored), tuple(type(item) for item in value))

    def test_wrapper_preserves_harness_error_diagnoses_and_closed_vocabulary(self):
        with self.assertRaisesRegex(h.HarnessError, "UNSUPPORTED_R0_METADATA"):
            h._fact_node(object())
        cases = (({"fact": "Unregistered", "fields": {}}, "UNSUPPORTED_METADATA_FACT"),
                 ({"enum": "Unregistered", "value": "PASS"}, "UNSUPPORTED_METADATA_ENUM"),
                 ({"fact": "FileFact", "fields": {"path": "fixture.bin"}}, "METADATA_FIELDS_MISMATCH"),
                 ({"fraction": [2, 4]}, "NONCANONICAL_R0_FRACTION"),
                 ({"bytes": "FF"}, "NONCANONICAL_R0_BYTES"))
        for node, diagnosis in cases:
            with self.subTest(diagnosis=diagnosis), self.assertRaisesRegex(h.HarnessError, diagnosis):
                h._fact_read(node)

    def test_harness_local_constructor_validation_is_unchanged(self):
        file, accounting, finalization, provenance = (value for value, _ in self._local_golden_facts())
        cases = ((file, {"byte_length": True}), (file, {"path": "../escape"}),
                 (accounting, {"archive_bytes": 8}), (accounting, {"files": [file]}),
                 (finalization, {"complete": True}), (finalization, {"wall_ns": 0}),
                 (provenance, {"dont_write_bytecode": False}),
                 (provenance, {"selection_source_head": "f" * 40}))
        for value, changes in cases:
            with self.subTest(fact=type(value).__name__, changes=changes), self.assertRaises(h.HarnessError):
                replace(value, **changes)

    def test_existing_v1_schema_owners_retain_exact_identifiers(self):
        # These owners intentionally remain V1. Inspecting code constants avoids
        # invoking I/O/orchestration merely to exercise their unchanged literals.
        owners = ((h._r0a_evidence_node, "program-k-e2-r0a-observations/v1"),
                  (h.read_r0a_evidence, "program-k-e2-r0a-observations/v1"),
                  (h._finish_run, "program-k-e2-r0-run/v1"),
                  (h._validate_run_manifest, "program-k-e2-r0-run/v1"),
                  (h._close_experiment_archive, "program-k-e2-r0b-experiment/v1"),
                  (h.account_experiment_archive, "program-k-e2-r0b-experiment/v1"))
        for function, expected in owners:
            with self.subTest(owner=function.__name__):
                self.assertIn(expected, function.__code__.co_consts)
                self.assertNotIn(expected[:-1] + "2", function.__code__.co_consts)


# Slice 1F fixtures are deliberately tiny, supplied non-boards. They neither
# calibrate a profile nor run a corpus, constructor reference search or solver.
_TEXT_PROFILE = b"\x63" * 32
_TEXT_CAP = 131072
_TEXT_FAMILIES = (
    ("primary", 0, 0, execution.WorkerKind.PRIMARY),
    ("k_control", 1, 2, execution.WorkerKind.K_CONTROL),
    ("oracle_primary", 2, 0, execution.WorkerKind.PRIMARY),
    ("oracle_repeat", 3, 1, execution.WorkerKind.DETERMINISM),
    ("determinism", 4, 1, execution.WorkerKind.DETERMINISM),
)


def _text_fixture(oracle=1, position=0):
    runtime = records.RuntimeIdentity("FixturePython", "0", "fixture-os",
                                      "fixture-platform", "fixture-arch", None)
    work = execution.BoardWork(position, h.synthetic_board_identity(2_000_000_050_000),
        bytes.fromhex(identity.PROTOCOL_SHA256), "slice1f-bounded-fixture",
        True, True, True, runtime)
    sizes = readiness.ComponentSizes(1, 1, oracle, oracle, 1, 1)
    primary = h.build_synthetic_bundle(work, execution.WorkerKind.PRIMARY, sizes,
                                        max_payload_bytes=_TEXT_CAP)
    bundles = {execution.WorkerKind.PRIMARY: primary}
    for kind in (execution.WorkerKind.DETERMINISM, execution.WorkerKind.K_CONTROL):
        bundles[kind] = h.build_synthetic_bundle(work, kind, sizes, primary,
                                                 max_payload_bytes=_TEXT_CAP)
    return work, bundles


def _text_owned(name, kind, family):
    # Independent frozen ownership map, not a call to the constructor's map.
    if kind is execution.WorkerKind.PRIMARY:
        owner = ("reference" if name == "control_maintenance" else
                 "oracle_primary" if name == "oracle_b_audits" else "primary")
    elif kind is execution.WorkerKind.DETERMINISM:
        owner = "oracle_repeat" if name == "repeat_oracle_b_audits" else "determinism"
    else:
        owner = "k_control"
    return owner == family


def _text_family_metrics(view, family):
    rows = tuple(row for row in view.rows if _text_owned(row.stream_name, view.bundle.kind, family))
    return sum(len(row.frame_bytes) for row in rows), sum(len(row.logical_bytes) for row in rows)


def _text_with_literal(bundle, family, text):
    """Independent test mutation for canonical-size and semantic comparisons."""
    stream = {"primary": "evaluators", "determinism": "repeat_evaluators",
              "k_control": "kcontrol_maintenance", "oracle_primary": "oracle_b_audits",
              "oracle_repeat": "repeat_oracle_b_audits"}[family]
    streams = dict(bundle.streams)
    values = list(streams[stream])
    indices = range(2) if family.startswith("oracle_") else (-1,) if family == "k_control" else (0,)
    for index in indices:
        item = records.decode(values[index])
        if family.startswith("oracle_"):
            expected = replace(item.expected, shared_kernel_evidence=text)
            actual = replace(item.actual, shared_kernel_evidence=text)
            item = replace(item, expected=expected, actual=actual,
                expected_digest=records.oracle_b_snapshot_digest(expected),
                actual_digest=records.oracle_b_snapshot_digest(actual))
        elif family == "k_control":
            item = replace(item, soundness=tuple((key, text if key == "detail" else value)
                                                  for key, value in item.soundness))
        else:
            item = replace(item, detail=text)
        values[index] = records.encode(item)
    streams[stream] = tuple(values)
    return replace(bundle, streams=tuple((name, streams[name]) for name, _ in bundle.streams))


def _text_logical_bytes(bundle, family):
    return sum(len(data) for name, values in bundle.streams if _text_owned(name, bundle.kind, family)
               for data in values)


def _text_trial(ordinal, knob, p=100, logical=100, *, physical_target=100,
                logical_target=100, reason=None):
    evaluation = readiness.evaluate_family_size("primary", physical_target, logical_target, p, logical)
    rejection = evaluation.rejection_reason if reason is None else reason
    return h.TextTrial(ordinal, knob, 0, p, logical, p - physical_target,
        logical - logical_target, logical + 11, logical + 21, p + 11, p + 51,
        rejection is None, rejection)


class TextEntropyTests(unittest.TestCase):
    @staticmethod
    def raw(family_id, rank, position, block):
        domain = (b"PROGRAM_K_R0B_TEXT_FILL_V1\0" + bytes((family_id, rank))
                  + position.to_bytes(4, "big") + block.to_bytes(8, "big"))
        return shake_256(domain).digest(49152)

    def test_exact_tag_empty_entropy_and_small_canonical_base64_lengths(self):
        self.assertEqual(h._text_filler("primary", 0, 3, 0), "SYNTHETIC_NON_EVIDENCE|L:xxx|H:")
        self.assertEqual(h._text_filler("primary", 0, 0, 0), "SYNTHETIC_NON_EVIDENCE|L:|H:")
        self.assertEqual(h._text_entropy("primary", 0, 0), "")
        for raw_size, encoded_size in ((1, 4), (2, 4), (3, 4), (4, 8)):
            with self.subTest(raw_size=raw_size):
                value = h._text_entropy("primary", 0, raw_size)
                self.assertEqual(len(value), encoded_size)
                self.assertEqual(value, base64.b64encode(self.raw(0, 0, 0, 0)[:raw_size]).decode("ascii"))
                self.assertFalse(any(c.isspace() for c in value))

    def test_exact_family_rank_position_and_block_domains_are_repeatable(self):
        outputs = []
        for family, family_id, rank, _ in _TEXT_FAMILIES:
            for position in (0, 9999):
                with self.subTest(family=family, position=position):
                    actual = h._text_entropy(family, position, 49153)
                    expected = base64.b64encode(self.raw(family_id, rank, position, 0)
                                               + self.raw(family_id, rank, position, 1)[:1]).decode("ascii")
                    self.assertEqual(actual, expected)
                    self.assertEqual(h._text_entropy(family, position, 49153), actual)
                    outputs.append(actual)
        self.assertEqual(len(set(outputs)), 10)

    def test_full_block_and_partial_concatenation_is_canonical_base64(self):
        full = h._text_entropy("oracle_repeat", 9999, 49152)
        self.assertEqual(len(full), 65536)
        self.assertFalse(full.endswith("="))
        for tail in (1, 2, 3, 4):
            expected = full + base64.b64encode(self.raw(3, 1, 9999, 1)[:tail]).decode("ascii")
            self.assertEqual(h._text_entropy("oracle_repeat", 9999, 49152 + tail), expected)
            self.assertEqual(base64.b64decode(expected, validate=True),
                             self.raw(3, 1, 9999, 0) + self.raw(3, 1, 9999, 1)[:tail])

    def test_exact_constructor_local_integer_and_family_domain(self):
        for position in (-1, 10000, True, 1.0, "0"):
            with self.subTest(position=position), self.assertRaises(ValueError):
                h._text_entropy("primary", position, 1)
        for family in ("reference", "PRIMARY", 0, None):
            with self.subTest(family=family), self.assertRaises(ValueError):
                h._text_entropy(family, 0, 1)
        for value in (-1, True, 1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                h._text_filler("primary", 0, value, 0)
            with self.subTest(value=value), self.assertRaises(ValueError):
                h._text_entropy("primary", 0, value)

    def test_no_random_os_entropy_or_clock_source_is_used(self):
        import random
        with patch.object(os, "urandom", side_effect=AssertionError("No OS entropy")), \
             patch.object(random, "random", side_effect=AssertionError("No randomness")), \
             patch.object(h.time, "time", side_effect=AssertionError("No time salt")), \
             patch.object(h.time, "time_ns", side_effect=AssertionError("No time salt")), \
             patch.object(h.time, "monotonic_ns", side_effect=AssertionError("No time salt")), \
             patch.object(h.time, "perf_counter_ns", side_effect=AssertionError("No time salt")):
            self.assertEqual(h._text_filler("primary", 0, 7, 4),
                "SYNTHETIC_NON_EVIDENCE|L:xxxxxxx|H:"
                + base64.b64encode(self.raw(0, 0, 0, 0)[:4]).decode("ascii"))

    def test_check_callback_observes_each_repetition_and_entropy_chunk(self):
        checks = []
        h._text_filler("primary", 0, 2 * 65536 + 1, 2 * 49152 + 1,
                       _check=lambda: checks.append(1))
        self.assertGreaterEqual(len(checks), 6)
        for use_entropy in (False, True):
            calls = []
            def stop():
                calls.append(1)
                if len(calls) == 2:
                    raise RuntimeError("private cancellation")
            with self.subTest(entropy=use_entropy), self.assertRaisesRegex(RuntimeError, "private cancellation"):
                h._text_filler("primary", 0, 0 if use_entropy else 3 * 65536,
                               3 * 49152 if use_entropy else 0, _check=stop)
            self.assertEqual(len(calls), 2)

    def test_q_base64_ell_integer_arithmetic_and_overtaking(self):
        for multiplicity in (1, 4):
            for deficit in (-1, 0, 1, 7, 9):
                target, baseline = 100 + deficit, 100
                q = (max(0, deficit) + multiplicity - 1) // multiplicity
                for knob in (0, 1, 2, 3, 4, 6, 7, 9):
                    b = 4 * ((knob + 2) // 3)
                    with self.subTest(m=multiplicity, deficit=deficit, knob=knob):
                        self.assertEqual(h._text_lengths(target, baseline, multiplicity, knob),
                                         (q, b, max(0, q - b)))


class TextSearchSchedulerTests(unittest.TestCase):
    def run_search(self, upper, function, target=100, check=None):
        visited = []
        def evaluate(knob, ordinal):
            visited.append(knob)
            return function(knob, ordinal)
        trials, selected = h._search_text_trials(upper, target, evaluate, _check=check)
        self.assertEqual(tuple(visited), tuple(trial.h for trial in trials))
        self.assertEqual(tuple(trial.ordinal for trial in trials), tuple(range(1, len(trials) + 1)))
        self.assertLessEqual(len(trials), 8)
        self.assertEqual(len(set(visited)), len(visited))
        return trials, selected

    def test_first_zero_second_high_and_no_ninth_trial(self):
        function = lambda knob, ordinal: _text_trial(ordinal, knob, 50)
        first = self.run_search(100, function)
        self.assertEqual(first, self.run_search(100, function))
        self.assertEqual(tuple(t.h for t in first[0])[:2], (0, 100))
        self.assertEqual(len(first[0]), 8)
        self.assertIsNone(first[1])
        singleton, _ = self.run_search(0, function)
        self.assertEqual(tuple(t.h for t in singleton), (0,))
        all_values, _ = self.run_search(3, function)
        self.assertEqual(set(t.h for t in all_values), set(range(4)))

    def test_secant_targets_physical_floor_and_uses_integer_floor(self):
        trials = (_text_trial(1, 0, 10), _text_trial(2, 10, 40))
        self.assertEqual(h._next_text_h(trials, 10, 20), 3)
        negative_slope = (_text_trial(1, 0, 40), _text_trial(2, 10, 10))
        self.assertEqual(h._next_text_h(negative_slope, 10, 20), 6)

    def test_pair_selection_uses_exact_distance_then_a_then_b(self):
        trials = (_text_trial(1, 0, 90), _text_trial(2, 100, 110),
                  _text_trial(3, 20, 99), _text_trial(4, 70, 102))
        self.assertEqual(h._next_text_h(trials, 100, 100), 36)
        tied = (_text_trial(1, 0, 90), _text_trial(2, 100, 110),
                _text_trial(3, 20, 90), _text_trial(4, 70, 110))
        self.assertEqual(h._next_text_h(tied, 100, 100), 35)

    def test_out_of_range_duplicate_and_equal_physical_fallbacks(self):
        cases = ((_text_trial(1, 0, 10), _text_trial(2, 10, 11)),
                 (_text_trial(1, 0, 100), _text_trial(2, 10, 200)),
                 (_text_trial(1, 0, 10), _text_trial(2, 10, 10)))
        for trials in cases:
            with self.subTest(trials=trials):
                self.assertEqual(h._next_text_h(trials, 10, 100), 5)

    def test_largest_untested_integer_gap_ties_choose_lower_gap(self):
        trials = tuple(_text_trial(i + 1, knob, 50) for i, knob in enumerate((0, 8, 4)))
        self.assertEqual(h._next_text_h(trials, 8, 100), 2)
        full = tuple(_text_trial(i + 1, i, 50) for i in range(4))
        self.assertIsNone(h._next_text_h(full, 3, 100))

    def test_nonmonotonic_physical_observations_do_not_prune_any_gap(self):
        values = {0: 110, 16: 110, 8: 90, 4: 101, 12: 99, 2: 100, 6: 80, 10: 120}
        trials, selected = self.run_search(16,
            lambda knob, ordinal: _text_trial(ordinal, knob, values.get(knob, 95)))
        # Equal endpoints first force the midpoint. Subsequent nonmonotonic
        # measurements must leave both sides of that midpoint available.
        self.assertEqual(tuple(t.h for t in trials)[:4], (0, 16, 8, 4))
        self.assertTrue(any(t.h > 8 and t.h < 16 for t in trials))
        eligible = [t for t in trials if t.eligible]
        self.assertEqual(selected, min(eligible, key=lambda t: (t.actual_physical_bytes,
                         t.actual_logical_bytes, t.h)))

    def test_first_eligible_does_not_stop_and_final_lexicographic_minimum(self):
        trials, selected = self.run_search(20, lambda knob, ordinal:
            _text_trial(ordinal, knob, 110 if knob == 0 else 100,
                        101 if knob == 20 else 100))
        self.assertEqual(len(trials), 8)
        self.assertTrue(trials[0].eligible)
        self.assertNotEqual(selected, trials[0])
        self.assertEqual(selected, min((t for t in trials if t.eligible),
            key=lambda t: (t.actual_physical_bytes, t.actual_logical_bytes, t.h)))

    def test_callback_failure_after_eligible_trial_aborts_instead_of_returning_it(self):
        visited, callbacks = [], []
        def evaluate(knob, ordinal):
            visited.append(knob)
            return _text_trial(ordinal, knob)
        def check():
            callbacks.append(len(visited))
            if len(visited) == 1:
                raise RuntimeError("cancel after eligible")
        with self.assertRaisesRegex(RuntimeError, "cancel after eligible"):
            h._search_text_trials(100, 100, evaluate, _check=check)
        self.assertEqual(visited, [0])
        self.assertEqual(callbacks[0], 0)

    def test_callback_wraps_each_candidate_and_evaluator_errors_are_fatal(self):
        calls = []
        def evaluate(knob, ordinal):
            calls.append(("trial", knob))
            return _text_trial(ordinal, knob)
        h._search_text_trials(1, 100, evaluate, _check=lambda: calls.append(("check", None)))
        self.assertEqual(calls, [("check", None), ("trial", 0), ("check", None),
                                 ("check", None), ("trial", 1), ("check", None)])
        with self.assertRaisesRegex(MemoryError, "resource"):
            h._search_text_trials(5, 100,
                lambda *_: (_ for _ in ()).throw(MemoryError("resource")))

    def test_window_and_three_floor_reasons_remain_in_complete_trial_ledger(self):
        metrics = ((100, 100), (4196, 100), (4197, 100), (100, 99), (99, 100), (99, 99))
        trials, selected = self.run_search(5, lambda knob, ordinal:
            _text_trial(ordinal, knob, *metrics[knob]))
        by_knob = {trial.h: trial for trial in trials}
        self.assertEqual(set(by_knob), set(range(6)))
        self.assertTrue(by_knob[0].eligible and by_knob[1].eligible)
        self.assertEqual(by_knob[2].rejection_reason, "SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT")
        self.assertEqual(by_knob[3].rejection_reason, "SYNTHETIC_LOGICAL_MINIMUM_SHORTFALL")
        self.assertEqual(by_knob[4].rejection_reason, "SYNTHETIC_PHYSICAL_MINIMUM_SHORTFALL")
        self.assertEqual(by_knob[5].rejection_reason, "SYNTHETIC_BOTH_MINIMA_SHORTFALL")
        self.assertEqual(selected, by_knob[0])

    def test_terminal_window_and_general_exhaustion_keep_specific_trial_failures(self):
        window = (_text_trial(1, 0, 4197), _text_trial(2, 2, 4200))
        self.assertEqual(h._text_terminal_reason(window), "SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT")
        shortfall = (_text_trial(1, 0, 99), _text_trial(2, 2, 98))
        self.assertEqual(h._text_terminal_reason(shortfall), "SYNTHETIC_SIZING_SEARCH_EXHAUSTED")
        mixed = (_text_trial(1, 0, 4197), _text_trial(2, 2, 99),
                 _text_trial(3, 1, 101, reason="SYNTHETIC_TRIAL_SEMANTIC"))
        before = tuple(t.rejection_reason for t in mixed)
        self.assertEqual(h._text_terminal_reason(mixed), "SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT")
        self.assertEqual(tuple(t.rejection_reason for t in mixed), before)


class TextConstructorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work, cls.bundles = _text_fixture()
        cls.envelope = SyntheticMaterializationTests.envelope(max_payload_bytes=_TEXT_CAP)
        cls.prior = execution.encode_bundle_v2(cls.bundles[execution.WorkerKind.PRIMARY],
                                                _TEXT_PROFILE, max_payload_bytes=_TEXT_CAP)
        cls.views, cls.targets, cls.results = {}, {}, {}
        for family, _, _, kind in _TEXT_FAMILIES:
            bundle = cls.bundles[kind]
            wire = execution.encode_bundle_v2(bundle, _TEXT_PROFILE, max_payload_bytes=_TEXT_CAP)
            view = execution.decode_bundle_view_v2(wire, _TEXT_PROFILE, max_payload_bytes=_TEXT_CAP)
            p, logical = _text_family_metrics(view, family)
            targets = max(1, p - 128), logical + 17
            cls.views[family], cls.targets[family] = view, targets
            cls.results[family] = h.construct_text_family_v2(cls.work, bundle, family, _TEXT_PROFILE,
                physical_target=targets[0], logical_target=targets[1], max_payload_bytes=_TEXT_CAP,
                envelope=cls.envelope,
                prior_primary_wire=None if kind is execution.WorkerKind.PRIMARY else cls.prior)

    def construct(self, family, **changes):
        kind = next(kind for name, _, _, kind in _TEXT_FAMILIES if name == family)
        arguments = dict(physical_target=self.targets[family][0], logical_target=self.targets[family][1],
            max_payload_bytes=_TEXT_CAP, envelope=self.envelope,
            prior_primary_wire=None if kind is execution.WorkerKind.PRIMARY else self.prior)
        arguments.update(changes)
        return h.construct_text_family_v2(self.work, self.bundles[kind], family, _TEXT_PROFILE, **arguments)

    def test_five_real_family_results_are_immutable_canonical_and_fresh_validated(self):
        for family, _, _, kind in _TEXT_FAMILIES:
            with self.subTest(family=family):
                baseline, result = self.bundles[kind], self.results[family]
                self.assertEqual(execution.revalidate_bundle(baseline, self.work, kind,
                                                            max_payload_bytes=_TEXT_CAP), baseline)
                self.assertIsNone(result.rejection_reason)
                self.assertFalse(result.zero_oracle)
                self.assertIs(type(result.trials), tuple)
                self.assertGreater(len(result.trials), 1)
                self.assertLessEqual(len(result.trials), 8)
                self.assertIs(type(result.selected_wire), bytes)
                for value in (result, result.selected_trial):
                    self.assertFalse(hasattr(value, "__dict__"))
                    with self.assertRaises(FrozenInstanceError):
                        setattr(value, fields(value)[0].name, None)
                selected = result.selected_bundle
                self.assertEqual(execution.revalidate_bundle(selected, self.work, kind,
                                                             max_payload_bytes=_TEXT_CAP), selected)
                for _, values in selected.streams:
                    for data in values:
                        self.assertEqual(records.encode(records.decode(data)), data)
                fresh = operational._fresh_wb02_context(result.selected_wire, self.work, kind,
                    _TEXT_PROFILE, self.envelope,
                    prior_primary_wire=None if kind is execution.WorkerKind.PRIMARY else self.prior)
                self.assertEqual(fresh.bundle, selected)
                self.assertEqual(result.selected_wire, execution.encode_bundle_v2(selected, _TEXT_PROFILE,
                                                                                  max_payload_bytes=_TEXT_CAP))

    def test_only_authorized_text_fields_and_oracle_snapshot_digests_change(self):
        for family, _, _, kind in _TEXT_FAMILIES:
            with self.subTest(family=family):
                result, baseline = self.results[family], self.bundles[kind]
                chosen = result.selected_trial
                text = h._text_filler(family, self.work.position, chosen.ell, chosen.h)
                expected = _text_with_literal(baseline, family, text)
                self.assertEqual(result.selected_bundle, expected)
                before, after = dict(baseline.streams), dict(result.selected_bundle.streams)
                changed = [(name, index) for name, values in before.items()
                           for index, data in enumerate(values) if data != after[name][index]]
                name = {"primary": "evaluators", "k_control": "kcontrol_maintenance",
                        "oracle_primary": "oracle_b_audits", "oracle_repeat": "repeat_oracle_b_audits",
                        "determinism": "repeat_evaluators"}[family]
                expected_indices = [0, 1] if family.startswith("oracle_") else [1] if family == "k_control" else [0]
                self.assertEqual(changed, [(name, index) for index in expected_indices])
                if family.startswith("oracle_"):
                    self.assertEqual(before[name.replace("audits", "coverage")],
                                     after[name.replace("audits", "coverage")])
                    for data in after[name]:
                        item = records.decode(data)
                        self.assertEqual(item.expected, item.actual)
                        self.assertIs(item.status, records.AuditStatus.PASS)
                        self.assertEqual(item.expected.shared_kernel_evidence, text)
                        self.assertEqual(item.expected_digest, records.oracle_b_snapshot_digest(item.expected))
                        self.assertEqual(item.actual_digest, records.oracle_b_snapshot_digest(item.actual))

    def test_exact_family_and_complete_unit_metrics_match_selected_wire(self):
        for family, _, _, kind in _TEXT_FAMILIES:
            with self.subTest(family=family):
                result = self.results[family]
                view = execution.decode_bundle_view_v2(result.selected_wire, _TEXT_PROFILE,
                                                        max_payload_bytes=_TEXT_CAP)
                p, logical = _text_family_metrics(view, family)
                trial = result.selected_trial
                self.assertEqual((trial.actual_physical_bytes, trial.actual_logical_bytes), (p, logical))
                self.assertEqual((trial.lsum, trial.llegacy, trial.sunit, trial.wnew),
                    (sum(len(data) for _, values in view.bundle.streams for data in values),
                     len(execution.encode_bundle(view.bundle)), sum(len(row.frame_bytes) for row in view.rows),
                     len(result.selected_wire)))
                self.assertTrue(all(value <= _TEXT_CAP for value in
                                    (trial.lsum, trial.llegacy, trial.sunit, trial.wnew)))
                policy = readiness.evaluate_family_size(family, *self.targets[family], p, logical)
                self.assertEqual((trial.eligible, trial.rejection_reason, trial.physical_margin, trial.logical_margin),
                                 (policy.eligible, policy.rejection_reason, policy.physical_margin, policy.logical_margin))
                self.assertEqual(result.selected_trial, min((t for t in result.trials if t.eligible),
                    key=lambda t: (t.actual_physical_bytes, t.actual_logical_bytes, t.h)))
                self.assertEqual(trial.lsum, view.logical_bytes)
                self.assertEqual(trial.llegacy, view.legacy_bytes)
                self.assertEqual(trial.sunit, view.frame_bytes)
                self.assertEqual(trial.wnew, view.wire_bytes)
                if kind is not execution.WorkerKind.PRIMARY:
                    copied = tuple(row for row in view.rows if "control_maintenance" in row.stream_name)
                    self.assertTrue(copied)
                    self.assertTrue(all(_text_owned(row.stream_name, kind, family)
                                        for row in copied) if not family.startswith("oracle_") else
                                    all(not _text_owned(row.stream_name, kind, family) for row in copied))

    def test_actual_canonical_logical_construction_matches_multiplicity_for_every_trial(self):
        for family, _, _, kind in _TEXT_FAMILIES:
            result = self.results[family]
            fixed = _text_with_literal(self.bundles[kind], family, "SYNTHETIC_NON_EVIDENCE|L:|H:")
            l0 = _text_logical_bytes(fixed, family)
            multiplicity = 4 if family.startswith("oracle_") else 1
            target = self.targets[family][1]
            q = (max(0, target - l0) + multiplicity - 1) // multiplicity
            for trial in result.trials:
                with self.subTest(family=family, knob=trial.h):
                    encoded_entropy = 4 * ((trial.h + 2) // 3)
                    self.assertEqual(trial.ell, max(0, q - encoded_entropy))
                    actual_bundle = _text_with_literal(self.bundles[kind], family,
                        h._text_filler(family, self.work.position, trial.ell, trial.h))
                    measured = _text_logical_bytes(actual_bundle, family)
                    self.assertEqual(measured, l0 + multiplicity * max(q, encoded_entropy))
                    if trial.actual_logical_bytes is not None:
                        self.assertEqual(trial.actual_logical_bytes, measured)

    def test_canonical_low_exact_and_nondivisible_logical_targets(self):
        for family in ("primary", "oracle_primary"):
            fixed = _text_with_literal(self.bundles[execution.WorkerKind.PRIMARY], family,
                                       "SYNTHETIC_NON_EVIDENCE|L:|H:")
            l0 = _text_logical_bytes(fixed, family)
            m = 4 if family.startswith("oracle_") else 1
            for deficit in (-1, 0, 7, 33):
                with self.subTest(family=family, deficit=deficit):
                    result = self.construct(family, logical_target=l0 + deficit)
                    low = result.trials[0]
                    q = (max(0, deficit) + m - 1) // m
                    self.assertEqual((low.h, low.ell, low.actual_logical_bytes), (0, q, l0 + m * q))
                    self.assertGreaterEqual(low.actual_logical_bytes, l0 + deficit)

    def test_exact_high_endpoint_is_maximum_expanded_domain_not_a_compressed_search(self):
        for family, _, _, kind in _TEXT_FAMILIES:
            result = self.results[family]
            fixed = _text_with_literal(self.bundles[kind], family, "SYNTHETIC_NON_EVIDENCE|L:|H:")
            m = 4 if family.startswith("oracle_") else 1
            baseline_lsum = sum(len(data) for _, values in fixed.streams for data in values)
            baseline_legacy = len(execution.encode_bundle(fixed))
            stream = {"primary": "evaluators", "k_control": "kcontrol_maintenance",
                      "oracle_primary": "oracle_b_audits", "oracle_repeat": "repeat_oracle_b_audits",
                      "determinism": "repeat_evaluators"}[family]
            indices = (0, 1) if m == 4 else (-1,) if family == "k_control" else (0,)
            per_record = 2 if m == 4 else 1
            limits = [(_TEXT_CAP - baseline_lsum) // m, (_TEXT_CAP - baseline_legacy) // m]
            limits.extend((_TEXT_CAP - len(dict(fixed.streams)[stream][index])) // per_record
                          for index in indices)
            expected_high = 3 * (min(limits) // 4)
            with self.subTest(family=family):
                self.assertEqual(result.trials[1].h, expected_high)
                high = _text_with_literal(fixed, family,
                    h._text_filler(family, self.work.position, 0, expected_high))
                self.assertLessEqual(sum(len(data) for _, values in high.streams for data in values), _TEXT_CAP)
                self.assertLessEqual(len(execution.encode_bundle(high)), _TEXT_CAP)
                too_high = _text_with_literal(fixed, family,
                    h._text_filler(family, self.work.position, 0, expected_high + 1))
                sizes = [sum(len(data) for _, values in too_high.streams for data in values),
                         len(execution.encode_bundle(too_high))]
                sizes.extend(len(data) for _, values in too_high.streams for data in values)
                self.assertGreater(max(sizes), _TEXT_CAP)

    def test_actual_canonical_bytes_before_at_and_after_entropy_overtakes_q(self):
        for family, multiplicity in (("primary", 1), ("oracle_primary", 4)):
            baseline = self.bundles[execution.WorkerKind.PRIMARY]
            fixed = _text_with_literal(baseline, family, "SYNTHETIC_NON_EVIDENCE|L:|H:")
            l0 = _text_logical_bytes(fixed, family)
            target = l0 + (8 if multiplicity == 1 else 29)
            for knob, b, ell in ((3, 4, 4), (6, 8, 0), (7, 12, 0)):
                with self.subTest(family=family, knob=knob):
                    self.assertEqual(h._text_lengths(target, l0, multiplicity, knob), (8, b, ell))
                    text = h._text_filler(family, self.work.position, ell, knob)
                    candidate = h._mutate_text_bundle(baseline, family, text)
                    self.assertEqual(candidate, _text_with_literal(baseline, family, text))
                    self.assertEqual(_text_logical_bytes(candidate, family), l0 + multiplicity * max(8, b))
                    self.assertGreaterEqual(_text_logical_bytes(candidate, family), target)
                    execution.revalidate_bundle(candidate, self.work, candidate.kind, max_payload_bytes=_TEXT_CAP)

    def test_only_changed_rows_are_encoded_per_trial_and_unchanged_frames_are_reused(self):
        original_search, original_encode = h._search_text_trials, physical.encode_frame
        for family, _, _, _ in _TEXT_FAMILIES:
            evaluations, encoded = [], []
            def encode(*args, **kwargs):
                encoded.append((args[1], args[2].stream_name))
                return original_encode(*args, **kwargs)
            def search(upper, target, evaluate, *, _check=None):
                def observed(knob, ordinal):
                    start = len(encoded)
                    trial = evaluate(knob, ordinal)
                    evaluations.append(tuple(encoded[start:]))
                    return trial
                return original_search(upper, target, observed, _check=_check)
            with self.subTest(family=family), patch.object(physical, "encode_frame", side_effect=encode), \
                 patch.object(h, "_search_text_trials", side_effect=search), \
                 patch.object(execution, "encode_bundle_v2", wraps=execution.encode_bundle_v2) as full:
                result = self.construct(family)
                self.assertLessEqual(full.call_count, 1)
            limit = 2 if family.startswith("oracle_") else 1
            self.assertEqual(len(evaluations), len(result.trials))
            self.assertTrue(all(len(calls) <= limit for calls in evaluations))
            self.assertTrue(any(len(calls) == limit for calls in evaluations))
            final = execution.decode_bundle_view_v2(result.selected_wire, _TEXT_PROFILE,
                                                     max_payload_bytes=_TEXT_CAP)
            old = {(row.stream_name, row.key): row for row in self.views[family].rows}
            reused = 0
            for row in final.rows:
                baseline = old[row.stream_name, row.key]
                if baseline.logical_bytes == row.logical_bytes:
                    reused += 1
                    self.assertEqual(baseline.frame_bytes, row.frame_bytes)
            self.assertEqual(reused, len(final.rows) - limit)

    def test_readiness_is_called_with_actual_observations_and_selected_wire_is_fresh_checked(self):
        with patch.object(readiness, "evaluate_family_size", wraps=readiness.evaluate_family_size) as policy, \
             patch.object(operational, "_fresh_wb02_context", wraps=operational._fresh_wb02_context) as fresh:
            result = self.construct("primary")
        for trial in result.trials:
            if trial.rejection_reason is None or "SHORTFALL" in trial.rejection_reason or "OVERSHOOT" in trial.rejection_reason:
                self.assertTrue(any(call.args == ("primary", *self.targets["primary"],
                    trial.actual_physical_bytes, trial.actual_logical_bytes) for call in policy.call_args_list))
        self.assertTrue(any(call.args[0] == result.selected_wire for call in fresh.call_args_list))

    def test_empty_logical_domain_is_not_a_partial_success_or_extra_search(self):
        with patch.object(h, "_search_text_trials", side_effect=AssertionError("No admissible domain search")):
            result = self.construct("primary", logical_target=_TEXT_CAP)
        self.assertEqual(result.rejection_reason, "SYNTHETIC_LOGICAL_DOMAIN_EMPTY")
        self.assertEqual(result.trials, ())
        self.assertIsNone(result.selected_trial)
        self.assertIsNone(result.selected_bundle)
        self.assertIsNone(result.selected_wire)

    def test_rejects_wrong_family_kind_profile_nonboard_position_and_mutable_prior(self):
        baseline = self.bundles[execution.WorkerKind.PRIMARY]
        common = dict(physical_target=100, logical_target=100, max_payload_bytes=_TEXT_CAP,
                      envelope=self.envelope)
        for family in ("reference", "k_control", "determinism", "oracle_repeat", "PRIMARY"):
            with self.subTest(family=family), self.assertRaises(ValueError):
                h.construct_text_family_v2(self.work, baseline, family, _TEXT_PROFILE, **common)
        for profile in (b"x" * 31, bytearray(_TEXT_PROFILE), "x" * 32):
            with self.subTest(profile=type(profile)), self.assertRaises(ValueError):
                h.construct_text_family_v2(self.work, baseline, "primary", profile, **common)
        for work in (replace(self.work, position=10000),
                     replace(self.work, board=replace(self.work.board, fingerprint="pretend-real-board"))):
            with self.subTest(work=work), self.assertRaises(ValueError):
                h.construct_text_family_v2(work, baseline, "primary", _TEXT_PROFILE, **common)
        with self.assertRaises(ValueError):
            self.construct("primary", prior_primary_wire=self.prior)
        for family in ("determinism", "oracle_repeat", "k_control"):
            for prior in (None, bytearray(self.prior), self.prior[:-1], b"bad prior"):
                with self.subTest(family=family, prior=type(prior)), self.assertRaises(ValueError):
                    self.construct(family, prior_primary_wire=prior)

    def test_canonical_but_different_primary_premise_cannot_bind(self):
        primary = self.bundles[execution.WorkerKind.PRIMARY]
        values = dict(primary.streams)
        items = list(values["control_maintenance"])
        item = records.decode(items[-1])
        decision = replace(item.v1_decision, constraints=item.v1_decision.constraints * 2)
        items[-1] = records.encode(replace(item, v1_decision=decision))
        values["control_maintenance"] = tuple(items)
        other = replace(primary, streams=tuple((name, values[name]) for name, _ in primary.streams))
        execution.revalidate_bundle(other, self.work, execution.WorkerKind.PRIMARY, max_payload_bytes=_TEXT_CAP)
        wrong_prior = execution.encode_bundle_v2(other, _TEXT_PROFILE, max_payload_bytes=_TEXT_CAP)
        for family in ("determinism", "oracle_repeat", "k_control"):
            with self.subTest(family=family), self.assertRaises(ValueError):
                self.construct(family, prior_primary_wire=wrong_prior)

    def test_constructor_cancellation_and_resource_errors_propagate(self):
        def cancel():
            raise RuntimeError("constructor cancelled")
        with self.assertRaisesRegex(RuntimeError, "constructor cancelled"):
            self.construct("primary", _check=cancel)
        with patch.object(h, "_text_filler", side_effect=MemoryError("constructor resource")), \
             self.assertRaisesRegex(MemoryError, "constructor resource"):
            self.construct("primary")

    def test_trial_semantic_canonical_frame_and_wire_failures_are_static_and_bounded(self):
        original = h._search_text_trials
        cases = ((h, "_mutate_text_bundle", records.RecordError("private malformed detail"),
                  "SYNTHETIC_TEXT_CANONICAL_RECORD_FAILURE"),
                 (execution, "revalidate_bundle", execution.E2ExecutionError("private semantic detail"),
                  "SYNTHETIC_TEXT_SEMANTIC_OR_PRIOR_FAILURE"),
                 (operational, "_bind_prior_bundle", operational.OperationalError("private copied premise"),
                  "SYNTHETIC_TEXT_SEMANTIC_OR_PRIOR_FAILURE"),
                 (physical, "encode_frame", physical.PhysicalError("private frame detail"),
                  "SYNTHETIC_TEXT_FRAME_FAILURE"),
                 (execution, "_compose_bundle_v2_from_rows", execution.E2ExecutionError("private wire cap"),
                  "SYNTHETIC_TEXT_WIRE_FAILURE"))
        for owner, name, error, expected in cases:
            def search(upper, target, evaluate, *, _check=None):
                with patch.object(owner, name, side_effect=error):
                    return original(upper, target, evaluate, _check=_check)
            with self.subTest(stage=name), patch.object(h, "_search_text_trials", side_effect=search):
                result = self.construct("primary")
            self.assertEqual(result.rejection_reason, "SYNTHETIC_SIZING_SEARCH_EXHAUSTED")
            self.assertEqual(len(result.trials), 8)
            self.assertEqual({trial.rejection_reason for trial in result.trials}, {expected})
            self.assertTrue(all(not trial.eligible for trial in result.trials))
            self.assertIsNone(result.selected_wire)

    def test_physical_unit_cap_is_independent_of_the_logical_floor(self):
        original = h._search_text_trials
        def search(upper, target, evaluate, *, _check=None):
            with patch.object(physical, "encode_frame", return_value=b"x" * _TEXT_CAP):
                return original(upper, target, evaluate, _check=_check)
        with patch.object(h, "_search_text_trials", side_effect=search):
            result = self.construct("primary")
        self.assertEqual(len(result.trials), 8)
        self.assertEqual({t.rejection_reason for t in result.trials}, {"SYNTHETIC_TEXT_SUNIT_CAP"})
        self.assertTrue(all(t.actual_logical_bytes >= self.targets["primary"][1] for t in result.trials))
        self.assertTrue(all(t.sunit > _TEXT_CAP and not t.eligible for t in result.trials))
        self.assertTrue(all(t.wnew > t.sunit + 48 for t in result.trials))

    def test_logical_record_sum_legacy_and_wire_caps_fail_independently(self):
        original_search, original_mutate = h._search_text_trials, h._mutate_text_bundle
        baseline = self.bundles[execution.WorkerKind.PRIMARY]
        fixed = _text_with_literal(baseline, "primary", "SYNTHETIC_NON_EVIDENCE|L:|H:")
        base_sum = sum(len(data) for _, values in fixed.streams for data in values)
        base_legacy = len(execution.encode_bundle(fixed))
        cases = ((_TEXT_CAP, "SYNTHETIC_TEXT_LOGICAL_RECORD_CAP"),
                 (_TEXT_CAP - base_sum + 1, "SYNTHETIC_TEXT_LSUM_CAP"),
                 (_TEXT_CAP - base_legacy + 1, "SYNTHETIC_TEXT_LLEGACY_CAP"))
        for ell, expected in cases:
            def mutation(bundle, family, _text):
                return original_mutate(bundle, family, "SYNTHETIC_NON_EVIDENCE|L:" + "x" * ell + "|H:")
            def search(upper, target, evaluate, *, _check=None):
                with patch.object(h, "_mutate_text_bundle", side_effect=mutation):
                    return original_search(upper, target, evaluate, _check=_check)
            with self.subTest(cap=expected), patch.object(h, "_search_text_trials", side_effect=search):
                result = self.construct("primary")
            self.assertEqual({t.rejection_reason for t in result.trials}, {expected})
            self.assertTrue(all(not t.eligible for t in result.trials))
            if expected == "SYNTHETIC_TEXT_LLEGACY_CAP":
                self.assertTrue(all(t.lsum <= _TEXT_CAP < t.llegacy for t in result.trials))
        view = self.views["primary"]
        old = next(row for row in view.rows if row.stream_name == "evaluators" and row.key[2] == 0)
        unchanged_size = view.frame_bytes - old.frame_length
        frame_length = _TEXT_CAP - unchanged_size - 1
        def search(upper, target, evaluate, *, _check=None):
            with patch.object(physical, "encode_frame", return_value=b"x" * frame_length):
                return original_search(upper, target, evaluate, _check=_check)
        with patch.object(h, "_search_text_trials", side_effect=search):
            result = self.construct("primary")
        self.assertEqual({t.rejection_reason for t in result.trials}, {"SYNTHETIC_TEXT_WNEW_CAP"})
        self.assertTrue(all(t.sunit < _TEXT_CAP < t.wnew for t in result.trials))
        self.assertTrue(all(t.lsum <= _TEXT_CAP and t.llegacy <= _TEXT_CAP for t in result.trials))

    def test_value_error_callback_inside_candidate_is_fatal_not_a_trial_rejection(self):
        original = h._search_text_trials
        def search(upper, target, evaluate, *, _check=None):
            def stop():
                raise h.HarnessError("private fatal check")
            # The constructor's callback is closed over by evaluate; replace
            # only the filler call boundary to make this a during-trial error.
            with patch.object(h, "_text_filler", side_effect=lambda *_args, **_kwargs: stop()):
                return original(upper, target, evaluate, _check=_check)
        with patch.object(h, "_search_text_trials", side_effect=search), \
             self.assertRaisesRegex(h.HarnessError, "private fatal check"):
            self.construct("primary")


class ZeroOracleTextConstructorTests(unittest.TestCase):
    def test_both_zero_oracles_keep_selected_coverage_without_entropy_mutation_or_search(self):
        work, bundles = _text_fixture(oracle=0)
        envelope = SyntheticMaterializationTests.envelope(max_payload_bytes=_TEXT_CAP)
        prior = execution.encode_bundle_v2(bundles[execution.WorkerKind.PRIMARY], _TEXT_PROFILE,
                                            max_payload_bytes=_TEXT_CAP)
        for family, kind, stream in (("oracle_primary", execution.WorkerKind.PRIMARY, "oracle_b_audits"),
                                     ("oracle_repeat", execution.WorkerKind.DETERMINISM, "repeat_oracle_b_audits")):
            bundle = bundles[kind]
            encoded_names = []
            original = physical.encode_frame
            def encode(data, key, context, **kwargs):
                encoded_names.append(context.stream_name)
                return original(data, key, context, **kwargs)
            with self.subTest(family=family), \
                 patch.object(h, "_text_entropy", side_effect=AssertionError("No entropy")), \
                 patch.object(h, "_text_filler", side_effect=AssertionError("No filler")), \
                 patch.object(h, "_mutate_text_bundle", side_effect=AssertionError("No mutation")), \
                 patch.object(h, "_search_text_trials", side_effect=AssertionError("No search")), \
                 patch.object(physical, "encode_frame", side_effect=encode):
                result = h.construct_text_family_v2(work, bundle, family, _TEXT_PROFILE,
                    physical_target=0, logical_target=0, max_payload_bytes=_TEXT_CAP, envelope=envelope,
                    prior_primary_wire=None if kind is execution.WorkerKind.PRIMARY else prior)
            self.assertTrue(result.zero_oracle)
            self.assertIsNone(result.rejection_reason)
            self.assertEqual(result.trials, ())
            self.assertEqual(result.selected_bundle, bundle)
            self.assertEqual((result.selected_trial.actual_physical_bytes,
                              result.selected_trial.actual_logical_bytes), (0, 0))
            self.assertNotIn(stream, encoded_names)
            self.assertEqual(len(encoded_names), sum(len(rows) for _, rows in bundle.streams))
            self.assertEqual(dict(result.selected_bundle.streams)[stream], ())
            view = execution.decode_bundle_view_v2(result.selected_wire, _TEXT_PROFILE,
                                                    max_payload_bytes=_TEXT_CAP)
            self.assertEqual(_text_family_metrics(view, family), (0, 0))
            coverage_name = stream.replace("audits", "coverage")
            coverage = next(row for row in view.rows if row.stream_name == coverage_name)
            self.assertEqual(coverage.frame_bytes[0], physical.RAW)
            value = records.decode(coverage.logical_bytes)
            self.assertTrue(value.selected)
            self.assertEqual(value.applicable, ())
            owner = "primary" if kind is execution.WorkerKind.PRIMARY else "determinism"
            self.assertTrue(_text_owned(coverage_name, kind, owner))
            self.assertFalse(_text_owned(coverage_name, kind, family))

    def test_zero_inconsistent_targets_and_nonzero_audits_fail_closed(self):
        work, nonzero = _text_fixture(oracle=1)
        _, zero = _text_fixture(oracle=0)
        envelope = SyntheticMaterializationTests.envelope(max_payload_bytes=_TEXT_CAP)
        for p, logical, bundles in ((0, 1, zero), (1, 0, zero), (0, 0, nonzero), (1, 1, zero)):
            for family, kind in (("oracle_primary", execution.WorkerKind.PRIMARY),
                                 ("oracle_repeat", execution.WorkerKind.DETERMINISM)):
                prior = None if kind is execution.WorkerKind.PRIMARY else execution.encode_bundle_v2(
                    bundles[execution.WorkerKind.PRIMARY], _TEXT_PROFILE, max_payload_bytes=_TEXT_CAP)
                with self.subTest(p=p, logical=logical, family=family), self.assertRaises(ValueError):
                    h.construct_text_family_v2(work, bundles[kind], family, _TEXT_PROFILE,
                        physical_target=p, logical_target=logical, max_payload_bytes=_TEXT_CAP,
                        envelope=envelope, prior_primary_wire=prior)


class TextConstructorV1PreservationTests(unittest.TestCase):
    def test_v1_signatures_and_prechange_canonical_byte_goldens_remain_exact(self):
        signature = inspect.signature(h.build_synthetic_bundle)
        self.assertEqual(tuple(signature.parameters), ("work", "kind", "sizes", "primary", "max_payload_bytes"))
        self.assertIsNone(signature.parameters["primary"].default)
        self.assertIs(signature.parameters["max_payload_bytes"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(tuple(inspect.signature(h.synthetic_bundle_family_bytes).parameters), ("bundle",))
        self.assertEqual(tuple(inspect.signature(h.materialize_synthetic).parameters),
            ("plan", "sizes", "envelope", "streams_root", "identity_seal", "progress"))
        # Captured from accepted baseline 172f7aea before Slice 1F edits, with
        # the fixed literal runtime in _text_fixture (no host/time dependence).
        expected = {
            execution.WorkerKind.PRIMARY: (17792,
                "d92d0d63988d3b2f5071487efac9282fe3fdb12b195395b355184e19c9c1b116",
                (("primary", 9070), ("reference", 3049), ("oracle_primary", 2566))),
            execution.WorkerKind.DETERMINISM: (28788,
                "106f80776cc62443a6254760ea12325318a2b32de14948f29c7f06434106d6b8",
                (("determinism", 21028), ("oracle_repeat", 2566))),
            execution.WorkerKind.K_CONTROL: (9655,
                "3f11417a265dc092c7b6e153defa155363c11a53f0d9485a4ab64b99f6b7de37",
                (("k_control", 8151),)),
        }
        with patch.object(h, "construct_text_family_v2", side_effect=AssertionError("No V2 historical path")), \
             patch.object(execution, "encode_bundle_v2", side_effect=AssertionError("V1 bytes only")):
            _, bundles = _text_fixture()
            for kind, bundle in bundles.items():
                with self.subTest(kind=kind):
                    wire = execution.encode_bundle(bundle)
                    self.assertEqual((len(wire), sha256(wire).hexdigest(), h.synthetic_bundle_family_bytes(bundle)),
                                     expected[kind])

    def test_historical_materialization_still_writes_only_jsonl_and_never_calls_v2(self):
        fixture = SyntheticMaterializationTests()
        plan = fixture.plan()
        with tempfile.TemporaryDirectory() as directory:
            seal = fixture._identity(directory, plan)
            with patch.object(h, "construct_text_family_v2", side_effect=AssertionError("No V2 constructor")), \
                 patch.object(execution, "encode_bundle_v2", side_effect=AssertionError("No WB02 materialization")), \
                 patch.object(operational.harness, "_coordinator_private_bytes", return_value=100):
                result = h.materialize_synthetic(plan, readiness.ComponentSizes(1, 1, 1, 1, 1, 1),
                                                  fixture.envelope(), directory, seal)
            self.assertTrue(result.readback_complete and result.cleanup_complete)
            paths = tuple(Path(directory).iterdir())
            self.assertTrue(paths)
            self.assertTrue(all(path.suffix == ".jsonl" for path in paths))
            self.assertFalse(any(path.suffix == ".pkf" for path in paths))

    def test_new_trial_and_result_facts_are_excluded_from_historical_fact_registry(self):
        from experiments import program_k_e2_r0_evidence as evidence
        for cls in (h.TextTrial, h.TextConstructionResult):
            self.assertNotIn(cls, evidence._FACT_TYPES.values())
            self.assertNotIn(cls.__name__, evidence._FACT_TYPES)
            with self.assertRaisesRegex(h.HarnessError, "UNSUPPORTED_METADATA_FACT"):
                h._fact_read({"fact": cls.__name__, "fields": {}})


# Slice 1G fixtures are detached, deliberately counterfactual public traces.
# Every q used here is bounded; these tests make no performance/readiness claim.
from stage3_physical import action_cost as _reference_action_cost, load_timing_table as _reference_timing_table

_REFERENCE_PROFILE = b"\x71" * 32
_REFERENCE_CAP = 1048576
_REFERENCE_TAG = "SYNTHETIC_NON_EVIDENCE|L:|H:"
_REFERENCE_TARGET = (1, 0)
_REFERENCE_SOURCES = tuple((x, y) for y in range(16) for x in range(30)
                           if (x, y) != _REFERENCE_TARGET)
_REFERENCE_NEIGHBORS = ((0, 0), (2, 0), (0, 1), (1, 1), (2, 1))


def _reference_work(*, k=True, d=True, oracle=True):
    runtime = records.RuntimeIdentity("FixturePython", "0", "fixture-os",
                                      "fixture-platform", "fixture-arch", None)
    return execution.BoardWork(7, h.reference_board_identity(2_000_000_070_000),
        bytes.fromhex(identity.PROTOCOL_SHA256), "slice1g-bounded-fixture",
        oracle, d, k, runtime)


def _reference_fixture(q=0, **selection):
    work = _reference_work(**selection)
    bundles = h._reference_bundles(work, h._reference_prefix(q), q)
    return work, {bundle.kind: bundle for bundle in bundles}


def _reference_values(bundle, name):
    return tuple(records.decode(data) for data in dict(bundle.streams)[name])


def _reference_targets(work, *, logical_reference=1, physical_reference=1):
    oracle = int(work.oracle_b_selected)
    return readiness.DualComponentSizes(
        readiness.ComponentSizes(1, 1, oracle, oracle, 1, physical_reference),
        readiness.ComponentSizes(1, 1, oracle, oracle, 1, logical_reference))


def _reference_trial(ordinal, q, p=100, logical=100, *, target=100, logical_target=100):
    policy = readiness.evaluate_family_size("reference", target, logical_target, p, logical)
    units = (h.ReferenceUnitMetrics(execution.WorkerKind.PRIMARY,
        logical + 11, logical + 21, p + 11, p + 51, 0, 0),)
    return h.ReferenceTrial(ordinal, q, p, logical, p - target, logical - logical_target,
                             units, policy.eligible, policy.rejection_reason)


class ReferenceTraceCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work, cls.bundles = _reference_fixture(19)
        cls.primary = cls.bundles[execution.WorkerKind.PRIMARY]

    def test_exact_separate_synthetic_identity_and_two_model_c_inputs(self):
        board = self.work.board
        self.assertEqual((board.width, board.height, board.mines, board.first_click), (30, 16, 0, (0, 0)))
        self.assertNotEqual(board, h.synthetic_board_identity(board.game_index))
        self.assertIn("SYNTHETIC", board.fingerprint)
        projection = execution.restore_projection(self.primary, "control")
        inputs = projection.physical_inputs
        self.assertEqual(tuple((v.action_ordinal, v.action, v.target, v.cursor_before) for v in inputs),
            ((0, records.Action.OPEN, (0, 0), (0, 0)), (1, records.Action.OPEN, (1, 0), (0, 0))))
        table = _reference_timing_table()
        first, second = _reference_action_cost(table, (0, 0), (0, 0)), _reference_action_cost(table, (0, 0), (1, 0))
        self.assertEqual(tuple((v.input_us, v.cumulative_us) for v in inputs),
                         ((first, first), (second, first + second)))

    def test_build_is_detached_from_board_engine_solver_and_text_search(self):
        with patch("benchmark_board.generate_board", side_effect=AssertionError("No generated board")), \
             patch.object(execution, "_fresh_engine", side_effect=AssertionError("No engine")), \
             patch.object(execution, "_materialize_board", side_effect=AssertionError("No materialization")), \
             patch.object(h, "construct_text_family_v2", side_effect=AssertionError("No text search")):
            work, bundles = _reference_fixture(3)
        self.assertEqual(work.board.width, 30)
        self.assertEqual(set(bundles), set(execution.WorkerKind))

    def test_ordinal_zero_reveals_all_other_cells_once_in_reading_order(self):
        for role in ("control", "kp0"):
            first, second = execution.restore_projection(self.primary, role).public_effects
            self.assertEqual(tuple(v.cell for v in first.changes), _REFERENCE_SOURCES)
            self.assertEqual(len(first.changes), 479)
            self.assertTrue(all((v.before, v.after) == ("HIDDEN", "CLUE_0") for v in first.changes))
            self.assertEqual((first.before_status, first.after_status),
                             (records.Status.PLAYING, records.Status.PLAYING))
            self.assertEqual(second.changes, (records.PublicCellChange((1, 0), "HIDDEN", "CLUE_0"),))
            self.assertEqual((second.before_status, second.after_status),
                             (records.Status.PLAYING, records.Status.WON))

    def test_complete_catalog_has_exact_five_neighbors_and_474_true_empty_constraints(self):
        catalog = h._reference_catalog()
        self.assertEqual(tuple(v[0] for v in catalog), _REFERENCE_SOURCES)
        self.assertEqual(len(set(v[0] for v in catalog)), 479)
        self.assertTrue(all(v[1] == 0 for v in catalog))
        self.assertEqual(tuple(v[0] for v in catalog if v[2]), _REFERENCE_NEIGHBORS)
        self.assertTrue(all(v[2] == ((1, 0),) for v in catalog if v[2]))
        self.assertEqual(sum(v[2] == () for v in catalog), 474)

    def test_complete_catalog_precedes_each_redundancy_prefix_and_v1_fields_are_exact(self):
        for q in (0, 1, 19, 67):
            prefix = h._reference_prefix(q)
            constraints = h._reference_constraints(prefix, q)
            self.assertEqual(constraints[:479], h._reference_catalog())
            self.assertEqual(constraints[479:], tuple(h._reference_catalog()[prefix.index(i)] for i in range(q)))
            self.assertEqual(len(constraints), 479 + q)
        row = _reference_values(self.primary, "control_maintenance")[1]
        decision = row.v1_decision
        self.assertEqual((decision.action, decision.target, decision.evidence_kind,
                          decision.evidence_action, decision.evidence_target),
                         (records.Action.OPEN, (1, 0), "LOCAL_DETERMINISTIC", records.Action.OPEN, (1, 0)))
        self.assertEqual((decision.safe_cells, decision.mine_cells, decision.probability_total_worlds,
            decision.probabilities, decision.frontier_cells, decision.unconstrained_cells,
            decision.plan_actions, decision.plan_model_us, decision.plan_safe_reveals),
            (((1, 0),), (), None, (), (), (), (), None, None))

    def test_initial_and_ordinal_one_observations_match_public_reconstruction(self):
        initial = tuple(tuple(-2 for _ in range(30)) for _ in range(16))
        later = tuple(tuple(-2 if (x, y) == (1, 0) else 0 for x in range(30)) for y in range(16))
        self.assertEqual(h._reference_observation(initial=True), initial)
        self.assertEqual(h._reference_observation(), later)
        self.assertEqual(tuple(v.observation for v in _reference_values(self.primary, "control_maintenance")),
                         (initial, later))

    def test_fixed_text_surfaces_start_with_exact_empty_fill_tag(self):
        self.assertEqual(_reference_values(self.primary, "evaluators")[0].detail, _REFERENCE_TAG)
        repeated = self.bundles[execution.WorkerKind.DETERMINISM]
        self.assertEqual(_reference_values(repeated, "repeat_evaluators")[0].detail, _REFERENCE_TAG)
        actual = _reference_values(self.bundles[execution.WorkerKind.K_CONTROL], "kcontrol_maintenance")[-1]
        self.assertEqual(dict(actual.soundness)["detail"], _REFERENCE_TAG)
        self.assertTrue(all(v.expected.shared_kernel_evidence == _REFERENCE_TAG
                            for v in _reference_values(self.primary, "oracle_b_audits")))


class ReferencePackedPrefixTests(unittest.TestCase):
    @staticmethod
    def independent_indices(q):
        result = []
        for block in range((q + 15) // 16):
            digest = sha256(b"PROGRAM_K_R0B_REFERENCE_REDUNDANCY_V1\0"
                            + block.to_bytes(8, "big")).digest()
            result.extend(int.from_bytes(digest[i:i + 2], "big") % 479 for i in range(0, 32, 2))
        return tuple(result[:q])

    def test_independent_sha256_u16_domain_and_strict_prefix_extension(self):
        for q in (0, 1, 15, 16, 17, 79):
            prefix = h._reference_prefix(q)
            self.assertEqual(tuple(prefix.index(i) for i in range(q)), self.independent_indices(q))
            longer = h._reference_prefix(q + 3)
            self.assertEqual(prefix.indices, longer.indices[:2 * q])
            self.assertEqual(prefix.lengths, longer.lengths[:4 * (q + 1)])

    def test_packed_lengths_empty_prefix_and_no_retained_python_integer_sequence(self):
        for q in (0, 1, 79):
            prefix = h._reference_prefix(q)
            self.assertEqual(prefix.q, q)
            self.assertIs(type(prefix.indices), bytes)
            self.assertIs(type(prefix.lengths), bytes)
            self.assertEqual((len(prefix.indices), len(prefix.lengths)), (2 * q, 4 * (q + 1)))
            self.assertEqual(len(prefix.indices) + len(prefix.lengths), 6 * q + 4)
            self.assertEqual(prefix.added_length(0), 0)
            self.assertFalse(hasattr(prefix, "__dict__"))
            self.assertTrue(all(type(getattr(prefix, f.name)) is bytes for f in fields(prefix)))
        self.assertEqual(h._reference_constraints(h._reference_prefix(0), 0), h._reference_catalog())
        self.assertEqual(6 * 2_581_110 + 4, 15_486_664)

    def test_domain_five_does_not_use_random_time_os_or_text_entropy(self):
        import random
        with patch.object(os, "urandom", side_effect=AssertionError("No OS entropy")), \
             patch.object(random, "random", side_effect=AssertionError("No random")), \
             patch.object(h.time, "time_ns", side_effect=AssertionError("No timestamp")), \
             patch.object(h, "_text_entropy", side_effect=AssertionError("No text domain")):
            self.assertEqual(tuple(h._reference_prefix(33).index(i) for i in range(33)),
                             self.independent_indices(33))
        with self.assertRaises(ValueError):
            h._text_entropy("reference", 0, 10)

    def test_canonical_minimum_increment_is_13_and_catalog_increments_vary(self):
        canonical = json.dumps([[3, 0], 0, []], separators=(",", ":")).encode("ascii")
        self.assertEqual(canonical, b"[[3,0],0,[]]")
        self.assertEqual(len(canonical), 12)
        increments = tuple(1 + len(json.dumps(v, separators=(",", ":")).encode("ascii"))
                           for v in h._reference_catalog())
        self.assertEqual(min(increments), 13)
        self.assertGreater(len(set(increments)), 1)

    def test_prefix_lengths_equal_actual_canonical_record_deltas_for_many_small_prefixes(self):
        _, bundles = _reference_fixture()
        baseline = _reference_values(bundles[execution.WorkerKind.PRIMARY], "control_maintenance")[1]
        baseline_length = len(records.encode(baseline))
        prefix = h._reference_prefix(97)
        for q in (0, 1, 2, 7, 16, 31, 57, 97):
            candidate = replace(baseline, v1_decision=replace(baseline.v1_decision,
                constraints=h._reference_constraints(prefix, q)))
            self.assertEqual(len(records.encode(candidate)) - baseline_length, prefix.added_length(q))
            independent = sum(1 + len(json.dumps(h._reference_catalog()[index],
                separators=(",", ":")).encode("ascii")) for index in self.independent_indices(q))
            self.assertEqual(prefix.added_length(q), independent)

    def test_small_prefix_and_materialization_callbacks_are_fatal(self):
        seen = []
        prefix = h._reference_prefix(97, _check=lambda: seen.append("prefix"))
        h._reference_constraints(prefix, 97, _check=lambda: seen.append("materialize"))
        self.assertIn("prefix", seen)
        self.assertIn("materialize", seen)
        def stop():
            raise RuntimeError("bounded reference cancellation")
        with self.assertRaisesRegex(RuntimeError, "bounded reference cancellation"):
            h._reference_prefix(97, _check=stop)
        with self.assertRaisesRegex(RuntimeError, "bounded reference cancellation"):
            h._reference_constraints(prefix, 97, _check=stop)

    def test_packed_prefix_and_tuple_materialization_check_across_small_chunk_boundary(self):
        # 4,097 entries exercise two implementation chunks without encoding a
        # large reference record, frame or bundle.
        hashes, prefix_checks = [], []
        original_sha = h.sha256
        def hashed(data):
            hashes.append(data)
            return original_sha(data)
        with patch.object(h, "sha256", side_effect=hashed):
            prefix = h._reference_prefix(4097, _check=lambda: prefix_checks.append(len(hashes) * 16))
        self.assertGreaterEqual(len(prefix_checks), 3)
        self.assertTrue(all(b - a <= 65536 for a, b in zip(prefix_checks, prefix_checks[1:])))
        indices, materialization_checks = [], []
        original_index = h.ReferencePrefix.index
        def index(value, i):
            indices.append(i)
            return original_index(value, i)
        with patch.object(h.ReferencePrefix, "index", index):
            constraints = h._reference_constraints(prefix, 4097,
                _check=lambda: materialization_checks.append(len(indices)))
        self.assertEqual(len(constraints), 479 + 4097)
        self.assertEqual(indices, list(range(4097)))
        self.assertGreaterEqual(len(materialization_checks), 3)
        self.assertTrue(all(b - a <= 65536
                            for a, b in zip(materialization_checks, materialization_checks[1:])))


class ReferenceShadowBindingOracleTests(unittest.TestCase):
    def test_three_explicit_shadow_accounting_values_retain_479_true_clues(self):
        for q in (0, 23):
            _, bundles = _reference_fixture(q)
            row = _reference_values(bundles[execution.WorkerKind.K_CONTROL], "kcontrol_maintenance")[1]
            shadow = row.shadow.decision
            values = (shadow.local_before, shadow.local_after, shadow.after)
            self.assertEqual(values[0], values[1])
            self.assertEqual(values[1], values[2])
            self.assertEqual(len({id(value) for value in values}), 3)
            for value in values:
                self.assertEqual((value.P, value.M, value.J, value.H, value.U, value.b),
                                 ((), (), (), ((1, 0),), ((1, 0),), 0))
                self.assertEqual(tuple(v[0] for v in value.constraints), _REFERENCE_SOURCES)
                self.assertEqual(len(value.constraints), 479)
                self.assertEqual(tuple(v[0] for v in value.constraints if v[3]), _REFERENCE_NEIGHBORS)
                self.assertTrue(all(v[1] == 0 and v[2] == () and v[4] == 0 for v in value.constraints))
                self.assertTrue(all(v[3] == ((1, 0),) for v in value.constraints if v[3]))
                records.KControlAccounting.__post_init__(value)
            records.KControlShadowDecision.__post_init__(shadow)

    def test_shadow_connected_fields_and_actual_identity_are_exact(self):
        _, bundles = _reference_fixture(23)
        primary = _reference_values(bundles[execution.WorkerKind.PRIMARY], "control_maintenance")
        actual = _reference_values(bundles[execution.WorkerKind.K_CONTROL], "kcontrol_maintenance")
        shadow = actual[1].shadow.decision
        self.assertEqual((shadow.observation, shadow.num_mines), (h._reference_observation(), 0))
        self.assertEqual((shadow.acquired_mines, shadow.S_first, shadow.S_second_all, shadow.S_new,
            shadow.S_current, shadow.selection_safe_cells, shadow.local_certificates,
            shadow.exact_certificates, shadow.phase_d, shadow.phase_e, shadow.phase_e_status,
            shadow.continuation, shadow.guess_target),
            ((), ((1, 0),), ((1, 0),), (), ((1, 0),), ((1, 0),), (), (), None, None,
             "NOT_REACHED", "LOCAL_SAFE", None))
        self.assertEqual(execution.compare_k_control(primary, actual), (records.AuditStatus.PASS, ()))
        for left, right in zip(primary, actual):
            for field in ("physical", "observation", "public_effect", "terminal_effect", "v1_decision", "guess_checkpoint"):
                self.assertEqual(getattr(left, field), getattr(right, field))

    def test_all_premise_copies_repeat_arms_and_current_semantic_authorities_bind(self):
        for q in (0, 7, 29):
            work, bundles = _reference_fixture(q)
            primary = bundles[execution.WorkerKind.PRIMARY]
            source = dict(primary.streams)
            for kind, bundle in bundles.items():
                self.assertEqual(execution.revalidate_bundle(bundle, work, kind,
                    max_payload_bytes=_REFERENCE_CAP), bundle)
                if kind is not execution.WorkerKind.PRIMARY:
                    self.assertEqual(dict(bundle.streams)["control_maintenance"], source["control_maintenance"])
            repeat = bundles[execution.WorkerKind.DETERMINISM]
            for name, data in primary.streams:
                if name.startswith("control_") or name.startswith("kp0_"):
                    self.assertEqual(dict(repeat.streams)[name], data)
            first = _reference_values(primary, "control_maintenance")
            repeated = _reference_values(repeat, "repeat_control_maintenance")
            self.assertEqual(repeated[1].v1_decision.constraints, first[1].v1_decision.constraints)
            self.assertNotEqual(repeated[1].arm, first[1].arm)
            summary, = _reference_values(repeat, "control_determinism")
            self.assertIs(summary.status, records.AuditStatus.PASS)

    def test_oracle_overlap_exact_public_premises_and_current_qualification_reconstruction(self):
        from experiments import program_k_oracles
        work, bundles = _reference_fixture(7)
        observation = h._reference_observation()
        for kind in (execution.WorkerKind.PRIMARY, execution.WorkerKind.DETERMINISM):
            bundle = bundles[kind]
            prefix = "repeat_" if kind is execution.WorkerKind.DETERMINISM else ""
            coverage, = _reference_values(bundle, prefix + "oracle_b_coverage")
            self.assertTrue(coverage.selected)
            self.assertEqual(coverage.applicable, ((1, "D"), (1, "E")))
            audits = _reference_values(bundle, prefix + "oracle_b_audits")
            self.assertEqual(tuple(v.phase for v in audits), ("D", "E"))
            for audit in audits:
                self.assertEqual((audit.public_observation, audit.logical_mines), (observation, ()))
                self.assertEqual(audit.input_digest, program_k_oracles.oracle_b_input_digest(observation, 0, frozenset()))
                self.assertEqual(audit.expected, audit.actual)
                self.assertEqual((audit.expected.total_worlds, audit.expected.mine_worlds,
                    audit.expected.minimum_risk, audit.expected.minimum_risk_cells,
                    audit.expected.materialized_observation),
                    (1, (((1, 0), 0),), Fraction(0), ((1, 0),), observation))
                self.assertEqual(audit.expected_digest, records.oracle_b_snapshot_digest(audit.expected))
                self.assertEqual(audit.actual_digest, audit.expected_digest)
                self.assertIs(audit.status, records.AuditStatus.PASS)
            rebuilt = h.qualification._reconstruct(work, kind, dict(bundle.streams),
                _reference_timing_table(), SyntheticMaterializationTests.envelope(max_payload_bytes=_REFERENCE_CAP))
            self.assertEqual(rebuilt, bundle)
        k = bundles[execution.WorkerKind.K_CONTROL]
        self.assertEqual(h.qualification._reconstruct(work, k.kind, dict(k.streams), _reference_timing_table(),
            SyntheticMaterializationTests.envelope(max_payload_bytes=_REFERENCE_CAP)), k)

    def test_unselected_oracle_has_no_audits_and_reconstructs(self):
        work, bundles = _reference_fixture(3, oracle=False)
        for kind in (execution.WorkerKind.PRIMARY, execution.WorkerKind.DETERMINISM):
            bundle = bundles[kind]
            prefix = "repeat_" if kind is execution.WorkerKind.DETERMINISM else ""
            self.assertEqual(dict(bundle.streams)[prefix + "oracle_b_audits"], ())
            coverage, = _reference_values(bundle, prefix + "oracle_b_coverage")
            self.assertFalse(coverage.selected)
            self.assertEqual(coverage.applicable, ())
            self.assertEqual(h.qualification._reconstruct(work, kind, dict(bundle.streams), _reference_timing_table(),
                SyntheticMaterializationTests.envelope(max_payload_bytes=_REFERENCE_CAP)), bundle)


class ReferenceSearchSchedulerTests(unittest.TestCase):
    def search(self, low, high, evaluator, target=100, check=None):
        visited = []
        def evaluate(q, ordinal):
            visited.append(q)
            return evaluator(q, ordinal)
        trials, selected = h._search_reference_trials(low, high, target, evaluate, _check=check)
        self.assertEqual(tuple(visited), tuple(v.q for v in trials))
        self.assertEqual(tuple(v.ordinal for v in trials), tuple(range(1, len(trials) + 1)))
        self.assertEqual(len(set(visited)), len(visited))
        self.assertLessEqual(len(trials), 8)
        return trials, selected

    def test_nonzero_lower_endpoint_upper_endpoint_then_at_most_eight_unique_trials(self):
        first = self.search(7, 107, lambda q, ordinal: _reference_trial(ordinal, q, 50))
        self.assertEqual(tuple(v.q for v in first[0])[:2], (7, 107))
        self.assertEqual(len(first[0]), 8)
        self.assertIsNone(first[1])
        self.assertEqual(first, self.search(7, 107, lambda q, ordinal: _reference_trial(ordinal, q, 50)))
        singleton, _ = self.search(7, 7, lambda q, ordinal: _reference_trial(ordinal, q))
        self.assertEqual(tuple(v.q for v in singleton), (7,))
        tiny, _ = self.search(7, 10, lambda q, ordinal: _reference_trial(ordinal, q))
        self.assertEqual(set(v.q for v in tiny), {7, 8, 9, 10})

    def test_exact_secant_integer_floor_targets_reference_physical_minimum(self):
        rows = (_reference_trial(1, 7, 10), _reference_trial(2, 17, 40))
        self.assertEqual(h._next_reference_q(rows, 7, 17, 20), 10)
        negative = (_reference_trial(1, 7, 40), _reference_trial(2, 17, 10))
        self.assertEqual(h._next_reference_q(negative, 7, 17, 20), 13)

    def test_secant_pair_uses_distance_a_b_tie_order(self):
        rows = (_reference_trial(1, 7, 90), _reference_trial(2, 107, 110),
                _reference_trial(3, 27, 99), _reference_trial(4, 77, 102))
        self.assertEqual(h._next_reference_q(rows, 7, 107, 100), 43)
        tied = (_reference_trial(1, 7, 90), _reference_trial(2, 107, 110),
                _reference_trial(3, 27, 90), _reference_trial(4, 77, 110))
        self.assertEqual(h._next_reference_q(tied, 7, 107, 100), 42)

    def test_invalid_duplicate_equal_physical_proposals_use_largest_gap_midpoint(self):
        for pa, pb in ((10, 11), (100, 200), (10, 10)):
            rows = (_reference_trial(1, 7, pa), _reference_trial(2, 17, pb))
            self.assertEqual(h._next_reference_q(rows, 7, 17, 100), 12)
        rows = tuple(_reference_trial(i + 1, q, 50) for i, q in enumerate((7, 15, 11)))
        self.assertEqual(h._next_reference_q(rows, 7, 15, 100), 9)
        all_values = tuple(_reference_trial(i + 1, i + 7, 50) for i in range(4))
        self.assertIsNone(h._next_reference_q(all_values, 7, 10, 100))

    def test_nonmonotonic_physical_observations_leave_both_sides_available(self):
        values = {7: 110, 23: 110, 15: 90, 11: 101, 19: 99, 9: 100, 13: 80, 17: 120}
        trials, selected = self.search(7, 23,
            lambda q, ordinal: _reference_trial(ordinal, q, values.get(q, 95)))
        self.assertEqual(tuple(v.q for v in trials)[:4], (7, 23, 15, 11))
        self.assertTrue(any(15 < v.q < 23 for v in trials))
        self.assertEqual(selected, min((v for v in trials if v.eligible),
            key=lambda v: (v.actual_physical_bytes, v.actual_logical_bytes, v.q)))

    def test_first_eligible_is_not_returned_early_and_selection_uses_p_l_q(self):
        trials, selected = self.search(7, 27, lambda q, ordinal:
            _reference_trial(ordinal, q, 110 if q == 7 else 100, 101 if q == 27 else 100))
        self.assertEqual(len(trials), 8)
        self.assertTrue(trials[0].eligible)
        self.assertNotEqual(selected, trials[0])
        self.assertEqual(selected, min((v for v in trials if v.eligible),
            key=lambda v: (v.actual_physical_bytes, v.actual_logical_bytes, v.q)))

    def test_callback_wraps_each_trial_and_failure_after_success_aborts(self):
        calls = []
        def evaluate(q, ordinal):
            calls.append(("trial", q))
            return _reference_trial(ordinal, q)
        h._search_reference_trials(7, 8, 100, evaluate, _check=lambda: calls.append(("check", None)))
        self.assertEqual(calls, [("check", None), ("trial", 7), ("check", None),
                                 ("check", None), ("trial", 8), ("check", None)])
        visited = []
        def eligible(q, ordinal):
            visited.append(q)
            return _reference_trial(ordinal, q)
        def cancel():
            if visited:
                raise RuntimeError("cancel after reference success")
        with self.assertRaisesRegex(RuntimeError, "cancel after reference success"):
            h._search_reference_trials(7, 107, 100, eligible, _check=cancel)
        self.assertEqual(visited, [7])
        with self.assertRaisesRegex(MemoryError, "reference resource"):
            h._search_reference_trials(7, 107, 100,
                lambda *_: (_ for _ in ()).throw(MemoryError("reference resource")))

    def test_reference_policy_has_no_plus_4096_upper_window(self):
        for physical_bytes in (100, 4196, 4197, 100000):
            trial = _reference_trial(1, 7, physical_bytes)
            self.assertTrue(trial.eligible)
            self.assertIsNone(trial.rejection_reason)
        trials, selected = self.search(7, 10, lambda q, ordinal:
            _reference_trial(ordinal, q, (100, 4196, 4197, 100000)[q - 7]))
        self.assertTrue(all(v.eligible for v in trials))
        self.assertEqual(selected.q, 7)
        self.assertNotIn("SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT", tuple(v.rejection_reason for v in trials))


def _reference_text_families(kind, oracle):
    if kind is execution.WorkerKind.PRIMARY:
        return ("primary",) + (("oracle_primary",) if oracle else ())
    if kind is execution.WorkerKind.DETERMINISM:
        return ("determinism",) + (("oracle_repeat",) if oracle else ())
    return ("k_control",)


def _reference_actual_logical_fit(bundles, targets, cap, *, oracle=True):
    for bundle in bundles:
        reserve = sum(max(0, getattr(targets.logical, family) - _text_logical_bytes(bundle, family))
                      for family in _reference_text_families(bundle.kind, oracle))
        bodies = tuple(data for _, values in bundle.streams for data in values)
        if (any(len(data) > cap for data in bodies) or sum(map(len, bodies)) + reserve > cap
                or len(execution.encode_bundle(bundle)) + reserve > cap):
            return False
    return True


class ReferenceLogicalBoundsTests(unittest.TestCase):
    def test_copy_aware_absolute_ceiling_is_arithmetic_only(self):
        self.assertEqual(67_108_864 // 13, 5_162_220)
        self.assertEqual(67_108_864 // 26, 2_581_110)
        self.assertEqual(6 * (67_108_864 // 26) + 4, 15_486_664)

    def test_exact_q_hi_handles_k_only_d_only_and_both_including_fixed_bytes(self):
        cases = tuple(_reference_fixture(k=k, d=d) for k, d in ((True, False), (False, True), (True, True)))
        cap = max(len(execution.encode_bundle(v)) for _, values in cases for v in values.values()) + 1024
        prefix = h._reference_prefix(cap // 26)
        highs = []
        for work, values in cases:
            bundles = tuple(values.values())
            targets = _reference_targets(work)
            with patch.object(physical, "encode_payload", side_effect=AssertionError("Bounds use no compression")), \
                 patch.object(execution, "encode_bundle_v2", side_effect=AssertionError("Bounds use no physical wire")):
                low, high = h._reference_q_bounds(bundles, targets, prefix, cap)
            self.assertEqual(low, 0)
            self.assertLess(high, cap // 26)
            self.assertLessEqual(high, 2_581_110)
            actual = h._reference_bundles(work, prefix, high)
            after = h._reference_bundles(work, prefix, high + 1)
            self.assertTrue(_reference_actual_logical_fit(actual, targets, cap))
            self.assertFalse(_reference_actual_logical_fit(after, targets, cap))
            self.assertTrue(h._reference_expanded_fits(bundles, targets, prefix.added_length(high), cap))
            self.assertFalse(h._reference_expanded_fits(bundles, targets, prefix.added_length(high + 1), cap))
            highs.append(high)
        self.assertEqual(highs[2], min(highs[:2]))

    def test_text_logical_reserve_reduces_domain_and_is_dynamic_for_copied_families(self):
        work, values = _reference_fixture()
        bundles = tuple(values.values())
        cap = max(len(execution.encode_bundle(v)) for v in bundles) + 2048
        prefix = h._reference_prefix(cap // 26)
        baseline = _reference_targets(work)
        before = h._reference_q_bounds(bundles, baseline, prefix, cap)[1]
        for family, kind in (("primary", execution.WorkerKind.PRIMARY),
                             ("k_control", execution.WorkerKind.K_CONTROL),
                             ("determinism", execution.WorkerKind.DETERMINISM)):
            current = _text_logical_bytes(values[kind], family)
            target = replace(baseline, logical=replace(baseline.logical, **{family: current + 1024}))
            after = h._reference_q_bounds(bundles, target, prefix, cap)[1]
            self.assertLessEqual(after, before)
            for q in (0, min(7, after), after):
                actual = h._reference_bundles(work, prefix, q)
                self.assertEqual(h._reference_expanded_fits(bundles, target, prefix.added_length(q), cap),
                                 _reference_actual_logical_fit(actual, target, cap))
            beyond = h._reference_bundles(work, prefix, after + 1)
            self.assertFalse(_reference_actual_logical_fit(beyond, target, cap))

    def test_q_lo_prefix_binary_search_matches_actual_canonical_brute_force(self):
        work, values = _reference_fixture()
        bundles = tuple(values.values())
        primary = values[execution.WorkerKind.PRIMARY]
        row = _reference_values(primary, "control_maintenance")[1]
        fixed = len(dict(primary.streams)["control_maintenance"][0])
        prefix = h._reference_prefix(97)
        lengths = tuple(fixed + len(records.encode(replace(row, v1_decision=replace(row.v1_decision,
            constraints=h._reference_constraints(prefix, q))))) for q in range(98))
        for target in (lengths[0] - 1, lengths[0], lengths[1], lengths[7] - 1, lengths[31], lengths[97]):
            targets = _reference_targets(work, logical_reference=target)
            actual, _ = h._reference_q_bounds(bundles, targets, prefix, _REFERENCE_CAP)
            self.assertEqual(actual, next(q for q, length in enumerate(lengths) if length >= target))


class ReferenceConstructorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work, cls.baselines = _reference_fixture()
        cls.cap = max(len(execution.encode_bundle(v)) for v in cls.baselines.values()) + 1024
        cls.envelope = SyntheticMaterializationTests.envelope(max_payload_bytes=cls.cap)
        cls.logical0 = _text_logical_bytes(cls.baselines[execution.WorkerKind.PRIMARY], "reference")
        cls.targets = _reference_targets(cls.work,
            logical_reference=cls.logical0 + h._reference_prefix(7).added_length(7))
        cls.result = h.construct_reference_v2(cls.work, cls.targets, _REFERENCE_PROFILE,
            max_payload_bytes=cls.cap, envelope=cls.envelope)

    def construct(self, **changes):
        args = dict(max_payload_bytes=self.cap, envelope=self.envelope)
        args.update(changes)
        return h.construct_reference_v2(self.work, args.pop("targets", self.targets),
            _REFERENCE_PROFILE, **args)

    def test_selected_immutable_result_facts_have_all_units_and_bounded_q_ledger(self):
        result = self.result
        self.assertIsNone(result.rejection_reason)
        self.assertIsNone(result.cause)
        self.assertEqual(result.q_lo, 7)
        self.assertEqual(tuple(v.q for v in result.trials)[:2], (result.q_lo, result.q_hi))
        self.assertLessEqual(len(result.trials), 8)
        self.assertEqual(len(set(v.q for v in result.trials)), len(result.trials))
        self.assertEqual(result.selected_trial, min((v for v in result.trials if v.eligible),
            key=lambda v: (v.actual_physical_bytes, v.actual_logical_bytes, v.q)))
        self.assertEqual(tuple(v.kind for v in result.selected_trial.units), operational._kinds(self.work))
        self.assertTrue(all(type(wire) is bytes for wire in result.selected_wires))
        for value in (result, result.selected_trial, *result.selected_trial.units):
            self.assertFalse(hasattr(value, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)

    def test_selected_all_wires_equal_full_encoder_and_fresh_context_metrics(self):
        result = self.result
        prior = result.selected_wires[0]
        for bundle, wire, metrics in zip(result.selected_bundles, result.selected_wires, result.selected_trial.units):
            self.assertEqual(wire, execution.encode_bundle_v2(bundle, _REFERENCE_PROFILE, max_payload_bytes=self.cap))
            fresh = operational._fresh_wb02_context(wire, self.work, bundle.kind, _REFERENCE_PROFILE,
                self.envelope, prior_primary_wire=None if bundle.kind is execution.WorkerKind.PRIMARY else prior)
            self.assertEqual(fresh.bundle, bundle)
            self.assertEqual((metrics.lsum, metrics.llegacy, metrics.sunit, metrics.wnew),
                (fresh.logical_bytes, fresh.legacy_bundle_bytes, fresh.physical_frame_bytes, fresh.wb02_wire_bytes))
            self.assertEqual(metrics.physical_closure, metrics.sunit + metrics.physical_reserve)
            self.assertLessEqual(metrics.physical_closure, self.cap)
            self.assertTrue(all(v <= self.cap for v in (metrics.lsum, metrics.llegacy, metrics.sunit, metrics.wnew)))
            if bundle.kind is execution.WorkerKind.PRIMARY:
                rows = tuple(row for row in fresh.rows if row.stream_name == "control_maintenance")
                self.assertEqual((sum(v.frame_length for v in rows), sum(len(v.logical_bytes) for v in rows)),
                    (result.selected_trial.actual_physical_bytes, result.selected_trial.actual_logical_bytes))

    def test_no_repeated_primary_body_compression_and_unchanged_frames_reused(self):
        original_search, original_payload = h._search_reference_trials, physical.encode_payload
        compressions, per_trial = [], []
        def payload(data, *args, **kwargs):
            compressions.append(data)
            return original_payload(data, *args, **kwargs)
        def search(low, high, target, evaluate, *, _check=None):
            def observed(q, ordinal):
                start = len(compressions)
                trial = evaluate(q, ordinal)
                per_trial.append(tuple(compressions[start:]))
                return trial
            return original_search(low, high, target, observed, _check=_check)
        with patch.object(physical, "encode_payload", side_effect=payload), \
             patch.object(h, "_search_reference_trials", side_effect=search), \
             patch.object(execution, "encode_bundle_v2", wraps=execution.encode_bundle_v2) as full:
            result = self.construct()
        self.assertLessEqual(full.call_count, len(self.baselines))
        self.assertEqual(len(per_trial), len(result.trials))
        self.assertTrue(all(len(values) <= 4 for values in per_trial))
        self.assertTrue(all(len(values) == len(set(values)) for values in per_trial))
        self.assertTrue(any(len(values) == 4 for values in per_trial))
        copied = []
        for bundle, wire in zip(result.selected_bundles, result.selected_wires):
            current = execution.decode_bundle_view_v2(wire, _REFERENCE_PROFILE, max_payload_bytes=self.cap)
            oldwire = execution.encode_bundle_v2(self.baselines[bundle.kind], _REFERENCE_PROFILE, max_payload_bytes=self.cap)
            baseline = execution.decode_bundle_view_v2(oldwire, _REFERENCE_PROFILE, max_payload_bytes=self.cap)
            old = {(v.stream_name, v.key): v for v in baseline.rows}
            for row in current.rows:
                prior = old[row.stream_name, row.key]
                if row.logical_bytes == prior.logical_bytes:
                    self.assertEqual(row.frame_bytes, prior.frame_bytes)
                if row.stream_name == "control_maintenance" and row.key[2] == 1:
                    copied.append(row)
        self.assertEqual(len(copied), 3)
        self.assertEqual(len({row.logical_bytes for row in copied}), 1)
        self.assertEqual(len({row.key for row in copied}), 3)
        self.assertEqual(len({row.frame_bytes for row in copied}), 3)

    def test_logical_domain_failure_precedes_physical_search_and_has_concrete_cause(self):
        targets = replace(self.targets, logical=replace(self.targets.logical, reference=self.cap))
        with patch.object(h, "_search_reference_trials", side_effect=AssertionError("No physical q search")), \
             patch.object(physical, "encode_payload", side_effect=AssertionError("No physical compression")):
            result = self.construct(targets=targets)
        self.assertEqual(result.rejection_reason, "REFERENCE_SYNTHETIC_SIZING_UNREPRESENTABLE")
        self.assertIn("LOGICAL", result.cause)
        self.assertEqual(result.trials, ())
        self.assertIsNone(result.selected_trial)
        self.assertEqual(result.selected_bundles, ())
        self.assertEqual(result.selected_wires, ())

    def test_physical_text_reserve_is_exact_necessary_floor_without_4096(self):
        wire = execution.encode_bundle_v2(self.baselines[execution.WorkerKind.PRIMARY],
            _REFERENCE_PROFILE, max_payload_bytes=self.cap)
        view = execution.decode_bundle_view_v2(wire, _REFERENCE_PROFILE, max_payload_bytes=self.cap)
        primary_p, _ = _text_family_metrics(view, "primary")
        targets = replace(self.targets, physical=replace(self.targets.physical, primary=primary_p + 5))
        result = self.construct(targets=targets)
        self.assertIsNone(result.rejection_reason)
        primary = result.selected_trial.units[0]
        self.assertEqual(primary.physical_reserve, 5)
        self.assertEqual(primary.physical_closure, primary.sunit + 5)
        impossible = replace(targets, physical=replace(targets.physical, primary=self.cap + 1))
        rejected = self.construct(targets=impossible)
        self.assertEqual(rejected.rejection_reason, "REFERENCE_SYNTHETIC_SIZING_UNREPRESENTABLE")
        self.assertIsNotNone(rejected.cause)
        self.assertTrue(all(not v.eligible for v in rejected.trials))

    def test_new_identity_composes_with_one_1f_search_and_unknown_identity_rejects(self):
        result = self.result
        primary = result.selected_bundles[0]
        view = execution.decode_bundle_view_v2(result.selected_wires[0], _REFERENCE_PROFILE,
                                                max_payload_bytes=self.cap)
        p, logical = _text_family_metrics(view, "primary")
        text = h.construct_text_family_v2(self.work, primary, "primary", _REFERENCE_PROFILE,
            physical_target=max(1, p - 128), logical_target=logical + 3,
            max_payload_bytes=self.cap, envelope=self.envelope)
        self.assertIsNone(text.rejection_reason)
        self.assertEqual(dict(text.selected_bundle.streams)["control_maintenance"],
                         dict(primary.streams)["control_maintenance"])
        wrong = replace(self.work, board=replace(self.work.board, fingerprint="FORGED_REFERENCE"))
        with self.assertRaises(ValueError):
            h.construct_text_family_v2(wrong, primary, "primary", _REFERENCE_PROFILE,
                physical_target=1, logical_target=1, max_payload_bytes=self.cap, envelope=self.envelope)

    def test_input_domains_callbacks_resources_and_historical_fact_registry_are_closed(self):
        for work in (replace(self.work, k_control_selected=False, determinism_selected=False),
                     replace(self.work, board=h.synthetic_board_identity(self.work.board.game_index))):
            with self.assertRaises(ValueError):
                h.construct_reference_v2(work, self.targets, _REFERENCE_PROFILE,
                    max_payload_bytes=self.cap, envelope=self.envelope)
        with self.assertRaisesRegex(RuntimeError, "reference abort"):
            self.construct(_check=lambda: (_ for _ in ()).throw(RuntimeError("reference abort")))
        with patch.object(h, "_reference_prefix", side_effect=MemoryError("reference memory")), \
             self.assertRaisesRegex(MemoryError, "reference memory"):
            self.construct()
        from experiments import program_k_e2_r0_evidence as evidence
        for cls in (h.ReferenceTrial, h.ReferenceConstructionResult):
            self.assertNotIn(cls, evidence._FACT_TYPES.values())
            with self.assertRaisesRegex(h.HarnessError, "UNSUPPORTED_METADATA_FACT"):
                h._fact_read({"fact": cls.__name__, "fields": {}})

    def test_baseline_cap_and_binding_failures_return_concrete_root_cause(self):
        cases = ((execution, "encode_bundle_v2", execution.E2ExecutionError("WORKER_WIRE_CAP"),
                  "WORKER_WIRE_CAP"),
                 (operational, "_fresh_wb02_context", operational.OperationalError("WB02_WORK_KIND_BINDING"),
                  "WB02_WORK_KIND_BINDING"))
        for owner, name, error, cause in cases:
            with self.subTest(stage=name), patch.object(owner, name, side_effect=error), \
                 patch.object(h, "_search_reference_trials", side_effect=AssertionError("No invalid baseline search")):
                result = self.construct()
            self.assertEqual(result.rejection_reason, "REFERENCE_SYNTHETIC_SIZING_UNREPRESENTABLE")
            self.assertEqual(result.cause, cause)
            self.assertEqual(result.trials, ())
            self.assertIsNone(result.selected_trial)
            self.assertEqual((result.selected_bundles, result.selected_wires), ((), ()))
        # A callback carrying the same exception type/code remains fatal; it
        # cannot be converted to an ordinary baseline or candidate rejection.
        def stop():
            raise execution.E2ExecutionError("WORKER_WIRE_CAP")
        with self.assertRaisesRegex(execution.E2ExecutionError, "WORKER_WIRE_CAP"):
            self.construct(_check=stop)

    def test_trial_binding_failures_preserve_specific_cause_in_every_ledger_entry(self):
        original = h._search_reference_trials
        def search(low, high, target, evaluate, *, _check=None):
            with patch.object(execution, "revalidate_bundle",
                              side_effect=execution.E2ExecutionError("CONTROL_O4_REFERENCE_BINDING")):
                return original(low, high, target, evaluate, _check=_check)
        with patch.object(h, "_search_reference_trials", side_effect=search):
            result = self.construct()
        self.assertEqual(result.rejection_reason, "REFERENCE_SYNTHETIC_SIZING_UNREPRESENTABLE")
        self.assertEqual(result.cause, "CONTROL_O4_REFERENCE_BINDING")
        self.assertEqual(len(result.trials), 8)
        self.assertEqual({v.rejection_reason for v in result.trials}, {"CONTROL_O4_REFERENCE_BINDING"})
        self.assertTrue(all(not v.eligible for v in result.trials))
        self.assertTrue(all(v.actual_logical_bytes >= self.targets.logical.reference for v in result.trials))
        self.assertEqual((result.selected_bundles, result.selected_wires), ((), ()))


# Slice 1I profile capture is read-only. It exercises no synthetic constructor.
_POLICY_NAMES = ("program-k-r0b-reference-constructor/v1", "program-k-r0b-text-constructor/v1")
_POLICY_REFERENCE_SOURCES = (
    "reference_board_identity", "ReferencePrefix", "_reference_catalog", "_reference_observation",
    "_reference_prefix", "_reference_constraints", "_reference_work", "_reference_projection",
    "_reference_maintenance", "_reference_k_actual", "_reference_children", "_reference_bundles",
    "_reference_candidate_bundles", "_reference_text_families", "_reference_size_bases",
    "_reference_bases_fit", "_reference_expanded_fits", "_reference_q_bounds", "ReferenceUnitMetrics",
    "ReferenceTrial", "ReferenceConstructionResult", "_next_reference_q", "_search_reference_trials",
    "_reference_failure", "_reference_static_cause", "_reference_unit_metrics", "construct_reference_v2",
)
_POLICY_TEXT_SOURCES = (
    "TextTrial", "TextConstructionResult", "_text_spec", "_text_check", "_text_entropy", "_text_filler",
    "_text_lengths", "_next_text_h", "_search_text_trials", "_text_terminal_reason", "_mutate_text_bundle",
    "_text_owned", "construct_text_family_v2",
)


@contextmanager
def _profile_read_only():
    """Permit source/native reads while rejecting filesystem write entry points."""
    import builtins
    import io
    original_builtin, original_io, original_os = builtins.open, io.open, os.open
    def opened(original, file, mode="r", *args, **kwargs):
        if type(mode) is not str or any(flag in mode for flag in "wax+"):
            raise AssertionError("Profile capture must not write files")
        return original(file, mode, *args, **kwargs)
    def os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise AssertionError("Profile capture must not write files")
        return original_os(path, flags, *args, **kwargs)
    with patch.object(builtins, "open", side_effect=lambda *a, **k: opened(original_builtin, *a, **k)), \
         patch.object(io, "open", side_effect=lambda *a, **k: opened(original_io, *a, **k)), \
         patch.object(os, "open", side_effect=os_open), \
         patch.object(Path, "write_bytes", side_effect=AssertionError("No profile artifact")), \
         patch.object(Path, "write_text", side_effect=AssertionError("No profile artifact")), \
         patch.object(Path, "mkdir", side_effect=AssertionError("No profile directory")):
        yield


class ConstructorPolicyIdentityTests(unittest.TestCase):
    def test_exact_names_digests_repeat_capture_and_canonical_bundles(self):
        identities = h._constructor_policy_identities()
        self.assertIs(type(identities), tuple)
        self.assertEqual(tuple(v["name"] for v in identities), _POLICY_NAMES)
        self.assertEqual(identities, h._constructor_policy_identities())
        bundles = h._constructor_policy_source_bundles()
        self.assertEqual(len(bundles), 2)
        for identity_fact, data in zip(identities, bundles):
            self.assertEqual(set(identity_fact), {"name", "sha256"})
            self.assertRegex(identity_fact["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(identity_fact["sha256"], sha256(data).hexdigest())
            self.assertTrue(data.isascii())
            node = json.loads(data)
            self.assertEqual(set(node), {"schema", "name", "constants", "sources"})
            self.assertEqual(node["schema"], "program-k-r0b-constructor-policy-source/v1")
            self.assertEqual(node["name"], identity_fact["name"])
            self.assertEqual(data, json.dumps(node, sort_keys=True, separators=(",", ":"),
                                             ensure_ascii=True, allow_nan=False).encode("ascii"))

    def test_every_required_source_is_present_once_in_exact_order_and_preserved(self):
        getsource = inspect.getsource
        with patch.object(inspect, "getsource", wraps=getsource) as captured:
            bundles = h._constructor_policy_source_bundles()
        expected_names = _POLICY_REFERENCE_SOURCES + _POLICY_TEXT_SOURCES
        self.assertEqual(tuple(call.args[0] for call in captured.call_args_list),
                         tuple(getattr(h, name) for name in expected_names))
        for data, names in zip(bundles, (_POLICY_REFERENCE_SOURCES, _POLICY_TEXT_SOURCES)):
            sources = json.loads(data)["sources"]
            self.assertEqual(tuple(v["name"] for v in sources), names)
            self.assertEqual(len({v["name"] for v in sources}), len(names))
            for item in sources:
                self.assertEqual(set(item), {"name", "source"})
                source = getsource(getattr(h, item["name"])).replace("\r\n", "\n").replace("\r", "\n")
                self.assertEqual(item["source"], source)

    def test_closed_reference_and_text_constants_match_accepted_policy(self):
        reference, text = (json.loads(data)["constants"] for data in h._constructor_policy_source_bundles())
        self.assertEqual(reference, {
            "_REFERENCE_Q_MAX": 2581110, "_REFERENCE_TEXT": "SYNTHETIC_NON_EVIDENCE|L:|H:",
            "board_dimensions": [30, 16], "mines": 0, "origin": [0, 0], "target": [1, 0],
            "catalog_entries": 479, "redundancy_domain": "PROGRAM_K_R0B_REFERENCE_REDUNDANCY_V1\0",
            "minimum_additional_entry_bound": 13, "packed_prefix_bytes": "6q+4", "candidate_limit": 8,
            "selection_order": ["actual_physical_bytes", "actual_logical_bytes", "q"],
            "physical_upper_window": None, "readiness_policy": "dual-independent-ceil-3-over-2/v1",
        })
        self.assertEqual(text, {
            "_TEXT_FAMILIES": [
                ["primary", "PRIMARY", "evaluators", 0, 1],
                ["k_control", "K_CONTROL", "kcontrol_maintenance", -1, 1],
                ["oracle_primary", "PRIMARY", "oracle_b_audits", None, 4],
                ["oracle_repeat", "DETERMINISM", "repeat_oracle_b_audits", None, 4],
                ["determinism", "DETERMINISM", "repeat_evaluators", 0, 1],
            ],
            "text_format": '"SYNTHETIC_NON_EVIDENCE|L:" + "x"*ell + "|H:" + Base64(B(h))',
            "entropy_domain": "PROGRAM_K_R0B_TEXT_FILL_V1\0", "entropy_raw_block_bytes": 49152,
            "base64_full_block_chars": 65536, "candidate_limit": 8, "physical_window": 4096,
            "secant_target": "T_P", "selection_order": ["actual_physical_bytes", "actual_logical_bytes", "h"],
            "readiness_policy": "dual-independent-ceil-3-over-2/v1",
        })
        self.assertEqual(reference["_REFERENCE_Q_MAX"], h._REFERENCE_Q_MAX)
        self.assertEqual(reference["_REFERENCE_TEXT"], h._REFERENCE_TEXT)
        self.assertEqual(text["_TEXT_FAMILIES"],
                         [[name, kind.value, stream, index, copies] for name, kind, stream, index, copies
                          in h._TEXT_FAMILIES])

    def test_lf_crlf_and_cr_sources_have_identical_identity(self):
        expected = h._constructor_policy_identities()
        getsource = inspect.getsource
        for ending in ("\n", "\r\n", "\r"):
            def source(value):
                return getsource(value).replace("\r\n", "\n").replace("\r", "\n").replace("\n", ending)
            with self.subTest(ending=repr(ending)), patch.object(inspect, "getsource", side_effect=source):
                self.assertEqual(h._constructor_policy_identities(), expected)

    def test_constant_floats_nan_boolean_and_numeric_impostors_fail_closed(self):
        class IntImpostor(int):
            pass
        for value in (1.5, float("nan"), float("inf"), True, IntImpostor(2581110), object()):
            with self.subTest(value=type(value)), patch.object(h, "_REFERENCE_Q_MAX", value), \
                 self.assertRaisesRegex(h.HarnessError, "SOURCE_VALUE"):
                h._constructor_policy_identities()
        families = list(h._TEXT_FAMILIES)
        families[0] = families[0][:-1] + (1.5,)
        with patch.object(h, "_TEXT_FAMILIES", tuple(families)), \
             self.assertRaisesRegex(h.HarnessError, "SOURCE_VALUE"):
            h._constructor_policy_identities()

    def test_each_bound_source_change_affects_only_its_own_policy(self):
        before = h._constructor_policy_identities()
        sources = {name: inspect.getsource(getattr(h, name))
                   for name in _POLICY_REFERENCE_SOURCES + _POLICY_TEXT_SOURCES}
        for index, names in enumerate((_POLICY_REFERENCE_SOURCES, _POLICY_TEXT_SOURCES)):
            for changed_name in names:
                def source(value):
                    # Retaining this whitespace demonstrates that only newlines normalize.
                    return sources[value.__name__] + (" " if value.__name__ == changed_name else "")
                with self.subTest(source=changed_name), patch.object(inspect, "getsource", side_effect=source):
                    after = h._constructor_policy_identities()
                self.assertNotEqual(after[index]["sha256"], before[index]["sha256"])
                self.assertEqual(after[1 - index], before[1 - index])

    def test_orchestration_and_complete_harness_file_are_outside_policy_identity(self):
        expected = h._constructor_policy_identities()
        hashed = []
        def digest(data):
            hashed.append(data)
            return sha256(data)
        with patch.object(h, "_measure_r0a", new=lambda *a, **k: "changed orchestration"), \
             patch.object(h, "materialize_synthetic", new=lambda *a, **k: "changed persistence"), \
             patch.object(h, "launch_r0b", new=lambda *a, **k: "changed launcher"), \
             patch.object(h, "sha256", side_effect=digest):
            self.assertEqual(h._constructor_policy_identities(), expected)
        self.assertEqual(tuple(hashed), h._constructor_policy_source_bundles())
        self.assertEqual(len(hashed), 2)

    def test_path_mtime_line_number_and_object_identity_do_not_enter_digest(self):
        from types import FunctionType
        expected = h._constructor_policy_identities()
        sources = {name: inspect.getsource(getattr(h, name))
                   for name in _POLICY_REFERENCE_SOURCES + _POLICY_TEXT_SOURCES}
        original = h._text_entropy
        copied = FunctionType(original.__code__.replace(co_filename="different-source-path.py",
            co_firstlineno=original.__code__.co_firstlineno + 17), original.__globals__, original.__name__,
            original.__defaults__, original.__closure__)
        self.assertIsNot(copied, original)
        with patch.object(h, "_text_entropy", new=copied), \
             patch.object(h, "__file__", "different-harness-path.py"), \
             patch.object(h, "_HARNESS_PATH", "different-harness-path.py"), \
             patch.object(inspect, "getsource", side_effect=lambda value: sources[value.__name__]), \
             patch.object(Path, "stat", side_effect=AssertionError("No identity mtime")), \
             patch.object(Path, "read_bytes", side_effect=AssertionError("No whole-file identity")), \
             patch.object(Path, "open", side_effect=AssertionError("No whole-file identity")):
            self.assertEqual(h._constructor_policy_identities(), expected)

    def test_missing_impostor_and_unavailable_source_fail_closed(self):
        for name in _POLICY_REFERENCE_SOURCES + _POLICY_TEXT_SOURCES:
            with self.subTest(name=name), patch.object(h, name, None), \
                 self.assertRaisesRegex(h.HarnessError, "SOURCE_OBJECT_REQUIRED"):
                h._constructor_policy_identities()
        for value in (object(), h._text_filler, lambda: None):
            with self.subTest(value=type(value)), patch.object(h, "_text_entropy", value), \
                 self.assertRaisesRegex(h.HarnessError, "SOURCE_OBJECT_REQUIRED"):
                h._constructor_policy_identities()
        for unavailable in (OSError("missing source"), TypeError("built-in object")):
            with patch.object(inspect, "getsource", side_effect=unavailable), \
                 self.assertRaisesRegex(h.HarnessError, "SOURCE_UNAVAILABLE"):
                h._constructor_policy_identities()
        for unavailable in ("", " \n", None, b"source"):
            with patch.object(inspect, "getsource", return_value=unavailable), \
                 self.assertRaisesRegex(h.HarnessError, "SOURCE_UNAVAILABLE"):
                h._constructor_policy_identities()

    def test_import_performs_no_policy_capture_qualification_or_writes(self):
        import importlib.util
        import sys
        name = "experiments._slice1i_harness_import_fixture"
        spec = importlib.util.spec_from_file_location(name, h.__file__)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {name: module}), _profile_read_only(), \
             patch.object(inspect, "getsource", side_effect=AssertionError("No import source capture")), \
             patch.object(physical, "capture_profile", side_effect=AssertionError("No import profile")), \
             patch.object(physical, "capture_qualified_profile", side_effect=AssertionError("No import qualification")), \
             patch.object(physical, "encode_payload", side_effect=AssertionError("No import self-check")):
            spec.loader.exec_module(module)


class QualifiedHarnessProfileTests(unittest.TestCase):
    def test_harness_owner_propagates_capture_errors_and_rejects_unqualified_result(self):
        from tests.test_program_k_e2_physical import _profile_facts
        writers, runtime = _profile_facts()
        unqualified = physical.profile_from_facts(writer_sources=writers, runtime=runtime)
        policies = h._constructor_policy_identities()
        with patch.object(physical, "capture_qualified_profile", return_value=unqualified) as captured, \
             self.assertRaises(physical.PhysicalError):
            h._capture_qualified_codec_profile()
        captured.assert_called_once_with(constructor_policies=policies)
        with patch.object(physical, "capture_qualified_profile",
                          side_effect=physical.PhysicalError("PROFILE_CAPTURE_INCOMPLETE")), \
             self.assertRaisesRegex(physical.PhysicalError, "PROFILE_CAPTURE_INCOMPLETE"):
            h._capture_qualified_codec_profile()
        with patch.object(h, "_text_entropy", None), \
             patch.object(physical, "capture_qualified_profile", side_effect=AssertionError("No incomplete policy")), \
             self.assertRaisesRegex(h.HarnessError, "SOURCE_OBJECT_REQUIRED"):
            h._capture_qualified_codec_profile()

    def test_current_approved_windows_profile_is_exact_deterministic_and_read_only(self):
        import ctypes
        import subprocess
        import sys
        import sysconfig
        import zlib
        self.assertEqual(os.name, "nt")
        self.assertIsNone(getattr(zlib, "__file__", None))
        self.assertEqual(zlib.__spec__.origin, "built-in")
        self.assertIs(type(sys.dllhandle), int)
        buffer = ctypes.create_unicode_buffer(32768)
        get_name = ctypes.windll.kernel32.GetModuleFileNameW
        get_name.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32)
        get_name.restype = ctypes.c_uint32
        count = get_name(ctypes.c_void_p(sys.dllhandle), buffer, len(buffer))
        self.assertGreater(count, 0)
        self.assertLess(count, len(buffer))
        loaded_dll = Path(buffer.value).resolve(strict=True)
        blocked_codes = {getattr(h, name).__code__ for name in
            ("construct_text_family_v2", "construct_reference_v2", "_reference_prefix",
             "_reference_bundles", "reference_board_identity")}
        previous_profiler = sys.getprofile()
        def forbid_workload(frame, event, arg):
            if event == "call" and frame.f_code in blocked_codes:
                raise AssertionError("Profile capture may not construct a workload")
        with _profile_read_only(), \
             patch.object(subprocess, "Popen", side_effect=AssertionError("No process spawn")), \
             patch.object(h.qualification, "_git", side_effect=AssertionError("No Git capture")), \
             patch("benchmark_board.generate_board", side_effect=AssertionError("No board generation")), \
             patch.object(execution.runner, "run_k_p0", side_effect=AssertionError("No solver")), \
             patch.object(execution.runner, "run_k_control", side_effect=AssertionError("No solver")), \
             patch.object(h.store, "StreamWriter", side_effect=AssertionError("No store writer")), \
             patch.object(physical, "require_qualified_profile", wraps=physical.require_qualified_profile) as required:
            try:
                sys.setprofile(forbid_workload)
                first = h._capture_qualified_codec_profile()
                second = h._capture_qualified_codec_profile()
            finally:
                sys.setprofile(previous_profiler)
            self.assertEqual(required.call_count, 2)
            self.assertIs(required.call_args_list[0].args[0], first)
            self.assertIs(required.call_args_list[1].args[0], second)
        self.assertIs(type(first), physical.CodecProfile)
        self.assertTrue(first.qualified)
        self.assertIs(physical.require_qualified_profile(first), first)
        self.assertEqual(first.canonical_bytes, second.canonical_bytes)
        self.assertEqual(first.sha256, second.sha256)
        node = json.loads(first.canonical_bytes)
        self.assertEqual(node["status"], "QUALIFIED")
        self.assertTrue(first.canonical_bytes.isascii())
        self.assertEqual(first.canonical_bytes, json.dumps(node, sort_keys=True, separators=(",", ":"),
                                                         ensure_ascii=True, allow_nan=False).encode("ascii"))
        self.assertEqual(node["constructor_policies"], list(h._constructor_policy_identities()))
        writers = node["writer_sources"]
        self.assertEqual(tuple(v["role"] for v in writers), ("logical_records", "physical", "worker_bundle"))
        directory = Path(physical.__file__).resolve(strict=True).parent
        for fact, filename in zip(writers,
                ("program_k_e2_records.py", "program_k_e2_physical.py", "program_k_e2_execution.py")):
            path = directory / filename
            data = path.read_bytes()
            self.assertEqual(fact, dict(role=fact["role"], path=str(path.resolve(strict=True)),
                                       byte_length=len(data), sha256=sha256(data).hexdigest()))
        runtime = node["runtime"]
        self.assertEqual(runtime["unresolved"], [])
        self.assertEqual(runtime["python_implementation"], platform.python_implementation())
        self.assertEqual(runtime["python_version"], platform.python_version())
        self.assertEqual(runtime["python_abi"], sysconfig.get_config_var("SOABI") or sys.implementation.cache_tag)
        self.assertEqual(runtime["platform"], sys.platform)
        self.assertEqual(runtime["zlib_build_version"], zlib.ZLIB_VERSION)
        self.assertEqual(runtime["zlib_runtime_version"], zlib.ZLIB_RUNTIME_VERSION)
        self.assertEqual((runtime["zlib_build_version"], runtime["zlib_runtime_version"]), ("1.3.1", "1.3.1"))
        self.assertEqual(runtime["zlib_provider_kind"], "builtin-python-runtime")
        self.assertEqual(runtime["zlib_native_owner_role"], "python_dll")
        artifacts = {v["role"]: v for v in runtime["artifacts"]}
        expected_paths = {"interpreter": Path(sys.executable).resolve(strict=True), "python_dll": loaded_dll}
        base = Path(sys._base_executable).resolve(strict=True)
        if base != expected_paths["interpreter"]:
            expected_paths["base_interpreter"] = base
        self.assertEqual(set(artifacts), set(expected_paths))
        self.assertNotIn("zlib_extension", artifacts)
        for role, path in expected_paths.items():
            data = path.read_bytes()
            self.assertEqual(artifacts[role], dict(role=role, path=str(path), byte_length=len(data),
                                                 sha256=sha256(data).hexdigest()))


class V2MaterializationTransactionTests(unittest.TestCase):
    """Bounded constructor-to-RF02 transactions, never a full R0 materializer."""

    @classmethod
    def setUpClass(cls):
        cls.profile = h._capture_qualified_codec_profile()
        cls.work, baseline = _reference_fixture()
        cap = max(len(execution.encode_bundle(value)) for value in baseline.values()) + 1024
        cls.envelope = SyntheticMaterializationTests.envelope(max_payload_bytes=cap)
        logical = _text_logical_bytes(baseline[execution.WorkerKind.PRIMARY], "reference")
        targets = _reference_targets(cls.work,
            logical_reference=logical + h._reference_prefix(7).added_length(7))
        with patch.object(execution, "_materialize_board", side_effect=AssertionError("No board generation")), \
                patch.object(execution.runner, "run_k_p0", side_effect=AssertionError("No solver")), \
                patch.object(execution.runner, "run_k_control", side_effect=AssertionError("No solver")):
            cls.constructed = h.construct_reference_v2(cls.work, targets, cls.profile.sha256,
                max_payload_bytes=cap, envelope=cls.envelope)
        if cls.constructed.rejection_reason is not None:
            raise AssertionError(cls.constructed.rejection_reason)
        cls.wires = cls.constructed.selected_wires
        cls.views = tuple(execution.decode_bundle_view_v2(wire, cls.profile.sha256,
            max_payload_bytes=cap) for wire in cls.wires)
        cls.results = tuple(h._synthetic_v2_operation_result(cls.work, kind, wire,
            cls.profile, cls.envelope, prior_primary_wire=None if index == 0 else cls.wires[0])
            for index, (kind, wire) in enumerate(zip(operational._kinds(cls.work), cls.wires)))
        # Independent existing fixture partition: only PRIMARY.control_maintenance
        # owns Reference; copied K/D premises remain in their respective families.
        cls.actual = {family: tuple(sum(_text_family_metrics(view, family)[axis]
            for view in cls.views) for axis in (0, 1)) for family in readiness.V2_FAMILIES}
        cls.targets = readiness.DualComponentSizes(*(readiness.ComponentSizes(
            *(cls.actual[family][axis] for family in readiness.V2_FAMILIES)) for axis in (0, 1)))
        cls.owned = readiness.V2_FAMILIES

    @contextmanager
    def sink(self, envelope=None):
        with tempfile.TemporaryDirectory() as directory:
            sink = operational._V2EvidenceSink(directory, self.envelope if envelope is None else envelope,
                                                self.profile)
            try:
                yield Path(directory), sink
            finally:
                sink.close()

    def prepare(self, **changes):
        arguments = dict(work=self.work, results=self.results, targets=self.targets,
                         profile=self.profile, envelope=self.envelope, owned_families=self.owned)
        arguments.update(changes)
        return h._prepare_v2_materialization_unit(**arguments)

    def transact(self, sink, ledger=None, **changes):
        arguments = dict(work=self.work, results=self.results, targets=self.targets,
            profile=self.profile, envelope=sink.envelope, owned_families=self.owned,
            ledger=readiness.ProceduralLedger(0) if ledger is None else ledger, sink=sink)
        arguments.update(changes)
        return h._materialize_v2_unit(**arguments)

    @staticmethod
    def snapshot(sink):
        return (sink.byte_length, sink.durable_units, sink.durable_primary_boards,
            sink.event_ordinal, sink.resource_ordinal, tuple((name, writer.path.read_bytes(),
                writer.byte_length, writer.record_count, writer.last_key, writer.dirty)
                for name, writer in sink.writers.items()))

    def excess_targets(self, **excesses):
        return replace(self.targets, physical=replace(self.targets.physical,
            **{family: self.actual[family][0] - amount for family, amount in excesses.items()}))

    def test_actual_q7_constructor_adapter_prepare_exact_persistence_and_rf02_scan(self):
        self.assertEqual(self.constructed.q_lo, 7)
        self.assertLessEqual(len(self.constructed.trials), 8)
        self.assertLess(self.constructed.q_hi, 1000)
        self.assertEqual(len(self.results), 3)
        expected = {name: b"" for name in execution.STREAM_NAMES}
        for result, view in zip(self.results, self.views):
            self.assertEqual(result.receipt.reason, "SYNTHETIC_MATERIALIZATION")
            self.assertEqual((result.receipt.elapsed_ns, result.receipt.exit_code), (0, None))
            self.assertEqual((result.samples, result.observation), ((), None))
            self.assertEqual((result.logical_bytes, result.physical_frame_bytes,
                result.legacy_bundle_bytes, result.wb02_wire_bytes),
                (view.logical_bytes, view.frame_bytes, view.legacy_bytes, view.wire_bytes))
            for row in view.rows:
                expected[row.stream_name] += row.frame_bytes
        before = readiness.ProceduralLedger(0)
        with self.sink() as (root, sink), \
                patch.object(h.store.FramedStreamWriter, "append", side_effect=AssertionError("No re-encoding")):
            result = self.transact(sink, before)
            self.assertIsNot(result.ledger, before)
            self.assertEqual(result.ledger, before)
            self.assertEqual((sink.durable_units, sink.durable_primary_boards), (3, 1))
            self.assertEqual(result.receipts, tuple(value.receipt for value in self.results))
            self.assertFalse(result.ledger.reservation_pending)
            self.assertEqual(result.ledger.reserved_excess, 0)
            for name, raw in expected.items():
                self.assertEqual((root / (name + ".pkf")).read_bytes(), raw, name)
            scanned = {}
            for digest in sink.seal():
                rows = []
                self.assertEqual(h.store.scan_framed_stream(root, digest.name,
                    physical.context_for(digest.name, self.profile.sha256),
                    visit=lambda key, value, logical, length: rows.append((key, logical, length))), digest)
                scanned[digest.name] = rows
            for family in self.owned:
                physical_total = logical_total = 0
                for view in self.views:
                    for row in view.rows:
                        if _text_owned(row.stream_name, view.bundle.kind, family):
                            durable = next(value for value in scanned[row.stream_name] if value[0] == row.key)
                            logical_total += len(durable[1])
                            physical_total += durable[2]
                total = next(value for value in result.family_totals if value.family == family)
                self.assertEqual((total.physical_bytes, total.logical_bytes, total.physical_excess),
                                 (physical_total, logical_total, 0))
            self.assertFalse(list(root.glob("*.jsonl")))
            self.assertFalse((root / "COMPLETE.json").exists())
        self.assertEqual(before, readiness.ProceduralLedger(0))

    def test_preparation_revalidates_all_wires_primary_binding_and_exact_policy_calls(self):
        with patch.object(operational, "_fresh_wb02_context", wraps=operational._fresh_wb02_context) as fresh, \
                patch.object(readiness, "evaluate_family_size", wraps=readiness.evaluate_family_size) as evaluate, \
                patch.object(readiness, "unit_physical_excess", wraps=readiness.unit_physical_excess) as excess:
            prepared = self.prepare()
        top = [call for call in fresh.call_args_list if "prior_primary_wire" in call.kwargs]
        self.assertEqual(len(top), 3)
        for index, call in enumerate(top):
            self.assertIs(call.args[0], self.wires[index])
            self.assertIs(call.kwargs["prior_primary_wire"], None if index == 0 else self.wires[0])
        self.assertEqual([call.args for call in evaluate.call_args_list], [
            (family, *self.actual[family], *self.actual[family]) for family in self.owned])
        excess.assert_called_once_with(prepared.family_evaluations)
        self.assertEqual(prepared.physical_family_bytes,
                         tuple((family, self.actual[family][0]) for family in self.owned))
        self.assertEqual(prepared.logical_family_bytes,
                         tuple((family, self.actual[family][1]) for family in self.owned))
        self.assertEqual(prepared.physical_excess, 0)
        self.assertFalse(hasattr(prepared, "__dict__"))
        self.assertTrue({"context", "validated", "token", "path", "trusted"}.isdisjoint(
            field.name for field in fields(prepared)))
        with self.assertRaises(FrozenInstanceError):
            prepared.physical_excess = 1
        import pickle
        with self.assertRaises((TypeError, ValueError)):
            pickle.dumps(prepared)

    def test_copied_reference_is_owned_once_and_exact_kd_frames_remain_charged(self):
        targets = self.excess_targets(reference=3, k_control=2, determinism=1)
        with self.sink() as (_, sink), \
                patch.object(readiness, "unit_physical_excess", wraps=readiness.unit_physical_excess) as excess:
            result = self.transact(sink, readiness.ProceduralLedger(6), targets=targets)
        self.assertEqual(result.ledger.committed_excess, 6)
        for call in excess.call_args_list:
            self.assertEqual([value.family for value in call.args[0]].count("reference"), 1)
        reference = next(value for value in result.family_totals if value.family == "reference")
        primary_rows = tuple(row for row in self.views[0].rows if row.stream_name == "control_maintenance")
        self.assertEqual(reference.physical_bytes, sum(row.frame_length for row in primary_rows))
        copied = [row for view in self.views[1:] for row in view.rows if row.stream_name == "control_maintenance"]
        self.assertTrue(copied)
        self.assertEqual({row.logical_bytes for row in copied}, {row.logical_bytes for row in primary_rows})
        for family, view in (("determinism", self.views[1]), ("k_control", self.views[2])):
            value = next(value for value in result.family_totals if value.family == family)
            self.assertEqual(value.physical_bytes, _text_family_metrics(view, family)[0])

    def test_unknown_duplicate_missing_and_unscheduled_ownership_rejects(self):
        cases = ((), list(self.owned), self.owned + ("unknown",), self.owned + ("reference",),
                 self.owned[:-1], self.owned[::-1])
        with patch.object(readiness, "reserve_procedural_unit", side_effect=AssertionError("No reservation")) as reserve:
            for owned in cases:
                with self.subTest(owned=owned), self.assertRaises(ValueError):
                    self.prepare(owned_families=owned)
            with self.assertRaises(ValueError):
                self.prepare(work=replace(self.work, k_control_selected=False))
        reserve.assert_not_called()

    def test_zero_oracle_cannot_be_claimed_from_coverage_without_audit_bytes(self):
        work, bundles = _text_fixture(oracle=0)
        wires = tuple(execution.encode_bundle_v2(bundles[kind], self.profile.sha256,
            max_payload_bytes=self.envelope.max_payload_bytes) for kind in operational._kinds(work))
        results = tuple(h._synthetic_v2_operation_result(work, kind, wire, self.profile, self.envelope,
            prior_primary_wire=None if index == 0 else wires[0])
            for index, (kind, wire) in enumerate(zip(operational._kinds(work), wires)))
        targets = replace(self.targets,
            physical=replace(self.targets.physical, oracle_primary=0, oracle_repeat=0),
            logical=replace(self.targets.logical, oracle_primary=0, oracle_repeat=0))
        with self.assertRaises(ValueError):
            self.prepare(work=work, results=results, targets=targets)

    def test_result_shapes_status_scalars_profile_and_work_cannot_supply_authority(self):
        missing = replace(self.results[0], receipt=replace(self.results[0].receipt,
            status=records.AuditStatus.INCOMPLETE, reason="CASE_TIMEOUT"), wire=None,
            logical_bytes=0, physical_frame_bytes=0, legacy_bundle_bytes=0, wb02_wire_bytes=0)
        cases = [list(self.results), self.results[::-1], self.results[:-1],
                 (missing,) + self.results[1:],
                 (replace(self.results[0], codec_profile_sha256=b"x" * 32),) + self.results[1:]]
        for name in ("logical_bytes", "physical_frame_bytes", "legacy_bundle_bytes", "wb02_wire_bytes"):
            bad = replace(self.results[0])
            object.__setattr__(bad, name, getattr(bad, name) + 1)
            cases.append((bad,) + self.results[1:])
        for results in cases:
            with self.subTest(results_type=type(results)), self.assertRaises(ValueError):
                self.prepare(results=results)
        for changes in ({"profile": self.profile.sha256}, {"work": replace(self.work, position=8)}):
            with self.assertRaises(ValueError):
                self.prepare(**changes)

    def test_wrong_copied_primary_premise_is_rejected_by_fresh_validation(self):
        other = h._reference_bundles(self.work, h._reference_prefix(0), 0)[0]
        wire = execution.encode_bundle_v2(other, self.profile.sha256,
                                           max_payload_bytes=self.envelope.max_payload_bytes)
        result = h._synthetic_v2_operation_result(self.work, execution.WorkerKind.PRIMARY,
                                                  wire, self.profile, self.envelope)
        with self.assertRaises(ValueError):
            self.prepare(results=(result,) + self.results[1:])

    def test_synthetic_adapter_requires_explicit_samples_and_fresh_scalar_observations(self):
        sample = records.ResourceSampleRecord(operational._unit_id(self.work.position,
            execution.WorkerKind.PRIMARY), records.ProcessRole.COMBINED, 0, 5, 5,
            "synthetic:fixture", 0, records.MemoryMethod.PRIVATE_BYTES)
        with patch.object(operational, "_fresh_wb02_context", wraps=operational._fresh_wb02_context) as fresh:
            result = h._synthetic_v2_operation_result(self.work, execution.WorkerKind.PRIMARY,
                self.wires[0], self.profile, self.envelope, samples=(sample,))
        fresh.assert_called_once()
        self.assertEqual(result.samples, (sample,))
        self.assertIs(result.wire, self.wires[0])
        for wire in (bytearray(self.wires[0]), self.wires[0][:-1]):
            with self.assertRaises(ValueError):
                h._synthetic_v2_operation_result(self.work, execution.WorkerKind.PRIMARY,
                                                  wire, self.profile, self.envelope)

    def test_reserve_precedes_all_admission_and_final_checkpoint_precedes_commit(self):
        events = []
        reserve, commit = readiness.reserve_procedural_unit, readiness.commit_procedural_unit
        checkpoint = h.store.FramedStreamWriter.checkpoint
        original = readiness.ProceduralLedger(3)
        with self.sink() as (_, sink):
            admit = sink.admit
            def reserved(ledger, evaluations):
                events.append("reserve")
                return reserve(ledger, evaluations)
            def admitted(*args, **kwargs):
                events.append("admit")
                return admit(*args, **kwargs)
            def durable(writer):
                value = checkpoint(writer)
                events.append("durable")
                return value
            def committed(ledger):
                events.append("commit")
                self.assertEqual((sink.durable_units, sink.durable_primary_boards), (3, 1))
                self.assertTrue(all(not writer.dirty for writer in sink.writers.values()))
                return commit(ledger)
            with patch.object(readiness, "reserve_procedural_unit", side_effect=reserved), \
                    patch.object(sink, "admit", side_effect=admitted), \
                    patch.object(h.store.FramedStreamWriter, "checkpoint", new=durable), \
                    patch.object(readiness, "commit_procedural_unit", side_effect=committed):
                result = self.transact(sink, original, targets=self.excess_targets(reference=3))
        self.assertEqual((events[0], events[-1]), ("reserve", "commit"))
        self.assertEqual(events.count("admit"), 3)
        self.assertEqual(events[-2], "durable")
        self.assertEqual(result.ledger, readiness.ProceduralLedger(3, 3))
        self.assertEqual(original, readiness.ProceduralLedger(3))

    def test_zero_and_remaining_budget_edges_are_prewrite_and_immutable(self):
        cases = ((0, 0, 0, True), (0, 0, 1, False), (10, 7, 3, True), (10, 7, 4, False))
        for capacity, used, excess, succeeds in cases:
            ledger = readiness.ProceduralLedger(capacity, used)
            with self.subTest(capacity=capacity, used=used, excess=excess), self.sink() as (_, sink), \
                    patch.object(sink, "admit", wraps=sink.admit) as admit, \
                    patch.object(readiness, "commit_procedural_unit", wraps=readiness.commit_procedural_unit) as commit:
                before = self.snapshot(sink)
                if succeeds:
                    result = self.transact(sink, ledger, targets=self.excess_targets(reference=excess))
                    self.assertEqual(result.ledger.committed_excess, used + excess)
                    self.assertIsNot(result.ledger, ledger)
                    self.assertEqual(commit.call_count, 1)
                else:
                    with self.assertRaisesRegex(readiness.ReadinessError, "^SYNTHETIC_PROCEDURAL_EXCESS_BUDGET$"):
                        self.transact(sink, ledger, targets=self.excess_targets(reference=excess))
                    admit.assert_not_called()
                    commit.assert_not_called()
                    self.assertEqual(self.snapshot(sink), before)
                self.assertEqual(ledger, readiness.ProceduralLedger(capacity, used))

    def test_ineligible_family_shortfalls_never_reserve_or_cross_credit(self):
        base = self.excess_targets(reference=3)
        cases = ((replace(base, physical=replace(base.physical, primary=self.actual["primary"][0] + 1)),
                  "SYNTHETIC_PHYSICAL_MINIMUM_SHORTFALL"),
                 (replace(base, logical=replace(base.logical, reference=self.actual["reference"][1] + 1)),
                  "SYNTHETIC_LOGICAL_MINIMUM_SHORTFALL"))
        for targets, reason in cases:
            ledger = readiness.ProceduralLedger(10)
            with self.subTest(reason=reason), self.sink() as (_, sink), \
                    patch.object(readiness, "reserve_procedural_unit", wraps=readiness.reserve_procedural_unit) as reserve, \
                    patch.object(sink, "admit", wraps=sink.admit) as admit, \
                    patch.object(readiness, "commit_procedural_unit", wraps=readiness.commit_procedural_unit) as commit:
                before = self.snapshot(sink)
                with self.assertRaisesRegex(ValueError, reason):
                    self.transact(sink, ledger, targets=targets)
                reserve.assert_not_called()
                admit.assert_not_called()
                commit.assert_not_called()
                self.assertEqual(self.snapshot(sink), before)
                self.assertEqual(ledger, readiness.ProceduralLedger(10))

    def test_text_window_reference_exception_and_unused_window_have_no_budget_credit(self):
        accepted = readiness.evaluate_family_size("primary", 10, 10, 4106, 10)
        rejected = readiness.evaluate_family_size("primary", 10, 10, 4107, 10)
        reference = readiness.evaluate_family_size("reference", 10, 10, 5010, 10)
        self.assertTrue(accepted.eligible and reference.eligible)
        self.assertEqual(rejected.rejection_reason, "SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT")
        self.assertEqual(readiness.unit_physical_excess((accepted, reference)), 9096)
        ledger = readiness.ProceduralLedger(9096)
        with self.assertRaisesRegex(readiness.ReadinessError, "SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT"):
            readiness.reserve_procedural_unit(ledger, (rejected, reference))
        self.assertEqual(ledger, readiness.ProceduralLedger(9096))
        spare_window = readiness.evaluate_family_size("primary", 10, 10, 10, 10**9)
        one = readiness.evaluate_family_size("reference", 10, 10, 11, 10)
        with self.assertRaisesRegex(readiness.ReadinessError, "SYNTHETIC_PROCEDURAL_EXCESS_BUDGET"):
            readiness.reserve_procedural_unit(readiness.ProceduralLedger(0), (spare_window, one))

    def test_ledger_initializer_binds_existing_capacity_and_negative_budget_fails_before_sink(self):
        counts = (10000, 256, 128, 1, 256, 256)  # Supplied scalar policy fixture, no workload loop.
        available = identity.MAX_ARCHIVE_BYTES - identity.FIXED_REPORT_RECEIPT_ALLOWANCE
        physical_targets = readiness.ComponentSizes(1, 1, 1, available - 10896, 1, 1)
        targets = readiness.DualComponentSizes(physical_targets, physical_targets)
        with patch.object(readiness, "procedural_excess_capacity", wraps=readiness.procedural_excess_capacity) as capacity:
            ledger = h._new_v2_materialization_ledger(targets, counts)
        capacity.assert_called_once_with(targets.physical, counts)
        self.assertEqual(ledger, readiness.ProceduralLedger(0))
        changed_logical = replace(targets, logical=replace(targets.logical, primary=10**9))
        self.assertEqual(h._new_v2_materialization_ledger(changed_logical, counts), ledger)
        negative = replace(targets, physical=replace(physical_targets,
                                                     oracle_repeat=physical_targets.oracle_repeat + 1))
        with patch.object(operational._V2EvidenceSink, "admit", side_effect=AssertionError("No persistence")) as admit, \
                self.assertRaisesRegex(readiness.ReadinessError, "SYNTHETIC_PROCEDURAL_FIXED_RESERVATION_INFEASIBLE"):
            h._new_v2_materialization_ledger(negative, counts)
        admit.assert_not_called()

    def test_append_fsync_and_primary_progress_failures_abort_without_commit_or_totals(self):
        original_append = h.store.FramedStreamWriter.append_frame
        original_checkpoint = h.store.FramedStreamWriter.checkpoint
        for case in ("append", "checkpoint", "progress"):
            ledger = readiness.ProceduralLedger(3)
            initial = tuple(h._V2FamilyTotal(name, 0, 0, 0) for name in self.owned)
            state = dict(fired=False)
            def append(writer, key, logical, frame):
                value = original_append(writer, key, logical, frame)
                progress = (writer.stream_name == "operations"
                    and records.decode(logical).event_kind is records.EventKind.PROGRESS)
                if not state["fired"] and ((case == "append" and writer.stream_name in execution.STREAM_NAMES)
                                           or (case == "progress" and progress)):
                    state["fired"] = True
                    raise h.store.StoreError("SLICE1L_EXACT_APPEND_FAILURE")
                return value
            def checkpoint(writer):
                if case == "checkpoint" and not state["fired"]:
                    state["fired"] = True
                    raise h.store.StoreError("SLICE1L_CHECKPOINT_FAILURE")
                return original_checkpoint(writer)
            with self.subTest(case=case), self.sink() as (root, sink), \
                    patch.object(readiness, "reserve_procedural_unit", wraps=readiness.reserve_procedural_unit) as reserve, \
                    patch.object(readiness, "commit_procedural_unit", wraps=readiness.commit_procedural_unit) as commit:
                with patch.object(h.store.FramedStreamWriter, "append_frame", new=append), \
                        patch.object(h.store.FramedStreamWriter, "checkpoint", new=checkpoint), \
                        self.assertRaisesRegex(h.store.StoreError, "SLICE1L_"):
                    self.transact(sink, ledger, targets=self.excess_targets(reference=3), family_totals=initial)
                self.assertEqual(reserve.call_count, 1)
                commit.assert_not_called()
                self.assertTrue(state["fired"] and sink.poisoned)
                self.assertEqual((sink.durable_units, sink.durable_primary_boards), (0, 0))
                self.assertEqual(ledger, readiness.ProceduralLedger(3))
                self.assertTrue(all(value.physical_bytes == value.logical_bytes == value.physical_excess == 0
                                    for value in initial))
                sink.close()
                retained = {path.name: path.read_bytes() for path in root.glob("*.pkf")}
                self.assertGreater(sum(map(len, retained.values())), 0)
                with self.assertRaises(ValueError):
                    sink.seal()
                sink.close()
                self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.pkf")}, retained)

    def test_archive_cap_refusal_after_reserve_is_distinct_unpoisoned_and_stops_workflow(self):
        # A bounded existing support prefix makes the archive cap independently
        # reachable while preserving the accepted archive >= payload relation.
        text = "".join(sha256(str(index).encode("ascii")).hexdigest() for index in range(256))
        with self.sink() as (_, sink):
            while sink.byte_length < self.envelope.max_payload_bytes:
                ordinal = sink.event_ordinal
                sink.writers["operations"].append((ordinal,), records.OperationEventRecord(
                    records.Phase.EXECUTION, "slice1l-prefix:" + text, records.EventKind.START,
                    0, ordinal, records.OperationStatus.RUNNING))
                sink.event_ordinal += 1
            sink.checkpoint()
            sink.envelope = replace(self.envelope, archive_cap_bytes=sink.byte_length)
            before = self.snapshot(sink)
            ledger = readiness.ProceduralLedger(0)
            with patch.object(readiness, "reserve_procedural_unit", wraps=readiness.reserve_procedural_unit) as reserve, \
                    patch.object(sink, "admit", wraps=sink.admit) as admit, \
                    patch.object(readiness, "commit_procedural_unit", wraps=readiness.commit_procedural_unit) as commit, \
                    self.assertRaisesRegex(ValueError, "ARCHIVE_CAP"):
                self.transact(sink, ledger)
            self.assertEqual(reserve.call_count, 1)
            self.assertEqual(admit.call_count, 1)
            commit.assert_not_called()
            self.assertEqual(self.snapshot(sink), before)
            self.assertFalse(sink.poisoned)
            self.assertEqual(ledger, readiness.ProceduralLedger(0))

    def test_later_unit_failure_retains_durable_primary_prefix_without_ledger_update(self):
        original_append = h.store.FramedStreamWriter.append_frame
        first_downstream = self.views[1].rows[0]
        prefix = {}
        ledger = readiness.ProceduralLedger(3)
        with self.sink() as (root, sink):
            original_admit = sink.admit
            def admit(work, result, *, prior_primary_wire=None):
                receipt = original_admit(work, result, prior_primary_wire=prior_primary_wire)
                if result.receipt.kind is execution.WorkerKind.PRIMARY:
                    prefix.update({name: writer.path.read_bytes() for name, writer in sink.writers.items()})
                return receipt
            def append(writer, key, logical, frame):
                value = original_append(writer, key, logical, frame)
                if writer.stream_name == first_downstream.stream_name and key == first_downstream.key:
                    raise h.store.StoreError("SLICE1L_LATER_UNIT_FAILURE")
                return value
            with patch.object(sink, "admit", side_effect=admit), \
                    patch.object(h.store.FramedStreamWriter, "append_frame", new=append), \
                    patch.object(readiness, "commit_procedural_unit", wraps=readiness.commit_procedural_unit) as commit, \
                    self.assertRaisesRegex(h.store.StoreError, "SLICE1L_LATER_UNIT_FAILURE"):
                self.transact(sink, ledger, targets=self.excess_targets(reference=3))
            commit.assert_not_called()
            self.assertTrue(prefix and sink.poisoned)
            self.assertEqual((sink.durable_units, sink.durable_primary_boards), (1, 1))
            self.assertEqual(ledger, readiness.ProceduralLedger(3))
            sink.close()
            retained = {path.stem: path.read_bytes() for path in root.glob("*.pkf")}
            self.assertTrue(all(retained[name].startswith(raw) for name, raw in prefix.items()))
            self.assertGreater(sum(map(len, retained.values())), sum(map(len, prefix.values())))

    def test_nonpass_replaced_receipts_and_forged_durability_never_commit(self):
        for case in ("fail", "incomplete", "receipt_copy", "no_durability"):
            with self.subTest(case=case), self.sink() as (_, sink), \
                    patch.object(readiness, "commit_procedural_unit", wraps=readiness.commit_procedural_unit) as commit:
                def admit(work, result, *, prior_primary_wire=None):
                    if case in ("fail", "incomplete"):
                        return replace(result.receipt, status=records.AuditStatus.FAIL if case == "fail"
                                       else records.AuditStatus.INCOMPLETE, reason="SLICE1L_REFUSAL")
                    if case == "receipt_copy":
                        return replace(result.receipt)
                    return result.receipt
                with patch.object(sink, "admit", side_effect=admit), self.assertRaises(ValueError):
                    self.transact(sink)
                commit.assert_not_called()
                self.assertEqual(sink.byte_length, 0)

    def test_totals_accumulate_immutably_only_after_durable_success(self):
        initial = tuple(h._V2FamilyTotal(name, 100, 200, 0) for name in self.owned)
        with self.sink() as (_, sink):
            result = self.transact(sink, readiness.ProceduralLedger(2),
                                   targets=self.excess_targets(reference=2), family_totals=initial)
        self.assertEqual(result.family_totals, tuple(h._V2FamilyTotal(name,
            100 + self.actual[name][0], 200 + self.actual[name][1], 2 if name == "reference" else 0)
            for name in self.owned))
        self.assertTrue(all((value.physical_bytes, value.logical_bytes, value.physical_excess) == (100, 200, 0)
                            for value in initial))
        for value in (result, *result.family_totals):
            self.assertFalse(hasattr(value, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)

    def test_complete_scalar_totals_reconcile_actual_transaction_excess_and_reject_tampering(self):
        counts = (10000, 256, 128, 1, 256, 256)  # Aggregate inputs only; no 10000-unit construction.
        targets = self.excess_targets(reference=3)
        ledger = h._new_v2_materialization_ledger(targets, counts)
        with self.sink() as (_, sink):
            transaction = self.transact(sink, ledger, targets=targets)
        # Complete pure aggregate fixture: remaining units contribute their exact
        # supplied minima; one actual durable unit contributes observed RF02 sizes.
        totals = tuple(h._V2FamilyTotal(value.family,
            value.physical_bytes + (count - 1) * getattr(targets.physical, value.family),
            value.logical_bytes + (count - 1) * getattr(targets.logical, value.family), value.physical_excess)
            for value, count in zip(transaction.family_totals, counts))
        with patch.object(readiness, "reconcile_procedural_excess", wraps=readiness.reconcile_procedural_excess) as reconcile:
            self.assertEqual(h._reconcile_v2_materialization_totals(targets, counts, totals, transaction.ledger), 3)
        reconcile.assert_called_once_with(targets.physical, counts,
            readiness.ComponentSizes(*(value.physical_bytes for value in totals)), transaction.ledger)
        cases = (totals[:-1], (replace(totals[0], physical_bytes=totals[0].physical_bytes + 1),) + totals[1:],
                 (replace(totals[0], physical_bytes=counts[0] * targets.physical.primary - 1),) + totals[1:])
        for bad in cases:
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                h._reconcile_v2_materialization_totals(targets, counts, bad, transaction.ledger)
        logical_changed = tuple(replace(value, logical_bytes=value.logical_bytes + 10**9) for value in totals)
        self.assertEqual(h._reconcile_v2_materialization_totals(targets, counts, logical_changed, transaction.ledger), 3)
        with self.assertRaisesRegex(ValueError, "PROCEDURAL_CAPACITY_BINDING"):
            h._reconcile_v2_materialization_totals(targets, counts, totals,
                replace(transaction.ledger, capacity=transaction.ledger.capacity + 1))

    def test_zero_family_nonzero_totals_fail_accepted_reconciliation(self):
        counts = (10000, 256, 128, 0, 256, 256)
        basis = readiness.ComponentSizes(1, 1, 0, 0, 1, 1)
        targets = readiness.DualComponentSizes(basis, basis)
        ledger = h._new_v2_materialization_ledger(targets, counts)
        totals = tuple(h._V2FamilyTotal(name, count * getattr(basis, name),
            count * getattr(basis, name), 0) for name, count in zip(self.owned, counts))
        self.assertEqual(h._reconcile_v2_materialization_totals(targets, counts, totals, ledger), 0)
        bad = tuple(replace(value, physical_bytes=1) if value.family == "oracle_primary" else value for value in totals)
        with self.assertRaisesRegex(ValueError, "ZERO_FAMILY_REQUIRES_EXACT_TOTAL_ZERO"):
            h._reconcile_v2_materialization_totals(targets, counts, bad, ledger)


class V2TransactionV1IsolationTests(unittest.TestCase):
    def test_private_transaction_facts_are_not_historical_serialization_authority(self):
        from experiments import program_k_e2_r0_evidence as evidence
        for cls in (h._V2PreparedUnit, h._V2FamilyTotal, h._V2MaterializedUnit):
            self.assertNotIn(cls, evidence._FACT_TYPES.values())
            self.assertNotIn(cls.__name__, evidence._FACT_TYPES)
            with self.assertRaisesRegex(h.HarnessError, "UNSUPPORTED_METADATA_FACT"):
                h._fact_read({"fact": cls.__name__, "fields": {}})

    def test_historical_bundle_sizing_materialization_and_public_sources_stay_v1(self):
        names = ("_prepare_v2_materialization_unit", "_synthetic_v2_operation_result",
                 "_new_v2_materialization_ledger", "_materialize_v2_unit", "_reconcile_v2_materialization_totals")
        fixture = SyntheticMaterializationTests()
        plan = fixture.plan()
        with tempfile.TemporaryDirectory() as directory:
            seal = fixture._identity(directory, plan)
            with _EvidenceExitStack() as stack:
                for name in names:
                    stack.enter_context(patch.object(h, name, side_effect=AssertionError("No V2 historical caller")))
                stack.enter_context(patch.object(operational.harness, "_coordinator_private_bytes", return_value=100))
                bundle = h.build_synthetic_bundle(plan[0], execution.WorkerKind.PRIMARY,
                    readiness.ComponentSizes(1, 1, 1, 1, 1, 1), max_payload_bytes=67108864)
                self.assertTrue(h.synthetic_bundle_family_bytes(bundle))
                result = h.materialize_synthetic(plan, readiness.ComponentSizes(1, 1, 1, 1, 1, 1),
                    fixture.envelope(), directory, seal)
            self.assertTrue(result.readback_complete and result.cleanup_complete)
            self.assertTrue(list(Path(directory).glob("*.jsonl")))
            self.assertFalse(list(Path(directory).glob("*.pkf")))
        for function in (operational.coordinate, h.materialize_synthetic, h.build_synthetic_bundle,
                         h.synthetic_bundle_family_bytes):
            source = inspect.getsource(function)
            self.assertFalse(any(name in source for name in names))


class V2SyntheticMaterializerTests(unittest.TestCase):
    """Four real units only; complete-count policy checks use arithmetic padding."""

    _full_counts = (10000, 256, 128, 4, 256, 506)

    @staticmethod
    def source_plan():
        runtime = records.RuntimeIdentity("FixturePython", "0", "fixture-os",
                                          "fixture-platform", "fixture-arch", None)
        return tuple(execution.BoardWork(position,
            h.synthetic_board_identity(2_000_000_080_000 + position),
            bytes.fromhex(identity.PROTOCOL_SHA256), "slice1m-bounded-fixture",
            oracle, determinism, k_control, runtime)
            for position, (oracle, determinism, k_control) in enumerate(
                ((False, False, False), (True, False, False),
                 (False, False, True), (True, True, False))))

    @staticmethod
    def counts(plan):
        return (len(plan), sum(work.k_control_selected for work in plan),
            sum(work.oracle_b_selected for work in plan),
            sum(work.oracle_b_selected and work.determinism_selected for work in plan),
            sum(work.determinism_selected for work in plan),
            sum(work.k_control_selected or work.determinism_selected for work in plan))

    @staticmethod
    @contextmanager
    def forbidden_workloads():
        import socket
        with _EvidenceExitStack() as stack:
            for owner, name in ((execution, "_materialize_board"),
                    (execution, "MinesweeperEngine"),
                    (execution.runner, "run_k_p0"), (execution.runner, "run_k_control"),
                    (readiness, "search_synthetic_corpus"), (readiness, "target_counts"),
                    (h.analysis, "_shared_bootstrap"), (socket, "create_connection"),
                    (socket.socket, "connect")):
                stack.enter_context(patch.object(owner, name,
                    side_effect=AssertionError("No Slice 1M research workload")))
            stack.enter_context(patch("benchmark_board.generate_board",
                                      side_effect=AssertionError("No benchmark generation")))
            yield

    @classmethod
    def padded_reconciliation(cls, targets, counts, totals, ledger):
        # Only this test adapter adds unmaterialized minima. Actual four-unit
        # counts and exact durable totals are independently asserted below.
        padded = tuple(replace(value,
            physical_bytes=value.physical_bytes + (full - small) * getattr(targets.physical, value.family),
            logical_bytes=value.logical_bytes + (full - small) * getattr(targets.logical, value.family))
            for value, full, small in zip(totals, cls._full_counts, counts))
        return cls._real_reconcile(targets, cls._full_counts, padded, ledger)

    @classmethod
    def setUpClass(cls):
        cls.profile = h._capture_qualified_codec_profile()
        cls.plan = cls.source_plan()
        cls.materialization_plan = h._v2_materialization_plan(cls.plan)
        cls._real_reconcile = staticmethod(h._reconcile_v2_materialization_totals)
        provisional = readiness.DualComponentSizes(
            readiness.ComponentSizes(1, 1, 1, 1, 1, 1),
            readiness.ComponentSizes(1, 1, 1, 1, 1, 1))
        initial_envelope = SyntheticMaterializationTests.envelope(max_payload_bytes=1048576)
        baselines = []
        with cls.forbidden_workloads():
            for work in cls.materialization_plan:
                if work.k_control_selected or work.determinism_selected:
                    baselines.extend(h._reference_bundles(work, h._reference_prefix(0), 0))
                else:
                    baselines.append(h._build_primary_v2_baseline(
                        work, provisional, cls.profile, initial_envelope)[0])
        cap = max(execution.legacy_bundle_size(bundle) for bundle in baselines) + 4096
        cls.envelope = replace(initial_envelope, max_payload_bytes=cap)
        views = tuple(execution.decode_bundle_view_v2(
            execution.encode_bundle_v2(bundle, cls.profile.sha256, max_payload_bytes=cap),
            cls.profile.sha256, max_payload_bytes=cap) for bundle in baselines)
        bases = tuple(readiness.ComponentSizes(*(max(
            _text_family_metrics(view, family)[axis] for view in views)
            for family in readiness.V2_FAMILIES)) for axis in (0, 1))
        # Calibrate Oracle floors from the canonical h=0 text at the shared
        # logical minimum. The original prose's compressed size can fall just
        # outside the accepted eight-trial schedule's evaluated set.
        oracle_physical, cls.oracle_h0 = {}, {}
        for family in ("oracle_primary", "oracle_repeat"):
            sizes = []
            for bundle, view in zip(baselines, views):
                if not _text_family_metrics(view, family)[1]:
                    continue
                fixed = _text_with_literal(bundle, family, "SYNTHETIC_NON_EVIDENCE|L:|H:")
                ell = (max(0, getattr(bases[1], family) - _text_logical_bytes(fixed, family)) + 3) // 4
                candidate = _text_with_literal(fixed, family,
                    "SYNTHETIC_NON_EVIDENCE|L:" + "x" * ell + "|H:")
                candidate_view = execution.decode_bundle_view_v2(
                    execution.encode_bundle_v2(candidate, cls.profile.sha256, max_payload_bytes=cap),
                    cls.profile.sha256, max_payload_bytes=cap)
                measured = _text_family_metrics(candidate_view, family)
                cls.oracle_h0[bundle.work_position, family] = measured
                sizes.append(measured)
            target = min(physical_bytes for physical_bytes, _ in sizes)
            if not all(target <= physical_bytes <= target + 4096
                       and logical_bytes >= getattr(bases[1], family)
                       for physical_bytes, logical_bytes in sizes):
                raise AssertionError(("No common bounded Oracle h=0 window", family, sizes))
            oracle_physical[family] = target
        cls.targets = readiness.DualComponentSizes(
            replace(bases[0], reference=1, **oracle_physical),
            replace(bases[1], reference=bases[1].reference + h._reference_prefix(7).added_length(7)))
        # Prove the real Reference calls cannot accidentally enter the large
        # diagnostic domain, without changing the accepted constructor scheduler.
        cls.reference_bounds = {}
        for work in cls.materialization_plan:
            if work.k_control_selected or work.determinism_selected:
                prefix = h._reference_prefix(cap // 26)
                bundle_group = tuple(bundle for bundle in baselines if bundle.work_position == work.position)
                low, high = h._reference_q_bounds(bundle_group, cls.targets, prefix, cap)
                if high is None or not 0 <= low <= high < 10000:
                    raise AssertionError(("Unbounded Slice 1M fixture", low, high))
                cls.reference_bounds[work.position] = (low, high)
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        cls.progress, cls.constructor_calls = [], []
        cls.constructed, cls.reference_results, cls.text_results, cls.transactions = {}, {}, {}, []
        cls.text_priors = {}
        cls.reconciliation_calls = []
        reference = h.construct_reference_v2
        text = h.construct_text_family_v2
        construct = h._construct_v2_materialization_work
        transact = h._materialize_v2_unit
        def reference_call(work, *args, **kwargs):
            if not callable(kwargs.get("_check")):
                raise AssertionError("Reference constructor must receive the materialization monitor")
            cls.constructor_calls.append((work.position, "reference"))
            result = reference(work, *args, **kwargs)
            cls.reference_results[work.position] = result
            return result
        def text_call(work, bundle, family, *args, **kwargs):
            if not callable(kwargs.get("_check")):
                raise AssertionError("Text constructor must receive the materialization monitor")
            cls.constructor_calls.append((work.position, family))
            cls.text_priors[work.position, family] = kwargs.get("prior_primary_wire")
            result = text(work, bundle, family, *args, **kwargs)
            cls.text_results[work.position, family] = result
            return result
        def construct_call(work, *args, **kwargs):
            result = construct(work, *args, **kwargs)
            cls.constructed[work.position] = result
            return result
        def transaction_call(*args, **kwargs):
            result = transact(*args, **kwargs)
            cls.transactions.append((args, kwargs, result))
            return result
        def reconcile(*args):
            cls.reconciliation_calls.append(args)
            return cls.padded_reconciliation(*args)
        with cls.forbidden_workloads(), \
                patch.object(operational.harness, "_coordinator_private_bytes", return_value=100), \
                patch.object(h, "construct_reference_v2", side_effect=reference_call), \
                patch.object(h, "construct_text_family_v2", side_effect=text_call), \
                patch.object(h, "_construct_v2_materialization_work", side_effect=construct_call), \
                patch.object(h, "_materialize_v2_unit", side_effect=transaction_call), \
                patch.object(h, "_reconcile_v2_materialization_totals", side_effect=reconcile):
            cls.result = cls.run_lower(cls.root, progress=lambda done, total: cls.progress.append((done, total)))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    @classmethod
    def run_lower(cls, root, *, plan=None, targets=None, envelope=None, **kwargs):
        plan = cls.plan if plan is None else plan
        targets = cls.targets if targets is None else targets
        return h._materialize_v2_plan(plan, h._v2_materialization_plan(plan), targets,
            cls.profile, cls.envelope if envelope is None else envelope, root,
            cls.counts(plan), h._new_v2_materialization_ledger(targets, cls._full_counts),
            readiness.minimum_archive_preflight(targets.physical, cls._full_counts, 0), **kwargs)

    @contextmanager
    def cached_lower(self):
        with self.forbidden_workloads(), \
                patch.object(operational.harness, "_coordinator_private_bytes", return_value=100), \
                patch.object(h, "_construct_v2_materialization_work",
                    side_effect=lambda work, *args, **kwargs: self.constructed[work.position]), \
                patch.object(h, "_reconcile_v2_materialization_totals",
                    side_effect=self.padded_reconciliation):
            yield

    def scan(self, root, name):
        values = []
        digest = h.store.scan_framed_stream(root, name, physical.context_for(name, self.profile.sha256),
            visit=lambda key, value, logical, length: values.append((key, value, logical, length)))
        return digest, values

    def test_real_four_work_mapping_constructor_order_and_final_primary_binding(self):
        self.assertEqual(self.counts(self.plan), (4, 1, 2, 1, 1, 2))
        self.assertEqual(self.result.source_plan, self.plan)
        self.assertEqual(self.result.materialization_plan, self.materialization_plan)
        for source, derived in zip(self.plan, self.materialization_plan):
            self.assertEqual(source.board, h.synthetic_board_identity(source.board.game_index))
            expected = (h.reference_board_identity(source.board.game_index)
                        if source.k_control_selected or source.determinism_selected else source.board)
            self.assertEqual(derived.board, expected)
            self.assertEqual(replace(derived, board=source.board), source)
        self.assertEqual(self.constructor_calls, [(0, "primary"), (1, "primary"), (1, "oracle_primary"),
            (2, "reference"), (2, "primary"), (2, "k_control"), (3, "reference"),
            (3, "primary"), (3, "oracle_primary"), (3, "determinism"), (3, "oracle_repeat")])
        for key, measured in self.oracle_h0.items():
            low = self.text_results[key].trials[0]
            self.assertEqual((low.h, low.actual_physical_bytes, low.actual_logical_bytes), (0, *measured))
            self.assertTrue(low.eligible)
        for work in self.materialization_plan:
            final = self.constructed[work.position]
            for kind, wire in zip(operational._kinds(work), final.wires):
                context = operational._fresh_wb02_context(wire, work, kind, self.profile.sha256,
                    self.envelope, prior_primary_wire=None if kind is execution.WorkerKind.PRIMARY else final.wires[0])
                self.assertEqual(context.bundle.work_position, work.position)
            if work.position in self.reference_results:
                original = self.reference_results[work.position]
                self.assertEqual((original.q_lo, original.q_hi), self.reference_bounds[work.position])
                self.assertLessEqual(len(original.trials), 8)
                self.assertIsNot(final.wires[0], original.selected_wires[0])
            for family in ("determinism", "oracle_repeat", "k_control"):
                if (work.position, family) in self.text_priors:
                    self.assertIs(self.text_priors[work.position, family], final.wires[0])

    def test_actual_rf02_seals_totals_resource_samples_and_events(self):
        result = self.result
        self.assertEqual(tuple(value.name for value in result.coordinator.streams),
                         execution.STREAM_NAMES + ("operations", "resources"))
        expected = {name: b"" for name in execution.STREAM_NAMES}
        measured = {family: [0, 0] for family in readiness.V2_FAMILIES}
        for work in self.materialization_plan:
            for wire in self.constructed[work.position].wires:
                view = execution.decode_bundle_view_v2(wire, self.profile.sha256,
                                                        max_payload_bytes=self.envelope.max_payload_bytes)
                for row in view.rows:
                    expected[row.stream_name] += row.frame_bytes
                for family in measured:
                    for axis, amount in enumerate(_text_family_metrics(view, family)):
                        measured[family][axis] += amount
        for name, data in expected.items():
            self.assertEqual((self.root / (name + ".pkf")).read_bytes(), data, name)
        for digest in result.coordinator.streams:
            self.assertEqual(self.scan(self.root, digest.name)[0], digest)
        self.assertEqual(tuple((value.family, value.physical_bytes, value.logical_bytes)
            for value in result.family_totals),
            tuple((family, *measured[family]) for family in readiness.V2_FAMILIES))
        self.assertEqual(dict(result.family_counts), dict(zip(readiness.V2_FAMILIES, (4, 1, 2, 1, 1, 2))))
        self.assertEqual(result.coordinator.durable_units, 6)
        self.assertEqual(result.coordinator.durable_primary_boards, 4)
        self.assertEqual(result.coordinator.archive_bytes,
                         sum(path.stat().st_size for path in self.root.glob("*.pkf")))
        self.assertEqual((result.coordinator.status, result.coordinator.reason_codes), (records.AuditStatus.PASS, ()))
        events = [row[1] for row in self.scan(self.root, "operations")[1]]
        self.assertEqual((events[0].unit_id, events[0].event_kind, events[0].status),
            ("coordinator", records.EventKind.START, records.OperationStatus.RUNNING))
        self.assertEqual((events[-1].unit_id, events[-1].event_kind, events[-1].status),
            ("coordinator:ADMISSION_END", records.EventKind.END, records.OperationStatus.COMPLETED))
        samples = [row[1] for row in self.scan(self.root, "resources")[1]]
        self.assertEqual(len(samples), 6)
        expected_ids = tuple(operational._unit_id(work.position, kind)
            for work in self.materialization_plan for kind in operational._kinds(work))
        self.assertEqual(tuple(sample.unit_id for sample in samples), expected_ids)
        self.assertTrue(all((sample.worker_bytes, sample.coordinator_bytes, sample.combined_bytes) == (0, 100, 100)
            and sample.process_role is records.ProcessRole.COMBINED
            and sample.method is records.MemoryMethod.PRIVATE_BYTES for sample in samples))
        self.assertTrue(all(sample.elapsed_ns >= 0 for sample in samples))
        self.assertEqual(self.progress, [(index, 4) for index in range(5)])
        self.assertEqual({path.suffix for path in self.root.iterdir()}, {".pkf"})
        self.assertFalse((self.root / "COMPLETE.json").exists())

    def test_compact_constructor_facts_have_exact_trials_and_no_validation_authority(self):
        facts = self.result.constructor_facts
        self.assertEqual(len(facts), 11)
        self.assertEqual({(fact.position, fact.family) for fact in facts},
            {(work.position, family) for work in self.plan for family in h._v2_conceptual_families(work)})
        import pickle
        from experiments import program_k_e2_r0_evidence as evidence
        for fact in facts:
            original = (self.reference_results[fact.position] if fact.family == "reference"
                        else self.text_results[fact.position, fact.family])
            trial = original.selected_trial
            self.assertEqual((fact.selected_knob, fact.selected_trial_ordinal),
                (trial.q if fact.family == "reference" else trial.h, trial.ordinal))
            self.assertEqual((fact.actual_physical_bytes, fact.actual_logical_bytes,
                fact.physical_margin, fact.logical_margin),
                (trial.actual_physical_bytes, trial.actual_logical_bytes, trial.physical_margin, trial.logical_margin))
            self.assertEqual((fact.physical_excess, fact.logical_excess),
                             (max(0, fact.physical_margin), max(0, fact.logical_margin)))
            self.assertEqual(len(fact.trials), len(original.trials))
            self.assertLessEqual(len(fact.trials), 8)
            self.assertEqual(fact.constructor_kind, "reference" if fact.family == "reference" else "text")
            self.assertEqual(fact.text_window_applies, fact.family != "reference")
            self.assertEqual(fact.text_window_upper_bound,
                             None if fact.family == "reference" else fact.physical_target + 4096)
            for observed, raw in zip(fact.trials, original.trials):
                self.assertEqual((observed.ordinal, observed.knob, observed.actual_physical_bytes,
                    observed.actual_logical_bytes, observed.physical_margin, observed.logical_margin,
                    observed.eligible, observed.rejection_reason), (raw.ordinal,
                    raw.q if fact.family == "reference" else raw.h, raw.actual_physical_bytes,
                    raw.actual_logical_bytes, raw.physical_margin, raw.logical_margin,
                    raw.eligible, raw.rejection_reason))
            self.assertFalse(hasattr(fact, "__dict__"))
            self.assertTrue({"bundle", "wire", "context", "rows", "path", "trusted", "token"}.isdisjoint(
                field.name for field in fields(fact)))
            self.assertNotIn(type(fact), evidence._FACT_TYPES.values())
            with self.assertRaises(FrozenInstanceError):
                fact.physical_excess = 0
            with self.assertRaises(TypeError):
                pickle.dumps(fact)

    def test_serial_transaction_state_progress_and_final_policy_reconciliation(self):
        previous = h._new_v2_materialization_ledger(self.targets, self._full_counts)
        prior_totals = None
        for args, kwargs, transaction in self.transactions:
            self.assertEqual(args[6], previous)
            if prior_totals is not None:
                self.assertIs(args[6], previous)
                self.assertIs(kwargs["family_totals"], prior_totals)
            previous, prior_totals = transaction.ledger, transaction.family_totals
        result = self.result
        self.assertEqual(result.ledger, previous)
        self.assertEqual(result.family_totals, prior_totals)
        self.assertEqual(len(self.reconciliation_calls), 1)
        self.assertEqual(self.reconciliation_calls[0][1], (4, 1, 2, 1, 1, 2))
        self.assertEqual(sum(value.physical_excess for value in result.family_totals),
                         result.ledger.committed_excess)
        self.assertFalse(result.ledger.reservation_pending)
        self.assertEqual(result.fixed_allowance_reservation, 268435456)
        self.assertEqual(result.b_proc, result.ledger.capacity)
        self.assertEqual(result.remaining_procedural_budget, result.b_proc - result.ledger.committed_excess)
        self.assertEqual(result.max_coordinator_private_bytes, 100)
        self.assertTrue(result.progress_complete and result.cleanup_complete and result.synthetic_non_evidence)
        self.assertFalse(getattr(result, "readback_complete", False))

    @classmethod
    def full_metadata_fixture(cls):
        if not hasattr(cls, "_metadata_fixture"):
            with tempfile.TemporaryDirectory() as directory, cls.forbidden_workloads(), \
                    patch.object(h, "_construct_v2_materialization_work",
                                 side_effect=AssertionError("No 10000-unit construction")), \
                    patch.object(h, "_materialize_v2_plan",
                                 side_effect=AssertionError("No 10000-unit loop")), \
                    patch.object(operational._V2EvidenceSink, "__init__",
                                 side_effect=AssertionError("No metadata-only sink")):
                path = Path(directory) / "receipt.json"
                path.write_bytes(_accepted_receipt_bytes())
                receipt = h.load_selection_receipt(path)
                plan = h.build_selected_work_plan(receipt, "synthetic-i7-slice1m-metadata-only")
                cls._metadata_fixture = plan, receipt.workload
        return cls._metadata_fixture

    def test_full_owner_metadata_only_routes_exact_accepted_counts_without_construction(self):
        plan, workload = self.full_metadata_fixture()
        marker = object()
        with tempfile.TemporaryDirectory() as directory, self.forbidden_workloads(), \
                patch.object(h, "_materialize_v2_plan", return_value=marker) as lower, \
                patch.object(h, "_publish_v2_materialization", return_value=object()) as publish, \
                patch.object(h, "_close_v2_experiment_archive", side_effect=AssertionError("No live V2 archive close")), \
                patch.object(h, "_construct_v2_materialization_work",
                             side_effect=AssertionError("No full constructor")) as constructor, \
                patch.object(operational._V2EvidenceSink, "__init__",
                             side_effect=AssertionError("No metadata-only sink")) as sink, \
                patch.object(readiness, "validate_synthetic_work_plan",
                             wraps=readiness.validate_synthetic_work_plan) as validate, \
                patch.object(readiness, "validate_dual_payload_fit",
                             wraps=readiness.validate_dual_payload_fit) as payload, \
                patch.object(readiness, "minimum_archive_preflight",
                             wraps=readiness.minimum_archive_preflight) as minimum, \
                patch.object(h, "_new_v2_materialization_ledger",
                             wraps=h._new_v2_materialization_ledger) as ledger:
            self.assertIs(h._materialize_synthetic_v2(plan, workload, self.targets,
                self.profile, self.envelope, directory), marker)
            self.assertEqual(list(Path(directory).iterdir()), [])
        validate.assert_called_once_with(plan, workload)
        payload.assert_called_once_with(workload, self.targets, self.envelope.max_payload_bytes)
        minimum.assert_called_once_with(self.targets.physical, workload.unit_counts, 0)
        ledger.assert_called_once_with(self.targets, workload.unit_counts)
        constructor.assert_not_called()
        sink.assert_not_called()
        self.assertEqual(lower.call_count, 1)
        args = lower.call_args.args
        self.assertIs(args[0], plan)
        self.assertEqual(len(args[1]), 10000)
        self.assertEqual(args[6], (10000, 256, 128, 4, 256, 506))
        self.assertEqual(sum(args[6]), 11150)
        self.assertEqual(self.counts(args[1]), workload.unit_counts)
        self.assertEqual(sum(work.board.width == 30 for work in args[1]), 506)
        self.assertEqual(tuple(work.board.game_index for work in args[1]),
                         tuple(work.board.game_index for work in plan))
        self.assertEqual(args[7], h._new_v2_materialization_ledger(self.targets, workload.unit_counts))
        publish.assert_called_once_with(Path(directory), marker, self.targets, self.profile, self.envelope)

    def test_full_owner_changed_flags_counts_positions_identity_and_types_fail_before_lower(self):
        plan, workload = self.full_metadata_fixture()
        changed_selection = replace(workload.selection)
        object.__setattr__(changed_selection, "counts", replace(workload.selection.counts,
                                                              u_kd=workload.selection.counts.u_kd + 1))
        changed_workload = replace(workload)
        object.__setattr__(changed_workload, "selection", changed_selection)
        cases = ((list(plan), workload), (plan, object()), (plan, changed_workload),
            ((replace(plan[0], oracle_b_selected=not plan[0].oracle_b_selected),) + plan[1:], workload),
            ((replace(plan[0], position=1),) + plan[1:], workload),
            ((replace(plan[0], board=h.reference_board_identity(plan[0].board.game_index)),) + plan[1:], workload))
        with tempfile.TemporaryDirectory() as directory, self.forbidden_workloads(), \
                patch.object(h, "_materialize_v2_plan", side_effect=AssertionError("No lower loop")) as lower, \
                patch.object(operational._V2EvidenceSink, "__init__",
                             side_effect=AssertionError("No sink")) as sink:
            for bad_plan, bad_workload in cases:
                with self.subTest(plan_type=type(bad_plan), workload_type=type(bad_workload)), \
                        self.assertRaises(ValueError):
                    h._materialize_synthetic_v2(bad_plan, bad_workload, self.targets,
                                               self.profile, self.envelope, directory)
                self.assertEqual(list(Path(directory).iterdir()), [])
        lower.assert_not_called()
        sink.assert_not_called()

    def test_full_owner_minimum_and_procedural_infeasibility_are_prewrite(self):
        plan, workload = self.full_metadata_fixture()
        other_minima = workload.unit_counts[1] + workload.unit_counts[4] + workload.unit_counts[5]
        for boundary, reason in (
                (identity.MAX_ARCHIVE_BYTES, "SYNTHETIC_MINIMUM_ARCHIVE_CAP"),
                (identity.MAX_ARCHIVE_BYTES - identity.FIXED_REPORT_RECEIPT_ALLOWANCE,
                 "SYNTHETIC_PROCEDURAL_FIXED_RESERVATION_INFEASIBLE")):
            basis = readiness.ComponentSizes((boundary - other_minima) // 10000 + 1, 1, 0, 0, 1, 1)
            targets = readiness.DualComponentSizes(basis, basis)
            envelope = replace(self.envelope, max_payload_bytes=physical.MAX_PAYLOAD_BYTES)
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory, \
                    patch.object(h, "_materialize_v2_plan", side_effect=AssertionError("No lower loop")) as lower, \
                    patch.object(operational._V2EvidenceSink, "__init__",
                                 side_effect=AssertionError("No sink")) as sink:
                with self.assertRaisesRegex(readiness.ReadinessError, reason):
                    h._materialize_synthetic_v2(plan, workload, targets, self.profile, envelope, directory)
                self.assertEqual(list(Path(directory).iterdir()), [])
            lower.assert_not_called()
            sink.assert_not_called()

    def test_missing_file_nonempty_and_historical_roots_are_rejected_without_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            file_root = parent / "file"
            file_root.write_bytes(b"preserved")
            nonempty = parent / "nonempty"
            nonempty.mkdir()
            (nonempty / "operations.jsonl").write_bytes(b"historical")
            subtree = parent / "subtree"
            subtree.mkdir()
            (subtree / "child").mkdir()
            for root in (parent / "missing" / "nested", file_root, nonempty, subtree):
                with self.subTest(root=root.name), \
                        patch.object(operational._V2EvidenceSink, "__init__",
                                     side_effect=AssertionError("No sink")) as sink, \
                        self.assertRaisesRegex(ValueError, "V2_EMPTY_STREAM_ROOT_REQUIRED"):
                    self.run_lower(root, plan=self.plan[:1])
                sink.assert_not_called()
            self.assertFalse((parent / "missing").exists())
            self.assertEqual(file_root.read_bytes(), b"preserved")
            self.assertEqual((nonempty / "operations.jsonl").read_bytes(), b"historical")

    def test_zero_oracle_preserves_conceptual_fact_count_and_no_attributable_rows(self):
        plan = (replace(self.plan[0], oracle_b_selected=True),)
        targets = replace(self.targets,
            physical=replace(self.targets.physical, oracle_primary=0, oracle_repeat=0),
            logical=replace(self.targets.logical, oracle_primary=0, oracle_repeat=0))
        with tempfile.TemporaryDirectory() as directory, self.forbidden_workloads(), \
                patch.object(operational.harness, "_coordinator_private_bytes", return_value=100), \
                patch.object(h, "_reconcile_v2_materialization_totals",
                             side_effect=self.padded_reconciliation), \
                patch.object(h, "construct_text_family_v2", wraps=h.construct_text_family_v2) as text, \
                patch.object(h, "_materialize_v2_unit", wraps=h._materialize_v2_unit) as transaction:
            result = self.run_lower(directory, plan=plan, targets=targets)
            self.assertEqual([call.args[2] for call in text.call_args_list], ["primary", "oracle_primary"])
            self.assertEqual(transaction.call_args.args[5], ("primary",))
            self.assertEqual(dict(result.family_counts)["oracle_primary"], 1)
            oracle = next(value for value in result.family_totals if value.family == "oracle_primary")
            self.assertEqual((oracle.physical_bytes, oracle.logical_bytes, oracle.physical_excess), (0, 0, 0))
            fact = next(value for value in result.constructor_facts if value.family == "oracle_primary")
            self.assertTrue(fact.zero_oracle)
            self.assertEqual((fact.selected_knob, fact.selected_trial_ordinal, fact.trials), (0, 0, ()))
            self.assertFalse(fact.text_window_applies)
            self.assertEqual(self.scan(directory, "oracle_b_audits")[1], [])
            coverage = self.scan(directory, "oracle_b_coverage")[1][0][1]
            self.assertTrue(coverage.selected)
            self.assertEqual(coverage.applicable, ())
            h._publish_v2_materialization(directory, result, targets, self.profile, self.envelope)
            observed = self.readback_fixture(directory, plan=plan, targets=targets)
            self.assertEqual(dict(observed.family_counts)["oracle_primary"], 1)
            self.assertEqual(observed.constructor_fact_count, 2)
            oracle = next(value for value in observed.family_totals if value.family == "oracle_primary")
            self.assertEqual((oracle.physical_bytes, oracle.logical_bytes, oracle.physical_excess), (0, 0, 0))
        reference = replace(self.materialization_plan[3], position=0)
        with self.forbidden_workloads(), \
                patch.object(h, "construct_text_family_v2", side_effect=AssertionError("No text call")) as text, \
                self.assertRaisesRegex(ValueError, "REFERENCE_REACHED_ORACLE_TARGET_REQUIRED"):
            h._construct_v2_materialization_work(reference, targets, self.profile, self.envelope)
        text.assert_not_called()

    @contextmanager
    def capture_sinks(self):
        captured = []
        original = operational._V2EvidenceSink.__init__
        def initialize(sink, *args, **kwargs):
            original(sink, *args, **kwargs)
            captured.append(sink)
        with patch.object(operational._V2EvidenceSink, "__init__", new=initialize):
            yield captured

    def assert_failed_prefix(self, root, sink, completed):
        self.assertTrue(sink.closed)
        self.assertFalse(sink.sealed)
        self.assertEqual(sink.durable_primary_boards, completed)
        self.assertFalse((Path(root) / "COMPLETE.json").exists())
        self.assertFalse(list(Path(root).glob("*.jsonl")))
        for name in execution.STREAM_NAMES:
            rows = self.scan(root, name)[1]
            self.assertTrue(all(key[0] < completed for key, _, _, _ in rows), name)

    def test_constructor_rejections_stop_current_reservation_and_preserve_prior_work(self):
        original_construct = h._construct_v2_materialization_work
        for kind, reason in (("reference", "SYNTHETIC_SIZING_SEARCH_EXHAUSTED"),
                ("text", "SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT"),
                ("text", "SYNTHETIC_SIZING_SEARCH_EXHAUSTED"),
                ("text", "SYNTHETIC_LOGICAL_DOMAIN_EMPTY"),
                ("text", "SYNTHETIC_TEXT_LSUM_CAP")):
            calls = []
            def construct(work, *args, **kwargs):
                calls.append(work.position)
                return (self.constructed[work.position] if work.position < 2
                        else original_construct(work, *args, **kwargs))
            reference_result = (h._reference_failure(None, None, (), reason) if kind == "reference"
                                else self.reference_results[2])
            def text(work, bundle, family, *args, **kwargs):
                return h.TextConstructionResult(family, None, None, None, (), reason)
            with self.subTest(kind=kind, reason=reason), tempfile.TemporaryDirectory() as directory, \
                    self.capture_sinks() as sinks, self.cached_lower(), \
                    patch.object(h, "_construct_v2_materialization_work", side_effect=construct), \
                    patch.object(h, "construct_reference_v2", return_value=reference_result) as reference, \
                    patch.object(h, "construct_text_family_v2", side_effect=text) as text_call, \
                    patch.object(readiness, "reserve_procedural_unit", wraps=readiness.reserve_procedural_unit) as reserve, \
                    patch.object(readiness, "commit_procedural_unit", wraps=readiness.commit_procedural_unit) as commit:
                with self.assertRaisesRegex(ValueError, "^" + reason + "$"):
                    self.run_lower(directory)
                self.assertEqual(calls, [0, 1, 2])
                self.assertEqual((reserve.call_count, commit.call_count), (2, 2))
                self.assertEqual(reference.call_count, 1)
                self.assertEqual(text_call.call_count, 0 if kind == "reference" else 1)
                self.assert_failed_prefix(directory, sinks[0], 2)
                events = [row[1] for row in self.scan(directory, "operations")[1]]
                errors = [value for value in events if value.event_kind is records.EventKind.ERROR]
                self.assertEqual(len(errors), 1)
                self.assertEqual(errors[0].unit_id, "coordinator:SYNTHETIC_V2_MATERIALIZATION_INCOMPLETE")
                self.assertEqual(errors[0].status, records.OperationStatus.INCOMPLETE)
                self.assertNotIn("coordinator:ADMISSION_END", [value.unit_id for value in events])

    def test_inside_constructor_cancel_memory_and_wall_checks_abort_without_current_reservation(self):
        import threading
        for case, reason in (("cancel", "CANCELLED"), ("coordinator", "SYNTHETIC_COORDINATOR_MEMORY_CAP"),
                ("combined", "SYNTHETIC_COORDINATOR_MEMORY_CAP"), ("wall", "SYNTHETIC_MATERIALIZATION_TIMEOUT")):
            cancel = threading.Event()
            state = {"current": 100, "now": 1000}
            calls = []
            # Accepted envelopes require coordinator <= combined. A combined
            # breach necessarily hits the coordinator guard first with worker=0.
            envelope = replace(self.envelope, worker_memory_cap_bytes=100,
                coordinator_memory_cap_bytes=101 if case in ("coordinator", "combined") else 1000,
                memory_cap_bytes=101 if case == "combined" else 1000)
            def construct(work, *args, check=None, **kwargs):
                calls.append(work.position)
                if work.position == 1:
                    if case == "cancel":
                        cancel.set()
                    elif case == "wall":
                        state["now"] += envelope.max_launcher_wall_ms * 1000000
                    else:
                        state["current"] = 102
                    check()
                    raise AssertionError("Containment check must abort")
                return self.constructed[work.position]
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory, \
                    self.capture_sinks() as sinks, self.cached_lower(), \
                    patch.object(h.time, "monotonic_ns", side_effect=lambda: state["now"]), \
                    patch.object(operational.harness, "_coordinator_private_bytes",
                                 side_effect=lambda: state["current"]), \
                    patch.object(h, "_construct_v2_materialization_work", side_effect=construct), \
                    patch.object(readiness, "reserve_procedural_unit", wraps=readiness.reserve_procedural_unit) as reserve:
                with self.assertRaisesRegex(ValueError, "^" + reason + "$"):
                    self.run_lower(directory, envelope=envelope, cancel=cancel)
                self.assertEqual(calls, [0, 1])
                self.assertEqual(reserve.call_count, 1)
                self.assert_failed_prefix(directory, sinks[0], 1)

    def test_containment_callback_reaches_both_actual_constructor_types(self):
        for work in (self.materialization_plan[0], self.materialization_plan[2]):
            inside = []
            reference, text = h.construct_reference_v2, h.construct_text_family_v2
            def reference_call(*args, **kwargs):
                inside.append("reference")
                return reference(*args, **kwargs)
            def text_call(*args, **kwargs):
                inside.append("text")
                return text(*args, **kwargs)
            def check():
                if inside:
                    raise h.HarnessError("SLICE1M_CALLBACK_ABORT")
            with self.subTest(position=work.position), self.forbidden_workloads(), \
                    patch.object(h, "construct_reference_v2", side_effect=reference_call), \
                    patch.object(h, "construct_text_family_v2", side_effect=text_call), \
                    patch.object(readiness, "reserve_procedural_unit",
                                 side_effect=AssertionError("No reservation")) as reserve, \
                    self.assertRaisesRegex(ValueError, "SLICE1M_CALLBACK_ABORT"):
                h._construct_v2_materialization_work(work, self.targets, self.profile, self.envelope, check=check)
            self.assertEqual(inside, ["text"] if work.position == 0 else ["reference"])
            reserve.assert_not_called()

    def test_precancelled_or_memory_breach_before_sink_leaves_empty_root(self):
        import threading
        cancelled = threading.Event()
        cancelled.set()
        for cancel, memory, reason in ((cancelled, 100, "CANCELLED"),
                (None, self.envelope.coordinator_memory_cap_bytes + 1, "SYNTHETIC_COORDINATOR_MEMORY_CAP")):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory, \
                    patch.object(operational.harness, "_coordinator_private_bytes", return_value=memory), \
                    patch.object(operational._V2EvidenceSink, "__init__", side_effect=AssertionError("No sink")) as sink:
                with self.assertRaisesRegex(ValueError, reason):
                    self.run_lower(directory, cancel=cancel)
                sink.assert_not_called()
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_start_end_checkpoint_and_seal_failures_retain_bytes_without_success(self):
        append = h.store.FramedStreamWriter.append_frame
        checkpoint = h.store.FramedStreamWriter.checkpoint
        seal = h.store.FramedStreamWriter.seal
        for case in ("start_append", "start_checkpoint", "end_append", "end_checkpoint", "seal"):
            state = {"last_event": None, "fired": False}
            def append_frame(writer, key, logical, frame):
                value = append(writer, key, logical, frame)
                if writer.stream_name == "operations":
                    state["last_event"] = records.decode(logical).unit_id
                    matching = ((case == "start_append" and state["last_event"] == "coordinator")
                        or (case == "end_append" and state["last_event"] == "coordinator:ADMISSION_END"))
                    if matching and not state["fired"]:
                        state["fired"] = True
                        raise h.store.StoreError("SLICE1M_EVENT_WRITE_FAILURE")
                return value
            def checkpoint_stream(writer):
                value = checkpoint(writer)
                matching = writer.stream_name == "operations" and (
                    (case == "start_checkpoint" and state["last_event"] == "coordinator")
                    or (case == "end_checkpoint" and state["last_event"] == "coordinator:ADMISSION_END"))
                if matching and not state["fired"]:
                    state["fired"] = True
                    raise h.store.StoreError("SLICE1M_EVENT_CHECKPOINT_FAILURE")
                return value
            def seal_stream(writer):
                value = seal(writer)
                if case == "seal" and not state["fired"]:
                    state["fired"] = True
                    raise h.store.StoreError("SLICE1M_SEAL_FAILURE")
                return value
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory, \
                    self.capture_sinks() as sinks, self.cached_lower(), \
                    patch.object(h.store.FramedStreamWriter, "append_frame", new=append_frame), \
                    patch.object(h.store.FramedStreamWriter, "checkpoint", new=checkpoint_stream), \
                    patch.object(h.store.FramedStreamWriter, "seal", new=seal_stream):
                with self.assertRaisesRegex(h.store.StoreError, "SLICE1M_"):
                    self.run_lower(directory, plan=self.plan[:1])
                self.assertTrue(state["fired"])
                self.assertTrue(sinks[0].poisoned and sinks[0].closed)
                self.assertFalse(sinks[0].sealed)
                self.assertEqual(sinks[0].durable_primary_boards, 0 if case.startswith("start") else 1)
                retained = {path.name: path.read_bytes() for path in Path(directory).glob("*.pkf")}
                self.assertGreater(sum(map(len, retained.values())), 0)
                self.assertFalse((Path(directory) / "COMPLETE.json").exists())
                sinks[0].close()
                self.assertEqual({path.name: path.read_bytes() for path in Path(directory).glob("*.pkf")}, retained)

    def test_progress_exception_after_durability_aborts_without_rollback_or_later_work(self):
        for fail_at in (0, 1):
            updates = []
            def progress(done, total):
                updates.append((done, total))
                if done == fail_at:
                    raise RuntimeError("private progress diagnostic")
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as directory, \
                    self.capture_sinks() as sinks, self.cached_lower(), \
                    patch.object(readiness, "commit_procedural_unit", wraps=readiness.commit_procedural_unit) as commit:
                with self.assertRaisesRegex(RuntimeError, "private progress diagnostic"):
                    self.run_lower(directory, progress=progress)
                self.assertEqual(updates, [(done, 4) for done in range(fail_at + 1)])
                self.assertEqual(commit.call_count, fail_at)
                self.assert_failed_prefix(directory, sinks[0], fail_at)
                events = [row[1] for row in self.scan(directory, "operations")[1]]
                self.assertEqual(events[-1].unit_id, "coordinator:SYNTHETIC_V2_MATERIALIZATION_INCOMPLETE")
                self.assertTrue(all("private progress diagnostic" not in event.unit_id for event in events))

    def test_reconciliation_failure_or_wrong_excess_prevents_end_and_seal(self):
        for case in ("raises", "wrong"):
            def reconcile(targets, counts, totals, ledger):
                if case == "raises":
                    raise readiness.ReadinessError("PROCEDURAL_EXCESS_RECONCILIATION")
                return ledger.committed_excess + 1
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory, \
                    self.capture_sinks() as sinks, self.cached_lower(), \
                    patch.object(h, "_reconcile_v2_materialization_totals", side_effect=reconcile), \
                    patch.object(operational._V2EvidenceSink, "seal",
                                 side_effect=AssertionError("No success seal")) as seal:
                with self.assertRaisesRegex(ValueError, "PROCEDURAL_EXCESS_RECONCILIATION"):
                    self.run_lower(directory, plan=self.plan[:1])
                seal.assert_not_called()
                self.assert_failed_prefix(directory, sinks[0], 1)
                events = [row[1] for row in self.scan(directory, "operations")[1]]
                self.assertNotIn("coordinator:ADMISSION_END", [value.unit_id for value in events])

    def test_partial_transaction_poison_preserves_prefix_and_never_writes_error_or_later_work(self):
        append = h.store.FramedStreamWriter.append_frame
        prefix, constructed = {}, []
        def progress(done, total):
            if done == 1:
                prefix.update({path.name: path.read_bytes() for path in Path(directory).glob("*.pkf")})
        def construct(work, *args, **kwargs):
            constructed.append(work.position)
            return self.constructed[work.position]
        def fail_append(writer, key, logical, frame):
            value = append(writer, key, logical, frame)
            if writer.stream_name == "boards" and key[0] == 1:
                raise h.store.StoreError("SLICE1M_PARTIAL_UNIT_FAILURE")
            return value
        with tempfile.TemporaryDirectory() as directory, self.capture_sinks() as sinks, self.cached_lower(), \
                patch.object(h, "_construct_v2_materialization_work", side_effect=construct), \
                patch.object(h.store.FramedStreamWriter, "append_frame", new=fail_append), \
                patch.object(readiness, "reserve_procedural_unit", wraps=readiness.reserve_procedural_unit) as reserve, \
                patch.object(readiness, "commit_procedural_unit", wraps=readiness.commit_procedural_unit) as commit:
            with self.assertRaisesRegex(h.store.StoreError, "SLICE1M_PARTIAL_UNIT_FAILURE"):
                self.run_lower(directory, progress=progress)
            self.assertEqual(constructed, [0, 1])
            self.assertEqual((reserve.call_count, commit.call_count), (2, 1))
            self.assertTrue(sinks[0].poisoned and sinks[0].closed)
            self.assertFalse(sinks[0].sealed)
            self.assertEqual(sinks[0].durable_primary_boards, 1)
            retained = {path.name: path.read_bytes() for path in Path(directory).glob("*.pkf")}
            self.assertTrue(prefix and all(retained[name].startswith(raw) for name, raw in prefix.items()))
            self.assertGreater(sum(map(len, retained.values())), sum(map(len, prefix.values())))
            events = [row[1] for row in self.scan(directory, "operations")[1]]
            self.assertFalse(any(event.event_kind is records.EventKind.ERROR for event in events))
            self.assertFalse((Path(directory) / "COMPLETE.json").exists())

    def test_final_count_fact_and_total_tampering_cannot_publish_success(self):
        for case in ("facts", "totals"):
            def construct(work, *args, **kwargs):
                value = self.constructed[work.position]
                return replace(value, constructor_facts=()) if case == "facts" else value
            transaction = h._materialize_v2_unit
            def transact(*args, **kwargs):
                result = transaction(*args, **kwargs)
                if case == "totals":
                    first = result.family_totals[0]
                    return replace(result, family_totals=(replace(first,
                        physical_excess=first.physical_excess + 1),) + result.family_totals[1:])
                return result
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory, \
                    self.capture_sinks() as sinks, self.cached_lower(), \
                    patch.object(h, "_construct_v2_materialization_work", side_effect=construct), \
                    patch.object(h, "_materialize_v2_unit", side_effect=transact), \
                    patch.object(operational._V2EvidenceSink, "seal",
                                 side_effect=AssertionError("No success seal")) as seal:
                with self.assertRaisesRegex(ValueError, "V2_MATERIALIZATION_(FAMILY_COUNTS|EXCESS_TOTALS)"):
                    self.run_lower(directory, plan=self.plan[:1])
                seal.assert_not_called()
                self.assert_failed_prefix(directory, sinks[0], 1)

    @contextmanager
    def bounded_readback_policy(self):
        # The accepted readiness arithmetic has a full-10000 count domain.
        # Lift only pure arithmetic inputs; metadata and RF02 totals stay exact.
        new_ledger = h._new_v2_materialization_ledger
        minimum = readiness.minimum_archive_preflight
        with patch.object(h, "_new_v2_materialization_ledger",
                side_effect=lambda targets, counts: new_ledger(targets, self._full_counts)), \
                patch.object(readiness, "minimum_archive_preflight",
                    side_effect=lambda sizes, counts, supporting: minimum(sizes, self._full_counts, supporting)), \
                patch.object(h, "_reconcile_v2_materialization_totals", side_effect=self.padded_reconciliation):
            yield

    @contextmanager
    def independent_readback_guards(self):
        with self.forbidden_workloads(), _EvidenceExitStack() as stack:
            for name in ("construct_reference_v2", "construct_text_family_v2",
                    "_construct_v2_materialization_work", "_materialize_synthetic_v2",
                    "_materialize_v2_plan", "_reference_bundles", "_search_reference_trials",
                    "_search_text_trials", "_capture_qualified_codec_profile"):
                stack.enter_context(patch.object(h, name,
                    side_effect=AssertionError("Independent readback cannot construct or materialize")))
            for owner, name in ((execution, "encode_bundle_v2"), (physical, "encode_payload"),
                    (physical, "encode_frame"), (physical, "capture_qualified_profile")):
                stack.enter_context(patch.object(owner, name,
                    side_effect=AssertionError("Independent readback cannot re-encode or recapture")))
            yield

    def readback_fixture(self, root, *, plan=None, targets=None, envelope=None, memory_probe=None, **kwargs):
        plan = self.plan if plan is None else plan
        with self.independent_readback_guards(), self.bounded_readback_policy(), \
                patch.object(operational.harness, "_coordinator_private_bytes",
                    side_effect=(lambda: 100) if memory_probe is None else memory_probe):
            return h._readback_v2_plan(root, plan, self.targets if targets is None else targets,
                self.profile, self.envelope if envelope is None else envelope, self.counts(plan), **kwargs)

    @contextmanager
    def sealed_four_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source in self.root.glob("*.pkf"):
                (root / source.name).write_bytes(source.read_bytes())
            yield root

    @contextmanager
    def published_four_work(self):
        with self.sealed_four_work() as root:
            metadata = h._publish_v2_materialization(root, self.result, self.targets,
                                                   self.profile, self.envelope)
            yield root, metadata

    @staticmethod
    def metadata_node(root):
        return json.loads((Path(root) / "materialization-v2.json").read_bytes())

    @staticmethod
    def write_metadata_node(root, node):
        # Tamper fixtures deliberately replace an already published file. The
        # production exclusive-create publication path is never used to repair it.
        (Path(root) / "materialization-v2.json").write_bytes(json.dumps(node,
            sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n")

    def rewrite_v2_stream(self, root, name, transform):
        rows = [(key, record) for key, record, _, _ in self.scan(root, name)[1]]
        updated = transform(rows)
        context = physical.context_for(name, self.profile.sha256)
        raw = b"".join(physical.encode_frame(records.encode(record), key, context,
            max_payload_bytes=self.envelope.max_payload_bytes) for key, record in updated)
        (Path(root) / (name + ".pkf")).write_bytes(raw)
        node = self.metadata_node(root)
        seal = next(value for value in node["streams"] if value["name"] == name)
        seal.update(sha256=h.sha256(raw).hexdigest(), byte_length=len(raw), record_count=len(updated))
        node["current_sealed_pkf_bytes"] = sum(value["byte_length"] for value in node["streams"])
        node["attributable_experiment_bytes"] = sum(value["byte_length"] for value in node["streams"]
                                                    if value["name"] in execution.STREAM_NAMES)
        self.write_metadata_node(root, node)

    def test_v2_four_work_publication_and_independent_readback_reproduce_exact_disk_facts(self):
        from experiments import program_k_e2_r0_evidence as evidence
        with self.published_four_work() as (root, metadata):
            data = (root / "materialization-v2.json").read_bytes()
            self.assertEqual(data, evidence.encode_materialization_v2(metadata))
            self.assertTrue(data.endswith(b"\n") and not data.endswith(b"\n\n"))
            self.assertEqual(evidence.decode_materialization_v2(data,
                expected_profile_sha256=self.profile.sha256.hex()), metadata)
            self.assertEqual(metadata.codec_profile_bytes, self.profile.canonical_bytes)
            self.assertFalse(hasattr(metadata, "readback_complete"))
            self.assertEqual(dict(metadata.family_counts), dict(zip(readiness.V2_FAMILIES, (4, 1, 2, 1, 1, 2))))
            self.assertEqual(tuple((value.family, value.physical_bytes, value.logical_bytes, value.physical_excess)
                for value in metadata.family_totals), tuple((value.family, value.physical_bytes,
                value.logical_bytes, value.physical_excess) for value in self.result.family_totals))
            self.assertEqual(metadata.attributable_experiment_bytes,
                             sum(value.physical_bytes for value in self.result.family_totals))
            self.assertEqual(metadata.current_sealed_pkf_bytes, self.result.coordinator.archive_bytes)
            self.assertEqual({path.name for path in root.iterdir()},
                {name + ".pkf" for name in execution.STREAM_NAMES + ("operations", "resources")}
                | {"materialization-v2.json"})
            observed = self.readback_fixture(root)
            self.assertEqual(observed.streams, metadata.streams)
            self.assertEqual(observed.source_plan_identity, metadata.source_plan_identity)
            self.assertEqual(observed.materialization_plan_identity, metadata.materialization_plan_identity)
            self.assertEqual(observed.family_counts, metadata.family_counts)
            self.assertEqual(tuple((value.family, value.physical_bytes, value.logical_bytes, value.physical_excess)
                for value in observed.family_totals), tuple((value.family, value.physical_bytes,
                value.logical_bytes, value.physical_excess) for value in metadata.family_totals))
            self.assertEqual((observed.b_proc, observed.e_final,
                observed.remaining_procedural_budget), (metadata.b_proc, metadata.committed_procedural_excess,
                metadata.remaining_procedural_budget))
            self.assertEqual((observed.durable_operation_count, observed.durable_primary_count,
                              observed.constructor_fact_count), (6, 4, 11))
            self.assertEqual(observed.durable_sample_max_coordinator_private_bytes, 100)
            self.assertEqual(observed.runtime_monitor_peak_coordinator_private_bytes, 100)
            self.assertFalse(observed.runtime_peak_is_independent)
            self.assertTrue(observed.constructor_rejections_are_runtime_provenance)
            self.assertTrue(observed.progress_complete and observed.readback_complete and observed.synthetic_non_evidence)
            self.assertFalse(hasattr(observed, "__dict__"))
            self.assertTrue({"root", "path", "readers", "contexts", "bundles", "materialization"}.isdisjoint(
                field.name for field in fields(observed)))
            with self.assertRaises(FrozenInstanceError):
                observed.readback_complete = False
            self.assertEqual(data, (root / "materialization-v2.json").read_bytes())

    def test_v2_readback_opens_and_peeks_all_streams_without_eager_inflate(self):
        reader_type = h.store.FramedStreamPullReader
        original_init, original_decode = reader_type.__init__, physical.decode_frame
        opened, calls, active = [], [], [0]
        def initialize(reader, *args, **kwargs):
            original_init(reader, *args, **kwargs)
            opened.append(reader)
            before = len(calls)
            reader.peek_key()
            self.assertEqual(len(calls), before)
        def decode(*args, **kwargs):
            self.assertEqual(len(opened), len(execution.STREAM_NAMES) + 2)
            self.assertEqual(active[0], 0)
            active[0] += 1
            calls.append(1)
            try:
                return original_decode(*args, **kwargs)
            finally:
                active[0] -= 1
        with self.published_four_work() as (root, metadata), \
                patch.object(reader_type, "__init__", new=initialize), \
                patch.object(physical, "decode_frame", side_effect=decode):
            self.readback_fixture(root)
        self.assertEqual(len(calls), sum(value.record_count for value in metadata.streams))
        self.assertTrue(all(reader.completed_digest is not None for reader in opened))

    def test_v2_metadata_tampering_fails_without_rewriting_disk_evidence(self):
        def first_fact(node):
            return node["constructor_facts"][0]
        def selected_trial(node):
            fact = first_fact(node)
            return next(trial for trial in fact["trials"] if trial["ordinal"] == fact["selected_trial_ordinal"])
        cases = {
            "schema": lambda n: n.update(schema="program-k-e2-r0b-experiment/v1"),
            "basis": lambda n: n["size_basis"].update(record_frame_format="PKE2RF01"),
            "profile_bytes": lambda n: n.update(codec_profile_bytes="7b7d"),
            "profile_sha": lambda n: n.update(codec_profile_sha256="0" * 64),
            "dual_target": lambda n: n["targets"]["physical"].update(primary=n["targets"]["physical"]["primary"] + 1),
            "family_count": lambda n: n["family_counts"][0].__setitem__(1, 5),
            "physical_total": lambda n: n["family_totals"][0].update(physical_bytes=n["family_totals"][0]["physical_bytes"] + 1),
            "logical_total": lambda n: n["family_totals"][0].update(logical_bytes=n["family_totals"][0]["logical_bytes"] + 1),
            "physical_excess": lambda n: n["family_totals"][0].update(physical_excess=n["family_totals"][0]["physical_excess"] + 1),
            "b_proc": lambda n: n.update(b_proc=n["b_proc"] + 1),
            "committed": lambda n: n.update(committed_procedural_excess=n["committed_procedural_excess"] + 1),
            "remaining": lambda n: n.update(remaining_procedural_budget=n["remaining_procedural_budget"] - 1),
            "knob": lambda n: first_fact(n).update(selected_knob=first_fact(n)["selected_knob"] + 1),
            "selected_trial": lambda n: selected_trial(n).update(actual_physical_bytes=selected_trial(n)["actual_physical_bytes"] + 1),
            "trial_reason": lambda n: selected_trial(n).update(eligible=False, rejection_reason="PRIVATE_FREE_FORM_FAILURE"),
            "stream_seal": lambda n: n["streams"][0].update(sha256="0" * 64),
            "source_identity": lambda n: n.update(source_plan_identity="0" * 64),
            "materialization_identity": lambda n: n.update(materialization_plan_identity="0" * 64),
            "runtime_peak_below_samples": lambda n: n.update(runtime_monitor_peak_coordinator_private_bytes=99),
            "runtime_peak_above_cap": lambda n: n.update(runtime_monitor_peak_coordinator_private_bytes=self.envelope.coordinator_memory_cap_bytes + 1),
        }
        for case, mutate in cases.items():
            with self.subTest(case=case), self.published_four_work() as (root, _):
                node = self.metadata_node(root)
                mutate(node)
                self.write_metadata_node(root, node)
                before = {path.name: path.read_bytes() for path in root.iterdir()}
                with self.assertRaises(ValueError):
                    self.readback_fixture(root)
                self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)

    def test_v2_rf02_crc_and_canonical_semantic_key_and_frame_tampering_fail_closed(self):
        def changed_key(rows, axis, value):
            key, record = rows[0]
            key = tuple(value if index == axis else part for index, part in enumerate(key))
            return [(key, record)] + rows[1:]
        cases = {
            "logical_board_identity": lambda rows: [(rows[0][0], replace(rows[0][1], fingerprint="tampered-board"))] + rows[1:],
            "position": lambda rows: changed_key(rows, 0, 9),
            "rank": lambda rows: changed_key(rows, 1, 2),
            "index": lambda rows: changed_key(rows, 2, 1),
            "missing_frame": lambda rows: rows[1:],
            "trailing_frame": lambda rows: rows + [rows[0]],
        }
        for case, transform in cases.items():
            with self.subTest(case=case), self.published_four_work() as (root, _):
                self.rewrite_v2_stream(root, "boards", transform)
                with self.assertRaises(ValueError):
                    self.readback_fixture(root)
        with self.published_four_work() as (root, _):
            path = root / "boards.pkf"
            raw = bytearray(path.read_bytes())
            raw[-1] ^= 1
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                self.readback_fixture(root)

    def test_v2_operations_resources_and_file_set_tampering_fail_closed(self):
        def change_event(rows, predicate, **fields):
            index = next(index for index, (_, record) in enumerate(rows) if predicate(record))
            key, record = rows[index]
            return rows[:index] + [(key, replace(record, **fields))] + rows[index + 1:]
        cases = (
            ("terminal", "operations", lambda rows: change_event(rows,
                lambda event: event.event_kind is records.EventKind.END and event.unit_id.startswith("0:"),
                status=records.OperationStatus.FAILED)),
            ("progress", "operations", lambda rows: change_event(rows,
                lambda event: event.event_kind is records.EventKind.PROGRESS, unit_id="durable_primary_count:9")),
            ("resource_owner", "resources", lambda rows: [(rows[0][0], replace(rows[0][1], unit_id="unexpected-owner"))] + rows[1:]),
            ("resource_memory", "resources", lambda rows: [(rows[0][0], replace(rows[0][1], coordinator_bytes=101, combined_bytes=101))] + rows[1:]),
        )
        for case, name, transform in cases:
            with self.subTest(case=case), self.published_four_work() as (root, _):
                self.rewrite_v2_stream(root, name, transform)
                with self.assertRaises(ValueError):
                    self.readback_fixture(root)
        for case in ("unexpected_jsonl", "missing_pkf", "extra_pkf", "complete_marker"):
            with self.subTest(case=case), self.published_four_work() as (root, _):
                if case == "missing_pkf":
                    (root / "boards.pkf").unlink()
                else:
                    name = {"unexpected_jsonl": "boards.jsonl", "extra_pkf": "extra.pkf",
                            "complete_marker": "COMPLETE.json"}[case]
                    (root / name).write_bytes(b"")
                with self.assertRaises(ValueError):
                    self.readback_fixture(root)

    def test_v2_runtime_monitor_peak_is_distinct_from_durable_samples(self):
        inside_constructor = [False]
        checked_inside = []
        original_text = h.construct_text_family_v2
        def observed_text(*args, **kwargs):
            check = kwargs["_check"]
            def observed_check():
                checked_inside.append(True)
                return check()
            kwargs["_check"] = observed_check
            inside_constructor[0] = True
            try:
                return original_text(*args, **kwargs)
            finally:
                inside_constructor[0] = False
        def memory():
            return 200 if inside_constructor[0] else 100
        plan = self.plan[:1]
        with tempfile.TemporaryDirectory() as directory, self.forbidden_workloads(), \
                patch.object(operational.harness, "_coordinator_private_bytes", side_effect=memory), \
                patch.object(h, "construct_text_family_v2", side_effect=observed_text), \
                patch.object(h, "_reconcile_v2_materialization_totals", side_effect=self.padded_reconciliation):
            result = self.run_lower(directory, plan=plan)
            self.assertTrue(checked_inside)
            self.assertEqual(result.max_coordinator_private_bytes, 200)
            samples = self.scan(directory, "resources")[1]
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0][1].coordinator_bytes, 100)
            metadata = h._publish_v2_materialization(directory, result, self.targets, self.profile, self.envelope)
            self.assertEqual(metadata.runtime_monitor_peak_coordinator_private_bytes, 200)
            observed = self.readback_fixture(directory, plan=plan)
            self.assertEqual(observed.durable_sample_max_coordinator_private_bytes, 100)
            self.assertEqual(observed.runtime_monitor_peak_coordinator_private_bytes, 200)
            self.assertFalse(observed.runtime_peak_is_independent)
            node = self.metadata_node(directory)
            node["runtime_monitor_peak_coordinator_private_bytes"] = 99
            self.write_metadata_node(directory, node)
            with self.assertRaises(ValueError):
                self.readback_fixture(directory, plan=plan)

    def test_v2_serialized_reservation_exact_max_and_preopen_cap_enforcement(self):
        maximum = physical.MAX_PAYLOAD_BYTES
        self.assertEqual(h._v2_serialized_reservation(maximum, maximum), 402786480)
        for maximum, context in ((0, 1), (1, 0), (1, 2), (True, 1), (1, True)):
            with self.subTest(maximum=maximum, context=context), self.assertRaises(ValueError):
                h._v2_serialized_reservation(maximum, context)
        with self.published_four_work() as (root, _):
            context = len((root / "materialization-v2.json").read_bytes())
            reservation = h._v2_serialized_reservation(self.envelope.max_payload_bytes, context)
            self.assertEqual(reservation, 5 * self.envelope.max_payload_bytes + context + 131072 + 57 * 39 + 1)
            envelope = replace(self.envelope, coordinator_memory_cap_bytes=reservation - 1)
            with patch.object(h.store, "FramedStreamPullReader",
                    side_effect=AssertionError("Reservation must fail before opening PKF")) as reader, \
                    self.assertRaises(ValueError):
                self.readback_fixture(root, envelope=envelope)
            reader.assert_not_called()

    def test_v2_pre_cancel_and_pre_memory_breach_do_not_open_streams(self):
        class Cancelled:
            def is_set(self):
                return True
        with self.published_four_work() as (root, _):
            for options in ({"cancel": Cancelled()},
                    {"memory_probe": lambda: self.envelope.coordinator_memory_cap_bytes + 1}):
                with self.subTest(options=tuple(options)), \
                        patch.object(h.store, "FramedStreamPullReader",
                            side_effect=AssertionError("Containment must precede opening PKF")) as reader, \
                        self.assertRaises(ValueError):
                    self.readback_fixture(root, **options)
                reader.assert_not_called()

    def test_v2_mid_pull_cancel_wall_memory_and_pull_failure_close_every_reader(self):
        reader_type = h.store.FramedStreamPullReader
        original_init, original_pull = reader_type.__init__, reader_type.pull
        for case in ("cancel", "wall", "memory", "pull"):
            opened, pulled = [], [0]
            def initialize(reader, *args, **kwargs):
                original_init(reader, *args, **kwargs)
                opened.append(reader)
            def pull(reader):
                result = original_pull(reader)
                if result is not None:
                    pulled[0] += 1
                    if case == "pull":
                        raise h.store.StoreError("SLICE1N_PULL_FAILURE")
                return result
            class Cancel:
                def is_set(self):
                    return case == "cancel" and pulled[0] > 0
            def memory():
                return self.envelope.coordinator_memory_cap_bytes + 1 if case == "memory" and pulled[0] else 100
            def clock():
                return self.envelope.readback_wall_ms * 1_000_000 if case == "wall" and pulled[0] else 0
            with self.subTest(case=case), self.published_four_work() as (root, _), \
                    patch.object(reader_type, "__init__", new=initialize), \
                    patch.object(reader_type, "pull", new=pull), \
                    patch.object(h.time, "monotonic_ns", side_effect=clock):
                before = {path.name: path.read_bytes() for path in root.iterdir()}
                with self.assertRaises(ValueError):
                    self.readback_fixture(root, cancel=Cancel(), memory_probe=memory)
                self.assertGreater(pulled[0], 0)
                self.assertEqual(len(opened), len(execution.STREAM_NAMES) + 2)
                self.assertTrue(all(reader.completed_digest is None for reader in opened))
                self.assertTrue(all(reader._closed and reader._file.closed for reader in opened))
                self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)

    def test_v2_full_readback_owner_routes_only_exact_accepted_metadata_counts(self):
        plan, workload = self.full_metadata_fixture()
        marker = object()
        with self.forbidden_workloads(), tempfile.TemporaryDirectory() as directory, \
                patch.object(h, "_readback_v2_plan", return_value=marker) as lower, \
                patch.object(h.store, "FramedStreamPullReader", side_effect=AssertionError("Metadata route only")), \
                patch.object(h, "_construct_v2_materialization_work", side_effect=AssertionError("No full constructor")):
            self.assertIs(h._readback_synthetic_v2(directory, plan, workload, self.targets,
                                                 self.profile, self.envelope), marker)
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(lower.call_count, 1)
        self.assertIs(lower.call_args.args[1], plan)
        self.assertEqual(lower.call_args.args[5], (10000, 256, 128, 4, 256, 506))
        for bad_plan, bad_workload in ((list(plan), workload), (plan, object()),
                ((replace(plan[0], oracle_b_selected=not plan[0].oracle_b_selected),) + plan[1:], workload)):
            with self.subTest(plan_type=type(bad_plan), workload_type=type(bad_workload)), \
                    patch.object(h, "_readback_v2_plan", side_effect=AssertionError("No invalid lower readback")) as lower, \
                    self.assertRaises(ValueError):
                h._readback_synthetic_v2("unused", bad_plan, bad_workload, self.targets, self.profile, self.envelope)
            lower.assert_not_called()

    def test_v2_constructor_specific_rejection_is_runtime_provenance_not_family_policy(self):
        with self.published_four_work() as (root, _):
            node = self.metadata_node(root)
            fact = next(fact for fact in node["constructor_facts"]
                        if fact["constructor_kind"] == "text" and len(fact["trials"]) > 1)
            trial = next(trial for trial in fact["trials"] if trial["ordinal"] != fact["selected_trial_ordinal"])
            # This valid closed runtime reason intentionally need not equal the
            # family-only policy's reason. No rejected candidate is reconstructed.
            trial.update(eligible=False, rejection_reason="SYNTHETIC_TEXT_WNEW_CAP")
            self.write_metadata_node(root, node)
            observed = self.readback_fixture(root)
            self.assertTrue(observed.readback_complete and observed.constructor_rejections_are_runtime_provenance)
        with self.published_four_work() as (root, _):
            node = self.metadata_node(root)
            fact = next(fact for fact in node["constructor_facts"] if len(fact["trials"]) > 1)
            trial = next(trial for trial in fact["trials"] if trial["ordinal"] != fact["selected_trial_ordinal"])
            trial.update(actual_physical_bytes=fact["physical_target"], actual_logical_bytes=fact["logical_target"],
                physical_margin=0, logical_margin=0, eligible=False,
                rejection_reason="SYNTHETIC_BOTH_MINIMA_SHORTFALL")
            self.write_metadata_node(root, node)
            with self.assertRaises(ValueError):
                self.readback_fixture(root)

    def test_v2_constructor_selection_log_and_durable_selected_margins_fail_closed(self):
        cases = ("ordinal", "margin", "eligible_order", "too_many_trials")
        for case in cases:
            with self.subTest(case=case), self.published_four_work() as (root, _):
                node = self.metadata_node(root)
                fact = next(fact for fact in node["constructor_facts"]
                            if fact["constructor_kind"] == "text" and fact["selected_knob"] > 0)
                selected = next(trial for trial in fact["trials"]
                                if trial["ordinal"] == fact["selected_trial_ordinal"])
                if case == "ordinal":
                    fact["selected_trial_ordinal"] = 9
                elif case == "margin":
                    fact["physical_margin"] += 1
                elif case == "too_many_trials":
                    fact["trials"] = [dict(selected, ordinal=ordinal) for ordinal in range(1, 10)]
                else:
                    trial = next(trial for trial in fact["trials"]
                                 if trial["ordinal"] != fact["selected_trial_ordinal"])
                    ordinal = trial["ordinal"]
                    trial.update(selected)
                    trial.update(ordinal=ordinal, knob=fact["selected_knob"] - 1)
                self.write_metadata_node(root, node)
                with self.assertRaises(ValueError):
                    self.readback_fixture(root)

    def test_v2_metadata_publication_is_exclusive_durable_and_not_family_credit(self):
        original_open, original_fsync = Path.open, os.fsync
        actions = []
        class WriteProbe:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                self.stream.__enter__()
                return self
            def __exit__(self, *args):
                return self.stream.__exit__(*args)
            def write(self, data):
                actions.append("write")
                return self.stream.write(data)
            def flush(self):
                actions.append("flush")
                return self.stream.flush()
            def fileno(self):
                return self.stream.fileno()
        def opened(path, mode="r", *args, **kwargs):
            stream = original_open(path, mode, *args, **kwargs)
            if path.name == "materialization-v2.json" and mode == "xb":
                actions.append("exclusive")
                return WriteProbe(stream)
            return stream
        def fsync(descriptor):
            actions.append("fsync")
            return original_fsync(descriptor)
        with self.sealed_four_work() as root:
            pkf = {path.name: path.read_bytes() for path in root.iterdir()}
            with patch.object(Path, "open", new=opened), patch.object(os, "fsync", side_effect=fsync):
                metadata = h._publish_v2_materialization(root, self.result, self.targets, self.profile, self.envelope)
            self.assertEqual(actions, ["exclusive", "write", "flush", "fsync"])
            data = (root / "materialization-v2.json").read_bytes()
            self.assertEqual(metadata.committed_procedural_excess, self.result.ledger.committed_excess)
            self.assertEqual(metadata.attributable_experiment_bytes,
                             sum(value.physical_bytes for value in self.result.family_totals))
            self.assertEqual(sum(path.stat().st_size for path in root.iterdir()),
                             metadata.current_sealed_pkf_bytes + len(data))
            with self.assertRaises(FileExistsError):
                h._publish_v2_materialization(root, self.result, self.targets, self.profile, self.envelope)
            self.assertEqual(data, (root / "materialization-v2.json").read_bytes())
            self.assertEqual(pkf, {path.name: path.read_bytes() for path in root.glob("*.pkf")})

    def test_v2_publication_caps_fail_before_create_and_io_failure_preserves_sealed_prefix(self):
        from experiments import program_k_e2_r0_evidence as evidence
        with self.published_four_work() as (root, metadata):
            metadata_size = len(evidence.encode_materialization_v2(metadata))
        for case in ("metadata_cap", "archive_cap"):
            archive_bound = self.result.coordinator.archive_bytes + metadata_size - 1
            envelope = (replace(self.envelope, max_payload_bytes=metadata_size - 1) if case == "metadata_cap"
                else replace(self.envelope, archive_cap_bytes=archive_bound,
                             max_payload_bytes=min(self.envelope.max_payload_bytes, archive_bound)))
            with self.subTest(case=case), self.sealed_four_work() as root, \
                    patch.object(h, "_exclusive_bytes", side_effect=AssertionError("No pre-cap publication")) as write:
                with self.assertRaises(ValueError):
                    h._publish_v2_materialization(root, self.result, self.targets, self.profile, envelope)
                write.assert_not_called()
                self.assertFalse((root / "materialization-v2.json").exists())
        original_open = Path.open
        for case in ("write", "flush", "fsync"):
            class FailingWrite:
                def __init__(self, stream):
                    self.stream = stream
                def __enter__(self):
                    self.stream.__enter__()
                    return self
                def __exit__(self, *args):
                    return self.stream.__exit__(*args)
                def write(self, data):
                    if case == "write":
                        self.stream.write(data[:17])
                        raise OSError("SLICE1N_PUBLICATION_WRITE")
                    return self.stream.write(data)
                def flush(self):
                    self.stream.flush()
                    if case == "flush":
                        raise OSError("SLICE1N_PUBLICATION_FLUSH")
                def fileno(self):
                    return self.stream.fileno()
            def opened(path, mode="r", *args, **kwargs):
                stream = original_open(path, mode, *args, **kwargs)
                return FailingWrite(stream) if path.name == "materialization-v2.json" and mode == "xb" else stream
            def fsync(_):
                if case == "fsync":
                    raise OSError("SLICE1N_PUBLICATION_FSYNC")
            with self.subTest(case=case), self.sealed_four_work() as root:
                before = {path.name: path.read_bytes() for path in root.iterdir()}
                with patch.object(Path, "open", new=opened), patch.object(os, "fsync", side_effect=fsync), \
                        self.assertRaises(OSError):
                    h._publish_v2_materialization(root, self.result, self.targets, self.profile, self.envelope)
                self.assertEqual(before, {path.name: path.read_bytes() for path in root.glob("*.pkf")})
                self.assertFalse((root / "COMPLETE.json").exists())
                preserved = (root / "materialization-v2.json").read_bytes()
                with self.assertRaises(FileExistsError):
                    h._publish_v2_materialization(root, self.result, self.targets, self.profile, self.envelope)
                self.assertEqual((root / "materialization-v2.json").read_bytes(), preserved)

    def test_v2_full_owner_publication_failure_cannot_return_lower_success(self):
        plan, workload = self.full_metadata_fixture()
        calls = []
        def lower(*args, **kwargs):
            calls.append("sealed_lower_return")
            return self.result
        def publish(*args):
            calls.append("publication")
            self.assertIs(args[1], self.result)
            raise OSError("SLICE1N_PUBLICATION_FAILURE")
        with tempfile.TemporaryDirectory() as directory, self.forbidden_workloads(), \
                patch.object(h, "_materialize_v2_plan", side_effect=lower), \
                patch.object(h, "_publish_v2_materialization", side_effect=publish), \
                self.assertRaisesRegex(OSError, "SLICE1N_PUBLICATION_FAILURE"):
            h._materialize_synthetic_v2(plan, workload, self.targets, self.profile, self.envelope, directory)
        self.assertEqual(calls, ["sealed_lower_return", "publication"])


    @contextmanager
    def archive_count_domain(self):
        # Only the bounded count domain is extended. Production minimum,
        # capacity, per-family policy, and reconciliation arithmetic run intact.
        original = readiness._unit_counts_v2
        counts = self.counts(self.plan)
        def validate(value):
            if type(value) is tuple and all(type(count) is int for count in value) and value == counts:
                return value
            return original(value)
        with patch.object(readiness, "_unit_counts_v2", side_effect=validate):
            yield

    def archive_materialization_files(self):
        cls = type(self)
        if not hasattr(cls, "_archive_materialization_files"):
            with tempfile.TemporaryDirectory() as directory, self.archive_count_domain(), self.forbidden_workloads(), \
                    patch.object(operational.harness, "_coordinator_private_bytes", return_value=100), \
                    patch.object(h, "_construct_v2_materialization_work",
                        side_effect=lambda work, *args, **kwargs: self.constructed[work.position]):
                counts = self.counts(self.plan)
                ledger = h._new_v2_materialization_ledger(self.targets, counts)
                minimum = readiness.minimum_archive_preflight(self.targets.physical, counts, 0)
                materialization = h._materialize_v2_plan(self.plan, self.materialization_plan, self.targets,
                    self.profile, self.envelope, directory, counts, ledger, minimum)
                h._publish_v2_materialization(directory, materialization, self.targets, self.profile, self.envelope)
                cls._archive_materialization_files = {
                    path.name: path.read_bytes() for path in Path(directory).iterdir()}
        return cls._archive_materialization_files

    @contextmanager
    def archive_fixture(self, *, analysis_bytes=None, report_bytes=None):
        with tempfile.TemporaryDirectory() as directory, self.archive_count_domain():
            root = Path(directory) / "experiment"
            streams = root / "streams"
            streams.mkdir(parents=True)
            for name, raw in self.archive_materialization_files().items():
                (streams / name).write_bytes(raw)
            with self.independent_readback_guards(), \
                    patch.object(operational.harness, "_coordinator_private_bytes", return_value=100):
                readback = h._readback_v2_plan(streams, self.plan, self.targets, self.profile,
                                               self.envelope, self.counts(self.plan))
            self.assertFalse((streams / "qualification_identity.pkf").exists())
            post = root / "postprocessing"
            post.mkdir()
            # Registry-valid transport fixtures only: they deliberately make no
            # semantic qualification, postprocessing, or effectiveness claim.
            with h.store.FramedStreamWriter(streams, "qualification_identity",
                    physical.context_for("qualification_identity", self.profile.sha256)) as writer:
                writer.append((0,), self.plan[0].runtime)
                qualification = writer.seal()
            event = records.OperationEventRecord(records.Phase.EXECUTION, "slice1o-transport-only",
                records.EventKind.PROGRESS, 0, 0, records.OperationStatus.RUNNING)
            with h.store.FramedStreamWriter(post, "postprocessing_operations",
                    physical.context_for("postprocessing_operations", self.profile.sha256)) as writer:
                writer.append((0,), event)
                postprocessing = writer.seal()
            analysis_bytes = (b'{"classification":"TRANSPORT_FIXTURE_ONLY"}\n'
                              if analysis_bytes is None else analysis_bytes)
            report_bytes = (b"<!doctype html><p>Transport fixture only.</p>\n"
                            if report_bytes is None else report_bytes)
            (post / "analysis.json").write_bytes(analysis_bytes)
            (post / "report.html").write_bytes(report_bytes)
            yield dict(root=root, readback=readback, profile=self.profile, envelope=self.envelope,
                qualification_identity_seal=qualification, postprocessing_operations_seal=postprocessing,
                analysis_file=h.FileFact("postprocessing/analysis.json", len(analysis_bytes), h.sha256(analysis_bytes).hexdigest()),
                report_file=h.FileFact("postprocessing/report.html", len(report_bytes), h.sha256(report_bytes).hexdigest()),
                selection_receipt_sha256="a" * 64, corpus_sha256="b" * 64, source_sha256="c" * 64)

    @contextmanager
    def archive_close_guards(self):
        with self.independent_readback_guards(), _EvidenceExitStack() as stack:
            for name in ("_readback_v2_plan", "_readback_synthetic_v2", "_postprocess_r0b", "launch_r0b",
                         "_fact_node", "_fact_read"):
                stack.enter_context(patch.object(h, name,
                    side_effect=AssertionError("Archive closure cannot run semantic owners or V1 codecs")))
            stack.enter_context(patch.object(h.qualification, "write_identity",
                side_effect=AssertionError("Archive closure cannot generate qualification identity")))
            yield

    def close_archive(self, fixture, **changes):
        with self.archive_close_guards():
            return h._close_v2_experiment_archive(**(fixture | changes))

    def validate_archive(self, fixture, **changes):
        arguments = {name: fixture[name] for name in (
            "root", "profile", "envelope", "selection_receipt_sha256", "corpus_sha256", "source_sha256")}
        with self.archive_close_guards():
            return h._validate_closed_v2_experiment_archive(**(arguments | changes))

    @staticmethod
    def archive_bytes(root):
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*") if path.is_file()}

    def test_v2_archive_real_four_work_close_inventory_and_structural_validator(self):
        from experiments import program_k_e2_r0_evidence as evidence
        with self.archive_fixture() as fixture:
            checks, progress = [], []
            closed = self.close_archive(fixture, check=lambda: checks.append(None),
                                        progress=lambda *event: progress.append(event))
            root, readback = fixture["root"], fixture["readback"]
            actual = self.archive_bytes(root)
            self.assertEqual(set(actual), set(evidence.V2_ARCHIVE_FINAL_PATHS))
            self.assertEqual(len(actual), 64)
            self.assertEqual({path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir()},
                             {"streams", "postprocessing"})
            self.assertFalse(any(name.endswith(".jsonl") for name in actual))
            accounting, manifest, completion = closed.accounting, closed.manifest, closed.completion
            attributable = sum(len(actual[path]) for path in evidence.V2_ARCHIVE_ATTRIBUTABLE_PATHS)
            fixed = sum(len(raw) for path, raw in actual.items() if path not in evidence.V2_ARCHIVE_ATTRIBUTABLE_PATHS)
            self.assertEqual(len(evidence.V2_ARCHIVE_ATTRIBUTABLE_PATHS), 53)
            self.assertEqual(accounting.attributable_bytes, attributable)
            self.assertEqual(attributable, sum(value.physical_bytes for value in readback.family_totals))
            self.assertEqual((accounting.fixed_allowance_bytes, accounting.archive_bytes), (fixed, attributable + fixed))
            self.assertEqual(tuple(value.path for value in accounting.files), tuple(sorted(actual)))
            self.assertEqual(len(accounting.files), len(set(value.path for value in accounting.files)))
            for fact in accounting.files:
                self.assertEqual((fact.byte_length, fact.sha256), (len(actual[fact.path]), h.sha256(actual[fact.path]).hexdigest()))
            self.assertEqual((manifest.attributable_bytes, manifest.projected_fixed_bytes,
                manifest.projected_archive_bytes), (attributable, fixed, attributable + fixed))
            self.assertGreaterEqual(accounting.archive_bytes, readback.physical_minimum_total + fixed)
            self.assertEqual((manifest.e_final, manifest.b_proc, manifest.remaining_procedural_budget),
                             (readback.e_final, readback.b_proc, readback.remaining_procedural_budget))
            expected_minimum = sum(count * getattr(self.targets.physical, family)
                                   for family, count in readback.family_counts)
            self.assertEqual(readback.physical_minimum_total, expected_minimum)
            self.assertEqual(readback.e_final, attributable - expected_minimum)
            self.assertEqual(manifest.codec_profile_sha256, self.profile.sha256.hex())
            self.assertTrue(manifest.materialization_readback_complete and manifest.synthetic_non_evidence)
            self.assertFalse(manifest.runtime_peak_is_independent)
            self.assertTrue(manifest.constructor_rejections_are_runtime_provenance)
            self.assertEqual(manifest.classification, "SYNTHETIC_NON_EFFECTIVENESS")
            self.assertEqual(manifest.materialization_file.path, "streams/materialization-v2.json")
            self.assertEqual(manifest.qualification_identity_stream, fixture["qualification_identity_seal"])
            self.assertEqual(manifest.postprocessing_operations_stream, fixture["postprocessing_operations_seal"])
            self.assertEqual(manifest.analysis_file.sha256, fixture["analysis_file"].sha256)
            self.assertEqual(manifest.report_file.sha256, fixture["report_file"].sha256)
            self.assertEqual(evidence.encode_archive_manifest_v2(manifest), actual["manifest.json"])
            self.assertEqual(evidence.decode_archive_manifest_v2(actual["manifest.json"],
                expected_profile_sha256=self.profile.sha256.hex()), manifest)
            pre = tuple(value for value in accounting.files if value.path not in ("manifest.json", "COMPLETE.json"))
            self.assertEqual(tuple((v.path, v.byte_length, v.sha256) for v in manifest.inventory_before_manifest_receipt),
                             tuple((v.path, v.byte_length, v.sha256) for v in pre))
            self.assertNotIn("manifest_sha256", json.loads(actual["manifest.json"]))
            self.assertEqual(completion.manifest_sha256, h.sha256(actual["manifest.json"]).hexdigest())
            self.assertEqual(h.store.read_completion_receipt(root), completion)
            status = json.loads(actual["status.json"])
            self.assertFalse(status["archive_closed"])
            self.assertTrue(status["materialization_readback_complete"])
            self.assertTrue(status["materialization_integrity_reauthenticated"])
            self.assertTrue(status["support_files_present"] and status["cleanup_complete"])
            before = self.archive_bytes(root)
            self.assertEqual(self.validate_archive(fixture), closed)
            self.assertEqual(self.archive_bytes(root), before)
            self.assertGreaterEqual(len(checks), len(actual))
            order, last = [], {}
            for stage, done, total in progress:
                if stage not in last:
                    order.append(stage)
                    self.assertEqual(done, 0)
                else:
                    self.assertEqual(total, last[stage][1])
                    self.assertGreaterEqual(done, last[stage][0])
                self.assertLessEqual(done, total)
                last[stage] = done, total
            self.assertEqual(tuple(order), ("support_authentication", "coordinator_status", "manifest_inventory",
                "projected_accounting", "manifest_write", "completion_write", "final_inventory", "final_accounting"))
            self.assertTrue(all(done == total for done, total in last.values()))
            self.assertEqual(progress[-1][0], "final_accounting")
            self.assertFalse(hasattr(closed, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                closed.accounting = None
            print("SLICE1O_BOUNDED_CLOSE " + json.dumps({
                "attributable_bytes": attributable, "fixed_bytes": fixed,
                "archive_bytes": accounting.archive_bytes, "physical_minimum": readback.physical_minimum_total,
                "b_proc": readback.b_proc, "e_final": readback.e_final,
                "remaining": readback.remaining_procedural_budget,
                "manifest_bytes": len(actual["manifest.json"]), "completion_bytes": len(actual["COMPLETE.json"])},
                sort_keys=True, separators=(",", ":")))

    def test_v2_archive_manifest_registry_and_receipt_sorted_orders_reconcile_exactly(self):
        with self.archive_fixture() as fixture:
            closed = self.close_archive(fixture)
            seals = closed.manifest.streams
            names = execution.STREAM_NAMES + ("operations", "resources", "qualification_identity", "postprocessing_operations")
            self.assertEqual(tuple(value.name for value in seals), names)
            self.assertEqual(len(set(names)), 57)
            self.assertNotEqual(names, tuple(sorted(names)))
            with self.assertRaises(records.RecordError):
                replace(closed.completion, streams=seals)
            ordered = tuple(sorted(seals, key=lambda value: value.name))
            self.assertEqual(replace(closed.completion, streams=ordered), closed.completion)
            self.assertEqual({value.name: value for value in seals},
                             {value.name: value for value in closed.completion.streams})
            self.assertEqual(tuple(value.name for value in closed.completion.streams), tuple(sorted(names)))
            original = records.encode(closed.completion)
            for case in ("same_name_changed_digest", "missing", "extra", "duplicate", "wrong_order"):
                candidate = closed.completion
                if case == "same_name_changed_digest":
                    values = (replace(ordered[0], sha256="0" * 64),) + ordered[1:]
                elif case == "missing":
                    values = ordered[:-1]
                elif case == "extra":
                    values = tuple(sorted(ordered + (records.StreamDigest("extra", "0" * 64, 0, 0),), key=lambda value: value.name))
                elif case == "duplicate":
                    values = (ordered[0],) + ordered
                else:
                    values = tuple(reversed(ordered))
                with self.subTest(case=case):
                    if case in ("duplicate", "wrong_order"):
                        with self.assertRaises(records.RecordError):
                            replace(candidate, streams=values)
                        continue
                    candidate = replace(candidate, streams=values)
                    (fixture["root"] / "COMPLETE.json").write_bytes(records.encode(candidate) + b"\n")
                    with self.assertRaises(ValueError):
                        self.validate_archive(fixture)
                    (fixture["root"] / "COMPLETE.json").write_bytes(original + b"\n")

    def test_v2_archive_close_reauthenticates_materialization_and_support_before_new_files(self):
        paths = ("streams/boards.pkf", "streams/operations.pkf", "streams/resources.pkf",
            "streams/materialization-v2.json", "streams/qualification_identity.pkf",
            "postprocessing/postprocessing_operations.pkf", "postprocessing/analysis.json", "postprocessing/report.html")
        for name in paths:
            with self.subTest(path=name), self.archive_fixture() as fixture:
                path = fixture["root"] / name
                raw = bytearray(path.read_bytes())
                raw[-1] ^= 1
                path.write_bytes(raw)
                before = self.archive_bytes(fixture["root"])
                with self.assertRaises(ValueError):
                    self.close_archive(fixture)
                self.assertEqual(self.archive_bytes(fixture["root"]), before)
                self.assertFalse((fixture["root"] / "coordinator.json").exists())
                self.assertFalse((fixture["root"] / "COMPLETE.json").exists())

    def test_v2_archive_closed_validator_rejects_independent_final_file_tampering(self):
        paths = ("streams/boards.pkf", "streams/operations.pkf", "streams/qualification_identity.pkf",
            "postprocessing/postprocessing_operations.pkf", "streams/materialization-v2.json",
            "postprocessing/analysis.json", "postprocessing/report.html", "coordinator.json", "status.json",
            "manifest.json", "COMPLETE.json")
        with self.archive_fixture() as fixture:
            self.close_archive(fixture)
            originals = self.archive_bytes(fixture["root"])
            for name in paths:
                with self.subTest(path=name):
                    path = fixture["root"] / name
                    raw = bytearray(originals[name])
                    raw[-1] ^= 1
                    path.write_bytes(raw)
                    before = self.archive_bytes(fixture["root"])
                    with self.assertRaises(ValueError):
                        self.validate_archive(fixture)
                    self.assertEqual(self.archive_bytes(fixture["root"]), before)
                    path.write_bytes(originals[name])  # Separate tamper case, never production repair.

    def test_v2_archive_rejects_missing_extra_directories_links_and_preexisting_close_files(self):
        for case in ("missing", "extra_pkf", "extra_jsonl", "extra_file", "extra_directory", "manifest", "complete"):
            with self.subTest(case=case), self.archive_fixture() as fixture:
                root = fixture["root"]
                if case == "missing":
                    (root / "postprocessing/report.html").unlink()
                elif case == "extra_directory":
                    (root / "unexpected").mkdir()
                else:
                    name = {"extra_pkf": "streams/extra.pkf", "extra_jsonl": "streams/boards.jsonl",
                        "extra_file": "unaccounted.bin", "manifest": "manifest.json", "complete": "COMPLETE.json"}[case]
                    (root / name).write_bytes(b"unexpected")
                before = self.archive_bytes(root)
                inventories = []
                original = h._inventory
                def inventory(*args, **kwargs):
                    result = original(*args, **kwargs)
                    inventories.append(result)
                    return result
                with patch.object(h, "_inventory", side_effect=inventory), self.assertRaises(ValueError):
                    self.close_archive(fixture)
                self.assertEqual(self.archive_bytes(root), before)
                self.assertFalse((root / "coordinator.json").exists())
                self.assertTrue(inventories)
                if case in ("extra_pkf", "extra_jsonl", "extra_file"):
                    self.assertIn(name, {value.path for value in inventories[0]})
        for link_method in ("is_symlink", "is_junction"):
            with self.subTest(link=link_method), self.archive_fixture() as fixture:
                target = fixture["root"] / "postprocessing/report.html"
                original = getattr(Path, link_method)
                def link(path):
                    return path == target or original(path)
                before = self.archive_bytes(fixture["root"])
                with patch.object(Path, link_method, new=link), self.assertRaises(ValueError):
                    self.close_archive(fixture)
                self.assertEqual(self.archive_bytes(fixture["root"]), before)

    def test_v2_archive_exact_readback_support_and_authority_inputs_fail_before_publication(self):
        class DigestSubclass(str):
            pass
        with self.archive_fixture() as fixture:
            root, readback = fixture["root"], fixture["readback"]
            changes = [{"readback": object()}, {"analysis_file": object()},
                {"qualification_identity_seal": fixture["postprocessing_operations_seal"]},
                {"postprocessing_operations_seal": fixture["qualification_identity_seal"]},
                {"analysis_file": replace(fixture["analysis_file"], path="analysis.json")},
                {"report_file": replace(fixture["report_file"], sha256="0" * 64)}]
            for name in ("readback_complete", "progress_complete", "synthetic_non_evidence",
                         "constructor_rejections_are_runtime_provenance"):
                changes.append({"readback": replace(readback, **{name: False})})
            changes.extend(({"readback": replace(readback, runtime_peak_is_independent=True)},
                {"readback": replace(readback, streams=readback.streams[::-1])},
                {"readback": replace(readback, e_final=readback.e_final + 1)},
                {"readback": replace(readback, remaining_procedural_budget=readback.remaining_procedural_budget + 1)},
                {"readback": replace(readback, materialization_metadata_sha256="0" * 64)},
                {"readback": replace(readback, materialization_metadata_byte_length=readback.materialization_metadata_byte_length + 1)}))
            for name in ("selection_receipt_sha256", "corpus_sha256", "source_sha256"):
                for value in (True, "A" * 64, "0" * 63, DigestSubclass("0" * 64)):
                    changes.append({name: value})
            before = self.archive_bytes(root)
            for index, change in enumerate(changes):
                with self.subTest(case=index), self.assertRaises(ValueError):
                    self.close_archive(fixture, **change)
                self.assertEqual(self.archive_bytes(root), before)
                self.assertFalse((root / "coordinator.json").exists())

    def test_v2_archive_projected_exact_caps_and_cap_plus_one_without_large_files(self):
        fixed_cap, archive_cap = identity.FIXED_REPORT_RECEIPT_ALLOWANCE, identity.MAX_ARCHIVE_BYTES
        def files(attributable, supporting):
            return (h.FileFact("coordinator.json", supporting, "0" * 64),
                    h.FileFact("streams/boards.pkf", attributable, "1" * 64))
        projected = dict(manifest_bytes=17, completion_bytes=23)
        self.assertEqual(h._v2_archive_partition(files(1, fixed_cap - 40), **projected),
                         (1, fixed_cap, fixed_cap + 1))
        with self.assertRaisesRegex(ValueError, "V2_FIXED_ALLOWANCE_CAP"):
            h._v2_archive_partition(files(1, fixed_cap - 39), **projected)
        self.assertEqual(h._v2_archive_partition(files(archive_cap - 100, 60), **projected),
                         (archive_cap - 100, 100, archive_cap))
        with self.assertRaisesRegex(ValueError, "V2_ARCHIVE_CAP"):
            h._v2_archive_partition(files(archive_cap - 99, 60), **projected)
        original = h._v2_archive_partition
        for reason in ("V2_FIXED_ALLOWANCE_CAP", "V2_ARCHIVE_CAP"):
            reached = []
            def partition(values, *, manifest_bytes=0, completion_bytes=0):
                if manifest_bytes or completion_bytes:
                    reached.append((manifest_bytes, completion_bytes))
                    extras = manifest_bytes + completion_bytes
                    virtual = (files(1, fixed_cap + 1 - extras) if reason == "V2_FIXED_ALLOWANCE_CAP"
                               else files(archive_cap + 1 - extras, 0))
                    return original(virtual, manifest_bytes=manifest_bytes, completion_bytes=completion_bytes)
                return original(values)
            with self.subTest(reason=reason), self.archive_fixture() as fixture, \
                    patch.object(h, "_v2_archive_partition", side_effect=partition):
                with self.assertRaisesRegex(ValueError, reason):
                    self.close_archive(fixture)
                self.assertEqual(len(reached), 1)
                self.assertTrue(all(value > 0 for value in reached[0]))
                self.assertTrue((fixture["root"] / "coordinator.json").exists())
                self.assertTrue((fixture["root"] / "status.json").exists())
                self.assertFalse((fixture["root"] / "manifest.json").exists())
                self.assertFalse((fixture["root"] / "COMPLETE.json").exists())

    def test_v2_archive_fixed_support_and_logical_surplus_never_provide_family_credit(self):
        outcomes = []
        for padding in (0, 1000):
            with self.archive_fixture(report_bytes=b"<p>Transport only.</p>" + b"x" * padding) as fixture:
                closed = self.close_archive(fixture)
                outcomes.append(closed)
        smaller, larger = outcomes
        self.assertLess(smaller.accounting.fixed_allowance_bytes, larger.accounting.fixed_allowance_bytes)
        self.assertEqual(smaller.accounting.attributable_bytes, larger.accounting.attributable_bytes)
        self.assertEqual((smaller.manifest.b_proc, smaller.manifest.e_final, smaller.manifest.remaining_procedural_budget),
                         (larger.manifest.b_proc, larger.manifest.e_final, larger.manifest.remaining_procedural_budget))
        with self.archive_count_domain():
            manifest = smaller.manifest
            totals = (replace(manifest.family_totals[0], logical_bytes=manifest.family_totals[0].logical_bytes + 1000),) + manifest.family_totals[1:]
            h._v2_archive_reconcile(manifest.targets, manifest.family_counts, totals,
                manifest.physical_minimum_total, manifest.b_proc, manifest.e_final, manifest.remaining_procedural_budget)
            before = h._v2_archive_partition(smaller.accounting.files)
            self.assertEqual(before, (smaller.accounting.attributable_bytes,
                                     smaller.accounting.fixed_allowance_bytes, smaller.accounting.archive_bytes))
            self.assertEqual(before, h._v2_archive_partition(smaller.accounting.files))
            primary_floor = manifest.family_counts[0][1] * manifest.targets.physical.primary
            short = (replace(manifest.family_totals[0], physical_bytes=primary_floor - 1, physical_excess=0),) + manifest.family_totals[1:]
            with self.assertRaisesRegex(ValueError, "V2_ARCHIVE_DUAL_MINIMUM_SHORTFALL"):
                h._v2_archive_reconcile(manifest.targets, manifest.family_counts, short,
                    manifest.physical_minimum_total, manifest.b_proc, manifest.e_final, manifest.remaining_procedural_budget)

    def test_v2_archive_check_and_progress_failures_preserve_prefix_and_cannot_claim_close(self):
        stages = ("support_authentication", "coordinator_status", "manifest_inventory", "projected_accounting",
                  "manifest_write", "completion_write", "final_inventory", "final_accounting")
        for stage in stages:
            with self.subTest(stage=stage), self.archive_fixture() as fixture:
                observed = []
                marker = RuntimeError("bounded close progress failure")
                def progress(current, done, total):
                    observed.append((current, done, total))
                    if current == stage and done == 0:
                        raise marker
                with self.assertRaises(RuntimeError) as caught:
                    self.close_archive(fixture, progress=progress)
                self.assertIs(caught.exception, marker)
                self.assertNotIn(("final_accounting", 1, 1), observed)
                if stage in stages[:5]:
                    self.assertFalse((fixture["root"] / "manifest.json").exists())
                if stage in stages[:6]:
                    self.assertFalse((fixture["root"] / "COMPLETE.json").exists())
        with self.archive_fixture() as fixture:
            before = self.archive_bytes(fixture["root"])
            marker = KeyboardInterrupt("bounded close containment failure")
            def check():
                raise marker
            with self.assertRaises(KeyboardInterrupt) as caught:
                self.close_archive(fixture, check=check)
            self.assertIs(caught.exception, marker)
            self.assertEqual(self.archive_bytes(fixture["root"]), before)

    def test_v2_archive_partial_publication_and_final_inventory_failure_never_return_success(self):
        for case in ("manifest", "completion_write", "completion_fsync", "final_inventory"):
            with self.subTest(case=case), self.archive_fixture() as fixture, _EvidenceExitStack() as stack:
                root = fixture["root"]
                before = self.archive_bytes(root)
                original_exclusive, original_inventory = h._exclusive_bytes, h._inventory
                original_receipt, original_fsync = h.store.write_completion_receipt, os.fsync
                completion_active = [False]
                def exclusive(path, data):
                    if case == "manifest" and Path(path).name == "manifest.json":
                        with Path(path).open("xb") as stream:
                            stream.write(data[:17])
                        raise OSError("SLICE1O_PARTIAL_MANIFEST")
                    return original_exclusive(path, data)
                def write_complete(stream, data):
                    stream.write(data[:17])
                    raise OSError("SLICE1O_PARTIAL_COMPLETION")
                def receipt(*args, **kwargs):
                    completion_active[0] = True
                    try:
                        return original_receipt(*args, **kwargs)
                    finally:
                        completion_active[0] = False
                def fsync(descriptor):
                    if case == "completion_fsync" and completion_active[0]:
                        raise OSError("SLICE1O_COMPLETION_FSYNC")
                    return original_fsync(descriptor)
                def inventory(*args, **kwargs):
                    values = original_inventory(*args, **kwargs)
                    if case == "final_inventory" and (root / "COMPLETE.json").exists():
                        return tuple(replace(value, byte_length=value.byte_length + 1)
                                     if value.path == "status.json" else value for value in values)
                    return values
                stack.enter_context(patch.object(h, "_exclusive_bytes", side_effect=exclusive))
                stack.enter_context(patch.object(h, "_inventory", side_effect=inventory))
                stack.enter_context(patch.object(h.store, "write_completion_receipt", side_effect=receipt))
                stack.enter_context(patch.object(os, "fsync", side_effect=fsync))
                if case == "completion_write":
                    stack.enter_context(patch.object(h.store, "_write_complete", side_effect=write_complete))
                events = []
                with self.assertRaises((ValueError, OSError)):
                    self.close_archive(fixture, progress=lambda *event: events.append(event))
                self.assertNotIn(("final_accounting", 1, 1), events)
                after = self.archive_bytes(root)
                self.assertTrue(all(after[name] == raw for name, raw in before.items()))
                self.assertTrue((root / "coordinator.json").exists() and (root / "status.json").exists())
                if case == "manifest":
                    self.assertEqual((root / "manifest.json").stat().st_size, 17)
                    self.assertFalse((root / "COMPLETE.json").exists())
                elif case == "completion_write":
                    self.assertEqual((root / "COMPLETE.json").stat().st_size, 17)
                else:
                    self.assertTrue((root / "COMPLETE.json").exists())
                with self.assertRaises(ValueError):
                    self.close_archive(fixture)
                self.assertEqual(self.archive_bytes(root), after)

    def test_v2_archive_check_callback_interrupts_during_inventory(self):
        with self.archive_fixture() as fixture:
            original = h._inventory
            active, checks = [False], []
            marker = RuntimeError("SLICE1O_INVENTORY_CHECK")
            def inventory(*args, **kwargs):
                active[0] = True
                try:
                    return original(*args, **kwargs)
                finally:
                    active[0] = False
            def check():
                if active[0]:
                    checks.append(True)
                    if len(checks) == 3:
                        raise marker
            before = self.archive_bytes(fixture["root"])
            with patch.object(h, "_inventory", side_effect=inventory), self.assertRaises(RuntimeError) as caught:
                self.close_archive(fixture, check=check)
            self.assertIs(caught.exception, marker)
            self.assertEqual(len(checks), 3)
            self.assertEqual(self.archive_bytes(fixture["root"]), before)

    def test_v2_archive_canonical_materialization_change_after_readback_is_detected(self):
        with self.archive_fixture() as fixture:
            streams = fixture["root"] / "streams"
            node = self.metadata_node(streams)
            node["runtime_monitor_peak_coordinator_private_bytes"] += 1
            self.write_metadata_node(streams, node)
            before = self.archive_bytes(fixture["root"])
            with self.assertRaisesRegex(ValueError, "V2_ARCHIVE_METADATA_CHANGED_AFTER_READBACK"):
                self.close_archive(fixture)
            self.assertEqual(self.archive_bytes(fixture["root"]), before)

    def test_v2_archive_written_coordinator_status_drift_prevents_manifest(self):
        for name in ("coordinator.json", "status.json"):
            with self.subTest(path=name), self.archive_fixture() as fixture:
                changed = []
                def progress(stage, done, total):
                    if stage == "coordinator_status" and done == 1:
                        path = fixture["root"] / name
                        raw = bytearray(path.read_bytes())
                        raw[-1] ^= 1
                        path.write_bytes(raw)
                        changed.append(bytes(raw))
                with self.assertRaisesRegex(ValueError, "V2_ARCHIVE_PRE_MANIFEST_DRIFT"):
                    self.close_archive(fixture, progress=progress)
                self.assertEqual((fixture["root"] / name).read_bytes(), changed[0])
                self.assertFalse((fixture["root"] / "manifest.json").exists())
                self.assertFalse((fixture["root"] / "COMPLETE.json").exists())

    def test_v2_archive_manifest_materialization_and_authority_binding_survive_receipt_rehash(self):
        with self.archive_fixture() as fixture:
            closed = self.close_archive(fixture)
            path = fixture["root"] / "manifest.json"
            original_manifest = path.read_bytes()
            original_completion = (fixture["root"] / "COMPLETE.json").read_bytes()
            cases = {
                "schema": lambda node: node.update(schema="program-k-e2-r0b-experiment/v1"),
                "registry_order": lambda node: node["streams"].reverse(),
                "source_identity": lambda node: node.update(source_plan_identity="0" * 64),
                "materialization_identity": lambda node: node.update(materialization_plan_identity="0" * 64),
                "family_count": lambda node: node["family_counts"][0].__setitem__(1, 5),
                "targets": lambda node: node["targets"]["logical"].update(primary=node["targets"]["logical"]["primary"] + 1),
                "family_total": lambda node: node["family_totals"][0].update(logical_bytes=node["family_totals"][0]["logical_bytes"] + 1),
                "minimum": lambda node: node.update(physical_minimum_total=node["physical_minimum_total"] + 1),
                "b_proc": lambda node: node.update(b_proc=node["b_proc"] + 1),
                "e_final": lambda node: node.update(e_final=node["e_final"] + 1),
                "remaining": lambda node: node.update(remaining_procedural_budget=node["remaining_procedural_budget"] + 1),
                "operation_count": lambda node: node.update(durable_operation_count=node["durable_operation_count"] + 1),
                "primary_count": lambda node: node.update(durable_primary_count=node["durable_primary_count"] + 1),
                "runtime_peak_label": lambda node: node.update(runtime_peak_is_independent=True),
                "sample_above_runtime_peak": lambda node: node.update(durable_sample_max_coordinator_private_bytes=node["runtime_monitor_peak_coordinator_private_bytes"] + 1),
                "selection_authority": lambda node: node.update(selection_receipt_sha256="0" * 64),
            }
            for name, mutate in cases.items():
                with self.subTest(case=name):
                    node = json.loads(original_manifest)
                    mutate(node)
                    data = json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
                    path.write_bytes(data)
                    receipt = replace(closed.completion, manifest_sha256=h.sha256(data).hexdigest())
                    (fixture["root"] / "COMPLETE.json").write_bytes(records.encode(receipt) + b"\n")
                    with self.assertRaises(ValueError):
                        self.validate_archive(fixture)
            path.write_bytes(original_manifest)
            (fixture["root"] / "COMPLETE.json").write_bytes(original_completion)
            for name in ("selection_receipt_sha256", "corpus_sha256", "source_sha256"):
                with self.subTest(external_authority=name), self.assertRaises(ValueError):
                    self.validate_archive(fixture, **{name: "0" * 64})




# Slice 1P shares this non-TestCase fixture with qualification tests. Importing
# these helpers never registers or re-runs another module's unittest classes.
_SLICE1P_DATA = None


@contextmanager
def _slice1p_count_domain(counts):
    original = readiness._unit_counts_v2
    def validate(value):
        if type(value) is tuple and all(type(v) is int for v in value) and value == counts:
            return value
        return original(value)
    with patch.object(readiness, "_unit_counts_v2", side_effect=validate):
        yield


@contextmanager
def _slice1p_plan_domain(plan):
    # Four explicit coverage positions cannot obey production's minimum-256
    # selector domain. Only this exact immutable fixture plan is admitted.
    original = operational.validate_work_plan
    def validate(value):
        if type(value) is tuple and value == plan:
            if len(value) != 4 or tuple(v.position for v in value) != (0, 1, 2, 3):
                raise AssertionError("Exact bounded Slice 1P plan required")
            for work in value:
                execution.BoardWork.__post_init__(work)
            return value
        return original(value)
    with patch.object(operational, "validate_work_plan", side_effect=validate):
        yield


@contextmanager
def _slice1p_semantic_guards(*, allow_bootstrap=False):
    import socket
    with _EvidenceExitStack() as stack:
        forbidden = [(execution, "_materialize_board"), (execution, "MinesweeperEngine"),
            (execution.runner, "run_k_p0"), (execution.runner, "run_k_control"),
            (readiness, "search_synthetic_corpus"), (readiness, "target_counts"),
            (socket, "create_connection"), (socket.socket, "connect"),
            (h.qualification, "capture_sources"), (h.qualification, "_identity_records"),
            (h.qualification, "_Lane"), (h.store, "scan_stream"), (h.store, "scan_framed_stream"),
            (physical, "capture_qualified_profile"), (operational, "_bind_prior_bundle"),
            (execution, "encode_bundle_v2")]
        forbidden += [(h, name) for name in ("construct_reference_v2", "construct_text_family_v2",
            "_materialize_v2_plan", "_materialize_v2_unit", "_construct_v2_materialization_work",
            "_readback_synthetic_v2", "_readback_v2_plan", "_v2_readback_unit", "_v2_readback_prior",
            "_v2_readback_constructor", "_v2_readback_support", "_capture_qualified_codec_profile")]
        if not allow_bootstrap:
            forbidden.append((h.analysis, "_shared_bootstrap"))
        for owner, name in forbidden:
            stack.enter_context(patch.object(owner, name,
                side_effect=AssertionError("Slice 1P must consume durable RF02 independently")))
        stack.enter_context(patch("benchmark_board.generate_board",
                                  side_effect=AssertionError("No board generation")))
        yield


def _slice1p_fixture_data():
    global _SLICE1P_DATA
    if _SLICE1P_DATA is not None:
        return _SLICE1P_DATA
    runtime = records.RuntimeIdentity(platform.python_implementation(), platform.python_version(),
        os.name, platform.platform(), platform.machine(), None)
    source = tuple(replace(work, runtime=runtime, run_id="synthetic-i7-slice1p-four-work")
                   for work in V2SyntheticMaterializerTests.source_plan())
    plan = h._v2_materialization_plan(source)
    counts = V2SyntheticMaterializerTests.counts(plan)
    profile = h._capture_qualified_codec_profile()
    provisional = readiness.DualComponentSizes(*(readiness.ComponentSizes(1, 1, 1, 1, 1, 1)
                                                 for _ in range(2)))
    envelope = SyntheticMaterializationTests.envelope(max_payload_bytes=1048576)
    with V2SyntheticMaterializerTests.forbidden_workloads():
        baselines = []
        for work in plan:
            if work.k_control_selected or work.determinism_selected:
                baselines.extend(h._reference_bundles(work, h._reference_prefix(0), 0))
            else:
                baselines.append(h._build_primary_v2_baseline(work, provisional, profile, envelope)[0])
        cap = max(execution.legacy_bundle_size(bundle) for bundle in baselines) + 4096
        envelope = replace(envelope, max_payload_bytes=cap)
        def view(bundle):
            return execution.decode_bundle_view_v2(execution.encode_bundle_v2(bundle, profile.sha256,
                max_payload_bytes=cap), profile.sha256, max_payload_bytes=cap)
        views = tuple(view(bundle) for bundle in baselines)
        logical = readiness.ComponentSizes(*(max(_text_family_metrics(v, family)[1] for v in views)
                                             for family in readiness.V2_FAMILIES))
        # Calibrate only bounded fixture targets, at canonical h=0. The real
        # constructors, trial budget, eligibility and arithmetic remain intact.
        floors = {}
        for family in readiness.V2_FAMILIES[:-1]:
            measured = []
            multiplicity = 4 if family.startswith("oracle_") else 1
            for bundle, baseline in zip(baselines, views):
                if not _text_family_metrics(baseline, family)[1]:
                    continue
                fixed = _text_with_literal(bundle, family, "SYNTHETIC_NON_EVIDENCE|L:|H:")
                ell = (max(0, getattr(logical, family) - _text_logical_bytes(fixed, family))
                       + multiplicity - 1) // multiplicity
                candidate = _text_with_literal(fixed, family,
                    "SYNTHETIC_NON_EVIDENCE|L:" + "x" * ell + "|H:")
                measured.append(_text_family_metrics(view(candidate), family))
            floor = min(v[0] for v in measured)
            if not all(floor <= p <= floor + 4096 and length >= getattr(logical, family)
                       for p, length in measured):
                raise AssertionError(("No common bounded Slice 1P text window", family, measured))
            floors[family] = floor
        targets = readiness.DualComponentSizes(readiness.ComponentSizes(**floors, reference=1),
            replace(logical, reference=logical.reference + h._reference_prefix(7).added_length(7)))
        bounds = {}
        for work in plan:
            if work.k_control_selected or work.determinism_selected:
                group = tuple(bundle for bundle in baselines if bundle.work_position == work.position)
                low, high = h._reference_q_bounds(group, targets, h._reference_prefix(cap // 26), cap)
                if high is None or not 0 <= low <= high < 10000:
                    raise AssertionError(("Unbounded Slice 1P Reference fixture", low, high))
                bounds[work.position] = (low, high)
        with tempfile.TemporaryDirectory() as directory, _slice1p_count_domain(counts), \
                patch.object(operational.harness, "_coordinator_private_bytes", return_value=100):
            materialization = h._materialize_v2_plan(source, plan, targets, profile, envelope, directory,
                counts, h._new_v2_materialization_ledger(targets, counts),
                readiness.minimum_archive_preflight(targets.physical, counts, 0))
            h._publish_v2_materialization(directory, materialization, targets, profile, envelope)
            with patch.object(h.qualification, "validate_v2_materialization_semantics",
                    side_effect=AssertionError("Slice 1N cannot delegate to Slice 1P")):
                readback = h._readback_v2_plan(directory, source, targets, profile, envelope, counts)
            files = tuple((path.name, path.read_bytes()) for path in sorted(Path(directory).iterdir()))
    indices = tuple(work.board.game_index for work in plan)
    expected = (records.ProtocolIdentity(h.qualification._PROTOCOL, identity.PROTOCOL_SHA256,
        h.qualification._BLOB, h.qualification._FREEZE), records.CorpusIdentity("SYNTHETIC_I7",
        min(indices), max(indices) + 1, len(plan), indices,
        identity.corpus_digest(plan[0].protocol_seed, len(plan), indices).hex(), ()), runtime,
        records.SourceBlobIdentity("synthetic/slice1p/additional.py", "a" * 40, "b" * 64, 17),
        records.SourceBlobIdentity("synthetic/slice1p/materializer.py", "c" * 40, "d" * 64, 23))
    _SLICE1P_DATA = dict(plan=plan, source_plan=source, materialization=materialization,
        coordinator_result=materialization.coordinator, readback=readback, profile=profile,
        envelope=envelope, targets=targets, counts=counts, expected_identity=expected,
        reference_bounds=tuple(sorted(bounds.items())), files=files)
    return _SLICE1P_DATA


@contextmanager
def _slice1p_fixture(*, with_identity=False, fresh_readback=False):
    data = _slice1p_fixture_data()
    with tempfile.TemporaryDirectory() as directory, _slice1p_count_domain(data["counts"]), \
            _slice1p_plan_domain(data["plan"]):
        experiment = Path(directory) / "experiment"
        root = experiment / "streams"
        root.mkdir(parents=True)
        for name, raw in data["files"]:
            (root / name).write_bytes(raw)
        fixture = {key: value for key, value in data.items() if key != "files"}
        fixture.update(root=root, experiment_root=experiment, output_root=experiment / "postprocessing",
                       source_recheck=lambda: data["expected_identity"])
        if fresh_readback:
            with patch.object(operational.harness, "_coordinator_private_bytes", return_value=100), \
                    patch.object(h.qualification, "validate_v2_materialization_semantics",
                        side_effect=AssertionError("Slice 1N cannot delegate to Slice 1P")):
                fixture["readback"] = h._readback_v2_plan(root, data["source_plan"], data["targets"],
                    data["profile"], data["envelope"], data["counts"])
        if with_identity:
            fixture["identity_seal"] = h.qualification._write_identity_v2(root, data["plan"],
                data["expected_identity"], data["profile"], data["envelope"],
                source_recheck=fixture["source_recheck"])
        yield fixture


class ZZV2SemanticPostprocessingTests(unittest.TestCase):
    """One new real bootstrap, last; all fault cases inject bounded analysis."""

    @staticmethod
    def arguments(fixture):
        return {name: fixture[name] for name in ("plan", "materialization", "readback", "identity_seal",
            "root", "profile", "envelope", "output_root", "expected_identity", "source_recheck")}

    def execute(self, fixture, **changes):
        arguments = self.arguments(fixture)
        arguments["_analyze"] = _bounded_postprocess_analyze
        with _slice1p_semantic_guards():
            return h._postprocess_r0b_v2(**(arguments | changes))

    def assert_no_close(self, fixture):
        self.assertFalse((fixture["experiment_root"] / "COMPLETE.json").exists())
        self.assertFalse((fixture["experiment_root"] / "manifest.json").exists())

    def test_bindings_fail_before_progress_or_semantic_work(self):
        for mutation in ("plan", "materialization", "readback", "seals", "profile", "metadata", "identity", "source"):
            with self.subTest(mutation=mutation), _slice1p_fixture(with_identity=True) as fixture:
                changes = {}
                if mutation == "plan":
                    changes["plan"] = fixture["source_plan"]
                elif mutation == "materialization":
                    changes["materialization"] = replace(fixture["materialization"], cleanup_complete=False)
                elif mutation == "readback":
                    changes["readback"] = replace(fixture["readback"], readback_complete=False)
                elif mutation == "seals":
                    changed = tuple(replace(v, sha256="0" * 64) if i == 0 else v
                                    for i, v in enumerate(fixture["readback"].streams))
                    changes["readback"] = replace(fixture["readback"], streams=changed)
                elif mutation == "profile":
                    changes["readback"] = replace(fixture["readback"], codec_profile_sha256="0" * 64)
                elif mutation == "metadata":
                    path = fixture["root"] / "materialization-v2.json"
                    path.write_bytes(path.read_bytes() + b" ")
                elif mutation == "identity":
                    changes["identity_seal"] = fixture["materialization"].coordinator.streams[0]
                else:
                    changes["source_recheck"] = lambda: ()
                with patch.object(h.qualification, "validate_v2_materialization_semantics",
                        side_effect=AssertionError("Invalid binding reached qualification")), self.assertRaises(ValueError):
                    self.execute(fixture, **changes)
                self.assertFalse(fixture["output_root"].exists())
                self.assert_no_close(fixture)

    def test_validation_failure_preserves_progress_without_analysis(self):
        with _slice1p_fixture(with_identity=True) as fixture:
            error = RuntimeError("SLICE1P_VALIDATION_FAILURE")
            with patch.object(h.qualification, "validate_v2_materialization_semantics", side_effect=error), \
                    self.assertRaises(RuntimeError) as raised:
                self.execute(fixture, _analyze=lambda *a, **k: self.fail("No analysis after validation failure"))
            self.assertIs(raised.exception, error)
            path = fixture["output_root"] / "postprocessing_operations.pkf"
            before = path.read_bytes()
            self.assertGreater(len(before), 0)
            self.assertFalse((fixture["output_root"] / "analysis.json").exists())
            with self.assertRaises((ValueError, OSError)):
                self.execute(fixture)
            self.assertEqual(path.read_bytes(), before)
            self.assert_no_close(fixture)

    def test_analyze_and_both_renderers_fail_without_close_ready_support(self):
        cases = ((None, None), (h.report, "render_analysis_json"), (h.report, "render_report_html"))
        for owner, name in cases:
            with self.subTest(boundary=name or "analyze"), _slice1p_fixture(with_identity=True) as fixture:
                error = RuntimeError("SLICE1P_ANALYZE_OR_RENDER_FAILURE")
                with _EvidenceExitStack() as stack:
                    changes = {}
                    if owner is None:
                        changes["_analyze"] = lambda *a, **k: (_ for _ in ()).throw(error)
                    else:
                        stack.enter_context(patch.object(owner, name, side_effect=error))
                    with self.assertRaises(RuntimeError) as raised:
                        self.execute(fixture, **changes)
                    self.assertIs(raised.exception, error)
                self.assertTrue((fixture["output_root"] / "postprocessing_operations.pkf").exists())
                self.assertFalse((fixture["output_root"] / "report.html").exists())
                self.assert_no_close(fixture)

    def test_analysis_and_report_write_flush_fsync_failures_keep_partial_bytes(self):
        for filename in ("analysis.json", "report.html"):
            for operation in ("write", "flush", "fsync"):
                with self.subTest(filename=filename, operation=operation), \
                        _slice1p_fixture(with_identity=True) as fixture:
                    original_open, original_fsync = h.store._exclusive, h.os.fsync
                    target_fd, calls = [], []
                    error = OSError("SLICE1P_ARTIFACT_IO_FAILURE")
                    class BrokenFile:
                        def __init__(self, file):
                            self.file = file
                        def __enter__(self):
                            return self
                        def __exit__(self, *args):
                            self.file.close()
                        def __getattr__(self, name):
                            return getattr(self.file, name)
                        def write(self, data):
                            if operation == "write":
                                calls.append("write")
                                self.file.write(data[:min(7, len(data))])
                                raise error
                            return self.file.write(data)
                        def flush(self):
                            if operation == "flush":
                                calls.append("flush")
                                raise error
                            return self.file.flush()
                    def opened(path):
                        file = original_open(path)
                        if Path(path).name == filename:
                            target_fd.append(file.fileno())
                            return BrokenFile(file)
                        return file
                    def fsync(fd):
                        if operation == "fsync" and fd in target_fd:
                            calls.append("fsync")
                            raise error
                        return original_fsync(fd)
                    with patch.object(h.store, "_exclusive", side_effect=opened), \
                            patch.object(h.os, "fsync", side_effect=fsync), self.assertRaises(OSError) as raised:
                        self.execute(fixture)
                    self.assertIs(raised.exception, error)
                    self.assertEqual(calls, [operation])
                    path = fixture["output_root"] / filename
                    before = path.read_bytes()
                    self.assertGreater(len(before), 0)
                    with self.assertRaises((ValueError, OSError)):
                        self.execute(fixture)
                    self.assertEqual(path.read_bytes(), before)
                    self.assert_no_close(fixture)

    def test_artifact_and_source_readback_tampering_fails_closed(self):
        for target in ("analysis.json", "report.html", "source.pkf"):
            with self.subTest(target=target), _slice1p_fixture(with_identity=True) as fixture:
                original = h._postprocess_artifact_readback
                changed = []
                def artifact(path, fact, visit):
                    if Path(path).name == target:
                        Path(path).write_bytes(Path(path).read_bytes() + b" ")
                        changed.append(target)
                    return original(path, fact, visit)
                def progress(fact):
                    if target == "source.pkf" and not changed and fact.phase is records.Phase.READBACK:
                        path = fixture["root"] / "boards.pkf"
                        raw = path.read_bytes()
                        path.write_bytes(raw[:-1] + bytes((raw[-1] ^ 1,)))
                        changed.append(target)
                with patch.object(h, "_postprocess_artifact_readback", side_effect=artifact), \
                        self.assertRaises(ValueError):
                    self.execute(fixture, progress=progress)
                self.assertEqual(changed, [target])
                self.assert_no_close(fixture)

    def test_progress_append_checkpoint_seal_and_readback_fail_closed(self):
        for operation in ("append", "checkpoint", "seal", "readback"):
            with self.subTest(operation=operation), _slice1p_fixture(with_identity=True) as fixture:
                calls = []
                error = OSError("SLICE1P_PROGRESS_FAILURE")
                original_scan = h._v2_postprocess_scan
                def scanned(root, seal, *args):
                    if seal.name == "postprocessing_operations":
                        calls.append("readback")
                        path = Path(root) / "postprocessing_operations.pkf"
                        raw = path.read_bytes()
                        path.write_bytes(raw[:-1] + bytes((raw[-1] ^ 1,)))
                    return original_scan(root, seal, *args)
                with _EvidenceExitStack() as stack:
                    if operation == "readback":
                        stack.enter_context(patch.object(h, "_v2_postprocess_scan", side_effect=scanned))
                    else:
                        original = getattr(h.store.FramedStreamWriter, operation)
                        def failed(writer, *args, **kwargs):
                            if writer._stream_name == "postprocessing_operations":
                                calls.append(operation)
                                raise error
                            return original(writer, *args, **kwargs)
                        stack.enter_context(patch.object(h.store.FramedStreamWriter, operation, failed))
                    with self.assertRaises((ValueError, OSError)):
                        self.execute(fixture)
                self.assertEqual(calls, [operation])
                path = fixture["output_root"] / "postprocessing_operations.pkf"
                before = path.read_bytes()
                with self.assertRaises((ValueError, OSError)):
                    self.execute(fixture)
                self.assertEqual(path.read_bytes(), before)
                self.assert_no_close(fixture)

    def test_final_source_change_check_interrupt_and_observer_failure_keep_no_success(self):
        for mode in ("source", "check", "observer", "interrupt"):
            with self.subTest(mode=mode), _slice1p_fixture(with_identity=True) as fixture:
                calls = []
                error = KeyboardInterrupt("SLICE1P_INTERRUPT") if mode == "interrupt" else RuntimeError("SLICE1P_CHECK")
                def recheck():
                    if (fixture["output_root"] / "report.html").exists():
                        calls.append("source")
                        return ()
                    return fixture["expected_identity"]
                def checked():
                    if (fixture["output_root"] / "analysis.json").exists():
                        calls.append(mode)
                        raise error
                def observe(fact):
                    if fact.phase is records.Phase.AGGREGATION and fact.processed > 0:
                        calls.append(mode)
                        raise error
                changes = ({"source_recheck": recheck} if mode == "source" else
                           {"progress": observe} if mode == "observer" else {"check": checked})
                with self.assertRaises((ValueError, RuntimeError, KeyboardInterrupt)):
                    self.execute(fixture, **changes)
                self.assertEqual(calls, [mode])
                self.assert_no_close(fixture)

    def test_each_phase_wall_timeout_rejects_completion(self):
        for phase in readiness.POSTPROCESS_PHASES:
            with self.subTest(phase=phase), _slice1p_fixture(with_identity=True) as fixture:
                offset = [0]
                def observe(fact):
                    if fact.phase is phase:
                        offset[0] += 2_000_000
                ticks = iter(range(1, 10 ** 12))
                def clock():
                    return next(ticks) + offset[0]
                envelope = replace(fixture["envelope"], **{phase.value.lower() + "_wall_ms": 1})
                with self.assertRaisesRegex(ValueError, "POSTPROCESS_PHASE_TIMEOUT"):
                    self.execute(fixture, envelope=envelope, clock=clock, progress=observe)
                self.assert_no_close(fixture)

    def test_bad_analysis_and_bootstrap_progress_cannot_make_support(self):
        for mode in ("no_result", "context", "progress_missing", "progress_reordered"):
            with self.subTest(mode=mode), _slice1p_fixture(with_identity=True) as fixture:
                def analyze(rows, **kwargs):
                    if mode == "no_result":
                        return object()
                    if mode.startswith("progress_"):
                        callback = kwargs["bootstrap_progress"]
                        if mode == "progress_reordered":
                            callback(1, 10000)
                        kwargs["bootstrap_progress"] = lambda *_: None
                    result = _bounded_postprocess_analyze(rows, **kwargs)
                    return replace(result, context=("WRONG",)) if mode == "context" else result
                with self.assertRaisesRegex(ValueError, "ANALYSIS|BOOTSTRAP"):
                    self.execute(fixture, _analyze=analyze)
                self.assertFalse((fixture["output_root"] / "analysis.json").exists())
                self.assert_no_close(fixture)

    def test_v1_materializer_coordinator_postprocess_archive_and_launch_stay_disconnected(self):
        with _EvidenceExitStack() as stack:
            for name in ("_postprocess_r0b_v2", "_v2_postprocess_binding", "_v2_postprocess_scan", "_v2_postprocess_support"):
                stack.enter_context(patch.object(h, name, side_effect=AssertionError("No Slice 1P on V1")))
            for name in ("_validate_identity_v2", "_write_identity_v2", "validate_v2_materialization_semantics"):
                stack.enter_context(patch.object(h.qualification, name, side_effect=AssertionError("No V2 qualification")))
            V2FullMaterializerV1IsolationTests().test_historical_materializer_coordinator_and_r0_never_activate_full_v2_path()
            OperatorEvidenceTests().test_public_launch_requires_exact_authorization_before_any_io_or_workers()

    def test_zz_one_new_real_four_work_bootstrap_semantic_support_and_archive_close(self):
        from experiments import program_k_e2_r0_evidence as evidence
        with _slice1p_fixture(with_identity=True, fresh_readback=True) as fixture:
            self.assertEqual(fixture["counts"], (4, 1, 2, 1, 1, 2))
            self.assertEqual(fixture["materialization"].coordinator.durable_units, 6)
            self.assertEqual(fixture["plan"][0].runtime, records.RuntimeIdentity(platform.python_implementation(),
                platform.python_version(), os.name, platform.platform(), platform.machine(), None))
            self.assertTrue(fixture["plan"][0].run_id.startswith("synthetic-i7-"))
            self.assertEqual(fixture["plan"][0].protocol_seed.hex(), identity.PROTOCOL_SHA256)
            progress, reads, writes, scans = [], [], [], []
            original_reader, original_exclusive = h.store._reader, h.store._exclusive
            original_scan, original_qualify = h._v2_postprocess_scan, h.qualification.validate_v2_materialization_semantics
            class Probe:
                def __init__(self, file, path):
                    self.manager, self.file, self.path = file, file, Path(path)
                def __getattr__(self, name):
                    return getattr(self.file, name)
                def __enter__(self):
                    self.file = self.manager.__enter__()
                    return self
                def __exit__(self, *args):
                    return self.manager.__exit__(*args)
                def read(self, size=-1):
                    if type(size) is not int or not 1 <= size <= 65536:
                        raise AssertionError(("Unbounded Slice 1P read", self.path.name, size))
                    reads.append((self.path.name, size))
                    return self.file.read(size)
                def write(self, data):
                    if not 0 < len(data) <= 65536:
                        raise AssertionError(("Unbounded Slice 1P write", self.path.name, len(data)))
                    writes.append((self.path.name, len(data)))
                    return self.file.write(data)
            def scan(root, seal, *args):
                scans.append(seal.name)
                return original_scan(root, seal, *args)
            actual_bootstrap = h.analysis._shared_bootstrap
            with _slice1p_semantic_guards(allow_bootstrap=True), \
                    patch.object(h.store, "_reader", side_effect=lambda path: Probe(original_reader(path), path)), \
                    patch.object(h.store, "_exclusive", side_effect=lambda path: Probe(original_exclusive(path), path)), \
                    patch.object(h, "_v2_postprocess_scan", side_effect=scan), \
                    patch.object(h.qualification, "validate_v2_materialization_semantics", wraps=original_qualify) as qualified, \
                    patch.object(h.analysis, "_shared_bootstrap", wraps=actual_bootstrap) as bootstrap:
                result = h._postprocess_r0b_v2(**self.arguments(fixture), progress=progress.append)
            bootstrap.assert_called_once()
            qualified.assert_called_once()
            self.assertEqual(len(bootstrap.call_args.args[0]), 4)
            self.assertEqual((result.bootstrap_replicates, result.bootstrap_n, result.bootstrap_progress_count),
                             (10000, 4, 10001))
            self.assertEqual(result.analysis_result.bootstrap.accepted_draws, 40000)
            self.assertEqual(result.analysis_result.n, 4)
            self.assertIsNone(result.analysis_result.overall)
            self.assertEqual(result.analysis_result.context,
                             ("SYNTHETIC_R0B_OPERATIONAL_ONLY_NOT_EFFECTIVENESS_EVIDENCE",))
            self.assertEqual(result.streams, fixture["coordinator_result"].streams + (fixture["identity_seal"],))
            self.assertEqual(scans, [v.name for v in result.streams] + ["postprocessing_operations"])
            self.assertTrue(reads and writes)
            self.assertEqual(tuple(v.phase for v in result.phases), readiness.POSTPROCESS_PHASES)
            self.assertTrue(all(v.complete and v.progress_bounded and v.processed == v.total for v in result.phases))
            self.assertGreaterEqual(result.complete_wall_ns, sum(v.wall_ns for v in result.phases))
            for name in ("shared_bootstrap_complete", "compact_scalar_bootstrap", "streaming_reconstruction",
                         "readback_complete", "progress_bounded", "qualification_complete", "cleanup_complete",
                         "synthetic_non_evidence"):
                self.assertIs(getattr(result, name), True)
            self.assertFalse(hasattr(result, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                result.qualification_complete = False
            output = fixture["output_root"]
            self.assertEqual((output / "analysis.json").read_bytes(), h.report.render_analysis_json(result.analysis_result))
            self.assertEqual((output / "report.html").read_bytes(), h.report.render_report_html(result.analysis_result).encode("utf-8"))
            self.assertEqual({p.name for p in output.iterdir()},
                             {"analysis.json", "report.html", "postprocessing_operations.pkf"})
            support = h._v2_postprocess_support(result)
            self.assertEqual(support["qualification_identity_seal"], fixture["identity_seal"])
            self.assertEqual(support["postprocessing_operations_seal"], result.progress_stream)
            authorities = dict(selection_receipt_sha256="a" * 64,
                corpus_sha256=fixture["expected_identity"][1].corpus_sha256, source_sha256="c" * 64)
            with patch.object(h.qualification, "validate_v2_materialization_semantics",
                    side_effect=AssertionError("Archive validator is structural only")), \
                    patch.object(h, "_postprocess_r0b_v2", side_effect=AssertionError("No repeated postprocessing")), \
                    patch.object(h.analysis, "_shared_bootstrap", side_effect=AssertionError("Only one new bootstrap")):
                closed = h._close_v2_experiment_archive(fixture["experiment_root"], fixture["readback"],
                    fixture["profile"], fixture["envelope"], **support, **authorities)
                self.assertEqual(h._validate_closed_v2_experiment_archive(fixture["experiment_root"],
                    fixture["profile"], fixture["envelope"], **authorities), closed)
            files = tuple(sorted(p.relative_to(fixture["experiment_root"]).as_posix()
                                 for p in fixture["experiment_root"].rglob("*") if p.is_file()))
            self.assertEqual(files, evidence.V2_ARCHIVE_FINAL_PATHS)
            self.assertEqual(len(files), 64)
            self.assertFalse(any(name.endswith(".jsonl") for name in files))
            print("SLICE1P_BOUNDED_POSTPROCESS " + json.dumps(dict(new_actual_bootstraps=1, n=4,
                replicates=result.bootstrap_replicates, accepted_draws=result.analysis_result.bootstrap.accepted_draws,
                source_streams=len(result.streams), files=len(files), archive_bytes=closed.accounting.archive_bytes,
                attributable_bytes=closed.accounting.attributable_bytes,
                fixed_bytes=closed.accounting.fixed_allowance_bytes,
                reference_bounds=fixture["reference_bounds"], complete_wall_ns=result.complete_wall_ns), sort_keys=True))


class V2FullMaterializerV1IsolationTests(unittest.TestCase):
    def test_historical_materializer_coordinator_and_r0_never_activate_full_v2_path(self):
        from tests.test_program_k_e2_operational import StreamingCoordinatorTests, R0ComponentTests, _plan
        from experiments import program_k_e2_r0_evidence as evidence
        names = ("_materialize_synthetic_v2", "_materialize_v2_plan", "_construct_v2_materialization_work",
                 "_build_primary_v2_baseline", "_materialize_v2_unit", "_capture_qualified_codec_profile",
                 "_publish_v2_materialization", "_readback_synthetic_v2", "_readback_v2_plan",
                 "_v2_serialized_reservation", "_v2_materialization_evidence", "_v2_readback_constructor",
                 "_v2_readback_prior", "_v2_readback_unit", "_v2_readback_support",
                 "_close_v2_experiment_archive", "_validate_closed_v2_experiment_archive",
                 "_v2_archive_authority", "_v2_archive_inventory", "_v2_archive_file", "_v2_archive_read_bytes",
                 "_v2_archive_bind_seals", "_v2_archive_scan_support", "_v2_archive_reconcile",
                 "_v2_archive_readback_binding", "_v2_archive_peak", "_v2_archive_partition",
                 "_v2_archive_coordinator", "_v2_archive_status", "_v2_archive_completion", "_v2_archive_project")
        with _EvidenceExitStack() as stack:
            for name in names:
                stack.enter_context(patch.object(h, name, side_effect=AssertionError("No full V2 historical path")))
            stack.enter_context(patch.object(physical, "capture_qualified_profile",
                                             side_effect=AssertionError("No V1 profile capture")))
            for owner, name in ((evidence, "encode_materialization_v2"),
                    (evidence, "decode_materialization_v2"), (evidence, "plan_identity_v2"),
                    (evidence, "encode_archive_manifest_v2"), (evidence, "decode_archive_manifest_v2"),
                    (h.store, "FramedStreamPullReader")):
                stack.enter_context(patch.object(owner, name,
                    side_effect=AssertionError("No V2 evidence or PKF reader in V1")))
            stack.enter_context(patch.object(operational.harness, "_coordinator_private_bytes", return_value=100))
            fixture = SyntheticMaterializationTests()
            with tempfile.TemporaryDirectory() as directory:
                plan = fixture.plan()
                seal = fixture._identity(directory, plan)
                result = h.materialize_synthetic(plan, readiness.ComponentSizes(1, 1, 1, 1, 1, 1),
                                                fixture.envelope(), directory, seal)
                self.assertTrue(result.readback_complete and result.cleanup_complete)
                self.assertTrue(list(Path(directory).glob("*.jsonl")))
                self.assertFalse(list(Path(directory).rglob("*.pkf")))
            with tempfile.TemporaryDirectory() as directory:
                result = StreamingCoordinatorTests().run_plan(_plan(), directory)
                self.assertIs(result.status, records.AuditStatus.PASS)
                self.assertTrue(list(Path(directory).glob("*.jsonl")))
                self.assertFalse(list(Path(directory).rglob("*.pkf")))
            with tempfile.TemporaryDirectory() as directory:
                result = R0ComponentTests().run_component(directory, operational.R0Component.PRIMARY)
                self.assertIs(result.units[0].status, records.AuditStatus.PASS)
                self.assertTrue(list(Path(directory).rglob("*.jsonl")))
                self.assertFalse(list(Path(directory).rglob("*.pkf")))
            postprocess = R0BPostprocessingTests()
            with postprocess.fixture() as inputs, \
                    patch.object(h.analysis, "_shared_bootstrap", side_effect=AssertionError("No real bootstrap")):
                result = postprocess.execute(inputs)
                self.assertTrue(result.qualification_complete and result.readback_complete)
                self.assertFalse(list(inputs["root"].rglob("*.pkf")))
            with ClosedExperimentArchiveAccountingTests().fixture() as (root, _, accounting):
                self.assertTrue((root / "COMPLETE.json").exists())
                self.assertGreater(accounting.archive_bytes, 0)
                self.assertFalse(list(root.rglob("*.pkf")))
                self.assertEqual(json.loads((root / "manifest.json").read_bytes())["schema"],
                                 "program-k-e2-r0b-experiment/v1")
                self.assertEqual(h.store.read_completion_receipt(root).manifest_sha256,
                                 h.sha256((root / "manifest.json").read_bytes()).hexdigest())


@_evidence_contextmanager
def _slice1q_provenance_fixture():
    """Synthetic committed Git observations; production V2 checks stay intact."""
    q = h.qualification
    original_root = q._ROOT
    committed = {path: ("bounded Slice 1Q source: " + path + "\n").encode("ascii")
                 for path in q._V2_SOURCE_PATHS}
    for path in (q._PROTOCOL, q._AMENDMENT):
        committed[path] = (original_root / path).read_bytes()
    frozen = dict(committed)
    state = dict(head="a" * 40, status=b"", committed=committed, calls=[],
                 head_reads=0, head_after=None, ancestor_failure=None, blob_reads=0,
                 on_blobs=None, on_git=None)

    def git(*args, data=None):
        state["calls"].append(args)
        if state["on_git"] is not None:
            state["on_git"](args)
        if args == ("rev-parse", "HEAD"):
            state["head_reads"] += 1
            head = state["head"]
            if state["head_after"] is not None and state["head_reads"] >= state["head_after"]:
                head = "b" * 40
            return head.encode("ascii") + b"\n"
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return state["status"]
        if args[:2] == ("merge-base", "--is-ancestor"):
            if args[2] == state["ancestor_failure"]:
                raise q.QualificationError("SOURCE_IDENTITY_UNAVAILABLE")
            return b""
        raise AssertionError("Unexpected or mutating Git call: " + repr(args))

    def blobs(refs):
        state["blob_reads"] += 1
        result = []
        for ref in refs:
            revision, path = ref.split(":", 1)
            source = frozen if revision in (q._E1, q._FREEZE) else committed
            if path not in source:
                raise q.QualificationError("SOURCE_BLOB_REQUIRED")
            data = source[path]
            blob = q.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
            result.append((blob, data))
        if state["on_blobs"] is not None:
            state["on_blobs"](refs)
        return tuple(result)

    with tempfile.TemporaryDirectory(prefix="bounded-slice1q-provenance-") as directory, \
            _EvidenceExitStack() as stack:
        root = Path(directory)
        for path, data in committed.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        receipt_path = root / "accepted-receipt-copy.json"
        receipt_path.write_bytes(_accepted_receipt_bytes())
        receipt = h.load_selection_receipt(receipt_path)
        stack.enter_context(patch.object(q, "_ROOT", root))
        stack.enter_context(patch.object(q, "_git", side_effect=git))
        stack.enter_context(patch.object(q, "_blobs", side_effect=blobs))
        yield root, receipt, state


@_evidence_contextmanager
def _slice1q_v1_guards():
    """Every new live owner is forbidden on unchanged V1 routes."""
    with _EvidenceExitStack() as stack:
        for owner, names in ((h, ("capture_run_provenance_v2", "_recheck_provenance_v2",
                                 "_qualification_identity_v2", "_source_recheck_callback_v2")),
                             (h.qualification, ("capture_sources_v2", "_validate_sources_v2",
                                                "_validate_identity_v2", "_write_identity_v2",
                                                "validate_v2_materialization_semantics"))):
            for name in names:
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError("No V2 in V1")))
        stack.enter_context(patch.object(physical, "capture_qualified_profile",
                                        side_effect=AssertionError("No V1 codec profile")))
        stack.enter_context(patch.object(h.store, "FramedStreamWriter",
                                        side_effect=AssertionError("No RF02 in V1")))
        stack.enter_context(patch.object(h.store, "FramedStreamPullReader",
                                        side_effect=AssertionError("No RF02 in V1")))
        stack.enter_context(patch.object(h.analysis, "_shared_bootstrap",
                                        side_effect=AssertionError("No additional real bootstrap")))
        yield


class V2LiveProvenanceBridgeTests(unittest.TestCase):
    """Bounded source/identity ownership, no live admission or materialization."""

    @staticmethod
    def profile():
        from tests.test_program_k_e2_physical import _qualified_node, _json_bytes
        return physical.decode_profile(_json_bytes(_qualified_node()))

    def test_capture_exact_selection_head_sources_working_runtime_and_environment_read_only(self):
        q = h.qualification
        with _slice1q_provenance_fixture() as (root, receipt, state):
            before = {path: (root / path).read_bytes() for path in q._V2_SOURCE_PATHS}
            with _profile_read_only(), \
                    patch.object(q, "capture_sources", side_effect=AssertionError("No V1 source capture")), \
                    patch.object(h, "capture_run_provenance", side_effect=AssertionError("No V1 provenance")):
                value = h.capture_run_provenance_v2(receipt)
            self.assertIs(type(value), h.RunProvenance)
            self.assertEqual(value.selection_source_head, h.SELECTION_SOURCE_HEAD)
            self.assertEqual(value.r0_harness_source_head, state["head"])
            self.assertEqual(tuple(v.path for v in value.sources), q._V2_SOURCE_PATHS)
            self.assertEqual(value.runtime, h._runtime_identity())
            self.assertEqual(value.executable, h.sys.executable)
            self.assertIs(value.dont_write_bytecode, True)
            self.assertEqual(os.environ["PYTHONDONTWRITEBYTECODE"], "1")
            for source, working in zip(value.sources, value.working_files):
                data = before[source.path]
                blob = q.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
                self.assertEqual((source.blob_id, source.sha256, source.byte_length),
                                 (blob, h.sha256(data).hexdigest(), len(data)))
                self.assertEqual(working, (source.path, source.sha256, source.byte_length, False))
            self.assertEqual(before, {path: (root / path).read_bytes() for path in before})
            self.assertEqual(h._fact_read(h._fact_node(value)), value)
            for ancestor in (h.SELECTION_SOURCE_HEAD, h.SETUP_REPAIR_HEAD):
                self.assertIn(("merge-base", "--is-ancestor", ancestor, state["head"]), state["calls"])

    def test_capture_rejects_receipt_dirty_index_worktree_untracked_and_ancestry(self):
        with _slice1q_provenance_fixture() as (_, receipt, _):
            Path(receipt.path).write_bytes(receipt.canonical_bytes + b"\n")
            with self.assertRaises(ValueError):
                h.capture_run_provenance_v2(receipt)
        for status in (b" M experiments/program_k_e2_r0_harness.py\n",
                       b"M  experiments/program_k_e2_physical.py\n", b"?? candidate.py\n"):
            with self.subTest(status=status), _slice1q_provenance_fixture() as (_, receipt, state):
                state["status"] = status
                with self.assertRaises(ValueError):
                    h.capture_run_provenance_v2(receipt)
        for ancestor in (h.SELECTION_SOURCE_HEAD, h.SETUP_REPAIR_HEAD):
            with self.subTest(ancestor=ancestor), _slice1q_provenance_fixture() as (_, receipt, state):
                state["ancestor_failure"] = ancestor
                with self.assertRaises(ValueError):
                    h.capture_run_provenance_v2(receipt)

    def test_capture_binds_only_proven_crlf_and_exact_frozen_working_authorities(self):
        path = "experiments/program_k_e2_physical.py"
        with _slice1q_provenance_fixture() as (root, receipt, state):
            data = state["committed"][path]
            raw = data.replace(b"\n", b"\r\n")
            (root / path).write_bytes(raw)
            value = h.capture_run_provenance_v2(receipt)
            self.assertEqual(next(v for v in value.working_files if v[0] == path),
                             (path, h.sha256(raw).hexdigest(), len(raw), True))
            for bad in (data + b"semantic drift\n", data.replace(b"\n", b"\r"), data + b" "):
                (root / path).write_bytes(bad)
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    h.capture_run_provenance_v2(receipt)
        for authority in (h.qualification._PROTOCOL, h.qualification._AMENDMENT):
            with self.subTest(authority=authority), _slice1q_provenance_fixture() as (root, receipt, state):
                (root / authority).write_bytes(state["committed"][authority].replace(b"\n", b"\r\n"))
                with self.assertRaises(ValueError):
                    h.capture_run_provenance_v2(receipt)

    def test_capture_missing_v2_owner_and_substituted_source_identities_fail(self):
        q = h.qualification
        for path in ("experiments/program_k_e2_physical.py", "experiments/program_k_e2_r0_evidence.py"):
            with self.subTest(path=path), _slice1q_provenance_fixture() as (_, receipt, state):
                del state["committed"][path]
                with self.assertRaises(ValueError):
                    h.capture_run_provenance_v2(receipt)
        with _slice1q_provenance_fixture() as (_, receipt, _):
            sources = q.capture_sources_v2()
            index = next(i for i, source in enumerate(sources) if source.path.endswith("physical.py")
                         and source.path.startswith("experiments/"))
            for changes in ({"blob_id": "b" * 40}, {"sha256": "c" * 64}, {"byte_length": 0}):
                changed = sources[:index] + (replace(sources[index], **changes),) + sources[index + 1:]
                with self.subTest(changes=changes), patch.object(q, "capture_sources_v2", return_value=changed):
                    with self.assertRaises(ValueError):
                        h.capture_run_provenance_v2(receipt)
            for changed in (sources[:-1], sources[::-1], sources + (sources[-1],)):
                with self.subTest(paths=tuple(v.path for v in changed)), \
                        patch.object(q, "capture_sources_v2", return_value=changed):
                    with self.assertRaises(ValueError):
                        h.capture_run_provenance_v2(receipt)

    def test_capture_environment_and_head_drift_fail_closed(self):
        with _slice1q_provenance_fixture() as (_, receipt, _):
            with patch.dict(os.environ, {"PYTHONDONTWRITEBYTECODE": "0"}), self.assertRaises(ValueError):
                h.capture_run_provenance_v2(receipt)
            with patch.object(h.sys, "dont_write_bytecode", False), self.assertRaises(ValueError):
                h.capture_run_provenance_v2(receipt)
            with patch.object(h.sys, "executable", ""), self.assertRaises(ValueError):
                h.capture_run_provenance_v2(receipt)
        for head_after in (2, 3, 4):
            with self.subTest(head_after=head_after), _slice1q_provenance_fixture() as (_, receipt, state):
                state["head_after"] = head_after
                with self.assertRaises(ValueError):
                    h.capture_run_provenance_v2(receipt)

    def test_capture_rechecks_environment_and_working_bytes_after_first_observation(self):
        for drift in ("runtime", "executable", "bytecode_flag", "environment", "working"):
            with self.subTest(drift=drift), _slice1q_provenance_fixture() as (root, receipt, state), \
                    _EvidenceExitStack() as stack:
                runtime = h._runtime_identity()
                if drift == "runtime":
                    stack.enter_context(patch.object(h, "_runtime_identity",
                        side_effect=(runtime, replace(runtime, python_version="changed"))))
                elif drift == "working":
                    original = Path.read_bytes
                    target = root / h.qualification._V2_SOURCE_PATHS[0]
                    reads = []
                    def read(path):
                        data = original(path)
                        if path == target:
                            reads.append(None)
                            if len(reads) > 1:
                                return data + b"changed after first byte observation\n"
                        return data
                    stack.enter_context(patch.object(Path, "read_bytes", autospec=True, side_effect=read))
                else:
                    stack.enter_context(patch.object(h.sys, "executable", h.sys.executable))
                    stack.enter_context(patch.object(h.sys, "dont_write_bytecode", True))
                    stack.enter_context(patch.dict(os.environ, {"PYTHONDONTWRITEBYTECODE": "1"}))
                    def changed(_):
                        if drift == "executable":
                            h.sys.executable += ".changed"
                        elif drift == "bytecode_flag":
                            h.sys.dont_write_bytecode = False
                        else:
                            os.environ["PYTHONDONTWRITEBYTECODE"] = "0"
                    state["on_blobs"] = changed
                with self.assertRaises(ValueError):
                    h.capture_run_provenance_v2(receipt)

    def test_fresh_recheck_exact_equality_and_source_runtime_executable_head_status_drift(self):
        for drift in ("source", "runtime", "executable", "head", "worktree", "index", "untracked"):
            with self.subTest(drift=drift), _slice1q_provenance_fixture() as (root, receipt, state), \
                    _EvidenceExitStack() as stack:
                value = h.capture_run_provenance_v2(receipt)
                before = state["head_reads"]
                self.assertIs(h._recheck_provenance_v2(receipt, value), value)
                self.assertGreater(state["head_reads"], before)
                if drift == "source":
                    path = "experiments/program_k_e2_r0_evidence.py"
                    state["committed"][path] += b"new committed source\n"
                    (root / path).write_bytes(state["committed"][path])
                elif drift == "runtime":
                    stack.enter_context(patch.object(h, "_runtime_identity",
                        return_value=replace(value.runtime, python_version="changed")))
                elif drift == "executable":
                    stack.enter_context(patch.object(h.sys, "executable", value.executable + ".changed"))
                elif drift == "head":
                    state["head"] = "b" * 40
                else:
                    state["status"] = {"worktree": b" M tracked.py\n", "index": b"M  tracked.py\n",
                                       "untracked": b"?? extra.py\n"}[drift]
                with self.assertRaises(ValueError):
                    h._recheck_provenance_v2(receipt, value)

    def test_bridge_is_pure_and_preserves_exact_identity_order_objects_and_corpus(self):
        q = h.qualification
        with _slice1q_provenance_fixture() as (_, receipt, _):
            value = h.capture_run_provenance_v2(receipt)
            plan = SyntheticMaterializationTests.plan()
            with patch.object(q, "_git", side_effect=AssertionError("Pure bridge has no Git")), \
                    patch.object(q, "_blobs", side_effect=AssertionError("Pure bridge has no blobs")), \
                    patch.object(q, "capture_sources", side_effect=AssertionError("Pure bridge has no V1 capture")), \
                    patch.object(q, "capture_sources_v2", side_effect=AssertionError("Pure bridge has no capture")), \
                    patch.object(h, "capture_run_provenance_v2", side_effect=AssertionError("No live capture")), \
                    patch.object(Path, "read_bytes", side_effect=AssertionError("Pure bridge has no source IO")), \
                    patch.object(h, "_runtime_identity", side_effect=AssertionError("Pure bridge has no runtime capture")):
                expected = h._qualification_identity_v2(plan, value)
                callback = h._source_recheck_callback_v2(receipt, value, plan)
                self.assertTrue(callable(callback))
            self.assertEqual(tuple(type(v) for v in expected[:3]),
                             (records.ProtocolIdentity, records.CorpusIdentity, records.RuntimeIdentity))
            self.assertEqual(expected[0], records.ProtocolIdentity(q._PROTOCOL, identity.PROTOCOL_SHA256,
                                                                   q._BLOB, q._FREEZE))
            indices = tuple(v.board.game_index for v in plan)
            self.assertEqual(expected[1], records.CorpusIdentity("SYNTHETIC_I7", min(indices), max(indices) + 1,
                len(plan), indices, identity.corpus_digest(plan[0].protocol_seed, len(plan), indices).hex(), ()))
            self.assertIs(expected[2], value.runtime)
            self.assertEqual(expected[3:], value.sources)
            for actual, source in zip(expected[3:], value.sources):
                self.assertIs(actual, source)

    def test_bridge_rejects_runtime_mismatch_noncanonical_sources_and_wrong_plan(self):
        with _slice1q_provenance_fixture() as (_, receipt, _):
            value = h.capture_run_provenance_v2(receipt)
            plan = SyntheticMaterializationTests.plan()
            changed_runtime = tuple(replace(work, runtime=replace(value.runtime, architecture="changed"))
                                    for work in plan)
            with self.assertRaises(ValueError):
                h._qualification_identity_v2(changed_runtime, value)
            for sources in (value.sources[:-1], value.sources[::-1], value.sources + (value.sources[-1],)):
                forged = replace(value)
                object.__setattr__(forged, "sources", sources)
                with self.subTest(sources=sources), self.assertRaises(ValueError):
                    h._qualification_identity_v2(plan, forged)
            for changed in ((), list(plan), tuple(replace(work, protocol_seed=b"x" * 32) for work in plan),
                            tuple(replace(work, run_id="not-synthetic") for work in plan)):
                with self.subTest(plan=changed), self.assertRaises(ValueError):
                    h._qualification_identity_v2(changed, value)

    def test_callback_freshly_reauthenticates_without_changing_identity_or_source_objects(self):
        with _slice1q_provenance_fixture() as (_, receipt, state):
            value = h.capture_run_provenance_v2(receipt)
            plan = SyntheticMaterializationTests.plan()
            expected = h._qualification_identity_v2(plan, value)
            callback = h._source_recheck_callback_v2(receipt, value, plan)
            before = state["head_reads"]
            self.assertEqual(callback(), expected)
            self.assertGreater(state["head_reads"], before)
            self.assertIsNone(h.qualification._source_recheck_v2(expected, callback))
            state["head"] = "b" * 40
            with self.assertRaises(ValueError):
                h.qualification._source_recheck_v2(expected, callback)

    def test_bridge_output_is_accepted_unchanged_by_existing_validator_and_rf02_writer(self):
        q = h.qualification
        with _slice1q_provenance_fixture() as (_, receipt, _), tempfile.TemporaryDirectory() as directory:
            value = h.capture_run_provenance_v2(receipt)
            plan, profile, envelope = SyntheticMaterializationTests.plan(), self.profile(), SyntheticMaterializationTests.envelope()
            expected = h._qualification_identity_v2(plan, value)
            callback = h._source_recheck_callback_v2(receipt, value, plan)
            self.assertIs(q._validate_identity_v2(plan, expected, profile, envelope, callback), expected)
            seal = q._write_identity_v2(directory, plan, expected, profile, envelope, source_recheck=callback)
            reader = h.store.FramedStreamPullReader(directory, q.IDENTITY_STREAM,
                physical.context_for(q.IDENTITY_STREAM, profile.sha256), max_payload_bytes=envelope.max_payload_bytes)
            observed = []
            while reader.peek_key() is not None:
                row = reader.pull()
                self.assertEqual(row.key, (len(observed),))
                self.assertEqual(row.logical_bytes, records.encode(expected[len(observed)]))
                observed.append(row.record)
            self.assertEqual(reader.close(), seal)
            self.assertEqual(tuple(observed), expected)
            self.assertEqual(tuple(path.name for path in Path(directory).iterdir()), ("qualification_identity.pkf",))

    def test_existing_before_after_identity_checks_reject_live_callback_drift_and_preserve_bytes(self):
        q = h.qualification
        for after_write in (False, True):
            with self.subTest(after_write=after_write), _slice1q_provenance_fixture() as (_, receipt, state), \
                    tempfile.TemporaryDirectory() as directory:
                value = h.capture_run_provenance_v2(receipt)
                plan, profile, envelope = SyntheticMaterializationTests.plan(), self.profile(), SyntheticMaterializationTests.envelope()
                expected = h._qualification_identity_v2(plan, value)
                callback = h._source_recheck_callback_v2(receipt, value, plan)
                calls = []
                def recheck():
                    calls.append(None)
                    if len(calls) == (2 if after_write else 1):
                        state["head"] = "b" * 40
                    return callback()
                with self.assertRaises(ValueError):
                    q._write_identity_v2(directory, plan, expected, profile, envelope, source_recheck=recheck)
                target = Path(directory) / "qualification_identity.pkf"
                self.assertEqual(target.exists(), after_write)
                if after_write:
                    self.assertGreater(target.stat().st_size, 0)

    def test_existing_identity_validator_rejects_changed_corpus_or_changed_source_tuple(self):
        q = h.qualification
        with _slice1q_provenance_fixture() as (_, receipt, _):
            value = h.capture_run_provenance_v2(receipt)
            plan, profile, envelope = SyntheticMaterializationTests.plan(), self.profile(), SyntheticMaterializationTests.envelope()
            expected = h._qualification_identity_v2(plan, value)
            callback = h._source_recheck_callback_v2(receipt, value, plan)
            other_plan = SyntheticMaterializationTests.plan(2)
            changed_corpus = h._qualification_identity_v2(other_plan, value)
            with self.assertRaises(ValueError):
                q._validate_identity_v2(plan, changed_corpus, profile, envelope, callback)
            source = replace(expected[-1], sha256="f" * 64)
            changed_source = expected[:-1] + (source,)
            with self.assertRaises(ValueError):
                q._validate_identity_v2(plan, changed_source, profile, envelope, callback)

    def test_historical_capture_and_recheck_never_activate_v2_or_redefine_v1_sources(self):
        q = h.qualification
        historical_paths = tuple(sorted(set(q._PROTECTED + ("benchmark_board.py", q._PROTOCOL, q._REPAIR_TEST)
                                          + q._E2 + q._R0_SOURCE_PATHS)))
        with _provenance_fixture() as (_, receipt, _), _slice1q_v1_guards():
            value = h.capture_run_provenance(receipt)
            self.assertEqual(tuple(v.path for v in value.sources), historical_paths)
            self.assertIs(h._recheck_provenance(receipt, value), value)
            self.assertEqual(tuple(v.path for v in q.capture_sources()), historical_paths)
            self.assertNotIn("experiments/program_k_e2_physical.py", historical_paths)
            self.assertNotIn("experiments/program_k_e2_r0_evidence.py", historical_paths)

    def test_historical_r0a_launcher_outer_finish_and_manifest_remain_v1_only(self):
        with _slice1q_v1_guards(), _fake_r0a_launch() as (root, receipt, fixtures, calls):
            output = root / "results" / "slice1q-v1-only"
            manifest = h.launch_r0a(receipt.path, output, tuple(v[1] for v in fixtures),
                                   authorization=FixtureAuthorization("R0_A"))
            self.assertEqual(len(calls), 18)
            self.assertEqual(manifest["schema"], "program-k-e2-r0-run/v1")
            self.assertEqual(h.validate_existing_run(output, receipt), manifest)
            self.assertFalse(list(output.rglob("*.pkf")))
            V1MetadataSeamCompatibilityTests().test_existing_v1_schema_owners_retain_exact_identifiers()

    def test_historical_r0b_launcher_never_activates_v2_capture_or_identity(self):
        with _slice1q_v1_guards():
            R0BLauncherAssemblyTests.setUpClass()
            fixture_test = R0BLauncherAssemblyTests()
            fixture_test.test_public_r0b_connects_frozen_inputs_finalization_reaped_monitor_and_final_source_check()


@_evidence_contextmanager
def _slice1t_sealed_fixture(component, phase="target", *, envelope=None, rich=False, samples=None,
                           with_runtime=True, observation=None):
    """Genuine 1S files from supplied tiny literals, never a calibration collector."""
    from tests.test_program_k_e2_operational import (
        _envelope, _r0_v2_result, _r0_v2_supplied_profile,
        R0V2CurrentDecisionTimingTests)
    profile = _r0_v2_supplied_profile()
    envelope = _envelope(readback_wall_ms=10000, max_payload_bytes=1_000_000,
        archive_cap_bytes=5_000_000, max_physical_inputs=30) if envelope is None else envelope
    if rich:
        R0V2CurrentDecisionTimingTests.setUpClass()
        work, bundles = R0V2CurrentDecisionTimingTests().fixture(component)
    else:
        from tests.test_program_k_e2_execution import _literal_context, _literal_work
        literal = _literal_work(width=1, mines=frozenset())
        with _literal_context(literal, mines=frozenset()):
            primary = execution.execute_primary(literal)
            repeated = execution.execute_repeat(literal, primary)
            kcontrol = execution.execute_k_control(literal, primary)
        work = operational._r0_work(literal, component)
        bundles = (primary, repeated, kcontrol)
    runtime = records.RuntimeIdentity("Slice1TFixturePython", "0", "fixture-os",
        "fixture-platform", "fixture-arch", None) if with_runtime else None
    work = replace(work, runtime=runtime)
    adapted = []
    for bundle in bundles:
        values = dict(bundle.streams)
        if bundle.kind is execution.WorkerKind.PRIMARY and not (work.k_control_selected or work.determinism_selected):
            values.pop("control_maintenance", None)
        for name in ("oracle_b_coverage", "repeat_oracle_b_coverage"):
            if name in values:
                values[name] = tuple(records.encode(replace(records.decode(row),
                    selected=work.oracle_b_selected)) for row in values[name])
        if not work.oracle_b_selected:
            for name in ("oracle_b_audits", "repeat_oracle_b_audits"):
                if name in values:
                    values[name] = ()
        if runtime is not None:
            values["runtime"] = (records.encode(runtime),)
        adapted.append(replace(bundle, streams=tuple((name, values[name])
            for name in execution.STREAM_NAMES if name in values)))
    bundles = tuple(adapted)
    index = {operational.R0Component.PRIMARY: 0, operational.R0Component.ORACLE_B: 0,
        operational.R0Component.K_CONTROL: 2, operational.R0Component.ORACLE_K_BIND: 2,
        operational.R0Component.DETERMINISM: 1, operational.R0Component.ORACLE_D_REPEAT: 1}[component]
    with tempfile.TemporaryDirectory(prefix="slice1t-literal-") as directory:
        anchor = Path(directory)
        budget = operational._R0V2ComponentArchiveBudget(component, envelope)
        def seal(bundle, case_phase):
            result = _r0_v2_result(work, bundle, profile,
                prior_intervals=() if bundle.kind is execution.WorkerKind.PRIMARY else ((10, 12),))
            if rich:
                primary = bundle.kind is execution.WorkerKind.PRIMARY
                kcontrol = bundle.kind is execution.WorkerKind.K_CONTROL
                streams = dict(bundle.streams)
                prefix = "" if primary else "repeat_"
                probes = 2 * sum(records.decode(row).action_ordinal > 0
                    for row in streams[prefix + "kp0_decisions"]) if work.oracle_b_selected and not kcontrol else 0
                calls = sum(records.decode(row).status is not records.AuditStatus.INCOMPLETE
                    for row in streams[prefix + "oracle_b_audits"]) if work.oracle_b_selected and not kcontrol else 0
                inputs = len(streams["kcontrol_maintenance"]) if kcontrol else max(
                    len(streams[prefix + role + "_physical_inputs"]) for role in ("control", "kp0"))
                result = replace(result, receipt=replace(result.receipt, elapsed_ns=1000),
                    observation=replace(result.observation, decision_wall=200 if primary else 70 if kcontrol else 50,
                        arm_wall=300 if primary else 100, shadow_wall=30 if kcontrol else 0, physical_inputs=inputs,
                        oracle=(probes, calls, 0, ((10, 10),) * probes)))
            if samples is not None:
                result = replace(result, samples=tuple(replace(sample,
                    unit_id=operational._unit_id(work.position, bundle.kind)) for sample in samples))
            if observation is not None:
                result = replace(result, observation=observation)
            prior_wire = None if bundle.kind is execution.WorkerKind.PRIMARY else execution.encode_bundle_v2(
                bundles[0], profile.sha256)
            view = execution.decode_bundle_view_v2(result.wire, profile.sha256)
            claim = operational._seal_r0_case_v2(anchor, work, result, envelope, profile, budget,
                phase=case_phase, prior_primary_wire=prior_wire)
            return claim, view
        setup = None
        if index:
            setup, _ = seal(bundles[0], "setup")
        if phase == "setup":
            claim, bundle = setup, bundles[0]
            wire = execution.encode_bundle_v2(bundle, profile.sha256)
            view = execution.decode_bundle_view_v2(wire, profile.sha256)
        else:
            bundle = bundles[index]
            claim, view = seal(bundle, "target")
        yield dict(anchor=anchor, claim=claim, setup=setup, work=work, bundle=bundle,
            view=view, component=component, phase=phase, profile=profile, envelope=envelope)


@_evidence_contextmanager
def _slice1t_readonly_guards():
    with _EvidenceExitStack() as stack:
        for owner, names in (
                (execution, ("encode_bundle_v2", "decode_bundle", "decode_bundle_v2",
                    "decode_bundle_view_v2", "_materialize_board", "execute_primary", "execute_repeat",
                    "execute_k_control")),
                (operational, ("_fresh_wb02_context", "_supervise_operation_core", "_persist_r0",
                    "measure_r0_component", "_seal_r0_case_v2")),
                (physical, ("capture_profile", "capture_qualified_profile")),
                (h, ("capture_run_provenance", "capture_run_provenance_v2", "launch_r0a", "launch_r0b",
                    "_materialize_synthetic_v2", "_readback_synthetic_v2", "_readback_v2_plan")),
                (h.store, ("FramedStreamWriter", "StreamWriter")),
                (h.analysis, ("analyze_effectiveness",))):
            for name in names:
                stack.enter_context(patch.object(owner, name,
                    side_effect=AssertionError("Slice 1T independent readback activated " + name)))
        yield


class R0ACaseReadbackV2Tests(unittest.TestCase):
    """Independent one-case disk authority, including complete negative boundaries."""

    def read(self, fixture, *, claim=None, prior="automatic", **changes):
        claim = fixture["claim"] if claim is None else claim
        with _slice1t_readonly_guards(), patch.object(
                operational.harness, "_coordinator_private_bytes", return_value=100):
            if prior == "automatic":
                prior = None
                if fixture["phase"] == "target" and fixture["setup"] is not None:
                    if "authenticated_setup" not in fixture:
                        fixture["authenticated_setup"] = h._readback_r0a_case_v2(fixture["anchor"],
                            fixture["setup"], fixture["work"], fixture["component"], "setup",
                            fixture["profile"], fixture["envelope"])
                    prior = fixture["authenticated_setup"]
            arguments = dict(anchor=fixture["anchor"], sealed_case=claim, expected_work=fixture["work"],
                expected_component=fixture["component"], expected_phase=fixture["phase"],
                profile=fixture["profile"], envelope=fixture["envelope"], prior_primary=prior)
            arguments.update(changes)
            return h._readback_r0a_case_v2(**arguments)

    @staticmethod
    def snapshot(root):
        return tuple(sorted((str(path.relative_to(root)), path.read_bytes(), path.stat().st_mtime_ns)
                            for path in root.rglob("*") if path.is_file()))

    def rejects(self, fixture, *, before_seals=False, **kwargs):
        before = self.snapshot(fixture["anchor"])
        with _EvidenceExitStack() as stack:
            if before_seals:
                stack.enter_context(patch.object(h.store.FramedStreamPullReader, "close",
                    side_effect=AssertionError("Semantic failure was masked by writer-seal comparison")))
            with self.assertRaises((ValueError, OSError)):
                self.read(fixture, **kwargs)
        self.assertEqual(self.snapshot(fixture["anchor"]), before)

    @staticmethod
    def rows(fixture, name):
        values = []
        root = fixture["anchor"] / fixture["claim"].relative_directory
        h.store.scan_framed_stream(root, name, physical.context_for(name, fixture["profile"].sha256),
            visit=lambda key, record, logical, length: values.append((key, record)))
        return values

    @staticmethod
    def rewrite(fixture, name, rows):
        root = fixture["anchor"] / fixture["claim"].relative_directory
        context = physical.context_for(name, fixture["profile"].sha256)
        (root / (name + ".pkf")).write_bytes(b"".join(
            physical.encode_frame(records.encode(record), key, context) for key, record in rows))

    @staticmethod
    def forged_carrier(carrier, **changes):
        # Test-only corruption, never a production constructor or authority path.
        clone = object.__new__(type(carrier))
        for field in fields(carrier):
            object.__setattr__(clone, field.name, changes.get(field.name, getattr(carrier, field.name)))
        return clone

    def test_all_six_targets_and_four_setups_authenticate_exact_disk_facts(self):
        routes = tuple((component, "target") for component in operational.R0Component) + tuple(
            (component, "setup") for component in (operational.R0Component.K_CONTROL,
                operational.R0Component.DETERMINISM, operational.R0Component.ORACLE_K_BIND,
                operational.R0Component.ORACLE_D_REPEAT))
        families = {operational.R0Component.PRIMARY: "primary", operational.R0Component.K_CONTROL: "k_control",
            operational.R0Component.DETERMINISM: "determinism", operational.R0Component.ORACLE_B: "oracle_primary",
            operational.R0Component.ORACLE_D_REPEAT: "oracle_repeat", operational.R0Component.ORACLE_K_BIND: None}
        for component, phase in routes:
            with self.subTest(component=component, phase=phase), _slice1t_sealed_fixture(component, phase, rich=True) as fixture:
                claim, view = fixture["claim"], fixture["view"]
                before = self.snapshot(fixture["anchor"])
                observed = self.read(fixture)
                self.assertIs(type(observed), h._R0AReadbackCaseV2)
                case = observed.evidence
                self.assertIs(type(case), h.evidence.R0ACaseEvidenceV2)
                self.assertTrue(case.readback_complete)
                self.assertEqual(case.family, "reference" if phase == "setup" else families[component])
                self.assertEqual(case.archive.relative_directory, claim.relative_directory)
                self.assertEqual(case.archive.streams, claim.streams)
                self.assertEqual(len(case.archive.streams), 55)
                self.assertEqual(tuple(s.name for s in case.archive.streams),
                                 execution.STREAM_NAMES + ("operations", "resources"))
                self.assertEqual(sum(s.byte_length for s in case.archive.streams), claim.physical_case_bytes)
                self.assertEqual((case.payload.logical_sum_bytes, case.payload.physical_frame_bytes,
                    case.payload.legacy_bundle_bytes, case.payload.wb02_wire_bytes),
                    (claim.logical_bytes, claim.physical_frame_bytes, claim.legacy_bundle_bytes, claim.wb02_wire_bytes))
                execution.revalidate_bundle(observed.bundle, fixture["work"], claim.receipt.kind,
                                            max_payload_bytes=fixture["envelope"].max_payload_bytes)
                self.assertEqual(observed.bundle, fixture["bundle"])
                self.assertIs(type(observed.work.runtime), records.RuntimeIdentity)
                self.assertEqual(dict(observed.bundle.streams)["runtime"], (records.encode(observed.work.runtime),))
                self.assertEqual((observed.work, observed.component, observed.phase, observed.codec_profile_sha256),
                    (fixture["work"], component, phase, fixture["profile"].sha256))
                def owned(name):
                    if phase == "setup":
                        return name == "control_maintenance"
                    if component is operational.R0Component.PRIMARY:
                        return name not in ("control_maintenance", "oracle_b_audits")
                    if component is operational.R0Component.K_CONTROL:
                        return True
                    if component is operational.R0Component.DETERMINISM:
                        return name != "repeat_oracle_b_audits"
                    if component is operational.R0Component.ORACLE_B:
                        return name == "oracle_b_audits"
                    if component is operational.R0Component.ORACLE_D_REPEAT:
                        return name == "repeat_oracle_b_audits"
                    return False
                selected = tuple(row for row in view.rows if owned(row.stream_name))
                self.assertEqual(case.owned_bytes, h.evidence.R0AByteCountV2(
                    sum(len(row.frame_bytes) for row in selected), sum(len(row.logical_bytes) for row in selected),
                    len(selected)))
                if phase == "target" and component in (operational.R0Component.ORACLE_B,
                                                         operational.R0Component.ORACLE_D_REPEAT):
                    self.assertGreater(len(selected), 0)
                if component in (operational.R0Component.PRIMARY, operational.R0Component.DETERMINISM) and phase == "target":
                    coverage = "oracle_b_coverage" if component is operational.R0Component.PRIMARY else "repeat_oracle_b_coverage"
                    self.assertTrue(any(row.stream_name == coverage for row in selected))
                if component in (operational.R0Component.K_CONTROL, operational.R0Component.DETERMINISM):
                    self.assertTrue(any(row.stream_name == "control_maintenance" for row in selected))
                if component is operational.R0Component.DETERMINISM and phase == "target":
                    self.assertTrue(any(row.stream_name == "repeat_control_maintenance" for row in selected))
                    self.assertTrue(any(row.stream_name == "control_arms" for row in selected))
                self.assertFalse(any(row.stream_name in ("operations", "resources") for row in selected))
                self.assertEqual(self.snapshot(fixture["anchor"]), before)

    def test_zero_oracle_keeps_route_family_positive_payload_and_complete_archive(self):
        for component, family in ((operational.R0Component.ORACLE_B, "oracle_primary"),
                                  (operational.R0Component.ORACLE_D_REPEAT, "oracle_repeat")):
            with self.subTest(component=component), _slice1t_sealed_fixture(component) as fixture:
                observed = self.read(fixture).evidence
                self.assertEqual(observed.family, family)
                self.assertEqual(observed.owned_bytes, h.evidence.R0AByteCountV2(0, 0, 0))
                self.assertTrue(observed.readback_complete)
                self.assertTrue(all(getattr(observed.payload, field.name) > 0 for field in fields(observed.payload)))
                self.assertEqual(len(observed.archive.streams), 55)
                self.assertGreater(sum(item.byte_length for item in observed.archive.streams), 0)

    def test_private_carrier_is_exact_frozen_slotted_nonserializable_and_not_directly_constructible(self):
        import pickle
        with _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
            value = self.read(fixture)
            self.assertFalse(hasattr(value, "__dict__"))
            self.assertEqual(tuple(field.name for field in fields(value)),
                ("evidence", "bundle", "work", "component", "phase", "codec_profile_sha256"))
            for field in fields(value):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, field.name, None)
            for name in ("wire", "context", "view", "token"):
                self.assertFalse(hasattr(value, name))
            with self.assertRaises(TypeError):
                pickle.dumps(value)
            with self.assertRaises(TypeError):
                h._R0AReadbackCaseV2(*(getattr(value, f.name) for f in fields(value)))

    def test_runtime_none_is_rejected_before_inventory_readers_reconstruction_or_evidence(self):
        for component, phase in ((operational.R0Component.PRIMARY, "target"),
                                  (operational.R0Component.K_CONTROL, "setup")):
            with self.subTest(component=component), _slice1t_sealed_fixture(
                    component, phase, with_runtime=False) as fixture:
                self.assertIsNone(fixture["work"].runtime)
                self.assertNotIn("runtime", dict(fixture["bundle"].streams))
                self.assertIs(type(fixture["claim"]), operational._R0V2SealedCase)
                before = self.snapshot(fixture["anchor"])
                with patch.object(h, "_r0a_case_inventory_v2", side_effect=AssertionError("Runtime preflight did inventory")) as inventory, \
                        patch.object(h.store, "FramedStreamPullReader", side_effect=AssertionError("Runtime preflight opened reader")) as reader, \
                        patch.object(h.qualification, "_reconstruct", side_effect=AssertionError("Runtime preflight reconstructed")) as reconstruct, \
                        patch.object(h.evidence, "R0ACaseEvidenceV2", side_effect=AssertionError("Runtime preflight published")) as evidence:
                    with self.assertRaisesRegex(ValueError, "RUNTIME"):
                        self.read(fixture)
                self.assertEqual((inventory.call_count, reader.call_count, reconstruct.call_count, evidence.call_count),
                                 (0, 0, 0, 0))
                self.assertEqual(self.snapshot(fixture["anchor"]), before)

    def test_runtime_stream_requires_exact_expected_record_count_identity_and_key(self):
        for mutation in ("missing", "changed", "duplicate", "position", "rank", "index", "family"):
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                rows = self.rows(fixture, "runtime")
                self.assertEqual(rows, [((fixture["work"].position, 0, 0), fixture["work"].runtime)])
                key, runtime = rows[0]
                if mutation == "missing":
                    rows = []
                elif mutation == "changed":
                    rows = [(key, replace(runtime, python_version="tampered-runtime"))]
                elif mutation == "duplicate":
                    rows.append(((key[0], key[1], 1), runtime))
                elif mutation in ("position", "rank", "index"):
                    axis = ("position", "rank", "index").index(mutation)
                    rows = [(tuple(value + 1 if i == axis else value for i, value in enumerate(key)), runtime)]
                if mutation == "family":
                    with patch.object(physical, "_logical"):
                        data = physical.encode_frame(records.encode(fixture["work"].board), key,
                            physical.context_for("runtime", fixture["profile"].sha256))
                    (fixture["anchor"] / fixture["claim"].relative_directory / "runtime.pkf").write_bytes(data)
                else:
                    self.rewrite(fixture, "runtime", rows)
                self.rejects(fixture, before_seals=True)

    def test_expected_work_component_phase_profile_and_path_are_not_writer_authority(self):
        mutations = ("work", "component", "phase", "relative_directory", "codec_profile_sha256", "receipt_position",
                     "receipt_kind", "receipt_status", "receipt_reason", "receipt_exit_code", "receipt_elapsed_ns")
        for mutation in mutations:
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                claim = fixture["claim"]
                changes = {"work": replace(claim.work, run_id="wrong"), "component": operational.R0Component.ORACLE_B,
                    "phase": "setup", "relative_directory": "calibration/c1/P/01/target", "codec_profile_sha256": b"x" * 32}
                receipt = dict(position=1, kind=execution.WorkerKind.DETERMINISM, status=records.AuditStatus.FAIL,
                               reason="WRONG", exit_code=1, elapsed_ns=0)
                changed = replace(claim, **{mutation: changes[mutation]}) if mutation in changes else replace(
                    claim, receipt=replace(claim.receipt, **{mutation[8:]: receipt[mutation[8:]]}))
                self.rejects(fixture, claim=changed)
        for mutation in ("flags", "work", "component", "phase", "concurrency", "anchor"):
            with self.subTest(expected=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                changes = {"flags": dict(expected_work=replace(fixture["work"], oracle_b_selected=True)),
                    "work": dict(expected_work=replace(fixture["work"], run_id="wrong")),
                    "component": dict(expected_component=operational.R0Component.ORACLE_B),
                    "phase": dict(expected_phase="setup"),
                    "concurrency": dict(envelope=replace(fixture["envelope"], concurrency=4)),
                    "anchor": dict(anchor=fixture["anchor"] / "missing")}[mutation]
                self.rejects(fixture, **changes)

    def test_every_nonprimary_target_requires_authenticated_matching_setup(self):
        for component in (operational.R0Component.K_CONTROL, operational.R0Component.DETERMINISM,
                          operational.R0Component.ORACLE_K_BIND, operational.R0Component.ORACLE_D_REPEAT):
            for mutation in ("missing", "raw", "position", "work", "runtime", "runtime_row", "component", "phase", "profile", "kind", "family", "complete", "path"):
                with self.subTest(component=component, mutation=mutation), _slice1t_sealed_fixture(component) as fixture:
                    setup_fixture = dict(fixture, claim=fixture["setup"], phase="setup")
                    prior = self.read(setup_fixture)
                    case = prior.evidence
                    variants = {
                        "missing": None, "raw": prior.bundle,
                        "position": self.forged_carrier(prior, work=replace(prior.work, position=1)),
                        "work": self.forged_carrier(prior, work=replace(prior.work, run_id="wrong")),
                        "runtime": self.forged_carrier(prior, work=replace(prior.work,
                            runtime=replace(prior.work.runtime, python_version="different"))),
                        "runtime_row": self.forged_carrier(prior, bundle=replace(prior.bundle, streams=tuple(
                            (name, (records.encode(replace(prior.work.runtime, python_version="different")),)
                             if name == "runtime" else rows) for name, rows in prior.bundle.streams))),
                        "component": self.forged_carrier(prior, component=operational.R0Component.PRIMARY),
                        "phase": self.forged_carrier(prior, phase="target"),
                        "profile": self.forged_carrier(prior, codec_profile_sha256=b"x" * 32),
                        "kind": self.forged_carrier(prior, evidence=replace(case,
                            receipt=replace(case.receipt, kind=execution.WorkerKind.K_CONTROL))),
                        "family": self.forged_carrier(prior, evidence=replace(case, family="primary")),
                        "complete": self.forged_carrier(prior,
                            evidence=self.forged_carrier(case, readback_complete=False)),
                        "path": self.forged_carrier(prior, evidence=replace(case,
                            archive=replace(case.archive, relative_directory="calibration/c4/K/63/setup"))),
                    }
                    self.rejects(fixture, prior=variants[mutation])

    def test_primary_and_setup_reject_any_prior(self):
        for component, phase in ((operational.R0Component.PRIMARY, "target"),
                                  (operational.R0Component.K_CONTROL, "setup")):
            with self.subTest(component=component), _slice1t_sealed_fixture(component, phase) as fixture:
                self.rejects(fixture, prior=fixture["bundle"])

    def test_closed_ownership_excludes_support_and_keeps_each_nonempty_policy_boundary(self):
        sizes = {name: (100 + i, 200 + i, 1) for i, name in enumerate(execution.STREAM_NAMES)}
        sizes.update(operations=(10_000, 20_000, 30), resources=(40_000, 50_000, 60))
        names = set(execution.STREAM_NAMES)
        expected = (
            (operational.R0Component.PRIMARY, "target", "primary", names - {"control_maintenance", "oracle_b_audits"}),
            (operational.R0Component.K_CONTROL, "target", "k_control", names),
            (operational.R0Component.DETERMINISM, "target", "determinism", names - {"repeat_oracle_b_audits"}),
            (operational.R0Component.ORACLE_B, "target", "oracle_primary", {"oracle_b_audits"}),
            (operational.R0Component.ORACLE_D_REPEAT, "target", "oracle_repeat", {"repeat_oracle_b_audits"}),
            (operational.R0Component.ORACLE_K_BIND, "target", None, set()),
        ) + tuple((component, "setup", "reference", {"control_maintenance"}) for component in (
            operational.R0Component.K_CONTROL, operational.R0Component.DETERMINISM,
            operational.R0Component.ORACLE_K_BIND, operational.R0Component.ORACLE_D_REPEAT))
        for component, phase, family, owned in expected:
            with self.subTest(component=component, phase=phase):
                actual_family, actual = h._r0a_case_owned_v2(component, phase, sizes)
                self.assertEqual(actual_family, family)
                self.assertEqual(actual, h.evidence.R0AByteCountV2(*(sum(sizes[name][i] for name in owned)
                                                                  for i in range(3))))

    def test_prior_logical_maintenance_control_and_projection_headers_remain_authoritative(self):
        for component, mutation in ((operational.R0Component.K_CONTROL, "maintenance"),
                (operational.R0Component.DETERMINISM, "maintenance"),
                (operational.R0Component.DETERMINISM, "control"),
                (operational.R0Component.DETERMINISM, "kp0"),
                (operational.R0Component.DETERMINISM, "header")):
            with self.subTest(component=component, mutation=mutation), _slice1t_sealed_fixture(component) as fixture:
                prior = self.read(dict(fixture, claim=fixture["setup"], phase="setup"))
                bundle = prior.bundle
                if mutation == "header":
                    first = replace(bundle.projection_headers[0], comparable_compute_ns=1)
                    bundle = replace(bundle, projection_headers=(first,) + bundle.projection_headers[1:])
                else:
                    name = "control_maintenance" if mutation == "maintenance" else mutation + "_decisions"
                    bundle = replace(bundle, streams=tuple((n, () if n == name else rows) for n, rows in bundle.streams))
                self.rejects(fixture, prior=self.forged_carrier(prior, bundle=bundle))

    def test_inventory_rejects_missing_extra_nested_and_renamed_files_without_mutation(self):
        for mutation in ("missing_case", "missing_stream", "extra_pkf", "extra_file", "jsonl", "nested", "renamed"):
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                root = fixture["anchor"] / fixture["claim"].relative_directory
                if mutation == "missing_case":
                    root.rename(root.with_name("missing-target"))
                elif mutation == "missing_stream":
                    (root / "runtime.pkf").unlink()
                elif mutation == "nested":
                    (root / "nested").mkdir()
                elif mutation == "renamed":
                    (root / "runtime.pkf").rename(root / "renamed.pkf")
                else:
                    (root / {"extra_pkf": "extra.pkf", "extra_file": "metadata.json", "jsonl": "boards.jsonl"}[mutation]).write_bytes(b"intrusion")
                self.rejects(fixture)

    def test_nonregular_and_detectable_reparse_shapes_reject(self):
        import stat
        from types import SimpleNamespace
        for mutation in ("stream_directory", "stream_reparse", "ancestor_reparse"):
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                root = fixture["anchor"] / fixture["claim"].relative_directory
                if mutation == "stream_directory":
                    (root / "runtime.pkf").unlink()
                    (root / "runtime.pkf").mkdir()
                    self.rejects(fixture)
                else:
                    original = Path.lstat
                    selected = root / "boards.pkf" if mutation == "stream_reparse" else root.parent
                    def lstat(path, *args, **kwargs):
                        info = original(path, *args, **kwargs)
                        if path == selected:
                            return SimpleNamespace(st_mode=info.st_mode,
                                st_file_attributes=getattr(info, "st_file_attributes", 0) | stat.FILE_ATTRIBUTE_REPARSE_POINT)
                        return info
                    with patch.object(Path, "lstat", new=lstat), self.assertRaises(ValueError):
                        self.read(fixture)

    def test_rf02_truncation_corruption_and_trailing_bytes_reject(self):
        for mutation in ("truncated", "corrupt", "valid_extra", "invalid_extra"):
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                path = fixture["anchor"] / fixture["claim"].relative_directory / "boards.pkf"
                data = path.read_bytes()
                changed = data[:-1] if mutation == "truncated" else data[:-1] + bytes((data[-1] ^ 1,)) if mutation == "corrupt" else data + (data if mutation == "valid_extra" else b"bad")
                path.write_bytes(changed)
                self.rejects(fixture, before_seals=True)

    def test_experiment_keys_record_family_and_missing_extra_rows_reject(self):
        for mutation in ("position", "rank", "index", "duplicate", "missing", "family"):
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                rows = self.rows(fixture, "boards")
                key, record = rows[0]
                if mutation in ("position", "rank", "index"):
                    axis = ("position", "rank", "index").index(mutation)
                    rows = [(tuple(value + 1 if i == axis else value for i, value in enumerate(key)), record)]
                elif mutation == "duplicate":
                    rows += rows
                elif mutation == "missing":
                    rows = []
                if mutation == "family":
                    # Valid CRC under boards context, but the logical family is deliberately wrong.
                    context = physical.context_for("boards", fixture["profile"].sha256)
                    logical = records.encode(fixture["claim"].samples[0])
                    with patch.object(physical, "_logical"):
                        encoded = physical.encode_frame(logical, key, context)
                    (fixture["anchor"] / fixture["claim"].relative_directory / "boards.pkf").write_bytes(encoded)
                else:
                    self.rewrite(fixture, "boards", rows)
                self.rejects(fixture, before_seals=True)

    def test_writer_digest_order_and_total_claims_are_checked_against_actual_disk(self):
        for mutation in ("sha256", "byte_length", "record_count", "name", "order", "physical_case_bytes"):
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                claim = fixture["claim"]
                if mutation == "physical_case_bytes":
                    claim = replace(claim, physical_case_bytes=claim.physical_case_bytes + 1)
                elif mutation == "order":
                    claim = replace(claim, streams=claim.streams[::-1])
                else:
                    first = claim.streams[0]
                    value = "0" * 64 if mutation == "sha256" else "wrong" if mutation == "name" else getattr(first, mutation) + 1
                    claim = replace(claim, streams=(replace(first, **{mutation: value}),) + claim.streams[1:])
                self.rejects(fixture, claim=claim)

    def test_operations_exact_terminal_progress_and_elapsed_contract(self):
        mutations = ("unit_id", "phase", "event_kind", "status", "ordinal", "key", "missing_progress", "extra", "elapsed")
        for mutation in mutations:
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                rows = self.rows(fixture, "operations")
                key, value = rows[0]
                changes = {"unit_id": "wrong", "phase": records.Phase.READBACK, "event_kind": records.EventKind.START,
                    "status": records.OperationStatus.RUNNING, "ordinal": 3}
                if mutation in changes:
                    rows[0] = (key, replace(value, **{mutation: changes[mutation]}))
                elif mutation == "key":
                    rows[0] = ((2,), value)
                elif mutation == "missing_progress":
                    rows = rows[:1]
                elif mutation == "extra":
                    rows.append(((2,), replace(value, ordinal=2)))
                else:
                    rows[0] = (key, replace(value, elapsed_ns=rows[1][1].elapsed_ns + 1))
                self.rewrite(fixture, "operations", rows)
                self.rejects(fixture, before_seals=True)

    def test_resources_exact_samples_identity_role_method_key_and_count(self):
        for mutation in ("unit_id", "role", "method", "missing", "extra", "key", "sample_claim"):
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                rows = self.rows(fixture, "resources")
                key, sample = rows[0]
                if mutation == "sample_claim":
                    self.rejects(fixture, before_seals=True,
                        claim=replace(fixture["claim"], samples=(replace(sample, timestamp="different"),)))
                    continue
                if mutation == "missing":
                    rows = []
                elif mutation == "extra":
                    rows.append(((1,), sample))
                elif mutation == "key":
                    rows = [((1,), sample)]
                else:
                    changes = {"unit_id": dict(unit_id="wrong"), "role": dict(process_role=records.ProcessRole.WORKER),
                               "method": dict(method=records.MemoryMethod.RSS)}[mutation]
                    rows = [(key, replace(sample, **changes))]
                self.rewrite(fixture, "resources", rows)
                self.rejects(fixture, before_seals=True)

    def test_each_payload_axis_is_independently_reconstructed(self):
        for axis in ("logical_bytes", "physical_frame_bytes", "legacy_bundle_bytes", "wb02_wire_bytes"):
            with self.subTest(axis=axis), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                claim = fixture["claim"]
                self.rejects(fixture, before_seals=True,
                    claim=replace(claim, **{axis: getattr(claim, axis) + 1}))

    def test_durable_worker_sum_is_not_individual_live_worker_peak(self):
        from tests.test_program_k_e2_operational import _envelope
        envelope = _envelope(concurrency=2, worker_memory_cap_bytes=500,
            coordinator_memory_cap_bytes=1000, memory_cap_bytes=2000, readback_wall_ms=10000)
        sample = records.ResourceSampleRecord("placeholder", records.ProcessRole.COMBINED,
            700, 200, 900, "shared-ledger", 7, records.MemoryMethod.PRIVATE_BYTES)
        observation = operational._R0Observation(100, 250, 950, 2, 5, 0, 1,
            (0, 0, 0, ()), True, True, True, ())
        with _slice1t_sealed_fixture(operational.R0Component.PRIMARY, envelope=envelope,
                samples=(sample,), observation=observation) as fixture:
            observed = self.read(fixture).evidence
            self.assertEqual(observed.observation.worker_memory, 100)
            self.assertGreater(fixture["claim"].samples[0].worker_bytes, envelope.worker_memory_cap_bytes)
            self.assertLess(fixture["claim"].samples[0].coordinator_bytes, observed.observation.coordinator_memory)
            self.assertLess(fixture["claim"].samples[0].combined_bytes, observed.observation.combined_memory)
            self.assertTrue(observed.readback_complete)

    def test_c1_repeat_telemetry_converts_every_field_without_recomputing_copied_spans(self):
        for component in (operational.R0Component.DETERMINISM, operational.R0Component.ORACLE_D_REPEAT):
            with self.subTest(component=component), _slice1t_sealed_fixture(component, rich=True) as fixture:
                returned = self.read(fixture)
                telemetry, live = returned.evidence.observation, fixture["claim"].observation
                values = dict(returned.bundle.streams)
                copied = max(records.decode(row).duration_ns for row in values["control_decision_spans"])
                current = max(records.decode(row).duration_ns for row in values["repeat_control_decision_spans"])
                self.assertEqual((copied, current, telemetry.arm_wall, telemetry.decision_wall), (200, 50, 100, 50))
                self.assertGreater(copied, telemetry.arm_wall)
                for name in ("worker_memory", "coordinator_memory", "combined_memory", "decision_wall", "arm_wall",
                             "shadow_wall", "physical_inputs", "resources_complete", "cleanup_complete", "watchdogs_complete"):
                    self.assertEqual(getattr(telemetry, name), getattr(live, name))
                self.assertEqual((telemetry.oracle.probes, telemetry.oracle.calls, telemetry.oracle.wall_ns,
                    tuple((i.started_ns, i.finished_ns) for i in telemetry.oracle.intervals)), live.oracle)
                self.assertEqual(tuple((i.started_ns, i.finished_ns) for i in telemetry.prior_binding_intervals),
                                 live.prior_binding_intervals)

    def test_invalid_live_telemetry_is_not_clamped_or_replaced_with_durable_samples(self):
        for mutation in ("decision_scope", "completion", "worker_cap", "coordinator_cap", "combined_cap",
                         "physical_inputs", "coordinator_below_sample", "combined_below_sample"):
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                observation = fixture["claim"].observation
                changes = {"decision_scope": dict(decision_wall=observation.arm_wall + 1),
                    "completion": dict(cleanup_complete=False),
                    "worker_cap": dict(worker_memory=fixture["envelope"].worker_memory_cap_bytes + 1,
                        combined_memory=fixture["envelope"].worker_memory_cap_bytes + 201),
                    "coordinator_cap": dict(coordinator_memory=fixture["envelope"].coordinator_memory_cap_bytes + 1,
                        combined_memory=fixture["envelope"].coordinator_memory_cap_bytes + 101),
                    "combined_cap": dict(combined_memory=fixture["envelope"].memory_cap_bytes + 1),
                    "physical_inputs": dict(physical_inputs=2),
                    "coordinator_below_sample": dict(coordinator_memory=199),
                    "combined_below_sample": dict(combined_memory=299)}[mutation]
                self.rejects(fixture, claim=replace(fixture["claim"], observation=replace(observation, **changes)))

    def test_all_readers_open_before_decode_and_only_eof_close_produces_digests(self):
        reader_type = h.store.FramedStreamPullReader
        original_init, original_pull, original_close = reader_type.__init__, reader_type.pull, reader_type.close
        opened, eof, closed = [], set(), []
        def initialize(reader, *args, **kwargs):
            original_init(reader, *args, **kwargs)
            opened.append(reader)
        def pull(reader):
            self.assertEqual(len(opened), 55)
            row = original_pull(reader)
            if row is None:
                eof.add(id(reader))
            return row
        def close(reader):
            self.assertTrue(reader._eof)
            result = original_close(reader)
            self.assertIs(type(result), records.StreamDigest)
            closed.append(reader)
            return result
        with _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture, \
                patch.object(reader_type, "__init__", new=initialize), \
                patch.object(reader_type, "pull", new=pull), patch.object(reader_type, "close", new=close):
            self.read(fixture)
        self.assertEqual(len(opened), 55)
        self.assertEqual(len(closed), 55)
        self.assertTrue(all(reader.completed_digest is not None for reader in opened))

    def test_outer_semantic_prior_support_and_close_failures_invalidate_every_opened_reader(self):
        reader_type = h.store.FramedStreamPullReader
        original_init, original_close = reader_type.__init__, reader_type.close
        for mutation in ("semantic", "prior", "support", "premature_close", "close_failure",
                         "base_exception", "open_failure", "telemetry", "evidence"):
            component = operational.R0Component.DETERMINISM if mutation == "prior" else operational.R0Component.PRIMARY
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(component) as fixture:
                prior = None
                if fixture["setup"] is not None:
                    prior = self.read(dict(fixture, claim=fixture["setup"], phase="setup"))
                if mutation == "support":
                    self.rewrite(fixture, "operations", [])
                elif mutation == "telemetry":
                    fixture["claim"] = replace(fixture["claim"],
                        observation=replace(fixture["claim"].observation, decision_wall=6))
                opened, closed = [], []
                def initialize(reader, *args, **kwargs):
                    if mutation == "open_failure" and len(opened) == 10:
                        raise OSError("literal reader open failure")
                    original_init(reader, *args, **kwargs)
                    opened.append(reader)
                def close(reader):
                    closed.append(reader)
                    if mutation == "premature_close":
                        reader._eof = False
                    if mutation == "close_failure" and len(closed) == 2:
                        raise OSError("literal read-only close failure")
                    return original_close(reader)
                before = self.snapshot(fixture["anchor"])
                with _EvidenceExitStack() as stack:
                    stack.enter_context(patch.object(reader_type, "__init__", new=initialize))
                    stack.enter_context(patch.object(reader_type, "close", new=close))
                    if mutation in ("semantic", "base_exception"):
                        stack.enter_context(patch.object(h.qualification, "_reconstruct",
                            side_effect=KeyboardInterrupt("literal cancellation") if mutation == "base_exception" else ValueError("semantic failure")))
                    elif mutation == "prior":
                        stack.enter_context(patch.object(h.qualification, "_prior_bundle_v2", side_effect=ValueError("prior failure")))
                    elif mutation == "evidence":
                        stack.enter_context(patch.object(h.evidence, "R0ACaseEvidenceV2",
                            side_effect=ValueError("late evidence construction failure")))
                    with self.assertRaises(KeyboardInterrupt if mutation == "base_exception" else (ValueError, OSError)):
                        self.read(fixture, prior=prior)
                self.assertEqual(len(opened), 10 if mutation == "open_failure" else 55)
                if mutation in ("telemetry", "evidence"):
                    self.assertEqual(len(closed), 55)
                self.assertTrue(all(reader._closed and reader._poisoned and reader.completed_digest is None for reader in opened))
                self.assertEqual(self.snapshot(fixture["anchor"]), before)

    def test_readback_monitor_cancellation_timeout_and_both_memory_caps_fail_closed(self):
        from types import SimpleNamespace
        reader_type = h.store.FramedStreamPullReader
        original_init, original_pull = reader_type.__init__, reader_type.pull
        for mutation in ("cancel", "wall", "coordinator", "combined"):
            with self.subTest(mutation=mutation), _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
                opened, pulled = [], [False]
                def initialize(reader, *args, **kwargs):
                    original_init(reader, *args, **kwargs)
                    opened.append(reader)
                def pull(reader):
                    result = original_pull(reader)
                    pulled[0] = True
                    return result
                def clock():
                    return fixture["envelope"].readback_wall_ms * 1_000_000 if mutation == "wall" and pulled[0] else 0
                def memory():
                    if not pulled[0]:
                        return 100
                    cap = fixture["envelope"].coordinator_memory_cap_bytes if mutation == "coordinator" else fixture["envelope"].memory_cap_bytes
                    return cap + 1 if mutation in ("coordinator", "combined") else 100
                before = self.snapshot(fixture["anchor"])
                with _slice1t_readonly_guards(), patch.object(reader_type, "__init__", new=initialize), \
                        patch.object(reader_type, "pull", new=pull), patch.object(h.time, "monotonic_ns", side_effect=clock), \
                        patch.object(operational.harness, "_coordinator_private_bytes", side_effect=memory), self.assertRaises(ValueError):
                    h._readback_r0a_case_v2(fixture["anchor"], fixture["claim"], fixture["work"],
                        fixture["component"], fixture["phase"], fixture["profile"], fixture["envelope"],
                        cancel=SimpleNamespace(is_set=lambda: mutation == "cancel" and pulled[0]))
                self.assertEqual(len(opened), 55)
                self.assertTrue(all(reader._closed and reader._poisoned and reader.completed_digest is None for reader in opened))
                self.assertEqual(self.snapshot(fixture["anchor"]), before)

    def test_existing_v1_synthetic_and_non_r0_v2_owners_do_not_reference_new_boundary(self):
        owners = (h._readback_v2_plan, h._readback_synthetic_v2, h._v2_readback_unit,
            h._v2_readback_prior, h._v2_readback_support, h.launch_r0a, h.launch_r0b,
            operational.measure_r0_component, operational._persist_r0, operational._seal_r0_case_v2,
            operational._workflow_v2, operational._supervise_operation_v2, operational._supervise_r0_operation_v2)
        for owner in owners:
            with self.subTest(owner=owner.__name__):
                self.assertNotIn("_readback_r0a_case_v2", inspect.getsource(owner))
        with patch.object(h, "_readback_r0a_case_v2", side_effect=AssertionError("Implicit readback")), \
                _slice1t_sealed_fixture(operational.R0Component.PRIMARY) as fixture:
            self.assertIs(type(fixture["claim"]), operational._R0V2SealedCase)


class _Slice1UClock:
    """Deliberately disjoint clocks: evidence timestamps cannot be deadlines."""

    def __init__(self):
        self.value = 10_000_000
        self.monotonic_value = 100
        self.lock = threading.Lock()

    def perf_counter_ns(self):
        with self.lock:
            self.value += 10
            return self.value

    def monotonic_ns(self):
        return self.monotonic_value


class _Slice1UCarrier:
    """Test-only readback seam; public evidence is real, private life is tracked."""

    def __init__(self, evidence, work, component, phase, profile):
        self.evidence, self.work, self.component, self.phase = evidence, work, component, phase
        self.codec_profile_sha256 = profile.sha256


class _Slice1UFuture:
    def __init__(self, pool, function, arguments):
        self.pool, self.function, self.arguments = pool, function, arguments
        self.value = self.error = None
        self.completed = self.cancelled = False

    def execute(self):
        if not self.cancelled:
            try:
                self.value = self.function(*self.arguments)
            except BaseException as error:
                self.error = error
        self.function = self.arguments = None
        self.completed = True

    def result(self):
        if not self.completed:
            self.pool.drain()
        if self.cancelled:
            from concurrent.futures import CancelledError
            raise CancelledError()
        if self.error is not None:
            raise self.error
        return self.value

    def cancel(self):
        self.pool.world.events.append(("future_cancel", self.pool.world.cancel.is_set()))
        if not self.completed:
            self.cancelled = True
            self.function = self.arguments = None
            self.completed = True
            return True
        return False


class _Slice1UPool:
    """One deterministic reversed-completion wave, with no retained history."""

    def __init__(self, world, max_workers, **kwargs):
        import weakref
        self.world, self.limit = world, max_workers
        self.pending, self.closed = [], False
        self.futures = weakref.WeakSet()
        self.maximum_pending = 0
        world.pools.append(self)
        world.events.append(("pool_enter", max_workers))

    def submit(self, function, *arguments):
        assert not self.closed
        assert len(self.pending) < self.limit, "Unbounded future queue"
        work, kind, prior = arguments[:3]
        phase = "setup" if kind is execution.WorkerKind.PRIMARY and (
            work.determinism_selected or work.k_control_selected) else "target"
        if not self.pending:
            assert not tuple(self.futures), "Previous phase futures retained"
        if phase == "target" and prior is not None:
            offset = work.position // self.limit * self.limit
            assert all((self.world.component_for(work), "setup", p) in self.world.readbacks
                       for p in range(offset, min(offset + self.limit, 64))), "Target before setup authentication"
        if work.position % self.limit == 0 and phase != "target":
            assert not tuple(self.world.carriers), "Previous wave private carriers retained"
        self.world.events.append(("submit", phase, work.position))
        future = _Slice1UFuture(self, function, arguments)
        self.pending.append(future)
        self.futures.add(future)
        self.maximum_pending = max(self.maximum_pending, len(self.pending))
        return future

    def drain(self):
        pending, self.pending = self.pending, []
        self.world.binding_base = self.world.clock.perf_counter_ns()
        for future in reversed(pending):
            future.execute()

    def shutdown(self, wait=True, cancel_futures=False):
        self.world.events.append(("pool_shutdown", self.world.cancel.is_set(), wait, cancel_futures))
        if cancel_futures:
            for future in self.pending:
                future.cancel()
        self.pending.clear()
        self.closed = True
        if self.world.failure == "pool_close":
            raise RuntimeError("injected pool close failure")


class _Slice1UIdleThread:
    """Disable background scheduling while using the real monitor's checkpoints."""

    def __init__(self, world):
        self.world, self.ident, self.closed = world, None, False

    def start(self):
        self.ident = 1

    def join(self, timeout=None):
        self.closed = True
        self.world.events.append(("monitor_join", self.world.cancel.is_set()))
        if self.world.failure == "final_deadline":
            self.world.clock.monotonic_value += self.world.envelope.max_job_wall_ms * 1_000_000

    def is_alive(self):
        return self.world.failure == "monitor_close"


class _Slice1UFixture:
    """Mocked execution/disk claims for 64-unit collector orchestration only.

    The real monitor, archive budget and 1R constructors are exercised. This
    fixture does not claim its synthetic readback seam authenticates disk.
    Selected separate tests below use genuine 1S and 1T instead.
    """

    def __init__(self, concurrency=2, *, failure=None, zero_oracle=False):
        import weakref
        from tests.test_program_k_e2_operational import _envelope, _r0_v2_supplied_profile
        self.profile = _r0_v2_supplied_profile()
        self.envelope = _envelope(concurrency=concurrency, archive_cap_bytes=10_000_000)
        runtime = records.RuntimeIdentity("Slice1UFixture", "0", "fixture-os", "fixture-platform", "fixture-arch", None)
        self.work = tuple(operational.R0Work(position,
            records.BoardIdentity(70_000_000 + position, "slice1u-literal-" + str(position),
                1, 1, 0, (0, 0), "supplied-fixture", "supplied-fixture"),
            b"u" * 32, "R0-1U-LITERAL", runtime) for position in range(64))
        self.clock, self.cancel = _Slice1UClock(), threading.Event()
        self.failure, self.zero_oracle = failure, zero_oracle
        self.events, self.budgets, self.ledgers, self.monitors, self.pools = [], [], [], [], []
        self.readbacks, self.authenticated = set(), {}
        self.carriers = weakref.WeakSet()
        self.wires, self.prior_identities = {}, []
        self.seals, self.progress_facts, self.setup_counts = [], [], []
        self.max_carriers, self.max_setup_carriers, self.max_target_carriers, self.binding_base = 0, 0, 0, 0
        self.expected_monitor_counts = []
        self.original_budget = operational._R0V2ComponentArchiveBudget
        self.original_ledger = operational._MemoryLedger
        self.original_monitor = operational._R0MemoryMonitor

    @staticmethod
    def component_for(work):
        return next(component for component in operational.R0Component
                    if operational._r0_work(work, component) == work)

    def budget(self, component, envelope):
        value = self.original_budget(component, envelope)
        self.budgets.append(value)
        self.events.append(("budget", component.value))
        return value

    def ledger(self, envelope):
        value = self.original_ledger(envelope)
        self.ledgers.append(value)
        return value

    def monitor(self, ledger, cancel, envelope):
        value = self.original_monitor(ledger, cancel, envelope)
        value.thread = _Slice1UIdleThread(self)
        self.monitors.append(value)
        return value

    def memory(self):
        if self.failure == "memory" and self.seals:
            return self.envelope.coordinator_memory_cap_bytes + 1
        return 500 if self.monitors and self.monitors[-1].setup is not None else 900

    def supervise(self, work, kind, prior, envelope, ledger, cancel, job_start, launcher_start, digest):
        assert job_start == launcher_start == 100, "Evidence clock used as deadline clock"
        assert digest == self.profile.sha256 and ledger is self.ledgers[-1]
        component = self.component_for(work)
        phase = "setup" if kind is execution.WorkerKind.PRIMARY and component in operational._R0_SETUP_ROUTES else "target"
        if prior is not None:
            assert prior is self.wires[(component, "setup", work.position)]
            self.prior_identities.append((phase, work.position, id(prior)))
        self.events.append(("worker", phase, work.position, self.clock.perf_counter_ns()))
        if self.failure == "worker_exception" and work.position == 0:
            raise RuntimeError("injected worker exception")
        status = (records.AuditStatus.FAIL if self.failure == "worker_fail" else records.AuditStatus.INCOMPLETE)
        if self.failure in ("worker_fail", "worker_incomplete") and work.position == 0:
            return operational._R0V2OperationResult(operational.UnitReceipt(work.position, kind,
                status, "SYNTHETIC_FAILURE", 50, 0), None, digest, (), None, 0, 0, 0, 0)
        wire = (b"WB02" + bytes((work.position, operational._kind_rank(kind))) + b"supplied").ljust(2000, b"x")
        self.wires[(component, phase, work.position)] = wire
        binding = ((self.binding_base, self.binding_base + 5), (self.binding_base + 5, self.binding_base + 8)) \
            if component is operational.R0Component.ORACLE_K_BIND and phase == "target" else ()
        observation = operational._R0Observation(10, 20, 30, 1, 2, 0, 1,
            (0, 0, 0, ()), True, True, True, binding)
        sample = records.ResourceSampleRecord(operational._unit_id(work.position, kind), records.ProcessRole.COMBINED,
            10, 20, 30, "slice1u:literal", 50, records.MemoryMethod.PRIVATE_BYTES)
        value = operational._R0V2OperationResult(operational.UnitReceipt(work.position, kind,
            records.AuditStatus.PASS, "ADMITTED", 50, 0), wire, digest, (sample,), observation,
            1000, 1500, 1200, len(wire))
        if self.failure == "missing_wire" and work.position == 0:
            object.__setattr__(value, "wire", None)
        return value

    def seal(self, anchor, work, result, envelope, profile, budget, *, phase, prior_primary_wire=None):
        component = budget.component
        assert profile is self.profile and budget is self.budgets[-1]
        if prior_primary_wire is not None:
            assert prior_primary_wire is self.wires[(component, "setup", work.position)]
        started, finished = self.clock.perf_counter_ns(), self.clock.perf_counter_ns()
        relative = operational._r0_case_path_v2(envelope.concurrency, component, work.position, phase)
        directory = Path(anchor) / relative
        directory.mkdir(parents=True)
        streams = tuple(records.StreamDigest(name, "a" * 64, 500, 1)
                        for name in execution.STREAM_NAMES + ("operations", "resources"))
        byte_length = sum(s.byte_length for s in streams)
        reservation = budget.reserve((work.position, phase), byte_length)
        if self.failure == "seal" and work.position == 0:
            (directory / "operations.pkf").write_bytes(b"partial")
            raise OSError("injected partial sealing failure")
        claim = operational._R0V2SealedCase(work, component, phase, relative, result.receipt, streams,
            profile.sha256, result.samples, result.observation, result.logical_bytes, result.physical_frame_bytes,
            result.legacy_bundle_bytes, result.wb02_wire_bytes, (started, finished), byte_length)
        budget.commit(reservation, byte_length)
        self.seals.append((component, phase, work.position, claim.parent_admission_interval))
        self.events.append(("seal", phase, work.position, finished))
        return claim

    def readback(self, anchor, claim, work, component, phase, profile, envelope, *, prior_primary=None, cancel=None):
        import weakref
        assert profile is self.profile and claim.work == work and claim.component is component and claim.phase == phase
        if self.failure == "readback" and work.position == 0:
            raise ValueError("injected independent readback failure")
        if prior_primary is not None:
            assert prior_primary is self.authenticated[(component, "setup", work.position)]()
            assert prior_primary.work == work and prior_primary.codec_profile_sha256 == profile.sha256
            if self.failure == "prior":
                raise ValueError("injected authenticated prior mismatch")
        families = dict(P="primary", K="k_control", O="oracle_primary", D="determinism",
                        O_K_BIND=None, O_D_REPEAT="oracle_repeat")
        family = "reference" if phase == "setup" else families[component.value]
        owned = h.evidence.R0AByteCountV2(0, 0, 0) if family is None or (
            self.zero_oracle and family in ("oracle_primary", "oracle_repeat")) else h.evidence.R0AByteCountV2(
                300 if work.position == 0 else 200, 400 if work.position == 1 else 300, 1)
        observed = claim.observation
        telemetry = h.evidence.R0ATelemetryV2(observed.worker_memory, observed.coordinator_memory,
            observed.combined_memory, observed.decision_wall, observed.arm_wall, observed.shadow_wall,
            observed.physical_inputs, h.evidence.R0AOracleTelemetryV2(0, 0, 0, ()), True, True, True,
            tuple(h.evidence.R0AIntervalV2(*interval) for interval in observed.prior_binding_intervals))
        case = h.evidence.R0ACaseEvidenceV2(claim.receipt, telemetry,
            h.evidence.R0APayloadAxesV2(claim.logical_bytes, claim.legacy_bundle_bytes,
                claim.wb02_wire_bytes, claim.physical_frame_bytes),
            h.evidence.R0AArchiveEvidenceV2(claim.relative_directory, claim.streams), family, owned, True)
        carrier = _Slice1UCarrier(case, work, component, phase, profile)
        self.carriers.add(carrier)
        self.max_carriers = max(self.max_carriers, len(self.carriers))
        self.max_setup_carriers = max(self.max_setup_carriers, sum(c.phase == "setup" for c in self.carriers))
        self.max_target_carriers = max(self.max_target_carriers, sum(c.phase == "target" for c in self.carriers))
        self.authenticated[(component, phase, work.position)] = weakref.ref(carrier)
        self.readbacks.add((component, phase, work.position))
        self.events.append(("readback", phase, work.position, self.clock.perf_counter_ns()))
        if self.failure == "cancel" and work.position == 0:
            cancel.set()
        if self.failure == "deadline" and work.position == 0:
            self.clock.monotonic_value += envelope.max_job_wall_ms * 1_000_000
        if self.failure == "budget" and work.position == 63:
            self.budgets[-1]._committed_bytes += 1
        return carrier

    def progress(self, component, fact):
        import sys
        assert type(fact) is h.evidence.R0AProgressV2
        assert not tuple(self.carriers), "Private carrier escaped wave into progress"
        assert not tuple(self.pools[-1].futures), "Completed Future retained operation result"
        # Only the test's dictionary, loop value and getrefcount temporary remain.
        assert all(sys.getrefcount(value) == 3 for value in self.wires.values()), "Live wire escaped wave"
        self.wires.clear()
        assert (component, "target", fact.position) in self.readbacks
        self.events.append(("progress", fact.position, self.clock.perf_counter_ns()))
        self.progress_facts.append((component, fact))
        if self.failure == "callback":
            raise RuntimeError("injected callback failure")

    @_evidence_contextmanager
    def patches(self):
        with _EvidenceExitStack() as stack:
            for owner, name, replacement in (
                (h.time, "perf_counter_ns", self.clock.perf_counter_ns),
                (h.time, "monotonic_ns", self.clock.monotonic_ns),
                (operational, "_R0V2ComponentArchiveBudget", self.budget),
                (operational, "_MemoryLedger", self.ledger),
                (operational, "_R0MemoryMonitor", self.monitor),
                (operational.harness, "_coordinator_private_bytes", self.memory),
                (h, "ThreadPoolExecutor", lambda **kwargs: _Slice1UPool(self, **kwargs)),
                (operational, "_supervise_r0_operation_v2", self.supervise),
                (operational, "_seal_r0_case_v2", self.seal),
                (h, "_readback_r0a_case_v2", self.readback)):
                stack.enter_context(patch.object(owner, name, new=replacement))
            for owner, names in (
                (execution, ("encode_bundle_v2", "make_work_plan", "revalidate_work_plan", "_materialize_board")),
                (physical, ("capture_profile", "capture_qualified_profile")),
                (h, ("_materialize_r0a_work", "capture_run_provenance", "capture_run_provenance_v2",
                     "launch_r0a", "launch_r0b", "_materialize_synthetic_v2")),
                (h.evidence, ("R0AObservationsV2",)),
                (identity, ("select_indices", "select_subset_positions")),
                (h.analysis, ("analyze_effectiveness",))):
                for name in names:
                    stack.enter_context(patch.object(owner, name,
                        side_effect=AssertionError("Slice 1U collector activated forbidden " + name)))
            yield self

    def collect(self, anchor, component=operational.R0Component.PRIMARY):
        return h._collect_r0a_component_v2(self.work, component, anchor, self.envelope, self.profile,
                                          cancel=self.cancel, progress=self.progress)


class R0ACollectorInputV2Tests(unittest.TestCase):
    def test_all_identity_defects_reject_before_mutation_or_worker(self):
        fixture = _Slice1UFixture()
        def changed(index, **changes):
            values = list(fixture.work)
            value = replace(values[index])
            for name, item in changes.items():
                object.__setattr__(value, name, item)
            values[index] = value
            return tuple(values)
        mutations = (list(fixture.work), fixture.work[:-1], fixture.work + fixture.work[:1],
            changed(0, position=True), changed(1, position=0), changed(1, board=fixture.work[0].board),
            changed(1, protocol_seed=b"z" * 32), changed(1, run_id="R0-OTHER"), changed(0, run_id="OTHER"),
            changed(0, runtime=None), changed(0, runtime=object()),
            changed(1, runtime=replace(fixture.work[0].runtime, python_version="different")),
            tuple(replace(value, run_id="R0-") for value in fixture.work),
            (object(),) + fixture.work[1:])
        with tempfile.TemporaryDirectory() as directory, fixture.patches(), \
                patch.object(Path, "mkdir", side_effect=AssertionError("Invalid input mutated filesystem")):
            for work in mutations:
                with self.subTest(work=type(work), first=work[0] if work else None), self.assertRaises(ValueError):
                    h._collect_r0a_component_v2(work, operational.R0Component.PRIMARY, directory,
                                               fixture.envelope, fixture.profile)
            self.assertFalse(fixture.events)
            self.assertEqual(tuple(Path(directory).iterdir()), ())

    def test_envelope_profile_callback_cancel_and_component_domains(self):
        fixture = _Slice1UFixture()
        invalid_envelope = replace(fixture.envelope)
        object.__setattr__(invalid_envelope, "concurrency", True)
        invalid_three = replace(fixture.envelope)
        object.__setattr__(invalid_three, "concurrency", 3)
        node = json.loads(fixture.profile.canonical_bytes)
        node["status"] = "UNQUALIFIED_SLICE_1A"
        from tests.test_program_k_e2_physical import _json_bytes
        unqualified = physical.CodecProfile(_json_bytes(node))
        with tempfile.TemporaryDirectory() as directory, fixture.patches():
            for changes in ({"envelope": invalid_envelope}, {"envelope": invalid_three}, {"envelope": object()}, {"profile": object()},
                            {"profile": unqualified}, {"progress": 1}, {"cancel": object()}, {"component": "P"}):
                args = dict(work=fixture.work, component=operational.R0Component.PRIMARY, anchor=directory,
                            envelope=fixture.envelope, profile=fixture.profile)
                args.update(changes)
                with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError):
                    h._collect_r0a_component_v2(**args)
            self.assertFalse(fixture.events)

    def test_precancelled_input_has_no_workers_markers_or_budget(self):
        fixture = _Slice1UFixture()
        fixture.cancel.set()
        with tempfile.TemporaryDirectory() as directory, fixture.patches(), self.assertRaises(ValueError):
            fixture.collect(directory)
        self.assertFalse(fixture.events)

    def test_all_six_roots_are_preflighted_before_first_component(self):
        fixture = _Slice1UFixture()
        with tempfile.TemporaryDirectory() as directory:
            conflict = Path(directory) / "calibration/c2/O_D_REPEAT"
            conflict.mkdir(parents=True)
            with fixture.patches(), self.assertRaisesRegex(ValueError, "ALREADY_EXISTS"):
                h._collect_r0a_concurrency_v2(fixture.work, directory, fixture.envelope, fixture.profile)
            self.assertFalse(fixture.events)
            self.assertEqual(tuple(conflict.iterdir()), ())

    def test_existing_empty_component_and_non_directory_parent_reject(self):
        for shape in ("empty_component", "parent_file"):
            fixture = _Slice1UFixture()
            with self.subTest(shape=shape), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "calibration"
                if shape == "empty_component":
                    (path / "c2/P").mkdir(parents=True)
                else:
                    path.write_bytes(b"not a directory")
                with fixture.patches(), self.assertRaises((ValueError, OSError)):
                    fixture.collect(directory)
                self.assertFalse(fixture.events)

    def test_detectable_reparse_and_junction_ancestors_reject(self):
        from types import SimpleNamespace
        fixture = _Slice1UFixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).absolute()
            original = Path.lstat
            def reparse(path, *args, **kwargs):
                info = original(path, *args, **kwargs)
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400) if path == root else info
            with fixture.patches(), patch.object(Path, "lstat", new=reparse), self.assertRaises(ValueError):
                fixture.collect(directory)
            if hasattr(Path, "is_junction"):
                with fixture.patches(), patch.object(Path, "is_junction", return_value=True), self.assertRaises(ValueError):
                    fixture.collect(directory)
            self.assertFalse(fixture.events)


class R0ACollectorComponentV2Tests(unittest.TestCase):
    def test_real_executor_bounds_active_fake_workers_for_all_concurrencies(self):
        from concurrent.futures import ThreadPoolExecutor
        for concurrency in (1, 2, 4):
            fixture = _Slice1UFixture(concurrency)
            barrier, lock = threading.Barrier(concurrency), threading.Lock()
            active, peak, pools = [0], [0], []
            original = fixture.supervise
            def supervise(*args):
                work = args[0]
                if work.position >= concurrency:
                    previous = work.position // concurrency * concurrency - concurrency
                    assert all((operational.R0Component.PRIMARY, "target", p) in fixture.readbacks
                               for p in range(previous, previous + concurrency))
                with lock:
                    active[0] += 1
                    peak[0] = max(peak[0], active[0])
                try:
                    barrier.wait(timeout=5)
                    return original(*args)
                finally:
                    with lock:
                        active[0] -= 1
            class Pool(ThreadPoolExecutor):
                def __init__(self, **kwargs):
                    super().__init__(**kwargs)
                    pools.append(self)
            fixture.supervise = supervise
            with self.subTest(c=concurrency), tempfile.TemporaryDirectory() as directory, fixture.patches(), \
                    patch.object(h, "ThreadPoolExecutor", new=Pool):
                value = h._collect_r0a_component_v2(fixture.work, operational.R0Component.PRIMARY,
                    directory, fixture.envelope, fixture.profile, cancel=fixture.cancel)
            self.assertEqual(peak[0], concurrency)
            self.assertEqual(active[0], 0)
            self.assertEqual(len(value.units), 64)
            self.assertEqual(len(pools), 1)
            self.assertTrue(all(not thread.is_alive() for thread in pools[0]._threads))

    def test_bounded_reverse_completion_preserves_admission_progress_and_release_for_each_c(self):
        for concurrency in (1, 2, 4):
            fixture = _Slice1UFixture(concurrency)
            with self.subTest(c=concurrency), tempfile.TemporaryDirectory() as directory, fixture.patches():
                value = fixture.collect(directory, operational.R0Component.K_CONTROL)
            self.assertEqual(len(fixture.budgets), 1)
            self.assertEqual(len(fixture.ledgers), 1)
            self.assertEqual(len(fixture.monitors), 1)
            self.assertEqual(len(fixture.pools), 1)
            self.assertEqual(fixture.pools[0].maximum_pending, concurrency)
            self.assertEqual(tuple(v.position for v in value.units), tuple(range(64)))
            self.assertEqual(tuple(f.position for _, f in fixture.progress_facts), tuple(range(64)))
            self.assertEqual(tuple(w.positions for w in value.setup_waves),
                tuple(tuple(range(i, i + concurrency)) for i in range(0, 64, concurrency)))
            workers = [event[2] for event in fixture.events if event[:2] == ("worker", "setup")]
            self.assertEqual(workers[:concurrency], list(reversed(range(concurrency))))
            for phase in ("setup", "target"):
                self.assertEqual([v[2] for v in fixture.seals if v[1] == phase], list(range(64)))
            self.assertLessEqual(fixture.max_carriers, 2 * concurrency)
            self.assertLessEqual(fixture.max_setup_carriers, concurrency)
            self.assertLessEqual(fixture.max_target_carriers, concurrency)
            self.assertFalse(tuple(fixture.carriers))
            self.assertFalse(fixture.wires)

    def test_all_six_flags_owned_families_and_standalone_complete_walls(self):
        flags = ((False, False, False), (False, False, True), (True, False, False),
                 (False, True, False), (True, False, True), (True, True, False))
        families = ("primary", "k_control", "oracle_primary", "determinism", None, "oracle_repeat")
        for component, expected_flags, family in zip(operational.R0Component, flags, families):
            fixture = _Slice1UFixture(4, zero_oracle=True)
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory, fixture.patches():
                value = fixture.collect(directory, component)
            derived = operational._r0_work(fixture.work[0], component)
            self.assertEqual((derived.oracle_b_selected, derived.determinism_selected, derived.k_control_selected), expected_flags)
            self.assertIs(derived.runtime, fixture.work[0].runtime)
            self.assertTrue(all(u.target.family == family for u in value.units))
            if component in operational._R0_SETUP_ROUTES:
                self.assertTrue(all(u.setup.family == "reference" for u in value.units))
                self.assertEqual(len(fixture.seals), 128)
            else:
                self.assertTrue(all(u.setup is None for u in value.units))
                self.assertEqual(len(fixture.seals), 64)
            if component.value in ("P", "K", "O", "D"):
                self.assertEqual(value.wall_intervals, (h.evidence.R0AWallIntervalV2(
                    "COMPLETE_ROUTE", tuple(range(64)), value.complete_interval),))
                self.assertEqual(value.wall_ns, value.complete_interval.duration_ns)
            self.assertTrue(all(type(u.target) is h.evidence.R0ACaseEvidenceV2 for u in value.units))
            self.assertNotIn("wire", {field.name for field in fields(value.units[0].target)})

    def test_setup_authentication_precedes_every_target_submission_and_progress(self):
        fixture = _Slice1UFixture(4)
        with tempfile.TemporaryDirectory() as directory, fixture.patches():
            value = fixture.collect(directory, operational.R0Component.DETERMINISM)
        events = fixture.events
        for wave in value.setup_waves:
            setup_reads = [i for i, event in enumerate(events) if event[0:2] == ("readback", "setup") and event[2] in wave.positions]
            target_submits = [i for i, event in enumerate(events) if event[0:2] == ("submit", "target") and event[2] in wave.positions]
            target_reads = [i for i, event in enumerate(events) if event[0:2] == ("readback", "target") and event[2] in wave.positions]
            progress = [i for i, event in enumerate(events) if event[0] == "progress" and event[1] in wave.positions]
            self.assertLess(max(setup_reads), min(target_submits))
            self.assertLess(max(target_reads), min(progress))
            self.assertLessEqual(wave.setup_interval.finished_ns, wave.target_interval.started_ns)
        self.assertEqual(len(fixture.prior_identities), 64)

    def test_budget_reconciles_all_55_streams_and_exact_cap(self):
        fixture = _Slice1UFixture()
        fixture.envelope = replace(fixture.envelope, archive_cap_bytes=64 * 55 * 500)
        with tempfile.TemporaryDirectory() as directory, fixture.patches():
            value = fixture.collect(directory)
        budget = fixture.budgets[0]
        self.assertIsNone(budget.pending)
        self.assertFalse(budget.aborted)
        self.assertEqual(budget.committed_bytes, budget.cap_bytes)
        self.assertEqual(budget.committed_bytes,
            sum(s.byte_length for unit in value.units for s in unit.target.archive.streams))
        self.assertGreater(budget.committed_bytes, sum(unit.target.owned_bytes.physical_bytes for unit in value.units))
        self.assertTrue(all(len(unit.target.archive.streams) == 55 for unit in value.units))

    def test_case_exceeding_remaining_cap_by_one_aborts_without_refund(self):
        fixture = _Slice1UFixture()
        fixture.envelope = replace(fixture.envelope, archive_cap_bytes=64 * 55 * 500 - 1)
        with tempfile.TemporaryDirectory() as directory, fixture.patches(), self.assertRaisesRegex(ValueError, "ARCHIVE_CAP"):
            fixture.collect(directory)
        self.assertEqual(len(fixture.budgets), 1)
        self.assertTrue(fixture.budgets[0].aborted)
        self.assertEqual(fixture.budgets[0].committed_bytes, 63 * 55 * 500)

    def test_real_monitor_setup_and_global_facts_are_not_durable_samples(self):
        fixture = _Slice1UFixture()
        with tempfile.TemporaryDirectory() as directory, fixture.patches():
            value = fixture.collect(directory, operational.R0Component.K_CONTROL)
        monitor = fixture.monitors[0]
        self.assertEqual(value.monitor, h.evidence.R0AMonitorEvidenceV2(
            monitor.coordinator, monitor.combined, monitor.memory_sample_count))
        self.assertEqual((value.monitor.coordinator_private_peak_bytes, value.monitor.combined_peak_bytes), (900, 900))
        self.assertTrue(all((w.monitor.coordinator_private_peak_bytes, w.monitor.combined_peak_bytes) == (500, 500)
                            and w.monitor.memory_sample_count > 0 for w in value.setup_waves))
        self.assertGreater(value.monitor.memory_sample_count, sum(w.monitor.memory_sample_count for w in value.setup_waves))
        self.assertTrue(monitor.thread.closed)
        self.assertEqual(fixture.ledgers[0].values, {})
        self.assertGreater(value.monitor.coordinator_private_peak_bytes, value.units[0].target.observation.coordinator_memory)
        shutdown = next(i for i, event in enumerate(fixture.events) if event[0] == "pool_shutdown")
        joined = next(i for i, event in enumerate(fixture.events) if event[0] == "monitor_join")
        self.assertLess(shutdown, joined)

    def test_oracle_k_exact_live_phases_union_and_position_order(self):
        fixture = _Slice1UFixture(4)
        with tempfile.TemporaryDirectory() as directory, fixture.patches():
            value = fixture.collect(directory, operational.R0Component.ORACLE_K_BIND)
        rows = value.wall_intervals
        self.assertEqual({r.phase for r in rows}, {"ORCHESTRATION", "PRIOR_ENCODE", "PRIOR_BIND", "PARENT_ADMISSION", "CLEANUP"})
        self.assertEqual(sum(r.phase == "ORCHESTRATION" for r in rows), 1)
        self.assertEqual(sum(r.phase == "CLEANUP" for r in rows), 1)
        self.assertEqual(tuple(r.positions for r in rows if r.phase == "PRIOR_ENCODE"), tuple(w.positions for w in value.setup_waves))
        expected_bindings = tuple(sorted((h.evidence.R0AWallIntervalV2("PRIOR_BIND", (u.position,), i)
            for u in value.units for i in u.target.observation.prior_binding_intervals), key=h.evidence._r0a_wall_key))
        self.assertEqual(tuple(r for r in rows if r.phase == "PRIOR_BIND"), expected_bindings)
        admissions = tuple(r for r in rows if r.phase == "PARENT_ADMISSION")
        self.assertEqual(tuple(r.positions for r in admissions), tuple((p,) for p in range(64)))
        claims = tuple(v[3] for v in fixture.seals if v[1] == "target")
        self.assertEqual(tuple((r.interval.started_ns, r.interval.finished_ns) for r in admissions), claims)
        endpoints = sorted({x for r in rows for x in (r.interval.started_ns, r.interval.finished_ns)})
        independent_union = sum(b - a for a, b in zip(endpoints, endpoints[1:])
            if any(r.interval.started_ns <= a < b <= r.interval.finished_ns for r in rows))
        self.assertEqual(value.wall_ns, independent_union)
        self.assertLess(value.wall_ns, sum(r.interval.duration_ns for r in rows))
        self.assertLess(value.wall_ns, value.complete_wall_ns)

    def test_oracle_repeat_target_intervals_cover_readback_and_exclude_setup(self):
        fixture = _Slice1UFixture(2)
        with tempfile.TemporaryDirectory() as directory, fixture.patches():
            value = fixture.collect(directory, operational.R0Component.ORACLE_D_REPEAT)
        rows = value.wall_intervals
        self.assertEqual({r.phase for r in rows}, {"ORCHESTRATION", "TARGET_PHASE", "CLEANUP"})
        self.assertEqual(tuple((r.positions, r.interval) for r in rows if r.phase == "TARGET_PHASE"),
                         tuple((w.positions, w.target_interval) for w in value.setup_waves))
        self.assertTrue(all(a.interval.finished_ns <= b.interval.started_ns for a, b in zip(rows, rows[1:])))
        self.assertEqual(value.wall_ns, sum(r.interval.duration_ns for r in rows))
        for wave in value.setup_waves:
            for event in fixture.events:
                if event[0] in ("seal", "readback") and event[1] == "target" and event[2] in wave.positions:
                    self.assertLessEqual(wave.target_interval.started_ns, event[3])
                    self.assertLessEqual(event[3], wave.target_interval.finished_ns)
        self.assertEqual(rows[-1].phase, "CLEANUP")
        self.assertEqual(rows[-1].interval.started_ns, value.setup_waves[-1].target_interval.finished_ns)
        self.assertEqual(rows[-1].interval.finished_ns, value.complete_interval.finished_ns)

    def test_component_can_never_be_resumed_even_with_empty_existing_root(self):
        fixture = _Slice1UFixture()
        with tempfile.TemporaryDirectory() as directory, fixture.patches():
            fixture.collect(directory)
            before = len(fixture.events)
            with self.assertRaisesRegex(ValueError, "ALREADY_EXISTS"):
                fixture.collect(directory)
            self.assertEqual(len(fixture.events), before)


class R0ACollectorFailureV2Tests(unittest.TestCase):
    def test_monitor_entry_failure_preserves_original_even_if_its_cleanup_fails(self):
        fixture = _Slice1UFixture()
        monitors = []
        original_error = RuntimeError("original monitor entry failure")
        class Monitor:
            def __init__(self, ledger, cancel, envelope):
                self.stop = threading.Event()
                self.thread = _Slice1UIdleThread(fixture)
                self.thread.ident = 1
                self.closed = False
                monitors.append(self)
            def __enter__(self):
                raise original_error
            def __exit__(self, *args):
                self.closed = True
                raise RuntimeError("secondary cleanup failure")
        with tempfile.TemporaryDirectory() as directory, fixture.patches(), \
                patch.object(operational, "_R0MemoryMonitor", new=Monitor):
            with self.assertRaises(RuntimeError) as caught:
                fixture.collect(directory)
        self.assertIs(caught.exception, original_error)
        self.assertTrue(monitors[0].stop.is_set())
        self.assertTrue(monitors[0].closed)
        self.assertTrue(fixture.cancel.is_set())
        self.assertTrue(fixture.budgets[0].aborted)
        self.assertFalse(fixture.pools)

    def test_executor_creation_failure_reaps_the_already_started_monitor(self):
        fixture = _Slice1UFixture()
        with tempfile.TemporaryDirectory() as directory, fixture.patches(), patch.object(h,
                "ThreadPoolExecutor", side_effect=RuntimeError("executor construction")):
            with self.assertRaisesRegex(RuntimeError, "executor construction"):
                fixture.collect(directory)
        self.assertTrue(fixture.cancel.is_set())
        self.assertTrue(fixture.budgets[0].aborted)
        self.assertTrue(fixture.monitors[0].thread.closed)

    def test_every_failure_reaps_and_terminally_aborts_without_retry(self):
        failures = ("worker_exception", "worker_fail", "worker_incomplete", "missing_wire", "seal", "readback",
                    "prior", "memory", "deadline", "cancel", "callback", "budget", "pool_close", "monitor_close", "final_deadline")
        for failure in failures:
            fixture = _Slice1UFixture(failure=failure)
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory, fixture.patches():
                with self.assertRaises((ValueError, RuntimeError, OSError)):
                    fixture.collect(directory, operational.R0Component.K_CONTROL)
                self.assertTrue(fixture.cancel.is_set())
                self.assertEqual(len(fixture.budgets), 1)
                self.assertTrue(fixture.budgets[0].aborted)
                self.assertTrue(fixture.pools[0].closed)
                self.assertTrue(fixture.monitors[0].thread.closed)
                if failure == "seal":
                    path = Path(directory) / "calibration/c2/K/00/setup/operations.pkf"
                    self.assertEqual(path.read_bytes(), b"partial")
                    self.assertIsNotNone(fixture.budgets[0].pending)
                if failure == "readback":
                    self.assertEqual(fixture.budgets[0].committed_bytes, 2 * 55 * 500)
                    self.assertFalse(any(event[:2] == ("submit", "target") for event in fixture.events))
                if failure in ("callback", "readback", "seal", "prior", "worker_exception", "worker_fail", "worker_incomplete", "missing_wire", "memory", "deadline", "cancel"):
                    shutdown = next(event for event in fixture.events if event[0] == "pool_shutdown")
                    self.assertTrue(shutdown[1], "Cancellation must precede executor wait")
                self.assertLessEqual(len(fixture.progress_facts), 64)

    def test_public_constructor_failure_does_not_turn_cleanup_into_success(self):
        fixture = _Slice1UFixture()
        with tempfile.TemporaryDirectory() as directory, fixture.patches(), patch.object(
                h.evidence, "R0AComponentEvidenceV2", side_effect=ValueError("injected constructor failure")):
            with self.assertRaisesRegex(ValueError, "constructor"):
                fixture.collect(directory)
        self.assertTrue(fixture.cancel.is_set())
        self.assertTrue(fixture.budgets[0].aborted)
        self.assertEqual(fixture.budgets[0].committed_bytes, 64 * 55 * 500)
        self.assertTrue(fixture.monitors[0].thread.closed)
        self.assertTrue(fixture.pools[0].closed)


class R0ACollectorConcurrencyV2Tests(unittest.TestCase):
    def test_exact_six_components_distinct_owners_and_pure_assembly(self):
        fixture = _Slice1UFixture(4, zero_oracle=True)
        with tempfile.TemporaryDirectory() as directory, fixture.patches():
            value = h._collect_r0a_concurrency_v2(fixture.work, directory, fixture.envelope, fixture.profile,
                                                 cancel=fixture.cancel, progress=fixture.progress)
        self.assertEqual(tuple(v.component for v in value.components), h.evidence.R0A_COMPONENTS_V2)
        self.assertEqual(value.run_id, fixture.work[0].run_id)
        self.assertEqual(value.envelope, fixture.envelope)
        self.assertEqual(value.concurrency, 4)
        self.assertEqual(value.family_summaries, h.evidence.summarize_r0a_components_v2(value.components))
        self.assertEqual(value.containment, h.evidence.derive_r0a_containment_v2(value.components))
        self.assertEqual(tuple(c.route for c in value.containment), readiness.CALIBRATION_ROUTES)
        for owners in (fixture.budgets, fixture.ledgers, fixture.monitors, fixture.pools):
            self.assertEqual(len(owners), 6)
            self.assertEqual(len({id(owner) for owner in owners}), 6)
        for budget, component in zip(fixture.budgets, value.components):
            exact = sum(seal.byte_length for unit in component.units
                for case in ((unit.target,) if unit.setup is None else (unit.setup, unit.target)) for seal in case.archive.streams)
            self.assertEqual(budget.committed_bytes, exact)
            self.assertIsNone(budget.pending)
            self.assertFalse(budget.aborted)
        self.assertEqual(len(value.family_summaries), 9)
        self.assertTrue(all(s.record_count == 0 for s in value.family_summaries if s.family.startswith("oracle")))
        for changed in (value.components[::-1], value.components[:-1]):
            with self.assertRaises(ValueError):
                replace(value, components=changed)
        with self.assertRaises(ValueError):
            replace(value, family_summaries=value.family_summaries[::-1])

    def test_first_failed_component_stops_concurrency_and_sets_cancel(self):
        fixture = _Slice1UFixture()
        calls = []
        def failed(*args, **kwargs):
            calls.append(args[1])
            raise RuntimeError("component failed")
        with tempfile.TemporaryDirectory() as directory, patch.object(h, "_collect_r0a_component_v2", new=failed), \
                self.assertRaisesRegex(RuntimeError, "component failed"):
            h._collect_r0a_concurrency_v2(fixture.work, directory, fixture.envelope, fixture.profile, cancel=fixture.cancel)
        self.assertEqual(calls, [operational.R0Component.PRIMARY])
        self.assertTrue(fixture.cancel.is_set())

    def test_late_component_failure_preserves_earlier_archives_and_never_starts_later_routes(self):
        fixture = _Slice1UFixture(4)
        original = h._collect_r0a_component_v2
        calls = []
        def collect(*args, **kwargs):
            component = args[1]
            calls.append(component.value)
            if component is operational.R0Component.DETERMINISM:
                raise RuntimeError("late D failure")
            return original(*args, **kwargs)
        with tempfile.TemporaryDirectory() as directory, fixture.patches(), \
                patch.object(h, "_collect_r0a_component_v2", new=collect):
            with self.assertRaisesRegex(RuntimeError, "late D failure"):
                h._collect_r0a_concurrency_v2(fixture.work, directory, fixture.envelope, fixture.profile,
                                             cancel=fixture.cancel, progress=fixture.progress)
            self.assertEqual({p.name for p in (Path(directory) / "calibration/c4").iterdir()}, {"P", "K", "O"})
        self.assertEqual(calls, ["P", "K", "O", "D"])
        self.assertTrue(fixture.cancel.is_set())
        self.assertEqual(len(fixture.budgets), 3)
        self.assertTrue(all(not budget.aborted and budget.committed_bytes > 0 for budget in fixture.budgets))

    def test_existing_owners_never_activate_collectors(self):
        owners = (h.launch_r0a, h.launch_r0b, h._measure_r0a, h.adapt_r0a_concurrency,
            h._materialize_v2_plan, h._readback_v2_plan, h._readback_r0a_case_v2,
            operational._seal_r0_case_v2, operational.measure_r0_component,
            operational._workflow_v2, operational._supervise_operation_v2)
        for owner in owners:
            with self.subTest(owner=owner.__name__):
                source = inspect.getsource(owner)
                self.assertNotIn("_collect_r0a_component_v2", source)
                self.assertNotIn("_collect_r0a_concurrency_v2", source)


class R0ACollectorIntegrationV2Tests(unittest.TestCase):
    def test_small_literal_waves_use_real_1s_seal_and_1t_readback(self):
        from concurrent.futures import ThreadPoolExecutor
        from tests.test_program_k_e2_operational import _r0_v2_result
        for component in (operational.R0Component.PRIMARY, operational.R0Component.K_CONTROL):
            with self.subTest(component=component), _slice1t_sealed_fixture(component, rich=True) as fixture:
                work = fixture["work"]
                supplied = operational.R0Work(work.position, work.board, work.protocol_seed, work.run_id, work.runtime)
                profile, envelope = fixture["profile"], fixture["envelope"]
                primary = None
                if fixture["setup"] is not None:
                    with patch.object(operational.harness, "_coordinator_private_bytes", return_value=100):
                        primary = h._readback_r0a_case_v2(fixture["anchor"], fixture["setup"], work, component,
                            "setup", profile, envelope)
                bundles = {fixture["bundle"].kind: (fixture["bundle"], fixture["claim"])}
                if primary is not None:
                    bundles[execution.WorkerKind.PRIMARY] = (primary.bundle, fixture["setup"])
                results = {}
                for kind, (bundle, claim) in bundles.items():
                    result = _r0_v2_result(work, bundle, profile)
                    results[kind] = replace(result, receipt=claim.receipt, samples=claim.samples,
                                            observation=claim.observation)
                seen, returned = [], []
                def supervise(expected_work, kind, prior, *args):
                    self.assertEqual(expected_work, work)
                    if kind is not execution.WorkerKind.PRIMARY:
                        self.assertTrue(any(phase == "setup" for phase, _ in returned))
                        self.assertIs(prior, results[execution.WorkerKind.PRIMARY].wire)
                    seen.append(kind)
                    return results[kind]
                readback = h._readback_r0a_case_v2
                def authenticate(*args, **kwargs):
                    carrier = readback(*args, **kwargs)
                    returned.append((args[4], carrier.evidence))
                    return carrier
                cancel = threading.Event()
                ledger = operational._MemoryLedger(envelope)
                budget = operational._R0V2ComponentArchiveBudget(component, envelope)
                with tempfile.TemporaryDirectory(prefix="slice1u-real-chain-") as directory, \
                        patch.object(operational.harness, "_coordinator_private_bytes", return_value=100), \
                        patch.object(operational, "_supervise_r0_operation_v2", new=supervise), \
                        patch.object(h, "_readback_r0a_case_v2", new=authenticate), \
                        patch.object(execution, "encode_bundle_v2", side_effect=AssertionError("Collector regenerated prior")), \
                        operational._R0MemoryMonitor(ledger, cancel, envelope) as monitor, \
                        ThreadPoolExecutor(max_workers=envelope.concurrency) as pool:
                    units, setup_wave, rows, finished = h._collect_r0a_wave_v2((supplied,), component, directory,
                        envelope, profile, budget, ledger, monitor, pool, cancel, h.time.monotonic_ns())
                    self.assertEqual(len(units), 1)
                    self.assertIs(type(units[0]), h.evidence.R0AUnitEvidenceV2)
                    self.assertEqual(units[0].target, returned[-1][1])
                    expected_cases = 1 if primary is None else 2
                    self.assertEqual(len(tuple(Path(directory).rglob("*.pkf"))), expected_cases * 55)
                    self.assertFalse(tuple(Path(directory).rglob("*.jsonl")))
                    self.assertIsNone(budget.pending)
                    self.assertFalse(budget.aborted)
                    self.assertEqual(budget.committed_bytes, sum(seal.byte_length for _, case in returned for seal in case.archive.streams))
                    self.assertGreater(finished, 0)
                    if primary is not None:
                        self.assertEqual(units[0].setup, returned[0][1])
                        self.assertEqual(setup_wave.positions, (0,))
                        self.assertGreater(setup_wave.monitor.memory_sample_count, 0)
                    else:
                        self.assertIsNone(setup_wave)
                    self.assertEqual(rows, ())
                self.assertEqual(seen, [execution.WorkerKind.PRIMARY] if primary is None else
                    [execution.WorkerKind.PRIMARY, execution.WorkerKind.K_CONTROL])


def _slice1v_supplied_observations():
    """Literal 1R claims with 1U paths; not generated boards or case authentication."""
    from tests.test_program_k_e2_r0_evidence import _r0a_supplied_fixture_v2
    value = _r0a_supplied_fixture_v2()
    concurrencies = []
    for concurrency in value.concurrencies:
        components = []
        for component in concurrency.components:
            owner = operational.R0Component(component.component)
            units = []
            for unit in component.units:
                def case_path(case, phase):
                    return replace(case, archive=replace(case.archive,
                        relative_directory=operational._r0_case_path_v2(
                            concurrency.concurrency, owner, unit.position, phase)))
                units.append(replace(unit, target=case_path(unit.target, "target"),
                    setup=None if unit.setup is None else case_path(unit.setup, "setup")))
            components.append(replace(component, units=tuple(units)))
        concurrencies.append(replace(concurrency, components=tuple(components)))
    return replace(value, concurrencies=tuple(concurrencies))


class _Slice1VFixture:
    """Fake collector boundary with small archive sentinels and real public codec."""

    def __init__(self, root, observations):
        self.root = Path(root)
        self.output = self.root / "r0a-observations-v2.json"
        # The path intentionally does not exist: 1V may authenticate supplied bytes only.
        self.receipt = h.AcceptedSelectionReceipt(str(self.root / "absent-receipt.json"),
                                                  _accepted_receipt_bytes())
        self.observations = observations
        self.profile = physical.decode_profile(observations.codec_profile_bytes)
        self.plan = readiness.R0APlan(observations.plan.protocol_seed,
                                     tuple(board.game_index for board in observations.plan.boards))
        sources = tuple(records.SourceBlobIdentity(path, "a" * 40, "b" * 64, 10)
                        for path in h.qualification._V2_SOURCE_PATHS)
        working = tuple((source.path, source.sha256, source.byte_length, False) for source in sources)
        self.provenance = h.RunProvenance(h.SELECTION_SOURCE_HEAD, "c" * 40, sources, working,
                                          observations.runtime, "C:\\supplied\\python.exe", True)
        self.work = tuple(tuple(operational.R0Work(position, board, self.plan.protocol_seed,
            concurrency.run_id, self.provenance.runtime) for position, board in enumerate(observations.plan.boards))
            for concurrency in observations.concurrencies)
        self.envelopes = tuple(value.envelope for value in observations.concurrencies)
        self.cancel = threading.Event()
        self.calls, self.events, self.emitted = [], [], []
        self.active = self.maximum_active = self.rechecks = 0
        self.fail_concurrency = self.fail_recheck = None
        self.returned = {}

    def collect(self, work, anchor, envelope, profile, *, cancel, progress):
        concurrency = envelope.concurrency
        self.calls.append((work, anchor, envelope, profile, cancel, progress))
        self.events.append(("enter", concurrency))
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            directory = Path(anchor) / "calibration" / ("c" + str(concurrency))
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "sentinel").write_bytes(("preserve-c" + str(concurrency)).encode("ascii"))
            if concurrency == self.fail_concurrency:
                raise RuntimeError("collector failure")
            value = self.returned.get(concurrency, self.observations.concurrencies[(1, 2, 4).index(concurrency)])
            if progress is not None:
                for component in value.components:
                    owner = operational.R0Component(component.component)
                    for fact in component.progress:
                        self.emitted.append((concurrency, owner, fact))
                        progress(owner, fact)
            return value
        finally:
            self.active -= 1
            self.events.append(("exit", concurrency))

    def recheck(self):
        self.rechecks += 1
        self.events.append(("recheck", self.rechecks))
        if self.rechecks == self.fail_recheck:
            raise RuntimeError("live drift")
        return object()  # Deliberately different each time: never an authority token.

    def invoke(self, **changes):
        arguments = dict(receipt=self.receipt, provenance=self.provenance, plan=self.plan,
            work_by_concurrency=self.work, envelopes=self.envelopes, profile=self.profile,
            anchor=self.root, output_path=self.output, live_recheck=self.recheck,
            cancel=self.cancel, progress=None)
        arguments.update(changes)
        return h._assemble_r0a_observations_v2(**arguments)


class R0AObservationsAssemblyV2Tests(unittest.TestCase):
    """Slice 1V outer boundary only; collectors are always bounded supplied fakes."""

    @classmethod
    def setUpClass(cls):
        cls.supplied = _slice1v_supplied_observations()

    @_evidence_contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory(prefix="slice1v-outer-") as directory:
            fixture = _Slice1VFixture(directory, self.supplied)
            with patch.object(h, "_collect_r0a_concurrency_v2", new=fixture.collect):
                yield fixture

    @staticmethod
    def corrupt(value, **changes):
        value = replace(value)
        for name, changed in changes.items():
            object.__setattr__(value, name, changed)
        return value

    @staticmethod
    def work_slot(fixture, slot, offset, **changes):
        work = list(fixture.work)
        values = list(work[slot])
        values[offset] = R0AObservationsAssemblyV2Tests.corrupt(values[offset], **changes)
        work[slot] = tuple(values)
        return tuple(work)

    def assert_preflight_rejected(self, fixture, **changes):
        before = tuple(fixture.root.rglob("*"))
        with self.assertRaises((ValueError, TypeError, OSError)):
            fixture.invoke(**changes)
        self.assertEqual(fixture.calls, [])
        self.assertEqual(tuple(fixture.root.rglob("*")), before)
        self.assertFalse(fixture.output.exists())
        self.assertTrue(fixture.cancel.is_set())

    def test_exact_receipt_provenance_plan_profile_and_callback_types(self):
        for kind in ("receipt-object", "receipt-subclass", "receipt-bytes", "provenance-object",
                     "provenance-subclass", "plan-object", "plan-subclass", "profile-object",
                     "profile-subclass", "profile-unqualified", "profile-corrupt", "live", "progress"):
            with self.subTest(kind=kind), self.fixture() as f:
                changes = {}
                if kind.endswith("-object"):
                    changes[kind[:-7]] = object()
                elif kind.endswith("-subclass"):
                    name = kind[:-9]
                    value = getattr(f, name)
                    subclass = type("SuppliedSubclass", (type(value),), {})
                    changes[name] = subclass(**{field.name: getattr(value, field.name) for field in fields(value)})
                elif kind == "receipt-bytes":
                    changes["receipt"] = self.corrupt(f.receipt, canonical_bytes=b"{}\n")
                elif kind == "profile-corrupt":
                    changes["profile"] = self.corrupt(f.profile, canonical_bytes=b"{}")
                elif kind == "profile-unqualified":
                    node = json.loads(f.profile.canonical_bytes)
                    node["status"] = "UNQUALIFIED_SLICE_1A"
                    changes["profile"] = physical.decode_profile(physical._json(node))
                else:
                    changes["live_recheck" if kind == "live" else "progress"] = object()
                self.assert_preflight_rejected(f, **changes)

    def test_provenance_fields_and_v2_source_coverage_reject_before_collection(self):
        for field, value in (("selection_source_head", "d" * 40), ("r0_harness_source_head", "bad"),
                             ("runtime", None), ("executable", ""), ("dont_write_bytecode", False),
                             ("working_files", ()), ("sources", ()), ("sources", "missing"),
                             ("sources", "reordered")):
            with self.subTest(field=field, value=value), self.fixture() as f:
                changes = {field: value}
                if value == "missing":
                    changes = dict(sources=f.provenance.sources[:-1], working_files=f.provenance.working_files[:-1])
                elif value == "reordered":
                    changes = dict(sources=f.provenance.sources[::-1], working_files=f.provenance.working_files[::-1])
                self.assert_preflight_rejected(f, provenance=self.corrupt(f.provenance, **changes))

    def test_plan_seed_and_first_64_identity_revalidation(self):
        for kind in ("wrong-seed", "wrong-indices", "duplicate", "reordered"):
            with self.subTest(kind=kind), self.fixture() as f:
                if kind == "wrong-seed":
                    plan = readiness.build_r0a_plan(b"x" * 32)
                else:
                    indices = f.plan.ordered_indices
                    changed = indices[::-1] if kind == "reordered" else (indices[1],) + indices[1:]
                    if kind == "wrong-indices":
                        changed = (0,) + indices[1:]
                    plan = self.corrupt(f.plan, ordered_indices=changed)
                self.assert_preflight_rejected(f, plan=plan)

    def test_tuple_work_position_board_seed_run_and_runtime_cross_bindings(self):
        cases = ("outer-list", "outer-short", "outer-long", "inner-list", "inner-short", "work-object",
                 "position", "board-index", "board-drift", "duplicate-board", "seed", "duplicate-run",
                 "empty-run", "invalid-run", "nonprintable-run", "runtime-none", "runtime-within",
                 "runtime-cross", "runtime-provenance", "envelope-list", "envelope-short",
                 "envelope-order", "envelope-object")
        for kind in cases:
            with self.subTest(kind=kind), self.fixture() as f:
                work, envelopes = f.work, f.envelopes
                runtime = replace(f.provenance.runtime, architecture="different")
                if kind == "outer-list": work = list(work)
                elif kind == "outer-short": work = work[:2]
                elif kind == "outer-long": work = work + work[:1]
                elif kind == "inner-list": work = (list(work[0]),) + work[1:]
                elif kind == "inner-short": work = (work[0][:-1],) + work[1:]
                elif kind == "work-object": work = ((object(),) + work[0][1:],) + work[1:]
                elif kind == "position": work = self.work_slot(f, 2, 0, position=1)
                elif kind == "board-index": work = self.work_slot(f, 2, 0, board=replace(work[2][0].board, game_index=0))
                elif kind == "board-drift": work = self.work_slot(f, 2, 0, board=replace(work[2][0].board, fingerprint="other"))
                elif kind == "duplicate-board": work = self.work_slot(f, 2, 0, board=work[2][1].board)
                elif kind == "seed": work = self.work_slot(f, 2, 0, protocol_seed=b"x" * 32)
                elif kind == "duplicate-run": work = (work[0], tuple(replace(w, run_id=work[0][0].run_id) for w in work[1]), work[2])
                elif kind in ("empty-run", "invalid-run", "nonprintable-run"):
                    bad = {"empty-run": "R0-", "invalid-run": "wrong", "nonprintable-run": "R0-\x01"}[kind]
                    work = self.work_slot(f, 2, 0, run_id=bad)
                elif kind == "runtime-none": work = self.work_slot(f, 2, 0, runtime=None)
                elif kind == "runtime-within": work = self.work_slot(f, 2, 0, runtime=runtime)
                elif kind == "runtime-cross": work = work[:2] + (tuple(replace(w, runtime=runtime) for w in work[2]),)
                elif kind == "runtime-provenance": work = tuple(tuple(replace(w, runtime=runtime) for w in values) for values in work)
                elif kind == "envelope-list": envelopes = list(envelopes)
                elif kind == "envelope-short": envelopes = envelopes[:2]
                elif kind == "envelope-order": envelopes = envelopes[::-1]
                elif kind == "envelope-object": envelopes = (object(),) + envelopes[1:]
                self.assert_preflight_rejected(f, work_by_concurrency=work, envelopes=envelopes)

    def test_invalid_and_precancelled_tokens_do_not_collect(self):
        for token in (object(), type("NoSetter", (), {"is_set": lambda self: False})(),
                      type("NoGetter", (), {"set": lambda self: None})()):
            with self.subTest(token=type(token).__name__), self.fixture() as f:
                with self.assertRaises((ValueError, TypeError)):
                    f.invoke(cancel=token)
                self.assertEqual(f.calls, [])
                self.assertEqual(tuple(f.root.iterdir()), ())
        with self.fixture() as f:
            f.cancel.set()
            self.assert_preflight_rejected(f)
            self.assertEqual(f.rechecks, 0)

    def test_wrong_arity_recheck_and_broken_cancel_set_preserve_original_failure(self):
        with self.fixture() as f:
            self.assert_preflight_rejected(f, live_recheck=lambda required: None)
        with self.fixture() as f:
            class BrokenSetter:
                def is_set(self): return False
                def set(self): raise RuntimeError("broken cancellation setter")
            failure = RuntimeError("original callback failure")
            def recheck(): raise failure
            with self.assertRaises(RuntimeError) as raised:
                f.invoke(cancel=BrokenSetter(), live_recheck=recheck)
            self.assertIs(raised.exception, failure)
            self.assertEqual(f.calls, [])

    def test_all_concurrency_component_paths_preflight_before_c1(self):
        for concurrency in (1, 2, 4):
            for component in h.evidence.R0A_COMPONENTS_V2:
                with self.subTest(concurrency=concurrency, component=component), self.fixture() as f:
                    occupied = f.root / "calibration" / ("c" + str(concurrency)) / component
                    occupied.mkdir(parents=True)
                    self.assert_preflight_rejected(f)
                    self.assertTrue(occupied.is_dir())

    def test_output_and_anchor_paths_fail_before_collection(self):
        for kind in ("missing-anchor", "file-anchor", "output-file", "output-directory",
                     "wrong-name", "outside-child", "nested-child", "parent-alias", "bad-calibration"):
            with self.subTest(kind=kind), self.fixture() as f:
                changes = {}
                if kind == "missing-anchor": changes["anchor"] = f.root / "missing"
                elif kind == "file-anchor":
                    target = f.root / "file"
                    target.write_bytes(b"keep")
                    changes["anchor"] = target
                elif kind == "output-file": f.output.write_bytes(b"keep")
                elif kind == "output-directory": f.output.mkdir()
                elif kind == "wrong-name": changes["output_path"] = f.root / "r0a-observations.json"
                elif kind == "outside-child": changes["output_path"] = f.root.parent / f.output.name
                elif kind == "nested-child": changes["output_path"] = f.root / "nested" / f.output.name
                elif kind == "parent-alias": changes["output_path"] = f.root / "nested" / ".." / f.output.name
                else: (f.root / "calibration").write_bytes(b"keep")
                before = {str(p): p.read_bytes() for p in f.root.rglob("*") if p.is_file()}
                with self.assertRaises((ValueError, TypeError, OSError)):
                    f.invoke(**changes)
                self.assertEqual(f.calls, [])
                self.assertTrue(f.cancel.is_set())
                self.assertEqual({str(p): p.read_bytes() for p in f.root.rglob("*") if p.is_file()}, before)

    def test_detectable_reparse_and_output_link_are_rejected(self):
        from types import SimpleNamespace
        original = Path.lstat
        for kind in ("anchor", "output"):
            with self.subTest(kind=kind), self.fixture() as f:
                def lstat(path, *args, **kwargs):
                    if kind == "anchor" and path == f.root:
                        info = original(path, *args, **kwargs)
                        return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
                    if kind == "output" and path == f.output:
                        return SimpleNamespace(st_mode=h.stat.S_IFLNK, st_file_attributes=0x400)
                    return original(path, *args, **kwargs)
                with patch.object(Path, "lstat", new=lstat), self.assertRaises((ValueError, OSError)):
                    f.invoke()
                self.assertEqual(f.calls, [])
                self.assertTrue(f.cancel.is_set())

    def test_exact_sequential_calls_content_and_seven_gate_trace(self):
        with self.fixture() as f:
            encode = h.evidence.encode_r0a_observations_v2
            decode = h.evidence.decode_r0a_observations_v2
            write = h._exclusive_bytes
            encoded_values, decoded_values = [], []
            def encoding(value):
                encoded_values.append(value)
                return encode(value)
            def writing(path, data):
                f.events.append(("write",))
                return write(path, data)
            def decoding(data, **bindings):
                value = decode(data, **bindings)
                f.events.append(("decode",))
                decoded_values.append((value, bindings))
                return value
            with patch.object(h.evidence, "encode_r0a_observations_v2", new=encoding), \
                    patch.object(h.evidence, "decode_r0a_observations_v2", new=decoding), \
                    patch.object(h, "_exclusive_bytes", new=writing):
                result = f.invoke()
            self.assertEqual(f.events, [("recheck", 1), ("enter", 1), ("exit", 1), ("recheck", 2),
                ("enter", 2), ("exit", 2), ("recheck", 3), ("enter", 4), ("exit", 4), ("recheck", 4),
                ("recheck", 5), ("write",), ("decode",), ("recheck", 6), ("recheck", 7)])
            self.assertEqual(f.maximum_active, 1)
            for index, call in enumerate(f.calls):
                self.assertIs(call[0], f.work[index])
                self.assertEqual(Path(call[1]), f.root)
                self.assertIs(call[2], f.envelopes[index])
                self.assertIs(call[3], f.profile)
                self.assertIs(call[4], f.cancel)
            expected = replace(f.observations, source_head=f.provenance.r0_harness_source_head,
                provenance_sha256=h.evidence.provenance_digest_v2(f.provenance.selection_source_head,
                    f.provenance.r0_harness_source_head, f.provenance.sources, f.provenance.working_files,
                    f.provenance.runtime, f.provenance.executable, f.provenance.dont_write_bytecode))
            self.assertEqual(result.observations, expected)
            self.assertIs(result.observations, decoded_values[0][0])
            self.assertIsNot(result.observations, encoded_values[0])
            self.assertIsNot(result.observations.concurrencies[0], f.observations.concurrencies[0])
            bindings = decoded_values[0][1]
            self.assertEqual(bindings, dict(expected_profile_sha256=f.profile.sha256.hex(),
                expected_provenance_sha256=expected.provenance_sha256,
                expected_source_head=f.provenance.r0_harness_source_head,
                expected_selection_receipt_sha256=h.SELECTION_RECEIPT_SHA256,
                expected_plan=expected.plan, expected_runtime=f.provenance.runtime))
            self.assertFalse(f.cancel.is_set())

    def test_none_cancel_creates_exactly_one_shared_invocation_event(self):
        with self.fixture() as f:
            original = threading.Event
            with patch.object(h.threading, "Event", wraps=original) as factory:
                f.invoke(cancel=None)
            self.assertEqual(factory.call_count, 1)
            tokens = [call[4] for call in f.calls]
            self.assertTrue(all(token is tokens[0] for token in tokens))
            self.assertIsNot(tokens[0], f.cancel)
            self.assertFalse(tokens[0].is_set())

    def test_each_collector_failure_stops_later_work_and_preserves_archives(self):
        for failed in (1, 2, 4):
            with self.subTest(failed=failed), self.fixture() as f:
                f.fail_concurrency = failed
                with patch.object(h.evidence, "encode_r0a_observations_v2", side_effect=AssertionError("no encode")), \
                        self.assertRaisesRegex(RuntimeError, "collector failure"):
                    f.invoke()
                expected = (1, 2, 4)[:(1, 2, 4).index(failed) + 1]
                self.assertEqual(tuple(call[2].concurrency for call in f.calls), expected)
                self.assertTrue(f.cancel.is_set())
                self.assertFalse(f.output.exists())
                for concurrency in expected:
                    self.assertEqual((f.root / "calibration" / ("c" + str(concurrency)) / "sentinel").read_bytes(),
                                     ("preserve-c" + str(concurrency)).encode("ascii"))

    def test_each_live_gate_failure_preserves_written_file_and_never_returns(self):
        for gate in range(1, 8):
            with self.subTest(gate=gate), self.fixture() as f:
                f.fail_recheck = gate
                with self.assertRaisesRegex(RuntimeError, "live drift"):
                    f.invoke()
                self.assertTrue(f.cancel.is_set())
                self.assertEqual(f.rechecks, gate)
                self.assertEqual(tuple(call[2].concurrency for call in f.calls), (1, 2, 4)[:min(gate - 1, 3)])
                self.assertEqual(f.output.exists(), gate >= 6)
                if gate >= 6:
                    self.assertEqual(h.evidence.encode_r0a_observations_v2(
                        h.evidence.decode_r0a_observations_v2(f.output.read_bytes())), f.output.read_bytes())

    def test_cancellation_set_by_each_live_callback_prevents_success(self):
        for gate in range(1, 8):
            with self.subTest(gate=gate), self.fixture() as f:
                def recheck():
                    f.recheck()
                    if f.rechecks == gate:
                        f.cancel.set()
                with self.assertRaisesRegex(ValueError, "CANCELLED"):
                    f.invoke(live_recheck=recheck)
                self.assertEqual(f.rechecks, gate)
                self.assertEqual(f.output.exists(), gate >= 6)

    def test_progress_forwards_all_original_immutable_facts_without_synthesis(self):
        with self.fixture() as f:
            received = []
            result = f.invoke(progress=lambda *args: received.append(args))
            self.assertEqual(len(received), 1152)
            self.assertEqual(received, f.emitted)
            expected = [(c.concurrency, operational.R0Component(component.component), fact)
                        for c in f.observations.concurrencies for component in c.components for fact in component.progress]
            self.assertEqual(received, expected)
            for supplied, forwarded in zip(expected, received):
                self.assertIs(supplied[1], forwarded[1])
                self.assertIs(supplied[2], forwarded[2])
            self.assertEqual(result.observations.concurrencies, f.observations.concurrencies)

    def test_progress_exception_stops_later_collection_and_sets_cancel(self):
        for failure_position in (1, 385, 1152):
            with self.subTest(failure_position=failure_position), self.fixture() as f:
                received = []
                def progress(*args):
                    received.append(args)
                    if len(received) == failure_position:
                        raise RuntimeError("observer failure")
                with self.assertRaisesRegex(RuntimeError, "observer failure"):
                    f.invoke(progress=progress)
                self.assertTrue(f.cancel.is_set())
                self.assertEqual(len(received), failure_position)
                self.assertEqual(len(f.calls), (failure_position - 1) // 384 + 1)
                self.assertFalse(f.output.exists())

    def test_collector_return_type_identity_and_canonical_paths_are_bound(self):
        for kind in ("type", "concurrency", "envelope", "run", "path"):
            with self.subTest(kind=kind), self.fixture() as f:
                value = f.observations.concurrencies[0]
                if kind == "type": value = object()
                elif kind == "concurrency": value = f.observations.concurrencies[1]
                elif kind == "envelope": value = replace(value, envelope=replace(value.envelope, max_physical_inputs=999))
                elif kind == "run": value = replace(value, run_id="R0-another")
                else:
                    component = value.components[0]
                    unit = component.units[0]
                    target = replace(unit.target, archive=replace(unit.target.archive,
                        relative_directory="calibration/c2/P/00/target"))
                    component = replace(component, units=(replace(unit, target=target),) + component.units[1:])
                    value = replace(value, components=(component,) + value.components[1:])
                f.returned[1] = value
                with self.assertRaises((ValueError, TypeError)):
                    f.invoke()
                self.assertEqual(len(f.calls), 1)
                self.assertTrue(f.cancel.is_set())
                self.assertFalse(f.output.exists())

    def test_exclusive_fsync_independent_read_and_exact_file_fact(self):
        with self.fixture() as f:
            original_read = Path.read_bytes
            reads = []
            def read(path):
                data = original_read(path)
                if path == f.output:
                    reads.append(data)
                return data
            with patch.object(Path, "read_bytes", new=read), patch.object(h.os, "fsync", wraps=os.fsync) as fsync:
                result = f.invoke()
            self.assertGreaterEqual(len(reads), 2)
            self.assertEqual(fsync.call_count, 1)
            data = original_read(f.output)
            self.assertEqual(data, h.evidence.encode_r0a_observations_v2(result.observations))
            self.assertEqual((result.relative_path, result.byte_length, result.sha256),
                             (f.output.name, len(data), h.sha256(data).hexdigest()))
            count = len(f.calls)
            with self.assertRaises((ValueError, OSError)):
                f.invoke()
            self.assertEqual(len(f.calls), count)
            self.assertEqual(original_read(f.output), data)
            with self.assertRaises(FileExistsError):
                h._exclusive_bytes(f.output, b"replacement")
            self.assertEqual(original_read(f.output), data)

    def test_corrupted_independent_disk_bytes_cannot_be_accepted(self):
        for kind in ("truncate", "append", "substitute", "duplicate", "spacing", "order"):
            with self.subTest(kind=kind), self.fixture() as f:
                write = h._exclusive_bytes
                damaged = []
                def corrupt_write(path, data):
                    result = write(path, data)
                    if kind == "truncate": changed = data[:-1]
                    elif kind == "append": changed = data + b"x"
                    elif kind == "substitute": changed = data.replace(b"ADMITTED", b"REJECTED", 1)
                    elif kind == "duplicate": changed = b'{"schema":"duplicate",' + data[1:]
                    elif kind == "spacing": changed = b" " + data
                    else:
                        node = dict(reversed(tuple(json.loads(data).items())))
                        changed = json.dumps(node, sort_keys=False, separators=(",", ":")).encode("ascii") + b"\n"
                    Path(path).write_bytes(changed)
                    damaged.append(changed)
                    return result
                with patch.object(h, "_exclusive_bytes", new=corrupt_write), self.assertRaises(ValueError):
                    f.invoke()
                self.assertTrue(f.cancel.is_set())
                self.assertEqual(f.output.read_bytes(), damaged[0])
                self.assertEqual(f.rechecks, 5)

    def test_each_expected_decoder_binding_mismatch_rejects_preserving_disk(self):
        names = ("expected_profile_sha256", "expected_provenance_sha256", "expected_source_head",
                 "expected_selection_receipt_sha256", "expected_plan", "expected_runtime")
        for name in names:
            with self.subTest(name=name), self.fixture() as f:
                decoder = h.evidence.decode_r0a_observations_v2
                def decode(data, **bindings):
                    if name == "expected_plan":
                        plan = bindings[name]
                        bindings[name] = replace(plan, boards=(replace(plan.boards[0], fingerprint="wrong"),) + plan.boards[1:])
                    elif name == "expected_runtime": bindings[name] = replace(bindings[name], architecture="wrong")
                    else: bindings[name] = "f" * (40 if name == "expected_source_head" else 64)
                    return decoder(data, **bindings)
                with patch.object(h.evidence, "decode_r0a_observations_v2", new=decode), self.assertRaises(ValueError):
                    f.invoke()
                self.assertTrue(f.output.is_file())
                self.assertTrue(f.cancel.is_set())
                self.assertEqual(f.rechecks, 5)

    def test_write_fsync_and_decode_failures_keep_artifacts_without_retry(self):
        for kind in ("encode", "short-write", "fsync", "decode", "final-carrier"):
            with self.subTest(kind=kind), self.fixture() as f, _EvidenceExitStack() as stack:
                failure = RuntimeError(kind + " failed")
                if kind == "encode": stack.enter_context(patch.object(h.evidence, "encode_r0a_observations_v2", side_effect=failure))
                elif kind == "short-write":
                    def partial(path, data):
                        with Path(path).open("xb") as stream:
                            stream.write(data[:20])
                        raise failure
                    stack.enter_context(patch.object(h, "_exclusive_bytes", new=partial))
                elif kind == "fsync": stack.enter_context(patch.object(h.os, "fsync", side_effect=failure))
                elif kind == "decode": stack.enter_context(patch.object(h.evidence, "decode_r0a_observations_v2", side_effect=failure))
                else: stack.enter_context(patch.object(h._R0AObservationsFileV2, "__post_init__", side_effect=failure))
                with self.assertRaises(RuntimeError) as raised:
                    f.invoke()
                self.assertIs(raised.exception, failure)
                self.assertTrue(f.cancel.is_set())
                self.assertEqual(f.output.exists(), kind != "encode")
                self.assertEqual(len(f.calls), 3)
                self.assertEqual(len(list(f.root.glob("calibration/c*/sentinel"))), 3)

    def test_private_result_is_owner_created_frozen_slotted_detached_nonserializable(self):
        import pickle
        with self.fixture() as f:
            result = f.invoke()
            self.assertIs(type(result), h._R0AObservationsFileV2)
            self.assertEqual(tuple(field.name for field in fields(result)),
                             ("observations", "relative_path", "byte_length", "sha256"))
            self.assertFalse(hasattr(result, "__dict__"))
            with self.assertRaises((TypeError, ValueError)):
                type(result)(result.observations, result.relative_path, result.byte_length, result.sha256)
            with self.assertRaises((TypeError, ValueError)):
                type(result)()
            with self.assertRaises(FrozenInstanceError):
                result.byte_length = 0
            with self.assertRaises(TypeError):
                pickle.dumps(result)
            with self.assertRaises((TypeError, ValueError)):
                h._fact_node(result)
            self.assertIsNot(result.observations.plan, f.observations.plan)
            self.assertIsNot(result.observations.plan.boards[0], f.observations.plan.boards[0])

    def test_outer_boundary_never_captures_launches_admits_or_uses_v1_evidence(self):
        import benchmark_board
        guards = ((h, ("capture_run_provenance_v2", "_recheck_provenance_v2", "_capture_qualified_codec_profile",
                       "_runtime_identity", "load_selection_receipt", "launch_r0a", "launch_r0b", "_materialize_r0a_work",
                       "write_r0a_evidence", "read_r0a_evidence", "_measure_r0a", "adapt_r0a_concurrency",
                       "_finish_run", "_validate_run_manifest", "_fresh_ignored_root", "_begin_run", "_fail_run")),
                  (physical, ("capture_profile", "capture_qualified_profile")),
                  (h.qualification, ("_git", "_blobs", "capture_sources_v2")),
                  (readiness, ("target_counts", "search_synthetic_corpus", "derive_r0b_sizing_plan",
                               "select_operating_candidate", "project_execution", "project_archive",
                               "project_memory", "derive_r0a_dual_maxima_v2")),
                  (benchmark_board, ("generate_board",)),
                  (h.analysis, ("_shared_bootstrap", "analyze_effectiveness")),
                  (h.store, ("write_completion_receipt",)))
        with self.fixture() as f, _EvidenceExitStack() as stack:
            for owner, names in guards:
                for name in names:
                    stack.enter_context(patch.object(owner, name, side_effect=AssertionError("forbidden owner: " + name)))
            result = f.invoke()
            self.assertEqual(result.relative_path, "r0a-observations-v2.json")
            self.assertEqual({path.name for path in f.root.iterdir()}, {"calibration", result.relative_path})

    def test_existing_v1_1u_and_synthetic_owners_do_not_activate_outer_assembly(self):
        for owner in (h.launch_r0a, h.launch_r0b, h.write_r0a_evidence, h.read_r0a_evidence,
                      h._measure_r0a, h.adapt_r0a_concurrency, h._finish_run, h._validate_run_manifest,
                      h._collect_r0a_component_v2, h._collect_r0a_concurrency_v2,
                      h._materialize_v2_plan, h._readback_v2_plan, h._postprocess_r0b_v2):
            with self.subTest(owner=owner.__name__):
                self.assertNotIn("_assemble_r0a_observations_v2", inspect.getsource(owner))
        source = inspect.getsource(h._assemble_r0a_observations_v2)
        self.assertNotIn("R0_RUN_V2", source)
        self.assertFalse(hasattr(h, "launch_r0a_v2"))
        self.assertFalse(hasattr(h, "validate_existing_run_v2"))
