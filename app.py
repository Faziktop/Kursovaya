from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from functools import wraps
import uuid
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# Настройка базы данных
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "database.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройка загрузки файлов
UPLOAD_FOLDER = os.path.join(basedir, 'uploads', 'documents')
AVATAR_FOLDER = os.path.join(basedir, 'static', 'uploads', 'avatars')
ORDERS_FOLDER = os.path.join(basedir, 'uploads', 'orders')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs(ORDERS_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['AVATAR_FOLDER'] = AVATAR_FOLDER
app.config['ORDERS_FOLDER'] = ORDERS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


db = SQLAlchemy(app)


# ==================== МОДЕЛИ БАЗЫ ДАННЫХ ====================

class UserRole:
    AUTHENTICATED = 'authenticated'
    APPLICANT = 'applicant'
    STUDENT = 'student'
    EMPLOYEE = 'employee'
    TEACHER = 'teacher'
    ADMIN = 'admin'
    RECTOR = 'rector'


class StudentStatus:
    STUDYING = 'studying'
    ACADEMIC_LEAVE = 'academic_leave'
    EXPELLED = 'expelled'
    GRADUATED = 'graduated'


# Факультеты
class Faculty(db.Model):
    __tablename__ = 'faculties'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_icon = db.Column(db.String(100), default='fa-university')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Пользователи
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    fullname = db.Column(db.String(200))
    avatar = db.Column(db.String(500), default='/static/uploads/avatars/default.png')
    phone = db.Column(db.String(20))
    position = db.Column(db.String(200))
    bio = db.Column(db.Text)
    role = db.Column(db.String(50), default=UserRole.AUTHENTICATED)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Заявления на поступление
class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    specialty_id = db.Column(db.Integer, db.ForeignKey('specialties.id'), nullable=False)
    status = db.Column(db.String(50), default='pending')
    documents_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='applications')
    specialty = db.relationship('Specialty', backref='applications')


# Приказы о зачислении
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_number = db.Column(db.String(100), nullable=False)
    pdf_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    application = db.relationship('Application', backref='orders')
    user = db.relationship('User', backref='orders')


# Специальности
class Specialty(db.Model):
    __tablename__ = 'specialties'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculties.id'), nullable=False)
    level = db.Column(db.String(50))
    duration = db.Column(db.String(50))
    qualification = db.Column(db.String(100))
    form_of_education = db.Column(db.String(100), default='Очная')
    budget_places = db.Column(db.Integer, default=0)
    paid_places = db.Column(db.Integer, default=0)
    tuition_fee = db.Column(db.Float, default=0)
    location = db.Column(db.String(255), default='г. Ижевск, ул. Студенческая, 7')
    competencies = db.Column(db.Text)
    disciplines = db.Column(db.Text)
    head_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    faculty = db.relationship('Faculty', backref='specialties')
    head = db.relationship('User', backref='headed_specialties')


