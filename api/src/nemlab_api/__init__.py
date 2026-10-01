"""NEMLab HTTP API application (FastAPI).

Ports the Java ``api`` module: public price reads, protected operator refresh
endpoints and the public simulation lifecycle. Depends on ``nemlab_core`` and
``nemlab_infrastructure``; never on ``nemlab_worker``.
"""

__version__ = "0.1.0"
