from datetime import date, datetime, time, timedelta
from itertools import cycle

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from contact.models import Contact, ContactMethod
from event.models import Event, EventContact
from issue.models import Issue
from note.models import Note
from property.models import Property
from task.models import Task


DEMO_EMAIL = "portfolio.demo@example.com"
DEMO_PASSWORD = "PortfolioDemo!2026"


PROPERTY_ROOTS = (
    "Ash Grove",
    "Beech Court",
    "Cedar House",
    "Dovecote Mews",
    "Elm Terrace",
    "Foxglove Cottage",
    "Granary House",
    "Hawthorn Lodge",
    "Ivy Apartments",
    "Juniper Place",
    "Kingfisher Court",
    "Linden House",
    "Maple View",
    "Northgate Mews",
    "Orchard House",
    "Parkside Court",
    "Queensway Apartments",
    "Rosebank House",
    "Sycamore Lodge",
    "The Old Bakery",
    "Union Wharf",
    "Victoria Terrace",
    "Willow Court",
    "York House",
    "Acacia Place",
    "Birchfield House",
    "Canal View",
    "Drayton Court",
    "Eastfield Lodge",
    "Fernbank House",
)

PROPERTY_DESCRIPTIONS = (
    "Two-bedroom managed flat. Meter cupboard is beside the front entrance and the stopcock is under the kitchen sink.",
    "Three-bedroom terraced house with rear garden. Contractor access is through the side gate; keys are held at the office.",
    "First-floor apartment in a managed block. Building access requires the concierge fob during weekday hours.",
    "Ground-floor maisonette with private entrance. Boiler and consumer unit are located in the hall cupboard.",
    "Four-bedroom shared house. Annual safety checks are coordinated with the lead tenant by email.",
    "One-bedroom city flat. No parking is provided; loading is permitted outside before 10:00.",
    "End-of-terrace family home. Garden maintenance is included in the management agreement.",
    "Second-floor flat without a lift. Water isolation valve is in the communal riser cupboard.",
)

FIRST_NAMES = (
    "Amelia", "Benjamin", "Charlotte", "Daniel", "Eleanor",
    "Farah", "George", "Hannah", "Isaac", "Jasmine",
    "Kieran", "Leila", "Marcus", "Nadia", "Oliver",
)

LAST_NAMES = ("Bennett", "Clarke", "Davies", "Khan", "Morgan")

ISSUE_DETAILS = (
    ("Boiler pressure dropping", "The boiler loses pressure overnight and needs topping up each morning."),
    ("Water staining below bathroom", "A new stain has appeared on the ceiling below the upstairs bathroom."),
    ("Intermittent hallway lighting", "The communal hallway light flickers and occasionally fails to switch on."),
    ("Bedroom window will not close", "The handle turns but the window does not pull fully into the frame."),
    ("Loose kitchen tap", "The mixer tap moves at its base when used and needs securing."),
    ("Front door closer failing", "The communal front door no longer closes without being pulled shut."),
    ("Possible roof leak", "Water was reported near the loft hatch following heavy rain."),
    ("Radiator cold at top", "The living-room radiator remains cold across the upper section."),
    ("Cracked bathroom tile", "One floor tile beside the bath is cracked and has a sharp edge."),
    ("Extractor fan noisy", "The bathroom extractor has become unusually loud during operation."),
    ("Fence panel damaged", "A rear fence panel was damaged by wind and is leaning into the garden."),
    ("Smoke alarm chirping", "The landing alarm emits a low-battery chirp every few minutes."),
    ("Blocked kitchen waste", "The kitchen sink drains slowly and backs up when the washing machine runs."),
    ("Entry phone not ringing", "Calls from the main entrance do not ring inside the flat."),
    ("Damp around window", "Condensation and dark marks are visible around the bedroom window reveal."),
    ("Garage lock sticking", "The key is difficult to turn and sometimes cannot be removed."),
    ("Hot water temperature fluctuating", "Hot water alternates between warm and very hot during use."),
    ("Loose stair handrail", "The upper fixing of the stair handrail moves under light pressure."),
    ("Pest activity reported", "The tenant reported scratching sounds behind the kitchen units at night."),
    ("Gutter overflowing", "Rainwater spills over the front gutter above the entrance."),
    ("Oven not heating evenly", "Food remains undercooked on the left side despite the selected temperature."),
    ("Bathroom sealant failing", "Sealant behind the bath is lifting and allowing water behind the edge."),
    ("Communal bin lid broken", "The main refuse bin lid is detached and cannot be closed securely."),
    ("Thermostat display blank", "The wall thermostat has no display after its batteries were replaced."),
    ("Balcony drain slow", "Standing water remains around the balcony outlet after rainfall."),
)

