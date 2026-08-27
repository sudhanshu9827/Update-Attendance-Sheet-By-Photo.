from sheets import get_google_sheet


worksheet = get_google_sheet()

worksheet.update(
    range_name="A1",
    values=[["ATTENDANCE AGENT CONNECTED"]]
)

print("✅ Sheet connected successfully!")