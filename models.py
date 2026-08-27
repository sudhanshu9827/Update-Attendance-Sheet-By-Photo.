from pydantic import BaseModel


class AttendanceRecord(BaseModel):
    roll_no: str
    date: str
    marked: bool


class AttendanceSheet(BaseModel):
    records: list[AttendanceRecord]