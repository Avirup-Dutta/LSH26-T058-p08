from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SchoolClass(Base):
    __tablename__ = "school_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    session_year: Mapped[str] = mapped_column(String(16))

    students: Mapped[List["Student"]] = relationship(back_populates="school_class")


class Subject(Base):
    """A subject definition. Component full/pass marks live here, not in code."""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    has_practical: Mapped[bool] = mapped_column(Boolean, default=False)
    theory_full: Mapped[int] = mapped_column(Integer, default=100)
    theory_pass: Mapped[int] = mapped_column(Integer, default=33)
    practical_full: Mapped[int] = mapped_column(Integer, default=0)
    practical_pass: Mapped[int] = mapped_column(Integer, default=0)
    display_order: Mapped[int] = mapped_column(Integer, default=0)


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roll: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id"))
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    school_class: Mapped["SchoolClass"] = relationship(back_populates="students")
    marks: Mapped[List["Mark"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class Mark(Base):
    """One student, one subject. NULL obtained mark means absent in that part."""

    __tablename__ = "marks"
    __table_args__ = (UniqueConstraint("student_id", "subject_id", name="uq_mark"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    theory_obtained: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    practical_obtained: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    theory_absent: Mapped[bool] = mapped_column(Boolean, default=False)
    practical_absent: Mapped[bool] = mapped_column(Boolean, default=False)

    student: Mapped["Student"] = relationship(back_populates="marks")
    subject: Mapped["Subject"] = relationship()


class StudentResult(Base):
    """Snapshot of a computed result, so published numbers are reproducible."""

    __tablename__ = "student_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), unique=True
    )
    gpa: Mapped[float] = mapped_column(Float)
    letter: Mapped[str] = mapped_column(String(4))
    passed: Mapped[bool] = mapped_column(Boolean)
    gpa_without_optional: Mapped[float] = mapped_column(Float)
    optional_bonus: Mapped[float] = mapped_column(Float)
    compulsory_average_mark: Mapped[float] = mapped_column(Float)
    flags: Mapped[str] = mapped_column(String(300), default="")
    failing_subjects: Mapped[str] = mapped_column(String(300), default="")
    trace_json: Mapped[str] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
