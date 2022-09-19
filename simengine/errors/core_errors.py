class SimulationError(Exception):
    pass


class UnitError(SimulationError):
    pass


class NotSupportPartError(UnitError):
    pass


class UnsupportedUnitForHandlerError(UnitError):
    pass


class ProcessError(SimulationError):
    pass


class ProcessAlreadyCompletedError(ProcessError):
    pass


class ProcessHasNotStartedError(ProcessError):
    pass


class ProcessStateError(SimulationError):
    pass


class ProcessStateIsNotValidError(ProcessStateError):
    pass


class ProcessIsNoLongerSleepingError(ProcessStateIsNotValidError):
    pass
