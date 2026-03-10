"""
Database models for the GPT Records AI Artist Manager.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class OutreachStatus(str, enum.Enum):
    PENDING = "pending"
    CONTACTED = "contacted"
    FOLLOW_UP_SENT = "follow_up_sent"
    RESPONDED_POSITIVE = "responded_positive"
    RESPONDED_NEGATIVE = "responded_negative"
    BOOKED = "booked"
    NO_RESPONSE = "no_response"


class Platform(str, enum.Enum):
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    SOUNDCLOUD = "soundcloud"
    MIXCLOUD = "mixcloud"
    RESIDENT_ADVISOR = "resident_advisor"
    BANDCAMP = "bandcamp"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class Venue(Base):
    """A club, bar, festival, or event space to target for bookings."""

    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    city = Column(String(100))
    country = Column(String(100))
    contact_name = Column(String(200))
    contact_email = Column(String(200))
    website = Column(String(500))
    genres = Column(String(500))  # comma-separated genre tags
    capacity = Column(Integer)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    outreach_records = relationship("OutreachRecord", back_populates="venue")


class OutreachRecord(Base):
    """Tracks every contact attempt with a venue or promoter."""

    __tablename__ = "outreach_records"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=True)
    promoter_name = Column(String(200))
    contact_email = Column(String(200))
    email_subject = Column(String(500))
    email_body = Column(Text)
    status = Column(
        String(50),
        default=OutreachStatus.PENDING,
        nullable=False,
    )
    contacted_at = Column(DateTime)
    follow_up_at = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text)

    venue = relationship("Venue", back_populates="outreach_records")


class SocialPost(Base):
    """Generated social media content."""

    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    hashtags = Column(Text)
    post_type = Column(String(100))  # announcement, mix-release, promo, repost-request
    created_at = Column(DateTime, default=datetime.utcnow)
    scheduled_at = Column(DateTime)
    posted_at = Column(DateTime)
    notes = Column(Text)


class MetricEntry(Base):
    """Point-in-time snapshot of key growth metrics."""

    __tablename__ = "metric_entries"

    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    monthly_listeners = Column(Integer)
    soundcloud_followers = Column(Integer)
    instagram_followers = Column(Integer)
    mixcloud_followers = Column(Integer)
    resident_advisor_followers = Column(Integer)
    bandcamp_sales = Column(Integer)
    notes = Column(Text)


class WeeklyStrategy(Base):
    """AI-generated weekly promotion and booking strategy."""

    __tablename__ = "weekly_strategies"

    id = Column(Integer, primary_key=True, index=True)
    week_of = Column(DateTime, nullable=False)
    strategy = Column(Text, nullable=False)
    goals = Column(Text)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