# Вступительные испытания
class EntranceExam(db.Model):
    __tablename__ = 'entrance_exams'
    id = db.Column(db.Integer, primary_key=True)
    specialty_id = db.Column(db.Integer, db.ForeignKey('specialties.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    min_score = db.Column(db.Integer, default=30)
    priority = db.Column(db.Integer, default=1)

    specialty = db.relationship('Specialty', backref='entrance_exams')


# Данные о трудоустройстве
class Employment(db.Model):
    __tablename__ = 'employments'
    id = db.Column(db.Integer, primary_key=True)
    specialty_id = db.Column(db.Integer, db.ForeignKey('specialties.id'), nullable=False)
    description = db.Column(db.Text)
    positions = db.Column(db.String(500))

    specialty = db.relationship('Specialty', backref='employment')


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


# Модель для вопросов FAQ
class FAQ(db.Model):
    __tablename__ = 'faq'
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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
        user = db.session.get(User, session['user_id'])
        if user.role != UserRole.ADMIN:
            flash('Доступ запрещён. Требуются права администратора.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def rector_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'error')
            return redirect(url_for('login'))
        user = db.session.get(User, session['user_id'])
        if user.role not in [UserRole.RECTOR, UserRole.ADMIN]:
            flash('Доступ запрещён. Требуются права ректора или администратора.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_level_rus(level):
    levels = {
        'spo': 'Среднее профессиональное образование',
        'bachelor': 'Бакалавриат',
        'master': 'Магистратура',
        'postgraduate': 'Аспирантура'
    }
    return levels.get(level, level)


def get_back_url(level):
    urls = {
        'spo': '/admission/spo',
        'bachelor': '/admission/bachelor',
        'master': '/admission/master',
        'postgraduate': '/admission/postgraduate'
    }
    return urls.get(level, '/admission')


def save_avatar(user_id, file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        new_filename = f"avatar_{user_id}_{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(app.config['AVATAR_FOLDER'], new_filename)
        file.save(filepath)
        return f'/static/uploads/avatars/{new_filename}'
    return None


# ==================== СОЗДАНИЕ БД И ТЕСТОВЫХ ДАННЫХ ====================

with app.app_context():
    db.create_all()

    if Faculty.query.count() == 0:
        print("Создание начальных данных...")

        faculties_data = [
            {'name': 'Факультет информационных технологий', 'description': 'Подготовка IT-специалистов',
             'image_icon': 'fa-laptop'},
            {'name': 'Машиностроительный факультет', 'description': 'Подготовка инженеров-механиков',
             'image_icon': 'fa-industry'},
            {'name': 'Факультет экономики и права', 'description': 'Подготовка экономистов, юристов',
             'image_icon': 'fa-university'},
            {'name': 'Факультет строительства, архитектуры и дизайна',
             'description': 'Подготовка архитекторов, строителей', 'image_icon': 'fa-paint-brush'},
            {'name': 'Факультет математики и естественных наук', 'description': 'Подготовка математиков, физиков',
             'image_icon': 'fa-flask'},
            {'name': 'Институт энергетики', 'description': 'Подготовка энергетиков', 'image_icon': 'fa-bolt'},
            {'name': 'Приборостроительный факультет',
             'description': 'Подготовка специалистов в области приборостроения', 'image_icon': 'fa-microphone'},
            {'name': 'Институт физической культуры и спорта', 'description': 'Подготовка тренеров',
             'image_icon': 'fa-futbol-o'},
        ]
        for f in faculties_data:
            db.session.add(Faculty(name=f['name'], description=f['description'], image_icon=f['image_icon']))
        db.session.commit()
        faculties_dict = {f.name: f.id for f in Faculty.query.all()}

        users_data = [
            {'email': 'admin@gmail.com', 'fullname': 'Администратор', 'role': UserRole.ADMIN, 'password': 'admin',
             'position': 'Главный администратор'},
            {'email': 'rector@istu.ru', 'fullname': 'Ректор ИжГУ', 'role': UserRole.RECTOR, 'password': 'rector',
             'position': 'Ректор университета', 'phone': '+7 (3412) 77-60-50'},
            {'email': 'teacher_it@istu.ru', 'fullname': 'Петров Петр Петрович', 'role': UserRole.TEACHER,
             'password': 'teacher', 'position': 'Заведующий кафедрой ИТ'},
            {'email': 'teacher_economy@istu.ru', 'fullname': 'Сидорова Анна Ивановна', 'role': UserRole.TEACHER,
             'password': 'teacher', 'position': 'Заведующий кафедрой экономики'},
            {'email': 'teacher_engineering@istu.ru', 'fullname': 'Иванов Сергей Викторович', 'role': UserRole.TEACHER,
             'password': 'teacher', 'position': 'Заведующий кафедрой машиностроения'},
            {'email': 'employee_dean@istu.ru', 'fullname': 'Васильева Ольга Николаевна', 'role': UserRole.EMPLOYEE,
             'password': 'employee', 'position': 'Декан ФИТ'},
            {'email': 'student@mail.ru', 'fullname': 'Закиров Ильяс Русланович', 'role': UserRole.STUDENT,
             'password': 'student'},
            {'email': 'applicant@mail.ru', 'fullname': 'Иванов Иван Иванович', 'role': UserRole.APPLICANT,
             'password': 'applicant'},
        ]
        for u in users_data:
            user = User(email=u['email'], fullname=u['fullname'], role=u['role'],
                        avatar='/static/uploads/avatars/default.png', phone=u.get('phone', ''),
                        position=u.get('position', ''), bio=u.get('bio', ''), is_active=True)
            user.set_password(u['password'])
            db.session.add(user)
        db.session.commit()
        users_dict = {u.fullname: u.id for u in User.query.all()}

        specialties_data = [
            {'code': '09.02.07', 'name': 'Информационные системы и программирование',
             'faculty': 'Факультет информационных технологий', 'level': 'spo', 'duration': '2 года 10 месяцев',
             'qualification': 'Программист', 'budget_places': 50, 'paid_places': 50, 'tuition_fee': 120000,
             'head': 'Петров Петр Петрович'},
            {'code': '09.03.01', 'name': 'Информатика и вычислительная техника',
             'faculty': 'Факультет информационных технологий', 'level': 'bachelor', 'duration': '4 года',
             'qualification': 'Бакалавр', 'budget_places': 60, 'paid_places': 60, 'tuition_fee': 150000,
             'head': 'Петров Петр Петрович'},
            {'code': '38.03.01', 'name': 'Экономика', 'faculty': 'Факультет экономики и права', 'level': 'bachelor',
             'duration': '4 года', 'qualification': 'Бакалавр', 'budget_places': 70, 'paid_places': 70,
             'tuition_fee': 135000, 'head': 'Сидорова Анна Ивановна'},
            {'code': '40.03.01', 'name': 'Юриспруденция', 'faculty': 'Факультет экономики и права', 'level': 'bachelor',
             'duration': '4 года', 'qualification': 'Бакалавр', 'budget_places': 65, 'paid_places': 65,
             'tuition_fee': 145000, 'head': None},
            {'code': '08.03.01', 'name': 'Строительство', 'faculty': 'Факультет строительства, архитектуры и дизайна',
             'level': 'bachelor', 'duration': '4 года', 'qualification': 'Бакалавр', 'budget_places': 55,
             'paid_places': 55, 'tuition_fee': 140000, 'head': None},
        ]
        for s in specialties_data:
            specialty = Specialty(code=s['code'], name=s['name'], faculty_id=faculties_dict[s['faculty']],
                                  level=s['level'], duration=s['duration'], qualification=s['qualification'],
                                  budget_places=s['budget_places'], paid_places=s.get('paid_places', 0),
                                  tuition_fee=s['tuition_fee'],
                                  head_id=users_dict.get(s['head']) if s.get('head') else None)
            db.session.add(specialty)
        db.session.commit()

        for spec in Specialty.query.all():
            if spec.level == 'bachelor':
                exams = [{'name': 'Русский язык', 'min_score': 40}, {'name': 'Математика', 'min_score': 39},
                         {'name': 'Информатика', 'min_score': 44}]
                for exam_data in exams:
                    db.session.add(
                        EntranceExam(specialty_id=spec.id, name=exam_data['name'], min_score=exam_data['min_score']))
            elif spec.level == 'master':
                exams = [{'name': 'Специализированный экзамен', 'min_score': 50},
                         {'name': 'Собеседование', 'min_score': 60}]
                for exam_data in exams:
                    db.session.add(
                        EntranceExam(specialty_id=spec.id, name=exam_data['name'], min_score=exam_data['min_score']))
            elif spec.level == 'spo':
                exams = [{'name': 'Русский язык', 'min_score': 30}, {'name': 'Математика', 'min_score': 30}]
                for exam_data in exams:
                    db.session.add(
                        EntranceExam(specialty_id=spec.id, name=exam_data['name'], min_score=exam_data['min_score']))

            if 'Информационные' in spec.name or 'Информатика' in spec.name:
                spec.competencies = 'Разработка ПО, администрирование БД, веб-разработка'
                spec.disciplines = 'Программирование, Базы данных, Web-технологии'
                db.session.add(Employment(specialty_id=spec.id, description='Работа в IT-компаниях',
                                          positions='Программист, Разработчик, Аналитик'))
            elif 'Экономика' in spec.name:
                spec.competencies = 'Финансовый анализ, бюджетирование, налоговое планирование'
                spec.disciplines = 'Макроэкономика, Микроэкономика, Бухучет'
                db.session.add(Employment(specialty_id=spec.id, description='Работа в финансовых отделах',
                                          positions='Экономист, Бухгалтер, Аналитик'))
            elif 'Юриспруденция' in spec.name:
                spec.competencies = 'Знание законодательства, составление документов'
                spec.disciplines = 'Гражданское право, Уголовное право'
                db.session.add(Employment(specialty_id=spec.id, description='Работа в юридических компаниях',
                                          positions='Юрист, Адвокат, Юрисконсульт'))

        # Создание FAQ
        faq_data = [
            {'question': 'Как подать документы на поступление?',
             'answer': 'Для подачи документов необходимо авторизоваться в личном кабинете, выбрать интересующую специальность в разделе "Поступление" и заполнить форму с прикреплением необходимых документов (паспорт, СНИЛС, документ об образовании).',
             'order': 1},
            {'question': 'Какие документы нужны для поступления?',
             'answer': 'Для поступления необходимы: паспорт, СНИЛС, документ об образовании (аттестат или диплом), документы о льготах (при наличии), фотографии 3x4.',
             'order': 2},
            {'question': 'Как узнать статус моего заявления?',
             'answer': 'Статус заявления можно отслеживать в разделе "Мои заявления" личного кабинета. Статусы: "На рассмотрении", "На вступительных испытаниях", "На общем конкурсе", "Зачислен".',
             'order': 3},
            {'question': 'Как изменить личные данные?',
             'answer': 'Личные данные (ФИО, телефон) можно изменить в разделе "Профиль" личного кабинета. Изменение email возможно только через обращение в техническую поддержку.',
             'order': 4},
            {'question': 'Как загрузить аватар?',
             'answer': 'Для загрузки аватара наведите курсор на изображение профиля и нажмите на иконку камеры. Выберите файл изображения (PNG, JPG, JPEG) и он автоматически загрузится.',
             'order': 5},
            {'question': 'Что такое вступительные испытания?',
             'answer': 'Вступительные испытания - это экзамены или тестирования, которые необходимо сдать для поступления на выбранную специальность. Информацию о конкретных испытаниях можно найти на странице специальности.',
             'order': 6},
            {'question': 'Как связаться с приёмной комиссией?',
             'answer': 'Вы можете связаться с приёмной комиссией по телефону +7 (3412) 77-60-55 или по электронной почте abiturient@istu.ru.',
             'order': 7},
        ]
        for faq in faq_data:
            db.session.add(FAQ(question=faq['question'], answer=faq['answer'], order=faq['order'], is_active=True))

        db.session.commit()
        print("Начальные данные созданы!")
    else:
        print("База данных уже существует, данные сохранены.")


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
        phone = request.form.get('phone', '')

        if not fullname or not email or not password:
            flash('Заполните все обязательные поля!', 'error')
            return redirect(url_for('register'))
        if password != password_confirm:
            flash('Пароли не совпадают!', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует!', 'error')
            return redirect(url_for('register'))

        user = User(fullname=fullname, email=email, role=UserRole.AUTHENTICATED,
                    avatar='/static/uploads/avatars/default.png', phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация успешна!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
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
    return render_template('login.html')


@app.route('/cabinet')
@login_required
def cabinet():
    user = db.session.get(User, session['user_id'])
    return render_template('cabinet.html', user=user)


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'error': 'Файл не выбран'})
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Файл не выбран'})
    if file and allowed_file(file.filename):
        user_id = session['user_id']
        avatar_path = save_avatar(user_id, file)
        if avatar_path:
            user = db.session.get(User, user_id)
            if user.avatar and user.avatar != '/static/uploads/avatars/default.png':
                old_path = os.path.join(app.config['AVATAR_FOLDER'], user.avatar.split('/')[-1])
                if os.path.exists(old_path):
                    os.remove(old_path)
            user.avatar = avatar_path
            db.session.commit()
            session['user_avatar'] = avatar_path
            return jsonify({'success': True, 'message': 'Аватар обновлён!', 'avatar_path': avatar_path})
        return jsonify({'success': False, 'error': 'Недопустимый формат'})
    return jsonify({'success': False, 'error': 'Недопустимый формат'})


@app.route('/admin/upload_user_avatar/<int:user_id>', methods=['POST'])
@admin_required
def admin_upload_user_avatar(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'Пользователь не найден'})

    if 'avatar' not in request.files:
        return jsonify({'success': False, 'error': 'Файл не выбран'})

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Файл не выбран'})

    if file and allowed_file(file.filename):
        avatar_path = save_avatar(user_id, file)
        if avatar_path:
            if user.avatar and user.avatar != '/static/uploads/avatars/default.png':
                old_path = os.path.join(app.config['AVATAR_FOLDER'], user.avatar.split('/')[-1])
                if os.path.exists(old_path):
                    os.remove(old_path)
            user.avatar = avatar_path
            db.session.commit()
            return jsonify({'success': True, 'message': 'Аватар обновлён!', 'avatar_path': avatar_path})
        return jsonify({'success': False, 'error': 'Недопустимый формат файла'})
    return jsonify({'success': False, 'error': 'Недопустимый формат файла'})


@app.route('/admission')
def admission():
    return render_template('admission.html')


@app.route('/admission/spo')
def admission_spo():
    specialties = Specialty.query.filter_by(level='spo', is_active=True).all()
    return render_template('admission_level.html', title='Среднее профессиональное образование',
                           description='Обучение в колледже', specialties=specialties)


@app.route('/admission/bachelor')
def admission_bachelor():
    specialties = Specialty.query.filter_by(level='bachelor', is_active=True).all()
    return render_template('admission_level.html', title='Бакалавриат', description='Высшее образование',
                           specialties=specialties)


@app.route('/admission/master')
def admission_master():
    specialties = Specialty.query.filter_by(level='master', is_active=True).all()
    return render_template('admission_level.html', title='Магистратура', description='Углубленная подготовка',
                           specialties=specialties)


@app.route('/admission/postgraduate')
def admission_postgraduate():
    specialties = Specialty.query.filter_by(level='postgraduate', is_active=True).all()
    return render_template('admission_level.html', title='Аспирантура', description='Научная деятельность',
                           specialties=specialties)


@app.route('/specialty/<int:specialty_id>')
def specialty_detail(specialty_id):
    specialty = db.session.get(Specialty, specialty_id)
    entrance_exams = EntranceExam.query.filter_by(specialty_id=specialty_id).all()
    employment = Employment.query.filter_by(specialty_id=specialty_id).first()
    disciplines = [d.strip() for d in specialty.disciplines.split(',')] if specialty.disciplines else []
    specialty.level_rus = get_level_rus(specialty.level)
    return render_template('specialty.html', specialty=specialty, entrance_exams=entrance_exams, employment=employment,
                           disciplines=disciplines, back_url=get_back_url(specialty.level))


@app.route('/apply/<int:specialty_id>', methods=['GET', 'POST'])
@login_required
def apply(specialty_id):
    specialty = db.session.get(Specialty, specialty_id)
    user = db.session.get(User, session['user_id'])
    if request.method == 'POST':
        try:
            user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user.id))
            os.makedirs(user_folder, exist_ok=True)
            timestamp = int(datetime.utcnow().timestamp())
            application_folder = os.path.join(user_folder, str(timestamp))
            os.makedirs(application_folder, exist_ok=True)

            for field in ['passport', 'snils', 'education_doc', 'benefit_doc']:
                if field in request.files and request.files[field].filename:
                    file = request.files[field]
                    filename = f"{field}_{uuid.uuid4().hex}_{file.filename}"
                    file.save(os.path.join(application_folder, filename))

            if 'additional_docs' in request.files:
                for file in request.files.getlist('additional_docs'):
                    if file.filename:
                        filename = f"additional_{uuid.uuid4().hex}_{file.filename}"
                        file.save(os.path.join(application_folder, filename))

            benefits = request.form.getlist('benefits')
            benefit_types = ','.join(benefits) if benefits else 'none'

            form_data = {
                'last_name': request.form.get('last_name'),
                'first_name': request.form.get('first_name'),
                'patronymic': request.form.get('patronymic'),
                'birth_date': request.form.get('birth_date'),
                'education_doc_type': request.form.get('education_doc_type'),
                'benefit_type': benefit_types,
                'submitted_at': datetime.utcnow().isoformat()
            }
            import json
            with open(os.path.join(application_folder, 'form_data.json'), 'w', encoding='utf-8') as f:
                json.dump(form_data, f, ensure_ascii=False, indent=2)

            application = Application(user_id=user.id, specialty_id=specialty_id, status='pending',
                                      documents_path=application_folder)
            db.session.add(application)
            if user.role == 'authenticated':
                user.role = UserRole.APPLICANT
                session['user_role'] = user.role
            db.session.commit()
            flash('Документы успешно поданы!', 'success')
            return redirect(url_for('cabinet', section='applications'))
        except Exception as e:
            flash(f'Ошибка: {str(e)}', 'error')
    return render_template('apply.html', specialty=specialty, user=user)


# ==================== АДМИН-ПАНЕЛЬ ====================

@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = {'users_count': User.query.count(), 'specialties_count': Specialty.query.count(),
             'faculties_count': Faculty.query.count(),
             'admins_count': User.query.filter_by(role=UserRole.ADMIN).count()}
    return render_template('admin/dashboard.html', stats=stats)


@app.route('/admin/faculties')
@admin_required
def admin_faculties():
    return render_template('admin/faculties.html', faculties=Faculty.query.all())


@app.route('/admin/faculties/add', methods=['POST'])
@admin_required
def admin_add_faculty():
    if request.form.get('name'):
        db.session.add(Faculty(name=request.form.get('name'), description=request.form.get('description'),
                               image_icon=request.form.get('image_icon', 'fa-university')))
        db.session.commit()
        flash('Факультет добавлен', 'success')
    return redirect(url_for('admin_faculties'))


@app.route('/admin/faculties/delete/<int:faculty_id>')
@admin_required
def admin_delete_faculty(faculty_id):
    faculty = db.session.get(Faculty, faculty_id)
    if faculty:
        db.session.delete(faculty)
        db.session.commit()
        flash('Факультет удалён', 'success')
    return redirect(url_for('admin_faculties'))


@app.route('/admin/faculties/update/<int:faculty_id>', methods=['POST'])
@admin_required
def admin_update_faculty(faculty_id):
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({'success': False, 'error': 'Факультет не найден'})
    data = request.get_json()
    if data:
        if 'name' in data: faculty.name = data['name']
        if 'description' in data: faculty.description = data['description']
        if 'image_icon' in data: faculty.image_icon = data['image_icon']
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Нет данных'})


@app.route('/admin/faculties/get/<int:faculty_id>')
@admin_required
def admin_get_faculty_json(faculty_id):
    faculty = db.session.get(Faculty, faculty_id)
    if faculty:
        return jsonify({'success': True,
                        'faculty': {'id': faculty.id, 'name': faculty.name, 'description': faculty.description or '',
                                    'image_icon': faculty.image_icon or 'fa-university'}})
    return jsonify({'success': False, 'error': 'Факультет не найден'})


@app.route('/admin/specialties')
@admin_required
def admin_specialties():
    return render_template('admin/specialties.html', specialties=Specialty.query.all(), faculties=Faculty.query.all(),
                           users=User.query.filter(User.role.in_(
                               [UserRole.EMPLOYEE, UserRole.TEACHER, UserRole.ADMIN, UserRole.RECTOR])).all())


@app.route('/admin/specialties/add', methods=['POST'])
@admin_required
def admin_add_specialty():
    specialty = Specialty(code=request.form.get('code'), name=request.form.get('name'),
                          faculty_id=request.form.get('faculty_id'), level=request.form.get('level'),
                          duration=request.form.get('duration'), qualification=request.form.get('qualification'),
                          form_of_education=request.form.get('form_of_education', 'Очная'),
                          budget_places=request.form.get('budget_places', 0),
                          paid_places=request.form.get('paid_places', 0),
                          tuition_fee=request.form.get('tuition_fee', 0),
                          location=request.form.get('location', 'г. Ижевск, ул. Студенческая, 7'),
                          competencies=request.form.get('competencies', ''),
                          disciplines=request.form.get('disciplines', ''),
                          head_id=request.form.get('head_id') if request.form.get('head_id') else None, is_active=True)
    db.session.add(specialty)
    db.session.commit()
    flash('Специальность добавлена', 'success')
    return redirect(url_for('admin_specialties'))


@app.route('/admin/specialties/delete/<int:specialty_id>')
@admin_required
def admin_delete_specialty(specialty_id):
    specialty = db.session.get(Specialty, specialty_id)
    if specialty:
        db.session.delete(specialty)
        db.session.commit()
        flash('Специальность удалена', 'success')
    return redirect(url_for('admin_specialties'))


@app.route('/admin/specialties/get/<int:specialty_id>')
@admin_required
def admin_get_specialty_json(specialty_id):
    specialty = db.session.get(Specialty, specialty_id)
    if specialty:
        exams = EntranceExam.query.filter_by(specialty_id=specialty_id).all()
        return jsonify({
            'success': True,
            'specialty': {
                'id': specialty.id,
                'code': specialty.code,
                'name': specialty.name,
                'faculty_id': specialty.faculty_id,
                'level': specialty.level,
                'duration': specialty.duration,
                'qualification': specialty.qualification,
                'form_of_education': specialty.form_of_education,
                'budget_places': specialty.budget_places,
                'paid_places': specialty.paid_places,
                'tuition_fee': specialty.tuition_fee,
                'location': specialty.location,
                'competencies': specialty.competencies or '',
                'disciplines': specialty.disciplines or '',
                'head_id': specialty.head_id
            },
            'exams': [{'id': e.id, 'name': e.name, 'min_score': e.min_score} for e in exams]
        })
    return jsonify({'success': False, 'error': 'Специальность не найдена'})


@app.route('/admin/specialties/update/<int:specialty_id>', methods=['POST'])
@admin_required
def admin_update_specialty(specialty_id):
    specialty = db.session.get(Specialty, specialty_id)
    if not specialty:
        return jsonify({'success': False, 'error': 'Специальность не найдена'})

    data = request.get_json()
    if data:
        for key in ['code', 'name', 'faculty_id', 'level', 'duration', 'qualification', 'form_of_education', 'location',
                    'competencies', 'disciplines']:
            if key in data: setattr(specialty, key, data[key])
        for key in ['budget_places', 'paid_places', 'tuition_fee']:
            if key in data: setattr(specialty, key, data[key])
        if 'head_id' in data: specialty.head_id = data['head_id'] if data['head_id'] else None

        if 'exams' in data:
            EntranceExam.query.filter_by(specialty_id=specialty_id).delete()
            for exam in data['exams']:
                if exam.get('name') and exam.get('name').strip():
                    db.session.add(EntranceExam(
                        specialty_id=specialty_id,
                        name=exam['name'],
                        min_score=exam.get('min_score', 30),
                        priority=exam.get('priority', 1)
                    ))

        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Нет данных'})


@app.route('/admin/users')
@admin_required
def admin_users():
    return render_template('admin/users.html', users=User.query.all())


@app.route('/admin/users/role/<int:user_id>', methods=['POST'])
@admin_required
def admin_change_role(user_id):
    user = db.session.get(User, user_id)
    if user and user.id != session['user_id']:
        new_role = request.form.get('role')
        if new_role in ['authenticated', 'applicant', 'student', 'employee', 'teacher', 'rector', 'admin']:
            user.role = new_role
            db.session.commit()
            flash(f'Роль изменена на {new_role}', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/update/<int:user_id>', methods=['POST'])
@admin_required
def admin_update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'Пользователь не найден'})
    data = request.get_json()
    if data:
        for key in ['fullname', 'phone', 'position', 'bio', 'avatar']:
            if key in data: setattr(user, key, data[key])
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Нет данных'})


@app.route('/admin/users/get/<int:user_id>')
@admin_required
def admin_get_user_json(user_id):
    user = db.session.get(User, user_id)
    if user:
        return jsonify({'success': True, 'user': {'id': user.id, 'fullname': user.fullname or '', 'email': user.email,
                                                  'phone': user.phone or '', 'position': user.position or '',
                                                  'bio': user.bio or '',
                                                  'avatar': user.avatar or '/static/uploads/avatars/default.png',
                                                  'role': user.role}})
    return jsonify({'success': False, 'error': 'Пользователь не найден'})


# ==================== API ДЛЯ FAQ И ПРЕПОДАВАТЕЛЕЙ ====================

@app.route('/api/faq')
def get_faq():
    """Получение списка часто задаваемых вопросов"""
    faq_list = FAQ.query.filter_by(is_active=True).order_by(FAQ.order).all()
    return jsonify({
        'faq': [{'id': f.id, 'question': f.question, 'answer': f.answer} for f in faq_list]
    })


@app.route('/api/teachers')
def get_teachers():
    """Получение списка преподавателей"""
    teachers = User.query.filter(User.role == UserRole.TEACHER).all()
    return jsonify({
        'teachers': [{
            'id': t.id,
            'fullname': t.fullname,
            'position': t.position,
            'bio': t.bio,
            'phone': t.phone,
            'email': t.email,
            'avatar': t.avatar if t.avatar != '/static/uploads/avatars/default.png' else None
        } for t in teachers]
    })


# ==================== РЕКТОР - ПРИЁМНАЯ КОМИССИЯ ====================

@app.route('/rector/applications')
@rector_required
def rector_applications():
    faculties = Faculty.query.all()
    specialties = Specialty.query.all()
    return render_template('rector/applications.html', faculties=faculties, specialties=specialties)


@app.route('/rector/api/applications/<status_filter>')
@rector_required
def rector_api_applications_filtered(status_filter):
    status_map = {
        'pending': ['pending'],
        'exams': ['exams'],
        'competitive': ['competitive'],
        'consent': ['approved', 'consent_pending']
    }
    statuses = status_map.get(status_filter, ['pending', 'exams', 'competitive', 'approved', 'consent_pending'])

    status_text = {
        'pending': 'На рассмотрении',
        'exams': 'На вступительных испытаниях',
        'competitive': 'На общем конкурсе',
        'approved': 'Предложение о зачислении',
        'consent_pending': 'Согласие получено',
        'enrolled': 'Зачислен',
        'rejected': 'Отказано'
    }

    applications = Application.query.filter(Application.status.in_(statuses)).order_by(
        Application.created_at.desc()).all()
    return jsonify({
        'applications': [{
            'id': app.id,
            'specialty_id': app.specialty_id,
            'specialty_name': app.specialty.name if app.specialty else '',
            'specialty_code': app.specialty.code if app.specialty else '',
            'faculty_name': app.specialty.faculty.name if app.specialty and app.specialty.faculty else '',
            'applicant_name': app.user.fullname if app.user else '',
            'applicant_email': app.user.email if app.user else '',
            'status': app.status,
            'status_text': status_text.get(app.status, 'Неизвестно'),
            'created_at': app.created_at.strftime('%d.%m.%Y %H:%M')
        } for app in applications]
    })


@app.route('/rector/applications/bulk-update', methods=['POST'])
@rector_required
def rector_bulk_update():
    data = request.get_json()
    application_ids = data.get('ids', [])
    new_status = data.get('status')

    if not application_ids or not new_status:
        return jsonify({'success': False, 'error': 'Нет данных'})

    try:
        for app_id in application_ids:
            application = db.session.get(Application, app_id)
            if application:
                application.status = new_status
                application.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': f'Обновлено {len(application_ids)} заявлений'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/rector/applications/update/<int:application_id>', methods=['POST'])
