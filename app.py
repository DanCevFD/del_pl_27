from shiny import App, ui, render, reactive
import pandas as pd
import smtplib
import ssl
import os
import re
from email.message import EmailMessage
from datetime import date, datetime, timedelta


# ============================================================
# CONFIGURATION
# ============================================================

APP_TITLE = "Delivery Information"

# ------------------------------------------------------------
# Email configuration
# ------------------------------------------------------------
#
# DO NOT put your password directly in this file.
#
# These values should eventually be supplied as environment
# variables by the hosting service.
#
# Microsoft 365 example:
#
# SMTP_SERVER = smtp.office365.com
# SMTP_PORT   = 587
#
# ------------------------------------------------------------

OWNER_EMAIL = os.getenv(
    "OWNER_EMAIL",
    "YOUR_EMAIL@example.com"
)

SMTP_SERVER = os.getenv(
    "SMTP_SERVER",
    "smtp.office365.com"
)

SMTP_PORT = int(
    os.getenv(
        "SMTP_PORT",
        "587"
    )
)

SMTP_USERNAME = os.getenv(
    "SMTP_USERNAME",
    ""
)

SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD",
    ""
)


# ============================================================
# LOAD COUNTRY DATA
# ============================================================

try:

    country_df = pd.read_csv(
        "items_week.csv",
        dtype={
            "DST": str,
            "DESTINATION_NAME": str
        }
    )

except Exception as e:

    raise RuntimeError(
        f"Could not read items_week.csv: {e}"
    )


# ------------------------------------------------------------
# Clean columns
# ------------------------------------------------------------

country_df.columns = (
    country_df.columns
    .str.strip()
)


# ------------------------------------------------------------
# Make sure required columns exist
# ------------------------------------------------------------

required_columns = [
    "DST",
    "min_week",
    "max_week",
    "DESTINATION_NAME",
    "ord"
]

missing_columns = [
    column
    for column in required_columns
    if column not in country_df.columns
]

if missing_columns:

    raise ValueError(
        "items_week.csv is missing these columns: "
        + ", ".join(missing_columns)
    )


# ------------------------------------------------------------
# Clean destination names
# ------------------------------------------------------------

country_df["DESTINATION_NAME"] = (
    country_df["DESTINATION_NAME"]
    .fillna("")
    .astype(str)
    .str.strip()
)


# ------------------------------------------------------------
# Keep only countries that can actually be selected
# ------------------------------------------------------------

country_df = country_df[
    country_df["DESTINATION_NAME"] != ""
].copy()


# ------------------------------------------------------------
# Convert numeric columns
# ------------------------------------------------------------

country_df["min_week"] = pd.to_numeric(
    country_df["min_week"],
    errors="coerce"
)

country_df["max_week"] = pd.to_numeric(
    country_df["max_week"],
    errors="coerce"
)

country_df["ord"] = pd.to_numeric(
    country_df["ord"],
    errors="coerce"
)


# ------------------------------------------------------------
# Remove invalid rows
# ------------------------------------------------------------

country_df = country_df.dropna(
    subset=[
        "DST",
        "min_week",
        "max_week"
    ]
)


# ------------------------------------------------------------
# If duplicate destinations exist, keep the first.
#
# If your data can legitimately have multiple rows per
# destination, we should change this later.
# ------------------------------------------------------------

country_df = (
    country_df
    .drop_duplicates(
        subset=["DESTINATION_NAME"]
    )
    .reset_index(drop=True)
)


# ============================================================
# DESTINATION LIST
# ============================================================

destinations = (
    country_df["DESTINATION_NAME"]
    .dropna()
    .astype(str)
    .sort_values()
    .tolist()
)


# ============================================================
# MONTH CALCULATION
# ============================================================

def get_week_month(week_number, year=2026):
    """
    Convert a standard ISO calendar week into a month name.

    We use the Monday of the ISO week.

    IMPORTANT:
    If your min_week/max_week are NOT ISO calendar weeks,
    replace this function with your own week/month mapping.
    """

    try:

        monday = date.fromisocalendar(
            year,
            int(week_number),
            1
        )

        return monday.strftime("%B")

    except Exception:

        return ""


