"""
Data models for storing and managing group itinerary information.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, time
from enum import Enum
import json

class EventType(Enum):
    """Types of itinerary events."""
    FLIGHT = "flight"
    HOTEL = "hotel"
    RESTAURANT = "restaurant"
    ACTIVITY = "activity"
    TRANSPORT = "transport"
    MEETING = "meeting"
    FREE_TIME = "free_time"
    OTHER = "other"

class Priority(Enum):
    """Priority levels for events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Contact:
    """Contact information for people, venues, or services."""
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None

@dataclass
class Location:
    """Location information with coordinates and details."""
    name: str
    address: str
    city: str
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    notes: Optional[str] = None

@dataclass
class ItineraryEvent:
    """Individual event in the itinerary."""
    id: str
    title: str
    event_type: EventType
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    location: Optional[Location] = None
    description: Optional[str] = None
    contacts: List[Contact] = field(default_factory=list)
    cost: Optional[float] = None
    currency: str = "USD"
    priority: Priority = Priority.MEDIUM
    attendees: List[str] = field(default_factory=list)
    confirmation_number: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class GroupMember:
    """Information about a group member."""
    name: str
    email: str
    phone: Optional[str] = None
    role: str = "member"  # member, organizer, admin
    preferences: Dict[str, Any] = field(default_factory=dict)
    emergency_contact: Optional[Contact] = None
    joined_at: datetime = field(default_factory=datetime.now)

@dataclass
class TripItinerary:
    """Complete itinerary for a group trip."""
    id: str
    title: str
    description: Optional[str] = None
    start_date: date = field(default_factory=date.today)
    end_date: date = field(default_factory=date.today)
    destination: Optional[Location] = None
    organizer: Optional[GroupMember] = None
    members: List[GroupMember] = field(default_factory=list)
    events: List[ItineraryEvent] = field(default_factory=list)
    budget_total: Optional[float] = None
    budget_per_person: Optional[float] = None
    currency: str = "USD"
    emergency_contacts: List[Contact] = field(default_factory=list)
    important_info: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_event(self, event: ItineraryEvent) -> None:
        """Add an event to the itinerary."""
        self.events.append(event)
        self.updated_at = datetime.now()
        # Sort events by start time
        self.events.sort(key=lambda e: e.start_datetime)
    
    def remove_event(self, event_id: str) -> bool:
        """Remove an event from the itinerary."""
        for i, event in enumerate(self.events):
            if event.id == event_id:
                del self.events[i]
                self.updated_at = datetime.now()
                return True
        return False
    
    def get_event(self, event_id: str) -> Optional[ItineraryEvent]:
        """Get an event by ID."""
        for event in self.events:
            if event.id == event_id:
                return event
        return None
    
    def get_events_by_date(self, target_date: date) -> List[ItineraryEvent]:
        """Get all events for a specific date."""
        return [event for event in self.events 
                if event.start_datetime.date() == target_date]
    
    def get_events_by_type(self, event_type: EventType) -> List[ItineraryEvent]:
        """Get all events of a specific type."""
        return [event for event in self.events if event.event_type == event_type]
    
    def add_member(self, member: GroupMember) -> None:
        """Add a member to the group."""
        self.members.append(member)
        self.updated_at = datetime.now()
    
    def remove_member(self, email: str) -> bool:
        """Remove a member by email."""
        for i, member in enumerate(self.members):
            if member.email == email:
                del self.members[i]
                self.updated_at = datetime.now()
                return True
        return False
    
    def get_member(self, email: str) -> Optional[GroupMember]:
        """Get a member by email."""
        for member in self.members:
            if member.email == email:
                return member
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert itinerary to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert itinerary to JSON string."""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TripItinerary':
        """Create itinerary from dictionary."""
        # Convert string dates back to date objects
        if isinstance(data.get('start_date'), str):
            data['start_date'] = date.fromisoformat(data['start_date'])
        if isinstance(data.get('end_date'), str):
            data['end_date'] = date.fromisoformat(data['end_date'])
        
        # Convert datetime strings back to datetime objects
        for field_name in ['created_at', 'updated_at']:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        
        # Convert events
        if 'events' in data:
            events = []
            for event_data in data['events']:
                # Convert datetime strings
                for dt_field in ['start_datetime', 'end_datetime', 'created_at', 'updated_at']:
                    if isinstance(event_data.get(dt_field), str):
                        event_data[dt_field] = datetime.fromisoformat(event_data[dt_field])
                
                # Convert enums
                if 'event_type' in event_data:
                    event_data['event_type'] = EventType(event_data['event_type'])
                if 'priority' in event_data:
                    event_data['priority'] = Priority(event_data['priority'])
                
                # Convert location
                if 'location' in event_data and event_data['location']:
                    event_data['location'] = Location(**event_data['location'])
                
                # Convert contacts
                if 'contacts' in event_data:
                    contacts = [Contact(**contact_data) for contact_data in event_data['contacts']]
                    event_data['contacts'] = contacts
                
                events.append(ItineraryEvent(**event_data))
            data['events'] = events
        
        # Convert members
        if 'members' in data:
            members = []
            for member_data in data['members']:
                if isinstance(member_data.get('joined_at'), str):
                    member_data['joined_at'] = datetime.fromisoformat(member_data['joined_at'])
                if 'emergency_contact' in member_data and member_data['emergency_contact']:
                    member_data['emergency_contact'] = Contact(**member_data['emergency_contact'])
                members.append(GroupMember(**member_data))
            data['members'] = members
        
        # Convert organizer
        if 'organizer' in data and data['organizer']:
            organizer_data = data['organizer']
            if isinstance(organizer_data.get('joined_at'), str):
                organizer_data['joined_at'] = datetime.fromisoformat(organizer_data['joined_at'])
            if 'emergency_contact' in organizer_data and organizer_data['emergency_contact']:
                organizer_data['emergency_contact'] = Contact(**organizer_data['emergency_contact'])
            data['organizer'] = GroupMember(**organizer_data)
        
        # Convert destination
        if 'destination' in data and data['destination']:
            data['destination'] = Location(**data['destination'])
        
        # Convert emergency contacts
        if 'emergency_contacts' in data:
            contacts = [Contact(**contact_data) for contact_data in data['emergency_contacts']]
            data['emergency_contacts'] = contacts
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TripItinerary':
        """Create itinerary from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