@rector_required
def rector_update_application_status(application_id):
    application = db.session.get(Application, application_id)
    if not application:
        return jsonify({'success': False, 'error': 'Заявление не найдено'})

    data = request.get_json()
    if data and 'status' in data:
        application.status = data['status']
        application.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'new_status': data['status']})
    return jsonify({'success': False, 'error': 'Нет данных'})


@app.route('/rector/applications/view/<int:application_id>')
@rector_required
def rector_view_application(application_id):
    application = db.session.get(Application, application_id)
    if not application:
        flash('Заявление не найдено', 'error')
        return redirect(url_for('rector_applications'))

    form_data = {}
    if application.documents_path and os.path.exists(application.documents_path):
        json_path = os.path.join(application.documents_path, 'form_data.json')
        if os.path.exists(json_path):
            import json
            with open(json_path, 'r', encoding='utf-8') as f:
                form_data = json.load(f)

    files = []
    if application.documents_path and os.path.exists(application.documents_path):
        for file in os.listdir(application.documents_path):
            if file.endswith(('.pdf', '.jpg', '.jpeg', '.png')) and file != 'form_data.json':
                file_path = os.path.join(application.documents_path, file)
                files.append({'name': file, 'size': os.path.getsize(file_path)})

    return render_template('rector/application_detail.html', application=application,
                           user=db.session.get(User, application.user_id), form_data=form_data, files=files)


