class GeometryError(Exception):
    pass


class LineError(GeometryError):
    pass


class UnableToDivideVectorIntoPointsError(LineError):
    pass
