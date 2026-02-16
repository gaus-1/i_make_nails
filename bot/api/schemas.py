from __future__ import annotations

"""Pydantic-схемы запросов и ответов HTTP API мини-аппа."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field


class MeOut(BaseModel):
    """Текущий пользователь и роль для мини-аппа."""

    telegram_id: int
    role: str = Field(..., description="'admin' | 'master' | 'client'")
    is_owner: bool = Field(False, description="Показывать кнопку «Как клиент» в панели мастера.")


class SlotOut(BaseModel):
    """Single free slot for booking."""

    # Храним ISO-строку, как и раньше в API.
    start_utc_iso: str = Field(
        ...,
        description="Начало слота в UTC в формате ISO 8601.",
        examples=["2026-02-10T09:00:00+00:00"],
    )


class SlotsResponse(BaseModel):
    """Response with free slots for a given date and service."""

    date: str = Field(..., description="Дата, для которой рассчитаны слоты, в формате YYYY-MM-DD.")
    slots: list[SlotOut]
    slot_duration_minutes: int = Field(90, description="Длительность одного окна в минутах.")


class AppointmentOut(BaseModel):
    """Public representation of an appointment in mini-app."""

    id: int
    label: str = Field(..., description="Подпись записи (дата/время или «Запись»).")
    datetime_start_utc: datetime
    status: str
    source: str


class AppointmentCreateIn(BaseModel):
    """Payload for creating a new appointment from mini-app (v1)."""

    telegram_id: int = Field(..., description="Telegram ID клиента (временно, до initData).")
    name: str = Field(..., max_length=200, description="Имя клиента.")
    phone: str | None = Field(None, max_length=30, description="Телефон клиента.")
    slot_start_utc: datetime = Field(
        ...,
        description="Начало выбранного слота в UTC, ISO 8601.",
        examples=["2026-02-10T09:00:00+00:00"],
    )


class AppointmentRescheduleIn(BaseModel):
    """Payload for rescheduling an existing appointment."""

    slot_start_utc: datetime = Field(
        ...,
        description="Новое начало слота в UTC, ISO 8601.",
        examples=["2026-02-11T11:00:00+00:00"],
    )


class AppointmentsListResponse(BaseModel):
    """List of appointments for current client."""

    appointments: list[AppointmentOut]


class ClientOut(BaseModel):
    """Public representation of client for master panel."""

    id: int
    name: str
    phone: str | None
    telegram_id: int | None = None
    booking_allowed: bool
    future_appointments_count: int


class MasterAppointmentOut(BaseModel):
    """Appointment representation for master's daily schedule."""

    id: int
    client_name: str
    client_phone: str | None
    client_telegram_id: int | None = None
    service_name: str
    datetime_local: datetime
    status: str


class MasterAppointmentsResponse(BaseModel):
    """Daily schedule for master."""

    date: str
    appointments: list[MasterAppointmentOut]


class ClientsListResponse(BaseModel):
    """List of clients for master panel."""

    clients: list[ClientOut]


class ClientPatchIn(BaseModel):
    """Payload for updating client (e.g. blacklist)."""

    booking_allowed: bool | None = Field(None, description="Разрешить/запретить онлайн-запись.")


class WorkScheduleItemOut(BaseModel):
    """One work schedule line (day + time range)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    day_of_week: int  # 0=Monday ... 6=Sunday
    time_start: time
    time_end: time


class MasterSettingsOut(BaseModel):
    """Master settings for mini-app (booking on/off, work schedule). timezone только в ответе, не редактируется."""

    booking_enabled: bool
    timezone: str  # только для отображения/логики, настройка убрана
    slot_duration_minutes: int = 90
    work_schedule: list[WorkScheduleItemOut]


class WorkScheduleItemIn(BaseModel):
    """One work schedule line for PATCH."""

    day_of_week: int = Field(..., ge=0, le=6)
    time_start: time
    time_end: time


class MasterSettingsPatchIn(BaseModel):
    """Payload for updating master settings."""

    booking_enabled: bool | None = None
    work_schedule: list[WorkScheduleItemIn] | None = None


class BlockedSlotOut(BaseModel):
    """Один заблокированный период для мастера."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    date_start: date
    date_end: date
    reason: str | None


class BlockedSlotCreateIn(BaseModel):
    """Создание блокировки дат."""

    date_start: date = Field(..., description="Начало периода (включительно).")
    date_end: date | None = Field(
        None, description="Конец периода (включительно). Одна дата, если не указано."
    )
    reason: str | None = Field(None, max_length=500)
