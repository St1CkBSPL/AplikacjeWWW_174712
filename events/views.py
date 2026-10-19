from django.shortcuts import get_object_or_404, render

from .models import Category, Event


def event_list(request):
    """Wyświetla opublikowane wydarzenia, opcjonalnie filtrowane po tytule."""
    events = Event.objects.filter(is_published=True).select_related(
        "category", "organizer"
    )
    q = request.GET.get("q", "").strip()
    if q:
        events = events.filter(title__icontains=q)

    return render(
        request,
        "events/event_list.html",
        {
            "events": events,
            "categories": Category.objects.all(),
            "q": q,
        },
    )


def event_detail(request, slug):
    """Wyświetla opublikowane wydarzenie wskazane przez slug."""
    event = get_object_or_404(
        Event.objects.select_related("category", "organizer"),
        slug=slug,
        is_published=True,
    )
    related_events = (
        Event.objects.filter(category=event.category, is_published=True)
        .exclude(id=event.id)
        .select_related("category", "organizer")[:3]
    )

    return render(
        request,
        "events/event_detail.html",
        {"event": event, "related_events": related_events},
    )


def events_by_category(request, category_slug):
    """Wyświetla opublikowane wydarzenia z wybranej kategorii."""
    category = get_object_or_404(Category, slug=category_slug)
    events = category.events.filter(is_published=True).select_related(
        "category", "organizer"
    )

    return render(
        request,
        "events/event_list.html",
        {
            "events": events,
            "categories": Category.objects.all(),
            "current_category": category,
            "q": "",
        },
    )
