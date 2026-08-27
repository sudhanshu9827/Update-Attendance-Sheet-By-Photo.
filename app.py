import streamlit as st

from gemini_agent import process_attendance_image
from validator import validate_attendance

from sheets import (
    get_worksheet,
    preview_attendance,
    apply_attendance_changes
)


# =======================================
# Page Configuration
# =======================================

st.set_page_config(
    page_title="Attendance Agent",
    page_icon="📋",
    layout="wide"
)


# =======================================
# Header
# =======================================

st.title("📋 Attendance Agent")

st.markdown(
    """
    ### Upload attendance registers

    The agent will:

    **Image → Gemini → Validation → Preview → Confirm → Google Sheets**
    """
)


# =======================================
# Session State
# =======================================

if "attendance_data" not in st.session_state:

    st.session_state.attendance_data = []


if "processed" not in st.session_state:

    st.session_state.processed = False


if "sheet_preview" not in st.session_state:

    st.session_state.sheet_preview = None


# =======================================
# Upload
# =======================================

uploaded_files = st.file_uploader(

    "Upload attendance register images",

    type=[
        "jpg",
        "jpeg",
        "png",
        "webp"
    ],

    accept_multiple_files=True
)


# =======================================
# Process Images
# =======================================

if uploaded_files:

    st.info(
        f"{len(uploaded_files)} image(s) selected."
    )

    if st.button(
        "🔍 Process Attendance",
        type="primary"
    ):

        # Clear old state

        st.session_state.attendance_data = []

        st.session_state.processed = False

        st.session_state.sheet_preview = None

        all_valid = True

        progress = st.progress(0)

        status_text = st.empty()

        total_images = len(
            uploaded_files
        )

        # ===================================
        # Process each image
        # ===================================

        for index, uploaded_file in enumerate(
            uploaded_files
        ):

            filename = uploaded_file.name

            status_text.write(
                f"🤖 Processing **{filename}**..."
            )

            try:

                # -----------------------------------
                # Read image
                # -----------------------------------

                image_bytes = (
                    uploaded_file.getvalue()
                )

                # -----------------------------------
                # Gemini
                # -----------------------------------

                attendance = (
                    process_attendance_image(
                        image_bytes,
                        filename
                    )
                )

                # -----------------------------------
                # Validate
                # -----------------------------------

                errors = validate_attendance(
                    attendance
                )

                if errors:

                    st.error(
                        f"❌ Validation failed: "
                        f"{filename}"
                    )

                    for error in errors:

                        st.write(
                            f"- {error}"
                        )

                    all_valid = False

                    continue

                # -----------------------------------
                # Save
                # -----------------------------------

                st.session_state.attendance_data.append(
                    {
                        "filename": filename,
                        "attendance": attendance
                    }
                )

                # -----------------------------------
                # Dates
                # -----------------------------------

                dates = sorted(
                    set(
                        record.date
                        for record
                        in attendance.records
                    )
                )

                st.success(
                    f"✅ {filename} — "
                    f"{', '.join(dates)}"
                )

            except Exception as e:

                st.error(
                    f"❌ Failed to process "
                    f"{filename}"
                )

                st.exception(e)

                all_valid = False

            progress.progress(
                (index + 1)
                / total_images
            )

        status_text.empty()

        # ===================================
        # Processing result
        # ===================================

        if all_valid:

            st.session_state.processed = True

            st.success(
                "✅ All images processed and "
                "validated successfully!"
            )

        else:

            st.warning(
                "⚠️ Processing failed. "
                "No Sheet changes will be made."
            )


# =======================================
# Attendance Preview
# =======================================

