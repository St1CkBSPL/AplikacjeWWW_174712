from datetime import timedelta
from decimal import Decimal

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Event, OrganizerProfile, Tag, Ticket


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


class EventAPIV1Tests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organizer = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="StrongPassword123!",
        )
        cls.other_user = User.objects.create_user(
            username="attendee",
            email="attendee@example.com",
            password="StrongPassword123!",
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
        cls.tag_backend = Tag.objects.create(name="backend", slug="backend")

        cls.event = cls.create_event(
            "Django Day",
            "django-day",
            cls.category,
            description="Szczegółowy opis konferencji Django Day 2026.",
            tags=[cls.tag_python, cls.tag_ai],
            days_offset=14,
        )
        cls.paid_event = cls.create_event(
            "Python Workshop",
            "python-workshop",
            cls.other_category,
            description="Płatne warsztaty z programowania w języku Python.",
            price=Decimal("150.00"),
            tags=[cls.tag_python],
            days_offset=7,
        )
        cls.past_event = cls.create_event(
            "Past Conference",
            "past-conference",
            cls.category,
            description="Archiwalne wydarzenie, które już się odbyło.",
            price=Decimal("50.00"),
            days_offset=-5,
        )
        cls.draft_event = cls.create_event(
            "Draft Event",
            "draft-event",
            cls.category,
            description="Szkic wydarzenia nieopublikowanego publicznie.",
            price=Decimal("0.00"),
            tags=[cls.tag_ai],
            is_published=False,
            days_offset=20,
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
        is_published=True,
        days_offset=14,
        organizer=None,
    ):
        event = Event.objects.create(
            title=title,
            slug=slug,
            category=category,
            organizer=organizer or cls.organizer,
            description=description,
            location=location,
            date=timezone.now() + timedelta(days=days_offset),
            capacity=capacity,
            price=price,
            is_published=is_published,
        )
        if tags:
            event.tags.set(tags)
        return event

    def event_payload(self, **overrides):
        payload = {
            "title": "Nowa konferencja backendowa",
            "slug": "nowa-konferencja-backendowa",
            "category": self.category.id,
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

    def test_api_root_exposes_router_endpoints(self):
        response = self.client.get("/events/api/v1/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("categories", response.data)
        self.assertIn("events", response.data)
        self.assertIn("tags", response.data)
        self.assertIn("tickets", response.data)

    def test_generic_cbv_endpoints_work(self):
        list_resp = self.client.get(reverse("events:generic-event-list"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertIn("short_description", list_resp.data[0])

        detail_resp = self.client.get(
            reverse("events:generic-event-detail", kwargs={"pk": self.event.pk})
        )
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertIn("tags_details", detail_resp.data)

    def test_event_viewset_list_and_retrieve_use_dynamic_serializers(self):
        list_resp = self.client.get(reverse("events:v1:event-list"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        item = next(e for e in list_resp.data if e["slug"] == self.event.slug)
        self.assertEqual(item["short_description"], self.event.description)
        self.assertEqual(item["tags_count"], 2)
        self.assertNotIn("description", item)

        detail_resp = self.client.get(
            reverse("events:v1:event-detail", kwargs={"pk": self.event.pk})
        )
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["description"], self.event.description)
        self.assertEqual(len(detail_resp.data["tags_details"]), 2)
        self.assertIn("days_until_event", detail_resp.data)

    def test_event_viewset_create_requires_auth_and_auto_assigns_organizer(self):
        anon = self.client.post(
            reverse("events:v1:event-list"),
            self.event_payload(),
            format="json",
        )
        self.assertEqual(anon.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.other_user)
        created = self.client.post(
            reverse("events:v1:event-list"),
            self.event_payload(tag_ids=[self.tag_python.id, self.tag_ai.id]),
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["organizer"], self.other_user.id)
        self.assertEqual(created.data["organizer_username"], self.other_user.username)
        self.assertEqual(len(created.data["tags_details"]), 2)

        bad_online = self.client.post(
            reverse("events:v1:event-list"),
            self.event_payload(
                title="Webinar Python online",
                slug="webinar-online-bad",
                location="Olsztyn",
            ),
            format="json",
        )
        self.assertEqual(bad_online.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("location", bad_online.data)

        bad_capacity = self.client.post(
            reverse("events:v1:event-list"),
            self.event_payload(slug="over-capacity", capacity=1001),
            format="json",
        )
        self.assertEqual(bad_capacity.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("capacity", bad_capacity.data)

    def test_upcoming_and_free_events_actions(self):
        upcoming = self.client.get(reverse("events:v1:event-upcoming"))
        self.assertEqual(upcoming.status_code, status.HTTP_200_OK)
        upcoming_slugs = [e["slug"] for e in upcoming.data]
        self.assertEqual(upcoming_slugs, [self.paid_event.slug, self.event.slug])
        self.assertIn("short_description", upcoming.data[0])

        free = self.client.get(reverse("events:v1:event-free-events"))
        self.assertEqual(free.status_code, status.HTTP_200_OK)
        free_slugs = [e["slug"] for e in free.data]
        self.assertEqual(free_slugs, [self.event.slug])
        self.assertIn("short_description", free.data[0])

    def test_publish_toggle_action(self):
        self.client.force_authenticate(user=self.organizer)
        url = reverse("events:v1:event-publish-toggle", kwargs={"pk": self.event.pk})
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_published"])
        self.event.refresh_from_db()
        self.assertFalse(self.event.is_published)

    def test_manage_tags_action_add_remove_and_errors(self):
        self.client.force_authenticate(user=self.organizer)
        url = reverse("events:v1:event-manage-tags", kwargs={"pk": self.event.pk})

        missing = self.client.post(url, {}, format="json")
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing.data["error"], "Pole 'tag_id' jest wymagane.")

        not_found = self.client.post(url, {"tag_id": 999999}, format="json")
        self.assertEqual(not_found.status_code, status.HTTP_404_NOT_FOUND)

        added = self.client.post(url, {"tag_id": self.tag_backend.id}, format="json")
        self.assertEqual(added.status_code, status.HTTP_200_OK)
        self.assertIn("backend", [tag["name"] for tag in added.data])

        removed = self.client.delete(url, {"tag_id": self.tag_backend.id}, format="json")
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        self.assertNotIn("backend", [tag["name"] for tag in removed.data])

    def test_duplicate_action_creates_draft_copy_with_request_user_as_organizer(self):
        self.client.force_authenticate(user=self.other_user)
        url = reverse("events:v1:event-duplicate", kwargs={"pk": self.event.pk})
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["title"], f"{self.event.title} (Kopia)")
        self.assertTrue(resp.data["slug"].startswith(f"{self.event.slug}-kopia-"))
        self.assertFalse(resp.data["is_published"])
        self.assertEqual(resp.data["organizer"], self.other_user.id)
        self.assertEqual(len(resp.data["tags_details"]), 2)

        copy = Event.objects.get(pk=resp.data["id"])
        self.assertEqual(copy.date, self.event.date + timedelta(days=7))
        self.assertEqual(copy.category, self.event.category)
        self.assertEqual(copy.organizer, self.other_user)

    def test_category_viewset_crud_delete_guard_and_events_action(self):
        self.client.force_authenticate(user=self.organizer)
        blocked = self.client.delete(
            reverse("events:v1:category-detail", kwargs={"pk": self.category.pk})
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            blocked.data["error"],
            "Nie można usunąć kategorii, do której są przypisane wydarzenia.",
        )

        removed = self.client.delete(
            reverse("events:v1:category-detail", kwargs={"pk": self.empty_category.pk})
        )
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)

        cat_events = self.client.get(
            reverse("events:v1:category-events", kwargs={"pk": self.category.pk})
        )
        self.assertEqual(cat_events.status_code, status.HTTP_200_OK)
        slugs = {e["slug"] for e in cat_events.data}
        self.assertEqual(slugs, {self.event.slug, self.past_event.slug})

    def test_tag_viewset_crud_and_events_action(self):
        self.client.force_authenticate(user=self.organizer)
        created = self.client.post(
            reverse("events:v1:tag-list"),
            {"name": "devops", "slug": "devops"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        tag_events = self.client.get(
            reverse("events:v1:tag-events", kwargs={"pk": self.tag_ai.pk})
        )
        self.assertEqual(tag_events.status_code, status.HTTP_200_OK)
        self.assertEqual([e["slug"] for e in tag_events.data], [self.event.slug])
        self.assertIn("short_description", tag_events.data[0])

    def test_platform_summary_api_view(self):
        response = self.client.get(reverse("events:api-platform-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "total_published_events": 3,
                "upcoming_events_count": 2,
                "free_events_count": 1,
                "categories_count": 3,
                "tags_count": 3,
                "average_ticket_price": 66.67,
            },
        )

    def test_platform_summary_handles_no_published_events(self):
        Event.objects.update(is_published=False)
        response = self.client.get(reverse("events:api-platform-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_published_events"], 0)
        self.assertEqual(response.data["average_ticket_price"], 0.00)

    def test_my_organized_action_and_is_published_filter(self):
        url = reverse("events:v1:event-my-organized")
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)

        self.create_event(
            "Other User Event",
            "other-user-event",
            self.category,
            organizer=self.other_user,
            days_offset=30,
        )

        self.client.force_authenticate(user=self.organizer)
        all_mine = self.client.get(url)
        self.assertEqual(all_mine.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [e["slug"] for e in all_mine.data],
            [
                self.draft_event.slug,
                self.event.slug,
                self.paid_event.slug,
                self.past_event.slug,
            ],
        )

        drafts_only = self.client.get(url, {"is_published": "false"})
        self.assertEqual(drafts_only.status_code, status.HTTP_200_OK)
        self.assertEqual([e["slug"] for e in drafts_only.data], [self.draft_event.slug])

        published_only = self.client.get(url, {"is_published": "true"})
        self.assertEqual(published_only.status_code, status.HTTP_200_OK)
        self.assertEqual(len(published_only.data), 3)


class AuthProfileAndTicketsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Konferencje", slug="konferencje")
        cls.user = User.objects.create_user(
            username="jan_kowalski",
            email="jan@example.com",
            password="InitialPassword123!",
            first_name="Jan",
            last_name="Kowalski",
            is_staff=True,
        )
        cls.other_user = User.objects.create_user(
            username="anna_nowak",
            email="anna@example.com",
            password="OtherPassword123!",
        )
        cls.published_event = Event.objects.create(
            title="UWM Tech Summit",
            slug="uwm-tech-summit",
            category=cls.category,
            organizer=cls.user,
            description="Konferencja technologiczna dla studentów i specjalistów.",
            location="Olsztyn",
            date=timezone.now() + timedelta(days=10),
            capacity=120,
            price=Decimal("25.00"),
            is_published=True,
        )
        cls.draft_event = Event.objects.create(
            title="Ukryty warsztat",
            slug="ukryty-warsztat",
            category=cls.category,
            organizer=cls.user,
            description="Nieopublikowany warsztat testowy dla organizatorów.",
            location="Olsztyn",
            date=timezone.now() + timedelta(days=15),
            capacity=20,
            price=Decimal("0.00"),
            is_published=False,
        )

    def test_registration_creates_user_and_organizer_profile(self):
        url = reverse("events:api-register")

        mismatch = self.client.post(
            url,
            {
                "username": "nowy_user",
                "email": "nowy@example.com",
                "password": "SafePassword123!",
                "password_confirm": "Different123!",
            },
            format="json",
        )
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", mismatch.data)

        duplicate_email = self.client.post(
            url,
            {
                "username": "nowy_user",
                "email": "JAN@example.com",
                "password": "SafePassword123!",
                "password_confirm": "SafePassword123!",
            },
            format="json",
        )
        self.assertEqual(duplicate_email.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", duplicate_email.data)

        created = self.client.post(
            url,
            {
                "username": "nowy_user",
                "email": "nowy@example.com",
                "first_name": "Nowy",
                "last_name": "Użytkownik",
                "password": "SafePassword123!",
                "password_confirm": "SafePassword123!",
                "company_name": "UWM Lab",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="nowy_user")
        self.assertEqual(user.profile.company_name, "UWM Lab")
        self.assertFalse(user.profile.is_verified)

    def test_jwt_token_obtain_custom_claims_refresh_and_verify(self):
        token_resp = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "jan_kowalski", "password": "InitialPassword123!"},
            format="json",
        )
        self.assertEqual(token_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", token_resp.data)
        self.assertIn("refresh", token_resp.data)
        self.assertEqual(
            token_resp.data["user"],
            {
                "id": self.user.id,
                "username": "jan_kowalski",
                "email": "jan@example.com",
            },
        )

        decoded = jwt.decode(
            token_resp.data["access"],
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        self.assertEqual(decoded["username"], "jan_kowalski")
        self.assertEqual(decoded["email"], "jan@example.com")
        self.assertTrue(decoded["is_staff"])

        verify_resp = self.client.post(
            reverse("token_verify"),
            {"token": token_resp.data["access"]},
            format="json",
        )
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)

        refresh_resp = self.client.post(
            reverse("token_refresh"),
            {"refresh": token_resp.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_resp.data)

        # Użycie tokena Bearer do utworzenia wydarzenia bez podawania organizer
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_resp.data['access']}")
        create_event_resp = self.client.post(
            reverse("events:v1:event-list"),
            {
                "title": "JWT Event",
                "slug": "jwt-event",
                "category": self.category.id,
                "description": "Wydarzenie utworzone za pomocą tokena JWT Bearer.",
                "location": "Olsztyn",
                "date": (timezone.now() + timedelta(days=25)).isoformat(),
                "capacity": 50,
                "price": "0.00",
                "is_published": True,
            },
            format="json",
        )
        self.assertEqual(create_event_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_event_resp.data["organizer_username"], "jan_kowalski")

    def test_ticket_viewset_creation_validation_and_user_isolation(self):
        tickets_url = reverse("events:v1:ticket-list")
        self.assertEqual(self.client.get(tickets_url).status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.user)
        draft_attempt = self.client.post(
            tickets_url, {"event": self.draft_event.id}, format="json"
        )
        self.assertEqual(draft_attempt.status_code, status.HTTP_400_BAD_REQUEST)

        created = self.client.post(
            tickets_url, {"event": self.published_event.id}, format="json"
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["user_username"], self.user.username)
        self.assertIn("ticket_code", created.data)

        duplicate = self.client.post(
            tickets_url, {"event": self.published_event.id}, format="json"
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(user=self.other_user)
        other_list = self.client.get(tickets_url)
        self.assertEqual(other_list.status_code, status.HTTP_200_OK)
        self.assertEqual(other_list.data, [])

    def test_current_user_me_endpoint_retrieve_and_nested_profile_update(self):
        me_url = reverse("events:api-current-user")
        self.assertEqual(self.client.get(me_url).status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.user)
        get_resp = self.client.get(me_url)
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(get_resp.data["username"], "jan_kowalski")
        self.assertIn("profile", get_resp.data)

        patch_resp = self.client.patch(
            me_url,
            {
                "first_name": "Janusz",
                "email": "jan.nowy@example.com",
                "profile": {
                    "company_name": "EventHub Corp",
                    "bio": "Organizator konferencji IT.",
                    "website": "https://eventhub.example.com",
                    "is_verified": True,
                },
            },
            format="json",
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Janusz")
        self.assertEqual(self.user.email, "jan.nowy@example.com")
        self.assertEqual(self.user.profile.company_name, "EventHub Corp")
        self.assertEqual(self.user.profile.bio, "Organizator konferencji IT.")
        self.assertEqual(self.user.profile.website, "https://eventhub.example.com")
        self.assertFalse(self.user.profile.is_verified)

    def test_change_password_endpoint_validation_and_login_with_new_password(self):
        url = reverse("events:api-change-password")
        self.assertEqual(self.client.post(url, {}).status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.user)

        wrong_old = self.client.post(
            url,
            {"old_password": "WrongPassword123!", "new_password": "BrandNewPassword123!"},
            format="json",
        )
        self.assertEqual(wrong_old.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("old_password", wrong_old.data)

        same_password = self.client.post(
            url,
            {"old_password": "InitialPassword123!", "new_password": "InitialPassword123!"},
            format="json",
        )
        self.assertEqual(same_password.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", same_password.data)

        changed = self.client.post(
            url,
            {"old_password": "InitialPassword123!", "new_password": "BrandNewPassword123!"},
            format="json",
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        self.assertEqual(changed.data["message"], "Hasło zostało pomyślnie zmienione.")

        self.client.force_authenticate(user=None)
        login = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "jan_kowalski", "password": "BrandNewPassword123!"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn("access", login.data)
