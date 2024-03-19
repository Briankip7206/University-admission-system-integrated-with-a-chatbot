from flask import Flask, render_template, request, url_for, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField
from sqlalchemy.orm import aliased
from wtforms import PasswordField, validators
from sqlalchemy.exc import IntegrityError
from wtforms.validators import DataRequired


from chat import get_response





app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
app.config["SECRET_KEY"] = "abc"
db = SQLAlchemy()

login_manager = LoginManager()
login_manager.init_app(app)


class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    school_course = db.relationship('SchoolCourse', back_populates='user')

 
class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    message = db.Column(db.Text, nullable=False)

class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    school = db.relationship('School', backref='courses')

class SchoolCourse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school = db.Column(db.String(100))
    course = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('Users', back_populates='school_course')
    
class AdminAddStudentForm(FlaskForm):
    username = StringField('Username', [validators.DataRequired()])
    password = PasswordField('Password', [validators.DataRequired()])
        
class AdminAssignForm(FlaskForm):
    assigned_school = StringField('Assigned School', validators=[DataRequired()])
    assigned_course = StringField('Assigned Course', validators=[DataRequired()])
    
class SchoolAddForm(FlaskForm):
    school_name = StringField('School Name', [validators.DataRequired()])

class CourseAddForm(FlaskForm):
    course_name = StringField('Course Name', [validators.DataRequired()]) 
db.init_app(app)


with app.app_context():
	db.create_all()

@login_manager.user_loader
def loader_user(user_id):
	return Users.query.get(user_id)

@app.route('/admin/add_student', methods=['GET', 'POST'])
@login_required
def admin_add_student():
    form = AdminAddStudentForm()

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        # Check if the username already exists
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            error_message = ('Username already exists. Please choose a different username.', 'error')
            return render_template('admin_add_student.html', form=form, error_message=error_message)

        # Attempt to add the new student
        new_student = Users(username=username, password=password)
        try:
            db.session.add(new_student)
            db.session.commit()
            success_message = (f'Student {username} added successfully!', 'success')
            return redirect(url_for('admin', success_message=success_message))
        except IntegrityError:
            db.session.rollback()
            error_message = ('Username already exists. Please choose a different username.', 'error')
            return render_template('admin_add_student.html', form=form, error_message=error_message)

    return render_template('admin_add_student.html', form=form)


# Admin Panel to Assign Schools and Courses
@app.route('/admin/assign/<int:user_id>', methods=['GET', 'POST'])
@login_required
def admin_assign(user_id):
    user = Users.query.get(user_id)
    form = AdminAssignForm()

    # Populate choices for schools and courses
    form.assigned_school.choices = [(school.id, school.name) for school in School.query.all()]
    form.assigned_course.choices = [(course.id, course.name) for course in Course.query.all()]

    if form.validate_on_submit():
        assigned_school_id = form.assigned_school.data
        assigned_course_id = form.assigned_course.data

        # Check if there's an existing assignment, update it
        existing_assignment = SchoolCourse.query.filter_by(user_id=user.id).first()
        if existing_assignment:
            existing_assignment.school = assigned_school_id
            existing_assignment.course = assigned_course_id
        else:
            # Otherwise, create a new assignment
            assignment = SchoolCourse(
                school=assigned_school_id,
                course=assigned_course_id,
                user_id=user.id
            )
            db.session.add(assignment)

        db.session.commit()

        error_message = (f'Assigned school and course to {user.username}', 'success')
        return redirect(url_for('admin', error_message=error_message))

    return render_template('admin_assign.html', user=user, form=form)
