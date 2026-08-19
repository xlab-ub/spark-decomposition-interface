"""Unitree Go2 MuJoCo simulation backend.

Selected with SPARK_ROBOT_BACKEND=go2_sim. Not implemented yet: the factory
below raises so the actions server fails loudly instead of silently running noop.
"""


def create_go2_sim_backend(connection_settings=None, audio=False):
    raise NotImplementedError(
        "SPARK_ROBOT_BACKEND=go2_sim (Unitree Go2 MuJoCo) is not implemented yet. "
        "Use go2_noop for a dry run."
    )


__all__ = ["create_go2_sim_backend"]