class ItineraryManager:
    """Manager class for handling itinerary operations."""
    
    def __init__(self):
        """Initialize the itinerary manager."""
        self.itineraries: Dict[str, TripItinerary] = {}
    
    def create_itinerary(self, itinerary: TripItinerary) -> None:
        """Store an itinerary."""
        self.itineraries[itinerary.id] = itinerary
    
    def get_itinerary(self, itinerary_id: str) -> Optional[TripItinerary]:
        """Get an itinerary by ID."""
        return self.itineraries.get(itinerary_id)
    
    def update_itinerary(self, itinerary: TripItinerary) -> None:
        """Update an existing itinerary."""
        itinerary.updated_at = datetime.now()
        self.itineraries[itinerary.id] = itinerary
    
    def delete_itinerary(self, itinerary_id: str) -> bool:
        """Delete an itinerary."""
        if itinerary_id in self.itineraries:
            del self.itineraries[itinerary_id]
            return True
        return False
    
    def list_itineraries(self) -> List[TripItinerary]:
        """List all itineraries."""
        return list(self.itineraries.values())
    
    def search_events(self, query: str, itinerary_id: Optional[str] = None) -> List[ItineraryEvent]:
        """Search for events by query string."""
        results = []
        itineraries_to_search = [self.itineraries[itinerary_id]] if itinerary_id and itinerary_id in self.itineraries else self.itineraries.values()
        
        query_lower = query.lower()
        for itinerary in itineraries_to_search:
            for event in itinerary.events:
                if (query_lower in event.title.lower() or 
                    (event.description and query_lower in event.description.lower()) or
                    (event.location and query_lower in event.location.name.lower()) or
                    query_lower in event.event_type.value):
                    results.append(event)
        
        return results