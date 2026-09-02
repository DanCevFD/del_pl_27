from shiny import App, ui, render, reactive, Inputs, Outputs, Session
import pandas as pd
import re
from urllib.parse import quote
from datetime import date


# ============================================================
# CONFIGURATION
# ============================================================

APP_TITLE = "Delivery Information"


# ============================================================
# EMAIL CONFIGURATION
# ============================================================
#
# MAIN EMAIL
#
OWNER_EMAIL = "Stephan.Gilis@unitedbeetseeds.org"


# ------------------------------------------------------------
# CC EMAIL
#
SECOND_OWNER_EMAIL = "Danny.Cevallos@unitedbeetseeds.org"


# ============================================================
# LOAD CSV
# ============================================================

try:

    country_df = pd.read_csv(
        "items_week.csv"
    )

except Exception as e:

    raise RuntimeError(
        f"Could not read items_week.csv: {e}"
    )


# ============================================================
# CLEAN COLUMN NAMES
# ============================================================

country_df.columns = (
    country_df.columns
    .str.strip()
)


# ============================================================
# REQUIRED COLUMNS
# ============================================================

required_columns = [
    "DST",
    "min_date",
    "max_date",
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
        "items_week.csv is missing the following columns: "
        + ", ".join(missing_columns)
    )


# ============================================================
# CLEAN TEXT COLUMNS
# ============================================================

country_df["DST"] = (
    country_df["DST"]
    .fillna("")
    .astype(str)
    .str.strip()
)


country_df["DESTINATION_NAME"] = (
    country_df["DESTINATION_NAME"]
    .fillna("")
    .astype(str)
    .str.strip()
)


# ============================================================
# CLEAN DATE COLUMNS
# ============================================================

country_df["min_date"] = pd.to_datetime(
    country_df["min_date"],
    errors="coerce"
)


country_df["max_date"] = pd.to_datetime(
    country_df["max_date"],
    errors="coerce"
)


# ============================================================
# CLEAN NUMERIC COLUMNS
# ============================================================

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


# ============================================================
# REMOVE INVALID DESTINATIONS
# ============================================================

country_df = country_df[
    country_df["DESTINATION_NAME"] != ""
].copy()


country_df = country_df.dropna(
    subset=[
        "min_week",
        "max_week"
    ]
)


# ============================================================
# CONVERT WEEK NUMBERS TO INTEGER
# ============================================================

country_df["min_week"] = (
    country_df["min_week"]
    .astype(int)
)


country_df["max_week"] = (
    country_df["max_week"]
    .astype(int)
)


# ============================================================
# REMOVE DUPLICATE DESTINATIONS
# ============================================================

country_df = (
    country_df
    .drop_duplicates(
        subset=[
            "DESTINATION_NAME"
        ]
    )
    .reset_index(drop=True)
)


# ============================================================
# DESTINATION LIST
# ============================================================

destinations = (
    country_df[
        "DESTINATION_NAME"
    ]
    .sort_values()
    .tolist()
)


# ============================================================
# MONTH CALCULATION
# ============================================================

def get_month_for_week(
    week,
    country
):

    min_week = int(
        country["min_week"]
    )

    min_date = country["min_date"]

    if pd.isna(min_date):

        return ""

    min_date = pd.Timestamp(
        min_date
    )

    week_difference = (
        int(week)
        - min_week
    )

    calculated_date = (
        min_date
        + pd.Timedelta(
            weeks=week_difference
        )
    )

    max_date = country["max_date"]

    if not pd.isna(max_date):

        max_date = pd.Timestamp(
            max_date
        )

        if calculated_date > max_date:

            calculated_date = max_date

    return calculated_date.strftime(
        "%B"
    )


# ============================================================
# FORMAT ORD
# ============================================================

def format_ord(value):

    if pd.isna(value):

        return ""

    try:

        numeric_value = float(
            value
        )

        if numeric_value.is_integer():

            return str(
                int(numeric_value)
            )

        return str(
            numeric_value
        )

    except Exception:

        return str(
            value
        )


