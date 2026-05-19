import os
import csv
import uuid
import requests
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, ActionLog 

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-for-learnhub'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db' # MySQL link bhi use kar sakta hai
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

# ==========================================
# CONSTANTS & SETUP
# ==========================================
# Yahan apni main Google Sheet ka ID daalna mat bhoolna
SHEET_ID = '1jFpYhjEyyqHOJJDdyPRCMoltbiM3k0dspyVDihxEyzA' 
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"
SHEET_EDIT_LINK = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"

# Tera Webhook URL (Write karne ke liye)
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzn1Gx5dDAuScWtlNOoOFmYLP6r9wdLC0rK98RX2WJayezHKplhae8Eii_tHIZ7pWCU/exec"

# Upload Folder Setup (Images tere server par safe rahengi)
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_sheet_data():
    """Google Sheet se data CSV format mein read karna (Super Fast)"""
    try:
        response = requests.get(SHEET_CSV_URL)
        response.raise_for_status()
        decoded_content = response.content.decode('utf-8')
        csv_reader = csv.DictReader(decoded_content.splitlines())
        return list(csv_reader)
    except Exception as e:
        print("Error fetching sheet:", e)
        return []

# ==========================================
# PUBLIC ROUTES (READ FROM SHEET)
# ==========================================
@app.route("/")
def index():
    data = get_sheet_data()
    domains = list(set([row['Domain'] for row in data if row.get('Domain')]))
    return render_template("index.html", topics=domains)

@app.route("/topic/<string:domain_name>")
@login_required
def view_topic(domain_name):
    data = get_sheet_data()
    subtopics = list(set([row['Tabcat'] for row in data if row.get('Domain') == domain_name]))
    return render_template("topic_view.html", domain_name=domain_name, subtopics=subtopics)

@app.route("/subtopic/<string:domain_name>/<string:tabcat_name>")
@login_required
def view_subtopic(domain_name, tabcat_name):
    data = get_sheet_data()
    lessons = [row for row in data if row.get('Domain') == domain_name and row.get('Tabcat') == tabcat_name]
    return render_template("lessons.html", domain_name=domain_name, tabcat_name=tabcat_name, lessons=lessons)

@app.route("/lesson/<string:domain_name>/<string:tabcat_name>/<string:tab_name>")
@login_required
def view_lesson(domain_name, tabcat_name, tab_name):
    data = get_sheet_data()
    lesson_data = next((row for row in data if row.get('Domain') == domain_name and row.get('Tabcat') == tabcat_name and row.get('Tab') == tab_name), None)
    
    if not lesson_data:
        flash("Lesson not found!", "error")
        return redirect(url_for('index'))
        
    return render_template("lesson.html", lesson=lesson_data)

# ==========================================
# TEACHER ROUTE (UPLOAD IMAGE & SEND TO APPS SCRIPT)
# ==========================================
@app.route("/teacher/add_lesson", methods=["GET", "POST"])
@login_required
def add_lesson():
    if current_user.role != 'teacher':
        flash("Access Denied.", "error")
        return redirect(url_for('index'))

    if request.method == "POST":
        domain = request.form.get("domain")
        tabcat = request.form.get("tabcat")
        tab = request.form.get("tab") 
        content = request.form.get("content")
        links = request.form.get("links", "")

        image_file = request.files.get("image")
        pic_url = ""
        
        # 1. LOCAL FOLDER MEIN PHOTO SAVE KARNA
        if image_file and image_file.filename != '':
            try:
                ext = image_file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{ext}"
                
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                image_file.save(save_path)
                
                pic_url = url_for('static', filename=f'uploads/{unique_filename}', _external=True)
            except Exception as img_error:
                flash(f"Image Save Error: {str(img_error)}", "error")
                return redirect(url_for('add_lesson'))

        # 2. APPS SCRIPT (GOOGLE SHEET) KO BHEJNA
        try:
            payload = {
                "domain": domain,
                "tabcat": tabcat,
                "tab": tab,
                "content": content,
                "pic_url": pic_url,
                "links": links
            }
            
            # TIMEOUT lagaya hai taaki hang na ho (Max 10 seconds wait karega)
            response = requests.post(APPS_SCRIPT_URL, data=payload, timeout=10)
            
            if response.text == "Success":
                log = ActionLog(user_id=current_user.id, action_type="Added Lesson via Webhook", description=f"Added '{tab}'")
                db.session.add(log)
                db.session.commit()
                flash(f"Lesson '{tab}' added successfully to Google Sheet!", "success")
            else:
                flash(f"Saved to local server, but Google Sheet error: {response.text}", "warning")
                
        except requests.exceptions.Timeout:
            flash("Google Sheet took too long to respond (Timeout)! But image is saved on server.", "error")
        except Exception as e:
            flash(f"Error connecting to Google Sheet: {str(e)}", "error")
            print(f"❌ Server Error: {e}")

        return redirect(url_for('admin'))

    # GET REQUEST: Fetch existing domains and tabcats for the Dropdowns
    data = get_sheet_data()
    existing_domains = list(set([row['Domain'] for row in data if row.get('Domain')]))
    existing_tabcats = list(set([row['Tabcat'] for row in data if row.get('Tabcat')]))

    return render_template("add_lesson.html", existing_domains=existing_domains, existing_tabcats=existing_tabcats)

# ==========================================
# AUTH & ADMIN ROUTES (MySQL/SQLite)
# ==========================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == "POST":
        # Original fields
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        phone = request.form.get("phone")
        aadhar = request.form.get("aadhar")
        invite_code = request.form.get("invite_code")
        
        # New Extra fields added from the new UI
        fullname = request.form.get("fullname")
        gender = request.form.get("gender")
        dob = request.form.get("dob")
        school = request.form.get("school")
        class_grade = request.form.get("class_grade")
        stream = request.form.get("stream")
        address = request.form.get("address")
        city = request.form.get("city")
        state = request.form.get("state")
        district = request.form.get("district")
        
        existing_user = User.query.filter((User.email==email) | (User.username==username)).first()
        if existing_user:
            flash("Email or Username already registered.", "error")
            return redirect(url_for("register"))
            
        role = 'student'
        if invite_code == 'LEARNHUB_TEACHER':
            role = 'teacher'
            
        # Creating user with all the new data
        new_user = User(
            username=username, 
            email=email, 
            phone=phone, 
            aadhar=aadhar, 
            role=role,
            fullname=fullname,
            gender=gender,
            dob=dob,
            school=school,
            class_grade=class_grade,
            stream=stream,
            address=address,
            city=city,
            state=state,
            district=district
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for("index"))
        
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'teacher':
                return redirect(url_for('admin'))
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password.", "error")
            
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if current_user.role != 'teacher':
        flash("Access Denied.", "error")
        return redirect(url_for('index'))
        
    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete_student":
            student_id = request.form.get("student_id")
            student = db.session.get(User, student_id)
            if student and student.role == 'student':
                db.session.delete(student)
                db.session.commit()
                flash("Student deleted.", "success")
        return redirect(url_for('admin'))
        
    students = User.query.filter_by(role='student').all()
    return render_template("admin_dashboard.html", students=students, sheet_link=SHEET_EDIT_LINK)

if __name__ == "__main__":
    app.run(debug=True)