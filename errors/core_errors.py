class SimulationError(Exception):
    pass


class ProcessKeeperError(SimulationError):
    pass


class UnsupportedProcessError(ProcessKeeperError):
    pass


class InteractionError(SimulationError):
    pass


class UnmetDependencyError(SimulationError):
    pass


class WorldInhabitantsHandlerError(SimulationError):
    pass


class UnsupportedInhabitantForHandlerError(WorldInhabitantsHandlerError):
    pass


class UnitError(SimulationError):
    pass


class DiscreteError(SimulationError):
    pass


class NotSupportPartError(DiscreteError):
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


class WorldProcessError(ProcessError):
    pass


class AppFactoryError(SimulationError):
    pass


class InvalidWorldError(AppFactoryError):
    pass
