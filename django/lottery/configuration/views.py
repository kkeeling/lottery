from rest_framework import viewsets

from . import models, serializers

class BackgroundTaskViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.BackgroundTaskSerializer

    def initial(self, request, *args, **kwargs):
        self.current_user = request.user
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        try:
            return models.BackgroundTask.objects.filter(user=self.current_user)
        except:
            return None