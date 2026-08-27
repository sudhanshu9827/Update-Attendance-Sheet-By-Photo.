import os

from google import genai
from google.genai import types
from dotenv import load_dotenv

from models import AttendanceSheet
from validator import validate_attendance

from sheets import (
    get_worksheet,
    apply_attendance_changes
)


# =======================================
# Load environment variables
# =======================================

load_dotenv()

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    try:
        import streamlit as st
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY is not configured."
    )

# =======================================
# Create Gemini client
# =======================================

client = genai.Client(
    api_key=api_key
)


# =======================================
# Configuration
# =======================================

IMAGE_FOLDER = "attendance_images"

SUPPORTED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
)


# =======================================
# Get images
# =======================================

if not os.path.exists(IMAGE_FOLDER):

    raise FileNotFoundError(
        f"Folder '{IMAGE_FOLDER}' does not exist."
    )


image_files = [
    filename
    for filename in os.listdir(IMAGE_FOLDER)
    if filename.lower().endswith(
        SUPPORTED_EXTENSIONS
    )
]


if not image_files:

    raise FileNotFoundError(
        f"No images found inside '{IMAGE_FOLDER}'."
    )


image_files.sort()


print("\n======================================")
print("       ATTENDANCE AGENT")
print("======================================")

print(
    f"\nFound {len(image_files)} attendance image(s).\n"
)


for filename in image_files:

    print(f"📷 {filename}")


# =======================================
# Prompt
# =======================================

prompt = """
Analyze this attendance register.

The table contains:

- S.No
- Student Name
- Roll No
- Multiple date columns

IMPORTANT:

The date must be read directly from the column
header in the image.

For every visible student and every visible date:

1. Read the student's Roll No.
2. Read the date from the column header.
3. Inspect the corresponding attendance cell.
4. Classify the cell as exactly one of:

   PRESENT
   ABSENT
   UNCLEAR

PRESENT:
- A clearly intentional handwritten signature,
  tick, check mark, or handwriting is visible.
- The mark clearly belongs to this attendance cell.

ABSENT:
- The cell is genuinely blank.
- There is no intentional attendance mark.

UNCLEAR:
- There is a small line, scratch, dot, smudge,
  stain, shadow, or scanning artifact.
- The mark is too small or ambiguous.
- The mark may actually be a table/grid line.
- The mark crosses a cell boundary.
- You cannot confidently determine whether it
  is an attendance mark.

VERY IMPORTANT:

Do NOT consider table borders as attendance marks.

Do NOT consider printed lines as attendance marks.

Do NOT consider scanning artifacts as attendance marks.

Do NOT consider random scratches or stains as attendance marks.

Do NOT infer attendance from neighboring cells.

When uncertain, ALWAYS return UNCLEAR.

Never convert an uncertain mark into PRESENT.

Never invent attendance.

Roll No is the primary identifier.

Do NOT use student names as identifiers.

Do NOT invent missing students.

Do NOT invent missing dates.

Preserve dates exactly as written.

Include every visible student.

Include every visible date.

Return one record for every student-date combination.
"""


# =======================================
# Process one image
# =======================================

