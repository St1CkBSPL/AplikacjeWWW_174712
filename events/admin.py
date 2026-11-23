from django.contrib import admin
from .models import Category, Event, OrganizerProfile, Tag, Ticket


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'events_count', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}

    # Dekorator @admin.display formatuje niestandardowe kolumny na liście rekordów
    # Zob. https://docs.djangoproject.com/en/6.1/ref/contrib/admin/#django.contrib.admin.display
    @admin.display(description="Liczba wydarzeń")
    def events_count(self, obj):
        return obj.events.count()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'organizer', 'date', 'price', 'capacity', 'is_published')
    list_filter = ('category', 'is_published', 'date')
    search_fields = ('title', 'description', 'location')
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ('is_published', 'price')
    date_hierarchy = 'date'
    ordering = ('date',)
    filter_horizontal = ('tags',)

    fieldsets = (
        ("Podstawowe informacje", {
            'fields': ('title', 'slug', 'category', 'organizer', 'tags', 'description')
        }),
        ("Szczegóły organizacyjne", {
            'fields': ('location', 'date', 'capacity', 'price', 'is_published')
        }),
    )


@admin.register(OrganizerProfile)
class OrganizerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'website', 'is_verified')
    list_filter = ('is_verified',)
    search_fields = ('user__username', 'company_name', 'bio')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_code', 'event', 'user', 'status', 'purchased_at')
    list_filter = ('status', 'purchased_at')
    search_fields = ('ticket_code', 'event__title', 'user__username')
    readonly_fields = ('ticket_code', 'purchased_at')
