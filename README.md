# Photography Course Booking Platform

A mobile-first, SEO-critical Django-based photography course booking platform with franchise management and Stripe payment integration.

## Features

- **Server-rendered HTML** for all public pages (SEO-critical)
- **JSON-LD structured data** (schema.org) for courses, instances, offers, and FAQs
- **Franchise model** with multi-admin permission handling
- **Stripe payment integration** (Checkout Sessions & Payment Intents)
- **Role-based access control**: Platform Admins, Franchise Owners, Staff, Customers
- **SEO-friendly URLs**: `/photography-courses/<city>/<course-slug>/`

## Project Structure

```
going-digital/
├── photocourses/          # Main Django project
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                  # Core app (User model, permissions)
├── courses/               # Courses app (Course, CourseInstance, Instructor)
├── bookings/              # Bookings app (Booking model)
├── payments/              # Payments app (Stripe integration)
├── franchises/            # Franchises app (Franchise, Location)
├── templates/             # Django templates (server-rendered)
│   ├── base.html
│   └── courses/
│       ├── course_list.html
│       └── course_detail.html
└── static/                # Static files (CSS, JS for React components)
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment variables** (create `.env`; database is **MySQL/MariaDB** only):
   ```env
   SECRET_KEY=your-secret-key
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1

   DB_NAME=goingdigital
   DB_USER=root
   DB_PASSWORD=your-mysql-password
   DB_HOST=localhost
   DB_PORT=3306

   STRIPE_PUBLIC_KEY=pk_test_...
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...

   EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
   DEFAULT_FROM_EMAIL=noreply@example.com
   CONTACT_EMAIL=info@goingdigital.co.uk
   GOING_DIGITAL_FACEBOOK_GROUP_URL=https://www.facebook.com/groups/your-going-digital-group

   # Optional passcode gate for staging/dev (session cookie).
   # Defaults to enabled when DEBUG=True. For staging with DEBUG=False, set:
   # DEV_SITE_ACCESS_ENABLED=True
   # DEV_SITE_PASSWORD=your-secret-passcode
   ```
   For production: `DEBUG=False`, real `SECRET_KEY`, set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (HTTPS origins), and use a transactional email backend. Behind a reverse proxy, set `USE_PROXY_SSL=True`. See `photocourses/settings.py` (secure cookies and HSTS apply when `DEBUG=False`). If you want staging locked behind a passcode while keeping `DEBUG=False`, set `DEV_SITE_ACCESS_ENABLED=True` and `DEV_SITE_PASSWORD`.

3. **Database:** create the MySQL database, then migrate. Details: [MYSQL_SETUP.md](MYSQL_SETUP.md).
   ```bash
   python manage.py migrate
   ```

4. **Create superuser:**
   ```bash
   python manage.py createsuperuser
   ```

5. **Run development server:**
   ```bash
   python manage.py runserver
   ```
   Use **`http://127.0.0.1:8000/`** (HTTP only; `runserver` does not speak TLS). If you see HTTPS errors in the log, open `http://` explicitly or clear HSTS for `localhost`. With `DEBUG=False` locally, disable `SECURE_SSL_REDIRECT` or you may be redirected to `https://` and the dev server will fail.

6. **Legacy data:** import a MySQL dump with the `mysql` client if needed (see [MYSQL_SETUP.md](MYSQL_SETUP.md)).

## Staging/Production Deployment (Nginx + Gunicorn)

This repo includes deployment templates for running Django behind Gunicorn and Nginx on `80/443`.

### Deployment files in this repo
- Nginx vhost template: `deploy/nginx/staging.goingdigital.co.uk.conf`
- systemd service template: `deploy/systemd/goingdigital.service`
- production env template: `deploy/env/.env.production.example`

### Recommended deployment flow
1. **Install dependencies and collect static:**
   ```bash
   pip install -r requirements.txt
   python manage.py collectstatic --noinput
   ```

2. **Create `.env` from template** and fill real secrets/credentials:
   - copy `deploy/env/.env.production.example` to project root as `.env`
   - keep comma-separated lists with no extra spaces

