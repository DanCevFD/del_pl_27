from shiny import App, ui, render, reactive, Inputs, Outputs, Session
import pandas as pd
import re
from urllib.parse import quote
from datetime import date


# ============================================================
# CONFIGURATION
# ============================================================

APP_TITLE = "Delivery Information"

OWNER_EMAIL = "Stephan.Gilis@unitedbeetseeds.org"
SECOND_OWNER_EMAIL = "Danny.Cevallos@unitedbeetseeds.org"


# ============================================================
# LOAD DATA
# ============================================================

DATA_FILE = "items_week.csv"

df = pd.read_csv(DATA_FILE)

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
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing required columns in {DATA_FILE}: {missing_columns}"
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_month_for_week(week, country):
    """
    Return the month corresponding to a replenishment week.
    """

    try:
        week = int(week)
    except (ValueError, TypeError):
        return ""

    try:
        country_rows = df[df["DESTINATION_NAME"] == country]

        if country_rows.empty:
            return ""

        min_date = pd.to_datetime(
            country_rows.iloc[0]["min_date"]
        )

        max_date = pd.to_datetime(
            country_rows.iloc[0]["max_date"]
        )

        dates = pd.date_range(
            start=min_date,
            end=max_date,
            freq="D"
        )

        for d in dates:
            if d.isocalendar().week == week:
                return d.strftime("%B")

        return ""

    except Exception:
        return ""


def format_ord(value):

    if pd.isna(value):
        return "0"

    try:
        value = float(value)

        if value.is_integer():
            return str(int(value))

        return f"{value:g}"

    except Exception:
        return str(value)


def create_r_vector(submission_df):

    values = []

    for _, row in submission_df.iterrows():

        destination = row["DST"]

        for column in submission_df.columns:

            if column.startswith("week_"):

                value = row[column]

                if pd.notna(value) and str(value).strip() != "":

                    values.append(
                        f"{destination}:{column.replace('week_', '')}={value}"
                    )

    return "\n".join(values)


# ============================================================
# UI
# ============================================================