@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Check for empty inputs
        if not username or not password:
            error_message = "Please fill in both username and password fields."
            return render_template("register.html", error_message=error_message)

        # Check if the username already exists
        existing_user = Users.query.filter_by(username=username).first()

        if existing_user:
            error_message = "Username already exists. Please choose a different username."
            return render_template("register.html", error_message=error_message)

        try:
            # Attempt to create a new user and add it to the database
            user = Users(username=username, password=password)
            db.session.add(user)
            db.session.commit()

            # Redirect to the login page upon successful registration
            return redirect(url_for("login"))

        except Exception as e:
            # Handle database or other errors
            db.session.rollback()
            error_message = f"An error occurred: {str(e)}"
            return render_template("register.html", error_message=error_message)

    # Render the registration form for GET requests
    return render_template("register.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    error_message = None  # Initialize error_message outside the if block

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Check for empty username or password
        if not username or not password:
            error_message = "Please provide both username and password."
            return render_template("login.html", error_message=error_message)

        user = Users.query.filter_by(username=username).first()

        # Check if the user exists and the password is correct
        if user and user.password == password:
            login_user(user)
            return redirect(url_for("user_account"))
        else:
            error_message = "Invalid username or password. Please try again."
    return render_template("login.html", error_message=error_message)

@app.route("/user/account", methods=["GET", "POST"])
def user_account():
    return render_template('accounts.html')

@app.route("/contact", methods=["GET", "POST"])
def add_contact():
    if request.method == "POST":
        email = request.form.get("email")
        phone = request.form.get("phone")
        message = request.form.get("message")

        if not email or not phone or not message:
            error_message = ("Please fill in all contact details.")
            return render_template("contact.html", error_message = error_message)

        contact = Contact(email=email, phone=phone, message=message)
        db.session.add(contact)
        db.session.commit()
        error_message = ("Contact added successfully!")
        return redirect(url_for("home"))

    return render_template("contact.html")

@app.route("/admin/messages")
@login_required
def adm_contact():
    if not current_user.is_authenticated or current_user.username != "admin":
        error_message = "You do not have permission to access the admin panel."
        return redirect(url_for("home", error_message=error_message))

    # Exclude the admin user from the list
    contacts = Contact.query.all()

    return render_template("admcontact.html",  contacts=contacts)

@app.route("/admin/accounts")
@login_required
def adm_users():
    if not current_user.is_authenticated or current_user.username != "admin":
        error_message = "You do not have permission to access the admin panel."
        return redirect(url_for("home", error_message=error_message))

    # Exclude the admin user from the list
    users = Users.query.filter(Users.username != "admin").all()

    return render_template("admusers.html",  users=users)

@app.route("/admin")
@login_required
def admin():
    return redirect(url_for("admin_view_students"))
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error_message = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        username = request.form.get("username")
        password = request.form.get("password")

        # Check for empty username or password
        if not username or not password:
            error_message = "Please provide both username and password."
            return render_template("admin_login.html", error_message=error_message)

        user = Users.query.filter_by(username=username).first()

        # Check if the user exists and the password is correct
        if user and user.password == password:
            login_user(user)
        
            # Redirect to the admin panel
            return redirect(url_for("admin"))
        else:
            error_message = "Invalid admin credentials. Please try again."

    return render_template("admin_login.html", error_message=error_message)

@app.route("/delete_user/<int:user_id>", methods=["POST", "GET"])
@login_required
def delete_user(user_id):
    if current_user.is_authenticated and current_user.username == "admin":
        user = Users.query.get(user_id)
        if user and user.username != "admin":
            db.session.delete(user)
            db.session.commit()
    return redirect(url_for("admin"))

@app.route('/admin/add_school', methods=['GET', 'POST'])
@login_required
def admin_add_school():
    form = SchoolAddForm()

    if form.validate_on_submit():
        school_name = form.school_name.data

        new_school = School(name=school_name)
        db.session.add(new_school)
        db.session.commit()

        error_message = (f'School {school_name} added successfully!', 'success')
        return redirect(url_for('admin', error_message=error_message))

    return render_template('admin_add_school.html', form=form)

@app.route('/admin/add_course/<int:school_id>', methods=['GET', 'POST'])
@login_required
def admin_add_course(school_id):
    form = CourseAddForm()

    school = School.query.get(school_id)

    if form.validate_on_submit():
        course_name = form.course_name.data

        new_course = Course(name=course_name, school_id=school.id)
        db.session.add(new_course)
        db.session.commit()

        error_message = (f'Course {course_name} added successfully to {school.name}!', 'success')
        return redirect(url_for('admin', error_message=error_message))

    return render_template('admin_add_course.html', form=form, school=school)

@app.route('/admin/view_schools')
@login_required
def admin_view_schools():
    schools = School.query.all()
    return render_template('admin_view_schools.html', schools=schools)

@app.route('/admin/view_courses')
@login_required
def admin_view_all_courses():
    courses = Course.query.all()
    return render_template('admin_view_courses.html', courses=courses)


@app.route('/admin/view_students')
@login_required
def admin_view_students():
    # Create aliases for the joined tables
    user_alias = aliased(Users)
    users = Users.query.all()
    school_course_alias = aliased(SchoolCourse)

    # Fetch all students and their assignments
    students = Users.query.join(user_alias.school_course).join(school_course_alias).all()

    return render_template('admin_view_students.html', students=students, users=users) 


@app.route('/admin/modify_assignment/<int:user_id>', methods=['GET', 'POST'])
@login_required
def modify_assignment(user_id):
    user = Users.query.get(user_id)
    form = AdminAssignForm()

    if form.validate_on_submit():
        # Update or create assignment based on the form data
        # ...

        db.session.commit()

        flash('Assignment modified successfully!', 'success')
        return redirect(url_for('admin_view_students', school_id=school.id, course_id=course.id))

    return render_template('modify_assignment.html', user=user, form=form)


@app.post("/get_response")
def predict():
    text = request.get_json().get("message")
    response = get_response(text)
    message = {"answer" : response}
    return jsonify(message)

@app.get("/about")
def about_get():
    return render_template("about.html")
@app.get("/apply")
def apply_get():
    return render_template("apply.html")

@app.get("/programmes")
def programmes_get():
    return render_template("programmes.html")

@app.get("/contact")
def contact_get():
    return render_template("contact.html")

@app.get("/login")
def life_at_must_get():
    return render_template("login.html")


@app.route("/logout")
def logout():
	logout_user()
	return redirect(url_for("home"))


@app.route("/")
def home():
	return render_template("home.html")


if __name__ == "__main__":
	app.run(debug=True)
