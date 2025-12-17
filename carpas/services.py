from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .models import Attendance, Course, Enrollment, Mark, Student


class ServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class EnrollmentSummary:
    enrollment_id: int
    course_code: str
    course_name: str
    attendance_pct: float | None
    marks_pct: float | None


def _pct(numer: float, denom: float) -> float | None:
    if denom <= 0:
        return None
    return round((numer / denom) * 100.0, 2)


# -----------------
# Students
# -----------------

def create_student(
    session: Session,
    *,
    roll_no: str,
    name: str,
    department: str | None = None,
    semester: int | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> Student:
    student = Student(
        roll_no=roll_no.strip(),
        name=name.strip(),
        department=(department.strip() if department else None),
        semester=semester,
        email=(email.strip() if email else None),
        phone=(phone.strip() if phone else None),
    )
    session.add(student)
    try:
        session.flush()
    except IntegrityError as e:
        raise ServiceError("Roll number already exists.") from e
    return student


def list_students(session: Session) -> list[Student]:
    return list(session.execute(select(Student).order_by(Student.roll_no)).scalars().all())


def update_student(
    session: Session,
    *,
    student_id: int,
    roll_no: str,
    name: str,
    department: str | None,
    semester: int | None,
    email: str | None,
    phone: str | None,
) -> Student:
    student = session.get(Student, student_id)
    if not student:
        raise ServiceError("Student not found.")

    student.roll_no = roll_no.strip()
    student.name = name.strip()
    student.department = department.strip() if department else None
    student.semester = semester
    student.email = email.strip() if email else None
    student.phone = phone.strip() if phone else None

    try:
        session.flush()
    except IntegrityError as e:
        raise ServiceError("Roll number already exists.") from e

    return student


def delete_student(session: Session, *, student_id: int) -> None:
    student = session.get(Student, student_id)
    if not student:
        raise ServiceError("Student not found.")
    session.delete(student)


# -----------------
# Courses
# -----------------

def create_course(
    session: Session,
    *,
    code: str,
    name: str,
    semester: int | None = None,
    credits: int | None = None,
) -> Course:
    course = Course(
        code=code.strip().upper(),
        name=name.strip(),
        semester=semester,
        credits=credits,
    )
    session.add(course)
    try:
        session.flush()
    except IntegrityError as e:
        raise ServiceError("Course code already exists.") from e
    return course


def list_courses(session: Session) -> list[Course]:
    return list(session.execute(select(Course).order_by(Course.code)).scalars().all())


def update_course(
    session: Session,
    *,
    course_id: int,
    code: str,
    name: str,
    semester: int | None,
    credits: int | None,
) -> Course:
    course = session.get(Course, course_id)
    if not course:
        raise ServiceError("Course not found.")

    course.code = code.strip().upper()
    course.name = name.strip()
    course.semester = semester
    course.credits = credits

    try:
        session.flush()
    except IntegrityError as e:
        raise ServiceError("Course code already exists.") from e

    return course


def delete_course(session: Session, *, course_id: int) -> None:
    course = session.get(Course, course_id)
    if not course:
        raise ServiceError("Course not found.")
    session.delete(course)


# -----------------
# Enrollment
# -----------------

def enroll_student(session: Session, *, student_id: int, course_id: int) -> Enrollment:
    student = session.get(Student, student_id)
    if not student:
        raise ServiceError("Student not found.")
    course = session.get(Course, course_id)
    if not course:
        raise ServiceError("Course not found.")

    enrollment = Enrollment(student_id=student_id, course_id=course_id)
    session.add(enrollment)
    try:
        session.flush()
    except IntegrityError as e:
        raise ServiceError("Student is already enrolled in this course.") from e
    return enrollment


def list_enrollments(session: Session) -> list[Enrollment]:
    stmt = (
        select(Enrollment)
        .options(joinedload(Enrollment.student), joinedload(Enrollment.course))
        .order_by(Enrollment.id.desc())
    )
    return list(session.execute(stmt).scalars().all())


def remove_enrollment(session: Session, *, enrollment_id: int) -> None:
    enrollment = session.get(Enrollment, enrollment_id)
    if not enrollment:
        raise ServiceError("Enrollment not found.")
    session.delete(enrollment)


# -----------------
# Attendance
# -----------------

def set_attendance(
    session: Session,
    *,
    enrollment_id: int,
    total_classes: int,
    attended_classes: int,
) -> Attendance:
    enrollment = session.get(Enrollment, enrollment_id)
    if not enrollment:
        raise ServiceError("Enrollment not found.")

    if total_classes < 0 or attended_classes < 0:
        raise ServiceError("Attendance values must be >= 0.")
    if attended_classes > total_classes:
        raise ServiceError("Attended classes cannot exceed total classes.")

    attendance = enrollment.attendance
    if attendance is None:
        attendance = Attendance(enrollment_id=enrollment_id)
        session.add(attendance)
        session.flush()

    attendance.total_classes = total_classes
    attendance.attended_classes = attended_classes
    session.flush()
    return attendance


# -----------------
# Marks
# -----------------

def add_mark(
    session: Session,
    *,
    enrollment_id: int,
    assessment: str,
    marks_obtained: float,
    max_marks: float,
) -> Mark:
    enrollment = session.get(Enrollment, enrollment_id)
    if not enrollment:
        raise ServiceError("Enrollment not found.")

    if max_marks <= 0:
        raise ServiceError("Max marks must be > 0.")
    if marks_obtained < 0 or marks_obtained > max_marks:
        raise ServiceError("Marks obtained must be between 0 and max marks.")

    mark = Mark(
        enrollment_id=enrollment_id,
        assessment=(assessment.strip() or "Exam"),
        marks_obtained=float(marks_obtained),
        max_marks=float(max_marks),
    )
    session.add(mark)
    session.flush()
    return mark


def list_marks_for_enrollment(session: Session, *, enrollment_id: int) -> list[Mark]:
    stmt = select(Mark).where(Mark.enrollment_id == enrollment_id).order_by(Mark.id.desc())
    return list(session.execute(stmt).scalars().all())


def delete_mark(session: Session, *, mark_id: int) -> None:
    mark = session.get(Mark, mark_id)
    if not mark:
        raise ServiceError("Mark not found.")
    session.delete(mark)


# -----------------
# Analysis
# -----------------

def get_student_enrollment_summaries(session: Session, *, student_id: int) -> list[EnrollmentSummary]:
    stmt = (
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .options(
            joinedload(Enrollment.course),
            joinedload(Enrollment.attendance),
            joinedload(Enrollment.marks),
        )
        .order_by(Enrollment.id)
    )
    # joinedload(Enrollment.marks) is a collection eager load; unique() de-duplicates parent rows.
    enrollments = session.execute(stmt).unique().scalars().all()

    summaries: list[EnrollmentSummary] = []
    for e in enrollments:
        total = e.attendance.total_classes if e.attendance else 0
        attended = e.attendance.attended_classes if e.attendance else 0
        attendance_pct = _pct(attended, total)

        obtained = sum(m.marks_obtained for m in e.marks)
        maximum = sum(m.max_marks for m in e.marks)
        marks_pct = _pct(obtained, maximum)

        summaries.append(
            EnrollmentSummary(
                enrollment_id=e.id,
                course_code=e.course.code,
                course_name=e.course.name,
                attendance_pct=attendance_pct,
                marks_pct=marks_pct,
            )
        )

    return summaries


def course_class_average_marks_pct(session: Session, *, course_id: int) -> float | None:
    # Average of per-enrollment percentages; computed in SQL using sums.
    # For enrollments with no marks, they are ignored.
    subq = (
        select(
            Mark.enrollment_id.label("enrollment_id"),
            func.sum(Mark.marks_obtained).label("obtained"),
            func.sum(Mark.max_marks).label("maximum"),
        )
        .join(Enrollment, Enrollment.id == Mark.enrollment_id)
        .where(Enrollment.course_id == course_id)
        .group_by(Mark.enrollment_id)
        .subquery()
    )

    stmt = select(func.avg((subq.c.obtained / subq.c.maximum) * 100.0))
    avg_pct = session.execute(stmt).scalar_one_or_none()
    return round(float(avg_pct), 2) if avg_pct is not None else None


def course_class_average_attendance_pct(session: Session, *, course_id: int) -> float | None:
    subq = (
        select(
            Attendance.enrollment_id.label("enrollment_id"),
            Attendance.attended_classes.label("attended"),
            Attendance.total_classes.label("total"),
        )
        .join(Enrollment, Enrollment.id == Attendance.enrollment_id)
        .where(Enrollment.course_id == course_id)
        .where(Attendance.total_classes > 0)
        .subquery()
    )

    stmt = select(func.avg((subq.c.attended / subq.c.total) * 100.0))
    avg_pct = session.execute(stmt).scalar_one_or_none()
    return round(float(avg_pct), 2) if avg_pct is not None else None


def find_at_risk(
    session: Session,
    *,
    attendance_threshold: float = 75.0,
    marks_threshold: float = 40.0,
) -> list[dict[str, object]]:
    # Compute in Python for simplicity (good enough for small college datasets).
    enrollments = session.execute(
        select(Enrollment)
        .options(
            joinedload(Enrollment.student),
            joinedload(Enrollment.course),
            joinedload(Enrollment.attendance),
            joinedload(Enrollment.marks),
        )
    ).unique().scalars().all()

    results: list[dict[str, object]] = []
    for e in enrollments:
        total = e.attendance.total_classes if e.attendance else 0
        attended = e.attendance.attended_classes if e.attendance else 0
        attendance_pct = _pct(attended, total)

        obtained = sum(m.marks_obtained for m in e.marks)
        maximum = sum(m.max_marks for m in e.marks)
        marks_pct = _pct(obtained, maximum)

        low_attendance = attendance_pct is not None and attendance_pct < attendance_threshold
        low_marks = marks_pct is not None and marks_pct < marks_threshold

        if low_attendance or low_marks:
            reasons: list[str] = []
            if low_attendance:
                reasons.append("Low attendance")
            if low_marks:
                reasons.append("Low marks")

            results.append(
                {
                    "enrollment_id": e.id,
                    "roll_no": e.student.roll_no,
                    "student_name": e.student.name,
                    "course_code": e.course.code,
                    "course_name": e.course.name,
                    "attendance_pct": attendance_pct,
                    "marks_pct": marks_pct,
                    "reason": ", ".join(reasons),
                }
            )

    return results