TASK_ACTIONS = (
    "Call", "Email", "Arrange", "Confirm", "Inspect", "Book",
    "Review", "Send", "Collect", "Replace", "Photograph", "Follow up",
)

TASK_TARGETS = (
    "heating engineer", "tenant access", "contractor quotation", "inspection report",
    "replacement keys", "repair appointment", "invoice details", "safety certificate",
    "landlord approval", "parts availability", "completion photographs", "warranty position",
    "building manager", "cleaning visit", "maintenance update",
)

EVENT_TITLES = (
    "Annual gas safety inspection", "Tenant check-in", "Electrical inspection",
    "Contractor access appointment", "Inventory visit", "Fire alarm service",
    "Boiler engineer attendance", "End-of-tenancy inspection", "Roof survey",
    "Viewing with prospective tenants", "Meter reading visit", "Window repair appointment",
    "Landlord property review", "Cleaning team access", "Drainage contractor visit",
    "Smoke alarm inspection", "Keys handover", "Insurance surveyor visit",
    "Bathroom repair appointment", "Garden maintenance visit", "Check-out appointment",
    "Appliance engineer attendance", "Communal area inspection", "Pest-control follow-up",
    "Decorator quotation visit", "Plumber attendance", "Heating service",
    "Managing agent review", "Lease inspection", "Property photography appointment",
)

# A deliberately crowded calendar day for checking how the month grid behaves.
OCTOBER_1_DENSITY_TITLES = (
    "Morning contractor access", "Fire door inspection", "Tenant viewing",
    "Boiler follow-up", "Inventory handover", "Roofing quotation",
    "Cleaning team visit", "Owner walkthrough", "Evening key collection",
)


def padded(label, character, length):
    return (f"{label} " + character * length)[:length]


def long_description(label, length=1000):
    sentence = (
        "This deliberately long boundary-test description checks wrapping, spacing, "
        "modal height, cards, lists, and detail-page behaviour. "
    )
    return (f"{label} " + sentence * 20)[:length]


def aware_datetime(day, hour=12):
    return timezone.make_aware(datetime.combine(day, time(hour=hour)))


