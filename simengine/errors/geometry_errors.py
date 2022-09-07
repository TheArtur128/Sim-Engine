class GeometricPrimitiveError(Exception):
    pass


class FigureIsIncorrectError(GeometricPrimitiveError):
    pass


class FigureIsNotConvexError(FigureIsIncorrectError):
    pass
