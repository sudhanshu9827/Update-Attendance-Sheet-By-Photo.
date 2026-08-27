import os

import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import gspread
from dotenv import load_dotenv

from google.oauth2.service_account import Credentials as ServiceAccountCredentials



load_dotenv()
# =======================================
# Configuration
# =======================================

SHEET_URL = os.getenv("SHEET_URL")

if not SHEET_URL:
    try:
        import streamlit as st
        SHEET_URL = st.secrets["SHEET_URL"]
    except Exception:
        pass

if not SHEET_URL:
    raise ValueError(
        "SHEET_URL is not configured."
    )

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


# =======================================
# Google Authentication
# =======================================

def get_google_client():

    # ==========================================
    # STREAMLIT CLOUD
    # ==========================================

    try:
        import streamlit as st

        if "gcp_service_account" in st.secrets:

            print(
                "☁️ Using Streamlit Cloud Service Account..."
            )

            service_account_info = dict(
                st.secrets["gcp_service_account"]
            )

            creds = ServiceAccountCredentials.from_service_account_info(
                service_account_info,
                scopes=SCOPES
            )

            return gspread.authorize(creds)

    except Exception as e:

        print(
            f"Cloud authentication unavailable: {e}"
        )

    # ==========================================
    # LOCAL DEVELOPMENT
    # ==========================================

    print("💻 Using local Google OAuth...")

    creds = None

    # ------------------------------------------
    # Existing token
    # ------------------------------------------

    if os.path.exists(TOKEN_FILE):

        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )

    # ------------------------------------------
    # Refresh token
    # ------------------------------------------

    if creds and creds.expired and creds.refresh_token:

        creds.refresh(Request())

    # ------------------------------------------
    # New authentication
    # ------------------------------------------

    if not creds or not creds.valid:

        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE,
            SCOPES
        )

        creds = flow.run_local_server(
            port=0
        )

        with open(TOKEN_FILE, "w") as token:

            token.write(
                creds.to_json()
            )

    return gspread.authorize(creds)


# =======================================
# Get Worksheet
# =======================================

def get_worksheet():

    gc = get_google_client()

    spreadsheet = gc.open_by_url(
        SHEET_URL
    )

    worksheet = spreadsheet.sheet1

    return worksheet


# =======================================
# Normalize status
# =======================================

def normalize_status(value):

    value = str(value).strip().upper()

    if value in [
        "P",
        "PRESENT",
        "TRUE"
    ]:
        return "PRESENT"

    if value in [
        "A",
        "ABSENT",
        "FALSE"
    ]:
        return "ABSENT"

    if value == "":
        return ""

    return value


# =======================================
# Prepare Sheet Information
# =======================================

def prepare_sheet_data(worksheet):

    data = worksheet.get_all_values()

    if not data:

        raise ValueError(
            "Google Sheet is empty."
        )

    headers = data[0]

    # -----------------------------------
    # Normalize headers
    # -----------------------------------

    normalized_headers = [
        header.strip()
        for header in headers
    ]

    # -----------------------------------
    # Find Roll No column
    # -----------------------------------

    try:

        roll_column = [
            header.lower()
            for header in normalized_headers
        ].index("roll no")

    except ValueError:

        raise ValueError(
            f"Could not find 'Roll No' column. "
            f"Headers received: {headers}"
        )

    # -----------------------------------
    # Roll No → Sheet row
    # -----------------------------------

    roll_rows = {}

    for row_index, row in enumerate(
        data[1:],
        start=2
    ):

        if roll_column >= len(row):
            continue

        roll_no = str(
            row[roll_column]
        ).strip()

        if roll_no:

            roll_rows[roll_no] = row_index

    # -----------------------------------
    # Date → Sheet column
    # -----------------------------------

    date_columns = {}

    for column_index, header in enumerate(
        normalized_headers
    ):

        if header:

            date_columns[
                header
            ] = column_index

    return {
        "data": data,
        "headers": headers,
        "roll_column": roll_column,
        "roll_rows": roll_rows,
        "date_columns": date_columns
    }


# =======================================
# PREVIEW
# =======================================

