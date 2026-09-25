"""Generic inference categories, independent of any solver's decision types."""

from enum import Enum


class InferenceCategory(Enum):
    LOCAL_DETERMINISTIC = "local_deterministic"
    GLOBAL_CERTAINTY = "global_certainty"
    PROBABILITY_GUESS = "probability_guess"
