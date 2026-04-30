from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TrendSignal(BaseModel):
    query: str
    delta_yoy: float
    segment_age: Optional[str] = None


class Offer(BaseModel):
    title: str
    value: str
    audience: str


class VoiceProfile(BaseModel):
    tone: str
    vocab_allowed: List[str]
    taboos: List[str]


class PeerStats(BaseModel):
    avg_rating: float
    avg_reviews: int
    avg_ctr: float
    scope: str


class DigestItem(BaseModel):
    id: str
    kind: str
    title: str
    source: str
    content: Optional[str] = None


class SeasonalBeat(BaseModel):
    month_range: str
    note: str


class PatientContent(BaseModel):
    id: str
    title: str
    channel: str
    body: str


class CategoryContext(BaseModel):
    slug: str
    offer_catalog: List[Offer]
    voice: VoiceProfile
    peer_stats: PeerStats
    digest: List[DigestItem]
    patient_content_library: List[PatientContent]
    seasonal_beats: List[SeasonalBeat]
    trend_signals: List[TrendSignal]


class Identity(BaseModel):
    name: str
    city: str
    locality: str
    place_id: Optional[str] = None
    verified: bool
    languages: List[str]


class Subscription(BaseModel):
    status: str
    plan: str
    days_remaining: int


class Performance(BaseModel):
    window_days: int
    views: int
    calls: int
    directions: int
    leads: int
    ctr: float
    delta_7d: Optional[Dict[str, float]] = None


class MerchantContext(BaseModel):
    merchant_id: str
    category_slug: str
    identity: Identity
    subscription: Subscription
    performance: Performance
    offers: List[Offer]
    signals: List[str]
    conversation_history: Optional[List[Dict[str, Any]]] = None
    customer_aggregate: Optional[Dict[str, Any]] = None


class TriggerContext(BaseModel):
    id: str
    scope: str  # "merchant" or "customer"
    kind: str
    source: str  # "external" or "internal"
    payload: Dict[str, Any]
    urgency: int
    suppression_key: str
    expires_at: datetime


class Consent(BaseModel):
    opted_in_at: datetime
    scope: List[str]


class CustomerContext(BaseModel):
    customer_id: str
    merchant_id: str
    identity: Dict[str, Any]
    relationship: Dict[str, Any]
    state: str
    preferences: Optional[Dict[str, Any]] = None
    consent: Consent


class ContextPayload(BaseModel):
    scope: str  # "category", "merchant", "customer", "trigger"
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: datetime


class HealthzResponse(BaseModel):
    status: str
    uptime_seconds: int
    contexts_loaded: Dict[str, int]


class MetadataResponse(BaseModel):
    team_name: str
    team_members: List[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: datetime
    groq_default: Optional[bool] = False
    default_provider: Optional[str] = None


class TickResponse(BaseModel):
    actions: List[Dict[str, Any]]


class ReplyResponse(BaseModel):
    action: str  # "send", "wait", "end"
    body: Optional[str] = None
    cta: Optional[str] = None
    rationale: str
    wait_seconds: Optional[int] = None
