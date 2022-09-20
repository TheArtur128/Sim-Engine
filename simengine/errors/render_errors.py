class RenderError(Exception):
    pass


class RenderResourceError(RenderError):
    pass


class UnsupportedResourceError(RenderResourceError):
    pass
    
