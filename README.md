# Ijuru Hub

The first Django build for Ijuru Hub Ltd coworking space in Kigali. It includes the public website and a staff-managed booking foundation.

## Implemented in this first build

- Public landing page and space catalog for desks, private offices, meeting rooms, event spaces, and other listings.
- Listing descriptions, photos, inventory quantity, max group size, and daily, weekly, and monthly rates.
- Four Ijuru Hub photos used on the homepage and as category-based fallback photos for listings; a specific photo uploaded to a listing takes priority.
- Ijuru Hub Ltd logo in the public navigation, footer, and account pages.
- Availability lookup for a chosen start date and duration. A listing represents a shared quantity; a customer books one unit, not a numbered desk.
- Customer account signup/sign-in with username or email. Google sign-in is wired through django-allauth and becomes available when the Google OAuth credentials are configured.
- Booking one day, one week, or one month. A week occupies seven dates from the selected date. A month ends on the same date next month, clamped to that month’s final date (for example, January 31 to February 28).
- One-hour inventory hold from booking-form submission. Staff may approve manual payment after that hour only if capacity remains available.
- MTN MoMo Collections integration: when merchant credentials are configured, checkout requests payment on the customer’s Rwanda phone, verifies the result against MTN, and confirms successful bookings automatically. Pending requests appear on the staff dashboard; paid bookings that lose availability are flagged for staff follow-up.
- A staff portal at `/staff/` for payment review, inventory management, booking search, check-in/check-out, and viewing member accounts.
- Website pages for creating and editing space listings, changing their public availability, and searching/filtering bookings.
- Owner-only staff account creation and account activation controls from the website.
- Styled sign-in and registration pages with field-level help and validation messages; Google sign-in appears when OAuth credentials are configured.
- Customer booking status and a QR code after confirmation. A logged-in staff account can scan/open the code to record check-in and check-out during the booking dates.
- An in-site notification inbox with unread counts for customers and staff. It reports new bookings, payment outcomes, check-in/check-out, and new member registration; selecting an item opens the related booking or management page.
- PostgreSQL configuration through `DATABASE_URL`; local SQLite is used when it is not set.
- Bootstrap 5.3 is included for the interface toolkit, with Ijuru Hub’s responsive visual styling layered over it.

## Local setup on Windows PowerShell

Install Python 3.10+ first. From this project directory, run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Without `DATABASE_URL`, Django uses a local SQLite database for a quick preview. Open `http://127.0.0.1:8000/` for the public site. Enter `http://127.0.0.1:8000/staff/` for the website management area; sign in with an account marked as staff (a superuser works for local setup). Use **Spaces** to add listings and set their confirmed currency, **Bookings** for booking and visit management, and **People** to view member accounts. Only a superuser can create or disable staff accounts. Django admin remains available as a technical fallback, but routine operations are available from the website staff portal.

### Use PostgreSQL locally instead

Install and start Docker Desktop, then from the project directory run:

```powershell
docker compose up -d db
$env:DATABASE_URL = 'postgresql://ijuru_dev:ijuru_dev_only@127.0.0.1:5432/ijuru_hub'
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Keep this PowerShell window open while using the site. The environment setting applies only to that window; use the same database choice for all Django commands in that session.

## Google sign-in setup

Create a Google OAuth web client for the site. For local development, configure this authorized redirect URI:

```text
http://127.0.0.1:8000/accounts/google/login/callback/
```

Then set the credentials in the same PowerShell session before starting Django:

```powershell
$env:GOOGLE_CLIENT_ID = 'your-client-id'
$env:GOOGLE_CLIENT_SECRET = 'your-client-secret'
```

The sign-in option stays hidden until both values are present. Use the production domain’s callback URI for deployment, and store production secrets with the hosting provider rather than in source control.

## MTN MoMo setup

The integration uses MTN MoMo Collections `RequestToPay`. Start with MTN’s sandbox and merchant onboarding; production requires an approved MTN merchant account and production API credentials. The credentials belong in environment variables, never in source files. Configure these in the same PowerShell session before starting Django:

```powershell
$env:MTN_MOMO_BASE_URL = 'https://sandbox.momodeveloper.mtn.com'
$env:MTN_MOMO_TARGET_ENVIRONMENT = 'sandbox'
$env:MTN_MOMO_SUBSCRIPTION_KEY = 'your-collections-subscription-key'
$env:MTN_MOMO_API_USER = 'your-api-user-uuid'
$env:MTN_MOMO_API_KEY = 'your-api-key'
$env:MTN_MOMO_CALLBACK_URL = 'https://your-public-domain/payments/mtn-momo/callback/'
```

Set each space listing’s currency to `RWF`. With credentials present, the booking form requests the customer’s MTN MoMo number and sends an approval prompt; MTN success confirms the booking automatically after the server checks the payment status and amount. The callback endpoint treats MTN’s notification only as a signal and fetches the transaction status directly from MTN before changing a booking. Keep the booking page open during sandbox tests so it can also check the payment status. For production, use the base URL, callback requirements, target environment, and credentials provided during MTN Rwanda onboarding. Run `python manage.py migrate` after updating the project files.

Without MTN credentials, the site retains the existing manual payment review flow. Localhost is not a public callback host, so callback testing needs a publicly reachable development endpoint whose host and scheme follow MTN’s current sandbox setup instructions and match the callback host registered for the API user. The booking page’s status check can also retrieve the final state from MTN while testing.

## Known setup still needed

- MTN MoMo integration is implemented, but it cannot collect live funds until Ijuru Hub completes MTN merchant onboarding and supplies the production credentials and callback configuration. Other payment methods are not included.
- Prices need their confirmed currency code. Enter approved rates and currency on each listing.
- A one-month booking is currently a single booking period, not an automatically renewing subscription.
- Listing photos, descriptions, actual quantities, prices, and policies must be supplied by Ijuru Hub.
- The staff portal is restricted to accounts with staff access; staff share the same operational permissions, while staff account creation and deactivation are limited to superusers. Public visitors can browse without an account; booking requires signup or sign-in.
- Guest hosting, event-specific rules, refunds, and detailed reports are not implemented in this first slice. Notifications appear inside the website; email and SMS delivery are not configured.

## Before production

Set `DJANGO_DEBUG=false`, a unique secret key, production `ALLOWED_HOSTS`, HTTPS, and a managed PostgreSQL `DATABASE_URL`. Configure static/media storage, email delivery, backups and restore, monitoring, domain and OAuth credentials, and the client-selected payment workflow before launch. Do not use the development database password or secret key in production.
