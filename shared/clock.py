import time
from datetime import datetime, timezone, timedelta
from typing import Optional


class DemoClock:
    def __init__(self, speed: float = 1.0):
        self._speed: float = max(speed, 0.001)
        self._real_start: float = time.time()
        self._sim_start: datetime = datetime.now(timezone.utc)
        self._manual_offset_seconds: float = 0.0

    def set_speed(self, speed: float) -> None:
        current_sim_now = self.now()
        self._speed = max(speed, 0.001)
        self._real_start = time.time()
        self._sim_start = current_sim_now
        self._manual_offset_seconds = 0.0

    def get_speed(self) -> float:
        return self._speed

    def advance_seconds(self, seconds: float) -> None:
        self._manual_offset_seconds += seconds

    def advance_days(self, days: float) -> None:
        self.advance_seconds(days * 86400.0)

    def now(self) -> datetime:
        elapsed_real = time.time() - self._real_start
        virtual_elapsed = elapsed_real * self._speed + self._manual_offset_seconds
        return self._sim_start + timedelta(seconds=virtual_elapsed)

    def now_iso(self) -> str:
        return self.now().isoformat()

    def days_to_seconds(self, days: float) -> float:
        """Converts logical days to wait seconds respecting current DEMO_CLOCK_SPEED."""
        return (days * 86400.0) / self._speed

    def reset(self, speed: Optional[float] = None) -> None:
        if speed is not None:
            self._speed = max(speed, 0.001)
        self._real_start = time.time()
        self._sim_start = datetime.now(timezone.utc)
        self._manual_offset_seconds = 0.0


# Global singleton instance
_GLOBAL_CLOCK = DemoClock()


def get_clock() -> DemoClock:
    return _GLOBAL_CLOCK


def now() -> datetime:
    return _GLOBAL_CLOCK.now()


def now_iso() -> str:
    return _GLOBAL_CLOCK.now_iso()


def days_to_seconds(days: float) -> float:
    return _GLOBAL_CLOCK.days_to_seconds(days)
