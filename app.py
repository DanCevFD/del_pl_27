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

OWNER_EMAIL = "Stephan.Gilis@unitedbeetseeds.org"

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
        "SCENARIO",
        "DST",
        "DESTINATION",
        "WEEK",
        "qty",
        "percent",
        "REPLENISHMENT_WEEK"
    ]

    data = submission_df.copy()

    for column in columns:

        data[column] = (
            data[column]
            .astype(str)
        )

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

    for _, row in data.iterrows():

        parts = []

        for column in columns:

            value = str(
                row[column]
            )

            if column in [
                "SCENARIO",
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


            function renderWeekPicker(input) {

                if (!weekPicker) {
                    return;
                }

                weekPicker.innerHTML = "";


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
                                input.id,
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


            document.addEventListener(
                "click",
                function(event) {

                    const input =
                        event.target.closest(
                            "input[id^='replenishment_week_']"
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


                    createWeekPicker(
                        input
                    );
                },
                true
            );


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
                            "input[id^='replenishment_week_']"
                        )
                    ) {

                        weekPicker.remove();

                        weekPicker = null;
                    }
                }
            );


            window.addEventListener(
                "scroll",
                function() {

                    const input =
                        document.querySelector(
                            "input[id^='replenishment_week_']"
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


            window.addEventListener(
                "resize",
                function() {

                    const input =
                        document.querySelector(
                            "input[id^='replenishment_week_']"
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

        .scenario-table + .scenario-table {
            margin-top: 35px;
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
            width: 160px;
            min-width: 160px;
            max-width: 160px;
        }

        .delivery-table th:nth-child(2),
        .delivery-table td:nth-child(2) {
            width: 150px;
            min-width: 150px;
        }

        .delivery-table th:nth-child(3),
        .delivery-table td:nth-child(3) {
            width: 55px;
            min-width: 55px;
        }

        .delivery-table th:nth-child(4),
        .delivery-table td:nth-child(4) {
            width: 85px;
            min-width: 85px;
        }

        .delivery-table th:nth-child(n+5),
        .delivery-table td:nth-child(n+5) {
            width: 65px;
            min-width: 65px;
            max-width: 65px;
        }

        .delivery-table th.replenishment-header,
        .delivery-table td.replenishment-cell {
            width: 140px !important;
            min-width: 140px !important;
            max-width: 140px !important;
        }

        .replenishment-header {
            background-color: #f0f1f3 !important;
            white-space: normal !important;
            line-height: 1.2;
        }

        .replenishment-cell {
            background-color: white;
            vertical-align: middle;
            text-align: center !important;
        }

        .replenishment-content {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            width: 100%;
        }

        .replenishment-label {
            display: inline-block;
            font-size: 12px;
            color: #555;
            margin-right: 0;
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

        input[id^="replenishment_week_"] {
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

        .scenario-cell {
            font-weight: 600;
            text-align: center !important;
        }

        .ideal-scenario {
            color: #218838;
        }

        .acceptable-scenario {
            color: #dc3545;
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

        .send-controls {
            margin-top: 25px;
            text-align: center;
        }

        .notes-container {
            margin-top: 30px;
        }

        .notes-label {
            font-size: 15px;
            font-weight: 600;
            color: #555;
            margin-bottom: 8px;
        }

        .notes-container textarea {
            width: 100%;
            min-height: 110px;
            resize: vertical;
            border: 1px solid #d0d2d5;
            border-radius: 6px;
            padding: 10px;
            box-sizing: border-box;
            font-family: Arial, sans-serif;
            font-size: 14px;
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
        scenario,
        week
    ):

        return ui.input_text(

            f"{scenario}_week_{week}",

            None,

            value="",

            placeholder=""

        )


    # ========================================================
    # REPLENISHMENT WEEK INPUT
    # ========================================================

    def create_replenishment_week_input(
        scenario
    ):

        return ui.input_text(

            f"replenishment_week_{scenario}",

            None,

            value="",

            placeholder=""

        )


    # ========================================================
    # CREATE SCENARIO TABLE
    # ========================================================

    def create_scenario_table(
        country,
        scenario,
        scenario_class,
        scenario_label
    ):

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
                "Scenario"
            ),

            ui.tags.th(
                "DESTINATION"
            ),

            ui.tags.th(
                "DST"
            ),

            ui.tags.th(
                ui.HTML(
                    "Forecast<br>2027"
                )
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
                ui.HTML(
                    "Replenishment<br>week"
                ),
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
                        "month-header replenishment-header"
                }
            )

        )


        # ====================================================
        # QUANTITY ROW
        # ====================================================

        quantity_cells = [

            ui.tags.td(
                scenario_label,
                {
                    "class":
                        f"blocked-cell scenario-cell "
                        f"{scenario_class}"
                }
            ),

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
                        scenario,
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
                    f"{scenario}_total_quantity"
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

                ui.div(

                    {
                        "class":
                            "replenishment-content"
                    },

                    ui.span(
                        "Week",
                        {
                            "class":
                                "replenishment-label"
                        }
                    ),

                    create_replenishment_week_input(
                        scenario
                    )

                ),

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
            ),

            ui.tags.td(
                ""
            )

        ]


        for week in weeks:

            percentage_cells.append(

                ui.tags.td(

                    ui.output_text(
                        f"{scenario}_percent_{week}"
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


        return table


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


        ideal_table = create_scenario_table(
            country,
            "ideal",
            "ideal-scenario",
            "IDEAL"
        )


        acceptable_table = create_scenario_table(
            country,
            "acceptable",
            "acceptable-scenario",
            "ACCEPTABLE"
        )


        return ui.div(

            ui.div(

                {
                    "class":
                        "delivery-table-wrapper scenario-table"
                },

                ideal_table

            ),

            ui.div(

                {
                    "class":
                        "delivery-table-wrapper scenario-table"
                },

                acceptable_table

            ),

            ui.div(

                {
                    "class":
                        "notes-container"
                },

                ui.div(
                    {
                        "class":
                            "notes-label"
                    },

                    "Additional notes"
                ),

                ui.tags.textarea(
                    "",
                    {
                        "id":
                            "additional_notes",

                        "name":
                            "additional_notes",

                        "placeholder":
                            "Add any additional notes here..."
                    }
                )

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
    # TOTAL QUANTITY
    # ========================================================

    def make_total_renderer(
        scenario
    ):

        @output(
            id=f"{scenario}_total_quantity"
        )
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
                    f"{scenario}_week_{week}"
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


        return total_quantity


    make_total_renderer(
        "ideal"
    )

    make_total_renderer(
        "acceptable"
    )


    # ========================================================
    # PERCENTAGES
    # ========================================================

    def make_percentage_renderer(
        scenario,
        week
    ):

        @output(
            id=f"{scenario}_percent_{week}"
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
                    f"{scenario}_week_{w}"
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
                f"{scenario}_week_{week}"
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


    for scenario in [
        "ideal",
        "acceptable"
    ]:

        for week in range(
            1,
            54
        ):

            make_percentage_renderer(
                scenario,
                week
            )


    # ========================================================
    # AUTOMATIC ORD LIMIT
    # ========================================================

    def make_week_limiter(
        scenario,
        week
    ):

        @reactive.effect
        @reactive.event(
            lambda:
                getattr(
                    input,
                    f"{scenario}_week_{week}"
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
                f"{scenario}_week_{week}"
            )()

            if not current_value:

                return

            current_value = str(
                current_value
            ).strip()


            if not current_value.isdigit():

                return

            current_value = int(
                current_value
            )


            # ------------------------------------------------
            # OTHER WEEKS
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
                    f"{scenario}_week_{other_week}"
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


            remaining = (
                ord_value
                - other_total
            )

            remaining = max(
                0,
                remaining
            )


            if current_value > remaining:

                ui.update_text(
                    f"{scenario}_week_{week}",
                    value=str(
                        remaining
                    )
                )


        return limit_week


    for scenario in [
        "ideal",
        "acceptable"
    ]:

        for week in range(
            1,
            54
        ):

            make_week_limiter(
                scenario,
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
        # BUILD SCENARIO DATA
        # ====================================================

        all_output_rows = []

        scenario_vectors = []


        for scenario, scenario_label in [
            ("ideal", "IDEAL"),
            ("acceptable", "ACCEPTABLE")
        ]:

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


            # =================================================
            # REPLENISHMENT WEEK
            # =================================================

            replenishment_week = ""

            try:

                replenishment_week = getattr(
                    input,
                    f"replenishment_week_{scenario}"
                )()

            except Exception:

                replenishment_week = ""

            if replenishment_week is None:

                replenishment_week = ""

            replenishment_week = str(
                replenishment_week
            ).strip()


            for week in range(
                min_week,
                max_week + 1
            ):

                value = getattr(
                    input,
                    f"{scenario}_week_{week}"
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
                        f"{scenario_label}: "
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


            # =================================================
            # ORD CHECK
            # =================================================

            if (
                ord_value is not None
                and total > ord_value
            ):

                status_type.set(
                    "error"
                )

                status_message.set(
                    f"{scenario_label}: The total quantity "
                    f"cannot exceed the ORD value of "
                    f"{ord_value:,}."
                )

                return


            # =================================================
            # REQUIRE QUANTITY
            # =================================================

            if total <= 0:

                status_type.set(
                    "error"
                )

                status_message.set(
                    f"Please enter at least one quantity "
                    f"for the {scenario_label} scenario."
                )

                return


            # =================================================
            # BUILD OUTPUT
            # =================================================

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

                        "SCENARIO":
                            scenario_label,

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
                            f"{percentage:.0f}%",

                        "REPLENISHMENT_WEEK":
                            replenishment_week

                    }

                )


            scenario_df = pd.DataFrame(

                output_rows,

                columns=[
                    "SCENARIO",
                    "DST",
                    "DESTINATION",
                    "WEEK",
                    "qty",
                    "percent",
                    "REPLENISHMENT_WEEK"
                ]

            )


            all_output_rows.extend(
                output_rows
            )


            scenario_vectors.append(
                create_r_vector(
                    scenario_df
                )
            )


        # ====================================================
        # ADDITIONAL NOTES
        # ====================================================

        notes = ""

        try:

            notes = input.additional_notes()

        except Exception:

            notes = ""

        if notes is None:

            notes = ""

        notes = str(
            notes
        ).strip()


        # ====================================================
        # EMAIL
        # ====================================================

        subject = (
            "Delivery information - "
            f"{country['DESTINATION_NAME']}"
        )


        body_parts = [

            "Please see below the delivery information",

            "",

            "IDEAL scenario:",

            scenario_vectors[0],

            "",

            "ACCEPTABLE scenario:",

            scenario_vectors[1]

        ]


        if notes:

            body_parts.extend(

                [

                    "",

                    "Additional notes:",

                    notes

                ]

            )


        body = (
            "\n".join(
                body_parts
            )
            + "\n"
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
        # SEND URL TO BROWSER
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
