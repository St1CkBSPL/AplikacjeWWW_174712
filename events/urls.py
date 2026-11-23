from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import cbv_views, views
from .viewsets import CategoryViewSet, EventViewSet, TagViewSet

app_name = 'events'

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'events', EventViewSet, basename='event')
router.register(r'tags', TagViewSet, basename='tag')

urlpatterns = [
    # 1. Tradycyjne widoki HTML (MVT) z Lab 3
    path('', views.event_list, name='event-list'),
    path('event/<slug:slug>/', views.event_detail, name='event-detail'),
    path('category/<slug:category_slug>/', views.events_by_category, name='events-by-category'),

    # 2. Endpointy widoków generycznych CBV (porównawczo)
    path('api/cbv/events/', cbv_views.EventListCreateGenericView.as_view(), name='generic-event-list'),
    path('api/cbv/events/<int:pk>/', cbv_views.EventRetrieveUpdateDestroyGenericView.as_view(), name='generic-event-detail'),

    # 3. Profesjonalne REST API oparte na ViewSets i Routerze osadzone pod prefiksem wersji v1
    path('api/v1/summary/', cbv_views.PlatformSummaryAPIView.as_view(), name='api-platform-summary'),
    path('api/v1/', include((router.urls, 'v1'))),
]
