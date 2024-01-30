# -------------------------------- Installations and Imports --------------------------------
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField,DateField
from wtforms.fields.list import FieldList
from wtforms.validators import DataRequired, Length, Email, EqualTo
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import UserMixin, LoginManager, current_user, login_user, login_required,logout_user
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound

# ------------------------------------------------------------------------------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = '5791628bb0b13he0c676dfde280ba245'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
migrate = Migrate(app, db)
# ------------------------------------------------------------------------------------------

login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    user_id = int(user_id)
    return User.query.get(user_id)

# ------------------------------------------------------------------------------------------
#  Course model

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    schedule = db.Column(db.String(100), nullable=False)
    professor_name = db.Column(db.String(100), nullable=True)
    professor_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_course_professor_id'))
    professor = db.relationship('User', back_populates='courses_taught')
    students = db.relationship('User', secondary='course_registration', back_populates='courses')
    attendances = db.relationship('Attendance', back_populates='course')


# Adding a many-to-many association table for course registration
course_registration = db.Table(
    'course_registration',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', name='fk_course_registration_user_id'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('course.id', name='fk_course_registration_course_id'), primary_key=True)
)


# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    account_type = db.Column(db.String(10), nullable=False)
    courses = db.relationship('Course', secondary=course_registration, back_populates='students')
    courses_taught = db.relationship('Course', back_populates='professor')
    attendances = db.relationship('Attendance', back_populates='student')



# Attendance model
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_attendance_student_id'), nullable=False)
    student = db.relationship('User', back_populates='attendances')
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', name='fk_attendance_course_id'), nullable=False)
    course = db.relationship('Course', back_populates='attendances')
    status = db.Column(db.String(10), nullable=False)

# -------------------------------------- Forms ----------------------------------------------

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    account_type = SelectField('Account Type', choices=[('teacher', 'Teacher'), ('student', 'Student')], validators=[DataRequired()])
    submit = SubmitField('Sign Up')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class CourseRegistrationForm(FlaskForm):

    courses = SelectField('Select Course:', choices=[], validators=[DataRequired()])
    submit = SubmitField('Register')


class AttendanceForm(FlaskForm):
    date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Mark Attendance')


#-----------------------------------------Routes------------------------------------------------------------------------------------------------

@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')


@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password, account_type=form.account_type.data)
        db.session.add(user)
        db.session.commit()
        flash(f'Account created for {form.username.data}! Please Login. ', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            flash(f'{form.username.data} logged in successfully!', 'success')

            if user.account_type == 'student':
                return redirect(url_for('student_home'))
            elif user.account_type == 'teacher':
                return redirect(url_for('teacher_page'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', form=form)


#------------------------------------------------------------------ Student Routes-------------------------------------------------------------------------------


@app.route("/student_home", methods=['GET', 'POST'])
@login_required
def student_home():
    if current_user.account_type != 'student':
        flash('Access Denied. You are not a student.', 'danger')
        return redirect(url_for('home'))

    return render_template('student_home.html')


@app.route("/course_registration", methods=['GET', 'POST'])
@login_required
def course_registration():
    if current_user.account_type != 'student':
        flash('Access Denied. You are not a student.', 'danger')
        return redirect(url_for('home'))

    class DynamicCourseRegistrationForm(CourseRegistrationForm):
        courses = SelectField('Select Course:', choices=[], validators=[DataRequired()])

    registration_form = DynamicCourseRegistrationForm()


    registration_form.courses.choices = [(course.id, f"{course.name} - {course.department} - {course.schedule}") for course in Course.query.all()]

    if registration_form.validate_on_submit():
        selected_course_id = registration_form.courses.data
        selected_course = Course.query.get(selected_course_id)

        if selected_course:
            if selected_course not in current_user.courses:
                current_user.courses.append(selected_course)
                db.session.commit()
                flash(f'Successfully registered for course: {selected_course.name}', 'success')
            else:
                flash(f'You are already registered for course: {selected_course.name}', 'warning')
        else:
            flash('Invalid course selection.', 'danger')

    return render_template('course_registration.html', registration_form=registration_form)


@app.route("/student_courses", methods=['GET', 'POST'])
@login_required
def student_courses():
    if current_user.account_type != 'student':
        flash('Access Denied. You are not a student.', 'danger')
        return redirect(url_for('home'))

    registered_courses = current_user.courses

    return render_template('student_courses.html', registered_courses=registered_courses)


@app.route("/student_other", methods=['GET', 'POST'])
@login_required
def student_other():
    if current_user.account_type != 'student':
        flash('Access Denied. You are not a student.', 'danger')
        return redirect(url_for('home'))

    return render_template('student_other.html')


# ---------------------------------------------------------------Teacher Route ---------------------------------------------------------------

@app.route("/teacher_page", methods=['GET'])
@login_required
def teacher_page():
    if current_user.account_type != 'teacher':
        flash('Access Denied. You are not a teacher.', 'danger')
        return redirect(url_for('home'))

    # Fetch the courses taught by the current teacher
    courses_taught = Course.query.filter_by(professor=current_user).all()

    # Fetch enrolled students for each course
    enrolled_students = {}
    for course in courses_taught:
        students = course.students
        enrolled_students[course] = students

    return render_template('teacher_page.html', enrolled_students=enrolled_students)




#---------------------------------------------------------Teacher Marking attendance ---------------------------------------------------------------------------

@app.route("/mark_attendance/<int:course_id>/<int:student_id>", methods=['GET', 'POST'])
@login_required
def mark_attendance(course_id, student_id):
    if current_user.account_type != 'teacher':
        flash('Access Denied. You are not a teacher.', 'danger')
        return redirect(url_for('home'))

    course = Course.query.get(course_id)
    student = User.query.get(student_id)

    if not course or not student or course.professor != current_user:
        flash('Invalid request.', 'danger')
        return redirect(url_for('home'))

    form = AttendanceForm()

    if form.validate_on_submit():
        # Checking if attendance for the given date already exists
        try:
            existing_attendance = Attendance.query.filter_by(date=form.date.data, student=student, course=course).one()
            # If the attendance exists, update the status
            existing_attendance.status = 'present' if request.form.get('status') == 'present' else 'absent'
            db.session.commit()
            flash(f'Attendance for {student.username} on {form.date.data} updated successfully.', 'success')
        except NoResultFound:
            # If attendance  not exist, creating new record
            status = 'present' if request.form.get('status') == 'present' else 'absent'
            attendance = Attendance(date=form.date.data, student=student, course=course, status=status)
            db.session.add(attendance)
            db.session.commit()
            flash(f'Attendance for {student.username} on {form.date.data} marked successfully.', 'success')

    # Fetching  list of students for the given course
    students = course.students

    return render_template('mark_attendance.html', form=form, course=course, student=student, students=students)


#------------------------------------------------------------------------------------------------------------------------------------
# Student Checking attendance

@app.route("/student_attendance_records")
@login_required
def student_attendance_records():
    if current_user.account_type != 'student':
        flash('Access Denied. You are not a student.', 'danger')
        return redirect(url_for('home'))

    # Fetching attendance records for current student
    attendance_records = current_user.attendances

    return render_template('student_attendance_records.html', attendance_records=attendance_records)


#-----------------------------------------------------------------------------------------------------------------------------------------


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

