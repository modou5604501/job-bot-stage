from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
from app.config.settings import Settings

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    company = Column(String(255))
    location = Column(String(255))
    description = Column(Text)
    url = Column(String(500), unique=True)
    source = Column(String(50))
    relevance_score = Column(Float)
    analysis = Column(Text)
    applied = Column(Boolean, default=False)
    apply_email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class JobDatabase:
    def __init__(self, settings: Settings):
        self.engine = create_engine(settings.database_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    async def save_jobs(self, jobs: list) -> list:
        """Sauvegarde les jobs, evite les doublons"""
        new_jobs = []
        with self.SessionLocal() as session:
            for job in jobs:
                existing = session.query(Job).filter_by(url=job["url"]).first()
                if not existing:
                    db_job = Job(
                        title=job["title"],
                        company=job["company"],
                        location=job["location"],
                        description=job["description"],
                        url=job["url"],
                        source=job["source"],
                        relevance_score=job.get("analysis", {}).get("score", 0),
                        analysis=str(job.get("analysis", {})),
                        apply_email=job.get("apply_email") or None,
                    )
                    session.add(db_job)
                    new_jobs.append(job)
            session.commit()
        return new_jobs

    async def mark_applied(self, url: str, apply_email: str):
        """Marque un job comme postule avec l'email utilise"""
        with self.SessionLocal() as session:
            job = session.query(Job).filter_by(url=url).first()
            if job:
                job.applied = True
                job.apply_email = apply_email
                session.commit()

    def get_applied_companies(self) -> list:
        """Retourne la liste des entreprises a qui on a postule"""
        with self.SessionLocal() as session:
            rows = session.query(Job).filter_by(applied=True).all()
            return [
                {
                    "company": r.company.lower(),
                    "apply_email": (r.apply_email or "").lower(),
                    "title": r.title,
                }
                for r in rows
            ]
