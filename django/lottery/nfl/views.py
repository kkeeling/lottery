from django.shortcuts import get_object_or_404, render

from . import models

def slate_build(request):
    build_id = request.GET.get('build')
    build = get_object_or_404(models.SlateBuild, pk=build_id)

    data = {
        'build': build
    }
    return render(request, 'admin/nfl/build.html', data)