if st.session_state.processed:

    st.divider()

    st.header("👀 Extracted Attendance")

    total_present = 0
    total_absent = 0
    total_records = 0

    # =======================================
    # Group ALL records by date
    # =======================================

    records_by_date = {}

    for item in st.session_state.attendance_data:

        attendance = item["attendance"]

        for record in attendance.records:

            date = record.date.strip()

            status = (
                "PRESENT"
                if record.marked
                else "ABSENT"
            )

            if date not in records_by_date:
                records_by_date[date] = []

            records_by_date[date].append({
                "Roll No": record.roll_no,
                "Status": status
            })

            # Summary
            total_records += 1

            if record.marked:
                total_present += 1
            else:
                total_absent += 1


    # =======================================
    # Display each date separately
    # =======================================

    for date in sorted(records_by_date.keys()):

        st.subheader(f"📅 {date}")

        date_records = records_by_date[date]

        st.dataframe(
            date_records,
            use_container_width=True,
            hide_index=True
        )

        # Date-specific summary

        date_present = sum(
            1
            for record in date_records
            if record["Status"] == "PRESENT"
        )

        date_absent = sum(
            1
            for record in date_records
            if record["Status"] == "ABSENT"
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Students",
                len(date_records)
            )

        with col2:
            st.metric(
                "Present",
                date_present
            )

        with col3:
            st.metric(
                "Absent",
                date_absent
            )

        st.divider()


    # =======================================
    # Overall Summary
    # =======================================

    st.header("📊 Overall Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Total Records",
            total_records
        )

    with col2:
        st.metric(
            "Present",
            total_present
        )

    with col3:
        st.metric(
            "Absent",
            total_absent
        )


    # ===================================
    # STEP 2:
    # Compare with Google Sheet
    # ===================================

    st.divider()

    st.header(
        "🔎 Review Google Sheet Changes"
    )

    if st.button(
        "🔎 Check Sheet Changes"
    ):

        try:

            with st.spinner(
                "Reading Google Sheet..."
            ):

                worksheet = get_worksheet()

                all_previews = []

                for item in (
                    st.session_state.attendance_data
                ):

                    attendance = item[
                        "attendance"
                    ]

                    preview = preview_attendance(
                        worksheet,
                        attendance
                    )

                    all_previews.append(
                        preview
                    )

                # -----------------------------------
                # Merge previews
                # -----------------------------------

                merged = {

                    "changes": [],

                    "conflicts": [],

                    "skipped": [],

                    "missing_students": [],

                    "missing_dates": []
                }

                for preview in all_previews:

                    for key in merged:

                        merged[key].extend(
                            preview[key]
                        )

                st.session_state.sheet_preview = (
                    merged
                )

            st.success(
                "✅ Sheet comparison complete."
            )

        except Exception as e:

            st.error(
                "❌ Could not compare with Google Sheet."
            )

            st.exception(e)


# =======================================
# Display Sheet Preview
# =======================================

preview = st.session_state.sheet_preview


if preview is not None:

    # ===================================
    # Counts
    # ===================================

    safe_changes = len(
        preview["changes"]
    )

    conflicts = len(
        preview["conflicts"]
    )

    skipped = len(
        preview["skipped"]
    )

    missing_students = len(
        preview["missing_students"]
    )

    missing_dates = len(
        preview["missing_dates"]
    )


    # ===================================
    # Metrics
    # ===================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "✅ Safe Changes",
            safe_changes
        )

    with col2:

        st.metric(
            "⚠️ Conflicts",
            conflicts
        )

    with col3:

        st.metric(
            "⏭️ Already Correct",
            skipped
        )

    with col4:

        st.metric(
            "❓ Missing",
            missing_students
            + missing_dates
        )


    # ===================================
    # Safe changes
    # ===================================

    if safe_changes > 0:

        st.subheader(
            "✅ Changes Ready to Apply"
        )

        st.dataframe(
            preview["changes"],
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No new cells need updating."
        )


    # ===================================
    # Conflicts
    # ===================================

    if conflicts > 0:

        st.subheader(
            "⚠️ Conflicts"
        )

        st.warning(
            "These cells will NOT be overwritten."
        )

        st.dataframe(
            preview["conflicts"],
            use_container_width=True,
            hide_index=True
        )


    # ===================================
    # Missing students
    # ===================================

    if missing_students > 0:

        st.subheader(
            "❓ Missing Students"
        )

        st.dataframe(
            preview["missing_students"],
            use_container_width=True,
            hide_index=True
        )


    # ===================================
    # Missing dates
    # ===================================

    if missing_dates > 0:

        st.subheader(
            "❓ Missing Dates"
        )

        st.dataframe(
            preview["missing_dates"],
            use_container_width=True,
            hide_index=True
        )


    # ===================================
    # Confirmation
    # ===================================

    st.divider()

    st.subheader(
        "🚀 Confirm Update"
    )

    if conflicts > 0:

        st.warning(
            f"There are {conflicts} conflict(s). "
            "They will remain unchanged."
        )

    if safe_changes == 0:

        st.info(
            "There are no new changes to apply."
        )

    else:

        st.write(
            f"**{safe_changes} cells** "
            "are ready to be updated."
        )

        confirm = st.checkbox(
            "I have reviewed the changes above."
        )

        if confirm:

            if st.button(
                "🚀 Confirm & Update Sheet",
                type="primary"
            ):

                try:

                    with st.spinner(
                        "Updating Google Sheet..."
                    ):

                        worksheet = get_worksheet()

                        updated = (
                            apply_attendance_changes(
                                worksheet,
                                preview["changes"]
                            )
                        )

                    st.success(
                        f"🎉 Successfully updated "
                        f"{updated} cell(s)!"
                    )

                    st.balloons()

                    # Clear preview after update

                    st.session_state.sheet_preview = None

                except Exception as e:

                    st.error(
                        "❌ Google Sheet update failed."
                    )

                    st.exception(e)

        else:

            st.info(
                "☝️ Review the changes and "
                "check the confirmation box "
                "before updating."
            )