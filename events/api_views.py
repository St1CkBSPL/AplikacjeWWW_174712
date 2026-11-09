from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Category, Event, Tag
from .serializers import (
    CategorySerializer,
    EventListSerializer,
    EventModelSerializer,
    TagSerializer,
)


def _optimized_events():
    return Event.objects.select_related('category', 'organizer').prefetch_related('tags')


@api_view(['GET', 'POST'])
def event_list_create_api(request):
    """
    GET: Zwraca listę wydarzeń (opcjonalnie przefiltrowanych po kategorii, tagu i cenie).
    POST: Tworzy nowe wydarzenie po przejściu walidacji.
    """
    if request.method == 'GET':
        events = _optimized_events().all()

        category_id = request.query_params.get('category')
        if category_id:
            events = events.filter(category_id=category_id)

        tag_slug = request.query_params.get('tag')
        if tag_slug:
            events = events.filter(tags__slug=tag_slug).distinct()

        free = request.query_params.get('free')
        if free and free.lower() == 'true':
            events = events.filter(price=0)

        serializer = EventListSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = EventModelSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def event_detail_api(request, pk):
    """
    GET: Szczegóły pojedynczego wydarzenia.
    PUT: Pełna aktualizacja wydarzenia (wymaga wszystkich pól wymaganych).
    PATCH: Częściowa aktualizacja wybranych pól wydarzenia (partial=True).
    DELETE: Usunięcie wydarzenia.
    """
    event = get_object_or_404(_optimized_events(), pk=pk)

    if request.method == 'GET':
        serializer = EventModelSerializer(event)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'DELETE':
        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    partial = request.method == 'PATCH'
    serializer = EventModelSerializer(event, data=request.data, partial=partial)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
def category_list_api(request):
    """GET: lista kategorii. POST: utworzenie nowej kategorii."""
    if request.method == 'GET':
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = CategorySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def category_detail_api(request, pk):
    """Szczegóły, aktualizacja i usuwanie kategorii z ochroną niepustych rekordów."""
    category = get_object_or_404(Category, pk=pk)

    if request.method == 'GET':
        serializer = CategorySerializer(category)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'DELETE':
        if category.events.exists():
            return Response(
                {"error": "Nie można usunąć kategorii, do której są przypisane wydarzenia."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    partial = request.method == 'PATCH'
    serializer = CategorySerializer(category, data=request.data, partial=partial)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
def tag_list_create_api(request):
    """GET: alfabetyczna lista tagów. POST: utworzenie tagu."""
    if request.method == 'GET':
        tags = Tag.objects.all().order_by('name')
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = TagSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
