import math

from django.contrib import admin, messages

from celery import chain, group, chord
from configuration.models import BackgroundTask

from . import models
from . import tasks


@admin.register(models.Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        'list_display_name',
        'draftkings_name',
        'fanduel_name',
        'yahoo_name',
        'draftkings_player_id',
        'fanduel_player_id',
        'yahoo_player_id',
    )
    search_fields = [
        'draftkings_name',
        'fanduel_name',
        'yahoo_name',
        'draftkings_player_id',
        'fanduel_player_id',
        'yahoo_player_id',
    ]

    def list_display_name(self, obj):
        return f'{obj}'
    list_display_name.short_description = 'Player'
    list_display_name.admin_order_field = 'draftkings_name'


@admin.register(models.Simulation)
class SimulationAdmin(admin.ModelAdmin):
    list_display = (
        'list_display_name',
        'sim_type',
        'player_outcomes',
    )

    def list_display_name(self, obj):
        return f'{obj}'
    list_display_name.short_description = 'Simulation'