# ============================================================
# FORMAT R VECTOR
# ============================================================

def create_r_vector(
    submission_df
):

    columns = [
        "DST",
        "DESTINATION",
        "WEEK",
        "qty",
        "percent"
    ]

    data = submission_df.copy()

    # --------------------------------------------------------
    # Convert everything to strings
    # --------------------------------------------------------

    for column in columns:

        data[column] = (
            data[column]
            .astype(str)
        )

    # --------------------------------------------------------
    # Calculate column widths
    # --------------------------------------------------------

    widths = {}

    for column in columns:

        maximum = max(
            len(column),
            max(
                len(value)
                for value in data[column]
            )
        )

        widths[column] = maximum

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    header_parts = []

    for column in columns:

        header_parts.append(
            column.ljust(
                widths[column]
            )
        )

    header_line = (
        " ; ".join(
            header_parts
        )
        .rstrip()
    )

    lines = [
        header_line
    ]

    # --------------------------------------------------------
    # Data rows
    # --------------------------------------------------------

    for _, row in data.iterrows():

        parts = []

        for column in columns:

            value = str(
                row[column]
            )

            if column in [
                "DST",
                "DESTINATION"
            ]:

                formatted = value.ljust(
                    widths[column]
                )

            else:

                formatted = value.rjust(
                    widths[column]
                )

            parts.append(
                formatted
            )

        lines.append(
            " ; ".join(
                parts
            )
        )

    # --------------------------------------------------------
    # Convert to R strings
    # --------------------------------------------------------

    quoted_lines = []

    for line in lines:

        safe_line = (
            line
            .replace(
                "\\",
                "\\\\"
            )
            .replace(
                '"',
                '\\"'
            )
        )

        quoted_lines.append(
            f'"{safe_line}"'
        )

    # --------------------------------------------------------
    # Final c()
    # --------------------------------------------------------

    r_vector = (
        "c(\n"
        + ",\n".join(
            quoted_lines
        )
        + "\n)"
    )

    return r_vector


# ============================================================
# USER INTERFACE
# ============================================================

