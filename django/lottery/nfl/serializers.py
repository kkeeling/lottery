from django.db.models import ObjectDoesNotExist
from rest_framework import serializers

from . import models


class SlatePlayerProjectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SlatePlayerProjection
        fields = (
            'id',
            'projection',
            'floor',
            'ceiling',
            'zscore',
            'stdev',
            'ownership_projection',
            'adjusted_opportunity',
            'ao_zscore',
            'value',
            's20',
            'median',
            's75',
            's90',
        )


class SlatePlayerRawProjectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SlatePlayerRawProjection
        fields = '__all__'


class SlateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Slate
        depth = 1
        fields = (
            'id',
            'name',
            'week',
            'site',
        )


class SlateGameSerializer(serializers.ModelSerializer):
    display_text = serializers.SerializerMethodField()

    class Meta:
        model = models.SlateGame
        # depth = 1
        fields = (
            'id',
            # 'game',
            'zscore',
            'display_text',
        )

    def get_display_text(self, obj):
        return f'{obj.game.away_team} @ {obj.game.home_team}'


class SlatePlayerSerializer(serializers.ModelSerializer):
    slate_game = SlateGameSerializer()
    projection = SlatePlayerProjectionSerializer()
    # raw_projections = SlatePlayerRawProjectionSerializer(many=True)

    class Meta:
        model = models.SlatePlayer
        fields = (
            'player_id',
            'name',
            'csv_name',
            'salary',
            'site_pos',
            'team',
            'fantasy_points',
            'slate_game',
            'projection',
            # 'raw_projections',
        )

    def get_slate_game(self, obj):
        return f'{obj.slate_game.game.away_team} @ {obj.slate_game.game.home_team}'


class BuildPlayerProjectionSerializer(serializers.ModelSerializer):
    slate_player = SlatePlayerSerializer(required=False)
    etr_projection = serializers.SerializerMethodField()
    awesemo_projection = serializers.SerializerMethodField()
    rg_projection = serializers.SerializerMethodField()
    etr_ownership = serializers.SerializerMethodField()
    awesemo_ownership = serializers.SerializerMethodField()
    rg_ownership = serializers.SerializerMethodField()

    class Meta:
        model = models.BuildPlayerProjection
        fields = (
            'id', 
            'slate_player', 
            'projection',
            'etr_projection',
            'awesemo_projection',
            'rg_projection',
            'etr_ownership',
            'awesemo_ownership',
            'rg_ownership',
            'value',
            'adjusted_opportunity',
            'rb_group_value',
            'rb_group',
            'balanced_projection',
            'balanced_value',
            'in_play',
            'stack_only',
            'qb_stack_only',
            'opp_qb_stack_only',
            'disallow_ministack',
            'use_as_antileverage',
            'exposure',
        )

    def get_etr_projection(self, obj):
        try:
            raw_proj = obj.slate_player.raw_projections.get(projection_site='etr')
            return raw_proj.projection
        except ObjectDoesNotExist:
            return None

    def get_awesemo_projection(self, obj):
        try:
            raw_proj = obj.slate_player.raw_projections.get(projection_site='awesemo')
            return raw_proj.projection
        except ObjectDoesNotExist:
            return None

    def get_rg_projection(self, obj):
        try:
            raw_proj = obj.slate_player.raw_projections.get(projection_site='rg')
            return raw_proj.projection
        except ObjectDoesNotExist:
            return None

    def get_etr_ownership(self, obj):
        try:
            raw_proj = obj.slate_player.raw_projections.get(projection_site='etr')
            return raw_proj.ownership_projection
        except ObjectDoesNotExist:
            return None

    def get_awesemo_ownership(self, obj):
        try:
            raw_proj = obj.slate_player.raw_projections.get(projection_site='awesemo')
            return raw_proj.ownership_projection
        except ObjectDoesNotExist:
            return None

    def get_rg_ownership(self, obj):
        try:
            raw_proj = obj.slate_player.raw_projections.get(projection_site='rg')
            return raw_proj.ownership_projection
        except ObjectDoesNotExist:
            return None


class SlateBuildSerializer(serializers.ModelSerializer):
    slate = SlateSerializer()
    projections = BuildPlayerProjectionSerializer(many=True)
    class Meta:
        model = models.SlateBuild
        depth = 1
        fields = (
            'slate',
            'configuration',
            'in_play_criteria',
            'total_lineups',
            'status',
            'projections_ready',
            'construction_ready',
            'pct_complete',
            'error_message',
            'projections',
            'stacks',
            'lineups',
            'groups',
        )
