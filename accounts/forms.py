from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import PropertyMembership
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