app_ui = ui.page_fluid(

    ui.tags.head(

        ui.tags.title(
            APP_TITLE
        ),

        # ====================================================
        # JAVASCRIPT FOR REMOTE OUTLOOK
        # ====================================================

        ui.tags.script("""

        (function() {

            let outlookWindow = null;

            document.addEventListener(
                "click",
                function(event) {

                    const button =
                        event.target.closest(
                            "#send"
                        );

                    if (!button) {
                        return;
                    }

                    outlookWindow = window.open(
                        "about:blank",
                        "_blank"
                    );

                },
                true
            );


            Shiny.addCustomMessageHandler(
                "open_outlook",
                function(message) {

                    const url = message.url;

                    if (!url) {
                        return;
                    }

                    if (
                        outlookWindow &&
                        !outlookWindow.closed
                    ) {

                        outlookWindow.location.href =
                            url;

                        outlookWindow.focus();

                    }

                    else {

                        window.location.href =
                            url;

                    }

                }
            );

        })();

        """),


        # ====================================================
        # WEEK SELECTOR JAVASCRIPT
        # ====================================================

        ui.tags.script("""

        (function() {

            let weekPicker = null;
            let currentMonth = null;
            let currentYear = null;


            // ==================================================
            // ISO WEEK NUMBER
            // ==================================================

            function getISOWeek(dateObj) {

                const d = new Date(
                    Date.UTC(
                        dateObj.getFullYear(),
                        dateObj.getMonth(),
                        dateObj.getDate()
                    )
                );

                const day =
                    d.getUTCDay() || 7;

                d.setUTCDate(
                    d.getUTCDate()
                    + 4
                    - day
                );

                const yearStart =
                    new Date(
                        Date.UTC(
                            d.getUTCFullYear(),
                            0,
                            1
                        )
                    );

                return Math.ceil(
                    (
                        (
                            d - yearStart
                        ) / 86400000
                        + 1
                    ) / 7
                );

            }


            // ==================================================
            // CREATE PICKER
            // ==================================================

            function createWeekPicker() {

                if (weekPicker) {
                    return;
                }

                weekPicker = $(
                    "<div id='custom-week-picker'></div>"
                );

                $("body").append(
                    weekPicker
                );


                weekPicker.on(
                    "mousedown",
                    function(event) {

                        event.stopPropagation();

                    }
                );

            }


            // ==================================================
            // POSITION PICKER
            // ==================================================

            function positionWeekPicker() {

                const input =
                    $("#replenishment_week");

                if (
                    !input.length ||
                    !weekPicker
                ) {
                    return;
                }

                const offset =
                    input.offset();

                weekPicker.css({

                    top:
                        offset.top
                        + input.outerHeight()
                        + 4,

                    left:
                        offset.left

                });

            }


            // ==================================================
            // DRAW PICKER
            // ==================================================

            function drawWeekPicker() {

                createWeekPicker();


                const monthNames = [

                    "January",
                    "February",
                    "March",
                    "April",
                    "May",
                    "June",
                    "July",
                    "August",
                    "September",
                    "October",
                    "November",
                    "December"

                ];


                let html = "";


                // ------------------------------------------------
                // HEADER
                // ------------------------------------------------

                html +=
                    "<div class='week-picker-header'>";

                html +=
                    "<button " +
                    "type='button' " +
                    "class='week-picker-prev'>" +
                    "&#8249;" +
                    "</button>";

                html +=
                    "<div class='week-picker-title'>" +
                    monthNames[currentMonth]
                    + " "
                    + currentYear
                    + "</div>";

                html +=
                    "<button " +
                    "type='button' " +
                    "class='week-picker-next'>" +
                    "&#8250;" +
                    "</button>";

                html +=
                    "</div>";


                // ------------------------------------------------
                // WEEK LABEL
                // ------------------------------------------------

                html +=
                    "<div class='week-picker-label'>" +
                    "Week" +
                    "</div>";


                // ------------------------------------------------
                // WEEKS
                // ------------------------------------------------

                html +=
                    "<div class='week-picker-weeks'>";


                const daysInMonth =
                    new Date(
                        currentYear,
                        currentMonth + 1,
                        0
                    ).getDate();


                /*
                 * Only Mondays are displayed.
                 *
                 * Therefore January 2027 gives:
                 *
                 * Week 1
                 * Week 2
                 * Week 3
                 * Week 4
                 *
                 * corresponding to:
                 *
                 * Jan 4
                 * Jan 11
                 * Jan 18
                 * Jan 25
                 */

                for (
                    let day = 1;
                    day <= daysInMonth;
                    day++
                ) {

                    const d =
                        new Date(
                            currentYear,
                            currentMonth,
                            day
                        );


                    if (
                        d.getDay() !== 1
                    ) {

                        continue;

                    }


                    const week =
                        getISOWeek(d);


                    html +=
                        "<button " +
                        "type='button' " +
                        "class='week-number-button' " +
                        "data-week='" +
                        week +
                        "'>" +
                        week +
                        "</button>";

                }


                html +=
                    "</div>";


                weekPicker.html(
                    html
                );


                // ==================================================
                // PREVIOUS MONTH
                // ==================================================

                weekPicker.find(
                    ".week-picker-prev"
                ).on(
                    "click",
                    function(event) {

                        event.preventDefault();
                        event.stopPropagation();

                        currentMonth--;

                        if (
                            currentMonth < 0
                        ) {

                            currentMonth = 11;
                            currentYear--;

                        }

                        drawWeekPicker();

                    }
                );


                // ==================================================
                // NEXT MONTH
                // ==================================================

                weekPicker.find(
                    ".week-picker-next"
                ).on(
                    "click",
                    function(event) {

                        event.preventDefault();
                        event.stopPropagation();

                        currentMonth++;

                        if (
                            currentMonth > 11
                        ) {

                            currentMonth = 0;
                            currentYear++;

                        }

                        drawWeekPicker();

                    }
                );


                // ==================================================
                // WEEK CLICK
                // ==================================================

                weekPicker.find(
                    ".week-number-button"
                ).on(
                    "click",
                    function(event) {

                        event.preventDefault();
                        event.stopPropagation();

                        const week =
                            $(this).data(
                                "week"
                            );


                        // ------------------------------------------
                        // WRITE WEEK NUMBER IN THE INPUT
                        // ------------------------------------------

                        $("#replenishment_week")
                            .val(
                                String(week)
                            );


                        // ------------------------------------------
                        // Send value to Shiny
                        // ------------------------------------------

                        if (
                            typeof Shiny !==
                            "undefined"
                        ) {

                            Shiny.setInputValue(
                                "replenishment_week",
                                String(week),
                                {
                                    priority:
                                        "event"
                                }
                            );

                        }


                        // ------------------------------------------
                        // Close picker
                        // ------------------------------------------

                        weekPicker.hide();

                    }
                );


                positionWeekPicker();

            }


            // ==================================================
            // OPEN PICKER
            // ==================================================

            function openWeekPicker() {

                createWeekPicker();


                /*
                 * Always start from the current month when
                 * opening it for the first time.
                 */

                if (
                    currentMonth === null ||
                    currentYear === null
                ) {

                    const now =
                        new Date();

                    currentMonth =
                        now.getMonth();

                    currentYear =
                        now.getFullYear();

                }


                drawWeekPicker();

                positionWeekPicker();

                weekPicker.show();

            }


            // ==================================================
            // INPUT CLICK
            // ==================================================

            $(document).on(
                "click",
                "#replenishment_week",
                function(event) {

                    event.preventDefault();
                    event.stopPropagation();

                    openWeekPicker();

                }
            );


            // ==================================================
            // CLOSE OUTSIDE CLICK
            // ==================================================

            $(document).on(
                "mousedown",
                function(event) {

                    if (!weekPicker) {
                        return;
                    }

                    if (
                        weekPicker.is(":visible") &&
                        !$(event.target).closest(
                            "#custom-week-picker"
                        ).length &&
                        !$(event.target).closest(
                            "#replenishment_week"
                        ).length
                    ) {

                        weekPicker.hide();

                    }

                }
            );


            // ==================================================
            // KEEP POSITION
            // ==================================================

            $(window).on(
                "resize scroll",
                function() {

                    if (
                        weekPicker &&
                        weekPicker.is(":visible")
                    ) {

                        positionWeekPicker();

                    }

                }
            );


            // ==================================================
            // DISABLE AUTOCOMPLETE
            // ==================================================

            $(document).on(
                "focus",
                "#replenishment_week",
                function() {

                    $(this).attr(
                        "autocomplete",
                        "off"
                    );

                }
            );

        })();

        """),


        # ====================================================
        # ORIGINAL CSS
        # ====================================================

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

        .country-selector-container {
            margin-top: 25px;
            margin-bottom: 20px;
        }

        .selectize-control {
            max-width: 500px;
        }

        .delivery-table-wrapper {
            width: 100%;
            overflow-x: auto;
            margin-top: 25px;
        }

        .delivery-table {
            border-collapse: collapse;
            width: auto;
            min-width: 800px;
            table-layout: fixed;
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
            padding: 5px;
            text-align: center;
            white-space: nowrap;
        }

        .delivery-table th:nth-child(1),
        .delivery-table td:nth-child(1) {
            width: 150px;
            min-width: 150px;
        }

        .delivery-table th:nth-child(2),
        .delivery-table td:nth-child(2) {
            width: 55px;
            min-width: 55px;
        }

        .delivery-table th:nth-child(3),
        .delivery-table td:nth-child(3) {
            width: 85px;
            min-width: 85px;
        }

        .delivery-table th:nth-child(n+4),
        .delivery-table td:nth-child(n+4) {
            width: 65px;
            min-width: 65px;
            max-width: 65px;
        }

        .month-header {
            background-color: #fafafa !important;
            font-size: 13px;
            color: #555;
            height: 28px;
        }

        .blocked-cell {
            background-color: #eeeeee;
            color: #555;
        }

        .ord-cell {
            text-align: right !important;
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
            width: 80px;
            min-width: 80px;
        }

        .delivery-table .form-group {
            margin-bottom: 0;
        }

        .delivery-table input[type="text"] {
            width: 55px !important;
            min-width: 55px !important;
            max-width: 55px !important;
            height: 32px !important;
            padding: 3px !important;
            text-align: center;
            box-sizing: border-box;
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


        /* =====================================================
           WEEK PICKER
           ===================================================== */

        #custom-week-picker {

            position: absolute;

            background: white;

            border: 1px solid #d0d2d5;

            border-radius: 6px;

            box-shadow:
                0 4px 15px rgba(0,0,0,0.15);

            width: 220px;

            padding: 10px;

            z-index: 99999;

            font-family:
                Arial,
                sans-serif;

        }


        .week-picker-header {

            display: flex;

            align-items: center;

            justify-content: space-between;

            margin-bottom: 8px;

        }


        .week-picker-title {

            font-size: 15px;

            font-weight: 600;

            text-align: center;

            flex: 1;

        }


        .week-picker-prev,
        .week-picker-next {

            border: none;

            background: transparent;

            cursor: pointer;

            font-size: 25px;

            width: 30px;

            height: 30px;

            line-height: 25px;

            border-radius: 4px;

        }


        .week-picker-prev:hover,
        .week-picker-next:hover {

            background-color: #f0f1f3;

        }


        .week-picker-label {

            text-align: center;

            font-size: 12px;

            font-weight: 600;

            color: #666;

            border-bottom:
                1px solid #ddd;

            padding-bottom: 6px;

            margin-bottom: 6px;

        }


        .week-picker-weeks {

            display: flex;

            flex-direction: column;

            gap: 4px;

        }


        .week-number-button {

            width: 100%;

            height: 32px;

            border:
                1px solid #d0d2d5;

            border-radius: 4px;

            background: white;

            cursor: pointer;

            font-size: 14px;

        }


        .week-number-button:hover {

            background-color: #f0f1f3;

        }


        #replenishment_week {

            width: 55px !important;

            min-width: 55px !important;

            max-width: 55px !important;

            height: 32px !important;

            padding: 3px !important;

            text-align: center;

            box-sizing: border-box;

            cursor: pointer;

        }


        .replenishment-label {

            font-size: 12px;

            color: #555;

            margin-right: 5px;

        }

        """)
    ),


    ui.div(

        {
            "class":
                "main-container"
        },

        ui.div(
            {
                "class":
                    "title"
            },

            APP_TITLE
        ),

        ui.div(
            {
                "class":
                    "subtitle"
            },

            "Select a destination and enter the "
            "delivery quantities for each week."
        ),

        ui.input_action_button(
            "start_input",
            "Input information"
        ),

        ui.output_ui(
            "country_selector"
        ),

        ui.output_ui(
            "delivery_table"
        ),

        ui.output_ui(
            "status"
        )

    )

)


# ============================================================
# SERVER
# ============================================================

def server(
    input: Inputs,
    output: Outputs,
    session: Session
):

    # ========================================================
    # STATE
    # ========================================================

    input_enabled = reactive.Value(
        False
    )

    current_country = reactive.Value(
        None
    )

    status_message = reactive.Value(
        None
    )

    status_type = reactive.Value(
        None
    )


    # ========================================================
    # START INPUT
    # ========================================================

    @reactive.effect
    @reactive.event(
        input.start_input
    )
    def start_information():

        input_enabled.set(
            True
        )

        current_country.set(
            None
        )

        status_type.set(
            None
        )

        status_message.set(
            None
        )

        try:

            ui.update_selectize(
                "destination",
                selected=""
            )

        except Exception:

            pass


    # ========================================================
    # COUNTRY SELECTOR
    # ========================================================

    @output
    @render.ui
    def country_selector():

        if not input_enabled():

            return ui.HTML(
                ""
            )

        choices = {
            "":
                ""
        }

        choices.update(
            {
                destination:
                    destination
                for destination in destinations
            }
        )

        return ui.div(

            {
                "class":
                    "country-selector-container"
            },

            ui.div(
                {
                    "class":
                        "section-title"
                },

                "Destination"
            ),

            ui.input_selectize(

                "destination",

                "Country",

                choices=choices,

                selected="",

                multiple=False,

                options={

                    "placeholder":
                        "Search for a country...",

                    "allowEmptyOption":
                        True

                }

            )

        )


    # ========================================================
    # COUNTRY CHANGE
    # ========================================================

    @reactive.effect
    @reactive.event(
        input.destination
    )
    def destination_changed():

        destination = (
            input.destination()
        )

        if not destination:

            current_country.set(
                None
            )

            return

        selected = country_df[
            country_df[
                "DESTINATION_NAME"
            ]
            == destination
        ]

        if selected.empty:

            current_country.set(
                None
            )

            return

        country = (
            selected
            .iloc[0]
            .to_dict()
        )

        current_country.set(
            country
        )

        status_message.set(
            None
        )

        status_type.set(
            None
        )


    # ========================================================
    # QUANTITY INPUT
    # ========================================================

    def create_quantity_input(
        week
    ):

        return ui.input_text(

            f"week_{week}",

            None,

            value="",

            placeholder=""

        )


    # ========================================================
    # REPLENISHMENT WEEK INPUT
    # ========================================================

    def create_replenishment_week_input():

        return ui.input_text(

            "replenishment_week",

            None,

            value="",

            placeholder=""

        )


    # ========================================================
    # DELIVERY TABLE
    # ========================================================

    @output
    @render.ui
    def delivery_table():

        country = current_country()

        if country is None:

            return ui.HTML(
                ""
            )

        destination = str(
            country[
                "DESTINATION_NAME"
            ]
        )

        dst = str(
            country[
                "DST"
            ]
        )

        ord_display = format_ord(
            country[
                "ord"
            ]
        )

        min_week = int(
            country[
                "min_week"
            ]
        )

        max_week = int(
            country[
                "max_week"
            ]
        )

        weeks = list(
            range(
                min_week,
                max_week + 1
            )
        )

        months = [

            get_month_for_week(
                week,
                country
            )

            for week in weeks

        ]


        # ====================================================
        # MONTH HEADER
        # ====================================================

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


        # ====================================================
        # WEEK HEADER
        # ====================================================

        header_cells = [

            ui.tags.th(
                "DESTINATION"
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

        header_cells.append(

            ui.tags.th(
                ""
            )

        )


        # ====================================================
        # MONTH ROW
        # ====================================================

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


        # ====================================================
        # QUANTITY ROW
        # ====================================================

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


        # ====================================================
        # TOTAL
        # ====================================================

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


        # ====================================================
        # SEND + REPLENISHMENT WEEK
        # ====================================================

        quantity_cells.append(

            ui.tags.td(

                ui.span(
                    "Week",
                    {
                        "class":
                            "replenishment-label"
                    }
                ),

                create_replenishment_week_input(),

                ui.input_action_button(
                    "send",
                    "Send"
                ),

                {
                    "class":
                        "send-cell"
                }

            )

        )


        # ====================================================
        # PERCENTAGE ROW
        # ====================================================

        percentage_cells = [

            ui.tags.td(
                ""
            ),

            ui.tags.td(
                ""
            ),

            ui.tags.td(
                ""
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


        # ====================================================
        # TABLE
        # ====================================================

        return ui.div(

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
            country[
                "min_week"
            ]
        )

        max_week = int(
            country[
                "max_week"
            ]
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

            if not value:

                continue

            try:

                total += float(
                    value
                )

            except Exception:

                continue


        if total == int(
            total
        ):

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

        @output(
            id=f"percent_{week}"
        )
        @render.text
        def percentage():

            country = current_country()

            if country is None:

                return ""

            min_week = int(
                country[
                    "min_week"
                ]
            )

            max_week = int(
                country[
                    "max_week"
                ]
            )

            total = 0

            for w in range(
                min_week,
                max_week + 1
            ):

                value = getattr(
                    input,
                    f"week_{w}"
                )()

                if not value:

                    continue

                try:

                    total += float(
                        value
                    )

                except Exception:

                    continue


            value = getattr(
                input,
                f"week_{week}"
            )()

            if (
                not value
                or total == 0
            ):

                return "0%"

            try:

                result = (
                    float(value)
                    / total
                    * 100
                )

                return (
                    f"{result:.0f}%"
                )

            except Exception:

                return "0%"


        return percentage


    # ========================================================
    # REGISTER WEEK OUTPUTS
    # ========================================================

    for week in range(
        1,
        54
    ):

        make_percentage_renderer(
            week
        )


    # ========================================================
    # AUTOMATIC ORD LIMIT
    # ========================================================

    def make_week_limiter(
        week
    ):

        @reactive.effect
        @reactive.event(
            lambda:
                getattr(
                    input,
                    f"week_{week}"
                )()
        )
        def limit_week():

            country = current_country()

            if country is None:

                return


            # ------------------------------------------------
            # ORD
            # ------------------------------------------------

            ord_value = country.get(
                "ord"
            )

            if pd.isna(
                ord_value
            ):

                return

            try:

                ord_value = int(
                    float(
                        ord_value
                    )
                )

            except Exception:

                return


            # ------------------------------------------------
            # CURRENT VALUE
            # ------------------------------------------------

            current_value = getattr(
                input,
                f"week_{week}"
            )()

            if not current_value:

                return

            current_value = str(
                current_value
            ).strip()


            # ------------------------------------------------
            # Only process whole numbers
            # ------------------------------------------------

            if not current_value.isdigit():

                return

            current_value = int(
                current_value
            )


            # ------------------------------------------------
            # Calculate OTHER weeks
            # ------------------------------------------------

            other_total = 0

            min_week = int(
                country[
                    "min_week"
                ]
            )

            max_week = int(
                country[
                    "max_week"
                ]
            )

            for other_week in range(
                min_week,
                max_week + 1
            ):

                if other_week == week:

                    continue

                other_value = getattr(
                    input,
                    f"week_{other_week}"
                )()

                if not other_value:

                    continue

                other_value = str(
                    other_value
                ).strip()

                if other_value.isdigit():

                    other_total += int(
                        other_value
                    )


            # ------------------------------------------------
            # Remaining quantity
            # ------------------------------------------------

            remaining = (
                ord_value
                - other_total
            )

            remaining = max(
                0,
                remaining
            )


            # ------------------------------------------------
            # Cap current value
            # ------------------------------------------------

            if current_value > remaining:

                ui.update_text(
                    f"week_{week}",
                    value=str(
                        remaining
                    )
                )


        return limit_week


    # --------------------------------------------------------
    # REGISTER LIMITERS
    # --------------------------------------------------------

    for week in range(
        1,
        54
    ):

        make_week_limiter(
            week
        )


    # ========================================================
    # SEND
    # ========================================================

    @reactive.effect
    @reactive.event(
        input.send
    )
    async def process_submission():

        country = current_country()

        if country is None:

            status_type.set(
                "error"
            )

            status_message.set(
                "Please select a destination first."
            )

            return


        # ====================================================
        # REPLENISHMENT WEEK
        # ====================================================

        replenishment_week = (
            input.replenishment_week()
        )

        if (
            not replenishment_week
            or not str(
                replenishment_week
            ).isdigit()
        ):

            status_type.set(
                "error"
            )

            status_message.set(
                "Please select a replenishment week."
            )

            return

        replenishment_week = int(
            replenishment_week
        )


        # ====================================================
        # ORD
        # ====================================================

        ord_value = country.get(
            "ord"
        )

        if pd.isna(
            ord_value
        ):

            ord_value = None

        else:

            ord_value = int(
                float(
                    ord_value
                )
            )


        # ====================================================
        # WEEKS
        # ====================================================

        min_week = int(
            country[
                "min_week"
            ]
        )

        max_week = int(
            country[
                "max_week"
            ]
        )

        rows = []

        total = 0


        for week in range(
            min_week,
            max_week + 1
        ):

            value = getattr(
                input,
                f"week_{week}"
            )()

            if not value:

                value = "0"

            value = str(
                value
            ).strip()


            if not value.isdigit():

                status_type.set(
                    "error"
                )

                status_message.set(
                    f"W{week} must contain "
                    "a whole number."
                )

                return


            numeric_value = int(
                value
            )

            total += numeric_value

            rows.append(

                {
                    "week":
                        week,

                    "qty":
                        numeric_value
                }

            )


        # ====================================================
        # FINAL ORD CHECK
        # ====================================================

        if (
            ord_value is not None
            and total > ord_value
        ):

            status_type.set(
                "error"
            )

            status_message.set(
                "The total quantity cannot "
                f"exceed the ORD value of "
                f"{ord_value:,}."
            )

            return


        # ====================================================
        # REQUIRE QUANTITY
        # ====================================================

        if total <= 0:

            status_type.set(
                "error"
            )

            status_message.set(
                "Please enter at least one quantity."
            )

            return


        # ====================================================
        # BUILD OUTPUT
        # ====================================================

        output_rows = []


        for row in rows:

            week = row[
                "week"
            ]

            qty = row[
                "qty"
            ]

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
                            country[
                                "DST"
                            ]
                        ),

                    "DESTINATION":
                        str(
                            country[
                                "DESTINATION_NAME"
                            ]
                        ),

                    "WEEK":
                        int(
                            week
                        ),

                    "qty":
                        int(
                            qty
                        ),

                    "percent":
                        f"{percentage:.0f}%"

                }

            )


        submission_df = pd.DataFrame(

            output_rows,

            columns=[
                "DST",
                "DESTINATION",
                "WEEK",
                "qty",
                "percent"
            ]

        )


        # ====================================================
        # CREATE R VECTOR
        # ====================================================

        r_vector = create_r_vector(
            submission_df
        )


        # ====================================================
        # EMAIL
        # ====================================================

        subject = (
            "Delivery information - "
            f"{country['DESTINATION_NAME']}"
        )


        body = (
            "Please see below the delivery information\n"
            "\n"
            f"Replenishment week: "
            f"{replenishment_week}\n"
            "\n"
            f"{r_vector}\n"
        )


        # ====================================================
        # MICROSOFT 365 OUTLOOK URL
        # ====================================================

        outlook_url = (
            "https://outlook.office.com/mail/deeplink/compose?"
            "to="
            + quote(
                OWNER_EMAIL
            )
            + ","
            + quote(
                SECOND_OWNER_EMAIL
            )
            + "&subject="
            + quote(
                subject
            )
            + "&body="
            + quote(
                body
            )
        )


        # ====================================================
        # SEND URL TO THE USER'S BROWSER
        # ====================================================

        await session.send_custom_message(
            "open_outlook",
            {
                "url":
                    outlook_url
            }
        )


        # ====================================================
        # SUCCESS
        # ====================================================

        status_type.set(
            "success"
        )

        status_message.set(

            f"""
            Your email has been prepared successfully.<br><br>

            Please review the information in Outlook
            and press <b>Send</b> to submit it.<br><br>

            Replenishment week:
            <b>{replenishment_week}</b><br><br>

            After sending the email, you can press
            <b>Input information</b> to enter data
            for another country.
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

            return ui.HTML(
                ""
            )

        if status_type() == "success":

            return ui.div(

                {
                    "class":
                        "success-box"
                },

                ui.HTML(
                    message
                )

            )

        return ui.div(

            {
                "class":
                    "error-box"
            },

            ui.HTML(
                message
            )

        )


# ============================================================
# CREATE APP
# ============================================================

app = App(
    app_ui,
    server
)
