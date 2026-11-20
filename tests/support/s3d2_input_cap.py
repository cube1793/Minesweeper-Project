"""Input cap enforced at the Engine input boundary. Imports no project module.

D1's pilot observer compared the count AFTER an input had been applied, so a
481st input could reach the Engine before being refused. This proxy stands
between a runner and the Engine and refuses BEFORE delegating: at most ``cap``
inputs ever reach the wrapped Engine. A game that ends on the cap-th input is
never turned into an error, because no further step is attempted.

Only the channel the K runners use is forwarded: width, height, num_mines,
status, get_observation, step. Everything else raises AttributeError. Nothing
here selects, validates or authorises a game input.
"""

REASON = "INPUT_CAP_REACHED"


class InputCapReached(RuntimeError):
    """The next input was refused before it reached the Engine."""

    def __init__(self, record):
        self.record = record
        super().__init__(
            f"{REASON}: cap={record['cap']} engine_inputs_reached={record['engine_inputs_reached']}")


def _move(index, x, y, action):
    return {"index": index, "action": getattr(action, "name", str(action)), "x": x, "y": y}


class CappedEngine:
    """Forward at most ``cap`` step calls; count them where they are forwarded."""

    __slots__ = ("__engine", "__cap", "__reached", "__last_allowed", "__refused", "__refusals")

    def __init__(self, engine, cap):
        if type(cap) is not int or cap < 1:
            raise ValueError("Input cap must be a positive integer.")
        self.__engine = engine
        self.__cap = cap
        self.__reached = 0
        self.__last_allowed = None
        self.__refused = None
        self.__refusals = 0

    @property
    def width(self):
        return self.__engine.width

    @property
    def height(self):
        return self.__engine.height

    @property
    def num_mines(self):
        return self.__engine.num_mines

    @property
    def status(self):
        return self.__engine.status

    def get_observation(self):
        return self.__engine.get_observation()

    def step(self, x, y, action):
        if self.__reached >= self.__cap:
            # Refuse here. The Engine is not called for this attempt.
            self.__refusals += 1
            if self.__refused is None:
                self.__refused = _move(self.__reached, x, y, action)
            raise InputCapReached(self.cap_record())
        # Counted at the moment of delegation: an Engine error still means the
        # input reached the Engine boundary.
        self.__last_allowed = _move(self.__reached, x, y, action)
        self.__reached += 1
        return self.__engine.step(x, y, action)

    @property
    def cap(self):
        return self.__cap

    @property
    def engine_inputs_reached(self):
        return self.__reached

    def cap_record(self):
        """Detached record: last allowed input, first refused input and the reason."""
        return {
            "cap": self.__cap,
            "engine_inputs_reached": self.__reached,
            "last_allowed_input": None if self.__last_allowed is None else dict(self.__last_allowed),
            "refused_input": None if self.__refused is None else dict(self.__refused),
            "refusals": self.__refusals,
            "cap_reached": self.__refused is not None,
            "reason": REASON if self.__refused is not None else None,
        }
