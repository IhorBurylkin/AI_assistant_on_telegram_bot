from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import State, StatesGroup

class CheckState(StatesGroup):
    waiting_for_input = State()
    check_data = State()

class PromptState(StatesGroup):
    waiting_for_input = State()

class DateCB(CallbackData, prefix="dcb"):
    action: str
    year:   int
    month:  int
    day:    int

class PeriodCB(CallbackData, prefix="period"):
    mode: str            # preset / custom / cancel
    value: str | None    # today, 7d … | start | end | confirm

class CustomPeriod(StatesGroup):
    waiting_for_start = State()
    waiting_for_end   = State()
