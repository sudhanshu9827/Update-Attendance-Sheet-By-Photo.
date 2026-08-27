from models import AttendanceSheet


EXPECTED_DATES = {
    "17/08/26",
    "19/08/26",
    "21/08/26"
}


def validate_attendance(attendance: AttendanceSheet):

    errors = []

    # 1. Check number of records
    expected_records = 36 * 3
    actual_records = len(attendance.records)

    if actual_records != expected_records:
        errors.append(
            f"Expected {expected_records} records, "
            f"but received {actual_records}"
        )

    # 2. Check duplicate records
    seen = set()

    for record in attendance.records:

        key = (record.roll_no, record.date)

        if key in seen:
            errors.append(
                f"Duplicate record: {key}"
            )

        seen.add(key)

    # 3. Check dates
    for record in attendance.records:

        if record.date not in EXPECTED_DATES:
            errors.append(
                f"Unknown date: {record.date}"
            )

    return errors