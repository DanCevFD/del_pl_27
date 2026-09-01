from shiny import App, ui, render, reactive
import pandas as pd
import smtplib
import ssl
import os
import re
from email.message import EmailMessage
from datetime import date


# ============================================================
# CONFIGURATION
# ============================================================

APP_TITLE = "Delivery Date Request"

# Your email address.
# IMPORTANT:
# For deployment, set this as an environment variable instead
# of hard-coding it here.
OWNER_EMAIL = os.getenv(
    "OWNER_EMAIL",
    "YOUR_EMAIL@example.com"
)

# SMTP configuration.
#
# Example for Microsoft 365:
#
# SMTP_SERVER = "smtp.office365.com"
# SMTP_PORT = 587
#
# Example for Gmail:
#
# SMTP_SERVER = "smtp.gmail.com"
# SMTP_PORT = 587

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
# LOAD PRODUCTS
# ============================================================

try:

    products_df = pd.read_csv(
        "products.csv",
        dtype=str
    )

except Exception as e:

    raise RuntimeError(
        f"Could not read products.csv: {e}"
    )


if "product" not in products_df.columns:

    raise ValueError(
        "products.csv must contain a column called 'product'."
    )


products = (
    products_df["product"]
    .dropna()
    .astype(str)
    .str.strip()
    .loc[lambda x: x != ""]
    .drop_duplicates()
    .sort_values()
    .tolist()
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def valid_email(email):

    """
    Basic email validation.
    """

    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    return bool(
        re.match(
            pattern,
            email
        )
    )


def send_email(
    client_name,
    client_email,
    product,
    first_date,
    second_date
):

    """
    Sends the request to the owner and a confirmation
    to the client.
    """

    # --------------------------------------------------------
    # Data line
    # --------------------------------------------------------

    data_line = (
        f"{product} ; "
        f"{first_date} ; "
        f"{second_date}"
    )

    # --------------------------------------------------------
    # Email to owner
    # --------------------------------------------------------

    owner_message = EmailMessage()

    owner_message["Subject"] = (
        f"Delivery request - {product}"
    )

    owner_message["From"] = SMTP_USERNAME

    owner_message["To"] = OWNER_EMAIL

    owner_message["Reply-To"] = client_email

    owner_body = f"""
New delivery request

Client:
{client_name}

Email:
{client_email}

Product:
{product}

First possible date:
{first_date}

Second possible date:
{second_date}


CSV-style data:

{data_line}
"""

    owner_message.set_content(
        owner_body
    )

    # --------------------------------------------------------
    # CSV attachment
    # --------------------------------------------------------

    csv_content = (
        "product;first_possible_date;"
        "second_possible_date\n"
        f"{data_line}\n"
    )

    owner_message.add_attachment(
        csv_content.encode("utf-8"),
        maintype="text",
        subtype="csv",
        filename="delivery_request.csv"
    )

    # --------------------------------------------------------
    # Client confirmation
    # --------------------------------------------------------

    client_message = EmailMessage()

    client_message["Subject"] = (
        "Delivery request confirmation"
    )

    client_message["From"] = SMTP_USERNAME

    client_message["To"] = client_email

    client_body = f"""
Dear {client_name},

Thank you. Your delivery request has been received.

Product:
{product}

First possible delivery date:
{first_date}

Second possible delivery date:
{second_date}


Your data:

{data_line}

Best regards
"""

    client_message.set_content(
        client_body
    )

    # --------------------------------------------------------
    # Send both messages
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

    ui.tags.head(

        ui.tags.title(
            APP_TITLE
        ),

        ui.tags.style("""

            body {
                background-color: #f5f6f8;
                font-family: Arial, sans-serif;
            }

            .main-container {
                max-width: 1050px;
                margin: 40px auto;
                background: white;
                padding: 35px;
                border-radius: 12px;
                box-shadow: 0 4px 18px rgba(0,0,0,0.08);
            }

            .app-title {
                font-size: 30px;
                font-weight: 600;
                margin-bottom: 8px;
            }

            .app-subtitle {
                color: #666;
                margin-bottom: 30px;
            }

            .request-table {
                width: 100%;
                border-collapse: separate;
                border-spacing: 12px;
                margin-left: -12px;
            }

            .request-table th {
                text-align: left;
                font-weight: 600;
                padding-bottom: 5px;
            }

            .request-table td {
                vertical-align: top;
            }

            .send-column {
                width: 130px;
                vertical-align: bottom !important;
            }

            .send-button {
                width: 120px;
                height: 38px;
                font-weight: 600;
            }

            .success-box {
                margin-top: 25px;
                padding: 15px;
                border-radius: 8px;
                background-color: #eaf7ed;
                border: 1px solid #b7dfbf;
                color: #256b35;
            }

            .error-box {
                margin-top: 25px;
                padding: 15px;
                border-radius: 8px;
                background-color: #fff0f0;
                border: 1px solid #e0b5b5;
                color: #8a2525;
            }

            .required {
                color: #c62828;
            }

            @media (max-width: 800px) {

                .main-container {
                    margin: 15px;
                    padding: 20px;
                }

                .request-table,
                .request-table tbody,
                .request-table tr,
                .request-table td {
                    display: block;
                    width: 100%;
                }

                .request-table th {
                    display: none;
                }

                .send-column {
                    margin-top: 10px;
                }

            }

        """)

    ),

    ui.div(

        {"class": "main-container"},

        ui.div(
            {"class": "app-title"},
            "Delivery Date Request"
        ),

        ui.div(
            {"class": "app-subtitle"},
            "Please provide your contact information "
            "and the two possible delivery dates."
        ),

        # ----------------------------------------------------
        # NAME / EMAIL
        # ----------------------------------------------------

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

        ui.br(),

        # ----------------------------------------------------
        # MAIN REQUEST TABLE
        # ----------------------------------------------------

        ui.tags.table(

            {"class": "request-table"},

            ui.tags.thead(

                ui.tags.tr(

                    ui.tags.th(
                        "Product"
                    ),

                    ui.tags.th(
                        "First possible date"
                    ),

                    ui.tags.th(
                        "Second possible date"
                    ),

                    ui.tags.th(
                        ""
                    )

                )

            ),

            ui.tags.tbody(

                ui.tags.tr(

                    ui.tags.td(

                        ui.input_selectize(
                            "product",
                            None,
                            choices=products,
                            selected=None,
                            multiple=False,
                            options={
                                "placeholder":
                                    "Search for a product..."
                            }
                        )

                    ),

                    ui.tags.td(

                        ui.input_date(
                            "first_date",
                            None,
                            value=None,
                            min=date.today(),
                            format="yyyy-mm-dd"
                        )

                    ),

                    ui.tags.td(

                        ui.input_date(
                            "second_date",
                            None,
                            value=None,
                            min=date.today(),
                            format="yyyy-mm-dd"
                        )

                    ),

                    ui.tags.td(

                        {
                            "class":
                                "send-column"
                        },

                        ui.input_action_button(
                            "send",
                            "Send",
                            class_="send-button"
                        )

                    )

                )

            )

        ),

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

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
    # Status message
    # --------------------------------------------------------

    status_message = reactive.Value(None)

    status_type = reactive.Value(None)

    # --------------------------------------------------------
    # Send button
    # --------------------------------------------------------

    @reactive.effect
    @reactive.event(input.send)
    def process_request():

        status_message.set(None)
        status_type.set(None)

        # ----------------------------------------------------
        # Get values
        # ----------------------------------------------------

        client_name = (
            input.client_name()
            or ""
        ).strip()

        client_email = (
            input.client_email()
            or ""
        ).strip()

        product = input.product()

        first_date = input.first_date()

        second_date = input.second_date()

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        errors = []

        if not client_name:

            errors.append(
                "Please enter your name."
            )

        if not client_email:

            errors.append(
                "Please enter your email address."
            )

        elif not valid_email(
            client_email
        ):

            errors.append(
                "Please enter a valid email address."
            )

        if not product:

            errors.append(
                "Please select a product."
            )

        if not first_date:

            errors.append(
                "Please select the first possible date."
            )

        if not second_date:

            errors.append(
                "Please select the second possible date."
            )

        # ----------------------------------------------------
        # Date comparison
        # ----------------------------------------------------

        if (
            first_date
            and second_date
            and second_date < first_date
        ):

            errors.append(
                "The second possible date cannot be "
                "earlier than the first possible date."
            )

        # ----------------------------------------------------
        # Show errors
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
        # Convert dates
        # ----------------------------------------------------

        first_date_string = str(
            first_date
        )

        second_date_string = str(
            second_date
        )

        # ----------------------------------------------------
        # Send email
        # ----------------------------------------------------

        try:

            send_email(

                client_name=client_name,

                client_email=client_email,

                product=product,

                first_date=first_date_string,

                second_date=second_date_string

            )

            # ------------------------------------------------
            # Success
            # ------------------------------------------------

            status_type.set(
                "success"
            )

            status_message.set(
                f"""
                Thank you, {client_name}.
                Your delivery request has been sent successfully.
                """
            )

            # ------------------------------------------------
            # Reset fields
            # ------------------------------------------------

            ui.update_text(
                "client_name",
                value=""
            )

            ui.update_text(
                "client_email",
                value=""
            )

            ui.update_selectize(
                "product",
                selected=""
            )

            ui.update_date(
                "first_date",
                value=None
            )

            ui.update_date(
                "second_date",
                value=None
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
                """
                Something went wrong while sending your request.
                Please check your information and try again.
                """
            )

    # --------------------------------------------------------
    # Render status
    # --------------------------------------------------------

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
# CREATE APP
# ============================================================

app = App(
    app_ui,
    server
)
