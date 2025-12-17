from __future__ import annotations

import argparse
import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import PROJECT_ROOT
from .db import engine, init_db, session_scope
from .models import Base, Course, Enrollment, Mark, Student
from .services import ServiceError, add_mark, create_course, create_student, enroll_student, set_attendance


def _get_student_by_roll(session: Session, roll_no: str) -> Student | None:
    return session.execute(select(Student).where(Student.roll_no == roll_no)).scalar_one_or_none()


def _get_course_by_code(session: Session, code: str) -> Course | None:
    return session.execute(select(Course).where(Course.code == code)).scalar_one_or_none()


def _get_enrollment(session: Session, student_id: int, course_id: int) -> Enrollment | None:
    stmt = select(Enrollment).where(
        Enrollment.student_id == student_id,
        Enrollment.course_id == course_id,
    )
    return session.execute(stmt).scalar_one_or_none()


def _marks_count(session: Session, enrollment_id: int) -> int:
    return int(
        session.execute(
            select(func.count(Mark.id)).where(Mark.enrollment_id == enrollment_id)
        ).scalar_one()
    )


def seed_demo_data(*, reset: bool = False, rng_seed: int = 42) -> dict[str, int]:
    """Seed the database with deterministic demo data.

    - Safe to run multiple times: it will not duplicate demo students/courses/enrollments.
    - Marks are only created if an enrollment has no marks yet.

    Returns counts of inserted/updated records.
    """

    # Ensure local data dir exists for SQLite default.
    (PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)

    if reset:
        Base.metadata.drop_all(engine)

    init_db()

    rng = random.Random(rng_seed)

    courses_seed = [
        ("CS301", "Data Structures & Algorithms", 3, 4),
        ("CS302", "Database Management Systems", 3, 4),
        ("CS303", "Operating Systems", 3, 4),
        ("CS304", "Computer Networks", 3, 4),
        ("MA301", "Discrete Mathematics", 3, 3),
        ("HS301", "Professional Communication", 3, 2),
    ]

    first_names = [
        "Aarav",
        "Aditya",
        "Ananya",
        "Ayesha",
        "Diya",
        "Ishaan",
        "Kavya",
        "Meera",
        "Neha",
        "Nikhil",
        "Priya",
        "Rahul",
        "Riya",
        "Rohit",
        "Sanya",
        "Shreya",
        "Siddharth",
        "Tanvi",
        "Varun",
        "Yash",
    ]

    last_names = [
        "Sharma",
        "Verma",
        "Gupta",
        "Singh",
        "Patel",
        "Mishra",
        "Jain",
        "Khan",
        "Yadav",
        "Joshi",
    ]

    counts = {
        "students_created": 0,
        "courses_created": 0,
        "enrollments_created": 0,
        "attendance_set": 0,
        "marks_created": 0,
    }

    with session_scope() as session:
        # Courses
        courses: list[Course] = []
        for code, name, sem, credits in courses_seed:
            code = code.strip().upper()
            c = _get_course_by_code(session, code)
            if c is None:
                c = create_course(session, code=code, name=name, semester=sem, credits=credits)
                counts["courses_created"] += 1
            courses.append(c)

        # Students
        students: list[Student] = []
        for i in range(1, 21):
            roll_no = f"DEMO-{i:03d}"
            s = _get_student_by_roll(session, roll_no)
            if s is None:
                fn = rng.choice(first_names)
                ln = rng.choice(last_names)
                name = f"{fn} {ln}"
                email = f"demo{i:03d}@example.com"
                phone = f"9{rng.randint(100000000, 999999999)}"

                s = create_student(
                    session,
                    roll_no=roll_no,
                    name=name,
                    department="CSE",
                    semester=3,
                    email=email,
                    phone=phone,
                )
                counts["students_created"] += 1
            students.append(s)

        # Enrollments + attendance + marks
        for s in students:
            # Pick 4 distinct courses per student
            chosen = rng.sample(courses, k=4)

            for c in chosen:
                e = _get_enrollment(session, s.id, c.id)
                if e is None:
                    try:
                        e = enroll_student(session, student_id=s.id, course_id=c.id)
                        counts["enrollments_created"] += 1
                    except ServiceError:
                        # In case of race/duplicate, re-fetch
                        e = _get_enrollment(session, s.id, c.id)
                        if e is None:
                            continue

                # Attendance: total fixed, attended varies
                total_classes = 40
                attended = rng.randint(24, 40)

                # Force a few at-risk cases for demo screenshots
                if s.roll_no in {"DEMO-003", "DEMO-014"} and c.code in {"CS302", "CS303"}:
                    attended = rng.randint(10, 20)  # < 75%

                set_attendance(
                    session,
                    enrollment_id=e.id,
                    total_classes=total_classes,
                    attended_classes=attended,
                )
                counts["attendance_set"] += 1

                # Only add marks if none exist for this enrollment (idempotent)
                if _marks_count(session, e.id) == 0:
                    # Assessments total 100
                    # Mid Sem: /30, Assignment: /20, End Sem: /50
                    mid = rng.randint(10, 30)
                    assign = rng.randint(5, 20)
                    end = rng.randint(15, 50)

                    # Force a few low-marks cases
                    if s.roll_no in {"DEMO-007", "DEMO-014"} and c.code in {"MA301", "CS301"}:
                        mid = rng.randint(5, 12)
                        assign = rng.randint(2, 8)
                        end = rng.randint(10, 18)  # total often < 40

                    add_mark(
                        session,
                        enrollment_id=e.id,
                        assessment="Mid Sem",
                        marks_obtained=float(mid),
                        max_marks=30.0,
                    )
                    add_mark(
                        session,
                        enrollment_id=e.id,
                        assessment="Assignment",
                        marks_obtained=float(assign),
                        max_marks=20.0,
                    )
                    add_mark(
                        session,
                        enrollment_id=e.id,
                        assessment="End Sem",
                        marks_obtained=float(end),
                        max_marks=50.0,
                    )
                    counts["marks_created"] += 3

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed CARPAS with demo/synthetic data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables before seeding (DANGEROUS: deletes existing data).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic demo data (default: 42).",
    )

    args = parser.parse_args(argv)

    counts = seed_demo_data(reset=args.reset, rng_seed=args.seed)
    print("Demo data ready:")
    for k, v in counts.items():
        print(f"- {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
