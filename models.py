import sqlite3
from datetime import datetime, timedelta
from config import DEFAULT_INCOME_CATEGORY, DEFAULT_EXPENSE_CATEGORIES

DB_PATH = "finance.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Проекты
    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Статьи доходов/расходов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL CHECK(type IN ('income','expense'))
        )
    """)

    # Операции (доходы/расходы)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    """)

    # Сотрудники
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE
        )
    """)

    # Связь сотрудников и проектов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS project_employees (
            project_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'участник',
            PRIMARY KEY(project_id, employee_id),
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        )
    """)

    # Заполняем категории по умолчанию, если пусто
    cur.execute("SELECT count(*) FROM categories")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO categories (name, type) VALUES (?, ?)",
                    (DEFAULT_INCOME_CATEGORY, "income"))
        for cat in DEFAULT_EXPENSE_CATEGORIES:
            cur.execute("INSERT INTO categories (name, type) VALUES (?, ?)", (cat, "expense"))

    conn.commit()
    conn.close()


def seed_data():
    """Добавляет тестовые данные, если в БД ещё нет проектов."""
    conn = get_conn()
    cur = conn.cursor()

    # Проверяем, есть ли уже проекты
    cur.execute("SELECT count(*) FROM projects")
    if cur.fetchone()[0] > 0:
        conn.close()
        return  # данные уже есть, ничего не делаем

    # Получаем ID категорий
    cur.execute("SELECT id, name, type FROM categories")
    cats = {c["name"]: c["id"] for c in cur.fetchall()}
    income_cat_id = cats.get(DEFAULT_INCOME_CATEGORY)
    expense_cats = [c for c in cats.items() if c[1] != income_cat_id]

    # 5 тестовых проектов
    projects = [
        ("Разработка CRM-модуля", "Интеграция с Битрикс24, REST API, отчёты"),
        ("Мобильное приложение для курьеров", "Android/iOS, офлайн-режим, трекинг"),
        ("Портал для HR-отдела", "Личный кабинет сотрудника, заявки, согласования"),
        ("Дашборд аналитики продаж", "Power BI, выгрузка из 1С, KPI по менеджерам"),
        ("Чат-бот для техподдержки", "Telegram/WhatsApp, FAQ, эскалация тикетов"),
    ]

    now = datetime.now()

    for i, (name, desc) in enumerate(projects, start=1):
        # Создаём проект
        cur.execute(
            "INSERT INTO projects (name, description, created_at) VALUES (?, ?, ?)",
            (name, desc, now.strftime("%Y-%m-%d %H:%M:%S"))
        )
        project_id = cur.lastrowid

        # Добавляем 3–5 операций на проект (смешанные доходы/расходы)
        ops = []
        base_date = now - timedelta(days=60)
        for j in range(3 + i % 3):
            is_income = (j % 2 == 0)
            cat_id = income_cat_id if is_income else expense_cats[j % len(expense_cats)][1]
            amount = (150000 + j * 20000) if is_income else (80000 + j * 15000)
            date_str = (base_date + timedelta(days=j * 7)).strftime("%Y-%m-%d")
            desc_op = f"Этап {j+1}"
            ops.append((project_id, cat_id, amount, date_str, desc_op))

        cur.executemany(
            "INSERT INTO operations (project_id, category_id, amount, date, description) VALUES (?, ?, ?, ?, ?)",
            ops
        )

    # Добавим 4 тестовых сотрудника
    employees = [
        ("Анна Петрова", "anna.petrova@example.com"),
        ("Иван Смирнов", "ivan.smirnov@example.com"),
        ("Мария Козлова", "maria.kozlova@example.com"),
        ("Дмитрий Волков", "dmitry.volkov@example.com"),
    ]
    for name, email in employees:
        try:
            cur.execute("INSERT INTO employees (name, email) VALUES (?, ?)", (name, email))
        except sqlite3.IntegrityError:
            pass

    # Назначим сотрудников на проекты (по 1–2 на проект)
    assignments = [
        (1, 1, "руководитель"), (1, 2, "участник"),
        (2, 2, "руководитель"), (2, 3, "участник"),
        (3, 3, "руководитель"), (3, 4, "участник"),
        (4, 1, "руководитель"), (4, 4, "участник"),
        (5, 2, "руководитель"), (5, 3, "участник"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO project_employees (project_id, employee_id, role) VALUES (?, ?, ?)",
        assignments
    )

    conn.commit()
    conn.close()
