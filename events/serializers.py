from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from .models import Category, Event, Tag


class EventSerializer(serializers.Serializer):
    """
    Niskopoziomowy serializator modelu Event.

    Pola oraz operacje zapisu są zdefiniowane jawnie, aby pokazać mechanizm
    serializacji i deserializacji bez użycia ModelSerializer.
    """

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(required=True, max_length=200)
    slug = serializers.SlugField(required=True, max_length=220)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        write_only=False,
    )
    organizer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="organizer",
    )
    description = serializers.CharField(style={"base_template": "textarea.html"})
    location = serializers.CharField(max_length=255)
    date = serializers.DateTimeField()
    capacity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    is_published = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(read_only=True)

    def create(self, validated_data):
        """Tworzy wydarzenie na podstawie zwalidowanych danych."""
        return Event.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """Aktualizuje wydarzenie przy użyciu przekazanych pól."""
        instance.title = validated_data.get("title", instance.title)
        instance.slug = validated_data.get("slug", instance.slug)
        instance.category = validated_data.get("category", instance.category)
        instance.organizer = validated_data.get("organizer", instance.organizer)
        instance.description = validated_data.get(
            "description", instance.description
        )
        instance.location = validated_data.get("location", instance.location)
        instance.date = validated_data.get("date", instance.date)
        instance.capacity = validated_data.get("capacity", instance.capacity)
        instance.price = validated_data.get("price", instance.price)
        instance.is_published = validated_data.get(
            "is_published", instance.is_published
        )
        instance.save()
        return instance


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']
        read_only_fields = ['id']


class CategorySerializer(serializers.ModelSerializer):
    events_count = serializers.IntegerField(source='events.count', read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'events_count', 'created_at']
        read_only_fields = ['id', 'created_at', 'events_count']


class EventModelSerializer(serializers.ModelSerializer):
    # 1. Pola pomocnicze tylko do odczytu (zamiast samych kluczy obcych ID)
    category_name = serializers.ReadOnlyField(source='category.name')
    organizer_username = serializers.ReadOnlyField(source='organizer.username')

    # 2. Obsługa relacji ManyToMany (Tagi):
    # - w odpowiedziach GET zwracamy pełne obiekty tagów (id, name, slug)
    tags_details = TagSerializer(source='tags', many=True, read_only=True)
    # - w żądaniach POST/PUT/PATCH przyjmujemy tablicę identyfikatorów, np. "tag_ids": [1, 2]
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        source='tags',
        write_only=True,
        required=False
    )

    # 3. Pola dynamiczne wyliczane metodą (SerializerMethodField)
    is_free = serializers.SerializerMethodField()
    days_until_event = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'category', 'category_name',
            'organizer', 'organizer_username', 'tags_details', 'tag_ids',
            'description', 'location', 'date', 'capacity', 'price',
            'is_free', 'days_until_event', 'is_published',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_is_free(self, obj) -> bool:
        """Zwraca True, jeśli wydarzenie jest bezpłatne."""
        return obj.price == 0

    def get_days_until_event(self, obj) -> int:
        """Oblicza liczbę pełnych dni pozostałych do rozpoczęcia wydarzenia (lub 0, jeśli już minęło)."""
        delta = obj.date - timezone.now()
        return max(0, delta.days)

    def validate_date(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Termin wydarzenia musi być datą w przyszłości!")
        return value

    def validate_capacity(self, value):
        if value < 5:
            raise serializers.ValidationError("Minimalna liczba uczestników wydarzenia wynosi 5 osób.")
        return value

    def validate(self, attrs):
        title = attrs.get('title', getattr(self.instance, 'title', ''))
        price = attrs.get('price', getattr(self.instance, 'price', 0))
        is_published = attrs.get('is_published', getattr(self.instance, 'is_published', True))
        description = attrs.get('description', getattr(self.instance, 'description', ''))
        location = attrs.get('location', getattr(self.instance, 'location', ''))
        capacity = attrs.get('capacity', getattr(self.instance, 'capacity', 0))

        if any(word in title.lower() for word in ['darmow', 'bezpłatn', 'free']) and price > 0:
            raise serializers.ValidationError({
                "price": "Wydarzenie oznaczone w tytule jako bezpłatne nie może mieć ceny wyższej niż 0.00 PLN."
            })

        if is_published and len(description.strip()) < 20:
            raise serializers.ValidationError({
                "description": "Opublikowane wydarzenie musi posiadać szczegółowy opis (minimum 20 znaków)."
            })

        searchable_text = f"{title} {description}".lower()
        is_online_event = "online" in searchable_text or "webinar" in searchable_text
        has_url_location = location.startswith("http://") or location.startswith("https://")

        if is_online_event and not has_url_location:
            raise serializers.ValidationError({
                "location": "Dla wydarzeń online pole lokalizacji musi zawierać poprawny adres URL (http:// lub https://)."
            })

        if not has_url_location and capacity > 1000:
            raise serializers.ValidationError({
                "capacity": "Maksymalna pojemność wydarzenia stacjonarnego wynosi 1000 osób."
            })

        return attrs


class EventListSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    organizer_username = serializers.ReadOnlyField(source='organizer.username')
    is_free = serializers.SerializerMethodField()
    short_description = serializers.SerializerMethodField()
    tags_count = serializers.IntegerField(source='tags.count', read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'category_name', 'organizer_username',
            'date', 'location', 'price', 'is_free', 'short_description', 'tags_count'
        ]

    def get_is_free(self, obj) -> bool:
        return obj.price == 0

    def get_short_description(self, obj) -> str:
        if len(obj.description) > 80:
            return f"{obj.description[:80]}..."
        return obj.description