@app.route('/rector/applications/download/<int:application_id>/<filename>')
@rector_required
def rector_download_file(application_id, filename):
    application = db.session.get(Application, application_id)
    return send_from_directory(application.documents_path, filename, as_attachment=True)


# ==================== РЕКТОР - ЗАЧИСЛЕНИЕ ====================

@app.route('/rector/offer-enrollment/<int:application_id>', methods=['POST'])
@rector_required
def offer_enrollment(application_id):
    application = db.session.get(Application, application_id)
    if not application:
        return jsonify({'success': False, 'error': 'Заявление не найдено'})

    application.status = 'approved'
    application.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Предложение о зачислении отправлено'})


@app.route('/rector/offer-enrollment-bulk', methods=['POST'])
@rector_required
def offer_enrollment_bulk():
    data = request.get_json()
    application_ids = data.get('ids', [])

    if not application_ids:
        return jsonify({'success': False, 'error': 'Нет выбранных заявлений'})

    try:
        for app_id in application_ids:
            application = db.session.get(Application, app_id)
            if application and application.status == 'competitive':
                application.status = 'approved'
                application.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': f'Предложения отправлены для {len(application_ids)} заявлений'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/rector/issue-order/<int:application_id>', methods=['POST'])
@rector_required
def issue_order(application_id):
    application = db.session.get(Application, application_id)
    if not application:
        return jsonify({'success': False, 'error': 'Заявление не найдено'})

    order_number = request.form.get('order_number')
    if not order_number:
        return jsonify({'success': False, 'error': 'Номер приказа обязателен'})

    pdf_file = request.files.get('order_pdf')
    if not pdf_file or pdf_file.filename == '':
        return jsonify({'success': False, 'error': 'PDF файл приказа обязателен'})

    user_folder = os.path.join(app.config['ORDERS_FOLDER'], str(application.user_id))
    os.makedirs(user_folder, exist_ok=True)
    pdf_filename = f"order_{application_id}_{uuid.uuid4().hex}.pdf"
    pdf_path = os.path.join(user_folder, pdf_filename)
    pdf_file.save(pdf_path)

    order = Order(application_id=application_id, user_id=application.user_id, order_number=order_number,
                  pdf_path=f"/uploads/orders/{application.user_id}/{pdf_filename}")
    db.session.add(order)

    application.status = 'enrolled'
    application.updated_at = datetime.utcnow()

    user = db.session.get(User, application.user_id)
    if user and user.role == UserRole.APPLICANT:
        user.role = UserRole.STUDENT
        if session.get('user_id') == user.id:
            session['user_role'] = user.role

    db.session.commit()
    return jsonify({'success': True, 'message': 'Приказ издан, студент зачислен'})


