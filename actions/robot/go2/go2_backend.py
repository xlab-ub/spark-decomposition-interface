"""Unitree Go2 real-robot backend (unitree_sdk2py).

Selected with SPARK_ROBOT_BACKEND=go2. Not implemented yet: the factory below
raises so the actions server fails loudly instead of silently running noop.
"""


def create_go2_backend(connection_settings=None, audio=False):
    raise NotImplementedError(
        "SPARK_ROBOT_BACKEND=go2 (real Unitree Go2) is not implemented yet. "
        "Use go2_noop for a dry run."
    )


__all__ = ["create_go2_backend"]
