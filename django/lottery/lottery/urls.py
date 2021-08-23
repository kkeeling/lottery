from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic.base import RedirectView
from rest_framework.routers import DefaultRouter


import django.contrib.auth.views
import nfl.views

urlpatterns = []
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

router = DefaultRouter()

urlpatterns += [
    url(r'^admin_tools/', include('admin_tools.urls')),
    url(r'^favicon\.ico$', RedirectView.as_view(url=settings.STATIC_URL + 'img/favicon.ico', permanent=True)),
    url(r'^grappelli/', include('grappelli.urls')), # grappelli URLS
    url(r'^admin/nfl/slate_build/', nfl.views.slate_build, name='slate_build'),
    url(r'^admin/', admin.site.urls),
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

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]
