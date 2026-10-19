import os
import sys
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventhub.settings')
django.setup()

from decimal import Decimal
from events.models import Event, Category


def run_queries():
    print("=" * 60)
    print("1. Opublikowane wydarzenia (posortowane chronologicznie):")
    print("=" * 60)
    published_events = Event.objects.filter(is_published=True).order_by('date')
    for ev in published_events:
        print(f"- {ev.title} | Data: {ev.date.strftime('%Y-%m-%d %H:%M')} | Cena: {ev.price} PLN")

    print("\n" + "=" * 60)
    print("2. Wydarzenia z limitem miejsc >= 50 osób:")
    print("=" * 60)
    large_events = Event.objects.filter(capacity__gte=50)
    for ev in large_events:
        print(f"- {ev.title} (Miejsc: {ev.capacity})")

    print("\n" + "=" * 60)
    print("3. Łączna liczba darmowych wydarzeń (cena = 0.00 PLN):")
    print("=" * 60)
    free_events_count = Event.objects.filter(price=Decimal('0.00')).count()
    print(f"Liczba darmowych wydarzeń: {free_events_count}")

    print("\n" + "=" * 60)
    print("4. Zmiana statusu is_published wybranego wydarzenia (True -> False):")
    print("=" * 60)
    event_to_update = Event.objects.filter(is_published=True).first()
    if event_to_update:
        print(f"Przed zmianą: '{event_to_update.title}' | is_published = {event_to_update.is_published}")
        event_to_update.is_published = False
        event_to_update.save()
        print(f"Po zmianie:   '{event_to_update.title}' | is_published = {event_to_update.is_published}")
    else:
        print("Brak opublikowanych wydarzeń do modyfikacji.")


if __name__ == '__main__':
    run_queries()