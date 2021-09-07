from rest_framework import serializers
from . import models

class BackgroundTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BackgroundTask
        fields = ('id', 'action', 'name', 'status', 'content', 'link')
