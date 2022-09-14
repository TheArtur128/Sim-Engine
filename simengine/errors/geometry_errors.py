from errors.tool_error import UnableToDivideError


class GeometryError(Exception):
    pass


class LineError(GeometryError):
    pass


class UnableToDivideVectorIntoPointsError(GeometryError, UnableToDivideError):
    pass