# ============================================================
# EMAIL VALIDATION
# ============================================================

def valid_email(email):

    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    return bool(
        re.match(
            pattern,
            email
        )
    )


# ============================================================
# EMAIL SENDING
# ============================================================

def send_email(
    client_name,
    client_email,
    submission_df
):

    """
    Sends:

    1. Email to the owner
    2. Confirmation email to the client

    submission_df contains:

    DST
    DESTINATION
    WEEK
    qty
    percent
    """

    # --------------------------------------------------------
    # Convert dataframe to CSV
    # --------------------------------------------------------

    csv_content = submission_df.to_csv(
        index=False,
        sep=";"
    )

    # --------------------------------------------------------
    # Human-readable table
    # --------------------------------------------------------

    text_table = submission_df.to_string(
        index=False
    )

    destination = (
        submission_df["DESTINATION"]
        .iloc[0]
    )

    # --------------------------------------------------------
    # OWNER EMAIL
    # --------------------------------------------------------

    owner_message = EmailMessage()

    owner_message["Subject"] = (
        f"Delivery information - "
        f"{destination} - {client_name}"
    )

    owner_message["From"] = SMTP_USERNAME

    owner_message["To"] = OWNER_EMAIL

    owner_message["Reply-To"] = client_email

    owner_body = f"""
New delivery information received.

Client:
{client_name}

Client email:
{client_email}

Destination:
{destination}


Submitted information:

{text_table}


The structured CSV data is attached.
"""

    owner_message.set_content(
        owner_body
    )

    # --------------------------------------------------------
    # CSV ATTACHMENT
    # --------------------------------------------------------

    owner_message.add_attachment(
        csv_content.encode("utf-8"),
        maintype="text",
        subtype="csv",
        filename="delivery_information.csv"
    )

    # --------------------------------------------------------
    # CLIENT CONFIRMATION EMAIL
    # --------------------------------------------------------

    client_message = EmailMessage()

    client_message["Subject"] = (
        "Delivery information successfully received"
    )

    client_message["From"] = SMTP_USERNAME

    client_message["To"] = client_email

    client_body = f"""
Dear {client_name},

Your delivery information has been successfully received.

Destination:
{destination}


Submitted information:

{text_table}


Thank you.
"""

    client_message.set_content(
        client_body
    )

    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    context = ssl.create_default_context()

    with smtplib.SMTP(
        SMTP_SERVER,
        SMTP_PORT
    ) as server:

        server.starttls(
            context=context
        )

        server.login(
            SMTP_USERNAME,
            SMTP_PASSWORD
        )

        server.send_message(
            owner_message
        )

        server.send_message(
            client_message
        )


# ============================================================
# USER INTERFACE
# ============================================================

