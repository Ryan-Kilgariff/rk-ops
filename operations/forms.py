from django import forms
from .models import Task
from .models import HandoverNote, Issue, Task
from django.contrib.auth import get_user_model
from accounts.models import PropertyMembership
User = get_user_model()
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "category",
            "priority",
            "assigned_to",
            "due_at",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Check breakfast stock",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Add any useful details...",
                }
            ),
            "category": forms.Select(
                attrs={"class": "form-control"}
            ),
            "priority": forms.Select(
                attrs={"class": "form-control"}
            ),
            "assigned_to": forms.Select(
                attrs={"class": "form-control"}
            ),
            "due_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
            "status": forms.Select(
                attrs={"class": "form-control"}
            ),
        }
        def __init__(self, *args, property_obj=None, **kwargs):
            super().__init__(*args, **kwargs)
            if property_obj is not None:
                allowed_user_ids = (
                    PropertyMembership.objects
                    .filter(
                        property=property_obj,
                        is_active=True,
                    )
                    .values_list(
                        "user_id",
                        flat=True,
                    )
                )
                self.fields["assigned_to"].queryset = (
                    User.objects
                    .filter(id__in=allowed_user_ids)
                    .order_by(
                        "first_name",
                        "last_name",
                        "username",
                    )
                )
class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = [
            "title",
            "description",
            "location",
            "category",
            "priority",
            "assigned_to",
            "status",
            "resolution_notes",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Leaking tap",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describe the issue...",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Room 204",
                }
            ),
            "category": forms.Select(
                attrs={"class": "form-control"}
            ),
            "priority": forms.Select(
                attrs={"class": "form-control"}
            ),
            "assigned_to": forms.Select(
                attrs={"class": "form-control"}
            ),
            "status": forms.Select(
                attrs={"class": "form-control"}
            ),
            "resolution_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Add resolution details when resolved...",
                }
            ),
        }
        def __init__(self, *args, property_obj=None, **kwargs):
            super().__init__(*args, **kwargs)
            if property_obj is not None:
                allowed_user_ids = (
                    PropertyMembership.objects
                    .filter(
                        property=property_obj,
                        is_active=True,
                    )
                    .values_list(
                        "user_id",
                        flat=True,
                    )
                )
                self.fields["assigned_to"].queryset = (
                    User.objects
                    .filter(id__in=allowed_user_ids)
                    .order_by(
                        "first_name",
                        "last_name",
                        "username",
                    )
                )
class HandoverNoteForm(forms.ModelForm):
    class Meta:
        model = HandoverNote
        fields = [
            "shift",
            "priority",
            "note",
        ]
        widgets = {
            "shift": forms.Select(
                attrs={"class": "form-control"}
            ),
            "priority": forms.Select(
                attrs={"class": "form-control"}
            ),
            "note": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "e.g. Room 206 arriving after 11pm. "
                        "Key prepared at reception."
                    ),
                }
            ),
        }