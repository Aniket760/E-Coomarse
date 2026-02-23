# E-commarse Django Website

This repository contains a Django e-commerce starter with:
- Database-backed product catalog
- Django admin product management
- Product image upload
- Session-based cart
- Checkout flow
- Razorpay online payment (UPI / debit card / credit card)

## Setup

1. Create virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure Razorpay keys:

```bash
export RAZORPAY_KEY_ID="rzp_test_xxxxx"
export RAZORPAY_KEY_SECRET="your_secret"
export ORDER_NOTIFY_EMAIL="you@example.com"
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Create admin user:

```bash
python manage.py createsuperuser
```

6. Start development server:

```bash
python manage.py runserver
```

Open: http://127.0.0.1:8000/

## Routes

- `/` Home (featured DB products)
- `/products/` Product listing from DB
- `/cart/` Cart
- `/checkout/` Checkout
- `/payment/verify/` Razorpay signature verification callback
- `/about/` About
- `/contact/` Contact
- `/admin/` Admin dashboard

## Online payment notes

- `Cash on Delivery` works without payment gateway setup.
- `Online Payment` requires Razorpay keys.
- In test mode, use Razorpay test UPI/card methods.
- For real customer payments, use a live Razorpay account with completed KYC and live API keys.
- New order notifications are sent to `ORDER_NOTIFY_EMAIL`.

## Add products from admin

1. Go to `/admin/` and log in with superuser credentials.
2. Open **Products** and add items.
3. Upload an image in the `image` field (optional but supported).
4. Mark `is_active=True` to show in listing.
5. Mark `is_featured=True` to show on home page.
