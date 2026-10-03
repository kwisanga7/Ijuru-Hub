from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from coworking import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/register/", views.register, name="register"),
    path("", include("coworking.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
