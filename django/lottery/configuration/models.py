from django.contrib.auth.models import User
from django.db import models


class BackgroundTask(models.Model):
    ACTION_CHOICES = (
        ('message', 'Message'),
        ('download', 'Download'),
    )
    STATUS_CHOICES = (
        ('processing', 'Processing'),
        ('info', 'Info'),
        ('download', 'Download'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='processing', choices=STATUS_CHOICES)
    action = models.CharField(max_length=20, default='message', choices=ACTION_CHOICES)
    name = models.CharField(max_length=255)
    content = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created']

    def __str__(self):
        return '{} - {}'.format(self.created, self.name)