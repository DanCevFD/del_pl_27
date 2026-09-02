from shiny import App, ui, render, reactive, Inputs, Outputs, Session
import pandas as pd
import re
from urllib.parse import quote


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
        # WEEK PICKER JAVASCRIPT
        # ====================================================

        ui.tags.script("""

        (function() {

            let weekPicker = null;

            let pickerYear =
                new Date().getFullYear();

            let pickerMonth =
                new Date().getMonth();


            // ==================================================
            // ISO WEEK
            // ==================================================

            function getISOWeek(date) {

                const tmp = new Date(
                    Date.UTC(
                        date.getFullYear(),
                        date.getMonth(),
                        date.getDate()
                    )
                );

                const dayNum =
                    tmp.getUTCDay() || 7;

                tmp.setUTCDate(
                    tmp.getUTCDate() + 4 - dayNum
                );

                const yearStart =
                    new Date(
                        Date.UTC(
                            tmp.getUTCFullYear(),
                            0,
                            1
                        )
                    );

                return Math.ceil(
                    (
                        (
                            (
                                tmp -
                                yearStart
                            ) / 86400000
                        ) + 1
                    ) / 7
                );
            }


            // ==================================================
            // GET MONDAY
            // ==================================================

            function getMonday(date) {

                const d =
                    new Date(date);

                const day =
                    d.getDay();

                const difference =
                    day === 0
                        ? -6
                        : 1 - day;

                d.setDate(
                    d.getDate() + difference
                );

                return d;
            }


            // ==================================================
            // CREATE PICKER
            // ==================================================

            function createWeekPicker(input) {

                if (weekPicker) {

                    weekPicker.remove();

                    weekPicker = null;
                }


                weekPicker =
                    document.createElement(
                        "div"
                    );

                weekPicker.id =
                    "custom-week-picker";


                document.body.appendChild(
                    weekPicker
                );


                renderWeekPicker(
                    input
                );


                positionWeekPicker(
                    input
                );
            }


            // ==================================================
            // POSITION PICKER
            // ==================================================

            function positionWeekPicker(input) {

                if (
                    !weekPicker ||
                    !input
                ) {
                    return;
                }


                const rect =
                    input.getBoundingClientRect();


                weekPicker.style.left =
                    (
                        rect.left +
                        window.scrollX
                    ) + "px";


                weekPicker.style.top =
                    (
                        rect.bottom +
                        window.scrollY +
                        4
                    ) + "px";
            }


            // ==================================================
            // RENDER PICKER
            // ==================================================

            function renderWeekPicker(input) {

                if (!weekPicker) {
                    return;
                }


                weekPicker.innerHTML = "";


                // ==================================================
                // HEADER
                // ==================================================

                const header =
                    document.createElement(
                        "div"
                    );

                header.className =
                    "week-picker-header";


                const previousButton =
                    document.createElement(
                        "button"
                    );

                previousButton.type =
                    "button";

                previousButton.className =
                    "week-picker-nav";

                previousButton.innerHTML =
                    "‹";


                previousButton.onclick =
                    function(event) {

                        event.preventDefault();
                        event.stopPropagation();

                        pickerMonth--;

                        if (pickerMonth < 0) {

                            pickerMonth = 11;

                            pickerYear--;
                        }

                        renderWeekPicker(
                            input
                        );

                        positionWeekPicker(
                            input
                        );
                    };


                const title =
                    document.createElement(
                        "div"
                    );

                title.className =
                    "week-picker-title";

                const monthName =
                    new Date(
                        pickerYear,
                        pickerMonth,
                        1
                    ).toLocaleString(
                        "default",
                        {
                            month: "long"
                        }
                    );


                title.innerHTML =
                    monthName +
                    " " +
                    pickerYear;


                const nextButton =
                    document.createElement(
                        "button"
                    );

                nextButton.type =
                    "button";

                nextButton.className =
                    "week-picker-nav";

                nextButton.innerHTML =
                    "›";


                nextButton.onclick =
                    function(event) {

                        event.preventDefault();
                        event.stopPropagation();

                        pickerMonth++;

                        if (pickerMonth > 11) {

                            pickerMonth = 0;

                            pickerYear++;
                        }

                        renderWeekPicker(
                            input
                        );

                        positionWeekPicker(
                            input
                        );
                    };


                header.appendChild(
                    previousButton
                );

                header.appendChild(
                    title
                );

                header.appendChild(
                    nextButton
                );


                weekPicker.appendChild(
                    header
                );


                // ==================================================
                // WEEK LABEL
                // ==================================================

                const weekLabel =
                    document.createElement(
                        "div"
                    );

                weekLabel.className =
                    "week-picker-label";

                weekLabel.innerText =
                    "Select a week";


                weekPicker.appendChild(
                    weekLabel
                );


                // ==================================================
                // FIND MONDAYS IN MONTH
                // ==================================================

                const weeksContainer =
                    document.createElement(
                        "div"
                    );

                weeksContainer.className =
                    "week-picker-weeks";


                const firstDay =
                    new Date(
                        pickerYear,
                        pickerMonth,
                        1
                    );

                const lastDay =
                    new Date(
                        pickerYear,
                        pickerMonth + 1,
                        0
                    );


                let monday =
                    getMonday(
                        firstDay
                    );


                /*
                 * If the first Monday belongs to the
                 * previous month, move to the next Monday.
                 */

                if (
                    monday.getMonth() !==
                    pickerMonth
                ) {

                    monday.setDate(
                        monday.getDate() + 7
                    );
                }


                while (
                    monday <= lastDay
                ) {

                    if (
                        monday.getMonth() !==
                        pickerMonth
                    ) {
                        break;
                    }


                    const week =
                        getISOWeek(
                            monday
                        );


                    const weekButton =
                        document.createElement(
                            "button"
                        );

                    weekButton.type =
                        "button";

                    weekButton.className =
                        "week-picker-week";


                    weekButton.innerText =
                        "Week " + week;


                    weekButton.onclick =
                        function(event) {

                            event.preventDefault();
                            event.stopPropagation();


                            input.value =
                                String(
                                    week
                                );


                            input.dispatchEvent(
                                new Event(
                                    "input",
                                    {
                                        bubbles: true
                                    }
                                )
                            );


                            input.dispatchEvent(
                                new Event(
                                    "change",
                                    {
                                        bubbles: true
                                    }
                                )
                            );


                            Shiny.setInputValue(
                                "replenishment_week",
                                String(week),
                                {
                                    priority:
                                        "event"
                                }
                            );


                            if (weekPicker) {

                                weekPicker.remove();

                                weekPicker = null;
                            }
                        };


                    weeksContainer.appendChild(
                        weekButton
                    );


                    monday.setDate(
                        monday.getDate() + 7
                    );
                }


                weekPicker.appendChild(
                    weeksContainer
                );
            }


            // ==================================================
            // OPEN PICKER
            // ==================================================

            document.addEventListener(
                "click",
                function(event) {

                    const input =
                        event.target.closest(
                            "#replenishment_week"
                        );


                    if (!input) {
                        return;
                    }


                    event.preventDefault();
                    event.stopPropagation();


                    if (
                        weekPicker &&
                        weekPicker.parentNode
                    ) {

                        weekPicker.remove();

                        weekPicker = null;

                        return;
                    }


                    pickerYear =
                        new Date().getFullYear();

                    pickerMonth =
                        new Date().getMonth();


                    /*
                     * If there is already a selected week,
                     * keep the current month/year picker
                     * behavior rather than changing the
                     * value.
                     */

                    createWeekPicker(
                        input
                    );
                },
                true
            );


            // ==================================================
            // CLOSE OUTSIDE CLICK
            // ==================================================

            document.addEventListener(
                "click",
                function(event) {

                    if (!weekPicker) {
                        return;
                    }


                    if (
                        !event.target.closest(
                            "#custom-week-picker"
                        ) &&
                        !event.target.closest(
                            "#replenishment_week"
                        )
                    ) {

                        weekPicker.remove();

                        weekPicker = null;
                    }
                }
            );


            // ==================================================
            // REPOSITION ON SCROLL
            // ==================================================

            window.addEventListener(
                "scroll",
                function() {

                    const input =
                        document.getElementById(
                            "replenishment_week"
                        );

                    if (
                        weekPicker &&
                        input
                    ) {

                        positionWeekPicker(
                            input
                        );
                    }
                }
            );


            // ==================================================
            // REPOSITION ON RESIZE
            // ==================================================

            window.addEventListener(
                "resize",
                function() {

                    const input =
                        document.getElementById(
                            "replenishment_week"
                        );

                    if (
                        weekPicker &&
                        input
                    ) {

                        positionWeekPicker(
                            input
                        );
                    }
                }
            );

        })();

        """),

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

        /* ====================================================
           REPLENISHMENT WEEK COLUMN
           ==================================================== */

        .delivery-table th.replenishment-header,
        .delivery-table td.replenishment-cell {
            width: 150px !important;
            min-width: 150px !important;
            max-width: 150px !important;
        }

        .replenishment-header {
            background-color: #f0f1f3 !important;
        }

        .replenishment-cell {
            background-color: white;
            vertical-align: middle;
        }

        .replenishment-label {
            display: inline-block;
            font-size: 12px;
            color: #555;
            margin-right: 5px;
            vertical-align: middle;
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

        /* ====================================================
           SEND BELOW TABLE
           ==================================================== */

        .send-controls {
            margin-top: 12px;
            text-align: right;
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

        /* ====================================================
           WEEK PICKER
           ==================================================== */

        #custom-week-picker {
            position: absolute;
            background: white;
            border: 1px solid #d0d2d5;
            border-radius: 6px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            width: 220px;
            padding: 10px;
            z-index: 99999;
            font-family: Arial, sans-serif;
        }

        .week-picker-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        }

        .week-picker-title {
            font-weight: 600;
            text-align: center;
            flex: 1;
            font-size: 14px;
        }

        .week-picker-nav {
            border: none;
            background: transparent;
            font-size: 24px;
            cursor: pointer;
            width: 30px;
            height: 30px;
            line-height: 25px;
        }

        .week-picker-nav:hover {
            background-color: #f0f1f3;
            border-radius: 4px;
        }

        .week-picker-label {
            font-size: 12px;
            color: #666;
            text-align: center;
            margin-bottom: 8px;
        }

        .week-picker-weeks {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .week-picker-week {
            width: 100%;
            border: 1px solid #d0d2d5;
            background: white;
            border-radius: 4px;
            padding: 7px;
            cursor: pointer;
            font-size: 14px;
            text-align: center;
        }

        .week-picker-week:hover {
            background-color: #f0f1f3;
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

        # ----------------------------------------------------
        # TOTAL COLUMN
        # ----------------------------------------------------

        header_cells.append(

            ui.tags.th(
                "Total"
            )

        )

        # ----------------------------------------------------
        # REPLENISHMENT WEEK COLUMN
        # ----------------------------------------------------

        header_cells.append(

            ui.tags.th(
                "Replenishment week",
                {
                    "class":
                        "replenishment-header"
                }
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

        # Total month cell

        month_row.append(

            ui.tags.th(
                "",
                {
                    "class":
                        "month-header"
                }
            )

        )

        # Replenishment week month cell

        month_row.append(

            ui.tags.th(
                "",
                {
                    "class":
                        "month-header replenishment-header"
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
        # REPLENISHMENT WEEK
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

                {
                    "class":
                        "replenishment-cell"
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

        # Replenishment week percentage cell

        percentage_cells.append(

            ui.tags.td(
                "",
                {
                    "class":
                        "replenishment-cell percentage-row"
                }
            )

        )


        # ====================================================
        # TABLE
        # ====================================================

        table = ui.tags.table(

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


        # ====================================================
        # TABLE + SEND BELOW TABLE
        # ====================================================

        return ui.div(

            ui.div(

                {
                    "class":
                        "delivery-table-wrapper"
                },

                table

            ),

            ui.div(

                {
                    "class":
                        "send-controls"
                },

                ui.input_action_button(
                    "send",
                    "Send"
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

            """
            Your email has been prepared successfully.<br><br>

            Please review the information in Outlook
            and press <b>Send</b> to submit it.<br><br>

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
