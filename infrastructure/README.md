# Infrastructure module

This module will contain persistence, Open Electricity integration and durable job adapters.
It may depend on core; core must never depend on infrastructure. There are no adapters or
Spring beans yet. Applications will register adapters explicitly when they are implemented.
Database configuration and migrations belong to the next data-foundation tasks.
