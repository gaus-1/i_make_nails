from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bot.models import Appointment, Base, Client, Master
from bot.services.appointment_service import AppointmentService
from bot.services.exceptions import SlotBusyError


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
    master = db.query(Master).first()
    client = db.query(Client).first()
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
    all_appointments = db.query(Appointment).all()
    assert len(all_appointments) == 2
