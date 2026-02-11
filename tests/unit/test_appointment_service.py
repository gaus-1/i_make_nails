from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from bot.models import Appointment, Base, Client, Master
from bot.services.appointment_service import AppointmentService
from bot.services.exceptions import AppointmentNotFoundError, SlotBusyError


def setup_in_memory_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    master = Master(
        timezone="Europe/Moscow",
        booking_enabled=True,
        slot_duration_minutes=60,
    )
    db.add(master)
    db.flush()

    client = Client(master_id=master.id, name="Test Client")
    db.add(client)
    db.commit()

    return db


def test_create_appointment_and_prevent_overlap() -> None:
    db = setup_in_memory_db()
    master = db.execute(select(Master).limit(1)).scalars().first()
    client = db.execute(select(Client).limit(1)).scalars().first()
    assert master and client

    master_id = master.id
    client_id = client.id

    svc = AppointmentService(db)
    start1 = datetime(2026, 2, 10, 9, 0, tzinfo=UTC)
    appt1 = svc.create(
        master_id=master_id,
        client_id=client_id,
        datetime_start_utc=start1,
    )

    assert appt1.id is not None
    assert appt1.datetime_end - appt1.datetime_start == timedelta(minutes=60)

    # overlapping appointment must fail
    start_overlap = datetime(2026, 2, 10, 9, 30, tzinfo=UTC)
    try:
        svc.create(
            master_id=master_id,
            client_id=client_id,
            datetime_start_utc=start_overlap,
        )
    except SlotBusyError:
        pass
    else:
        raise AssertionError("Expected SlotBusyError for overlapping appointment")

    # adjacent appointment must succeed
    start2 = datetime(2026, 2, 10, 10, 0, tzinfo=UTC)
    appt2 = svc.create(
        master_id=master_id,
        client_id=client_id,
        datetime_start_utc=start2,
    )
    assert appt2.id != appt1.id

    # ensure we really have two appointments in db
    all_appointments = db.execute(select(Appointment)).scalars().all()
    assert len(all_appointments) == 2


def test_reschedule_success() -> None:
    db = setup_in_memory_db()
    master = db.execute(select(Master).limit(1)).scalars().first()
    client = db.execute(select(Client).limit(1)).scalars().first()
    assert master and client

    svc = AppointmentService(db)
    start1 = datetime(2026, 2, 10, 9, 0, tzinfo=UTC)
    appt = svc.create(
        master_id=master.id,
        client_id=client.id,
        datetime_start_utc=start1,
    )
    new_start = datetime(2026, 2, 10, 11, 0, tzinfo=UTC)
    rescheduled = svc.reschedule(
        appointment_id=appt.id,
        new_datetime_start_utc=new_start,
    )
    assert rescheduled.id == appt.id
    start_utc = (
        rescheduled.datetime_start.replace(tzinfo=UTC)
        if rescheduled.datetime_start.tzinfo is None
        else rescheduled.datetime_start
    )
    assert start_utc == new_start
    end_utc = (
        rescheduled.datetime_end.replace(tzinfo=UTC)
        if rescheduled.datetime_end.tzinfo is None
        else rescheduled.datetime_end
    )
    assert end_utc == new_start + timedelta(minutes=60)


def test_reschedule_slot_busy_raises() -> None:
    db = setup_in_memory_db()
    master = db.execute(select(Master).limit(1)).scalars().first()
    client = db.execute(select(Client).limit(1)).scalars().first()
    assert master and client

    svc = AppointmentService(db)
    start1 = datetime(2026, 2, 10, 9, 0, tzinfo=UTC)
    appt1 = svc.create(
        master_id=master.id,
        client_id=client.id,
        datetime_start_utc=start1,
    )
    start2 = datetime(2026, 2, 10, 10, 0, tzinfo=UTC)
    svc.create(master_id=master.id, client_id=client.id, datetime_start_utc=start2)

    try:
        svc.reschedule(
            appointment_id=appt1.id,
            new_datetime_start_utc=start2,
        )
    except SlotBusyError:
        pass
    else:
        raise AssertionError("Expected SlotBusyError when rescheduling into occupied slot")


def test_reschedule_not_found_raises() -> None:
    db = setup_in_memory_db()
    svc = AppointmentService(db)
    new_start = datetime(2026, 2, 10, 11, 0, tzinfo=UTC)
    try:
        svc.reschedule(appointment_id=99999, new_datetime_start_utc=new_start)
    except AppointmentNotFoundError as e:
        assert "99999" in str(e)
    else:
        raise AssertionError("Expected AppointmentNotFoundError for missing appointment")
