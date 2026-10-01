"""Half-open interval indices — ports Java ``ScheduleWindows``.

0 is 00:00, 288 is next midnight in fixed UTC+10.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduleWindows:
    charge_start: int
    charge_end: int
    discharge_start: int
    discharge_end: int

    def __post_init__(self) -> None:
        if (
            self.charge_start < 0
            or self.charge_start >= self.charge_end
            or self.charge_end > self.discharge_start
            or self.discharge_start >= self.discharge_end
            or self.discharge_end > 288
        ):
            raise ValueError(
                "require ordered, nonempty, nonoverlapping windows within one day"
            )

    @classmethod
    def minutes(
        cls,
        charge_start: int,
        charge_end: int,
        discharge_start: int,
        discharge_end: int,
    ) -> "ScheduleWindows":
        for minute in (charge_start, charge_end, discharge_start, discharge_end):
            if minute < 0 or minute > 1440 or minute % 5 != 0:
                raise ValueError(
                    "window boundaries must be five-minute aligned within the day"
                )
        return cls(
            charge_start // 5, charge_end // 5, discharge_start // 5, discharge_end // 5
        )

    def can_charge(self, i: int) -> bool:
        return self.charge_start <= i < self.charge_end

    def can_discharge(self, i: int) -> bool:
        return self.discharge_start <= i < self.discharge_end
