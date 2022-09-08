class SimulationError(Exception):
    pass


class UnitError(SimulationError):
    pass


class NotSupportPartError(UnitError):
    pass


class UnsupportedUnitForHandlerError(UnitError):
    pass
