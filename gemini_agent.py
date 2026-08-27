import os

# from google import genai
# from google.genai import types
from dotenv import load_dotenv

from models import AttendanceSheet

import google
import sys
import sys
import google

print("========== GOOGLE DEBUG ==========")
print("Python:", sys.version)
print("Google module:", google)
print("Google path:", getattr(google, "__path__", None))
print("Google file:", getattr(google, "__file__", None))

try:
    import google.genai

    print("google.genai FOUND")
    print("google.genai:", google.genai)
    print("google.genai file:", google.genai.__file__)

except Exception as e:

    print("google.genai FAILED")
    print("Error:", repr(e))

print("==================================")

from google import genai
from google.genai import types


# =======================================
# Load environment variables
# =======================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY is not set in .env"
    )


# =======================================
# Gemini client
# =======================================

client = genai.Client(
    api_key=api_key
)


# =======================================
# Prompt
# =======================================

ATTENDANCE_PROMPT = """
Analyze this attendance register.

The table contains:

- S.No
- Student Name
- Roll No
- Multiple date columns

IMPORTANT:

The date must be read directly from the column
header in the image.

Do NOT use the filename to determine the date.

For every visible student and every visible date:

1. Read the student's Roll No.
2. Read the date from the column header.
3. Inspect the corresponding attendance cell.
4. If the cell contains a handwritten signature,
   handwriting, tick, or any other attendance mark,
   set marked=true.
5. If the cell is completely blank,
   set marked=false.

IMPORTANT RULES:

- Roll No is the primary identifier.
- Do NOT use student names as identifiers.
- Do NOT infer attendance from neighboring cells.
- Do NOT invent missing students.
- Do NOT invent missing dates.
- Do NOT assume that a difficult-to-read mark is present.
- Preserve the dates exactly as written in the image.
- Include every visible student.
- Include every visible date.
- Return one record for every student-date combination.

The image may contain more than one date column.
Extract ALL visible date columns.
"""


# =======================================
# MIME type
# =======================================

def get_mime_type(filename):

    extension = os.path.splitext(
        filename
    )[1].lower()

    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp"
    }

    if extension not in mime_types:
        raise ValueError(
            f"Unsupported image format: {extension}"
        )

    return mime_types[extension]


# =======================================
# Process image
# =======================================

def process_attendance_image(
    image_bytes,
    filename="attendance.jpg"
):

    mime_type = get_mime_type(
        filename
    )

    response = client.models.generate_content(

        model="gemini-3.1-flash-lite",

        contents=[

            ATTENDANCE_PROMPT,

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
    # Convert Gemini response
    # -----------------------------------

    attendance = (
        AttendanceSheet.model_validate_json(
            response.text
        )
    )

    return attendance