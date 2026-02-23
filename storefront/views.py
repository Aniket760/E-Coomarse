from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

try:
    import razorpay
    from razorpay.errors import SignatureVerificationError
except ImportError:  # pragma: no cover
    razorpay = None

    class SignatureVerificationError(Exception):
        pass

from .forms import ProfileForm, RegisterForm
from .models import Product, UserProfile

CART_SESSION_KEY = "cart"
PENDING_PAYMENT_SESSION_KEY = "pending_online_payment"
PAYMENT_METHODS = {
    "cod": "Cash on Delivery",
    "online": "Online Payment (UPI / Debit Card / Credit Card)",
}


def _get_cart(request):
    return request.session.get(CART_SESSION_KEY, {})


def _save_cart(request, cart):
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


def _build_cart_items(cart):
    if not cart:
        return [], Decimal("0.00")

    product_ids = [int(product_id) for product_id in cart.keys()]
    products = Product.objects.filter(id__in=product_ids, is_active=True)

    items = []
    total = Decimal("0.00")

    for product in products:
        quantity = cart.get(str(product.id), 0)
        line_total = product.price * quantity
        total += line_total
        items.append(
            {
                "product": product,
                "quantity": quantity,
                "line_total": line_total,
            }
        )

    return items, total


def _get_razorpay_client():
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")

    if not key_id or not key_secret or razorpay is None:
        return None

    return razorpay.Client(auth=(key_id, key_secret))


def _send_order_notification(*, customer_name, customer_email, total, payment_method, payment_id="", username=""):
    notify_to = getattr(settings, "ORDER_NOTIFY_EMAIL", "")
    if not notify_to:
        return

    subject = f"New Order Placed: {customer_name}"
    lines = [
        "A new order has been placed on E-commarse.",
        f"Customer Name: {customer_name}",
        f"Username: {username or 'Guest'}",
        f"Customer Email: {customer_email or 'N/A'}",
        f"Total Amount: Rs {Decimal(total):.2f}",
        f"Payment Method: {payment_method}",
    ]

    if payment_id:
        lines.append(f"Payment ID: {payment_id}")

    send_mail(
        subject=subject,
        message="\n".join(lines),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@ecommarse.local"),
        recipient_list=[notify_to],
        fail_silently=True,
    )