def preview_attendance(
    worksheet,
    attendance
):

    sheet_data = prepare_sheet_data(
        worksheet
    )

    data = sheet_data["data"]
    roll_rows = sheet_data["roll_rows"]
    date_columns = sheet_data["date_columns"]

    # -----------------------------------
    # Results
    # -----------------------------------

    changes = []

    conflicts = []

    skipped = []

    missing_students = []

    missing_dates = []

    # ===================================
    # Examine every Gemini record
    # ===================================

    for record in attendance.records:

        roll_no = str(
            record.roll_no
        ).strip()

        date = str(
            record.date
        ).strip()

        detected_status = (
            "PRESENT"
            if record.marked
            else "ABSENT"
        )

        # -----------------------------------
        # Student doesn't exist
        # -----------------------------------

        if roll_no not in roll_rows:

            missing_students.append({
                "roll_no": roll_no,
                "date": date,
                "detected": detected_status
            })

            continue

        row = roll_rows[
            roll_no
        ]

        # -----------------------------------
        # Date doesn't exist
        # -----------------------------------

        if date not in date_columns:

            missing_dates.append({
                "roll_no": roll_no,
                "date": date,
                "detected": detected_status
            })

            continue

        column = date_columns[
            date
        ]

        # -----------------------------------
        # Existing value
        # -----------------------------------

        existing_value = ""

        if (
            row - 1 < len(data)
            and column < len(data[row - 1])
        ):

            existing_value = normalize_status(
                data[row - 1][column]
            )

        # ===================================
        # EMPTY → SAFE CHANGE
        # ===================================

        if existing_value == "":

            changes.append({
                "roll_no": roll_no,
                "date": date,
                "row": row,
                "column": column + 1,
                "existing": "",
                "detected": detected_status
            })

        # ===================================
        # SAME → SKIP
        # ===================================

        elif existing_value == detected_status:

            skipped.append({
                "roll_no": roll_no,
                "date": date,
                "status": existing_value
            })

        # ===================================
        # DIFFERENT → CONFLICT
        # ===================================

        else:

            conflicts.append({
                "roll_no": roll_no,
                "date": date,
                "row": row,
                "column": column + 1,
                "existing": existing_value,
                "detected": detected_status
            })

    # ===================================
    # Return preview
    # ===================================

    return {
        "changes": changes,
        "conflicts": conflicts,
        "skipped": skipped,
        "missing_students": missing_students,
        "missing_dates": missing_dates
    }


# =======================================
# APPLY CHANGES
# =======================================


def apply_attendance_changes(
    worksheet,
    changes
):

    if not changes:
        return {
            "updated": 0
        }

    # ===================================
    # 1. Update cell values
    # ===================================

    value_updates = []

    for change in changes:

        row = change["row"]
        column = change["column"]

        status = str(
            change["detected"]
        ).strip().upper()

        cell = gspread.utils.rowcol_to_a1(
            row,
            column
        )

        value_updates.append({
            "range": cell,
            "values": [[status]]
        })

    # -----------------------------------
    # Update values
    # -----------------------------------

    worksheet.batch_update(
        value_updates
    )

    # ===================================
    # 2. Apply colors
    # ===================================

    color_updates = []

    for change in changes:

        row = change["row"]
        column = change["column"]

        status = str(
            change["detected"]
        ).strip().upper()

        cell = gspread.utils.rowcol_to_a1(
            row,
            column
        )

        # --------------------------------
        # PRESENT → GREEN
        # --------------------------------

        if status == "PRESENT":

            color_updates.append({

                "range": cell,

                "format": {

                    "backgroundColor": {
                        "red": 0.72,
                        "green": 0.88,
                        "blue": 0.72
                    },

                    "textFormat": {

                        "bold": True,

                        "foregroundColor": {
                            "red": 0.0,
                            "green": 0.35,
                            "blue": 0.0
                        }
                    },

                    "horizontalAlignment": "CENTER",

                    "verticalAlignment": "MIDDLE"
                }
            })

        # --------------------------------
        # ABSENT → RED
        # --------------------------------

        elif status == "ABSENT":

            color_updates.append({

                "range": cell,

                "format": {

                    "backgroundColor": {
                        "red": 0.95,
                        "green": 0.70,
                        "blue": 0.70
                    },

                    "textFormat": {

                        "bold": True,

                        "foregroundColor": {
                            "red": 0.65,
                            "green": 0.0,
                            "blue": 0.0
                        }
                    },

                    "horizontalAlignment": "CENTER",

                    "verticalAlignment": "MIDDLE"
                }
            })

    # ===================================
    # 3. Apply formatting
    # ===================================

    if color_updates:

        worksheet.batch_format(
            color_updates
        )

    # ===================================
    # 4. Return result
    # ===================================

    return {
        "updated": len(changes)
    }