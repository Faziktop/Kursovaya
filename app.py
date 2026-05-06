from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# Настройка базы данных
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "database.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ==================== МОДЕЛИ БАЗЫ ДАННЫХ ====================

# ENUM типы (в SQLite используем строки с проверкой)
class UserRole:
    AUTHENTICATED = 'authenticated'
    APPLICANT = 'applicant'
    STUDENT = 'student'
    EMPLOYEE = 'employee'
    ADMIN = 'admin'


class StudentStatus:
    STUDYING = 'studying'
    ACADEMIC_LEAVE = 'academic_leave'
    EXPELLED = 'expelled'
    GRADUATED = 'graduated'


class DocumentStatus:
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    VERIFIED = 'verified'
    REJECTED = 'rejected'


# Факультеты
class Faculty(db.Model):
    __tablename__ = 'faculties'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_icon = db.Column(db.String(100), default='fa-university')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Специальности
class Specialty(db.Model):
    __tablename__ = 'specialties'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculties.id'), nullable=False)
    level = db.Column(db.String(50))  # spo, bachelor, master, postgraduate
    duration = db.Column(db.String(50))
    qualification = db.Column(db.String(100))
    form_of_education = db.Column(db.String(100), default='Очная')
    budget_places = db.Column(db.Integer, default=0)
    tuition_fee = db.Column(db.Float, default=0)
    location = db.Column(db.String(255), default='г. Ижевск, ул. Студенческая, 7')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    faculty = db.relationship('Faculty', backref='specialties')


# Пользователи
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    fullname = db.Column(db.String(200))
    role = db.Column(db.String(50), default=UserRole.AUTHENTICATED)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Группы
class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    specialty_id = db.Column(db.Integer, db.ForeignKey('specialties.id'))
    year_of_admission = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)


