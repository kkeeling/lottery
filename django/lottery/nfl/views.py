from django.db.models.aggregates import Count
from django.db.models.expressions import ExpressionWrapper
from django.db.models.fields import FloatField
from django.db.models import F, Case, When
from django.shortcuts import get_object_or_404, render
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets

from . import models, serializers


def slate_build(request):
    build_id = request.GET.get('build')
    build = get_object_or_404(models.SlateBuild, pk=build_id)
    qbs = build.projections.filter(
        in_play=True,
        slate_player__site_pos='QB'
    )
    wrs = build.projections.filter(
        in_play=True,
        slate_player__site_pos='WR'
    )
    tes = build.projections.filter(
        in_play=True,
        slate_player__site_pos='TE'
    )
    dsts = build.projections.filter(
        in_play=True,
        slate_player__site_pos='D' if build.slate.site == 'fanduel' else 'DST'
    )

    data = {
        'build': build,
        'qbs': qbs,
        'wrs': wrs,
        'tes': tes,
        'dsts': dsts
    }
    return render(request, 'admin/nfl/build.html', data)


class SlateBuildViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.SlateBuildSerializer
    queryset = models.SlateBuild.objects.all()
    authentication_classes = []
    permission_classes = []

    @action(methods=['get'], detail=True, permission_classes=[])
    def projections(self, request, pk=None):
        build = models.SlateBuild.objects.get(id=pk)
        queryset = build.projections.filter(projection__gt=4.99)
        serializer = serializers.BuildPlayerProjectionSerializer(build.projections.all(), many=True)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = serializers.BuildPlayerProjectionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = serializers.BuildPlayerProjectionSerializer(queryset, many=True)
        return Response(serializer.data)


class BuildPlayerProjectionViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.BuildPlayerProjectionSerializer
    queryset = models.BuildPlayerProjection.objects.all()
    authentication_classes = []
    permission_classes = []


class FindWinnerBuildViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.FindWinnerBuildSerializer
    queryset = models.FindWinnerBuild.objects.all()
    authentication_classes = []
    permission_classes = []
    pagination_class = None

    @action(methods=['get'], detail=True, permission_classes=[])
    def lineups(self, request, pk=None):
        build = models.FindWinnerBuild.objects.get(id=pk)

        if build.slate.is_showdown:
            lineups = build.winning_sd_lineups.all().order_by('-rating')[:20]
            serializer = serializers.WinningSDLineupSerializer(lineups, many=True)
        else:
            lineups = build.winning_lineups.all().order_by('-rating')[:20]
            serializer = serializers.WinningLineupSerializer(lineups, many=True)

        return Response(serializer.data)
