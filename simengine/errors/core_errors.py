class SimulationError(Exception):
    pass


class UnitError(SimulationError):
    pass


class UnitRelationError(UnitError):
    pass


class DiscreteUnitError(UnitError):
    pass


class NotSupportPartError(DiscreteUnitError):
    pass


class UnsupportedUnitForHandlerError(UnitError):
    pass


class ProcessError(SimulationError):
    pass


class ProcessAlreadyCompletedError(ProcessError):
    pass


class ProcessHasNotStartedError(ProcessError):
    pass


class ProcessStateError(ProcessError):
    pass


class ProcessStateIsNotValidError(ProcessStateError):
    pass


class ProcessIsNoLongerSleepingError(ProcessStateIsNotValidError):
    pass


class AppFactoryError(SimulationError):
    pass


class InvalidWorldError(AppFactoryError):
    pass
