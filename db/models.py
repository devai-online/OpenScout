from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(255), nullable=False)
    country = Column(String(100), default="")
    min_emp = Column(Integer, default=0)
    max_emp = Column(Integer, default=0)
    limit = Column(Integer, default=30)
    notes = Column(Text, default="")
    status = Column(String(20), default="pending")
    log = Column(Text, default="")
    lead_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)

    leads = relationship("Lead", back_populates="session", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("search_sessions.id"), nullable=False, index=True)
    company = Column(String(255), nullable=False)
    website = Column(String(500), default="")
    email = Column(String(255), default="")
    phone = Column(String(64), default="")
    contact_person = Column(String(255), default="")
    contact_title = Column(String(255), default="")
    employee_count = Column(String(50), default="")
    country = Column(String(100), default="")
    description = Column(Text, default="")
    relevance_score = Column(Float, default=0.0)
    relevance_reason = Column(String(500), default="")
    source_url = Column(String(500), default="")
    found_at = Column(DateTime, default=utcnow)

    session = relationship("SearchSession", back_populates="leads")
