from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..config import APP_TITLE
from ..db import session_scope
from ..services import (
    ServiceError,
    add_mark,
    course_class_average_attendance_pct,
    course_class_average_marks_pct,
    create_course,
    create_student,
    delete_course,
    delete_mark,
    delete_student,
    enroll_student,
    find_at_risk,
    get_student_enrollment_summaries,
    list_courses,
    list_enrollments,
    list_marks_for_enrollment,
    list_students,
    remove_enrollment,
    set_attendance,
    update_course,
    update_student,
)


def _parse_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    return int(value)


def _parse_float(value: str) -> float:
    return float(value.strip())


def _parse_choice_id(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value.split(":", 1)[0])
    except ValueError:
        return None


class CarpasApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title(APP_TITLE)
        self.geometry("1100x650")
        self.minsize(1000, 600)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.students_tab = StudentsTab(notebook, app=self)
        self.courses_tab = CoursesTab(notebook, app=self)
        self.enrollments_tab = EnrollmentsTab(notebook, app=self)
        self.attendance_tab = AttendanceTab(notebook, app=self)
        self.marks_tab = MarksTab(notebook, app=self)
        self.analysis_tab = AnalysisTab(notebook, app=self)

        notebook.add(self.students_tab, text="Students")
        notebook.add(self.courses_tab, text="Courses")
        notebook.add(self.enrollments_tab, text="Enrollments")
        notebook.add(self.attendance_tab, text="Attendance")
        notebook.add(self.marks_tab, text="Marks")
        notebook.add(self.analysis_tab, text="Analysis")

        self.refresh_all()

    def refresh_all(self) -> None:
        self.students_tab.refresh()
        self.courses_tab.refresh()
        self.enrollments_tab.refresh()
        self.attendance_tab.refresh()
        self.marks_tab.refresh()
        self.analysis_tab.refresh()

    def refresh_reference_data(self) -> None:
        # Any tab that relies on student/course/enrollment lists should refresh its dropdowns.
        self.enrollments_tab.refresh_choices()
        self.attendance_tab.refresh_choices()
        self.marks_tab.refresh_choices()
        self.analysis_tab.refresh_choices()


class StudentsTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, *, app: CarpasApp) -> None:
        super().__init__(parent)
        self.app = app
        self.selected_student_id: int | None = None

        # Form
        self.roll_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.dept_var = tk.StringVar()
        self.sem_var = tk.StringVar()
        self.email_var = tk.StringVar()
        self.phone_var = tk.StringVar()

        form = ttk.LabelFrame(self, text="Student Details")
        form.pack(fill="x", padx=10, pady=10)

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text="Roll No *").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.roll_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Name *").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.name_var).grid(row=0, column=3, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Department").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.dept_var).grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Semester").grid(row=1, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.sem_var).grid(row=1, column=3, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Email").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.email_var).grid(row=2, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Phone").grid(row=2, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.phone_var).grid(row=2, column=3, sticky="ew", padx=6, pady=6)

        buttons = ttk.Frame(form)
        buttons.grid(row=3, column=0, columnspan=4, sticky="w", padx=6, pady=6)

        ttk.Button(buttons, text="Add", command=self.add_student).pack(side="left", padx=4)
        ttk.Button(buttons, text="Update", command=self.update_student).pack(side="left", padx=4)
        ttk.Button(buttons, text="Delete", command=self.delete_student).pack(side="left", padx=4)
        ttk.Button(buttons, text="Clear", command=self.clear_form).pack(side="left", padx=4)
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left", padx=4)

        # Table
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("roll_no", "name", "department", "semester", "email", "phone")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("roll_no", text="Roll No")
        self.tree.heading("name", text="Name")
        self.tree.heading("department", text="Department")
        self.tree.heading("semester", text="Semester")
        self.tree.heading("email", text="Email")
        self.tree.heading("phone", text="Phone")

        self.tree.column("roll_no", width=120, anchor="w")
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("department", width=160, anchor="w")
        self.tree.column("semester", width=90, anchor="center")
        self.tree.column("email", width=220, anchor="w")
        self.tree.column("phone", width=140, anchor="w")

        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

    def clear_form(self) -> None:
        self.selected_student_id = None
        self.roll_var.set("")
        self.name_var.set("")
        self.dept_var.set("")
        self.sem_var.set("")
        self.email_var.set("")
        self.phone_var.set("")
        self.tree.selection_remove(self.tree.selection())

    def on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        student_id = int(selection[0])
        self.selected_student_id = student_id

        with session_scope() as session:
            student = next((s for s in list_students(session) if s.id == student_id), None)
            if not student:
                return

            self.roll_var.set(student.roll_no or "")
            self.name_var.set(student.name or "")
            self.dept_var.set(student.department or "")
            self.sem_var.set("" if student.semester is None else str(student.semester))
            self.email_var.set(student.email or "")
            self.phone_var.set(student.phone or "")

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        with session_scope() as session:
            for s in list_students(session):
                self.tree.insert(
                    "",
                    "end",
                    iid=str(s.id),
                    values=(
                        s.roll_no,
                        s.name,
                        s.department or "",
                        "" if s.semester is None else s.semester,
                        s.email or "",
                        s.phone or "",
                    ),
                )

    def add_student(self) -> None:
        try:
            roll = self.roll_var.get().strip()
            name = self.name_var.get().strip()
            if not roll or not name:
                raise ServiceError("Roll No and Name are required.")

            semester = _parse_int(self.sem_var.get())
            with session_scope() as session:
                create_student(
                    session,
                    roll_no=roll,
                    name=name,
                    department=self.dept_var.get(),
                    semester=semester,
                    email=self.email_var.get(),
                    phone=self.phone_var.get(),
                )

            self.refresh()
            self.app.refresh_reference_data()
            self.clear_form()
            messagebox.showinfo("Success", "Student added.")
        except (ServiceError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def update_student(self) -> None:
        if self.selected_student_id is None:
            messagebox.showerror("Error", "Select a student first.")
            return

        try:
            roll = self.roll_var.get().strip()
            name = self.name_var.get().strip()
            if not roll or not name:
                raise ServiceError("Roll No and Name are required.")

            semester = _parse_int(self.sem_var.get())
            with session_scope() as session:
                update_student(
                    session,
                    student_id=self.selected_student_id,
                    roll_no=roll,
                    name=name,
                    department=self.dept_var.get(),
                    semester=semester,
                    email=self.email_var.get(),
                    phone=self.phone_var.get(),
                )

            self.refresh()
            self.app.refresh_reference_data()
            messagebox.showinfo("Success", "Student updated.")
        except (ServiceError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def delete_student(self) -> None:
        if self.selected_student_id is None:
            messagebox.showerror("Error", "Select a student first.")
            return

        if not messagebox.askyesno("Confirm", "Delete this student and related records?"):
            return

        try:
            with session_scope() as session:
                delete_student(session, student_id=self.selected_student_id)

            self.refresh()
            self.app.refresh_reference_data()
            self.clear_form()
            messagebox.showinfo("Success", "Student deleted.")
        except ServiceError as e:
            messagebox.showerror("Error", str(e))


class CoursesTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, *, app: CarpasApp) -> None:
        super().__init__(parent)
        self.app = app
        self.selected_course_id: int | None = None

        self.code_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.sem_var = tk.StringVar()
        self.credits_var = tk.StringVar()

        form = ttk.LabelFrame(self, text="Course Details")
        form.pack(fill="x", padx=10, pady=10)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text="Code *").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.code_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Name *").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.name_var).grid(row=0, column=3, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Semester").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.sem_var).grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Credits").grid(row=1, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.credits_var).grid(row=1, column=3, sticky="ew", padx=6, pady=6)

        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=0, columnspan=4, sticky="w", padx=6, pady=6)

        ttk.Button(buttons, text="Add", command=self.add_course).pack(side="left", padx=4)
        ttk.Button(buttons, text="Update", command=self.update_course).pack(side="left", padx=4)
        ttk.Button(buttons, text="Delete", command=self.delete_course).pack(side="left", padx=4)
        ttk.Button(buttons, text="Clear", command=self.clear_form).pack(side="left", padx=4)
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left", padx=4)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("code", "name", "semester", "credits")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("code", text="Code")
        self.tree.heading("name", text="Name")
        self.tree.heading("semester", text="Semester")
        self.tree.heading("credits", text="Credits")

        self.tree.column("code", width=120, anchor="w")
        self.tree.column("name", width=360, anchor="w")
        self.tree.column("semester", width=100, anchor="center")
        self.tree.column("credits", width=100, anchor="center")

        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

    def clear_form(self) -> None:
        self.selected_course_id = None
        self.code_var.set("")
        self.name_var.set("")
        self.sem_var.set("")
        self.credits_var.set("")
        self.tree.selection_remove(self.tree.selection())

    def on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        course_id = int(selection[0])
        self.selected_course_id = course_id

        with session_scope() as session:
            course = next((c for c in list_courses(session) if c.id == course_id), None)
            if not course:
                return

            self.code_var.set(course.code or "")
            self.name_var.set(course.name or "")
            self.sem_var.set("" if course.semester is None else str(course.semester))
            self.credits_var.set("" if course.credits is None else str(course.credits))

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        with session_scope() as session:
            for c in list_courses(session):
                self.tree.insert(
                    "",
                    "end",
                    iid=str(c.id),
                    values=(
                        c.code,
                        c.name,
                        "" if c.semester is None else c.semester,
                        "" if c.credits is None else c.credits,
                    ),
                )

    def add_course(self) -> None:
        try:
            code = self.code_var.get().strip()
            name = self.name_var.get().strip()
            if not code or not name:
                raise ServiceError("Course Code and Name are required.")

            semester = _parse_int(self.sem_var.get())
            credits = _parse_int(self.credits_var.get())

            with session_scope() as session:
                create_course(session, code=code, name=name, semester=semester, credits=credits)

            self.refresh()
            self.app.refresh_reference_data()
            self.clear_form()
            messagebox.showinfo("Success", "Course added.")
        except (ServiceError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def update_course(self) -> None:
        if self.selected_course_id is None:
            messagebox.showerror("Error", "Select a course first.")
            return

        try:
            code = self.code_var.get().strip()
            name = self.name_var.get().strip()
            if not code or not name:
                raise ServiceError("Course Code and Name are required.")

            semester = _parse_int(self.sem_var.get())
            credits = _parse_int(self.credits_var.get())

            with session_scope() as session:
                update_course(
                    session,
                    course_id=self.selected_course_id,
                    code=code,
                    name=name,
                    semester=semester,
                    credits=credits,
                )

            self.refresh()
            self.app.refresh_reference_data()
            messagebox.showinfo("Success", "Course updated.")
        except (ServiceError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def delete_course(self) -> None:
        if self.selected_course_id is None:
            messagebox.showerror("Error", "Select a course first.")
            return

        if not messagebox.askyesno("Confirm", "Delete this course and related records?"):
            return

        try:
            with session_scope() as session:
                delete_course(session, course_id=self.selected_course_id)

            self.refresh()
            self.app.refresh_reference_data()
            self.clear_form()
            messagebox.showinfo("Success", "Course deleted.")
        except ServiceError as e:
            messagebox.showerror("Error", str(e))


class EnrollmentsTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, *, app: CarpasApp) -> None:
        super().__init__(parent)
        self.app = app
        self.student_var = tk.StringVar()
        self.course_var = tk.StringVar()

        form = ttk.LabelFrame(self, text="Enroll Student in Course")
        form.pack(fill="x", padx=10, pady=10)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text="Student").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.student_cb = ttk.Combobox(form, textvariable=self.student_var, state="readonly")
        self.student_cb.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Course").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        self.course_cb = ttk.Combobox(form, textvariable=self.course_var, state="readonly")
        self.course_cb.grid(row=0, column=3, sticky="ew", padx=6, pady=6)

        buttons = ttk.Frame(form)
        buttons.grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=6)
        ttk.Button(buttons, text="Enroll", command=self.enroll).pack(side="left", padx=4)
        ttk.Button(buttons, text="Remove", command=self.remove).pack(side="left", padx=4)
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left", padx=4)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("student", "course", "enrolled_on")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("student", text="Student")
        self.tree.heading("course", text="Course")
        self.tree.heading("enrolled_on", text="Enrolled On")

        self.tree.column("student", width=320, anchor="w")
        self.tree.column("course", width=420, anchor="w")
        self.tree.column("enrolled_on", width=120, anchor="center")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

    def refresh_choices(self) -> None:
        with session_scope() as session:
            students = list_students(session)
            courses = list_courses(session)

        self.student_cb["values"] = [f"{s.id}: {s.roll_no} - {s.name}" for s in students]
        self.course_cb["values"] = [f"{c.id}: {c.code} - {c.name}" for c in courses]

    def refresh(self) -> None:
        self.refresh_choices()

        for item in self.tree.get_children():
            self.tree.delete(item)

        with session_scope() as session:
            for e in list_enrollments(session):
                self.tree.insert(
                    "",
                    "end",
                    iid=str(e.id),
                    values=(
                        f"{e.student.roll_no} - {e.student.name}",
                        f"{e.course.code} - {e.course.name}",
                        e.enrolled_on,
                    ),
                )

    def enroll(self) -> None:
        try:
            student_id = _parse_choice_id(self.student_var.get())
            course_id = _parse_choice_id(self.course_var.get())
            if not student_id or not course_id:
                raise ServiceError("Select both a student and a course.")

            with session_scope() as session:
                enroll_student(session, student_id=student_id, course_id=course_id)

            self.refresh()
            self.app.refresh_reference_data()
            messagebox.showinfo("Success", "Enrollment saved.")
        except ServiceError as e:
            messagebox.showerror("Error", str(e))

    def remove(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("Error", "Select an enrollment to remove.")
            return

        enrollment_id = int(selection[0])
        if not messagebox.askyesno("Confirm", "Remove this enrollment?"):
            return

        try:
            with session_scope() as session:
                remove_enrollment(session, enrollment_id=enrollment_id)

            self.refresh()
            self.app.refresh_reference_data()
            messagebox.showinfo("Success", "Enrollment removed.")
        except ServiceError as e:
            messagebox.showerror("Error", str(e))


class AttendanceTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, *, app: CarpasApp) -> None:
        super().__init__(parent)
        self.app = app

        self.enrollment_var = tk.StringVar()
        self.total_var = tk.StringVar()
        self.attended_var = tk.StringVar()

        form = ttk.LabelFrame(self, text="Set Attendance (per enrollment)")
        form.pack(fill="x", padx=10, pady=10)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text="Enrollment").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.enrollment_cb = ttk.Combobox(form, textvariable=self.enrollment_var, state="readonly")
        self.enrollment_cb.grid(row=0, column=1, columnspan=3, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Total Classes").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.total_var).grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Attended").grid(row=1, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.attended_var).grid(row=1, column=3, sticky="ew", padx=6, pady=6)

        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=0, columnspan=4, sticky="w", padx=6, pady=6)
        ttk.Button(buttons, text="Load", command=self.load_existing).pack(side="left", padx=4)
        ttk.Button(buttons, text="Save", command=self.save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left", padx=4)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("student", "course", "attended", "total", "pct")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("student", text="Student")
        self.tree.heading("course", text="Course")
        self.tree.heading("attended", text="Attended")
        self.tree.heading("total", text="Total")
        self.tree.heading("pct", text="%")

        self.tree.column("student", width=280, anchor="w")
        self.tree.column("course", width=420, anchor="w")
        self.tree.column("attended", width=90, anchor="center")
        self.tree.column("total", width=90, anchor="center")
        self.tree.column("pct", width=80, anchor="center")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

    def refresh_choices(self) -> None:
        with session_scope() as session:
            enrollments = list_enrollments(session)

        self.enrollment_cb["values"] = [
            f"{e.id}: {e.student.roll_no} - {e.student.name} | {e.course.code}"
            for e in enrollments
        ]

    def refresh(self) -> None:
        self.refresh_choices()

        for item in self.tree.get_children():
            self.tree.delete(item)

        with session_scope() as session:
            enrollments = list_enrollments(session)
            for e in enrollments:
                total = e.attendance.total_classes if e.attendance else 0
                attended = e.attendance.attended_classes if e.attendance else 0
                pct = ""
                if total > 0:
                    pct = round((attended / total) * 100.0, 2)
                self.tree.insert(
                    "",
                    "end",
                    iid=str(e.id),
                    values=(
                        f"{e.student.roll_no} - {e.student.name}",
                        f"{e.course.code} - {e.course.name}",
                        attended,
                        total,
                        pct,
                    ),
                )

    def load_existing(self) -> None:
        enrollment_id = _parse_choice_id(self.enrollment_var.get())
        if not enrollment_id:
            messagebox.showerror("Error", "Select an enrollment.")
            return

        with session_scope() as session:
            e = next((x for x in list_enrollments(session) if x.id == enrollment_id), None)
            if not e:
                messagebox.showerror("Error", "Enrollment not found.")
                return

            total = e.attendance.total_classes if e.attendance else 0
            attended = e.attendance.attended_classes if e.attendance else 0
            self.total_var.set(str(total))
            self.attended_var.set(str(attended))

    def save(self) -> None:
        try:
            enrollment_id = _parse_choice_id(self.enrollment_var.get())
            if not enrollment_id:
                raise ServiceError("Select an enrollment.")

            total = _parse_int(self.total_var.get())
            attended = _parse_int(self.attended_var.get())
            if total is None or attended is None:
                raise ServiceError("Enter total and attended classes.")

            with session_scope() as session:
                set_attendance(
                    session,
                    enrollment_id=enrollment_id,
                    total_classes=total,
                    attended_classes=attended,
                )

            self.refresh()
            self.app.analysis_tab.refresh_at_risk()
            messagebox.showinfo("Success", "Attendance saved.")
        except (ServiceError, ValueError) as e:
            messagebox.showerror("Error", str(e))


class MarksTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, *, app: CarpasApp) -> None:
        super().__init__(parent)
        self.app = app

        self.enrollment_var = tk.StringVar()
        self.assessment_var = tk.StringVar(value="Exam")
        self.obtained_var = tk.StringVar()
        self.max_var = tk.StringVar(value="100")

        form = ttk.LabelFrame(self, text="Add Marks")
        form.pack(fill="x", padx=10, pady=10)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text="Enrollment").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.enrollment_cb = ttk.Combobox(form, textvariable=self.enrollment_var, state="readonly")
        self.enrollment_cb.grid(row=0, column=1, columnspan=3, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Assessment").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.assessment_var).grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Obtained").grid(row=1, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.obtained_var).grid(row=1, column=3, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Max").grid(row=2, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.max_var).grid(row=2, column=3, sticky="ew", padx=6, pady=6)

        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=6)
        ttk.Button(buttons, text="Add Mark", command=self.add_mark).pack(side="left", padx=4)
        ttk.Button(buttons, text="Delete Selected", command=self.delete_selected).pack(side="left", padx=4)
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left", padx=4)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("assessment", "obtained", "max", "pct", "recorded_on")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("assessment", text="Assessment")
        self.tree.heading("obtained", text="Obtained")
        self.tree.heading("max", text="Max")
        self.tree.heading("pct", text="%")
        self.tree.heading("recorded_on", text="Recorded")

        self.tree.column("assessment", width=200, anchor="w")
        self.tree.column("obtained", width=100, anchor="center")
        self.tree.column("max", width=100, anchor="center")
        self.tree.column("pct", width=80, anchor="center")
        self.tree.column("recorded_on", width=120, anchor="center")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.enrollment_cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_marks_only())

    def refresh_choices(self) -> None:
        with session_scope() as session:
            enrollments = list_enrollments(session)

        self.enrollment_cb["values"] = [
            f"{e.id}: {e.student.roll_no} - {e.student.name} | {e.course.code}"
            for e in enrollments
        ]

    def refresh_marks_only(self) -> None:
        enrollment_id = _parse_choice_id(self.enrollment_var.get())
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not enrollment_id:
            return

        with session_scope() as session:
            marks = list_marks_for_enrollment(session, enrollment_id=enrollment_id)
            for m in marks:
                pct = round((m.marks_obtained / m.max_marks) * 100.0, 2) if m.max_marks else ""
                self.tree.insert(
                    "",
                    "end",
                    iid=str(m.id),
                    values=(m.assessment, m.marks_obtained, m.max_marks, pct, m.recorded_on),
                )

    def refresh(self) -> None:
        self.refresh_choices()
        self.refresh_marks_only()

    def add_mark(self) -> None:
        try:
            enrollment_id = _parse_choice_id(self.enrollment_var.get())
            if not enrollment_id:
                raise ServiceError("Select an enrollment.")

            obtained = _parse_float(self.obtained_var.get())
            max_marks = _parse_float(self.max_var.get())

            with session_scope() as session:
                add_mark(
                    session,
                    enrollment_id=enrollment_id,
                    assessment=self.assessment_var.get(),
                    marks_obtained=obtained,
                    max_marks=max_marks,
                )

            self.refresh_marks_only()
            self.app.analysis_tab.refresh_at_risk()
            messagebox.showinfo("Success", "Mark added.")
        except (ServiceError, ValueError) as e:
            messagebox.showerror("Error", str(e))

    def delete_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("Error", "Select a mark to delete.")
            return

        mark_id = int(selection[0])
        if not messagebox.askyesno("Confirm", "Delete selected mark?"):
            return

        try:
            with session_scope() as session:
                delete_mark(session, mark_id=mark_id)

            self.refresh_marks_only()
            self.app.analysis_tab.refresh_at_risk()
            messagebox.showinfo("Success", "Mark deleted.")
        except ServiceError as e:
            messagebox.showerror("Error", str(e))


class AnalysisTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, *, app: CarpasApp) -> None:
        super().__init__(parent)
        self.app = app

        self.student_var = tk.StringVar()
        self.course_var = tk.StringVar()

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        ttk.Label(top, text="Student").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.student_cb = ttk.Combobox(top, textvariable=self.student_var, state="readonly")
        self.student_cb.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(top, text="Course").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        self.course_cb = ttk.Combobox(top, textvariable=self.course_var, state="readonly")
        self.course_cb.grid(row=0, column=3, sticky="ew", padx=6, pady=6)

        btns = ttk.Frame(top)
        btns.grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=6)
        ttk.Button(btns, text="Student Report", command=self.show_student_report).pack(side="left", padx=4)
        ttk.Button(btns, text="Course Averages", command=self.show_course_averages).pack(side="left", padx=4)
        ttk.Button(btns, text="Refresh At-Risk", command=self.refresh_at_risk).pack(side="left", padx=4)

        # Student report table
        report_frame = ttk.LabelFrame(self, text="Student Course Summary")
        report_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        report_frame.rowconfigure(0, weight=1)
        report_frame.columnconfigure(0, weight=1)

        rep_cols = ("course", "attendance", "marks")
        self.report_tree = ttk.Treeview(report_frame, columns=rep_cols, show="headings", height=8)
        self.report_tree.heading("course", text="Course")
        self.report_tree.heading("attendance", text="Attendance %")
        self.report_tree.heading("marks", text="Marks %")
        self.report_tree.column("course", width=520, anchor="w")
        self.report_tree.column("attendance", width=120, anchor="center")
        self.report_tree.column("marks", width=120, anchor="center")
        self.report_tree.grid(row=0, column=0, sticky="nsew")

        rep_scroll = ttk.Scrollbar(report_frame, orient="vertical", command=self.report_tree.yview)
        self.report_tree.configure(yscrollcommand=rep_scroll.set)
        rep_scroll.grid(row=0, column=1, sticky="ns")

        # At-risk table
        risk_frame = ttk.LabelFrame(self, text="At-Risk Students")
        risk_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        risk_frame.rowconfigure(0, weight=1)
        risk_frame.columnconfigure(0, weight=1)

        risk_cols = ("student", "course", "attendance", "marks", "reason")
        self.risk_tree = ttk.Treeview(risk_frame, columns=risk_cols, show="headings", height=8)
        self.risk_tree.heading("student", text="Student")
        self.risk_tree.heading("course", text="Course")
        self.risk_tree.heading("attendance", text="Attendance %")
        self.risk_tree.heading("marks", text="Marks %")
        self.risk_tree.heading("reason", text="Reason")

        self.risk_tree.column("student", width=260, anchor="w")
        self.risk_tree.column("course", width=320, anchor="w")
        self.risk_tree.column("attendance", width=120, anchor="center")
        self.risk_tree.column("marks", width=120, anchor="center")
        self.risk_tree.column("reason", width=200, anchor="w")

        self.risk_tree.grid(row=0, column=0, sticky="nsew")
        risk_scroll = ttk.Scrollbar(risk_frame, orient="vertical", command=self.risk_tree.yview)
        self.risk_tree.configure(yscrollcommand=risk_scroll.set)
        risk_scroll.grid(row=0, column=1, sticky="ns")

    def refresh_choices(self) -> None:
        with session_scope() as session:
            students = list_students(session)
            courses = list_courses(session)

        self.student_cb["values"] = [f"{s.id}: {s.roll_no} - {s.name}" for s in students]
        self.course_cb["values"] = [f"{c.id}: {c.code} - {c.name}" for c in courses]

    def refresh(self) -> None:
        self.refresh_choices()
        self.refresh_at_risk()

    def show_student_report(self) -> None:
        student_id = _parse_choice_id(self.student_var.get())
        if not student_id:
            messagebox.showerror("Error", "Select a student.")
            return

        for item in self.report_tree.get_children():
            self.report_tree.delete(item)

        with session_scope() as session:
            summaries = get_student_enrollment_summaries(session, student_id=student_id)

        for s in summaries:
            attendance = "" if s.attendance_pct is None else s.attendance_pct
            marks = "" if s.marks_pct is None else s.marks_pct
            self.report_tree.insert(
                "",
                "end",
                iid=str(s.enrollment_id),
                values=(f"{s.course_code} - {s.course_name}", attendance, marks),
            )

    def show_course_averages(self) -> None:
        course_id = _parse_choice_id(self.course_var.get())
        if not course_id:
            messagebox.showerror("Error", "Select a course.")
            return

        with session_scope() as session:
            avg_marks = course_class_average_marks_pct(session, course_id=course_id)
            avg_att = course_class_average_attendance_pct(session, course_id=course_id)

        messagebox.showinfo(
            "Course Averages",
            f"Average Marks %: {avg_marks if avg_marks is not None else 'N/A'}\n"
            f"Average Attendance %: {avg_att if avg_att is not None else 'N/A'}",
        )

    def refresh_at_risk(self) -> None:
        for item in self.risk_tree.get_children():
            self.risk_tree.delete(item)

        with session_scope() as session:
            rows = find_at_risk(session)

        for r in rows:
            self.risk_tree.insert(
                "",
                "end",
                iid=str(r["enrollment_id"]),
                values=(
                    f"{r['roll_no']} - {r['student_name']}",
                    f"{r['course_code']} - {r['course_name']}",
                    "" if r["attendance_pct"] is None else r["attendance_pct"],
                    "" if r["marks_pct"] is None else r["marks_pct"],
                    r["reason"],
                ),
            )


def run() -> None:
    app = CarpasApp()
    app.mainloop()
