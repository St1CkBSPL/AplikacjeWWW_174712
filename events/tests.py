from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Event, Tag


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


class EventAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organizer = User.objects.create_user(
            username="organizer", password="test-password"
        )
        cls.category = Category.objects.create(
            name="Konferencje",
            slug="konferencje",
            description="Wydarzenia konferencyjne",
        )
        cls.other_category = Category.objects.create(
            name="Warsztaty",
            slug="warsztaty",
            description="Warsztaty praktyczne",
        )
        cls.empty_category = Category.objects.create(
            name="Pusta kategoria",
            slug="pusta-kategoria",
        )
        cls.tag_python = Tag.objects.create(name="python", slug="python")
        cls.tag_ai = Tag.objects.create(name="ai", slug="ai")
        cls.event = cls.create_event(
            "Django Day",
            "django-day",
            cls.category,
            description="Szczegółowy opis konferencji Django Day 2026.",
            tags=[cls.tag_python, cls.tag_ai],
        )
        cls.paid_event = cls.create_event(
            "Python Workshop",
            "python-workshop",
            cls.other_category,
            description="Płatne warsztaty z programowania w języku Python.",
            price=Decimal("150.00"),
            tags=[cls.tag_python],
        )

    @classmethod
    def create_event(
        cls,
        title,
        slug,
        category,
        description="Szczegółowy opis wydarzenia testowego.",
        price=Decimal("0.00"),
        tags=None,
        location="Olsztyn",
        capacity=100,
    ):
        event = Event.objects.create(
            title=title,
            slug=slug,
            category=category,
            organizer=cls.organizer,
            description=description,
            location=location,
            date=timezone.now() + timedelta(days=14),
            capacity=capacity,
            price=price,
            is_published=True,
        )
        if tags:
            event.tags.set(tags)
        return event

    def event_payload(self, **overrides):
        payload = {
            "title": "Nowa konferencja backendowa",
            "slug": "nowa-konferencja-backendowa",
            "category": self.category.id,
            "organizer": self.organizer.id,
            "description": "Szczegółowy opis nowej konferencji backendowej.",
            "location": "Olsztyn",
            "date": (timezone.now() + timedelta(days=30)).isoformat(),
            "capacity": 80,
            "price": "0.00",
            "is_published": True,
            "tag_ids": [self.tag_python.id],
        }
        payload.update(overrides)
        return payload

    def test_event_list_uses_list_serializer_fields(self):
        response = self.client.get(reverse("events:api-event-list-create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)
        item = next(event for event in response.data if event["slug"] == self.event.slug)
        self.assertEqual(item["short_description"], self.event.description)
        self.assertEqual(item["tags_count"], 2)
        self.assertTrue(item["is_free"])
        self.assertNotIn("description", item)
        self.assertNotIn("updated_at", item)

    def test_event_list_truncates_long_description(self):
        long_description = "A" * 90
        self.event.description = long_description
        self.event.save(update_fields=["description"])

        response = self.client.get(reverse("events:api-event-list-create"))
        item = next(event for event in response.data if event["slug"] == self.event.slug)

        self.assertEqual(item["short_description"], f"{'A' * 80}...")

    def test_event_list_filters_by_tag_and_free_flag(self):
        by_tag = self.client.get(
            reverse("events:api-event-list-create"), {"tag": "ai"}
        )
        free_only = self.client.get(
            reverse("events:api-event-list-create"), {"free": "TRUE"}
        )

        self.assertEqual(len(by_tag.data), 1)
        self.assertEqual(by_tag.data[0]["slug"], self.event.slug)
        self.assertEqual(len(free_only.data), 1)
        self.assertEqual(free_only.data[0]["slug"], self.event.slug)

    def test_event_create_returns_nested_tags_and_computed_fields(self):
        response = self.client.post(
            reverse("events:api-event-list-create"),
            self.event_payload(tag_ids=[self.tag_python.id, self.tag_ai.id]),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["tags_details"]), 2)
        self.assertTrue(response.data["is_free"])
        self.assertIn("days_until_event", response.data)
        self.assertGreaterEqual(response.data["days_until_event"], 29)

    def test_event_patch_updates_price(self):
        response = self.client.patch(
            reverse("events:api-event-detail", kwargs={"pk": self.event.pk}),
            {"price": "99.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["price"], "99.00")
        self.assertFalse(response.data["is_free"])

    def test_online_event_requires_url_location(self):
        response = self.client.post(
            reverse("events:api-event-list-create"),
            self.event_payload(
                title="Webinar Python online",
                slug="webinar-python-online",
                location="Olsztyn",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("location", response.data)

    def test_online_event_accepts_https_location(self):
        response = self.client.post(
            reverse("events:api-event-list-create"),
            self.event_payload(
                title="Webinar Python online",
                slug="webinar-python-online",
                location="https://meet.example.com/python",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["location"], "https://meet.example.com/python")

    def test_stationary_event_rejects_capacity_over_limit(self):
        response = self.client.post(
            reverse("events:api-event-list-create"),
            self.event_payload(slug="duza-sala", capacity=1001),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("capacity", response.data)

    def test_category_crud_and_protected_delete(self):
        created = self.client.post(
            reverse("events:api-category-list"),
            {"name": "Hackathony", "slug": "hackathony", "description": "Maratony programowania"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        blocked = self.client.delete(
            reverse("events:api-category-detail", kwargs={"pk": self.category.pk})
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            blocked.data["error"],
            "Nie można usunąć kategorii, do której są przypisane wydarzenia.",
        )

        removed = self.client.delete(
            reverse("events:api-category-detail", kwargs={"pk": self.empty_category.pk})
        )
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)

    def test_tag_list_is_alphabetical_and_create_works(self):
        listing = self.client.get(reverse("events:api-tag-list-create"))
        names = [tag["name"] for tag in listing.data]
        self.assertEqual(names, sorted(names))

        created = self.client.post(
            reverse("events:api-tag-list-create"),
            {"name": "backend", "slug": "backend"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["name"], "backend")