# Профиль студента
class StudentProfile(db.Model):
    __tablename__ = 'student_profiles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    student_card_number = db.Column(db.String(20), unique=True)
    specialty_id = db.Column(db.Integer, db.ForeignKey('specialties.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    student_status = db.Column(db.String(50), default=StudentStatus.STUDYING)
    enrollment_year = db.Column(db.Integer)
    graduation_year = db.Column(db.Integer)
    form_of_education = db.Column(db.String(20), default='full-time')
    funding_type = db.Column(db.String(20), default='budget')


# ==================== ДЕКОРАТОРЫ ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'error')
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if user.role != UserRole.ADMIN:
            flash('Доступ запрещён. Требуются права администратора.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


# ==================== СОЗДАНИЕ БД И ТЕСТОВЫХ ДАННЫХ ====================

with app.app_context():
    db.drop_all()
    db.create_all()

    # Создание факультетов
    faculties_data = [
        {'name': 'Факультет информационных технологий',
         'description': 'Подготовка IT-специалистов, программистов, разработчиков', 'image_icon': 'fa-laptop'},
        {'name': 'Машиностроительный факультет', 'description': 'Подготовка инженеров-механиков, конструкторов',
         'image_icon': 'fa-industry'},
        {'name': 'Факультет экономики и права', 'description': 'Подготовка экономистов, юристов, менеджеров',
         'image_icon': 'fa-university'},
        {'name': 'Факультет строительства, архитектуры и дизайна',
         'description': 'Подготовка архитекторов, строителей, дизайнеров', 'image_icon': 'fa-paint-brush'},
        {'name': 'Факультет математики и естественных наук', 'description': 'Подготовка математиков, физиков, химиков',
         'image_icon': 'fa-flask'},
        {'name': 'Институт энергетики', 'description': 'Подготовка энергетиков, теплотехников',
         'image_icon': 'fa-bolt'},
        {'name': 'Приборостроительный факультет', 'description': 'Подготовка специалистов в области приборостроения',
         'image_icon': 'fa-microphone'},
        {'name': 'Институт физической культуры и спорта',
         'description': 'Подготовка тренеров, преподавателей физкультуры', 'image_icon': 'fa-futbol-o'},
    ]

    faculties = {}
    for f in faculties_data:
        faculty = Faculty(name=f['name'], description=f['description'], image_icon=f['image_icon'])
        db.session.add(faculty)
    db.session.commit()

    # Получаем созданные факультеты
    faculties_dict = {f.name: f.id for f in Faculty.query.all()}

    # Создание специальностей
    specialties_data = [
        # СПО
        {'code': '09.02.07', 'name': 'Информационные системы и программирование',
         'faculty': 'Факультет информационных технологий', 'level': 'spo', 'duration': '2 года 10 месяцев',
         'qualification': 'Программист', 'budget_places': 50, 'tuition_fee': 120000},
        {'code': '15.02.12', 'name': 'Монтаж, техническое обслуживание и ремонт промышленного оборудования',
         'faculty': 'Машиностроительный факультет', 'level': 'spo', 'duration': '3 года 10 месяцев',
         'qualification': 'Техник-механик', 'budget_places': 40, 'tuition_fee': 110000},
        {'code': '38.02.01', 'name': 'Экономика и бухгалтерский учет', 'faculty': 'Факультет экономики и права',
         'level': 'spo', 'duration': '2 года 10 месяцев', 'qualification': 'Бухгалтер', 'budget_places': 45,
         'tuition_fee': 100000},

        # Бакалавриат
        {'code': '09.03.01', 'name': 'Информатика и вычислительная техника',
         'faculty': 'Факультет информационных технологий', 'level': 'bachelor', 'duration': '4 года',
         'qualification': 'Бакалавр', 'budget_places': 60, 'tuition_fee': 150000},
        {'code': '15.03.05', 'name': 'Конструкторско-технологическое обеспечение машиностроительных производств',
         'faculty': 'Машиностроительный факультет', 'level': 'bachelor', 'duration': '4 года',
         'qualification': 'Бакалавр', 'budget_places': 55, 'tuition_fee': 140000},
        {'code': '38.03.01', 'name': 'Экономика', 'faculty': 'Факультет экономики и права', 'level': 'bachelor',
         'duration': '4 года', 'qualification': 'Бакалавр', 'budget_places': 70, 'tuition_fee': 135000},
        {'code': '40.03.01', 'name': 'Юриспруденция', 'faculty': 'Факультет экономики и права', 'level': 'bachelor',
         'duration': '4 года', 'qualification': 'Бакалавр', 'budget_places': 65, 'tuition_fee': 145000},
        {'code': '44.03.01', 'name': 'Педагогическое образование',
         'faculty': 'Факультет математики и естественных наук', 'level': 'bachelor', 'duration': '4 года',
         'qualification': 'Бакалавр', 'budget_places': 50, 'tuition_fee': 125000},
        {'code': '08.03.01', 'name': 'Строительство', 'faculty': 'Факультет строительства, архитектуры и дизайна',
         'level': 'bachelor', 'duration': '4 года', 'qualification': 'Бакалавр', 'budget_places': 55,
         'tuition_fee': 140000},

        # Магистратура
        {'code': '09.04.01', 'name': 'Информатика и вычислительная техника',
         'faculty': 'Факультет информационных технологий', 'level': 'master', 'duration': '2 года',
         'qualification': 'Магистр', 'budget_places': 30, 'tuition_fee': 170000},
        {'code': '38.04.01', 'name': 'Экономика', 'faculty': 'Факультет экономики и права', 'level': 'master',
         'duration': '2 года', 'qualification': 'Магистр', 'budget_places': 35, 'tuition_fee': 160000},
        {'code': '15.04.05', 'name': 'Конструкторско-технологическое обеспечение машиностроительных производств',
         'faculty': 'Машиностроительный факультет', 'level': 'master', 'duration': '2 года', 'qualification': 'Магистр',
         'budget_places': 25, 'tuition_fee': 165000},

        # Аспирантура
        {'code': '09.06.01', 'name': 'Информатика и вычислительная техника',
         'faculty': 'Факультет информационных технологий', 'level': 'postgraduate', 'duration': '3 года',
         'qualification': 'Исследователь', 'budget_places': 10, 'tuition_fee': 200000},
        {'code': '15.06.01', 'name': 'Машиностроение', 'faculty': 'Машиностроительный факультет',
         'level': 'postgraduate', 'duration': '3 года', 'qualification': 'Исследователь', 'budget_places': 10,
         'tuition_fee': 200000},
        {'code': '38.06.01', 'name': 'Экономика', 'faculty': 'Факультет экономики и права', 'level': 'postgraduate',
         'duration': '3 года', 'qualification': 'Исследователь', 'budget_places': 8, 'tuition_fee': 195000},
    ]

    for s in specialties_data:
        specialty = Specialty(
            code=s['code'],
            name=s['name'],
            faculty_id=faculties_dict[s['faculty']],
            level=s['level'],
            duration=s['duration'],
            qualification=s['qualification'],
            budget_places=s['budget_places'],
            tuition_fee=s['tuition_fee']
        )
        db.session.add(specialty)

    # Создание тестового админа
    admin = User.query.filter_by(email='admin@gmail.com').first()
    if not admin:
        admin = User(
            email='admin@gmail.com',
            fullname='Администратор',
            role=UserRole.ADMIN,
            is_active=True
        )
        admin.set_password('admin')
        db.session.add(admin)

    # Создание тестового студента
    student = User.query.filter_by(email='student@mail.ru').first()
    if not student:
        student = User(
            email='student@mail.ru',
            fullname='Иванов Иван Иванович',
            role=UserRole.STUDENT,
            is_active=True
        )
        student.set_password('student')
        db.session.add(student)

    db.session.commit()
    print("База данных создана с тестовыми данными!")
    print("Админ: admin@gmail.com / admin")
    print("Студент: student@mail.ru / student")


# ==================== МАРШРУТЫ ====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        if not fullname or not email or not password:
            flash('Заполните все поля!', 'error')
            return redirect(url_for('register'))

        if password != password_confirm:
            flash('Пароли не совпадают!', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует!', 'error')
            return redirect(url_for('register'))

        user = User(fullname=fullname, email=email, role=UserRole.AUTHENTICATED)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_name'] = user.fullname
            session['user_email'] = user.email
            session['user_role'] = user.role

            user.last_login = datetime.utcnow()
            db.session.commit()

            flash(f'Добро пожаловать, {user.fullname}!', 'success')
            return redirect(url_for('cabinet'))
        else:
            flash('Неверный email или пароль!', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/cabinet')
@login_required
def cabinet():
    user = User.query.get(session['user_id'])
    return render_template('cabinet.html', user=user)


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


# ==================== СТРАНИЦЫ ПОСТУПЛЕНИЯ ====================

@app.route('/admission')
def admission():
    return render_template('admission.html')


@app.route('/admission/spo')
def admission_spo():
    specialties = Specialty.query.filter_by(level='spo', is_active=True).all()
    return render_template('admission_level.html',
                           title='Среднее профессиональное образование',
                           description='Обучение в колледже при ИжГУ. Диплом государственного образца.',
                           specialties=specialties)


@app.route('/admission/bachelor')
def admission_bachelor():
    specialties = Specialty.query.filter_by(level='bachelor', is_active=True).all()
    return render_template('admission_level.html',
                           title='Бакалавриат и специалитет',
                           description='Высшее образование. Диплом бакалавра государственного образца.',
                           specialties=specialties)


@app.route('/admission/master')
def admission_master():
    specialties = Specialty.query.filter_by(level='master', is_active=True).all()
    return render_template('admission_level.html',
                           title='Магистратура',
                           description='Углубленная подготовка по выбранному направлению.',
                           specialties=specialties)


@app.route('/admission/postgraduate')
def admission_postgraduate():
    specialties = Specialty.query.filter_by(level='postgraduate', is_active=True).all()
    return render_template('admission_level.html',
                           title='Аспирантура',
                           description='Научная деятельность, подготовка диссертации.',
                           specialties=specialties)


# ==================== АДМИН-ПАНЕЛЬ ====================

@app.route('/admin')
@admin_required
def admin_dashboard():
    users_count = User.query.count()
    specialties_count = Specialty.query.count()
    faculties_count = Faculty.query.count()
    admins_count = User.query.filter_by(role=UserRole.ADMIN).count()

    stats = {
        'users_count': users_count,
        'specialties_count': specialties_count,
        'faculties_count': faculties_count,
        'admins_count': admins_count
    }
    return render_template('admin/dashboard.html', stats=stats)


@app.route('/admin/faculties')
@admin_required
def admin_faculties():
    faculties = Faculty.query.all()
    return render_template('admin/faculties.html', faculties=faculties)


@app.route('/admin/faculties/add', methods=['POST'])
@admin_required
def admin_add_faculty():
    name = request.form.get('name')
    description = request.form.get('description')
    image_icon = request.form.get('image_icon', 'fa-university')

    if name:
        faculty = Faculty(name=name, description=description, image_icon=image_icon)
        db.session.add(faculty)
        db.session.commit()
        flash('Факультет успешно добавлен', 'success')

    return redirect(url_for('admin_faculties'))


@app.route('/admin/faculties/delete/<int:faculty_id>')
@admin_required
def admin_delete_faculty(faculty_id):
    faculty = Faculty.query.get(faculty_id)
    if faculty:
        db.session.delete(faculty)
        db.session.commit()
        flash('Факультет удалён', 'success')
    return redirect(url_for('admin_faculties'))


@app.route('/admin/specialties')
@admin_required
def admin_specialties():
    specialties = Specialty.query.all()
    faculties = Faculty.query.all()
    return render_template('admin/specialties.html', specialties=specialties, faculties=faculties)


@app.route('/admin/specialties/add', methods=['POST'])
@admin_required
def admin_add_specialty():
    specialty = Specialty(
        code=request.form.get('code'),
        name=request.form.get('name'),
        faculty_id=request.form.get('faculty_id'),
        level=request.form.get('level'),
        duration=request.form.get('duration'),
        qualification=request.form.get('qualification'),
        budget_places=request.form.get('budget_places', 0),
        tuition_fee=request.form.get('tuition_fee', 0)
    )
    db.session.add(specialty)
    db.session.commit()
    flash('Специальность успешно добавлена', 'success')
    return redirect(url_for('admin_specialties'))


@app.route('/admin/specialties/edit/<int:specialty_id>', methods=['POST'])
@admin_required
def admin_edit_specialty(specialty_id):
    specialty = Specialty.query.get(specialty_id)
    if specialty:
        specialty.code = request.form.get('code')
        specialty.name = request.form.get('name')
        specialty.faculty_id = request.form.get('faculty_id')
        specialty.level = request.form.get('level')
        specialty.duration = request.form.get('duration')
        specialty.qualification = request.form.get('qualification')
        specialty.budget_places = request.form.get('budget_places', 0)
        specialty.tuition_fee = request.form.get('tuition_fee', 0)
        db.session.commit()
        flash('Специальность обновлена', 'success')
    return redirect(url_for('admin_specialties'))


@app.route('/admin/specialties/delete/<int:specialty_id>')
@admin_required
def admin_delete_specialty(specialty_id):
    specialty = Specialty.query.get(specialty_id)
    if specialty:
        db.session.delete(specialty)
        db.session.commit()
        flash('Специальность удалена', 'success')
    return redirect(url_for('admin_specialties'))


@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/role/<int:user_id>', methods=['POST'])
@admin_required
def admin_change_role(user_id):
    user = User.query.get(user_id)
    if user and user.id != session['user_id']:
        new_role = request.form.get('role')
        user.role = new_role
        db.session.commit()
        flash(f'Роль пользователя {user.email} изменена на {new_role}', 'success')
    return redirect(url_for('admin_users'))


# ==================== ЗАПУСК ====================

if __name__ == '__main__':
    app.run(debug=True, port=5000)