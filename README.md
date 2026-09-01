# Delivery Information App

A Shiny for Python web application for collecting delivery information from clients.

The application allows a client to:

1. Enter their name.
2. Enter their email address.
3. Click **Input information**.
4. Search for and select a destination.
5. Automatically see the corresponding:
   - DST code
   - ord value
   - available delivery weeks
6. Enter quantities for the available weeks.
7. See the total quantity calculated automatically.
8. See the percentage for each week calculated automatically.
9. Click **Send**.
10. Receive a confirmation email.

The owner receives the submitted information by email as a structured CSV attachment.

---

## Repository structure

```text
delivery-request-app/
│
├── app.py
├── items_week.csv
├── requirements.txt
├── .gitignore
└── README.md
