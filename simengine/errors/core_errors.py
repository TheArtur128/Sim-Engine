class SimulationError(Exception):
    pass


class ActionError(SimulationError):
    pass


class ForcedReplacementOfActionError(ActionError):
    pass


class UnsupportedActionError(ActionError):
    pass


class UnitError(SimulationError):
    pass


class NotSupportPartError(UnitError):
    pass


class UnsupportedUnitForHandlerError(UnitError):
    pass
