from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include

from app.views import MasternodeMonitor

urlpatterns = [
    path('mnmonitor/', MasternodeMonitor.as_view(), name='mn_monitor'),
    path('admin/', admin.site.urls),
    path('preferences/', include('dynamic_preferences.urls', namespace='dp')),
]

urlpatterns += staticfiles_urlpatterns()