app_ui = ui.page_fluid(

    # --------------------------------------------------------
    # CSS
    # --------------------------------------------------------

    ui.tags.head(

        ui.tags.title(
            APP_TITLE
        ),

        ui.tags.style("""

        body {
            background-color: #f4f5f7;
            font-family: Arial, sans-serif;
        }

        .main-container {
            max-width: 1250px;
            margin: 35px auto;
            background: white;
            padding: 35px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }

        .title {
            font-size: 30px;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .subtitle {
            color: #666;
            margin-bottom: 30px;
        }

        .section-title {
            font-size: 18px;
            font-weight: 600;
            margin-top: 25px;
            margin-bottom: 15px;
        }

        .input-information-button {
            margin-top: 10px;
            font-weight: 600;
        }

        .delivery-table-wrapper {
            width: 100%;
            overflow-x: auto;
            margin-top: 20px;
        }

        .delivery-table {
            border-collapse: collapse;
            width: 100%;
            min-width: 700px;
        }

        .delivery-table th {
            background-color: #f0f1f3;
            border: 1px solid #d0d2d5;
            padding: 8px;
            text-align: center;
            font-weight: 600;
            white-space: nowrap;
        }

        .delivery-table td {
            border: 1px solid #d0d2d5;
            padding: 6px;
            text-align: center;
            white-space: nowrap;
        }

        .destination-header {
            text-align: left !important;
        }

        .month-header {
            background-color: #fafafa !important;
            font-size: 13px;
            color: #555;
        }

        .blocked-cell {
            background-color: #eeeeee;
            color: #555;
        }

        .week-input {
            width: 90px;
            text-align: right;
            border: 1px solid #aaa;
            padding: 6px;
            border-radius: 4px;
        }

        .week-input:focus {
            outline: none;
            border: 2px solid #555;
        }

        .total-cell {
            background-color: #eeeeee;
            font-weight: 600;
        }

        .percentage-row td {
            background-color: #f8f8f8;
            color: #555;
            font-size: 13px;
        }

        .send-cell {
            border: none !important;
            background-color: white !important;
            padding-left: 15px !important;
        }

        .send-button {
            min-width: 100px;
            font-weight: 600;
        }

        .success-box {
            margin-top: 25px;
            padding: 18px;
            border-radius: 8px;
            background-color: #eaf7ed;
            border: 1px solid #b7dfbf;
            color: #256b35;
            font-weight: 500;
        }

        .error-box {
            margin-top: 25px;
            padding: 18px;
            border-radius: 8px;
            background-color: #fff0f0;
            border: 1px solid #e0b5b5;
            color: #8a2525;
        }

        .waiting-box {
            margin-top: 20px;
            padding: 15px;
            background-color: #f5f5f5;
            border-radius: 8px;
            color: #555;
        }

        .ord-cell {
            text-align: right !important;
        }

        .disabled-section {
            opacity: 0.55;
        }

        """)

    ),

    # --------------------------------------------------------
    # MAIN CONTAINER
    # --------------------------------------------------------

    ui.div(

        {"class": "main-container"},

        ui.div(
            {"class": "title"},
            "Delivery Information"
        ),

        ui.div(
            {"class": "subtitle"},
            "Please enter your information before "
            "entering delivery quantities."
        ),

        # ====================================================
        # CLIENT INFORMATION
        # ====================================================

        ui.div(
            {"class": "section-title"},
            "Your information"
        ),

        ui.layout_columns(

            ui.input_text(
                "client_name",
                "Name",
                placeholder="Your name"
            ),

            ui.input_text(
                "client_email",
                "Email",
                placeholder="your.email@example.com"
            ),

            col_widths=(6, 6)

        ),

        ui.input_action_button(
            "start_input",
            "Input information",
            class_="input-information-button"
        ),

        # ====================================================
        # DELIVERY AREA
        # ====================================================

        ui.output_ui(
            "delivery_area"
        ),

        # ====================================================
        # STATUS
        # ====================================================

        ui.output_ui(
            "status"
        )

    )

)


# ============================================================
# SERVER
# ============================================================