# ==================== АБИТУРИЕНТ - СОГЛАСИЕ НА ЗАЧИСЛЕНИЕ ====================

@app.route('/applicant/consent/<int:application_id>', methods=['POST'])
@login_required
def applicant_consent(application_id):
    application = db.session.get(Application, application_id)
    if not application or application.user_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Заявление не найдено'})

    if application.status != 'approved':
        return jsonify({'success': False, 'error': 'Нет активного предложения'})

    action = request.json.get('action')
    if action == 'accept':
        application.status = 'consent_pending'
        application.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Согласие принято'})
    elif action == 'reject':
        application.status = 'competitive'
        application.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Вы отказались'})

    return jsonify({'success': False, 'error': 'Неверное действие'})


# ==================== API ====================

@app.route('/api/applications')
@login_required
def get_applications():
    status_text = {'pending': 'На рассмотрении', 'exams': 'На вступительных', 'competitive': 'На общем конкурсе',
                   'approved': 'Предложение о зачислении', 'consent_pending': 'Согласие получено',
                   'enrolled': 'Зачислен', 'rejected': 'Отказано'}
    applications = Application.query.filter_by(user_id=session['user_id']).all()
    return jsonify({'applications': [
        {'id': app.id, 'specialty_name': app.specialty.name if app.specialty else '', 'status': app.status,
         'status_text': status_text.get(app.status, 'Неизвестно'),
         'created_at': app.created_at.strftime('%d.%m.%Y %H:%M')} for app in applications]})


