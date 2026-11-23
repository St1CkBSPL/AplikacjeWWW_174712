from django.contrib.auth.models import User
from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Event, OrganizerProfile, Tag
from .serializers import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    EventListSerializer,
    EventModelSerializer,
    UserRegistrationSerializer,
)


# --- PODEJŚCIE 1: Klasa bazowa APIView ---
class EventListAPIView(APIView):
    """Ręczna obsługa metod GET i POST wewnątrz klasy APIView."""

    def get(self, request):
        events = (
            Event.objects.filter(is_published=True)
            .select_related('category', 'organizer')
            .prefetch_related('tags')
        )
        serializer = EventListSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = EventModelSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(organizer=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --- PODEJŚCIE 2: Widoki generyczne (generics.*) ---
class EventListCreateGenericView(generics.ListCreateAPIView):
    """
    Automatycznie implementuje GET (lista) oraz POST (tworzenie).
    Metoda get_serializer_class pozwala użyć lżejszego serializatora dla GET.
    """

    queryset = (
        Event.objects.select_related('category', 'organizer')
        .prefetch_related('tags')
        .all()
    )

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return EventListSerializer
        return EventModelSerializer

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)


class EventRetrieveUpdateDestroyGenericView(generics.RetrieveUpdateDestroyAPIView):
    """
    Automatycznie implementuje GET (szczegóły), PUT, PATCH (edycja) oraz DELETE (usuwanie).
    """

    queryset = (
        Event.objects.select_related('category', 'organizer')
        .prefetch_related('tags')
        .all()
    )
    serializer_class = EventModelSerializer


class PlatformSummaryAPIView(APIView):
    """Zwraca zbiorcze statystyki platformy EventHub z użyciem agregacji ORM."""

    def get(self, request):
        now = timezone.now()
        published_events = Event.objects.filter(is_published=True)
        stats = published_events.aggregate(
            total_published_events=Count('id'),
            upcoming_events_count=Count('id', filter=Q(date__gte=now)),
            free_events_count=Count('id', filter=Q(price=0)),
            average_ticket_price=Avg('price'),
            min_ticket_price=Min('price'),
            max_ticket_price=Max('price'),
        )
        avg_price = stats['average_ticket_price']
        rounded_avg = round(float(avg_price), 2) if avg_price is not None else 0.00

        return Response(
            {
                'total_published_events': stats['total_published_events'],
                'upcoming_events_count': stats['upcoming_events_count'],
                'free_events_count': stats['free_events_count'],
                'categories_count': Category.objects.count(),
                'tags_count': Tag.objects.count(),
                'average_ticket_price': rounded_avg,
            },
            status=status.HTTP_200_OK,
        )


class UserRegisterView(generics.CreateAPIView):
    """Publiczny endpoint rejestracji nowych użytkowników."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]


class CurrentUserProfileView(generics.RetrieveUpdateAPIView):
    """Odczyt i edycja danych oraz profilu bieżącego użytkownika."""

    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        OrganizerProfile.objects.get_or_create(user=self.request.user)
        return self.request.user


class ChangePasswordView(APIView):
    """Bezpieczna zmiana hasła uwierzytelnionego użytkownika."""

    permission_classes = [IsAuthenticated]

    def _change_password(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response(
            {"message": "Hasło zostało pomyślnie zmienione."},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        return self._change_password(request)

    def put(self, request):
        return self._change_password(request)
