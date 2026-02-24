class RouteRequest:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class GraphUpdateRequest(RouteRequest):
    pass


class ReachabilityRequest(RouteRequest):
    pass
