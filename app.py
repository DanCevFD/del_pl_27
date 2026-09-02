from shiny import App, ui, render, reactive, Inputs, Outputs, Session
import pandas as pd
import re
from urllib.parse import quote
from datetime import date, timedelta


# ============================================================
# CONFIGURATION
# ============================================================

APP_TITLE = "Delivery Information"

OWNER_EMAIL = "Stephan.Gilis@unitedbeetseeds.org"
SECOND_OWNER_EMAIL = "Danny.Cevallos@unitedbeetseeds.org"


# ============================================================
# LOAD DATA
# ============================================================

try:
    df = pd.read_csv("items_week.csv")
except Exception as e:
    raise RuntimeError(f"Could not load items_week.csv: {e}")


df.columns = df.columns.str.strip()


required_columns = [
    "DST",
    "min_date",
    "max_date",
    "min_week",
    "max_week",
    "DESTINATION_NAME",
    "ord",
]


missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        "The following required columns are missing from "
        f"items_week.csv: {missing_columns}"
    )


# ============================================================
# CLEAN DATA
# ============================================================

df["DESTINATION_NAME"] = (
    df["DESTINATION_NAME"]
    .astype(str)
    .str.strip()
)

df["DST"] = (
    df["DST"]
    .astype(str)
    .str.strip()
)

df["min_date"] = pd.to_datetime(
    df["min_date"],
    errors="coerce"
)

df["max_date"] = pd.to_datetime(
    df["max_date"],
    errors="coerce"
)

df["min_week"] = pd.to_numeric(
    df["min_week"],
    errors="coerce"
)

df["max_week"] = pd.to_numeric(
    df["max_week"],
    errors="coerce"
)

df["ord"] = pd.to_numeric(
    df["ord"],
    errors="coerce"
).fillna(0)

df = df[
    df["DESTINATION_NAME"].notna()
    & (df["DESTINATION_NAME"] != "")
].copy()


# Keep one row per destination
country_df = (
    df
    .drop_duplicates(subset=["DESTINATION_NAME"])
    .copy()
)


