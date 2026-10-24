"""Bounded R0 harness fixtures. No actual R0 or production bootstrap workload."""

from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
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
