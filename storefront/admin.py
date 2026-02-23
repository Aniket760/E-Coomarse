from django.contrib import admin

from .models import Product, UserProfile


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_featured", "is_active", "updated_at")
    list_filter = ("is_featured", "is_active")
    search_fields = ("name", "description")
    fields = ("name", "price", "description", "image", "is_featured", "is_active")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "city", "state", "updated_at")
    search_fields = ("user__username", "user__email", "phone", "city", "state")