destinations = sorted(
    country_df["DESTINATION_NAME"].tolist()
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_month_for_week(week, country):
    """
    Determine the month associated with a week for a country.
    """

    row = country_df[
        country_df["DESTINATION_NAME"] == country
    ]

    if row.empty:
        return ""

    row = row.iloc[0]

    min_date = row["min_date"]

    if pd.isna(min_date):
        return ""

    try:
        min_date = min_date.date()
    except Exception:
        pass

    try:
        week = int(week)
    except Exception:
        return ""

    monday = (
        min_date
        - timedelta(days=min_date.weekday())
        + timedelta(weeks=week - int(row["min_week"]))
    )

    return monday.strftime("%B")


def format_ord(value):
    try:
        value = float(value)

        if value.is_integer():
            return str(int(value))

        return f"{value:,.0f}"

    except Exception:
        return "0"


def create_r_vector(values):
    """
    Create an R vector string.
    """

    if not values:
        return "c()"

    formatted = []

    for value in values:
        formatted.append(str(value))

    max_len = max(
        len(x)
        for x in formatted
    )

    return (
        "c(\n    "
        + ",\n    ".join(
            x.ljust(max_len)
            for x in formatted
        )
        + "\n)"
    )


# ============================================================
# CALENDAR LIMITS
# ============================================================

today = date.today()

current_week_start = (
    today
    - timedelta(days=today.weekday())
)

next_year_end = date(
    today.year + 1,
    12,
    31
)


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
            var outlookWindow = null;

            $(document).on("click", "#send", function() {

                if (
                    outlookWindow === null ||
                    outlookWindow.closed
                ) {

                    outlookWindow = window.open(
                        "about:blank",
                        "outlookCompose",
                        "width=1200,height=900"
                    );

                }

            });

            Shiny.addCustomMessageHandler(
                "open_outlook",
                function(message) {

                    if (
                        outlookWindow === null ||
                        outlookWindow.closed
                    ) {

                        outlookWindow = window.open(
                            "about:blank",
                            "outlookCompose",
                            "width=1200,height=900"
                        );

                    }

                    outlookWindow.location.href =
                        message.url;

                    outlookWindow.focus();

                }
            );
            """
        ),


        # ====================================================
        # CUSTOM WEEK PICKER
        # ====================================================

        ui.tags.script(
            """
            (function() {

                let picker = null;
                let currentMonth = null;
                let currentYear = null;


                // ------------------------------------------------
                // ISO WEEK NUMBER
                // ------------------------------------------------

                function getISOWeek(dateObj) {

                    const d = new Date(
                        Date.UTC(
                            dateObj.getFullYear(),
                            dateObj.getMonth(),
                            dateObj.getDate()
                        )
                    );

                    const dayNum =
                        d.getUTCDay() || 7;

                    d.setUTCDate(
                        d.getUTCDate()
                        + 4
                        - dayNum
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


                // ------------------------------------------------
                // MONDAY OF ISO WEEK
                // ------------------------------------------------

                function getMonday(dateObj) {

                    const d =
                        new Date(dateObj);

                    const day =
                        d.getDay();

                    const difference =
                        day === 0
                            ? -6
                            : 1 - day;

                    d.setDate(
                        d.getDate()
                        + difference
                    );

                    d.setHours(
                        0, 0, 0, 0
                    );

                    return d;

                }


                // ------------------------------------------------
                // CREATE PICKER
                // ------------------------------------------------

                function createPicker() {

                    if (picker) {
                        return;
                    }

                    picker = $(
                        "<div id='custom-week-picker'></div>"
                    );

                    picker.css({

                        position: "absolute",

                        background: "#ffffff",

                        border: "1px solid #ccc",

                        borderRadius: "4px",

                        boxShadow:
                            "0 4px 12px rgba(0,0,0,0.15)",

                        padding: "10px",

                        width: "230px",

                        zIndex: "99999",

                        display: "none"

                    });

                    $("body").append(
                        picker
                    );


                    // ------------------------------------------------
                    // PREVENT CLICK FROM CLOSING PICKER
                    // ------------------------------------------------

                    picker.on(
                        "mousedown",
                        function(event) {

                            event.stopPropagation();

                        }
                    );

                }


                // ------------------------------------------------
                // POSITION PICKER
                // ------------------------------------------------

                function positionPicker() {

                    const input =
                        $("#replenishment_week");

                    if (
                        !input.length ||
                        !picker
                    ) {
                        return;
                    }

                    const offset =
                        input.offset();

                    const height =
                        input.outerHeight();

                    picker.css({

                        top:
                            offset.top
                            + height
                            + 4,

                        left:
                            offset.left

                    });

                }


                // ------------------------------------------------
                // DRAW PICKER
                // ------------------------------------------------

                function drawPicker() {

                    if (!picker) {
                        createPicker();
                    }

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


                    // ------------------------------------------------
                    // HEADER
                    // ------------------------------------------------

                    let html = "";

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
                    // WEEK LIST
                    // ------------------------------------------------

                    html +=
                        "<div class='week-picker-label'>" +
                        "Week" +
                        "</div>";

                    html +=
                        "<div class='week-picker-weeks'>";


                    /*
                        Only show Mondays that belong to the
                        selected month.

                        Therefore January 2027 gives:

                        Week 1
                        Week 2
                        Week 3
                        Week 4

                        because the Mondays are:

                        Jan 4
                        Jan 11
                        Jan 18
                        Jan 25
                    */

                    const daysInMonth =
                        new Date(
                            currentYear,
                            currentMonth + 1,
                            0
                        ).getDate();


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
                            "data-week='"
                            + week
                            + "' " +
                            "data-date='"
                            + d.getTime()
                            + "'>" +
                            week +
                            "</button>";

                    }


                    html +=
                        "</div>";


                    picker.html(
                        html
                    );


                    // ------------------------------------------------
                    // PREVIOUS MONTH
                    // ------------------------------------------------

                    picker.find(
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

                            drawPicker();

                        }
                    );


                    // ------------------------------------------------
                    // NEXT MONTH
                    // ------------------------------------------------

                    picker.find(
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

                            drawPicker();

                        }
                    );


                    // ------------------------------------------------
                    // WEEK SELECTION
                    // ------------------------------------------------

                    picker.find(
                        ".week-number-button"
                    ).on(
                        "click",
                        function(event) {

                            event.preventDefault();
                            event.stopPropagation();

                            const week =
                                $(this)
                                .data("week");

                            const dateValue =
                                $(this)
                                .data("date");

                            const selectedDate =
                                new Date(
                                    Number(dateValue)
                                );


                            // ----------------------------------------
                            // Put WEEK NUMBER into visible input
                            // ----------------------------------------

                            const input =
                                $("#replenishment_week");

                            input.val(
                                String(week)
                            );


                            // ----------------------------------------
                            // Store useful internal date
                            // ----------------------------------------

                            input.attr(
                                "data-week",
                                String(week)
                            );

                            input.attr(
                                "data-week-date",
                                selectedDate
                                .toISOString()
                            );


                            // ----------------------------------------
                            // Tell Shiny that the value changed
                            // ----------------------------------------

                            input.trigger(
                                "change"
                            );

                            input.trigger(
                                "input"
                            );


                            // Shiny update
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


                            // ----------------------------------------
                            // Close picker
                            // ----------------------------------------

                            picker.hide();

                        }
                    );


                    positionPicker();

                }


                // ------------------------------------------------
                // OPEN PICKER
                // ------------------------------------------------

                function openPicker() {

                    const input =
                        $("#replenishment_week");

                    if (!input.length) {
                        return;
                    }

                    createPicker();


                    // If a month has not been selected yet,
                    // use the current month.

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


                    drawPicker();

                    positionPicker();

                    picker.show();

                }


                // ------------------------------------------------
                // INPUT CLICK
                // ------------------------------------------------

                $(document).on(
                    "click",
                    "#replenishment_week",
                    function(event) {

                        event.preventDefault();
                        event.stopPropagation();

                        openPicker();

                    }
                );


                // ------------------------------------------------
                // PREVENT ORIGINAL DATEPICKER
                // ------------------------------------------------

                $(document).on(
                    "focus",
                    "#replenishment_week",
                    function() {

                        // Remove Bootstrap datepicker if
                        // Shiny attached one.

                        const input =
                            $(this);

                        const datepicker =
                            input.data(
                                "datepicker"
                            );

                        if (datepicker) {

                            try {

                                datepicker.hide();

                            }
                            catch(e) {}

                        }

                    }
                );


                // ------------------------------------------------
                // CLOSE WHEN CLICKING OUTSIDE
                // ------------------------------------------------

                $(document).on(
                    "mousedown",
                    function(event) {

                        if (!picker) {
                            return;
                        }

                        if (
                            picker.is(":visible") &&
                            !$(event.target)
                                .closest(
                                    "#custom-week-picker"
                                ).length &&
                            !$(event.target)
                                .closest(
                                    "#replenishment_week"
                                ).length
                        ) {

                            picker.hide();

                        }

                    }
                );


                // ------------------------------------------------
                // KEEP POSITION CORRECT
                // ------------------------------------------------

                $(window).on(
                    "resize scroll",
                    function() {

                        if (
                            picker &&
                            picker.is(":visible")
                        ) {

                            positionPicker();

                        }

                    }
                );


                // ------------------------------------------------
                // SHINY CAN REBUILD THE INPUT
                // ------------------------------------------------

                $(document).on(
                    "shiny:value",
                    function() {

                        setTimeout(
                            function() {

                                const input =
                                    $("#replenishment_week");

                                if (
                                    input.length
                                ) {

                                    input.attr(
                                        "autocomplete",
                                        "off"
                                    );

                                }

                            },
                            100
                        );

                    }
                );


            })();
            """
        ),


        # ====================================================
        # CUSTOM WEEK PICKER CSS
        # ====================================================

        ui.tags.style(
            """

            #custom-week-picker {

                font-family:
                    Arial,
                    Helvetica,
                    sans-serif;

            }


            .week-picker-header {

                display: flex;

                align-items: center;

                justify-content: space-between;

                margin-bottom: 10px;

            }


            .week-picker-title {

                font-weight: 600;

                font-size: 15px;

                text-align: center;

                flex: 1;

            }


            .week-picker-prev,
            .week-picker-next {

                border: none;

                background: transparent;

                font-size: 25px;

                line-height: 25px;

                cursor: pointer;

                width: 35px;

                height: 30px;

                padding: 0;

            }


            .week-picker-prev:hover,
            .week-picker-next:hover {

                background: #f0f0f0;

                border-radius: 4px;

            }


            .week-picker-label {

                text-align: center;

                font-size: 12px;

                font-weight: 600;

                color: #777;

                border-bottom:
                    1px solid #ddd;

                padding-bottom: 6px;

                margin-bottom: 6px;

            }


            .week-picker-weeks {

                display: flex;

                flex-direction: column;

                gap: 5px;

            }


            .week-number-button {

                width: 100%;

                height: 34px;

                border: 1px solid #ddd;

                border-radius: 4px;

                background: #fff;

                font-size: 14px;

                cursor: pointer;

            }


            .week-number-button:hover {

                background: #f0f0f0;

                border-color: #999;

            }


            #replenishment_week {

                text-align: center;

                cursor: pointer;

                background-color: #fff;

            }

            """
        ),


        # ====================================================
        # GENERAL CSS
        # ====================================================

        ui.tags.style(
            """

            .datepicker {

                z-index: 9999 !important;

            }


            body {

                font-family:
                    Arial,
                    Helvetica,
                    sans-serif;

            }


            .main-container {

                max-width: 1200px;

                margin: 0 auto;

                padding: 30px;

            }


            .app-title {

                font-size: 28px;

                font-weight: 600;

                margin-bottom: 5px;

            }


            .app-subtitle {

                color: #666;

                margin-bottom: 25px;

            }


            .delivery-table {

                margin-top: 25px;

                overflow-x: auto;

            }


            .delivery-table table {

                border-collapse: collapse;

                width: 100%;

            }


            .delivery-table th,
            .delivery-table td {

                border:
                    1px solid #ddd;

                padding: 6px;

                text-align: center;

            }


            .delivery-table th {

                background-color: #f5f5f5;

                font-weight: 600;

            }


            .delivery-table input {

                text-align: center;

            }


            .month-row {

                background-color: #f8f8f8;

                font-weight: 600;

            }


            .total-row {

                font-weight: 600;

                background-color: #f5f5f5;

            }


            .percent-row {

                font-size: 12px;

                color: #666;

            }


            .status-success {

                margin-top: 15px;

                padding: 10px;

                border-radius: 4px;

                background-color: #e8f5e9;

                color: #2e7d32;

            }


            .status-error {

                margin-top: 15px;

                padding: 10px;

                border-radius: 4px;

                background-color: #ffebee;

                color: #c62828;

            }

            """
        )

    ),


    # ========================================================
    # MAIN PAGE
    # ========================================================

    ui.div(

        {"class": "main-container"},

        ui.div(
            {"class": "app-title"},
            APP_TITLE
        ),

        ui.div(
            {
                "class":
                    "app-subtitle"
            },
            "Please enter the delivery information."
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
    # REACTIVE VALUES
    # ========================================================

    input_enabled = reactive.Value(False)

    current_country = reactive.Value(None)

    status_message = reactive.Value("")

    status_type = reactive.Value("")


    # ========================================================
    # START BUTTON
    # ========================================================

    @reactive.effect
    @reactive.event(input.start_input)
    def _():

        input_enabled.set(True)

        current_country.set(None)

        status_message.set("")

        status_type.set("")


    # ========================================================
    # COUNTRY SELECTOR
    # ========================================================

    @output
    @render.ui
    def country_selector():

        if not input_enabled.get():

            return ui.div()

        return ui.div(

            {
                "style":
                    "margin-top:20px;"
            },

            ui.input_selectize(
                "destination",
                "Country",
                choices={
                    "": ""
                }
                | {
                    x: x
                    for x in destinations
                },
                selected="",
                multiple=False,
                options={
                    "placeholder":
                        "Search for a country...",
                    "allowEmptyOption":
                        True
                },
                width="300px"
            )

        )


    # ========================================================
    # COUNTRY CHANGE
    # ========================================================

    @reactive.effect
    def _country_change():

        country = input.destination()

        if (
            country
            and country != ""
        ):

            current_country.set(
                country
            )

        else:

            current_country.set(
                None
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

        # This remains an input_text rather than input_date.
        #
        # The JavaScript above provides the custom calendar.
        #
        # The value shown to the user is simply:
        #
        #       1
        #       2
        #       3
        #       4
        #
        # etc.

        return ui.input_text(
            "replenishment_week",
            None,
            value="",
            placeholder="Week",
            width="70px"
        )


    # ========================================================
    # DELIVERY TABLE
    # ========================================================

    @output
    @render.ui
    def delivery_table():

        country = current_country.get()

        if not country:

            return ui.div()

        row = country_df[
            country_df["DESTINATION_NAME"]
            == country
        ]

        if row.empty:

            return ui.div()

        row = row.iloc[0]

        min_week = row["min_week"]
        max_week = row["max_week"]

        try:
            min_week = int(min_week)
        except Exception:
            min_week = 1

        try:
            max_week = int(max_week)
        except Exception:
            max_week = 52

        weeks = list(
            range(
                min_week,
                max_week + 1
            )
        )


        # ====================================================
        # MONTH ROW
        # ====================================================

        month_cells = []

        previous_month = None

        for week in weeks:

            month = get_month_for_week(
                week,
                country
            )

            if month != previous_month:

                month_cells.append(
                    ui.tags.td(
                        month,
                        colspan=1,
                        class_="month-row"
                    )
                )

                previous_month = month

            else:

                month_cells.append(
                    ui.tags.td(
                        "",
                        class_="month-row"
                    )
                )


        # ====================================================
        # WEEK HEADER
        # ====================================================

        week_headers = []

        for week in weeks:

            week_headers.append(
                ui.tags.th(
                    f"W{week}"
                )
            )


        # ====================================================
        # QUANTITY CELLS
        # ====================================================

        quantity_cells = []

        for week in weeks:

            quantity_cells.append(
                ui.tags.td(
                    create_quantity_input(
                        week
                    )
                )
            )


        # ====================================================
        # TOTAL ROW
        # ====================================================

        total_cells = []

        for week in weeks:

            total_cells.append(
                ui.tags.td(
                    ui.output_text(
                        f"total_week_{week}"
                    )
                )
            )


        # ====================================================
        # REPLENISHMENT WEEK
        # ====================================================

        replenishment_cells = [
            ui.tags.td(
                "Replenishment week"
            )
        ]

        replenishment_cells.append(
            ui.tags.td(
                create_replenishment_week_input(),
                colspan=max(
                    1,
                    len(weeks) - 1
                )
            )
        )


        # ====================================================
        # PERCENTAGE ROW
        # ====================================================

        percent_cells = []

        for week in weeks:

            percent_cells.append(
                ui.tags.td(
                    ui.output_text(
                        f"percent_week_{week}"
                    )
                )
            )


        return ui.div(

            {
                "class":
                    "delivery-table"
            },

            ui.tags.table(

                ui.tags.thead(

                    ui.tags.tr(
                        *month_cells
                    ),

                    ui.tags.tr(
                        *week_headers
                    )

                ),

                ui.tags.tbody(

                    ui.tags.tr(
                        *quantity_cells
                    ),

                    ui.tags.tr(
                        *total_cells,
                        class_="total-row"
                    ),

                    ui.tags.tr(
                        *replenishment_cells
                    ),

                    ui.tags.tr(
                        *percent_cells,
                        class_="percent-row"
                    )

                )

            ),

            ui.div(
                {
                    "style":
                        "margin-top:20px;"
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
    def total():

        country = current_country.get()

        if not country:
            return ""

        row = country_df[
            country_df["DESTINATION_NAME"]
            == country
        ]

        if row.empty:
            return ""

        ord_value = row.iloc[0]["ord"]

        return format_ord(
            ord_value
        )


    # ========================================================
    # WEEK TOTAL OUTPUTS
    # ========================================================

    for week in range(1, 54):

        def make_total_output(w):

            @output(id=f"total_week_{w}")
            @render.text
            def total_week():

                value = input[
                    f"week_{w}"
                ]()

                if (
                    value is None
                    or value == ""
                ):
                    return ""

                try:
                    return str(
                        int(
                            float(value)
                        )
                    )

                except Exception:
                    return ""

            return total_week


        make_total_output(week)


    # ========================================================
    # PERCENTAGE OUTPUTS
    # ========================================================

    for week in range(1, 54):

        def make_percent_output(w):

            @output(id=f"percent_week_{w}")
            @render.text
            def percent_week():

                country = (
                    current_country.get()
                )

                if not country:
                    return ""

                row = country_df[
                    country_df[
                        "DESTINATION_NAME"
                    ] == country
                ]

                if row.empty:
                    return ""

                ord_value = float(
                    row.iloc[0]["ord"]
                )

                if ord_value == 0:
                    return ""

                value = input[
                    f"week_{w}"
                ]()

                if (
                    value is None
                    or value == ""
                ):
                    return ""

                try:

                    qty = float(value)

                    pct = (
                        qty
                        / ord_value
                        * 100
                    )

                    return f"{pct:.1f}%"

                except Exception:

                    return ""

            return percent_week


        make_percent_output(week)


    # ========================================================
    # WEEK LIMITERS
    # ========================================================

    @reactive.effect
    def _limit_week_inputs():

        country = current_country.get()

        if not country:
            return

        row = country_df[
            country_df[
                "DESTINATION_NAME"
            ] == country
        ]

        if row.empty:
            return

        ord_value = float(
            row.iloc[0]["ord"]
        )

        for week in range(1, 54):

            try:

                current_value = input[
                    f"week_{week}"
                ]()

            except Exception:

                continue

            if (
                current_value is None
                or current_value == ""
            ):
                continue

            try:

                current_qty = int(
                    float(current_value)
                )

            except Exception:

                continue

            other_total = 0

            for other_week in range(1, 54):

                if (
                    other_week
                    == week
                ):
                    continue

                try:

                    other_value = input[
                        f"week_{other_week}"
                    ]()

                    if (
                        other_value is not None
                        and other_value != ""
                    ):

                        other_total += int(
                            float(
                                other_value
                            )
                        )

                except Exception:

                    pass

            remaining = max(
                0,
                int(ord_value)
                - other_total
            )

            if current_qty > remaining:

                ui.update_text(
                    f"week_{week}",
                    value=str(
                        remaining
                    ),
                    session=session
                )


    # ========================================================
    # STATUS
    # ========================================================

    @output
    @render.ui
    def status():

        message = (
            status_message.get()
        )

        if not message:
            return ui.div()

        if (
            status_type.get()
            == "success"
        ):

            return ui.div(
                {
                    "class":
                        "status-success"
                },
                message
            )

        return ui.div(
            {
                "class":
                    "status-error"
            },
            message
        )


    # ========================================================
    # SEND
    # ========================================================

    @reactive.effect
    @reactive.event(input.send)
    def _send():

        country = (
            current_country.get()
        )

        if not country:

            status_message.set(
                "Please select a country."
            )

            status_type.set(
                "error"
            )

            return


        # ====================================================
        # COUNTRY ROW
        # ====================================================

        row = country_df[
            country_df[
                "DESTINATION_NAME"
            ] == country
        ]

        if row.empty:

            status_message.set(
                "Country information could not be found."
            )

            status_type.set(
                "error"
            )

            return

        row = row.iloc[0]

        dst = row["DST"]

        ord_value = float(
            row["ord"]
        )


        # ====================================================
        # REPLENISHMENT WEEK
        # ====================================================

        replenishment_week = (
            input.replenishment_week()
        )

        if (
            replenishment_week
            is None
            or str(
                replenishment_week
            ).strip() == ""
        ):

            status_message.set(
                "Please select a replenishment week."
            )

            status_type.set(
                "error"
            )

            return


        try:

            replenishment_week = int(
                str(
                    replenishment_week
                ).strip()
            )

        except Exception:

            status_message.set(
                "Please select a valid replenishment week."
            )

            status_type.set(
                "error"
            )

            return


        # ====================================================
        # COLLECT WEEK QUANTITIES
        # ====================================================

        values = []

        total_qty = 0

        for week in range(1, 54):

            try:

                value = input[
                    f"week_{week}"
                ]()

            except Exception:

                continue

            if (
                value is None
                or str(value).strip() == ""
            ):
                continue

            value = str(value).strip()

            if not re.fullmatch(
                r"\d+",
                value
            ):

                status_message.set(
                    f"Week {week} must contain a whole number."
                )

                status_type.set(
                    "error"
                )

                return

            qty = int(value)

            if qty <= 0:
                continue

            values.append(
                (
                    week,
                    qty
                )
            )

            total_qty += qty


        # ====================================================
        # VALIDATION
        # ====================================================

        if total_qty <= 0:

            status_message.set(
                "Please enter at least one delivery quantity."
            )

            status_type.set(
                "error"
            )

            return


        if total_qty > ord_value:

            status_message.set(
                "The total delivery quantity cannot exceed the ORD."
            )

            status_type.set(
                "error"
            )

            return


        # ====================================================
        # PERCENTAGES
        # ====================================================

        output_rows = []

        for week, qty in values:

            percent = (
                qty
                / total_qty
                * 100
            )

            output_rows.append({

                "DST":
                    dst,

                "DESTINATION":
                    country,

                "WEEK":
                    week,

                "qty":
                    qty,

                "percent":
                    percent

            })


        # ====================================================
        # R VECTOR
        # ====================================================

        r_values = [
            row["qty"]
            for row in output_rows
        ]

        r_vector = create_r_vector(
            r_values
        )


        # ====================================================
        # EMAIL
        # ====================================================

        subject = (
            f"Delivery Information - "
            f"{country}"
        )


        body_lines = [

            f"Destination: {country}",

            f"DST: {dst}",

            f"ORD: {format_ord(ord_value)}",

            (
                "Replenishment week: "
                f"{replenishment_week}"
            ),

            "",

            "Delivery quantities:"

        ]


        for row in output_rows:

            body_lines.append(

                f"Week {row['WEEK']}: "
                f"{row['qty']} "
                f"({row['percent']:.1f}%)"

            )


        body_lines.extend([

            "",

            "R vector:",

            r_vector

        ])


        body = "\n".join(
            body_lines
        )


        # ====================================================
        # OUTLOOK URL
        # ====================================================

        recipients = (
            f"{OWNER_EMAIL};"
            f"{SECOND_OWNER_EMAIL}"
        )

        outlook_url = (
            "https://outlook.office.com/mail/deeplink/compose?"
            f"to={quote(recipients)}"
            f"&subject={quote(subject)}"
            f"&body={quote(body)}"
        )


        # ====================================================
        # OPEN OUTLOOK
        # ====================================================

        session.send_custom_message(
            "open_outlook",
            {
                "url":
                    outlook_url
            }
        )


        status_message.set(
            "The Outlook email window has been opened."
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