@app.route('/api/applications/delete/<int:application_id>', methods=['DELETE'])
@login_required
def delete_application(application_id):
    application = db.session.get(Application, application_id)
    if not application or application.user_id != session['user_id'] or application.status != 'pending':
        return jsonify({'success': False, 'error': 'Нельзя удалить'})
    try:
        if application.documents_path and os.path.exists(application.documents_path):
            import shutil
            shutil.rmtree(application.documents_path)
        db.session.delete(application)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/user/orders')
@login_required
def user_orders():
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).all()
    return jsonify({'orders': [
        {'id': o.id, 'order_number': o.order_number, 'created_at': o.created_at.strftime('%d.%m.%Y'),
         'pdf_path': o.pdf_path,
         'specialty_name': o.application.specialty.name if o.application and o.application.specialty else 'Не указана'}
        for o in orders]})


@app.route('/uploads/orders/<path:filename>')
def serve_order_file(filename):
    return send_from_directory(app.config['ORDERS_FOLDER'], filename)


# ==================== УПРАВЛЕНИЕ FAQ (АДМИН-ПАНЕЛЬ) ====================


@app.route('/admin/faq')
@admin_required
def admin_faq():
    """Страница управления FAQ в админ-панели"""
    faq_list = FAQ.query.order_by(FAQ.order).all()
    return render_template('admin/faq.html', faq_list=faq_list)


