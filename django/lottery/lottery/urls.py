from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic.base import RedirectView
from rest_framework.routers import DefaultRouter


import nfl.views
import configuration.views

from .admin import lottery_admin_site

urlpatterns = []
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

router = DefaultRouter()
router.register(r'backgroundtask', configuration.views.BackgroundTaskViewSet, basename='backgroundtask')

urlpatterns += [
    url(r'^admin_tools/', include('admin_tools.urls')),
    url(r'^favicon\.ico$', RedirectView.as_view(url=settings.STATIC_URL + 'img/favicon.ico', permanent=True)),
    url(r'^grappelli-docs/', include('grappelli.urls_docs')),
    url(r'^grappelli/', include('grappelli.urls')), # grappelli URLS
    url(r'^admin/nfl/slate_build/', nfl.views.slate_build, name='slate_build'),
    url(r'^admin/', lottery_admin_site.urls),
    url(r'^api/', include(router.urls)),
    # include URLs
    url('^', include('django.contrib.auth.urls')),
]

# serve media when running via runserver
if settings.DEFAULT_HOST == 'localhost:8000':
    from django.views.static import serve

    urlpatterns += [
        url(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
    ]
