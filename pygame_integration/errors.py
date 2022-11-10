class PygameRenderError(Exception):
    pass


class PygameRenderResourceError(PygameRenderError):
    pass


class PygameEventError(PygameRenderError):
    pass


class PygameEventHandlerError(PygameEventError):
    pass
