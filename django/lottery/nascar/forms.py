from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from . import models

class SlateBuildForm(forms.ModelForm):
    class Meta:
        model = models.SlateBuild
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)

        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.filter(id=request.user.id)
        self.fields['user'].initial = request.user
