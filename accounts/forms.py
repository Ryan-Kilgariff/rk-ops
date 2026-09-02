from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import (
    OrganisationInvitation,
    PropertyMembership,
)
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import OrganisationInvitation
User = get_user_model()
class OrganisationInvitationForm(forms.ModelForm):
    class Meta:
        model = OrganisationInvitation
        fields = [
            "email",
            "role",
            "property_role",
            "properties",
        ]
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "name@example.com",
                }
            ),
            "role": forms.Select(
                attrs={"class": "form-control"}
            ),
            "property_role": forms.Select(
                attrs={"class": "form-control"}
            ),
            "properties": forms.CheckboxSelectMultiple(),
        }
    def __init__(
        self,
        *args,
        organisation=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if organisation:
            self.fields["properties"].queryset = (
                organisation.properties
                .filter(is_active=True)
                .order_by("name")
            )
        else:
            self.fields["properties"].queryset = (
                self.fields["properties"]
                .queryset.none()
            )
class InvitationSignupForm(forms.ModelForm):
    password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
            }
        ),
        label="Password",
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
            }
        ),
        label="Confirm password",
    )
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
        }
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if (
            password1
            and password2
            and password1 != password2
        ):
            self.add_error(
                "password2",
                "Passwords do not match.",
            )
        if password1:
            try:
                validate_password(password1)
            except forms.ValidationError as error:
                self.add_error(
                    "password1",
                    error,
                )
        return cleaned_data
User = get_user_model()
class TeamMemberCreateForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "staff@example.com",
            }
        ),
    )
    first_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
            }
        ),
    )
    last_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
            }
        ),
    )
    role = forms.ChoiceField(
        choices=PropertyMembership.Role.choices,
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
    )
    job_title = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Reception Supervisor",
            }
        ),
    )
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "job_title",
            "password1",
            "password2",
        ]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update(
            {"class": "form-control"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": "form-control"}
        )
class MembershipEditForm(forms.ModelForm):
    class Meta:
        model = PropertyMembership
        fields = [
            "role",
            "job_title",
            "is_active",
        ]
        widgets = {
            "role": forms.Select(
                attrs={"class": "form-control"}
            ),
            "job_title": forms.TextInput(
                attrs={"class": "form-control"}
            ),
        }
class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="Email address",
    )
    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
        )
        help_texts = {
            "username": "",
        }
    def clean_email(self):
        email = (
            self.cleaned_data["email"]
            .strip()
            .lower()
        )
        if User.objects.filter(
            email__iexact=email
        ).exists():
            raise forms.ValidationError(
                "An account with this email "
                "already exists."
            )
        return email
    def save(self, commit=True):
        user = super().save(
            commit=False
        )
        user.email = (
            self.cleaned_data["email"]
            .strip()
            .lower()
        )
        if commit:
            user.save()
        return user
    def clean_username(self):
        username = (
            self.cleaned_data["username"]
            .strip()
        )
        if User.objects.filter(
            username__iexact=username
        ).exists():
            raise forms.ValidationError(
                "An account with this username already exists."
            )
        return username