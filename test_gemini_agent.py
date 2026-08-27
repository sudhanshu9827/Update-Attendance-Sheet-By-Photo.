from gemini_agent import process_attendance_image


with open(
    "attendance.jpeg",
    "rb"
) as f:

    image_bytes = f.read()


attendance = process_attendance_image(
    image_bytes,
    "attendance.jpeg"
)


print("\n========== RESULT ==========\n")

for record in attendance.records:

    status = (
        "PRESENT"
        if record.marked
        else "ABSENT"
    )

    print(
        f"{record.roll_no} | "
        f"{record.date} | "
        f"{status}"
    )