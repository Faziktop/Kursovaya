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

class UserRole:
    AUTHENTICATED = 'authenticated'
    APPLICANT = 'applicant'
    STUDENT = 'student'
    EMPLOYEE = 'employee'
    TEACHER = 'teacher'
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

    for f in faculties_data:
        faculty = Faculty(name=f['name'], description=f['description'], image_icon=f['image_icon'])
        db.session.add(faculty)
    db.session.commit()

    faculties_dict = {f.name: f.id for f in Faculty.query.all()}

    # Создание пользователей
    users_data = [
        {'email': 'admin@gmail.com', 'fullname': 'Администратор', 'role': UserRole.ADMIN, 'password': 'admin',
         'position': 'Главный администратор', 'bio': 'Администратор системы'},
        {'email': 'teacher_it@istu.ru', 'fullname': 'Петров Петр Петрович', 'role': UserRole.TEACHER,
         'password': 'teacher', 'position': 'Заведующий кафедрой информационных технологий',
         'phone': '+7 (3412) 77-60-55', 'bio': 'Доктор технических наук, профессор'},
        {'email': 'teacher_economy@istu.ru', 'fullname': 'Сидорова Анна Ивановна', 'role': UserRole.TEACHER,
         'password': 'teacher', 'position': 'Заведующий кафедрой экономики', 'phone': '+7 (3412) 77-60-56',
         'bio': 'Кандидат экономических наук, доцент'},
        {'email': 'teacher_engineering@istu.ru', 'fullname': 'Иванов Сергей Викторович', 'role': UserRole.TEACHER,
         'password': 'teacher', 'position': 'Заведующий кафедрой машиностроения', 'phone': '+7 (3412) 77-60-57',
         'bio': 'Доктор технических наук, профессор'},
        {'email': 'teacher_law@istu.ru', 'fullname': 'Козлова Елена Михайловна', 'role': UserRole.TEACHER,
         'password': 'teacher', 'position': 'Заведующий кафедрой права', 'phone': '+7 (3412) 77-60-58',
         'bio': 'Кандидат юридических наук, доцент'},
        {'email': 'teacher_construction@istu.ru', 'fullname': 'Михайлов Андрей Владимирович', 'role': UserRole.TEACHER,
         'password': 'teacher', 'position': 'Заведующий кафедрой строительства', 'phone': '+7 (3412) 77-60-59',
         'bio': 'Кандидат технических наук, доцент'},
        {'email': 'employee_dean@istu.ru', 'fullname': 'Васильева Ольга Николаевна', 'role': UserRole.EMPLOYEE,
         'password': 'employee', 'position': 'Декан факультета информационных технологий',
         'phone': '+7 (3412) 77-60-60', 'bio': 'Кандидат педагогических наук'},
        {'email': 'employee_methodist@istu.ru', 'fullname': 'Смирнова Татьяна Алексеевна', 'role': UserRole.EMPLOYEE,
         'password': 'employee', 'position': 'Методист учебного отдела', 'phone': '+7 (3412) 77-60-61', 'bio': ''},
        {'email': 'student@mail.ru', 'fullname': 'Закиров Ильяс Русланович', 'role': UserRole.STUDENT,
         'password': 'student'},
    ]

    for u in users_data:
        user = User(
            email=u['email'],
            fullname=u['fullname'],
            role=u['role'],
            avatar='/static/uploads/avatars/default.png',
            phone=u.get('phone', ''),
            position=u.get('position', ''),
            bio=u.get('bio', ''),
            is_active=True
        )
        user.set_password(u['password'])
        db.session.add(user)
    db.session.commit()

    users_dict = {u.fullname: u.id for u in User.query.all()}

    # Создание специальностей
    specialties_data = [
        {'code': '09.02.07', 'name': 'Информационные системы и программирование',
         'faculty': 'Факультет информационных технологий', 'level': 'spo', 'duration': '2 года 10 месяцев',
         'qualification': 'Программист', 'budget_places': 50, 'paid_places': 50, 'tuition_fee': 120000,
         'head': 'Петров Петр Петрович'},
        {'code': '15.02.12', 'name': 'Монтаж, техническое обслуживание и ремонт промышленного оборудования',
         'faculty': 'Машиностроительный факультет', 'level': 'spo', 'duration': '3 года 10 месяцев',
         'qualification': 'Техник-механик', 'budget_places': 40, 'paid_places': 40, 'tuition_fee': 110000,
         'head': 'Иванов Сергей Викторович'},
        {'code': '38.02.01', 'name': 'Экономика и бухгалтерский учет', 'faculty': 'Факультет экономики и права',
         'level': 'spo', 'duration': '2 года 10 месяцев', 'qualification': 'Бухгалтер', 'budget_places': 45,
         'paid_places': 45, 'tuition_fee': 100000, 'head': 'Сидорова Анна Ивановна'},
        {'code': '09.03.01', 'name': 'Информатика и вычислительная техника',
         'faculty': 'Факультет информационных технологий', 'level': 'bachelor', 'duration': '4 года',
         'qualification': 'Бакалавр', 'budget_places': 60, 'paid_places': 60, 'tuition_fee': 150000,
         'head': 'Петров Петр Петрович'},
        {'code': '15.03.05', 'name': 'Конструкторско-технологическое обеспечение машиностроительных производств',
         'faculty': 'Машиностроительный факультет', 'level': 'bachelor', 'duration': '4 года',
         'qualification': 'Бакалавр', 'budget_places': 55, 'paid_places': 55, 'tuition_fee': 140000,
         'head': 'Иванов Сергей Викторович'},
        {'code': '38.03.01', 'name': 'Экономика', 'faculty': 'Факультет экономики и права', 'level': 'bachelor',
         'duration': '4 года', 'qualification': 'Бакалавр', 'budget_places': 70, 'paid_places': 70,
         'tuition_fee': 135000, 'head': 'Сидорова Анна Ивановна'},
        {'code': '40.03.01', 'name': 'Юриспруденция', 'faculty': 'Факультет экономики и права', 'level': 'bachelor',
         'duration': '4 года', 'qualification': 'Бакалавр', 'budget_places': 65, 'paid_places': 65,
         'tuition_fee': 145000, 'head': 'Козлова Елена Михайловна'},
        {'code': '44.03.01', 'name': 'Педагогическое образование',
         'faculty': 'Факультет математики и естественных наук', 'level': 'bachelor', 'duration': '4 года',
         'qualification': 'Бакалавр', 'budget_places': 50, 'paid_places': 50, 'tuition_fee': 125000, 'head': None},
        {'code': '08.03.01', 'name': 'Строительство', 'faculty': 'Факультет строительства, архитектуры и дизайна',
         'level': 'bachelor', 'duration': '4 года', 'qualification': 'Бакалавр', 'budget_places': 55, 'paid_places': 55,
         'tuition_fee': 140000, 'head': 'Михайлов Андрей Владимирович'},
        {'code': '09.04.01', 'name': 'Информатика и вычислительная техника',
         'faculty': 'Факультет информационных технологий', 'level': 'master', 'duration': '2 года',
         'qualification': 'Магистр', 'budget_places': 30, 'paid_places': 30, 'tuition_fee': 170000,
         'head': 'Петров Петр Петрович'},
        {'code': '38.04.01', 'name': 'Экономика', 'faculty': 'Факультет экономики и права', 'level': 'master',
         'duration': '2 года', 'qualification': 'Магистр', 'budget_places': 35, 'paid_places': 35,
         'tuition_fee': 160000, 'head': 'Сидорова Анна Ивановна'},
        {'code': '15.04.05', 'name': 'Конструкторско-технологическое обеспечение машиностроительных производств',
         'faculty': 'Машиностроительный факультет', 'level': 'master', 'duration': '2 года', 'qualification': 'Магистр',
         'budget_places': 25, 'paid_places': 25, 'tuition_fee': 165000, 'head': 'Иванов Сергей Викторович'},
        {'code': '09.06.01', 'name': 'Информатика и вычислительная техника',
         'faculty': 'Факультет информационных технологий', 'level': 'postgraduate', 'duration': '3 года',
         'qualification': 'Исследователь', 'budget_places': 10, 'paid_places': 10, 'tuition_fee': 200000,
         'head': 'Петров Петр Петрович'},
        {'code': '15.06.01', 'name': 'Машиностроение', 'faculty': 'Машиностроительный факультет',
         'level': 'postgraduate', 'duration': '3 года', 'qualification': 'Исследователь', 'budget_places': 10,
         'paid_places': 10, 'tuition_fee': 200000, 'head': 'Иванов Сергей Викторович'},
        {'code': '38.06.01', 'name': 'Экономика', 'faculty': 'Факультет экономики и права', 'level': 'postgraduate',
         'duration': '3 года', 'qualification': 'Исследователь', 'budget_places': 8, 'paid_places': 8,
         'tuition_fee': 195000, 'head': 'Сидорова Анна Ивановна'},
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
            paid_places=s.get('paid_places', 0),
            tuition_fee=s['tuition_fee'],
            head_id=users_dict.get(s['head']) if s.get('head') else None
        )
        db.session.add(specialty)
    db.session.commit()

    # Добавление вступительных испытаний, компетенций, дисциплин и трудоустройства
    for spec in Specialty.query.all():
        if spec.level == 'bachelor':
            exams = [
                {'name': 'Русский язык', 'min_score': 40},
                {'name': 'Математика (профильная)', 'min_score': 39},
                {'name': 'Информатика и ИКТ', 'min_score': 44}
            ]
            for exam_data in exams:
                exam = EntranceExam(
                    specialty_id=spec.id,
                    name=exam_data['name'],
                    min_score=exam_data['min_score']
                )
                db.session.add(exam)
        elif spec.level == 'master':
            exams = [
                {'name': 'Специализированный экзамен', 'min_score': 50},
                {'name': 'Собеседование', 'min_score': 60}
            ]
            for exam_data in exams:
                exam = EntranceExam(
                    specialty_id=spec.id,
                    name=exam_data['name'],
                    min_score=exam_data['min_score']
                )
                db.session.add(exam)
        elif spec.level == 'spo':
            exams = [
                {'name': 'Русский язык', 'min_score': 30},
                {'name': 'Математика', 'min_score': 30}
            ]
            for exam_data in exams:
                exam = EntranceExam(
                    specialty_id=spec.id,
                    name=exam_data['name'],
                    min_score=exam_data['min_score']
                )
                db.session.add(exam)

        if 'Информационные' in spec.name or 'Информатика' in spec.name:
            spec.competencies = 'Разработка программного обеспечения, администрирование баз данных, веб-разработка, машинное обучение, защита информации'
            spec.disciplines = 'Программирование, Базы данных, Web-технологии, Операционные системы, Сети и телекоммуникации, Искусственный интеллект'
        elif 'Экономика' in spec.name or 'Бухгалтерский' in spec.name:
            spec.competencies = 'Финансовый анализ, бюджетирование, налоговое планирование, управленческий учет'
            spec.disciplines = 'Макроэкономика, Микроэкономика, Бухучет, Финансы, Статистика, Налоги'
        elif 'Юриспруденция' in spec.name or 'Право' in spec.name:
            spec.competencies = 'Знание законодательства, составление документов, представление интересов в суде'
            spec.disciplines = 'Гражданское право, Уголовное право, Административное право, Трудовое право'
        elif 'Строительство' in spec.name:
            spec.competencies = 'Проектирование зданий, строительный контроль, сметное дело'
            spec.disciplines = 'Строительные материалы, Сопромат, Архитектура, Инженерные сети'
        elif 'Педагогическое' in spec.name:
            spec.competencies = 'Преподавание, воспитательная работа, разработка учебных программ'
            spec.disciplines = 'Педагогика, Психология, Методика преподавания, Возрастная психология'
        else:
            spec.competencies = 'Профессиональные компетенции по направлению подготовки'
            spec.disciplines = 'Профессиональные дисциплины по направлению подготовки'

        if 'Информационные' in spec.name or 'Информатика' in spec.name:
            employment = Employment(
                specialty_id=spec.id,
                description='Выпускники работают в IT-компаниях, банках, государственных структурах',
                positions='Программист, Разработчик, Системный аналитик, DevOps-инженер, Тестировщик'
            )
            db.session.add(employment)
        elif 'Экономика' in spec.name or 'Бухгалтерский' in spec.name:
            employment = Employment(
                specialty_id=spec.id,
                description='Выпускники востребованы в финансовых и экономических отделах компаний',
                positions='Экономист, Финансовый аналитик, Бухгалтер, Аудитор, Налоговый консультант'
            )
            db.session.add(employment)
        elif 'Юриспруденция' in spec.name or 'Право' in spec.name:
            employment = Employment(
                specialty_id=spec.id,
                description='Выпускники работают в юридических компаниях, государственных органах',
                positions='Юрист, Адвокат, Нотариус, Юрисконсульт, Судья'
            )
            db.session.add(employment)
        elif 'Строительство' in spec.name:
            employment = Employment(
                specialty_id=spec.id,
                description='Выпускники работают в строительных компаниях и проектных организациях',
                positions='Инженер-строитель, Прораб, Сметчик, Проектировщик'
            )
            db.session.add(employment)
        elif 'Педагогическое' in spec.name:
            employment = Employment(
                specialty_id=spec.id,
                description='Выпускники работают в образовательных учреждениях',
                positions='Учитель, Преподаватель, Педагог-психолог, Репетитор'
            )
            db.session.add(employment)

    db.session.commit()
    print("База данных создана с тестовыми данными!")


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

        user = User(
            fullname=fullname,
            email=email,
            role=UserRole.AUTHENTICATED,
            avatar='/static/uploads/avatars/default.png',
            phone=phone
        )
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
            session['user_avatar'] = user.avatar

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


