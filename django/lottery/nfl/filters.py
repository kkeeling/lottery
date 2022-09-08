import django_filters

from . import models


class SlateLineupFilter(django_filters.FilterSet):
    class Meta:
        model = models.SlateLineup
        fields = {
            'total_salary': ['gte', 'gt', 'lt', 'lte'],
        }
