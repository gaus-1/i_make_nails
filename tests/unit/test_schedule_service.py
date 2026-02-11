from datetime import date, time, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from bot.models import Appointment, Base, BlockedSlot, Client, Master, WorkSchedule
from bot.services.schedule_service import ScheduleService


def setup_in_memory_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.flush()

    # Monday schedule: 10:00-14:00
    ws = WorkSchedule(
        master_id=master.id,
        day_of_week=0,
        time_start=time(10, 0),
        time_end=time(14, 0),
    )
    db.add(ws)
    db.commit()

    return db


def test_get_free_slots_without_appointments() -> None:
    db = setup_in_memory_db()
    master = db.execute(select(Master).limit(1)).scalars().first()
    assert master

    svc = ScheduleService(db)
    target = date(2026, 2, 9)  # Monday
    result = svc.get_free_slots_for_date(
        master_id=master.id, target_date=target, duration_minutes=60
    )

    assert result.date == target
    # 10-11, 11-12, 12-13, 13-14
    assert len(result.slots_utc) == 4


def test_get_free_slots_excludes_existing_appointments() -> None:
    db = setup_in_memory_db()
    master = db.execute(select(Master).limit(1)).scalars().first()
    assert master

    client = Client(master_id=master.id, name="Test Client")
    db.add(client)
    db.flush()

    svc = ScheduleService(db)
    target = date(2026, 2, 9)  # Monday

    initial = svc.get_free_slots_for_date(
        master_id=master.id,
        target_date=target,
        duration_minutes=60,
    )
    assert len(initial.slots_utc) == 4
    busy_slot_start = initial.slots_utc[1]
    busy_slot_end = busy_slot_start + timedelta(hours=1)

    appt = Appointment(
        master_id=master.id,
        client_id=client.id,
        service_id=None,
        datetime_start=busy_slot_start,
        datetime_end=busy_slot_end,
        status="confirmed",
        source="test",
    )
    db.add(appt)
    db.commit()

    result = svc.get_free_slots_for_date(
        master_id=master.id, target_date=target, duration_minutes=60
    )

    # всего четыре слота, один занят -> остаётся три
    assert len(result.slots_utc) == 3
    assert busy_slot_start not in result.slots_utc


def test_get_free_slots_booking_disabled_returns_empty() -> None:
    db = setup_in_memory_db()
    master = db.execute(select(Master).limit(1)).scalars().first()
    assert master
    master.booking_enabled = False
    db.add(master)
    db.commit()

    svc = ScheduleService(db)
    target = date(2026, 2, 9)
    result = svc.get_free_slots_for_date(
        master_id=master.id, target_date=target, duration_minutes=60
    )
    assert result.date == target
    assert result.slots_utc == []


def test_get_free_slots_blocked_date_returns_empty() -> None:
    db = setup_in_memory_db()
    master = db.execute(select(Master).limit(1)).scalars().first()
    assert master

    blocked = BlockedSlot(
        master_id=master.id,
        date_start=date(2026, 2, 9),
        date_end=date(2026, 2, 9),
        reason="Выходной",
    )
    db.add(blocked)
    db.commit()

    svc = ScheduleService(db)
    result = svc.get_free_slots_for_date(
        master_id=master.id, target_date=date(2026, 2, 9), duration_minutes=60
    )
    assert result.slots_utc == []


def test_get_free_slots_no_work_schedule_returns_empty() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    master = Master(timezone="Europe/Moscow", booking_enabled=True)
    db.add(master)
    db.commit()
    # нет WorkSchedule — день выходной

    svc = ScheduleService(db)
    result = svc.get_free_slots_for_date(
        master_id=master.id, target_date=date(2026, 2, 9), duration_minutes=60
    )
    assert result.date == date(2026, 2, 9)
    assert result.slots_utc == []