3. **Install Gunicorn as a service:**
   - copy `deploy/systemd/goingdigital.service` to `/etc/systemd/system/goingdigital.service`
   - update `WorkingDirectory`, `EnvironmentFile`, and `ExecStart` paths for your server
   - then run:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now goingdigital
   sudo systemctl status goingdigital
   ```

4. **Install Nginx vhost:**
   - copy `deploy/nginx/staging.goingdigital.co.uk.conf` to `/etc/nginx/sites-available/staging.goingdigital.co.uk`
   - enable it with a symlink in `/etc/nginx/sites-enabled/`
   - disable the default vhost if it conflicts
   - then run:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

5. **Issue TLS certificate (Let's Encrypt):**
   ```bash
   sudo certbot --nginx -d staging.goingdigital.co.uk
   ```

6. **Verify**
   ```bash
   curl -I http://staging.goingdigital.co.uk
   curl -I https://staging.goingdigital.co.uk
   ```

If the Nginx welcome page appears, your staging vhost is not enabled or the default vhost is still taking precedence.

## Models

### Core Models
- **User**: Custom user with roles (platform_admin, franchise_owner, staff, customer)

### Franchise Models
- **Franchise**: Franchise entity owned by a franchise owner
- **Location**: Physical location where courses are held

### Course Models
- **Course**: Abstract course definition (reusable)
- **CourseInstance**: Scheduled course at specific location and date
- **Instructor**: Instructor profile linked to User
- **FAQ**: FAQ entries for FAQPage schema

### Booking Models
- **Booking**: Course booking linked to payment and course instance

### Payment Models
- **Payment**: Stripe payment record

## SEO & Structured Data

Every course detail page includes:
- **JSON-LD schema.org** structured data:
  - Course
  - CourseInstance
  - Offer
  - FAQPage (if FAQs exist)
- **Semantic HTML** structure:
  - H1: Course name
  - Course description
  - Key facts (date, location, price)
  - "What you'll learn"
  - Audience
  - Instructor
  - FAQs

## URL Structure

- Course list: `/photography-courses/`
- Course overview: `/photography-courses/<course-slug>/`
- Course at venue: `/photography-courses/<course-slug>/<location-slug>/` (e.g. `/photography-courses/get-off-auto/cardiff-docks/`)
- Venue page: `/photography-courses/venues/<location-slug>/` (e.g. `/photography-courses/venues/cardiff-docks`)
- Redirects: `/photography-workshops/` and all paths under it (every course overview and course-at-venue URL) **301** to the matching `/photography-courses/` URL via `PhotographyWorkshopsRedirectMiddleware`. The list page is also in the **Redirect** table (Django admin → Website → Redirects). Other one-off redirects can be added there too.
- Legacy: `/courses/`, `/courses/<slug>/`, and old venue URL format redirect to the above

## Permissions

### Platform Admins
- Full access to all franchises, locations, courses, bookings
- Can create franchises and assign owners
- Access via `request.user.is_platform_admin`

### Franchise Owners
- Can manage only their own franchises, locations, courses, instructors
- Can view bookings for their courses
- Access via `request.user.is_franchise_owner`
- Permission check: `request.user.has_franchise_access(franchise)`

### Mixins
- `FranchiseOwnerMixin`: Restrict views to franchise owners (with optional franchise filtering)
- `PlatformAdminMixin`: Restrict views to platform admins only

## Payments

Stripe integration includes:
- **Checkout Sessions** for booking payments
- **Webhooks** for payment status updates
- Automatic booking confirmation on successful payment
- Email notifications (booking confirmation, payment success)

**Admin light/dark mode:** Jazzmin uses your OS setting (`prefers-color-scheme`). Light mode uses the default theme; dark mode loads Bootswatch **darkly**. Custom dashboard styles are in `static/admin/css/jazzmin-admin.css`.

**Local dev — payment stays `pending`:** Checkout creates a `pending` payment; it moves to `succeeded` when Stripe notifies `/payments/webhook/` or when the customer lands on `/payments/success/` (the success page confirms with Stripe automatically). For webhooks on localhost, use [Stripe CLI](https://stripe.com/docs/stripe-cli): `stripe listen --forward-to http://127.0.0.1:8000/payments/webhook/` and set `STRIPE_WEBHOOK_SECRET` from the CLI output. If Stripe CLI shows **302** responses, the dev passcode gate was blocking the webhook — `/payments/webhook/` is exempt; restart `runserver` after pulling. Ensure `STRIPE_WEBHOOK_SECRET` matches the `whsec_` from the running `stripe listen` session.

**Stripe `Permission denied` / network error on Windows:** If checkout returns a Stripe connection error mentioning `Permission denied`, check whether `SSLKEYLOGFILE` is set (common when using Cursor or TLS-debugging tools). It may point at a path Python cannot write, which breaks all HTTPS. Unset it in your terminal (`Remove-Item Env:SSLKEYLOGFILE` in PowerShell) and restart `runserver`. This project also clears invalid `\\?\Volume{...}` keylog paths at startup in `photocourses/settings.py`.

## React Integration

React is used only for **progressive enhancement**:
- Search filters (enhanced client-side filtering)
- Booking UI (interactive booking forms)
- Admin dashboards (data visualization)

All public pages are **server-rendered Django templates** for SEO.

## Next Steps

1. Add React components for progressive enhancement
2. Implement email templates (HTML)
3. Add admin dashboard views for franchise owners
4. Implement course search with Elasticsearch/Algolia (optional)
5. Add course reviews/ratings
6. Implement booking cancellation and refunds
