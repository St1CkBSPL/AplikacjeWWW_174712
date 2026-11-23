from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Category, Event, Tag
from .serializers import (
    CategorySerializer,
    EventListSerializer,
    EventModelSerializer,
    TagSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    """Kompletny zestaw operacji CRUD dla kategorii wydarzeń."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def destroy(self, request, *args, **kwargs):
        """Blokada usunięcia kategorii, która posiada przypisane wydarzenia."""
        category = self.get_object()
        if category.events.exists():
            return Response(
                {"error": "Nie można usunąć kategorii, do której są przypisane wydarzenia."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def events(self, request, pk=None):
        """Zwraca opublikowane wydarzenia przypisane do danej kategorii."""
        category = self.get_object()
        events = (
            category.events.filter(is_published=True)
            .select_related('category', 'organizer')
            .prefetch_related('tags')
        )
        serializer = EventListSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TagViewSet(viewsets.ModelViewSet):
    """Kompletny zestaw operacji CRUD dla tagów tematycznych."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer

    @action(detail=True, methods=['get'])
    def events(self, request, pk=None):
        """Zwraca opublikowane wydarzenia oznaczone danym tagiem."""
        tag = self.get_object()
        events = (
            tag.events.filter(is_published=True)
            .select_related('category', 'organizer')
            .prefetch_related('tags')
        )
        serializer = EventListSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EventViewSet(viewsets.ModelViewSet):
    """
    Kompletny zestaw operacji CRUD dla wydarzeń z dynamicznym wyborem serializatora
    oraz niestandardowymi akcjami biznesowymi.
    """

    queryset = (
        Event.objects.select_related('category', 'organizer')
        .prefetch_related('tags')
        .all()
    )

    def get_serializer_class(self):
        """
        Dla listy wydarzeń oraz akcji zwracających kolekcje używamy lżejszego EventListSerializer.
        Dla szczegółów (retrieve) oraz zapisu używamy EventModelSerializer.
        """
        if self.action in ['list', 'upcoming', 'free_events']:
            return EventListSerializer
        return EventModelSerializer

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Zwraca wyłącznie opublikowane wydarzenia, które odbędą się w przyszłości."""
        upcoming_events = (
            self.get_queryset()
            .filter(is_published=True, date__gte=timezone.now())
            .order_by('date')
        )
        serializer = self.get_serializer(upcoming_events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def free_events(self, request):
        """Zwraca wyłącznie opublikowane, bezpłatne wydarzenia."""
        free = self.get_queryset().filter(is_published=True, price=0)
        serializer = self.get_serializer(free, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def publish_toggle(self, request, pk=None):
        """Przełącza status publikacji wydarzenia (is_published)."""
        event = self.get_object()
        event.is_published = not event.is_published
        event.save(update_fields=['is_published', 'updated_at'])
        status_text = "opublikowane" if event.is_published else "ukryte"
        return Response(
            {
                "message": f"Wydarzenie '{event.title}' zostało {status_text}.",
                "is_published": event.is_published,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post', 'delete'], url_path='manage-tags')
    def manage_tags(self, request, pk=None):
        """Dopinanie (POST) lub odpinanie (DELETE) pojedynczego tagu od wydarzenia."""
        event = self.get_object()
        tag_id = request.data.get('tag_id')
        if tag_id is None or tag_id == '':
            return Response(
                {"error": "Pole 'tag_id' jest wymagane."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tag = get_object_or_404(Tag, pk=tag_id)
        if request.method == 'POST':
            event.tags.add(tag)
        else:
            event.tags.remove(tag)

        serializer = TagSerializer(event.tags.all(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Tworzy kopię wydarzenia jako szkic przesunięty o 7 dni do przodu."""
        original = self.get_object()
        base_slug = f"{original.slug}-kopia-{int(timezone.now().timestamp())}"
        slug = base_slug
        counter = 1
        while Event.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        new_event = Event.objects.create(
            title=f"{original.title} (Kopia)",
            slug=slug,
            category=original.category,
            organizer=original.organizer,
            description=original.description,
            location=original.location,
            date=original.date + timedelta(days=7),
            capacity=original.capacity,
            price=original.price,
            is_published=False,
        )
        new_event.tags.set(original.tags.all())

        serializer = EventModelSerializer(new_event)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
