from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .models import Attendance, Course, Enrollment, Mark, Student


def cleanup_duplicates(session: Session) -> None:
    """Best-effort cleanup for historical duplicates.

    Why this exists:
    - SQLAlchemy `create_all()` does not retrofit constraints into an existing SQLite DB.
    - If an older DB file was created without unique constraints, duplicates can exist and
      show up as repeated rows in the UI.

    Strategy:
    - Deduplicate `Student` by `roll_no` and `Course` by `code` by re-pointing enrollments.
    - Deduplicate `Enrollment` by (`student_id`, `course_id`) by merging child rows:
      - Move marks to the kept enrollment.
      - Merge attendance (keep max totals/attended).

    This is intentionally conservative and only touches obvious duplicates.
    """

    # -----------------
    # Students (roll_no)
    # -----------------
    dup_rolls = session.execute(
        select(Student.roll_no)
        .where(Student.roll_no.is_not(None))
        .group_by(Student.roll_no)
        .having(func.count(Student.id) > 1)
    ).scalars().all()

    for roll_no in dup_rolls:
        students = (
            session.execute(select(Student).where(Student.roll_no == roll_no).order_by(Student.id))
            .scalars()
            .all()
        )
        if len(students) < 2:
            continue

        keep = students[0]
        for dup in students[1:]:
            session.execute(
                Enrollment.__table__.update()
                .where(Enrollment.student_id == dup.id)
                .values(student_id=keep.id)
            )
            session.delete(dup)

    # -----------------
    # Courses (code)
    # -----------------
    dup_codes = session.execute(
        select(Course.code)
        .where(Course.code.is_not(None))
        .group_by(Course.code)
        .having(func.count(Course.id) > 1)
    ).scalars().all()

    for code in dup_codes:
        courses = (
            session.execute(select(Course).where(Course.code == code).order_by(Course.id))
            .scalars()
            .all()
        )
        if len(courses) < 2:
            continue

        keep = courses[0]
        for dup in courses[1:]:
            session.execute(
                Enrollment.__table__.update()
                .where(Enrollment.course_id == dup.id)
                .values(course_id=keep.id)
            )
            session.delete(dup)

    session.flush()

    # -----------------
    # Attendance (enrollment_id)
    # -----------------
    dup_att_enrollments = session.execute(
        select(Attendance.enrollment_id)
        .where(Attendance.enrollment_id.is_not(None))
        .group_by(Attendance.enrollment_id)
        .having(func.count(Attendance.id) > 1)
    ).scalars().all()

    for enrollment_id in dup_att_enrollments:
        rows = (
            session.execute(
                select(Attendance)
                .where(Attendance.enrollment_id == enrollment_id)
                .order_by(Attendance.id)
            )
            .scalars()
            .all()
        )
        if len(rows) < 2:
            continue

        keep = rows[0]
        for dup in rows[1:]:
            keep.total_classes = max(keep.total_classes, dup.total_classes)
            keep.attended_classes = max(keep.attended_classes, dup.attended_classes)
            if keep.attended_classes > keep.total_classes:
                keep.attended_classes = keep.total_classes
            session.delete(dup)

    session.flush()

    # -----------------
    # Enrollments (student_id, course_id)
    # -----------------
    dup_pairs = session.execute(
        select(Enrollment.student_id, Enrollment.course_id)
        .group_by(Enrollment.student_id, Enrollment.course_id)
        .having(func.count(Enrollment.id) > 1)
    ).all()

    for student_id, course_id in dup_pairs:
        enrollments = (
            session.execute(
                select(Enrollment)
                .where(Enrollment.student_id == student_id)
                .where(Enrollment.course_id == course_id)
                .order_by(Enrollment.id)
            )
            .scalars()
            .all()
        )
        if len(enrollments) < 2:
            continue

        keep = enrollments[0]
        for dup in enrollments[1:]:
            # Move marks
            session.execute(
                Mark.__table__.update()
                .where(Mark.enrollment_id == dup.id)
                .values(enrollment_id=keep.id)
            )

            # Merge attendance
            keep_att = session.execute(
                select(Attendance).where(Attendance.enrollment_id == keep.id)
            ).scalar_one_or_none()
            dup_att = session.execute(
                select(Attendance).where(Attendance.enrollment_id == dup.id)
            ).scalar_one_or_none()

            if dup_att is not None:
                if keep_att is None:
                    dup_att.enrollment_id = keep.id
                else:
                    # Merge in a predictable way.
                    keep_att.total_classes = max(keep_att.total_classes, dup_att.total_classes)
                    keep_att.attended_classes = max(keep_att.attended_classes, dup_att.attended_classes)
                    if keep_att.attended_classes > keep_att.total_classes:
                        keep_att.attended_classes = keep_att.total_classes
                    session.delete(dup_att)

            session.delete(dup)

    session.flush()


def ensure_sqlite_unique_indexes(session: Session) -> None:
    """Ensure key unique indexes exist for SQLite DBs.

    Note: This is only applied to SQLite because adding constraints in-place is not
    something `create_all()` handles for existing DBs.
    """

    bind = session.get_bind()
    if bind is None or bind.dialect.name != "sqlite":
        return

    # If duplicates still exist for any of these, SQLite will error here. By the time we
    # get here, `cleanup_duplicates()` should have removed the obvious cases.
    session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_students_roll_no ON students (roll_no)"))
    session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_courses_code ON courses (code)"))
    session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_attendance_enrollment ON attendance (enrollment_id)"))
    session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_enrollments_student_course ON enrollments (student_id, course_id)"
        )
    )
