class SlotBusyError(Exception):
    """Слот уже занят другой записью."""


class AppointmentNotFoundError(Exception):
    """Запись с указанным id не найдена."""
