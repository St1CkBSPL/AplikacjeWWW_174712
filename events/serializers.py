from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Category, Event, OrganizerProfile, Tag, Ticket


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
    tags_details = TagSerializer(source='tags', many=True, read_only=True)
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
        read_only_fields = ['id', 'organizer', 'created_at', 'updated_at']

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


class OrganizerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizerProfile
        fields = ['company_name', 'bio', 'website', 'is_verified']
        read_only_fields = ['is_verified']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )
    company_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'password', 'password_confirm', 'company_name',
        ]

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Użytkownik z tym adresem e-mail już istnieje.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Podane hasła nie są identyczne."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        company_name = validated_data.pop('company_name', '')

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        OrganizerProfile.objects.create(user=user, company_name=company_name)
        return user


class CurrentUserSerializer(serializers.ModelSerializer):
    profile = OrganizerProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'profile']
        read_only_fields = ['id', 'username', 'date_joined']

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Użytkownik z tym adresem e-mail już istnieje.")
        return value

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data is not None:
            profile, _ = OrganizerProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Dotychczasowe hasło jest nieprawidłowe.")
        return value

    def validate(self, attrs):
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({
                "new_password": "Nowe hasło musi różnić się od dotychczasowego."
            })
        return attrs


class TicketSerializer(serializers.ModelSerializer):
    event_title = serializers.ReadOnlyField(source='event.title')
    event_date = serializers.ReadOnlyField(source='event.date')
    event_location = serializers.ReadOnlyField(source='event.location')
    user_username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_code', 'event', 'event_title',
            'event_date', 'event_location', 'user_username',
            'status', 'purchased_at',
        ]
        read_only_fields = ['id', 'ticket_code', 'status', 'purchased_at', 'user_username']

    def validate_event(self, event):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if Ticket.objects.filter(event=event, user=request.user).exists():
                raise serializers.ValidationError("Posiadasz już bilet na to wydarzenie.")
        if not event.is_published:
            raise serializers.ValidationError("Nie można kupić biletu na nieopublikowane wydarzenie.")
        return event


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        token['is_staff'] = user.is_staff
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
        }
        return data