def server(
    input,
    output,
    session
):

    # --------------------------------------------------------
    # Application state
    # --------------------------------------------------------

    input_enabled = reactive.Value(False)

    submitted = reactive.Value(False)

    current_country = reactive.Value(None)

    status_message = reactive.Value(None)

    status_type = reactive.Value(None)

    # --------------------------------------------------------
    # Quantities
    #
    # Stored as a reactive dictionary:
    #
    # {
    #     4: 100,
    #     5: 400,
    #     6: 1012
    # }
    # --------------------------------------------------------

    quantities = reactive.Value({})

    # --------------------------------------------------------
    # Start input
    # --------------------------------------------------------

    @reactive.effect
    @reactive.event(input.start_input)
    def start_information():

        name = (
            input.client_name()
            or ""
        ).strip()

        email = (
            input.client_email()
            or ""
        ).strip()

        errors = []

        if not name:

            errors.append(
                "Please enter your name."
            )

        if not email:

            errors.append(
                "Please enter your email address."
            )

        elif not valid_email(email):

            errors.append(
                "Please enter a valid email address."
            )

        if errors:

            status_type.set(
                "error"
            )

            status_message.set(
                "<br>".join(
                    f"• {x}"
                    for x in errors
                )
            )

            return

        # ----------------------------------------------------
        # Activate country selection
        # ----------------------------------------------------

        input_enabled.set(
            True
        )

        submitted.set(
            False
        )

        status_type.set(
            None
        )

        status_message.set(
            None
        )

    # --------------------------------------------------------
    # Country selection
    # --------------------------------------------------------

    @reactive.effect
    @reactive.event(input.destination)
    def destination_changed():

        destination = input.destination()

        if not destination:

            current_country.set(
                None
            )

            quantities.set({})

            return

        country = country_df[
            country_df["DESTINATION_NAME"]
            == destination
        ]

        if country.empty:

            current_country.set(
                None
            )

            quantities.set({})

            return

        country = country.iloc[0]

        current_country.set(
            country.to_dict()
        )

        # Reset quantities whenever country changes

        quantities.set({})

        status_message.set(None)
        status_type.set(None)

    # ========================================================
    # QUANTITY INPUTS
    # ========================================================

    def create_quantity_input(
        week
    ):

        return ui.input_numeric(
            f"week_{week}",
            None,
            value=None,
            min=0,
            step=1,
            width="90px"
        )

    # --------------------------------------------------------
    # Delivery area
    # --------------------------------------------------------

    @output
    @render.ui
    def delivery_area():

        if not input_enabled():

            return ui.div(
                {
                    "class":
                        "waiting-box"
                },
                "Enter your name and email address, "
                "then press 'Input information' "
                "to begin."
            )

        # ----------------------------------------------------
        # Country selector
        # ----------------------------------------------------

        country_selector = ui.div(

            ui.div(
                {"class": "section-title"},
                "Destination"
            ),

            ui.input_selectize(
                "destination",
                "Country",
                choices=destinations,
                selected=None,
                multiple=False,
                options={
                    "placeholder":
                        "Search for a country..."
                }
            )

        )

        country = current_country()

        # ----------------------------------------------------
        # Nothing selected yet
        # ----------------------------------------------------

        if country is None:

            return country_selector

        # ----------------------------------------------------
        # Country information
        # ----------------------------------------------------

        dst = str(
            country["DST"]
        )

        destination = str(
            country["DESTINATION_NAME"]
        )

        ord_value = country["ord"]

        if pd.isna(ord_value):

            ord_display = ""

        else:

            ord_display = (
                f"{ord_value:g}"
                if isinstance(
                    ord_value,
                    float
                )
                else str(ord_value)
            )

        min_week = int(
            country["min_week"]
        )

        max_week = int(
            country["max_week"]
        )

        weeks = list(
            range(
                min_week,
                max_week + 1
            )
        )

        # ----------------------------------------------------
        # Build month labels
        # ----------------------------------------------------

        months = [
            get_week_month(
                week
            )
            for week in weeks
        ]

        # ----------------------------------------------------
        # MONTH HEADER
        # ----------------------------------------------------

        month_cells = []

        previous_month = None

        for month in months:

            if month == previous_month:

                month_cells.append(
                    ""
                )

            else:

                month_cells.append(
                    month
                )

            previous_month = month

        # ----------------------------------------------------
        # HEADER ROW
        # ----------------------------------------------------

        header_cells = [

            ui.tags.th(
                "DESTINATION",
                {
                    "class":
                        "destination-header"
                }
            ),

            ui.tags.th(
                "DST"
            ),

            ui.tags.th(
                "ord"
            )

        ]

        for week in weeks:

            header_cells.append(
                ui.tags.th(
                    f"W{week}"
                )
            )

        header_cells.append(
            ui.tags.th(
                "Total"
            )
        )

        # Send is outside the actual table

        header_cells.append(
            ui.tags.th("")
        )

        # ----------------------------------------------------
        # MONTH ROW
        # ----------------------------------------------------

        month_row = [

            ui.tags.th(
                "",
                {
                    "class":
                        "month-header"
                }
            ),

            ui.tags.th(
                "",
                {
                    "class":
                        "month-header"
                }
            ),

            ui.tags.th(
                "",
                {
                    "class":
                        "month-header"
                }
            )

        ]

        for month in month_cells:

            month_row.append(
                ui.tags.th(
                    month,
                    {
                        "class":
                            "month-header"
                    }
                )
            )

        month_row.append(
            ui.tags.th(
                "",
                {
                    "class":
                        "month-header"
                }
            )
        )

        month_row.append(
            ui.tags.th(
                "",
                {
                    "class":
                        "month-header"
                }
            )
        )

        # ----------------------------------------------------
        # QUANTITY ROW
        # ----------------------------------------------------

        quantity_cells = [

            ui.tags.td(
                destination,
                {
                    "class":
                        "blocked-cell"
                }
            ),

            ui.tags.td(
                dst,
                {
                    "class":
                        "blocked-cell"
                }
            ),

            ui.tags.td(
                ord_display,
                {
                    "class":
                        "blocked-cell ord-cell"
                }
            )

        ]

        for week in weeks:

            quantity_cells.append(

                ui.tags.td(
                    create_quantity_input(
                        week
                    )
                )

            )

        # Total is calculated below using JS-style
        # reactive outputs.

        quantity_cells.append(

            ui.tags.td(
                ui.output_text(
                    "total_quantity"
                ),
                {
                    "class":
                        "total-cell"
                }
            )

        )

        quantity_cells.append(

            ui.tags.td(
                ui.input_action_button(
                    "send",
                    "Send",
                    class_="send-button"
                ),
                {
                    "class":
                        "send-cell"
                }
            )

        )

        # ----------------------------------------------------
        # PERCENTAGE ROW
        # ----------------------------------------------------

        percentage_cells = [

            ui.tags.td(
                "",
                {
                    "class":
                        "percentage-row"
                }
            ),

            ui.tags.td(
                "",
                {
                    "class":
                        "percentage-row"
                }
            ),

            ui.tags.td(
                "",
                {
                    "class":
                        "percentage-row"
                }
            )

        ]

        for week in weeks:

            percentage_cells.append(

                ui.tags.td(
                    ui.output_text(
                        f"percent_{week}"
                    )
                )

            )

        percentage_cells.append(

            ui.tags.td(
                "100%"
            )

        )

        percentage_cells.append(

            ui.tags.td(
                "",
                {
                    "class":
                        "send-cell"
                }
            )

        )

        # ----------------------------------------------------
        # TABLE
        # ----------------------------------------------------

        table = ui.div(

            {
                "class":
                    "delivery-table-wrapper"
            },

            ui.tags.table(

                {
                    "class":
                        "delivery-table"
                },

                ui.tags.thead(

                    ui.tags.tr(
                        month_row
                    ),

                    ui.tags.tr(
                        header_cells
                    )

                ),

                ui.tags.tbody(

                    ui.tags.tr(
                        quantity_cells
                    ),

                    ui.tags.tr(
                        {
                            "class":
                                "percentage-row"
                        },
                        percentage_cells
                    )

                )

            )

        )

        return ui.div(

            country_selector,

            table

        )

    # ========================================================
    # TOTAL
    # ========================================================

    @output
    @render.text
    def total_quantity():

        country = current_country()

        if country is None:

            return ""

        min_week = int(
            country["min_week"]
        )

        max_week = int(
            country["max_week"]
        )

        total = 0

        for week in range(
            min_week,
            max_week + 1
        ):

            value = getattr(
                input,
                f"week_{week}"
            )()

            if value is not None:

                try:

                    total += float(
                        value
                    )

                except Exception:

                    pass

        if total == int(total):

            return str(
                int(total)
            )

        return str(
            round(
                total,
                2
            )
        )

    # ========================================================
    # PERCENTAGES
    # ========================================================

    def make_percentage_renderer(
        week
    ):

        @output(id=f"percent_{week}")
        @render.text
        def percentage():

            country = current_country()

            if country is None:

                return ""

            total = 0

            min_week = int(
                country["min_week"]
            )

            max_week = int(
                country["max_week"]
            )

            # Calculate total

            for w in range(
                min_week,
                max_week + 1
            ):

                value = getattr(
                    input,
                    f"week_{w}"
                )()

                if value is not None:

                    try:

                        total += float(
                            value
                        )

                    except Exception:

                        pass

            # Current week

            value = getattr(
                input,
                f"week_{week}"
            )()

            if (
                total == 0
                or value is None
            ):

                return "0%"

            try:

                percentage = (
                    float(value)
                    / total
                    * 100
                )

                return (
                    f"{percentage:.0f}%"
                )

            except Exception:

                return "0%"

        return percentage

    # --------------------------------------------------------
    # Create percentage outputs dynamically.
    #
    # We need outputs for all possible weeks.
    # --------------------------------------------------------

    for week in range(
        1,
        54
    ):

        make_percentage_renderer(
            week
        )

    # ========================================================
    # SEND
    # ========================================================

    @reactive.effect
    @reactive.event(input.send)
    def process_submission():

        country = current_country()

        if country is None:

            status_type.set(
                "error"
            )

            status_message.set(
                "Please select a destination first."
            )

            return

        # ----------------------------------------------------
        # Client information
        # ----------------------------------------------------

        client_name = (
            input.client_name()
            or ""
        ).strip()

        client_email = (
            input.client_email()
            or ""
        ).strip()

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        errors = []

        if not client_name:

            errors.append(
                "Name is missing."
            )

        if not valid_email(
            client_email
        ):

            errors.append(
                "Email address is invalid."
            )

        # ----------------------------------------------------
        # Weeks
        # ----------------------------------------------------

        min_week = int(
            country["min_week"]
        )

        max_week = int(
            country["max_week"]
        )

        rows = []

        total = 0

        # ----------------------------------------------------
        # Read quantities
        # ----------------------------------------------------

        for week in range(
            min_week,
            max_week + 1
        ):

            value = getattr(
                input,
                f"week_{week}"
            )()

            if value is None:

                value = 0

            try:

                value = float(
                    value
                )

            except Exception:

                value = 0

            if value < 0:

                errors.append(
                    f"W{week} cannot contain "
                    "a negative quantity."
                )

            total += value

            rows.append(
                {
                    "week": week,
                    "qty": value
                }
            )

        # ----------------------------------------------------
        # Must have some quantity
        # ----------------------------------------------------

        if total <= 0:

            errors.append(
                "Please enter at least one quantity."
            )

        # ----------------------------------------------------
        # Stop if validation failed
        # ----------------------------------------------------

        if errors:

            status_type.set(
                "error"
            )

            status_message.set(
                "<br>".join(
                    f"• {error}"
                    for error in errors
                )
            )

            return

        # ----------------------------------------------------
        # Construct final dataframe
        # ----------------------------------------------------

        output_rows = []

        for row in rows:

            week = row["week"]

            qty = row["qty"]

            # Ignore zero quantities

            if qty == 0:

                continue

            percentage = (
                qty
                / total
                * 100
            )

            output_rows.append(
                {
                    "DST":
                        str(
                            country["DST"]
                        ),

                    "DESTINATION":
                        str(
                            country[
                                "DESTINATION_NAME"
                            ]
                        ),

                    "WEEK":
                        int(week),

                    "qty":
                        qty,

                    "percent":
                        f"{percentage:.0f}%"
                }
            )

        submission_df = pd.DataFrame(
            output_rows
        )

        # ----------------------------------------------------
        # Send
        # ----------------------------------------------------

        try:

            send_email(
                client_name=client_name,
                client_email=client_email,
                submission_df=submission_df
            )

        except Exception as e:

            print(
                "EMAIL ERROR:",
                repr(e)
            )

            status_type.set(
                "error"
            )

            status_message.set(
                "There was an error sending your "
                "information. Please try again."
            )

            return

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        submitted.set(
            True
        )

        status_type.set(
            "success"
        )

        status_message.set(
            f"""
            Your data was successfully sent.<br><br>
            You can press <b>Input information</b>
            to enter data for another country.
            """
        )

    # ========================================================
    # STATUS
    # ========================================================

    @output
    @render.ui
    def status():

        message = status_message()

        if not message:

            return ui.HTML("")

        if status_type() == "success":

            return ui.div(
                {
                    "class":
                        "success-box"
                },
                ui.HTML(message)
            )

        return ui.div(
            {
                "class":
                    "error-box"
            },
            ui.HTML(message)
        )


# ============================================================
# CREATE APPLICATION
# ============================================================

app = App(
    app_ui,
    server
)