@app.route('/admin/faq/add', methods=['POST'])
@admin_required
def admin_faq_add():
    """Добавление нового вопроса"""
    question = request.form.get('question')
    answer = request.form.get('answer')
    order = request.form.get('order', 0)

    if not question or not answer:
        flash('Заполните все поля!', 'error')
        return redirect(url_for('admin_faq'))

    faq = FAQ(question=question, answer=answer, order=int(order), is_active=True)
    db.session.add(faq)
    db.session.commit()
    flash('Вопрос успешно добавлен!', 'success')
    return redirect(url_for('admin_faq'))


@app.route('/admin/faq/edit/<int:faq_id>', methods=['POST'])
@admin_required
def admin_faq_edit(faq_id):
    """Редактирование вопроса"""
    faq = db.session.get(FAQ, faq_id)
    if not faq:
        return jsonify({'success': False, 'error': 'Вопрос не найден'})

    data = request.get_json()
    if data:
        if 'question' in data:
            faq.question = data['question']
        if 'answer' in data:
            faq.answer = data['answer']
        if 'order' in data:
            faq.order = data['order']
        if 'is_active' in data:
            faq.is_active = data['is_active']
        db.session.commit()
        return jsonify({'success': True, 'message': 'Сохранено'})
    return jsonify({'success': False, 'error': 'Нет данных'})


@app.route('/admin/faq/delete/<int:faq_id>', methods=['DELETE'])
@admin_required
def admin_faq_delete(faq_id):
    """Удаление вопроса"""
    faq = db.session.get(FAQ, faq_id)
    if not faq:
        return jsonify({'success': False, 'error': 'Вопрос не найден'})

    db.session.delete(faq)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Вопрос удалён'})


@app.route('/admin/faq/get/<int:faq_id>')
@admin_required
def admin_faq_get(faq_id):
    """Получение данных вопроса для редактирования"""
    faq = db.session.get(FAQ, faq_id)
    if faq:
        return jsonify({
            'success': True,
            'faq': {
                'id': faq.id,
                'question': faq.question,
                'answer': faq.answer,
                'order': faq.order,
                'is_active': faq.is_active
            }
        })
    return jsonify({'success': False, 'error': 'Вопрос не найден'})


if __name__ == '__main__':
    app.run(debug=True, port=7777, host="0.0.0.0")