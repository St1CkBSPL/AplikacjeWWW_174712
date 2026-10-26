# Test serializatora `EventSerializer` w powłoce Django

Test wykonano poleceniem:

```powershell
.\.venv\Scripts\python.exe manage.py shell
```

## 1. Serializacja obiektu `Event` do JSON

Polecenia:

```python
import io

from events.models import Event
from events.serializers import EventSerializer
from rest_framework.renderers import JSONRenderer

event = Event.objects.first()
serializer = EventSerializer(event)

print(serializer.data)
json_bytes = JSONRenderer().render(serializer.data)
print(json_bytes)
```

Rzeczywisty wynik:

```text
{'id': 3, 'title': 'Meczyk Medi Eryk', 'slug': 'meczyk-medi-eryk', 'category_id': 3, 'organizer_id': 1, 'description': '3;2', 'location': 'u Eryka', 'date': '2026-10-11T00:00:00Z', 'capacity': 2, 'price': '0.00', 'is_published': False, 'created_at': '2026-10-12T14:12:16.280970Z'}
b'{"id":3,"title":"Meczyk Medi Eryk","slug":"meczyk-medi-eryk","category_id":3,"organizer_id":1,"description":"3;2","location":"u Eryka","date":"2026-10-11T00:00:00Z","capacity":2,"price":"0.00","is_published":false,"created_at":"2026-10-12T14:12:16.280970Z"}'
```

## 2. Deserializacja i utworzenie obiektu

Polecenia:

```python
from rest_framework.parsers import JSONParser

stream = io.BytesIO(json_bytes)
data = JSONParser().parse(stream)
data["title"] = "Nowe Warsztaty Pythona"
data["slug"] = "nowe-warsztaty-pythona-lab04"

deserializer = EventSerializer(data=data)
print(deserializer.is_valid())
print(deserializer.validated_data)

new_event = deserializer.save()
print({"id": new_event.id, "title": new_event.title, "slug": new_event.slug})
```

Rzeczywisty wynik:

```text
True
{'title': 'Nowe Warsztaty Pythona', 'slug': 'nowe-warsztaty-pythona-lab04', 'category': <Category: Wyniki>, 'organizer': <User: Kacper>, 'description': '3;2', 'location': 'u Eryka', 'date': datetime.datetime(2026, 10, 11, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='UTC')), 'capacity': 2, 'price': Decimal('0.00'), 'is_published': False}
{'id': 5, 'title': 'Nowe Warsztaty Pythona', 'slug': 'nowe-warsztaty-pythona-lab04'}
```

Obiekt został zapisany w bazie danych z identyfikatorem `5`.

## 3. Walidacja niepoprawnych danych

W danych celowo pominięto `category_id` i podano błędny format daty.

Polecenia:

```python
invalid_data = {
    "title": "Błędne wydarzenie",
    "slug": "bledne-wydarzenie",
    "organizer_id": event.organizer_id,
    "description": "Test błędów",
    "location": "Olsztyn",
    "date": "niepoprawna-data",
    "capacity": 10,
    "price": "0.00",
}

bad_serializer = EventSerializer(data=invalid_data)
print(bad_serializer.is_valid())
print(bad_serializer.errors)
```

Rzeczywisty wynik:

```text
False
{'category_id': [ErrorDetail(string='This field is required.', code='required')], 'date': [ErrorDetail(string='Datetime has wrong format. Use one of these formats instead: YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z].', code='invalid')]}
```
