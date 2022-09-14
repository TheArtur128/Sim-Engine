class ToolError(Exception):
    pass


class DividerError(ToolError):
    pass


class UnableToDivideError(DividerError):
    pass
