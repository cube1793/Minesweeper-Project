"""Pure E2 I1 identities and frozen selection bytes (protocol sections 5/6/9/14/21).

No repository inspection, host capture, board generation or execution occurs here.
All seeds and protocol bytes are supplied by the caller. The exposure metadata is
the documented pre-freeze registry, not a claim of complete global index usage.
"""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
import hashlib


PROTOCOL_PATH = "docs/stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md"
PROTOCOL_SHA256 = "10b1055a6e1bcab8e03ab504755c9c9d655d5457800318396afb6e31497ba2fa"
PROTOCOL_BLOB_ID = "3351017f0f0116be00917be3ff95312120f43117"
PROTOCOL_BYTE_LENGTH = 57_841
FREEZE_COMMIT = "6d3eb456d72632d24e9cab14bdeea0cffd279092"
E1_CORE_BASELINE = "6106f730320c35e7123a75526f34dbeadeef3c5d"
PRIMARY_LABEL = b"PROGRAM_K_E2_PRIMARY_V1"
PRIMARY_LOW, PRIMARY_HIGH = 1_000_000_000, 1_001_000_000
CANDIDATE_MAX = 10_000
REHEARSAL_LABEL = b"PROGRAM_K_E2_REHEARSAL_V1"
REHEARSAL_LOW, REHEARSAL_HIGH = 1_001_000_000, 1_001_100_000
CORPUS_LABEL = b"PROGRAM_K_E2_CORPUS_V1"
KCONTROL_LABEL = b"PROGRAM_K_E2_KCONTROL_V1"
ORACLE_B_LABEL = b"PROGRAM_K_E2_ORACLEB_V1"
DETERMINISM_LABEL = b"PROGRAM_K_E2_DETERMINISM_V1"
BOOT_LABEL = b"PROGRAM_K_E2_BOOTSTRAP_V1"
ORDER_LABEL = b"PROGRAM_K_E2_ARM_ORDER_V1"
E2_PRIMARY_EXCLUSION_SET = frozenset()
E2_REHEARSAL_EXCLUSION_SET = frozenset()
N_LADDER = (1_000, 2_500, 5_000, 10_000)
KCONTROL_CAP, ORACLE_B_CAP, DETERMINISM_CAP = 256, 128, 256
PRACTICAL_MARGIN_US_PER_WW = 126_005
BOOTSTRAP_REPLICATES = 10_000
CONFIDENCE_LEVEL = Fraction(95, 100)
INTERVAL = "percentile"
LOWER_RANK, UPPER_RANK = 250, 9_750  # one-based nearest ranks, no interpolation
MAX_DECISION_WALL_MS, MAX_ARM_WALL_MS, SHADOW_TIMEOUT_MS = 30_000, 420_000, 1_000
R0_A_BOARD_COUNT = 64
R0_A_CONCURRENCY_CANDIDATES = (1, 2, 4)
EXECUTION_WALL_SAFETY_FACTOR = Fraction(2)
POSTPROCESS_WALL_SAFETY_FACTOR = Fraction(2)
ARCHIVE_BYTES_SAFETY_FACTOR = Fraction(3, 2)
MEMORY_SAFETY_FACTOR = Fraction(3, 2)
MAX_ACTUAL_E2_LAUNCHER_WALL_SECONDS = 43_200
MAX_COMBINED_MEMORY_BYTES = 4_294_967_296
MAX_ARCHIVE_BYTES = 17_179_869_184
FIXED_REPORT_RECEIPT_ALLOWANCE = 268_435_456
UINT64_MAX = (1 << 64) - 1


class IdentityError(ValueError):
    """An input cannot represent the registered exact identity/selection bytes."""


def strict_int(value, *, minimum=0, maximum=UINT64_MAX):
    if type(value) is not int or not minimum <= value <= maximum:
        raise IdentityError("Expected an exact integer in the declared bounds.")
    return value


def uint64_be(value):
    return strict_int(value).to_bytes(8, "big")


