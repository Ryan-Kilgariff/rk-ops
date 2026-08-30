from django import forms
from .models import Property
class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            "name",
            "address_line_1",
            "address_line_2",
            "town_city",
            "postcode",
            "phone",
            "email",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "address_line_1": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "address_line_2": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "town_city": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "postcode": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control"}
            ),
            "is_active": forms.CheckboxInput(),
        }