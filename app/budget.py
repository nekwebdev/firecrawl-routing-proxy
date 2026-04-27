from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class TavilyBudgetGuard:
    def __init__(
        self,
        db_path: str,
        daily_soft_cap_calls: int,
        monthly_cap_calls: int,
        reserve_percent_critical: int,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.daily_soft_cap_calls = daily_soft_cap_calls
        self.monthly_cap_calls = monthly_cap_calls
        self.reserve_percent_critical = reserve_percent_critical
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tavily_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_critical INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def _daily_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM tavily_calls WHERE date(created_at) = date('now')"
            ).fetchone()
            return int(row["c"])

    def _monthly_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM tavily_calls
                WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
                """
            ).fetchone()
            return int(row["c"])

    def can_use(self, is_critical: bool) -> tuple[bool, str]:
        monthly = self._monthly_count()
        if monthly >= self.monthly_cap_calls:
            return False, "monthly_cap_reached"

        daily = self._daily_count()
        reserve_calls = int(
            round(self.daily_soft_cap_calls * (self.reserve_percent_critical / 100))
        )
        reserve_calls = max(1, reserve_calls) if self.daily_soft_cap_calls > 0 else 0

        if is_critical:
            if daily >= self.daily_soft_cap_calls:
                return False, "daily_soft_cap_reached"
            return True, "ok"

        non_critical_limit = max(0, self.daily_soft_cap_calls - reserve_calls)
        if daily >= non_critical_limit:
            return False, "reserved_for_critical"
        return True, "ok"

    def record_call(self, is_critical: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tavily_calls (is_critical) VALUES (?)",
                (1 if is_critical else 0,),
            )

    def state_snapshot(self) -> dict[str, Any]:
        daily = self._daily_count()
        monthly = self._monthly_count()
        reserve_calls = int(
            round(self.daily_soft_cap_calls * (self.reserve_percent_critical / 100))
        )
        reserve_calls = max(1, reserve_calls) if self.daily_soft_cap_calls > 0 else 0
        return {
            "daily_used": daily,
            "daily_soft_cap": self.daily_soft_cap_calls,
            "monthly_used": monthly,
            "monthly_cap": self.monthly_cap_calls,
            "critical_reserve_calls": reserve_calls,
        }