def uint64_be_decode(value):
    if type(value) is not bytes or len(value) != 8:
        raise IdentityError("Unsigned-64 decoding requires exactly eight bytes.")
    return int.from_bytes(value, "big")


def ascii_label(value):
    """Labels are nonempty printable ASCII bytes without whitespace or NUL."""
    if type(value) is not bytes or not value or any(not 33 <= b <= 126 for b in value):
        raise IdentityError("Expected a nonempty ASCII label without separators.")
    return value


def sha256_bytes(value):
    if type(value) is not bytes:
        raise IdentityError("Hash input must be exact bytes.")
    return hashlib.sha256(value).digest()


def _seed(value):
    if type(value) is not bytes or len(value) != 32:
        raise IdentityError("Seed/digest must be exactly 32 bytes.")
    return value


@dataclass(frozen=True, slots=True)
class ValidatedProtocolBytes:
    """Byte identity only; supplying a digest does not authenticate Git provenance."""

    sha256: str
    seed: bytes
    byte_length: int

    def __post_init__(self):
        _seed(self.seed)
        if type(self.sha256) is not str or self.sha256 != self.seed.hex():
            raise IdentityError("Protocol digest/seed mismatch.")
        strict_int(self.byte_length)


def validate_protocol_bytes(protocol_bytes, *, expected_sha256=PROTOCOL_SHA256):
    """Validate supplied committed bytes; override the digest only for synthetic use."""
    if (type(expected_sha256) is not str or len(expected_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_sha256)):
        raise IdentityError("Expected a lowercase SHA-256 hex digest.")
    digest = sha256_bytes(protocol_bytes)
    if digest.hex() != expected_sha256:
        raise IdentityError("Frozen protocol SHA-256 mismatch.")
    return ValidatedProtocolBytes(digest.hex(), digest, len(protocol_bytes))