# ==================== СТРАНИЦА СПЕЦИАЛЬНОСТИ ====================

@app.route('/specialty/<int:specialty_id>')
def specialty_detail(specialty_id):
    specialty = Specialty.query.get_or_404(specialty_id)
    entrance_exams = EntranceExam.query.filter_by(specialty_id=specialty_id).all()
    employment = Employment.query.filter_by(specialty_id=specialty_id).first()

    disciplines = []
    if specialty.disciplines:
        disciplines = [d.strip() for d in specialty.disciplines.split(',')]

    specialty.level_rus = get_level_rus(specialty.level)

    return render_template('specialty.html',
                           specialty=specialty,
                           entrance_exams=entrance_exams,
                           employment=employment,
                           disciplines=disciplines,
                           back_url=get_back_url(specialty.level))


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
    users = User.query.filter(User.role.in_([UserRole.EMPLOYEE, UserRole.TEACHER, UserRole.ADMIN])).all()
    return render_template('admin/specialties.html', specialties=specialties, faculties=faculties, users=users)


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
        form_of_education=request.form.get('form_of_education', 'Очная'),
        budget_places=request.form.get('budget_places', 0),
        paid_places=request.form.get('paid_places', 0),
        tuition_fee=request.form.get('tuition_fee', 0),
        location=request.form.get('location', 'г. Ижевск, ул. Студенческая, 7'),
        competencies=request.form.get('competencies', ''),
        disciplines=request.form.get('disciplines', ''),
        head_id=request.form.get('head_id') if request.form.get('head_id') else None,
        is_active=True
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
        specialty.form_of_education = request.form.get('form_of_education', 'Очная')
        specialty.budget_places = request.form.get('budget_places', 0)
        specialty.paid_places = request.form.get('paid_places', 0)
        specialty.tuition_fee = request.form.get('tuition_fee', 0)
        specialty.location = request.form.get('location', 'г. Ижевск, ул. Студенческая, 7')
        specialty.competencies = request.form.get('competencies', '')
        specialty.disciplines = request.form.get('disciplines', '')
        specialty.head_id = request.form.get('head_id') if request.form.get('head_id') else None
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


@app.route('/admin/users/edit/<int:user_id>', methods=['POST'])
@admin_required
def admin_edit_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.fullname = request.form.get('fullname')
        user.phone = request.form.get('phone')
        user.position = request.form.get('position')
        user.bio = request.form.get('bio')
        db.session.commit()
        flash('Данные пользователя обновлены', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/get/<int:user_id>')
@admin_required
def admin_get_user(user_id):
    user = User.query.get(user_id)
    if user:
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'fullname': user.fullname,
                'email': user.email,
                'phone': user.phone,
                'position': user.position,
                'bio': user.bio,
                'avatar': user.avatar,
                'role': user.role
            }
        })
    return jsonify({'success': False, 'error': 'Пользователь не найден'})
# ==================== ЗАПУСК ====================

if __name__ == '__main__':
    app.run(debug=True, port=5000)