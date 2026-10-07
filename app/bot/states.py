from aiogram.fsm.state import State, StatesGroup


class UploadExcel(StatesGroup):
    waiting_for_file = State()
