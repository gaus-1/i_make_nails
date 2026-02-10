from datetime import date, time, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bot.models import Appointment, Base, Master, WorkSchedule
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
    master = db.query(Master).first()
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
    master = db.query(Master).first()
    assert master

    svc = ScheduleService(db)
    target = date(2026, 2, 9)  # Monday

    # сначала получаем свободные слоты, чтобы понимать реальные времена
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
        client_id=0,
        service_id=0,
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
