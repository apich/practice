# -*- coding: utf-8 -*-
"""Channel storage support for AsyncSQLAlchemyStorage.

AgentScope's AsyncSQLAlchemyStorage does not implement the channel
persistence methods (upsert_channel, get_channel, list_channels,
list_all_channels, delete_channel, get_channel_id_by_platform_bot_id).
When channels (Discord, Feishu, …) are registered in create_app, the
channel dispatcher calls list_all_channels() on startup and hits
NotImplementedError.

This module patches AsyncSQLAlchemyStorage in-place with:
- A ChannelRow SQLAlchemy table (attached to agentscope's _Base so
  create_all provisions it automatically).
- Concrete implementations of every channel persistence method.

The table layout follows the same _JsonRecordMixin pattern used by
other rows: envelope fields (id, created_at, updated_at) + promoted
index columns (user_id, channel_type, platform_bot_id) + a JSON
payload carrying the rest of the ChannelRecord.
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, delete, select
from sqlalchemy.orm import Mapped, mapped_column

from agentscope.app.storage._model import ChannelRecord
from agentscope.app.storage._sql._tables import _Base

_ID_LEN = 255


# ------------------------------------------------------------------
# Channel table — registered on agentscope's _Base metadata so it is
# created by the same create_all call that provisions the other
# agentscope tables.
# ------------------------------------------------------------------


class ChannelRow(_Base):
    """One row per :class:`ChannelRecord`.

    Promotes ``user_id``, ``channel_type`` and ``platform_bot_id`` to
    dedicated columns for indexed queries; the remainder of the record
    lives in the ``payload`` JSON column.
    """

    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(_ID_LEN), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(_ID_LEN),
        nullable=False,
    )
    channel_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    platform_bot_id: Mapped[str] = mapped_column(
        String(_ID_LEN),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("ix_channels_user_id", "user_id"),
        Index("ix_channels_platform_bot_id", "platform_bot_id"),
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _utcnow() -> datetime:
    """Current naive UTC timestamp."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_naive_utc(dt: datetime | str) -> datetime:
    """Normalise *dt* to a naive UTC datetime."""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _record_to_row_values(record: ChannelRecord, platform_bot_id: str) -> dict:
    """Project a ChannelRecord onto ChannelRow column values.

    The promoted columns (id, created_at, updated_at, user_id,
    channel_type, platform_bot_id, enabled) are extracted; the
    remaining fields go into ``payload``.
    """
    dump = record.model_dump(mode="json")
    promoted = {
        "id": dump.pop("id"),
        "created_at": _to_naive_utc(dump.pop("created_at")),
        "updated_at": _to_naive_utc(dump.pop("updated_at")),
        "user_id": dump.pop("user_id"),
        "channel_type": dump.pop("channel_type"),
        "enabled": dump.pop("enabled", True),
    }
    return {
        **promoted,
        "platform_bot_id": platform_bot_id,
        "payload": dump,
    }


def _row_to_record(row: ChannelRow) -> ChannelRecord:
    """Reconstruct a ChannelRecord from a ChannelRow."""
    obj: dict = dict(row.payload or {})
    obj["id"] = row.id
    obj["created_at"] = row.created_at.isoformat() if isinstance(row.created_at, datetime) else row.created_at
    obj["updated_at"] = row.updated_at.isoformat() if isinstance(row.updated_at, datetime) else row.updated_at
    obj["user_id"] = row.user_id
    obj["channel_type"] = row.channel_type
    obj["enabled"] = row.enabled
    return ChannelRecord.model_validate(obj)


# ------------------------------------------------------------------
# Method implementations — these are bound to AsyncSQLAlchemyStorage
# via _patch_storage below.
# ------------------------------------------------------------------


async def _upsert_channel(
    self: Any,
    record: ChannelRecord,
    platform_bot_id: str,
) -> str:
    """Create or update a channel record."""
    values = _record_to_row_values(record, platform_bot_id)
    update_cols = (
        "updated_at",
        "user_id",
        "channel_type",
        "platform_bot_id",
        "enabled",
        "payload",
    )
    async with self._session() as sess:
        await sess.execute(
            self._upsert_stmt(ChannelRow, values, ["id"], update_cols),
        )
        await sess.commit()
    return record.id


async def _get_channel(
    self: Any,
    channel_id: str,
) -> ChannelRecord | None:
    """Fetch a channel by its global id."""
    async with self._session() as sess:
        row = await sess.get(ChannelRow, channel_id)
    if row is None:
        return None
    return _row_to_record(row)


async def _list_channels(
    self: Any,
    user_id: str,
) -> list[ChannelRecord]:
    """Return all channels for *user_id*."""
    async with self._session() as sess:
        rows = (
            (
                await sess.execute(
                    select(ChannelRow).where(ChannelRow.user_id == user_id),
                )
            )
            .scalars()
            .all()
        )
    return [_row_to_record(r) for r in rows]


async def _list_all_channels(self: Any) -> list[ChannelRecord]:
    """Return every channel record across all users."""
    async with self._session() as sess:
        rows = (await sess.execute(select(ChannelRow))).scalars().all()
    return [_row_to_record(r) for r in rows]


async def _delete_channel(
    self: Any,
    channel_id: str,
    platform_bot_id: str,
) -> bool:
    """Delete a channel record."""
    _ = platform_bot_id  # dedup index entry is removed with the row
    async with self._session() as sess:
        result = await sess.execute(
            delete(ChannelRow).where(ChannelRow.id == channel_id),
        )
        await sess.commit()
    return result.rowcount > 0


async def _get_channel_id_by_platform_bot_id(
    self: Any,
    platform_bot_id: str,
) -> str | None:
    """Return the channel id bound to *platform_bot_id*, if any."""
    async with self._session() as sess:
        row = (
            await sess.execute(
                select(ChannelRow.id).where(
                    ChannelRow.platform_bot_id == platform_bot_id,
                ),
            )
        ).scalar_one_or_none()
    return row


# ------------------------------------------------------------------
# Patch entry point
# ------------------------------------------------------------------

_patched = False


def patch_storage_with_channel_support() -> None:
    """Monkey-patch AsyncSQLAlchemyStorage with channel methods.

    Idempotent — safe to call multiple times.  Must be called before
    the storage is used (ideally at import time in main.py).
    """
    global _patched
    if _patched:
        return

    from agentscope.app.storage._sql._storage import AsyncSQLAlchemyStorage

    AsyncSQLAlchemyStorage.upsert_channel = _upsert_channel
    AsyncSQLAlchemyStorage.get_channel = _get_channel
    AsyncSQLAlchemyStorage.list_channels = _list_channels
    AsyncSQLAlchemyStorage.list_all_channels = _list_all_channels
    AsyncSQLAlchemyStorage.delete_channel = _delete_channel
    AsyncSQLAlchemyStorage.get_channel_id_by_platform_bot_id = (
        _get_channel_id_by_platform_bot_id
    )

    _patched = True
