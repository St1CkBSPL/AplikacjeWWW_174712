from decimal import Decimal
import uuid

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nazwa kategorii")
    slug = models.SlugField(max_length=120, unique=True, verbose_name="Slug (URL)")
    description = models.TextField(blank=True, verbose_name="Opis kategorii")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data utworzenia")

    class Meta:
        verbose_name = "Kategoria"
        verbose_name_plural = "Kategorie"
        ordering = ['name']

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Nazwa tagu")
    slug = models.SlugField(max_length=60, unique=True, verbose_name="Slug tagu")

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tagi"
        ordering = ['name']

    def __str__(self):
        return f"#{self.name}"


class Event(models.Model):
    title = models.CharField(max_length=200, verbose_name="Tytuł wydarzenia")
    slug = models.SlugField(max_length=220, unique=True, verbose_name="Slug (URL)")
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Kategoria"
    )
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="organized_events",
        verbose_name="Organizator"
    )
    tags = models.ManyToManyField(
        Tag,
        related_name="events",
        blank=True,
        verbose_name="Tagi tematyczne"
    )
    description = models.TextField(verbose_name="Szczegółowy opis")
    location = models.CharField(max_length=255, verbose_name="Miejsce / Adres / Link online")
    date = models.DateTimeField(verbose_name="Data i godzina rozpoczęcia")
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Maksymalna liczba uczestników"
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Cena biletu (PLN)"
    )
    is_published = models.BooleanField(default=True, verbose_name="Opublikowane")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data dodania")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ostatnia aktualizacja")

    class Meta:
        verbose_name = "Wydarzenie"
        verbose_name_plural = "Wydarzenia"
        ordering = ['date']

    def __str__(self):
        return f"{self.title} ({self.date.strftime('%Y-%m-%d %H:%M')})"


class OrganizerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Użytkownik"
    )
    company_name = models.CharField(max_length=150, blank=True, verbose_name="Nazwa firmy / organizacji")
    bio = models.TextField(blank=True, verbose_name="O organizatorze")
    website = models.URLField(blank=True, verbose_name="Strona WWW")
    is_verified = models.BooleanField(default=False, verbose_name="Zweryfikowany organizator")

    class Meta:
        verbose_name = "Profil organizatora"
        verbose_name_plural = "Profile organizatorów"

    def __str__(self):
        return f"Profil: {self.user.username} ({self.company_name or 'Osoba prywatna'})"


class Ticket(models.Model):
    STATUS_CHOICES = (
        ('reserved', 'Zarezerwowany'),
        ('confirmed', 'Opłacony i potwierdzony'),
        ('used', 'Wykorzystany na wejściu'),
        ('cancelled', 'Anulowany'),
    )

    ticket_code = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name="Unikalny kod biletu (UUID)"
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name="Wydarzenie"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='my_tickets',
        verbose_name="Uczestnik"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed', verbose_name="Status")
    purchased_at = models.DateTimeField(auto_now_add=True, verbose_name="Data zakupu")

    class Meta:
        verbose_name = "Bilet"
        verbose_name_plural = "Bilety"
        ordering = ['-purchased_at']
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'user'],
                name='unique_event_user_ticket'
            )
        ]

    def __str__(self):
        return f"Bilet {self.ticket_code} -> {self.event.title} ({self.user.username})"
