from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from api.views import health, recipe_short_link

urlpatterns = [
    path('health/', health),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('s/<int:pk>/', recipe_short_link, name='recipe-short-link'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