def _get_or_create_user_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _build_saved_address(profile):
    line2 = " ".join(part for part in [profile.city, profile.state, profile.postal_code] if part)
    return "\n".join(part for part in [profile.address.strip(), line2.strip()] if part)


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect("home")
    else:
        form = RegisterForm()

    return render(request, "storefront/register.html", {"page_title": "Register", "form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    next_url = request.GET.get("next") or request.POST.get("next") or reverse("home")
    if not url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        next_url = reverse("home")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
            )
            if user is not None:
                login(request, user)
                messages.success(request, "Logged in successfully.")
                return redirect(next_url)
    else:
        form = AuthenticationForm()

    form.fields["username"].widget.attrs.update(
        {"placeholder": "Email or username", "class": "login-input"}
    )
    form.fields["password"].widget.attrs.update(
        {"placeholder": "Password", "class": "login-input"}
    )

    return render(
        request,
        "storefront/login.html",
        {"page_title": "Login", "form": form, "next": next_url},
    )


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")


@login_required
def profile_view(request):
    profile = _get_or_create_user_profile(request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()

        if form.is_valid():
            form.save()
            if full_name:
                parts = full_name.split(None, 1)
                request.user.first_name = parts[0]
                request.user.last_name = parts[1] if len(parts) > 1 else ""
            request.user.email = email
            request.user.save()
            messages.success(request, "Profile and address saved.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)

    return render(
        request,
        "storefront/profile.html",
        {
            "page_title": "My Account",
            "form": form,
            "full_name": request.user.get_full_name(),
            "email": request.user.email,
        },
    )


def home(request):
    featured_products = Product.objects.filter(is_featured=True, is_active=True)[:6]
    context = {
        "featured_products": featured_products,
        "page_title": "Home",
    }
    return render(request, "storefront/home.html", context)


def products(request):
    product_list = Product.objects.filter(is_active=True)
    return render(
        request,
        "storefront/products.html",
        {"products": product_list, "page_title": "Products"},
    )


def about(request):
    return render(request, "storefront/about.html", {"page_title": "About"})


def contact(request):
    return render(request, "storefront/contact.html", {"page_title": "Contact"})


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    quantity = int(request.POST.get("quantity", 1))
    if quantity < 1:
        quantity = 1

    cart = _get_cart(request)
    key = str(product.id)
    cart[key] = cart.get(key, 0) + quantity
    _save_cart(request, cart)

    messages.success(request, f"Added {product.name} to cart.")
    return redirect(request.POST.get("next") or "products")


@require_POST
def remove_from_cart(request, product_id):
    cart = _get_cart(request)
    key = str(product_id)

    if key in cart:
        del cart[key]
        _save_cart(request, cart)
        messages.info(request, "Item removed from cart.")

    return redirect("cart")


def cart(request):
    cart_data = _get_cart(request)
    items, total = _build_cart_items(cart_data)
    return render(
        request,
        "storefront/cart.html",
        {
            "page_title": "Your Cart",
            "items": items,
            "total": total,
        },
    )


@login_required
def checkout(request):
    cart_data = _get_cart(request)
    items, total = _build_cart_items(cart_data)
    profile = _get_or_create_user_profile(request.user)

    if not items:
        messages.warning(request, "Your cart is empty.")
        return redirect("products")

    if request.method == "POST":
        customer_name = request.POST.get("name", request.user.get_full_name() or request.user.username).strip() or request.user.username
        customer_email = request.POST.get("email", request.user.email).strip()
        customer_address = request.POST.get("address", "").strip()
        payment_method = request.POST.get("payment_method", "cod")

        if customer_address:
            profile.address = customer_address
            profile.save(update_fields=["address", "updated_at"])

        if payment_method not in PAYMENT_METHODS:
            messages.error(request, "Please select a valid payment method.")
            return redirect("checkout")

        if payment_method == "cod":
            _send_order_notification(
                customer_name=customer_name,
                customer_email=customer_email,
                total=total,
                payment_method=PAYMENT_METHODS["cod"],
                username=request.user.username,
            )
            request.session[CART_SESSION_KEY] = {}
            request.session.modified = True
            return render(
                request,
                "storefront/checkout_success.html",
                {
                    "page_title": "Order Confirmed",
                    "customer_name": customer_name,
                    "total": total,
                    "payment_method_label": PAYMENT_METHODS[payment_method],
                },
            )

        client = _get_razorpay_client()
        if not client:
            messages.error(
                request,
                "Online payment is not configured yet. Add Razorpay keys in settings/env.",
            )
            return redirect("checkout")

        amount_subunits = int(total * 100)
        order = client.order.create(
            data={
                "amount": amount_subunits,
                "currency": "INR",
                "receipt": f"order_{request.session.session_key or request.user.username}_{amount_subunits}",
                "notes": {
                    "customer_name": customer_name,
                    "email": customer_email,
                    "username": request.user.username,
                },
            }
        )

        request.session[PENDING_PAYMENT_SESSION_KEY] = {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_address": customer_address,
            "amount": str(total),
            "razorpay_order_id": order["id"],
            "username": request.user.username,
        }
        request.session.modified = True

        return render(
            request,
            "storefront/online_payment.html",
            {
                "page_title": "Online Payment",
                "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                "razorpay_order_id": order["id"],
                "amount_subunits": amount_subunits,
                "total": total,
                "currency": "INR",
                "customer_name": customer_name,
                "customer_email": customer_email,
                "verify_url": request.build_absolute_uri(reverse("payment_verify")),
            },
        )

    return render(
        request,
        "storefront/checkout.html",
        {
            "page_title": "Checkout",
            "items": items,
            "total": total,
            "payment_methods": PAYMENT_METHODS,
            "initial_name": request.user.get_full_name() or request.user.username,
            "initial_email": request.user.email,
            "initial_address": _build_saved_address(profile),
        },
    )


@login_required
@require_POST
def payment_verify(request):
    client = _get_razorpay_client()
    if not client:
        messages.error(request, "Online payment is not configured.")
        return redirect("checkout")

    pending = request.session.get(PENDING_PAYMENT_SESSION_KEY)
    if not pending:
        messages.error(request, "No pending online payment found.")
        return redirect("checkout")

    razorpay_payment_id = request.POST.get("razorpay_payment_id", "")
    razorpay_order_id = request.POST.get("razorpay_order_id", "")
    razorpay_signature = request.POST.get("razorpay_signature", "")

    if razorpay_order_id != pending.get("razorpay_order_id"):
        messages.error(request, "Order mismatch detected. Please try checkout again.")
        return redirect("checkout")

    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
    except SignatureVerificationError:
        return render(
            request,
            "storefront/payment_failed.html",
            {
                "page_title": "Payment Failed",
                "reason": "Payment signature verification failed.",
            },
        )

    _send_order_notification(
        customer_name=pending.get("customer_name") or request.user.username,
        customer_email=pending.get("customer_email", ""),
        total=Decimal(pending.get("amount", "0.00")),
        payment_method=PAYMENT_METHODS["online"],
        payment_id=razorpay_payment_id,
        username=pending.get("username", request.user.username),
    )

    request.session[CART_SESSION_KEY] = {}
    request.session[PENDING_PAYMENT_SESSION_KEY] = {}
    request.session.modified = True

    return render(
        request,
        "storefront/checkout_success.html",
        {
            "page_title": "Order Confirmed",
            "customer_name": pending.get("customer_name") or request.user.username,
            "total": Decimal(pending.get("amount", "0.00")),
            "payment_method_label": PAYMENT_METHODS["online"],
            "payment_id": razorpay_payment_id,
        },
    )
