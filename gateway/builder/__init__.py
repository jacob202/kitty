"""Builder package.

Two distinct systems live here and are easy to confuse:

- The autonomous build pipeline (spec -> scaffold -> implement -> test ->
  review), whose public API is defined in :mod:`gateway.builder.api` and
  re-exported below. This is what the ``/build`` routes call.
- KittyBuilder's packet/initiative machinery (queue, attempt, runner, loop,
  ...), reached as submodules: ``from gateway.builder import queue as bq``.

Only the pipeline API is re-exported here. Everything else stays an explicit
submodule import so there is exactly one way to reach each name.

``status`` is the pipeline function. The read-only projection over Builder
state that used to be ``gateway.builder_status`` is :mod:`gateway.builder.
projection` — renamed because a ``status`` submodule and a ``status()``
export cannot share the attribute.
"""

from gateway.builder.api import (
    approve_stage,
    get_artifact,
    init_db,
    list_builds,
    start,
    status,
)

__all__ = [
    "approve_stage",
    "get_artifact",
    "init_db",
    "list_builds",
    "start",
    "status",
]