def process_image(image_path):

    filename = os.path.basename(
        image_path
    )

    print("\n")
    print("======================================")
    print(f"📷 PROCESSING: {filename}")
    print("======================================")


    # -----------------------------------
    # Read image
    # -----------------------------------

    with open(image_path, "rb") as f:

        image_bytes = f.read()


    # -----------------------------------
    # Determine MIME type
    # -----------------------------------

    extension = os.path.splitext(
        image_path
    )[1].lower()


    mime_types = {

        ".jpg": "image/jpeg",

        ".jpeg": "image/jpeg",

        ".png": "image/png",

        ".webp": "image/webp"
    }


    mime_type = mime_types[
        extension
    ]


    # -----------------------------------
    # Send to Gemini
    # -----------------------------------

    print(
        "🤖 Sending image to Gemini..."
    )


    response = client.models.generate_content(

        model="gemini-3.1-flash-lite",

        contents=[

            prompt,

            types.Part.from_bytes(

                data=image_bytes,

                mime_type=mime_type
            )
        ],

        config=types.GenerateContentConfig(

            response_mime_type="application/json",

            response_schema=AttendanceSheet
        )
    )


    # -----------------------------------
    # Convert response to Pydantic
    # -----------------------------------

    try:

        attendance = (
            AttendanceSheet.model_validate_json(
                response.text
            )
        )

    except Exception as e:

        print(
            f"\n❌ Failed to parse Gemini "
            f"response for {filename}"
        )

        print("\nRaw response:")

        print(response.text)

        raise e


    print(
        "✅ Gemini extraction successful!"
    )


    # -----------------------------------
    # Print detected dates
    # -----------------------------------

    dates = sorted(
        set(
            record.date
            for record in attendance.records
        )
    )


    print(
        f"\n📅 Dates detected: "
        f"{', '.join(dates)}"
    )


    # -----------------------------------
    # Print records
    # -----------------------------------

    print(
        "\n========== GEMINI OUTPUT ==========\n"
    )


    for record in attendance.records:

        status = (

            "PRESENT"

            if record.marked

            else "ABSENT"
        )


        print(

            f"Roll No: {record.roll_no} | "

            f"Date: {record.date} | "

            f"Status: {status}"
        )


    # -----------------------------------
    # Validation
    # -----------------------------------

    print(
        "\n========== VALIDATION ==========\n"
    )


    errors = validate_attendance(
        attendance
    )


    if errors:

        print(
            f"❌ Validation failed "
            f"for {filename}!\n"
        )


        for error in errors:

            print(f"- {error}")


        return None


    print(
        "✅ Attendance data is valid!"
    )


    print(
        f"Total records: "
        f"{len(attendance.records)}"
    )


    # -----------------------------------
    # Summary
    # -----------------------------------

    present = sum(

        1

        for record in attendance.records

        if record.marked
    )


    absent = sum(

        1

        for record in attendance.records

        if not record.marked
    )


    print(
        "\n========== SUMMARY ==========\n"
    )


    print(
        f"Present records : {present}"
    )


    print(
        f"Absent records  : {absent}"
    )


    print(
        f"Total records   : "
        f"{present + absent}"
    )


    return attendance


# =======================================
# Process all images
# =======================================

all_attendance = []


for filename in image_files:

    image_path = os.path.join(
        IMAGE_FOLDER,
        filename
    )


    attendance = process_image(
        image_path
    )


    if attendance is not None:

        all_attendance.append(
            attendance
        )


# =======================================
# Stop if any image failed
# =======================================

if len(all_attendance) != len(
    image_files
):

    print(
        "\n======================================"
    )

    print(
        "❌ PROCESS STOPPED"
    )

    print(
        "======================================"
    )


    print(
        "\nAt least one image failed validation."
    )


    print(
        "Google Sheet was NOT modified."
    )


    raise SystemExit(1)


# =======================================
# Google Sheets
# =======================================

print("\n")

print(
    "======================================"
)

print(
    "       GOOGLE SHEETS"
)

print(
    "======================================"
)


print(
    "\nConnecting to Google Sheet..."
)


try:

    worksheet = get_worksheet()

except Exception as e:

    print(
        "\n❌ Could not connect "
        "to Google Sheet."
    )

    raise e


print(
    "✅ Google Sheet connected!"
)


# =======================================
# Update every attendance image
# =======================================

total_updated = 0

total_skipped = 0

total_conflicts = 0

total_missing_students = 0

total_missing_dates = 0


for attendance in all_attendance:

    print("\n")

    print(
        "--------------------------------------"
    )


    dates = sorted(
        set(
            record.date
            for record in attendance.records
        )
    )


    print(
        f"Updating dates: "
        f"{', '.join(dates)}"
    )


    print(
        "--------------------------------------"
    )


    try:

        result = apply_attendance_changes(

            worksheet,

            attendance
        )


    except Exception as e:

        print(
            "\n❌ Failed to update "
            "Google Sheet."
        )

        raise e


    # -----------------------------------
    # Result from sheets.py
    # -----------------------------------

    total_updated += result["updated"]

    total_skipped += result["skipped"]

    total_conflicts += result["conflicts"]

    total_missing_students += (
        result["missing_students"]
    )

    total_missing_dates += (
        result["missing_dates"]
    )


# =======================================
# Final summary
# =======================================

print("\n")

print(
    "======================================"
)

print(
    "       FINAL SHEET UPDATE"
)

print(
    "======================================"
)


print(
    f"\nImages processed   : "
    f"{len(all_attendance)}"
)


print(
    f"Updated cells      : "
    f"{total_updated}"
)


print(
    f"Already correct    : "
    f"{total_skipped}"
)


print(
    f"Conflicts          : "
    f"{total_conflicts}"
)


print(
    f"Missing students   : "
    f"{total_missing_students}"
)


print(
    f"Missing dates      : "
    f"{total_missing_dates}"
)


print(
    "\n======================================"
)


if total_conflicts > 0:

    print(
        "⚠️ Sheet updated, "
        "but conflicts were found."
    )


elif total_updated > 0:

    print(
        "✅ Attendance sheet "
        "updated successfully!"
    )


else:

    print(
        "ℹ️ No changes were required."
    )


print(
    "======================================"
)