"""Database models using SQLAlchemy."""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()


class QueryStatus(enum.Enum):
    """Query status enumeration."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TrendQuery(Base):
    """Trend query model - equivalent to Prisma TrendQuery."""
    __tablename__ = 'trend_queries'
    
    id = Column(String, primary_key=True)
    keyword = Column(String, nullable=False)
    country = Column(String(2), nullable=False)
    window_days = Column(Integer, nullable=False)
    baseline_days = Column(Integer, nullable=False)
    status = Column(SQLEnum(QueryStatus), nullable=False, default=QueryStatus.PENDING)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<TrendQuery(id={self.id}, keyword={self.keyword}, status={self.status})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'keyword': self.keyword,
            'country': self.country,
            'window_days': self.window_days,
            'baseline_days': self.baseline_days,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'error_message': self.error_message,
        }
