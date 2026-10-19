from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, Event


class EventViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organizer = User.objects.create_user(
            username="organizer", password="test-password"
        )
        cls.category = Category.objects.create(name="Konferencje", slug="konferencje")
        cls.other_category = Category.objects.create(name="Warsztaty", slug="warsztaty")
        cls.event = cls.create_event("Django Day", "django-day", cls.category)
        cls.hidden_event = cls.create_event(
            "Ukryte wydarzenie", "ukryte-wydarzenie", cls.category, is_published=False
        )
        for number in range(4):
            cls.create_event(
                f"Podobne wydarzenie {number}",
                f"podobne-{number}",
                cls.category,
            )
        cls.create_event("Python Workshop", "python-workshop", cls.other_category)

    @classmethod
    def create_event(cls, title, slug, category, is_published=True):
        return Event.objects.create(
            title=title,
            slug=slug,
            category=category,
            organizer=cls.organizer,
            description="Opis wydarzenia",
            location="Olsztyn",
            date=timezone.now() + timedelta(days=7),
            capacity=100,
            price=0,
            is_published=is_published,
        )

    def test_list_displays_only_published_events_and_categories(self):
        response = self.client.get(reverse("events:event-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)
        self.assertNotContains(response, self.hidden_event.title)
        self.assertContains(response, self.category.name)
        self.assertTemplateUsed(response, "events/event_list.html")

    def test_search_filters_events_and_preserves_query(self):
        response = self.client.get(reverse("events:event-list"), {"q": "Django"})

        self.assertContains(response, self.event.title)
        self.assertNotContains(response, "Python Workshop")
        self.assertEqual(response.context["q"], "Django")

    def test_category_view_filters_events(self):
        response = self.client.get(
            reverse(
                "events:events-by-category",
                kwargs={"category_slug": self.category.slug},
            )
        )

        self.assertContains(response, self.event.title)
        self.assertNotContains(response, "Python Workshop")
        self.assertEqual(response.context["current_category"], self.category)

    def test_detail_displays_at_most_three_related_events(self):
        response = self.client.get(
            reverse("events:event-detail", kwargs={"slug": self.event.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["related_events"]), 3)
        self.assertNotIn(self.event, response.context["related_events"])
        self.assertTemplateUsed(response, "events/event_detail.html")

    def test_unpublished_event_detail_returns_not_found(self):
        response = self.client.get(
            reverse("events:event-detail", kwargs={"slug": self.hidden_event.slug})
        )

        self.assertEqual(response.status_code, 404)
