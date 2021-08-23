from django.db.models.aggregates import Count
from django.db.models.expressions import ExpressionWrapper
from django.db.models.fields import FloatField
from django.db.models import F, Case, When
from django.shortcuts import get_object_or_404, render

from . import models

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
