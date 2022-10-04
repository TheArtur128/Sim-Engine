from simengine.errors.tool_errors import UnableToDivideError


class GeometryError(Exception):
    pass


class VectorError(GeometryError):
    pass


class LineError(GeometryError):
    pass


class UnableToDivideVectorIntoPointsError(GeometryError, UnableToDivideError):
    pass


class FigureError(GeometryError):
    pass


class FigureIsNotCorrect(FigureError):
    pass


class FigureIsNotClosedError(FigureIsNotCorrect):
    pass