app_ui = ui.page_fluid(

    ui.tags.head(

        ui.tags.title(APP_TITLE),

        # ====================================================
        # OUTLOOK JAVASCRIPT
        # ====================================================

        ui.tags.script(
            """
            (function() {

                let outlookWindow = null;

                document.addEventListener(
                    "click",
                    function(event) {

                        const button =
                            event.target.closest("#send");

                        if (!button) return;

                        outlookWindow =
                            window.open(
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

                        if (!url) return;

                        if (
                            outlookWindow &&
                            !outlookWindow.closed
                        ) {

                            outlookWindow.location.href = url;
                            outlookWindow.focus();

                        } else {

                            window.location.href = url;

                        }

                    }
                );

            })();
            """
        ),

        # ====================================================
        # WEEK PICKER JAVASCRIPT
        # ====================================================

        ui.tags.script(
            """
            (function() {

                let picker = null;
                let displayedDate = new Date();

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

                    const d = new Date(date);

                    const day =
                        d.getDay();

                    const diff =
                        day === 0
                            ? -6
                            : 1 - day;

                    d.setDate(
                        d.getDate() + diff
                    );

                    return d;
                }


                function createPicker() {

                    if (picker) {
                        picker.remove();
                    }

                    picker =
                        document.createElement("div");

                    picker.id =
                        "custom-week-picker";

                    document.body.appendChild(
                        picker
                    );

                    renderPicker();
                }


                function renderPicker() {

                    if (!picker) return;

                    picker.innerHTML = "";

                    const year =
                        displayedDate.getFullYear();

                    const month =
                        displayedDate.getMonth();


                    // ==================================================
                    // HEADER
                    // ==================================================

                    const header =
                        document.createElement("div");

                    header.className =
                        "week-picker-header";


                    const previousButton =
                        document.createElement("button");

                    previousButton.type =
                        "button";

                    previousButton.innerHTML =
                        "‹";

                    previousButton.className =
                        "week-picker-nav";


                    previousButton.onclick =
                        function(event) {

                            event.preventDefault();
                            event.stopPropagation();

                            displayedDate.setMonth(
                                displayedDate.getMonth() - 1
                            );

                            renderPicker();
                        };


                    const monthYear =
                        document.createElement("div");

                    monthYear.className =
                        "week-picker-month-year";

                    monthYear.innerText =
                        displayedDate.toLocaleString(
                            "default",
                            {
                                month: "long",
                                year: "numeric"
                            }
                        );


                    const nextButton =
                        document.createElement("button");

                    nextButton.type =
                        "button";

                    nextButton.innerHTML =
                        "›";

                    nextButton.className =
                        "week-picker-nav";


                    nextButton.onclick =
                        function(event) {

                            event.preventDefault();
                            event.stopPropagation();

                            displayedDate.setMonth(
                                displayedDate.getMonth() + 1
                            );

                            renderPicker();
                        };


                    header.appendChild(
                        previousButton
                    );

                    header.appendChild(
                        monthYear
                    );

                    header.appendChild(
                        nextButton
                    );

                    picker.appendChild(
                        header
                    );


                    // ==================================================
                    // WEEK LIST
                    // ==================================================

                    const weeksContainer =
                        document.createElement("div");

                    weeksContainer.className =
                        "week-picker-weeks";


                    const firstDay =
                        new Date(
                            year,
                            month,
                            1
                        );

                    const lastDay =
                        new Date(
                            year,
                            month + 1,
                            0
                        );


                    let monday =
                        getMonday(firstDay);


                    /*
                        If the Monday belongs to the previous
                        month, move to the first Monday that is
                        actually inside this displayed month.
                    */

                    if (
                        monday.getMonth() !== month
                    ) {

                        monday.setDate(
                            monday.getDate() + 7
                        );

                    }


                    while (
                        monday <= lastDay
                    ) {

                        if (
                            monday.getMonth() !== month
                        ) {
                            break;
                        }


                        const week =
                            getISOWeek(monday);


                        const weekButton =
                            document.createElement("button");

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

                                const input =
                                    document.getElementById(
                                        "replenishment_week"
                                    );

                                if (input) {

                                    input.value =
                                        week;

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
                                            priority: "event"
                                        }
                                    );
                                }

                                picker.remove();
                                picker = null;
                            };


                        weeksContainer.appendChild(
                            weekButton
                        );


                        monday.setDate(
                            monday.getDate() + 7
                        );
                    }


                    picker.appendChild(
                        weeksContainer
                    );
                }


                // ======================================================
                // OPEN PICKER
                // ======================================================

                document.addEventListener(
                    "click",
                    function(event) {

                        const input =
                            event.target.closest(
                                "#replenishment_week"
                            );

                        if (!input) return;

                        event.preventDefault();
                        event.stopPropagation();


                        if (
                            picker &&
                            picker.parentNode
                        ) {

                            picker.remove();
                            picker = null;

                            return;
                        }


                        const rect =
                            input.getBoundingClientRect();


                        const currentValue =
                            parseInt(
                                input.value
                            );


                        if (
                            !isNaN(currentValue)
                        ) {

                            /*
                                Start from the current year.
                                The month picker can then be
                                navigated with ‹ and ›.
                            */

                            displayedDate =
                                new Date(
                                    new Date().getFullYear(),
                                    new Date().getMonth(),
                                    1
                                );

                        } else {

                            displayedDate =
                                new Date(
                                    new Date().getFullYear(),
                                    new Date().getMonth(),
                                    1
                                );
                        }


                        createPicker();


                        picker.style.left =
                            (
                                rect.left +
                                window.scrollX
                            ) + "px";

                        picker.style.top =
                            (
                                rect.bottom +
                                window.scrollY +
                                4
                            ) + "px";
                    },
                    true
                );


                // ======================================================
                // CLOSE WHEN CLICKING OUTSIDE
                // ======================================================

                document.addEventListener(
                    "click",
                    function(event) {

                        if (!picker) return;

                        if (
                            !event.target.closest(
                                "#custom-week-picker"
                            ) &&
                            !event.target.closest(
                                "#replenishment_week"
                            )
                        ) {

                            picker.remove();
                            picker = null;
                        }
                    }
                );


                // ======================================================
                // KEEP PICKER POSITIONED
                // ======================================================

                window.addEventListener(
                    "resize",
                    function() {

                        const input =
                            document.getElementById(
                                "replenishment_week"
                            );

                        if (
                            !picker ||
                            !input
                        ) return;

                        const rect =
                            input.getBoundingClientRect();

                        picker.style.left =
                            (
                                rect.left +
                                window.scrollX
                            ) + "px";

                        picker.style.top =
                            (
                                rect.bottom +
                                window.scrollY +
                                4
                            ) + "px";
                    }
                );


                window.addEventListener(
                    "scroll",
                    function() {

                        const input =
                            document.getElementById(
                                "replenishment_week"
                            );

                        if (
                            !picker ||
                            !input
                        ) return;

                        const rect =
                            input.getBoundingClientRect();

                        picker.style.left =
                            (
                                rect.left +
                                window.scrollX
                            ) + "px";

                        picker.style.top =
                            (
                                rect.bottom +
                                window.scrollY +
                                4
                            ) + "px";
                    }
                );

            })();
            """
        ),

        # ====================================================
        # CSS
        # ====================================================

        ui.tags.style(
            """

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
                box-shadow:
                    0 4px 20px
                    rgba(0,0,0,0.08);
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

            /* ======================================================
               TABLE
               ====================================================== */

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

            /*
                IMPORTANT:

                Week columns are the normal delivery-week columns.
                The LAST column is explicitly reserved for
                Replenishment week.
            */

            .delivery-table th:nth-child(n+4),
            .delivery-table td:nth-child(n+4) {
                width: 65px;
                min-width: 65px;
                max-width: 65px;
            }

            /* ======================================================
               REPLENISHMENT WEEK COLUMN
               ====================================================== */

            .delivery-table th.replenishment-header,
            .delivery-table td.replenishment-cell {
                width: 155px !important;
                min-width: 155px !important;
                max-width: 155px !important;
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

            /* ======================================================
               OTHER TABLE STYLING
               ====================================================== */

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

            /* ======================================================
               SEND BUTTON
               ====================================================== */

            .send-controls {
                margin-top: 12px;
                text-align: right;
            }

            /* ======================================================
               STATUS
               ====================================================== */

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

            /* ======================================================
               WEEK PICKER
               ====================================================== */

            #custom-week-picker {
                position: absolute;
                background: white;
                border: 1px solid #d0d2d5;
                border-radius: 6px;
                box-shadow:
                    0 4px 15px
                    rgba(0,0,0,0.15);
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

            .week-picker-month-year {
                font-weight: 600;
                text-align: center;
                flex: 1;
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

            """
        )
    ),

    # ========================================================
    # MAIN CONTAINER
    # ========================================================

    ui.div(

        {"class": "main-container"},

        ui.div(
            APP_TITLE,
            {"class": "title"}
        ),

        ui.div(
            "Select a country and enter the delivery quantities.",
            {"class": "subtitle"}
        ),

        ui.output_ui("country_selector"),

        ui.output_ui("delivery_table"),

        ui.output_ui("status")
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

    input_enabled = reactive.Value(False)

    current_country = reactive.Value(None)

    status_message = reactive.Value(None)

    status_type = reactive.Value(None)


    # ========================================================
    # COUNTRY SELECTOR
    # ========================================================

    @output
    @render.ui
    def country_selector():

        choices = {
            ""
            : ""
        }

        for country in sorted(
            df["DESTINATION_NAME"]
            .dropna()
            .unique()
        ):

            choices[country] = country


        return ui.div(

            {"class": "country-selector-container"},

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
    # QUANTITY INPUT
    # ========================================================

    def create_quantity_input(week):

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

        country =
            input.destination()

        if not country:

            return ui.div()


        country_rows =
            df[
                df["DESTINATION_NAME"] == country
            ].copy()


        if country_rows.empty:

            return ui.div()


        min_week =
            int(
                country_rows["min_week"].min()
            )

        max_week =
            int(
                country_rows["max_week"].max()
            )


        weeks =
            list(
                range(
                    min_week,
                    max_week + 1
                )
            )


        # ====================================================
        # HEADER ROW
        # ====================================================

        header_cells = [

            ui.tags.th("DESTINATION"),

            ui.tags.th("DST"),

            ui.tags.th("ord")
        ]


        for week in weeks:

            header_cells.append(

                ui.tags.th(
                    f"W{week}"
                )
            )


        # ----------------------------------------------------
        # TOTAL
        # ----------------------------------------------------

        header_cells.append(

            ui.tags.th(
                "Total"
            )
        )


        # ----------------------------------------------------
        # NEW COLUMN: REPLENISHMENT WEEK
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


        header_row =
            ui.tags.tr(
                *header_cells
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


        previous_month = None


        for week in weeks:

            month =
                get_month_for_week(
                    week,
                    country
                )


            if month != previous_month:

                month_row.append(

                    ui.tags.th(
                        month,
                        {
                            "class":
                                "month-header"
                        }
                    )
                )

                previous_month = month

            else:

                month_row.append(

                    ui.tags.th(
                        "",
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


        # Replenishment month cell

        month_row.append(

            ui.tags.th(
                "",
                {
                    "class":
                        "month-header replenishment-header"
                }
            )
        )


        month_table_row =
            ui.tags.tr(
                *month_row
            )


        # ====================================================
        # QUANTITY ROW
        # ====================================================

        quantity_cells = [

            ui.tags.td(
                country
            ),

            ui.tags.td(
                country_rows.iloc[0]["DST"]
            ),

            ui.tags.td(
                format_ord(
                    country_rows.iloc[0]["ord"]
                ),
                {
                    "class":
                        "ord-cell"
                }
            )
        ]


        # ----------------------------------------------------
        # WEEK CELLS
        # ----------------------------------------------------

        for week in weeks:

            quantity_cells.append(

                ui.tags.td(

                    create_quantity_input(
                        week
                    )
                )
            )


        # ----------------------------------------------------
        # TOTAL CELL
        # ----------------------------------------------------

        quantity_cells.append(

            ui.tags.td(
                "0",
                {
                    "class":
                        "total-cell"
                }
            )
        )


        # ----------------------------------------------------
        # REPLENISHMENT WEEK CELL
        #
        # THIS IS A REAL TABLE CELL.
        # It is the column immediately after Total.
        # ----------------------------------------------------

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


        quantity_row =
            ui.tags.tr(
                *quantity_cells
            )


        # ====================================================
        # PERCENTAGE ROW
        # ====================================================

        percentage_cells = [

            ui.tags.td(""),

            ui.tags.td(""),

            ui.tags.td("")
        ]


        for week in weeks:

            percentage_cells.append(

                ui.tags.td(
                    "",
                    {
                        "class":
                            "percentage-row"
                    }
                )
            )


        percentage_cells.append(

            ui.tags.td(
                "",
                {
                    "class":
                        "percentage-row"
                }
            )
        )


        # ----------------------------------------------------
        # REPLENISHMENT WEEK PERCENTAGE CELL
        # ----------------------------------------------------

        percentage_cells.append(

            ui.tags.td(
                "",
                {
                    "class":
                        "replenishment-cell percentage-row"
                }
            )
        )


        percentage_row =
            ui.tags.tr(
                {
                    "class":
                        "percentage-row"
                },

                *percentage_cells
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

                header_row,

                month_table_row
            ),

            ui.tags.tbody(

                quantity_row,

                percentage_row
            )
        )


        # ====================================================
        # RETURN TABLE + SEND BELOW IT
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
    # STATUS
    # ========================================================

    @output
    @render.ui
    def status():

        message =
            status_message()

        if not message:

            return ui.div()


        if status_type() == "success":

            return ui.div(

                message,

                {
                    "class":
                        "success-box"
                }
            )


        return ui.div(

            message,

            {
                "class":
                    "error-box"
            }
        )


    # ========================================================
    # PROCESS SUBMISSION
    # ========================================================

    @reactive.effect
    @reactive.event(input.send)
    def process_submission():

        country =
            input.destination()

        if not country:

            status_message.set(
                "Please select a country."
            )

            status_type.set(
                "error"
            )

            return


        replenishment_week =
            input.replenishment_week()


        if (
            replenishment_week is None
            or
            str(replenishment_week).strip() == ""
        ):

            status_message.set(
                "Please select a replenishment week."
            )

            status_type.set(
                "error"
            )

            return


        country_rows =
            df[
                df["DESTINATION_NAME"] == country
            ].copy()


        if country_rows.empty:

            status_message.set(
                "No data found for the selected country."
            )

            status_type.set(
                "error"
            )

            return


        min_week =
            int(
                country_rows["min_week"].min()
            )

        max_week =
            int(
                country_rows["max_week"].max()
            )


        weeks =
            list(
                range(
                    min_week,
                    max_week + 1
                )
            )


        # ====================================================
        # BUILD SUBMISSION DATAFRAME
        # ====================================================

        submission_data = {

            "DESTINATION": [
                country
            ],

            "DST": [
                country_rows.iloc[0]["DST"]
            ],

            "ord": [
                country_rows.iloc[0]["ord"]
            ]
        }


        for week in weeks:

            value =
                input[
                    f"week_{week}"
                ]()


            submission_data[
                f"week_{week}"
            ] = [value]


        submission_df =
            pd.DataFrame(
                submission_data
            )


        # ====================================================
        # R VECTOR
        # ====================================================

        r_vector =
            create_r_vector(
                submission_df
            )


        # ====================================================
        # EMAIL BODY
        # ====================================================

        body = (

            "Please see below the delivery information\n"

            "\n"

            f"Replenishment week: "
            f"{replenishment_week}\n"

            "\n"

            f"{r_vector}\n"
        )


        subject =
            f"Delivery Information - {country}"


        # ====================================================
        # OUTLOOK URL
        # ====================================================

        url = (

            "mailto:"
            + OWNER_EMAIL

            + "?cc="
            + quote(SECOND_OWNER_EMAIL)

            + "&subject="
            + quote(subject)

            + "&body="
            + quote(body)
        )


        session.send_custom_message(

            "open_outlook",

            {
                "url":
                    url
            }
        )


        status_message.set(
            "The delivery information has been prepared in Outlook."
        )

        status_type.set(
            "success"
        )


# ============================================================
# APP
# ============================================================

app = App(
    app_ui,
    server
)
