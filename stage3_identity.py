"""Fixed Stage-3 V1 algorithm identity, separate from profile and run settings.

The digest identifies canonical LF specification content, not executable code.
Telemetry retains ownership of the existing public solver stage/policy strings.
"""

from dataclasses import dataclass

from telemetry_schema import SOLVER_POLICY_E_FIRST_FIRST_REVEAL_V1, SOLVER_STAGE_STAGE_3


@dataclass(frozen=True)
class Stage3AlgorithmIdentity:
    """The declared algorithm contract of the fixed V1 producer."""

    algorithm_spec_version: int
    algorithm_spec_sha256: str
    solver_stage: str
    solver_policy: str


STAGE3_V1_IDENTITY = Stage3AlgorithmIdentity(
    algorithm_spec_version=1,
    algorithm_spec_sha256="6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33",
    solver_stage=SOLVER_STAGE_STAGE_3,
    solver_policy=SOLVER_POLICY_E_FIRST_FIRST_REVEAL_V1,
)
