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

2. **Environment variables** (create `.env` file):
   ```env
   SECRET_KEY=your-secret-key
   DEBUG=True
   DB_NAME=photocourses
   DB_USER=postgres
   DB_PASSWORD=your-password
   DB_HOST=localhost
   DB_PORT=5432
   STRIPE_PUBLIC_KEY=pk_test_...
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
   DEFAULT_FROM_EMAIL=noreply@photocourses.com
   ```

3. **Run migrations:**
   ```bash
   python manage.py makemigrations
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

- Course list: `/`
- Course detail (with city): `/photography-courses/<city>/<course-slug>/`
- Course detail (fallback): `/photography-courses/<course-slug>/`

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
