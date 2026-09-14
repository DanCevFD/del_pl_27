from shiny import App, ui, render, reactive, Inputs, Outputs, Session
import pandas as pd
import re
from urllib.parse import quote
from datetime import date, timedelta


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
# WEEK NORMALIZATION
# ============================================================

def normalize_week(week):

    week = int(week)

    while week < 1:

        week += 52

    while week > 52:

        week -= 52

    return week


# ============================================================
# GET WEEK RANGE
# ============================================================

def get_week_range(
    min_week,
    max_week
):

    min_week = int(min_week)
    max_week = int(max_week)

    if max_week < min_week:
        max_week += 52

    return list(
        range(
            min_week,
            max_week + 1
        )
    )


# ============================================================
# MONTH CALCULATION
# ============================================================

def get_month_for_week(
    week,
    country,
    original_min_week=None
):

    min_date = country["min_date"]

    if pd.isna(min_date):

        return ""

    min_date = pd.Timestamp(
        min_date
    )

    base_year = int(
        min_date.isocalendar().year
    )

    normalized_week = normalize_week(
        week
    )

    if original_min_week is not None:

        start_display_week = normalize_week(
            original_min_week
        )

        if normalized_week < start_display_week:

            base_year += 1

    try:

        week_date = pd.Timestamp.fromisocalendar(
            base_year,
            normalized_week,
            1
        )

    except ValueError:

        return ""

    return week_date.strftime(
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
        # BUTTON ENABLE / DISABLE JAVASCRIPT
        # ====================================================

        ui.tags.script("""

        (function() {

            function hasScenarioWeekValue(
                scenario
            ) {

                const weekInputs =
                    document.querySelectorAll(
                        "input[id^='" +
                        scenario +
                        "_week_']"
                    );

                for (const input of weekInputs) {

                    if (
                        input.value &&
                        input.value.trim() !== "" &&
                        !isNaN(
                            Number(
                                input.value.trim()
                            )
                        ) &&
                        Number(
                            input.value.trim()
                        ) > 0
                    ) {

                        return true;
                    }
                }

                return false;
            }


            function hasScenarioReplenishmentWeek(
                scenario
            ) {

                const replenishmentInput =
                    document.getElementById(
                        "replenishment_week_" +
                        scenario
                    );

                if (!replenishmentInput) {

                    return false;
                }

                return (
                    replenishmentInput.value &&
                    replenishmentInput.value.trim() !== ""
                );
            }


            function updateActionButtons() {

                const sendButton =
                    document.getElementById(
                        "send"
                    );

                const downloadButton =
                    document.getElementById(
                        "download_table"
                    );

                if (
                    !sendButton &&
                    !downloadButton
                ) {

                    return;
                }


                const idealHasData =
                    hasScenarioWeekValue(
                        "ideal"
                    ) &&
                    hasScenarioReplenishmentWeek(
                        "ideal"
                    );


                const acceptableHasData =
                    hasScenarioWeekValue(
                        "acceptable"
                    ) &&
                    hasScenarioReplenishmentWeek(
                        "acceptable"
                    );


                const enabled =
                    idealHasData &&
                    acceptableHasData;


                if (sendButton) {

                    sendButton.disabled =
                        !enabled;

                    if (enabled) {

                        sendButton.classList.remove(
                            "button-blocked"
                        );

                    }

                    else {

                        sendButton.classList.add(
                            "button-blocked"
                        );
                    }
                }


                if (downloadButton) {

                    downloadButton.disabled =
                        !enabled;

                    if (enabled) {

                        downloadButton.classList.remove(
                            "button-blocked"
                        );

                    }

                    else {

                        downloadButton.classList.add(
                            "button-blocked"
                        );
                    }
                }
            }


            document.addEventListener(
                "input",
                function(event) {

                    if (
                        event.target.matches(
                            "input[id^='ideal_week_'], " +
                            "input[id^='acceptable_week_'], " +
                            "input[id^='replenishment_week_']"
                        )
                    ) {

                        updateActionButtons();
                    }
                }
            );


            document.addEventListener(
                "change",
                function(event) {

                    if (
                        event.target.matches(
                            "input[id^='ideal_week_'], " +
                            "input[id^='acceptable_week_'], " +
                            "input[id^='replenishment_week_']"
                        )
                    ) {

                        updateActionButtons();
                    }
                }
            );


            const observer =
                new MutationObserver(
                    function() {

                        updateActionButtons();
                    }
                );


            observer.observe(
                document.body,
                {
                    childList: true,
                    subtree: true
                }
            );


            document.addEventListener(
                "click",
                function(event) {

                    const button =
                        event.target.closest(
                            "#send, #download_table"
                        );

                    if (!button) {

                        return;
                    }


                    if (button.disabled) {

                        event.preventDefault();
                        event.stopPropagation();

                        return false;
                    }
                },
                true
            );


            document.addEventListener(
                "DOMContentLoaded",
                function() {

                    updateActionButtons();
                }
            );


            setTimeout(
                updateActionButtons,
                100
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

                d.setHours(
                    0,
                    0,
                    0,
                    0
                );

                return d;
            }


            function getCurrentWeekMonday() {

                return getMonday(
                    new Date()
                );
            }


            function isBeforeCurrentMonth() {

                const now =
                    new Date();

                if (
                    pickerYear <
                    now.getFullYear()
                ) {

                    return true;
                }

                if (
                    pickerYear ===
                    now.getFullYear() &&
                    pickerMonth <
                    now.getMonth()
                ) {

                    return true;
                }

                return false;
            }


            function isCurrentMonth() {

                const now =
                    new Date();

                return (
                    pickerYear ===
                    now.getFullYear() &&
                    pickerMonth ===
                    now.getMonth()
                );
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


                previousButton.disabled =
                    isCurrentMonth();


                previousButton.onclick =
                    function(event) {

                        event.preventDefault();
                        event.stopPropagation();

                        if (
                            isCurrentMonth()
                        ) {

                            return;
                        }

                        pickerMonth--;

                        if (pickerMonth < 0) {

                            pickerMonth = 11;

                            pickerYear--;
                        }

                        if (
                            isBeforeCurrentMonth()
                        ) {

                            const now =
                                new Date();

                            pickerYear =
                                now.getFullYear();

                            pickerMonth =
                                now.getMonth();
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


                const currentWeekMonday =
                    getCurrentWeekMonday();


                let monday =
                    getMonday(
                        firstDay
                    );


                if (
                    monday.getMonth() !==
                    pickerMonth
                ) {

                    if (
                        !(
                            isCurrentMonth() &&
                            monday.getTime() ===
                            currentWeekMonday.getTime()
                        )
                    ) {

                        monday.setDate(
                            monday.getDate() + 7
                        );
                    }
                }


                while (
                    monday <= lastDay
                ) {

                    const isCurrentWeek =
                        monday.getTime() ===
                        currentWeekMonday.getTime();


                    if (
                        monday.getMonth() !==
                        pickerMonth &&
                        !(
                            isCurrentMonth() &&
                            isCurrentWeek
                        )
                    ) {

                        break;
                    }


                    if (
                        monday >=
                        currentWeekMonday
                    ) {

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
                    }


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

        # ====================================================
        # EXACT ROW HEIGHT SYNCHRONIZATION
        # ====================================================

        ui.tags.script("""

        (function() {

            /*
               The W table remains the reference.

               The important difference here is that the measured
               W heights are rounded UP to whole CSS pixels and
               then applied to ALL THREE tables, including W itself.

               This prevents fractional/sub-pixel row heights from
               producing border lines that are visually a fraction
               of a pixel apart.
            */

            function setRowHeight(row, height, sourceRow) {

                if (!row || !height || height <= 0) {
                    return;
                }

                const value = Math.ceil(height) + "px";

                row.style.setProperty(
                    "height",
                    value,
                    "important"
                );

                row.style.setProperty(
                    "min-height",
                    value,
                    "important"
                );

                row.style.setProperty(
                    "max-height",
                    value,
                    "important"
                );

                row.style.setProperty(
                    "box-sizing",
                    "border-box",
                    "important"
                );

                const sourceCell =
                    sourceRow
                        ? sourceRow.querySelector("th, td")
                        : null;

                let sourceLineHeight = "";

                if (sourceCell) {
                    sourceLineHeight =
                        getComputedStyle(
                            sourceCell
                        ).lineHeight;
                }

                row.querySelectorAll("th, td").forEach(
                    function(cell) {

                        cell.style.setProperty(
                            "height",
                            value,
                            "important"
                        );

                        cell.style.setProperty(
                            "min-height",
                            value,
                            "important"
                        );

                        cell.style.setProperty(
                            "max-height",
                            value,
                            "important"
                        );

                        cell.style.setProperty(
                            "box-sizing",
                            "border-box",
                            "important"
                        );

                        cell.style.setProperty(
                            "vertical-align",
                            "middle",
                            "important"
                        );

                        cell.style.setProperty(
                            "overflow",
                            "hidden",
                            "important"
                        );

                        /*
                           Keep normal cells visually consistent with
                           the W section. For the two-line fixed headers,
                           calculate a line-height that fits exactly
                           inside the common row height.
                        */

                        if (
                            cell.querySelector("br")
                        ) {

                            const borderTop =
                                parseFloat(
                                    getComputedStyle(
                                        cell
                                    ).borderTopWidth
                                ) || 0;

                            const borderBottom =
                                parseFloat(
                                    getComputedStyle(
                                        cell
                                    ).borderBottomWidth
                                ) || 0;

                            const available =
                                Math.max(
                                    1,
                                    Math.ceil(height) -
                                    borderTop -
                                    borderBottom
                                );

                            cell.style.setProperty(
                                "padding-top",
                                "0px",
                                "important"
                            );

                            cell.style.setProperty(
                                "padding-bottom",
                                "0px",
                                "important"
                            );

                            cell.style.setProperty(
                                "line-height",
                                (available / 2).toFixed(3) + "px",
                                "important"
                            );

                        }
                        else if (
                            sourceLineHeight
                        ) {

                            cell.style.setProperty(
                                "line-height",
                                sourceLineHeight,
                                "important"
                            );

                        }

                    }
                );
            }


            function syncOneSegment(segment) {

                const middle =
                    segment.querySelector(
                        ".scenario-weeks-table"
                    );

                const left =
                    segment.querySelector(
                        ".scenario-left-table"
                    );

                const right =
                    segment.querySelector(
                        ".scenario-right-table"
                    );

                if (
                    !middle ||
                    !left ||
                    !right
                ) {
                    return;
                }


                const middleRows = [

                    middle.querySelector(
                        "thead tr:nth-child(2)"
                    ),

                    middle.querySelector(
                        "tbody tr:first-child"
                    ),

                    middle.querySelector(
                        "tbody tr:nth-child(2)"
                    )

                ];


                const leftRows = [

                    left.querySelector(
                        "thead tr:nth-child(2)"
                    ),

                    left.querySelector(
                        "tbody tr:first-child"
                    ),

                    left.querySelector(
                        "tbody tr:nth-child(2)"
                    )

                ];


                const rightRows = [

                    right.querySelector(
                        "thead tr:nth-child(2)"
                    ),

                    right.querySelector(
                        "tbody tr:first-child"
                    ),

                    right.querySelector(
                        "tbody tr:nth-child(2)"
                    )

                ];


                middleRows.forEach(
                    function(
                        middleRow,
                        index
                    ) {

                        if (!middleRow) {
                            return;
                        }

                        /*
                           Measure the natural W height before
                           changing any of the three tables.
                        */

                        const measuredHeight =
                            middleRow
                                .getBoundingClientRect()
                                .height;

                        if (
                            !measuredHeight ||
                            measuredHeight <= 0
                        ) {
                            return;
                        }

                        /*
                           Use one whole-pixel height for the
                           corresponding row in ALL sections.

                           The W row is also forced to this height.
                           This is the key change that removes the
                           remaining sub-pixel border mismatch.
                        */

                        const commonHeight =
                            Math.ceil(
                                measuredHeight
                            );

                        setRowHeight(
                            middleRow,
                            commonHeight,
                            middleRow
                        );

                        setRowHeight(
                            leftRows[index],
                            commonHeight,
                            middleRow
                        );

                        setRowHeight(
                            rightRows[index],
                            commonHeight,
                            middleRow
                        );

                    }
                );


                /*
                   Keep the replenishment controls inside the exact
                   common height of the quantity row.
                */

                const rightQuantityRow =
                    right.querySelector(
                        "tbody tr:first-child"
                    );

                if (rightQuantityRow) {

                    const commonHeight =
                        rightQuantityRow
                            .getBoundingClientRect()
                            .height;

                    const content =
                        rightQuantityRow.querySelector(
                            ".replenishment-content"
                        );

                    if (
                        content &&
                        commonHeight > 0
                    ) {

                        const contentHeight =
                            Math.max(
                                0,
                                Math.ceil(
                                    commonHeight
                                ) - 2
                            );

                        content.style.setProperty(
                            "height",
                            contentHeight + "px",
                            "important"
                        );

                        content.style.setProperty(
                            "max-height",
                            contentHeight + "px",
                            "important"
                        );

                        content.style.setProperty(
                            "overflow",
                            "hidden",
                            "important"
                        );

                    }

                }

            }


            function syncAllSegments() {

                document
                    .querySelectorAll(
                        ".scenario-segments"
                    )
                    .forEach(
                        function(segment) {

                            syncOneSegment(
                                segment
                            );

                        }
                    );

            }


            let syncPending = false;


            function scheduleSync() {

                if (syncPending) {
                    return;
                }

                syncPending = true;

                requestAnimationFrame(
                    function() {

                        syncPending = false;

                        syncAllSegments();

                        /*
                           Run two additional layout passes. The
                           first pass establishes the common integer
                           heights; the following passes confirm that
                           the browser has settled all table borders.
                        */

                        requestAnimationFrame(
                            function() {

                                syncAllSegments();

                                requestAnimationFrame(
                                    function() {

                                        syncAllSegments();

                                    }
                                );

                            }
                        );

                    }
                );

            }


            /*
               Shiny replaces the scenario tables whenever the
               destination changes.
            */

            const mutationObserver =
                new MutationObserver(
                    function() {

                        scheduleSync();

                    }
                );


            mutationObserver.observe(
                document.body,
                {
                    childList: true,
                    subtree: true
                }
            );


            /*
               Re-run whenever the W table itself changes size.
            */

            function attachResizeObservers() {

                document
                    .querySelectorAll(
                        ".scenario-weeks-table"
                    )
                    .forEach(
                        function(table) {

                            if (
                                table.dataset
                                    .rowHeightObserver ===
                                "attached"
                            ) {
                                return;
                            }

                            if (
                                typeof ResizeObserver !==
                                "undefined"
                            ) {

                                const resizeObserver =
                                    new ResizeObserver(
                                        function() {

                                            scheduleSync();

                                        }
                                    );

                                resizeObserver.observe(
                                    table
                                );

                                table._rowHeightObserver =
                                    resizeObserver;

                                table.dataset
                                    .rowHeightObserver =
                                    "attached";

                            }

                        }
                    );

                scheduleSync();

            }


            document.addEventListener(
                "DOMContentLoaded",
                function() {

                    attachResizeObservers();

                    setTimeout(
                        attachResizeObservers,
                        50
                    );

                    setTimeout(
                        attachResizeObservers,
                        200
                    );

                    setTimeout(
                        attachResizeObservers,
                        500
                    );

                }
            );


            window.addEventListener(
                "resize",
                function() {

                    scheduleSync();

                }
            );


            setTimeout(
                attachResizeObservers,
                100
            );

            setTimeout(
                attachResizeObservers,
                500
            );

        })();

        """),

        # ====================================================
        # CSS
        # ====================================================

        ui.tags.style("""

        body {
            background-color: #f4f5f7;
            font-family: Arial, sans-serif;
            font-size: 15px;
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
            font-size: 29px;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }

        .section-title {
            font-size: 17px;
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


        /* ====================================================
           THREE-PART SCENARIO TABLE
           ==================================================== */

        .scenario-table {
            width: 100%;
            margin-top: 25px;
        }

        .scenario-table + .scenario-table {
            margin-top: 35px;
        }

        .scenario-segments {
            width: 100%;
            display: flex;
            align-items: flex-start;
            overflow: hidden;
        }

        .scenario-left {
            flex: 0 0 422px;
            width: 422px;
            min-width: 422px;
            overflow: hidden;
        }

        .scenario-weeks {
            flex: 1 1 auto;
            min-width: 0;
            overflow-x: auto;
            overflow-y: hidden;
        }

        .scenario-right {
            flex: 0 0 197px;
            width: 197px;
            min-width: 197px;
            overflow: hidden;
        }

        .scenario-left table,
        .scenario-weeks table,
        .scenario-right table {
            border-collapse: collapse;
            table-layout: fixed;
            font-size: 13px;
            margin: 0;
        }

        .scenario-left table {
            width: 422px;
            min-width: 422px;
        }

        .scenario-right table {
            width: 197px;
            min-width: 197px;
        }

        .scenario-weeks table {
            width: max-content;
            min-width: max-content;
        }


        /* ====================================================
           ROW HEIGHTS
           ==================================================== */

        .scenario-left-table,
        .scenario-weeks-table,
        .scenario-right-table {
            border-collapse: collapse;
        }


        /*
           The month row is intentionally kept fixed because
           all three month rows already match exactly.
        */

        .scenario-left-table thead tr:first-child,
        .scenario-weeks-table thead tr:first-child,
        .scenario-right-table thead tr:first-child {
            height: 27px !important;
        }

        .scenario-left-table thead tr:first-child > th,
        .scenario-weeks-table thead tr:first-child > th,
        .scenario-right-table thead tr:first-child > th {
            height: 27px !important;
            min-height: 27px !important;
            max-height: 27px !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            line-height: 27px !important;
            box-sizing: border-box !important;
        }


        /*
           IMPORTANT:

           Do not define heights for the remaining rows here.

           Their heights come directly from the actual rendered
           W table through the synchronization JavaScript above.
        */

        .scenario-left-table thead tr:nth-child(2),
        .scenario-weeks-table thead tr:nth-child(2),
        .scenario-right-table thead tr:nth-child(2),

        .scenario-left-table tbody tr:first-child,
        .scenario-weeks-table tbody tr:first-child,
        .scenario-right-table tbody tr:first-child,

        .scenario-left-table tbody tr:nth-child(2),
        .scenario-weeks-table tbody tr:nth-child(2),
        .scenario-right-table tbody tr:nth-child(2) {
            height: auto !important;
        }


        /*
           The fixed sections must not introduce additional
           vertical padding that makes their cells intrinsically
           larger than the W cells.
        */

        .scenario-left-table thead tr:nth-child(2) > th,
        .scenario-right-table thead tr:nth-child(2) > th {
            box-sizing: border-box !important;
            vertical-align: middle !important;
            overflow: hidden !important;
        }

        .scenario-left-table tbody tr:first-child > td,
        .scenario-right-table tbody tr:first-child > td,
        .scenario-left-table tbody tr:nth-child(2) > td,
        .scenario-right-table tbody tr:nth-child(2) > td {
            box-sizing: border-box !important;
            vertical-align: middle !important;
            overflow: hidden !important;
        }


        /* ====================================================
           COMMON TABLE CELLS
           ==================================================== */

        .scenario-left th,
        .scenario-left td,
        .scenario-weeks th,
        .scenario-weeks td,
        .scenario-right th,
        .scenario-right td {
            border-top: 1px solid #d0d2d5;
            border-bottom: 1px solid #d0d2d5;
            padding: 7px;
            text-align: center;
            white-space: nowrap;
            box-sizing: border-box;
            vertical-align: middle;
        }

        .scenario-left th,
        .scenario-weeks th,
        .scenario-right th {
            background-color: #f0f1f3;
            font-weight: 600;
        }

        .scenario-left td,
        .scenario-weeks td,
        .scenario-right td {
            padding: 4px;
        }


        /* ====================================================
           LEFT SECTION
           ==================================================== */

        .scenario-left th,
        .scenario-left td {
            border-left: 1px solid #d0d2d5;
        }

        .scenario-left th:last-child,
        .scenario-left td:last-child {
            border-right: none;
        }

        .scenario-left th:nth-child(1),
        .scenario-left td:nth-child(1) {
            width: 150px;
            min-width: 150px;
            max-width: 150px;
        }

        .scenario-left th:nth-child(2),
        .scenario-left td:nth-child(2) {
            width: 140px;
            min-width: 140px;
            max-width: 140px;
        }

        .scenario-left th:nth-child(3),
        .scenario-left td:nth-child(3) {
            width: 52px;
            min-width: 52px;
            max-width: 52px;
        }

        .scenario-left th:nth-child(4),
        .scenario-left td:nth-child(4) {
            width: 80px;
            min-width: 80px;
            max-width: 80px;
        }


        /* ====================================================
           WEEK SECTION
           ==================================================== */

        .scenario-weeks th,
        .scenario-weeks td {
            width: 62px;
            min-width: 62px;
            max-width: 62px;
            padding-left: 2px;
            padding-right: 2px;
            border-left: 1px solid #d0d2d5;
            border-right: 1px solid #d0d2d5;
        }

        .scenario-weeks th:first-child,
        .scenario-weeks td:first-child {
            border-left: none;
        }

        .scenario-weeks th:last-child,
        .scenario-weeks td:last-child {
            border-right: none;
        }


        /* ====================================================
           RIGHT SECTION
           ==================================================== */

        .scenario-right th,
        .scenario-right td {
            border-left: 1px solid #d0d2d5;
            border-right: 1px solid #d0d2d5;
        }

        .scenario-right th:first-child,
        .scenario-right td:first-child {
            border-left: none;
        }

        .scenario-right th:last-child,
        .scenario-right td:last-child {
            border-right: 1px solid #d0d2d5;
        }

        .scenario-right th:nth-child(1),
        .scenario-right td:nth-child(1) {
            width: 62px;
            min-width: 62px;
            max-width: 62px;
        }

        .scenario-right th:nth-child(2),
        .scenario-right td:nth-child(2) {
            width: 135px;
            min-width: 135px;
            max-width: 135px;
        }


        /* ====================================================
           HEADER / MONTH ROW
           ==================================================== */

        .month-header {
            background-color: #fafafa !important;
            font-size: 12px;
            color: #555;
            height: 27px;
        }


        /* ====================================================
           BLOCKED CELLS
           ==================================================== */

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


        /* ====================================================
           TOTAL / REPLENISHMENT
           ==================================================== */

        .total-cell {
            background-color: #eeeeee;
            font-weight: 600;
        }

        .replenishment-header {
            background-color: #f0f1f3 !important;
            white-space: normal !important;
            line-height: 16px !important;
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
            gap: 4px;
            width: 100%;
            height: 30px;
            max-height: 30px;
            overflow: hidden;
        }

        .replenishment-label {
            display: inline-block;
            font-size: 11px;
            color: #555;
            margin-right: 0;
            vertical-align: middle;
        }


        /* ====================================================
           PERCENTAGE ROW
           ==================================================== */

        .percentage-row td {
            background-color: #f8f8f8;
            color: #555;
            font-size: 12px;
        }


        /* ====================================================
           INPUTS
           ==================================================== */

        .scenario-weeks .form-group {
            margin-bottom: 0;
        }

        .scenario-weeks input[type="text"] {
            width: 52px !important;
            min-width: 52px !important;
            max-width: 52px !important;
            height: 30px !important;
            padding: 2px !important;
            text-align: center;
            box-sizing: border-box;
            font-size: 13px;
        }

        input[id^="replenishment_week_"] {
            width: 52px !important;
            min-width: 52px !important;
            max-width: 52px !important;
            height: 30px !important;
            padding: 2px !important;
            text-align: center;
            box-sizing: border-box;
            cursor: pointer;
            font-size: 13px;
        }


        /* ====================================================
           SCROLLBAR
           ==================================================== */

        .scenario-weeks {
            scrollbar-width: auto;
        }

        .scenario-weeks::-webkit-scrollbar {
            height: 14px;
        }

        .scenario-weeks::-webkit-scrollbar-track {
            background-color: #f0f1f3;
        }

        .scenario-weeks::-webkit-scrollbar-thumb {
            background-color: #bdbdbd;
            border: 3px solid #f0f1f3;
            border-radius: 7px;
        }


        /* ====================================================
           SEND CONTROLS
           ==================================================== */

        .send-controls {
            margin-top: 25px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            width: 100%;
        }


        /* ====================================================
           BLOCKED SEND / DOWNLOAD BUTTONS
           ==================================================== */

        #send:disabled,
        #download_table:disabled,
        .button-blocked {
            background-color: #bdbdbd !important;
            border-color: #bdbdbd !important;
            color: #eeeeee !important;
            cursor: not-allowed !important;
            opacity: 1 !important;
            box-shadow: none !important;
        }

        #send:disabled:hover,
        #download_table:disabled:hover,
        .button-blocked:hover {
            background-color: #bdbdbd !important;
            border-color: #bdbdbd !important;
            color: #eeeeee !important;
            cursor: not-allowed !important;
        }


        /* ====================================================
           NOTES
           ==================================================== */

        .notes-container {
            margin-top: 30px;
        }

        .notes-label {
            font-size: 14px;
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
            font-size: 13px;
        }


        /* ====================================================
           STATUS
           ==================================================== */

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
            font-size: 13px;
        }

        .week-picker-nav {
            border: none;
            background: transparent;
            font-size: 23px;
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
            font-size: 11px;
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
            padding: 6px;
            cursor: pointer;
            font-size: 13px;
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

        # ====================================================
        # TUTORIAL LINK
        # ====================================================

        ui.div(
            {
                "class":
                    "subtitle"
            },

            "Select a destination and enter the delivery quantities for each week. ",

            ui.tags.a(
                "(Tutorial)",
                href="https://github.com/DanCevFD/del_pl_27/raw/refs/heads/main/test_app_1.mp4",
                target="_blank",
                rel="noopener noreferrer"
            )
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


        # ----------------------------------------------------
        # RAW AND DISPLAY WEEKS
        # ----------------------------------------------------

        raw_weeks = get_week_range(
            min_week,
            max_week
        )

        display_weeks = [
            normalize_week(
                week
            )
            for week in raw_weeks
        ]

        months = [

            get_month_for_week(
                week,
                country,
                min_week
            )

            for week in raw_weeks

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
        # LEFT SECTION
        # ====================================================

        left_month_row = [

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


        left_header_row = [

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


        left_quantity_row = [

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


        left_percentage_row = [

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


        left_table = ui.tags.table(

            {
                "class":
                    "scenario-left-table"
            },

            ui.tags.thead(

                ui.tags.tr(
                    left_month_row
                ),

                ui.tags.tr(
                    left_header_row
                )

            ),

            ui.tags.tbody(

                ui.tags.tr(
                    left_quantity_row
                ),

                ui.tags.tr(
                    {
                        "class":
                            "percentage-row"
                    },

                    left_percentage_row
                )

            )

        )


        # ====================================================
        # WEEK SECTION
        # ====================================================

        week_month_row = []

        for month in month_cells:

            week_month_row.append(

                ui.tags.th(
                    month,
                    {
                        "class":
                            "month-header"
                    }
                )

            )


        week_header_row = []

        for display_week in display_weeks:

            week_header_row.append(

                ui.tags.th(
                    f"W{display_week}"
                )

            )


        week_quantity_row = []

        for week in raw_weeks:

            week_quantity_row.append(

                ui.tags.td(

                    create_quantity_input(
                        scenario,
                        week
                    )

                )

            )


        week_percentage_row = []

        for week in raw_weeks:

            week_percentage_row.append(

                ui.tags.td(

                    ui.output_text(
                        f"{scenario}_percent_{week}"
                    )

                )

            )


        week_table = ui.tags.table(

            {
                "class":
                    "scenario-weeks-table"
            },

            ui.tags.thead(

                ui.tags.tr(
                    week_month_row
                ),

                ui.tags.tr(
                    week_header_row
                )

            ),

            ui.tags.tbody(

                ui.tags.tr(
                    week_quantity_row
                ),

                ui.tags.tr(
                    {
                        "class":
                            "percentage-row"
                    },

                    week_percentage_row
                )

            )

        )


        # ====================================================
        # RIGHT SECTION
        # ====================================================

        right_month_row = [

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
                        "month-header replenishment-header"
                }
            )

        ]


        right_header_row = [

            ui.tags.th(
                "Total"
            ),

            ui.tags.th(
                ui.HTML(
                    "Replenishment<br>week"
                ),
                {
                    "class":
                        "replenishment-header"
                }
            )

        ]


        right_quantity_row = [

            ui.tags.td(

                ui.output_text(
                    f"{scenario}_total_quantity"
                ),

                {
                    "class":
                        "total-cell"
                }

            ),

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

        ]


        right_percentage_row = [

            ui.tags.td(
                "100%"
            ),

            ui.tags.td(
                "",
                {
                    "class":
                        "replenishment-cell"
                }
            )

        ]


        right_table = ui.tags.table(

            {
                "class":
                    "scenario-right-table"
            },

            ui.tags.thead(

                ui.tags.tr(
                    right_month_row
                ),

                ui.tags.tr(
                    right_header_row
                )

            ),

            ui.tags.tbody(

                ui.tags.tr(
                    right_quantity_row
                ),

                ui.tags.tr(
                    {
                        "class":
                            "percentage-row"
                    },

                    right_percentage_row
                )

            )

        )


        # ====================================================
        # THREE SECTIONS
        #
        # LEFT  = fixed information
        # MIDDLE = ONLY SCROLLABLE PART
        # RIGHT = fixed total/replenishment
        # ====================================================

        return ui.div(

            {
                "class":
                    "scenario-segments"
            },

            ui.div(

                {
                    "class":
                        "scenario-left"
                },

                left_table

            ),

            ui.div(

                {
                    "class":
                        "scenario-weeks"
                },

                week_table

            ),

            ui.div(

                {
                    "class":
                        "scenario-right"
                },

                right_table

            )

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
                        "scenario-table"
                },

                ideal_table

            ),

            ui.div(

                {
                    "class":
                        "scenario-table"
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
                ),

                ui.download_button(
                    "download_table",
                    "download table"
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

            for week in get_week_range(
                min_week,
                max_week
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

                return "0%"

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

            for raw_week in get_week_range(
                min_week,
                max_week
            ):

                try:

                    value = getattr(
                        input,
                        f"{scenario}_week_{raw_week}"
                    )()

                except Exception:

                    value = ""

                if not value:

                    continue

                try:

                    total += float(
                        value
                    )

                except Exception:

                    continue


            try:

                value = getattr(
                    input,
                    f"{scenario}_week_{week}"
                )()

            except Exception:

                value = ""


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


    all_raw_weeks = sorted(
        {
            week
            for _, country_row in country_df.iterrows()
            for week in get_week_range(
                int(country_row["min_week"]),
                int(country_row["max_week"])
            )
        }
    )


    for scenario in [
        "ideal",
        "acceptable"
    ]:

        for week in all_raw_weeks:

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


            for other_week in get_week_range(
                min_week,
                max_week
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


    all_raw_weeks = sorted(
        {
            week
            for _, country_row in country_df.iterrows()
            for week in get_week_range(
                int(country_row["min_week"]),
                int(country_row["max_week"])
            )
        }
    )


    for scenario in [
        "ideal",
        "acceptable"
    ]:

        for week in all_raw_weeks:

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


        scenario_has_week_value = {
            "ideal": False,
            "acceptable": False
        }

        scenario_has_replenishment_week = {
            "ideal": False,
            "acceptable": False
        }


        for scenario in [
            "ideal",
            "acceptable"
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


            for week in get_week_range(
                min_week,
                max_week
            ):

                try:

                    value = getattr(
                        input,
                        f"{scenario}_week_{week}"
                    )()

                except Exception:

                    value = ""


                if (
                    value is not None
                    and str(value).strip() != ""
                    and str(value).strip().isdigit()
                    and int(
                        str(value).strip()
                    ) > 0
                ):

                    scenario_has_week_value[
                        scenario
                    ] = True

                    break


            try:

                replenishment_value = getattr(
                    input,
                    f"replenishment_week_{scenario}"
                )()

            except Exception:

                replenishment_value = ""


            if (
                replenishment_value is not None
                and str(
                    replenishment_value
                ).strip() != ""
            ):

                scenario_has_replenishment_week[
                    scenario
                ] = True


        if not scenario_has_week_value["ideal"]:

            status_type.set(
                "error"
            )

            status_message.set(
                "Please enter at least one quantity "
                "for the IDEAL scenario."
            )

            return


        if not scenario_has_week_value["acceptable"]:

            status_type.set(
                "error"
            )

            status_message.set(
                "Please enter at least one quantity "
                "for the ACCEPTABLE scenario."
            )

            return


        if not scenario_has_replenishment_week["ideal"]:

            status_type.set(
                "error"
            )

            status_message.set(
                "Please enter a replenishment week "
                "for the IDEAL scenario."
            )

            return


        if not scenario_has_replenishment_week["acceptable"]:

            status_type.set(
                "error"
            )

            status_message.set(
                "Please enter a replenishment week "
                "for the ACCEPTABLE scenario."
            )

            return


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


            for week in get_week_range(
                min_week,
                max_week
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
                        f"W{normalize_week(week)} must contain "
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


            if total <= 0:

                status_type.set(
                    "error"
                )

                status_message.set(
                    f"Please enter at least one quantity "
                    f"for the {scenario_label} scenario."
                )

                return


            output_rows = []


            for row in rows:

                raw_week = row[
                    "week"
                ]

                qty = row[
                    "qty"
                ]


                display_week = normalize_week(
                    raw_week
                )


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
                                display_week
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


        combined_df = pd.DataFrame(

            all_output_rows,

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

        combined_vector = create_r_vector(
            combined_df
        )


        body_parts = [

            "Please see below the delivery information",

            "",

            "Delivery plan information:",

            combined_vector

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
    # DOWNLOAD TABLE
    # ========================================================

    @render.download(
        filename=lambda:
            (
                f"{date.today().isoformat()}_"
                f"{str(current_country()['DESTINATION_NAME'])}_"
                f"delivery_plan.csv"
            )
            if current_country() is not None
            else "delivery_plan.csv"
    )
    def download_table():

        country = current_country()

        if country is None:

            return


        scenario_has_week_value = {
            "ideal": False,
            "acceptable": False
        }

        scenario_has_replenishment_week = {
            "ideal": False,
            "acceptable": False
        }


        for scenario in [
            "ideal",
            "acceptable"
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


            for week in get_week_range(
                min_week,
                max_week
            ):

                try:

                    value = getattr(
                        input,
                        f"{scenario}_week_{week}"
                    )()

                except Exception:

                    value = ""


                if (
                    value is not None
                    and str(value).strip() != ""
                    and str(value).strip().isdigit()
                    and int(
                        str(value).strip()
                    ) > 0
                ):

                    scenario_has_week_value[
                        scenario
                    ] = True

                    break


            try:

                replenishment_value = getattr(
                    input,
                    f"replenishment_week_{scenario}"
                )()

            except Exception:

                replenishment_value = ""


            if (
                replenishment_value is not None
                and str(
                    replenishment_value
                ).strip() != ""
            ):

                scenario_has_replenishment_week[
                    scenario
                ] = True


        if not scenario_has_week_value["ideal"]:

            return


        if not scenario_has_week_value["acceptable"]:

            return


        if not scenario_has_replenishment_week["ideal"]:

            return


        if not scenario_has_replenishment_week["acceptable"]:

            return


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

        all_output_rows = []

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

            for week in get_week_range(
                min_week,
                max_week
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

            if (
                ord_value is not None
                and total > ord_value
            ):

                return

            if total <= 0:

                return

            for row in rows:

                raw_week = row[
                    "week"
                ]

                qty = row[
                    "qty"
                ]

                display_week = normalize_week(
                    raw_week
                )

                if qty == 0:

                    continue

                percentage = (
                    qty
                    / total
                    * 100
                )

                all_output_rows.append(
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
                                display_week
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

        table_df = pd.DataFrame(
            all_output_rows,
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

        yield table_df.to_csv(
            index=False,
            sep=";"
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
