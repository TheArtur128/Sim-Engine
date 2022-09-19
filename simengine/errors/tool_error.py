class ToolError(Exception):
    pass


class DividerError(ToolError):
    pass


class UnableToDivideError(DividerError):
    pass


class RGBAColorError(ToolError):
    pass


class ColorCoordinateError(RGBAColorError):
    pass


class AlphaChannelError(RGBAColorError):
    pass
