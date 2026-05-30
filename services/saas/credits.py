from __future__ import annotations

import sqlite3
from uuid import uuid4


class InsufficientCredits(ValueError):
    pass


class CreditLedger:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def grant(
        self,
        *,
        user_id: str,
        minutes: float,
        reason: str,
        idempotency_key: str,
        created_at: str,
        created_by_user_id: str | None = None,
    ) -> float:
        return self._add_balance_and_ledger(
            user_id=user_id,
            job_id=None,
            ledger_type="grant",
            minutes=minutes,
            reason=reason,
            idempotency_key=idempotency_key,
            created_at=created_at,
            created_by_user_id=created_by_user_id,
        )

    def adjustment(
        self,
        *,
        user_id: str,
        minutes: float,
        reason: str,
        idempotency_key: str,
        created_at: str,
        created_by_user_id: str,
    ) -> float:
        return self._add_balance_and_ledger(
            user_id=user_id,
            job_id=None,
            ledger_type="adjustment",
            minutes=minutes,
            reason=reason,
            idempotency_key=idempotency_key,
            created_at=created_at,
            created_by_user_id=created_by_user_id,
        )

    def reserve(
        self,
        *,
        user_id: str,
        job_id: str,
        minutes: float,
        idempotency_key: str,
        created_at: str,
        reason: str = "job reserve",
    ) -> float:
        self._validate_minutes(minutes)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if self._is_idempotent_replay(
                idempotency_key=idempotency_key,
                user_id=user_id,
                job_id=job_id,
                ledger_type="reserve",
                minutes=minutes,
            ):
                balance = self._balance(user_id)
                self.conn.commit()
                return balance
            balance = self._balance(user_id)
            if balance < minutes:
                raise InsufficientCredits(
                    f"insufficient credits: balance={balance}, required={minutes}"
                )
            next_balance = balance - minutes
            self._set_balance(user_id, next_balance, created_at)
            self._insert_ledger(
                user_id=user_id,
                job_id=job_id,
                ledger_type="reserve",
                minutes=minutes,
                reason=reason,
                idempotency_key=idempotency_key,
                created_at=created_at,
                created_by_user_id=None,
            )
            self.conn.execute(
                "UPDATE jobs SET reserved_minutes = reserved_minutes + ? WHERE id = ?",
                (minutes, job_id),
            )
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return next_balance

    def consume(
        self,
        *,
        user_id: str,
        job_id: str,
        minutes: float,
        idempotency_key: str,
        created_at: str,
        reason: str = "job consume",
    ) -> float:
        self._validate_minutes(minutes)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if self._is_idempotent_replay(
                idempotency_key=idempotency_key,
                user_id=user_id,
                job_id=job_id,
                ledger_type="consume",
                minutes=minutes,
            ):
                balance = self._balance(user_id)
                self.conn.commit()
                return balance
            balance = self._balance(user_id)
            self._insert_ledger(
                user_id=user_id,
                job_id=job_id,
                ledger_type="consume",
                minutes=minutes,
                reason=reason,
                idempotency_key=idempotency_key,
                created_at=created_at,
                created_by_user_id=None,
            )
            self.conn.execute(
                "UPDATE jobs SET consumed_minutes = consumed_minutes + ? WHERE id = ?",
                (minutes, job_id),
            )
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return balance

    def refund(
        self,
        *,
        user_id: str,
        job_id: str,
        minutes: float,
        idempotency_key: str,
        created_at: str,
        reason: str = "job refund",
    ) -> float:
        return self._add_balance_and_ledger(
            user_id=user_id,
            job_id=job_id,
            ledger_type="refund",
            minutes=minutes,
            reason=reason,
            idempotency_key=idempotency_key,
            created_at=created_at,
            created_by_user_id=None,
        )

    def _add_balance_and_ledger(
        self,
        *,
        user_id: str,
        job_id: str | None,
        ledger_type: str,
        minutes: float,
        reason: str,
        idempotency_key: str,
        created_at: str,
        created_by_user_id: str | None,
    ) -> float:
        self._validate_minutes(minutes)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if self._is_idempotent_replay(
                idempotency_key=idempotency_key,
                user_id=user_id,
                job_id=job_id,
                ledger_type=ledger_type,
                minutes=minutes,
            ):
                balance = self._balance(user_id)
                self.conn.commit()
                return balance
            next_balance = self._balance(user_id) + minutes
            self._set_balance(user_id, next_balance, created_at)
            self._insert_ledger(
                user_id=user_id,
                job_id=job_id,
                ledger_type=ledger_type,
                minutes=minutes,
                reason=reason,
                idempotency_key=idempotency_key,
                created_at=created_at,
                created_by_user_id=created_by_user_id,
            )
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return next_balance

    def _balance(self, user_id: str) -> float:
        row = self.conn.execute(
            "SELECT balance_minutes FROM credit_balances WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return float(row["balance_minutes"]) if row else 0.0

    def _is_idempotent_replay(
        self,
        *,
        idempotency_key: str,
        user_id: str,
        job_id: str | None,
        ledger_type: str,
        minutes: float,
    ) -> bool:
        row = self.conn.execute(
            "SELECT * FROM credit_ledger WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return False
        if (
            row["user_id"] != user_id
            or row["job_id"] != job_id
            or row["type"] != ledger_type
            or float(row["minutes"]) != float(minutes)
        ):
            raise ValueError("idempotency key reused with different ledger parameters")
        return True

    def _set_balance(self, user_id: str, minutes: float, updated_at: str) -> None:
        self.conn.execute(
            """
            INSERT INTO credit_balances (user_id, balance_minutes, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
              balance_minutes = excluded.balance_minutes,
              updated_at = excluded.updated_at
            """,
            (user_id, minutes, updated_at),
        )

    def _insert_ledger(
        self,
        *,
        user_id: str,
        job_id: str | None,
        ledger_type: str,
        minutes: float,
        reason: str,
        idempotency_key: str,
        created_at: str,
        created_by_user_id: str | None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO credit_ledger (
              id, user_id, job_id, type, minutes, reason,
              idempotency_key, created_by_user_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"ledger_{uuid4().hex}",
                user_id,
                job_id,
                ledger_type,
                minutes,
                reason,
                idempotency_key,
                created_by_user_id,
                created_at,
            ),
        )

    @staticmethod
    def _validate_minutes(minutes: float) -> None:
        if minutes <= 0:
            raise ValueError("minutes must be positive")