class Command(BaseCommand):
    help = "Seed a local demo account with realistic and layout-stress data."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=DEMO_EMAIL)
        parser.add_argument("--password", default=DEMO_PASSWORD)
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete and recreate an existing demo account with this email.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo data may only be seeded while DEBUG is enabled.")

        email = options["email"].strip().lower()
        password = options["password"]
        User = get_user_model()
        existing = User.objects.filter(email__iexact=email).first()

        if existing and not options["reset"]:
            raise CommandError(
                f"{email} already exists. Use --reset to replace only that account."
            )
        if existing:
            existing.delete()

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name="Portfolio",
            last_name="Demo",
        )
        today = timezone.localdate()

        properties = self._create_properties(user)
        contacts = self._create_contacts(user)
        issues = self._create_issues(user, properties, today)
        tasks = self._create_tasks(user, properties, issues, today)
        events = self._create_events(user, properties, contacts, today)
        notes = self._create_notes(user, contacts)

        counts = {
            "properties": len(properties),
            "contacts": len(contacts),
            "contact methods": ContactMethod.objects.filter(contact__user=user).count(),
            "issues": len(issues),
            "tasks": len(tasks),
            "events": len(events),
            "event participants": EventContact.objects.filter(event__user=user).count(),
            "notes": len(notes),
        }
        self.stdout.write(self.style.SUCCESS(f"Seeded demo account {email}"))
        self.stdout.write(f"Counts: {counts}")

    def _create_properties(self, user):
        records = []
        descriptions = cycle(PROPERTY_DESCRIPTIONS)
        for index, root in enumerate(PROPERTY_ROOTS):
            number = 4 + index * 3
            name = root
            description = next(descriptions)
            address = f"{number} {root}, London, N{1 + index % 19} {1 + index % 9}AB"

            if index == 27:
                name = padded("[LAYOUT STRESS PROPERTY]", "P", 75)
                description = long_description("[1,000 CHARACTER PROPERTY DESCRIPTION]")
            elif index == 28:
                name = "W" * 75
                description = long_description("[UNBROKEN PROPERTY NAME]")
            elif index == 29:
                name = padded("A property name with many separate words", " word", 75)
                description = long_description("[VERBOSE PROPERTY]")

            records.append(Property(
                user=user,
                name=name,
                address=address,
                description=description,
                state=(
                    Property.State.DEACTIVATED
                    if index in (8, 17, 26)
                    else Property.State.ACTIVE
                ),
            ))
        return Property.objects.bulk_create(records)

    def _create_contacts(self, user):
        records = []
        for index, (first_name, last_name) in enumerate(
            (pair for first in FIRST_NAMES for pair in ((first, last) for last in LAST_NAMES))
        ):
            if index == 71:
                first_name = padded("[LAYOUT STRESS FIRST NAME]", "F", 50)
                last_name = padded("[LAYOUT STRESS LAST NAME]", "L", 50)
            elif index == 72:
                first_name = "N" * 50
                last_name = ""
            elif index == 73:
                first_name = padded("Hyphenated-and-multi-part-contact", "X", 50)
                last_name = padded("Very long family name", "Y", 50)
            elif index == 74:
                first_name = "Boundary"
                last_name = "Z" * 50

            records.append(Contact(
                user=user,
                first_name=first_name,
                last_name=last_name,
                state=(
                    Contact.State.DEACTIVATED
                    if index % 11 == 0
                    else Contact.State.ACTIVE
                ),
            ))
        contacts = Contact.objects.bulk_create(records)

        methods = []
        for index, contact in enumerate(contacts):
            variant = index % 6
            safe_name = f"contact{index + 1:02d}"
            if variant in (1, 3, 4, 5):
                methods.append(ContactMethod(
                    contact=contact,
                    type=ContactMethod.Type.EMAIL,
                    value=f"{safe_name}@example.com",
                ))
            if variant in (2, 3, 4, 5):
                methods.append(ContactMethod(
                    contact=contact,
                    type=ContactMethod.Type.TELEPHONE,
                    value=f"+4477009{index + 1:05d}",
                ))
            if variant == 4:
                methods.append(ContactMethod(
                    contact=contact,
                    type=ContactMethod.Type.EMAIL,
                    value=f"{safe_name}.work@example.com",
                ))
            if variant == 5:
                methods.append(ContactMethod(
                    contact=contact,
                    type=ContactMethod.Type.TELEPHONE,
                    value=f"+4420794{index + 1:05d}",
                ))
        ContactMethod.objects.bulk_create(methods)
        return contacts

    def _create_issues(self, user, properties, today):
        records = []
        for index, (title, description) in enumerate(ISSUE_DETAILS):
            state = Issue.State.ACTIVE
            terminated_at = None
            if 18 <= index <= 22:
                state = Issue.State.RESOLVED
                terminated_at = timezone.now() - timedelta(days=index - 16)
            elif index >= 23:
                state = Issue.State.DISMISSED
                terminated_at = timezone.now() - timedelta(days=index - 20)

            if index >= 22:
                title = padded(f"[LAYOUT STRESS ISSUE {index - 21}]", "I", 100)
                description = long_description("[1,000 CHARACTER ISSUE DESCRIPTION]")

            deadline = None if index % 6 == 0 else today + timedelta(days=index - 12)
            records.append(Issue(
                user=user,
                property=None if index % 5 == 0 else properties[index % len(properties)],
                state=state,
                priority=(index % 4) + 1,
                title=title,
                description=description,
                resolution_deadline=deadline,
                terminated_at=terminated_at,
            ))
        return Issue.objects.bulk_create(records)

    def _create_tasks(self, user, properties, issues, today):
        records = []
        for index in range(150):
            title = f"{TASK_ACTIONS[index % len(TASK_ACTIONS)]} {TASK_TARGETS[index % len(TASK_TARGETS)]}"
            description = (
                f"Coordinate this action and record the outcome. Reference task {index + 1:03d} "
                "when contacting the relevant tenant, contractor, or property owner."
            )
            if index >= 144:
                title = padded(f"[LAYOUT STRESS TASK {index - 143}]", "T", 100)
                description = long_description("[1,000 CHARACTER TASK DESCRIPTION]")

            relation = index % 3
            property_record = properties[index % len(properties)] if relation == 1 else None
            issue = issues[index % len(issues)] if relation == 2 else None

            state = Task.State.ACTIVE
            terminated_at = None
            if index % 10 in (0, 1):
                state = Task.State.COMPLETED
                terminated_at = timezone.now() - timedelta(days=index % 18)
            elif index % 10 == 2:
                state = Task.State.DISMISSED
                terminated_at = timezone.now() - timedelta(days=index % 12)

            scheduled_date = None if index % 4 == 0 else today + timedelta(days=(index % 31) - 15)
            completion_deadline = None if index % 5 == 0 else (
                (scheduled_date or today) + timedelta(days=2 + index % 6)
            )
            records.append(Task(
                user=user,
                property=property_record,
                issue=issue,
                state=state,
                priority=(index % 4) + 1,
                title=title,
                description=description,
                scheduled_date=scheduled_date,
                completion_deadline=completion_deadline,
                terminated_at=terminated_at,
            ))
        return Task.objects.bulk_create(records)

    def _create_events(self, user, properties, contacts, today):
        records = []
        for index, original_title in enumerate(EVENT_TITLES):
            title = original_title
            description = (
                "Confirm access arrangements with attendees and add any outcome or follow-up "
                "work to the relevant property record after the appointment."
            )
            if index >= 27:
                title = padded(f"[LAYOUT STRESS EVENT {index - 26}]", "E", 100)
                description = long_description("[1,000 CHARACTER EVENT DESCRIPTION]")

            if index < 20:
                state = Event.State.SCHEDULED
                day = today + timedelta(days=index % 16)
                terminated_at = None
            elif index < 27:
                state = Event.State.OCCURRED
                day = today - timedelta(days=index - 18)
                terminated_at = aware_datetime(day, 18)
            else:
                state = Event.State.CANCELLED
                day = today + timedelta(days=index - 24)
                terminated_at = timezone.now() - timedelta(days=1)

            all_day = index % 5 == 0
            start_hour = 8 + index % 10
            records.append(Event(
                user=user,
                property=None if index % 4 == 0 else properties[index % len(properties)],
                state=state,
                title=title,
                description=description,
                scheduled_date=day,
                all_day=all_day,
                start_time=None if all_day else time(start_hour, 0),
                end_time=None if all_day else time(start_hour + 1, 0),
                user_participation_required=index % 3 == 0,
                user_presence_required=index % 6 == 0,
                terminated_at=terminated_at,
            ))
        for index, title in enumerate(OCTOBER_1_DENSITY_TITLES):
            hour = 9 + index
            records.append(Event(
                user=user,
                property=properties[index % len(properties)],
                state=Event.State.SCHEDULED,
                title=title,
                description="Calendar density example: several appointments on one day.",
                scheduled_date=date(2026, 10, 1),
                all_day=False,
                start_time=time(hour, 0),
                end_time=time(hour + 1, 0),
            ))
        events = Event.objects.bulk_create(records)

        links = []
        active_contacts = [
            contact for contact in contacts
            if contact.state == Contact.State.ACTIVE
        ]
        for index, event in enumerate(events):
            participant_count = index % 5
            for offset in range(participant_count):
                contact = active_contacts[(index * 3 + offset) % len(active_contacts)]
                links.append(EventContact(event=event, contact=contact))
        EventContact.objects.bulk_create(links)
        return events

    def _create_notes(self, user, contacts):
        records = []
        general_notes = (
            "Review outstanding contractor invoices before Friday.",
            "Prepare the monthly owner update after closing overdue work.",
            "Check upcoming safety-certificate dates across the portfolio.",
            "Follow up on keys that have not yet been returned to the office.",
            "Confirm next week's inspection schedule with the maintenance team.",
            "Update emergency contact details for the managed blocks.",
        )
        records.extend(Note(user=user, content=content) for content in general_notes)

        for index in range(12):
            content = (
                "Prefers contact by email after 17:00. "
                "Confirm appointments at least one day in advance."
            )
            if index >= 10:
                content = long_description("[250 CHARACTER CONTACT NOTE]", 250)
            records.append(Note(
                user=user,
                contact=contacts[index],
                content=content,
            ))
        return Note.objects.bulk_create(records)
