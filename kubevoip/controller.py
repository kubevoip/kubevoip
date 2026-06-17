"""Shared controller exceptions."""


class InvalidSpecError(Exception):
    pass


class DependencyError(Exception):
    pass


class WaitingForLoadBalancerError(DependencyError):
    pass
