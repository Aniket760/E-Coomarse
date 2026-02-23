from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import UserProfile


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "password1", "password2")
        help_texts = {
            "username": "",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"placeholder": "Choose username"})
        self.fields["password1"].widget.attrs.update({"placeholder": "Create password"})
        self.fields["password2"].widget.attrs.update({"placeholder": "Confirm password"})

        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""

        self.fields["username"].error_messages.update(
            {
                "required": "Please enter a username.",
                "unique": "This username already exists. Try another.",
                "invalid": "Use only letters, numbers, and @/./+/-/_.",
            }
        )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("phone", "address", "city", "state", "postal_code")
        widgets = {
            "phone": forms.TextInput(attrs={"placeholder": "Phone number"}),
            "address": forms.Textarea(attrs={"rows": 3, "placeholder": "Address"}),
            "city": forms.TextInput(attrs={"placeholder": "City"}),
            "state": forms.TextInput(attrs={"placeholder": "State"}),
            "postal_code": forms.TextInput(attrs={"placeholder": "Postal code"}),
        }
