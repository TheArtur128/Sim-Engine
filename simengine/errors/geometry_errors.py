from errors.tool_error import UnableToDivideError


class GeometryError(Exception):
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


class FigureCrossesItselfError(FigureIsNotCorrect):
    pass
