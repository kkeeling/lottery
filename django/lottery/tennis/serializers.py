from django.db.models import ObjectDoesNotExist
from rest_framework import serializers

from . import models


class CsvUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

# class SaveFileSerializer(serializers.Serializer):
    
#     class Meta:
#         model = File
#         fields = "__all__"