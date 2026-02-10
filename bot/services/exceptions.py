class SlotBusyError(Exception):
    """Raised when trying to create or move an appointment into an occupied time slot."""


class AppointmentNotFoundError(Exception):
    """Raised when an appointment with the given id does not exist."""

