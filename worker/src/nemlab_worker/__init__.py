"""NEMLab non-HTTP worker application.

Ports the Java ``worker`` module: refresh-queue polling, fixed daily price
schedules and bounded simulation child processes. Depends on ``nemlab_core``
and ``nemlab_infrastructure``; never on ``nemlab_api``.
"""

__version__ = "0.1.0"
