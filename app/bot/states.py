"""FSM states for the Excel upload workflow."""

from aiogram.fsm.state import State, StatesGroup


class UploadExcel(StatesGroup):
    """States covering file upload and price collection."""

    waiting_for_file = State()
    processing = State()
