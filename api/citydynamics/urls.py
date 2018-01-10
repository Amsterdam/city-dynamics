"""ibprojecten URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include

# Added to open Files on dev server
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from citydynamics.api.views import DrukteindexViewSet
from citydynamics.api.views import RecentIndexViewSet

router = DefaultRouter()
router.register('drukteindex', DrukteindexViewSet, 'drukteindex')
router.register('recentmeasures', RecentIndexViewSet, 'recentmeasures')

urlpatterns = router.urls

urlpatterns = [
    url(r'^citydynamics/', include(router.urls)),
    url(r'^status/', include('health.urls', namespace='health')),
]


# To open Files on development server add this:
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)