def select_indices(label, seed, low, high, count, exclusions=frozenset(), *, start_counter=0):
    """Ordered rejection sampling, section 6.2; no wrapping counter or RNG state.

    A high endpoint of 2**64 denotes the exclusive end of the uint64 domain.
    Exclusions outside the domain are harmless but must still be exact uint64s.
    Counter exhaustion is an error, never a partial selection or wrapped stream.
    """
    ascii_label(label)
    _seed(seed)
    strict_int(low)
    strict_int(high, minimum=1, maximum=1 << 64)
    strict_int(count)
    strict_int(start_counter)
    if high <= low or type(exclusions) is not frozenset:
        raise IdentityError("Invalid domain or exclusion-set ownership.")
    for index in exclusions:
        strict_int(index)
    width = high - low
    available = width - sum(low <= index < high for index in exclusions)
    if count > available:
        raise IdentityError("Requested count exceeds admissible domain.")
    limit = ((1 << 64) // width) * width
    accepted, seen = [], set()
    counter = start_counter
    while len(accepted) < count:
        if counter > UINT64_MAX:
            raise IdentityError("Selection exhausted uint64 counters.")
        digest = sha256_bytes(label + b"\0" + seed + uint64_be(counter))
        counter += 1
        x = uint64_be_decode(digest[:8])
        if x >= limit:
            continue
        index = low + x % width
        if index in seen or index in exclusions:
            continue
        seen.add(index)
        accepted.append(index)
    return tuple(accepted)


def corpus_bytes(protocol_seed, n, indices):
    _seed(protocol_seed)
    strict_int(n)
    if type(indices) is not tuple or n != len(indices):
        raise IdentityError("Ordered corpus must be an exact tuple of length N.")
    encoded = tuple(uint64_be(index) for index in indices)
    if len(set(indices)) != n:
        raise IdentityError("Duplicate corpus index.")
    return CORPUS_LABEL + b"\0" + protocol_seed + uint64_be(n) + b"".join(encoded)


def corpus_digest(protocol_seed, n, indices):
    return sha256_bytes(corpus_bytes(protocol_seed, n, indices))


def select_subset_positions(label, protocol_seed, digest, n, count):
    ascii_label(label)
    _seed(protocol_seed)
    _seed(digest)
    strict_int(n, minimum=1)
    subset_seed = sha256_bytes(label + b"\0" + protocol_seed + b"\0" + digest)
    return select_indices(label, subset_seed, 0, n, count)


class ArmOrder(Enum):
    CONTROL_THEN_KP0 = "CONTROL_THEN_KP0"
    KP0_THEN_CONTROL = "KP0_THEN_CONTROL"


def arm_order(protocol_seed, game_index):
    _seed(protocol_seed)
    digest = sha256_bytes(ORDER_LABEL + b"\0" + protocol_seed + uint64_be(game_index))
    return (ArmOrder.CONTROL_THEN_KP0, ArmOrder.KP0_THEN_CONTROL)[digest[0] & 1]


class ExposureCategory(Enum):
    INDEXED_RANGE = "INDEXED_RANGE"
    EXPLICIT_INDICES = "EXPLICIT_INDICES"
    SYNTHETIC_NON_INDEX = "SYNTHETIC_NON_INDEX"
    UNOPENED_HOLDOUT = "UNOPENED_HOLDOUT"


@dataclass(frozen=True, slots=True)
class ExposureEntry:
    name: str
    category: ExposureCategory
    domain: tuple | None = None
    indices: frozenset = frozenset()
    note: str = ""

    def __post_init__(self):
        if (type(self.name) is not str or not self.name or type(self.note) is not str
                or type(self.category) is not ExposureCategory or type(self.indices) is not frozenset):
            raise IdentityError("Invalid exposure metadata.")
        for index in self.indices:
            strict_int(index)
        if self.category in (ExposureCategory.INDEXED_RANGE, ExposureCategory.UNOPENED_HOLDOUT):
            if type(self.domain) is not tuple or len(self.domain) != 2 or self.indices:
                raise IdentityError("Indexed range requires only a half-open domain.")
            low, high = self.domain
            strict_int(low)
            strict_int(high, minimum=1, maximum=1 << 64)
            if high <= low:
                raise IdentityError("Empty/reversed exposure range.")
        elif self.domain is not None:
            raise IdentityError("Synthetic/explicit-index entries cannot have a range.")
        elif self.category is ExposureCategory.SYNTHETIC_NON_INDEX and self.indices:
            raise IdentityError("Synthetic fixtures are not indexed Expert boards.")
        elif self.category is ExposureCategory.EXPLICIT_INDICES and not self.indices:
            raise IdentityError("Explicit index entry must be nonempty.")


DOCUMENTED_EXPOSURE_REGISTRY = (
    ExposureEntry("official Stage-2/Stage-3", ExposureCategory.INDEXED_RANGE, (0, 100_000)),
    ExposureEntry("B7 / B7-C", ExposureCategory.INDEXED_RANGE, (0, 1_000), note="within range"),
    ExposureEntry("E/L", ExposureCategory.INDEXED_RANGE, (100_000, 110_000)),
    ExposureEntry("Program-K E1", ExposureCategory.EXPLICIT_INDICES, indices=frozenset((0, 1, 2, 3, 100_000))),
    ExposureEntry("Program-K E0", ExposureCategory.SYNTHETIC_NON_INDEX, note="schematic fixtures / probes"),
    ExposureEntry("R3", ExposureCategory.SYNTHETIC_NON_INDEX, note="synthetic layouts"),
    ExposureEntry("F1", ExposureCategory.SYNTHETIC_NON_INDEX, note="fabricated commitments; no scheduled Expert corpus"),
    ExposureEntry("fixed exemplars", ExposureCategory.EXPLICIT_INDICES, indices=frozenset((1, 73_024, 73_758, 93_557))),
    ExposureEntry("ZiNi development", ExposureCategory.INDEXED_RANGE, (1_010_000, 1_010_050)),
    ExposureEntry("ZiNi final holdout", ExposureCategory.UNOPENED_HOLDOUT, (2_010_000, 2_010_100), note="EXCLUDED / UNOPENED"),
    ExposureEntry("ZiNi tuning/internal validation", ExposureCategory.INDEXED_RANGE, (3_010_000, 3_010_500)),
)
