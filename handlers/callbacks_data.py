from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import State, StatesGroup
from aiogram.types.input_file import InputFile as AbstractInputFile
from io import BytesIO

class MemoryInputFile(AbstractInputFile):
    def __init__(self, file: BytesIO, filename: str):
        self.file = file
        self.filename = filename

    def read(self, *args, **kwargs):
        # If the first argument is not int or None, ignore it
        if args and not isinstance(args[0], (int, type(None))):
            return self.file.read()
        return self.file.read(*args, **kwargs)

class CheckState(StatesGroup):
    waiting_for_input = State()
    check_data = State()

class PromptState(StatesGroup):  # This class is used to handle the state of the role input
    waiting_for_input = State()

class PromtImageState(StatesGroup):  # This class is used to handle the state of the generate image input
    waiting_for_input_promt = State()

class CheckImageState(StatesGroup):  # This class is used to handle the state of the image input
    waiting_for_image_input = State()

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

class ReportСB(CallbackData, prefix="report"):
    report_type: str
    start_date: str
    end_date: str