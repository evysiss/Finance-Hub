from flask import Flask, render_template, request, redirect, url_for, flash
from models import init_db, get_conn, seed_data
from bitrix24 import sync_projects, sync_employees
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "dev-secret-key"

init_db()
seed_data()   

def calc_metrics(project_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM operations o
        JOIN categories c ON o.category_id = c.id
        WHERE o.project_id = ? AND c.type = 'income'
    """, (project_id,))
    income = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM operations o
        JOIN categories c ON o.category_id = c.id
        WHERE o.project_id = ? AND c.type = 'expense'
    """, (project_id,))
    expense = cur.fetchone()[0]

    profit = income - expense
    rent = (profit / income * 100) if income > 0 else 0
    conn.close()
    return income, expense, profit, rent


@app.route("/")
def index():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM projects ORDER BY created_at DESC")
    projects = cur.fetchall()

    metrics = {}
    total_income = 0
    total_expense = 0
    for p in projects:
        m = calc_metrics(p["id"])
        metrics[p["id"]] = m
        total_income += m[0]
        total_expense += m[1]

    total_profit = total_income - total_expense
    total_rent = (total_profit / total_income * 100) if total_income > 0 else 0

    conn.close()
    return render_template(
        "index.html",
        projects=projects,
        metrics=metrics,
        total_income=total_income,
        total_expense=total_expense,
        total_profit=total_profit,
        total_rent=total_rent,
    )


@app.route("/projects", methods=["GET", "POST"])
def projects():
    conn = get_conn()
    cur = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name")
        desc = request.form.get("description")
        if name:
            cur.execute("INSERT INTO projects (name, description) VALUES (?, ?)", (name, desc))
            conn.commit()
            conn.close()
            flash("Проект создан", "success")
            return redirect(url_for("projects"))

    cur.execute("SELECT * FROM projects ORDER BY created_at DESC")
    rows = cur.fetchall()
    metrics = {}
    for p in rows:
        metrics[p["id"]] = calc_metrics(p["id"])
    conn.close()
    return render_template("projects.html", projects=rows, metrics=metrics)



@app.route("/project/<int:pid>")
def project(pid):
    conn = get_conn()
    cur = conn.cursor()

    # 1. Получаем сам проект
    cur.execute("SELECT * FROM projects WHERE id = ?", (pid,))
    proj = cur.fetchone()
    if not proj:
        conn.close()
        flash("Проект не найден", "error")
        return redirect(url_for("index"))

    # 2. Операции
    cur.execute("""
        SELECT o.*, c.name AS cat_name, c.type AS cat_type
        FROM operations o
        JOIN categories c ON o.category_id = c.id
        WHERE o.project_id = ?
        ORDER BY o.date DESC
    """, (pid,))
    ops = cur.fetchall()

    # 3. Категории
    cur.execute("SELECT * FROM categories ORDER BY type, name")
    cats = cur.fetchall()

    # 4. Сотрудники проекта
    cur.execute("""
        SELECT e.name, e.email, pe.role
        FROM project_employees pe
        JOIN employees e ON pe.employee_id = e.id
        WHERE pe.project_id = ?
    """, (pid,))
    employees = cur.fetchall()

    # 5. ВСЕ сотрудники (для формы назначения)
    cur.execute("SELECT * FROM employees ORDER BY name")
    all_employees = cur.fetchall()

    # 6. Отдельно — ответственный (руководитель)
    cur.execute("""
        SELECT e.name AS responsible_name
        FROM project_employees pe
        JOIN employees e ON pe.employee_id = e.id
        WHERE pe.project_id = ? AND pe.role = 'руководитель'
    """, (pid,))
    resp_row = cur.fetchone()
    responsible_name = resp_row["responsible_name"] if resp_row else None

    # 7. Считаем метрики
    income, expense, profit, rent = calc_metrics(pid)

    conn.close()

    return render_template(
        "project.html",
        project=proj,
        operations=ops,
        categories=cats,
        employees=employees,
        all_employees=all_employees,
        income=income,
        expense=expense,
        profit=profit,
        rent=rent,
        responsible_name=responsible_name
    )




@app.route("/operation/<int:pid>", methods=["POST"])
def add_operation(pid):
    cat_id = request.form.get("category_id")
    amount = float(request.form.get("amount", 0))
    date = request.form.get("date") or str(datetime.now().date())
    desc = request.form.get("description", "")
    if cat_id and amount:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO operations (project_id, category_id, amount, date, description) VALUES (?, ?, ?, ?, ?)",
            (pid, cat_id, amount, date, desc)
        )
        conn.commit()
        conn.close()
        flash("Операция добавлена", "success")
    return redirect(url_for("project", pid=pid))


@app.route("/category", methods=["POST"])
def add_category():
    name = request.form.get("name")
    typ = request.form.get("type")
    pid = request.form.get("pid", 1)
    if name and typ in ("income", "expense"):
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO categories (name, type) VALUES (?, ?)", (name, typ))
            conn.commit()
            flash("Категория добавлена", "success")
        except sqlite3.IntegrityError:
            flash("Такая категория уже есть", "error")
        finally:
            conn.close()
    else:
        flash("Некорректные данные", "error")
    return redirect(url_for("project", pid=pid))


@app.route("/employee", methods=["POST"])
def add_employee():
    name = request.form.get("name")
    email = request.form.get("email")
    pid = request.form.get("pid")
    if name:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO employees (name, email) VALUES (?, ?)", (name, email))
            conn.commit()
            flash("Сотрудник создан", "success")
        except sqlite3.IntegrityError:
            flash("Сотрудник с таким email уже есть", "error")
        finally:
            conn.close()
    if pid:
        return redirect(url_for("project", pid=pid))
    return redirect(url_for("index"))



@app.route("/employee/<int:pid>", methods=["POST"])
def add_employee_to_project(pid):
    eid = request.form.get("employee_id")
    role = request.form.get("role", "участник")
    if eid:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT OR IGNORE INTO project_employees (project_id, employee_id, role) VALUES (?, ?, ?)",
                (pid, eid, role)
            )
            conn.commit()
            flash("Сотрудник добавлен в проект", "success")
        except Exception as e:
            flash(str(e), "error")
        finally:
            conn.close()
    return redirect(url_for("project", pid=pid))


@app.route("/sync-bitrix", methods=["POST"])
def sync_bitrix():
    projs = sync_projects()
    emps_raw = sync_employees()  # если есть отдельная синхронизация сотрудников

    conn = get_conn()
    cur = conn.cursor()

    added_projects = 0
    updated_projects = 0
    added_employees = 0

    for p in projs:
        title = p.get("title", "Без названия")
        desc = p.get("description", "")
        resp_name = p.get("responsible", "")

        # 1. Находим или создаём проект
        cur.execute("SELECT id FROM projects WHERE name = ?", (title,))
        existing = cur.fetchone()
        project_id = None

        if existing:
            cur.execute("UPDATE projects SET description = ? WHERE id = ?", (desc, existing["id"]))
            project_id = existing["id"]
            updated_projects += 1
        else:
            cur.execute("INSERT INTO projects (name, description) VALUES (?, ?)", (title, desc))
            project_id = cur.lastrowid
            added_projects += 1

        # 2. Находим или создаём сотрудника (по имени)
        employee_id = None
        if resp_name:
            # Ищем по имени
            cur.execute("SELECT id FROM employees WHERE name = ?", (resp_name,))
            emp = cur.fetchone()
            if emp:
                employee_id = emp["id"]
            else:
                # Создаём, если нет
                cur.execute("INSERT INTO employees (name) VALUES (?)", (resp_name,))
                employee_id = cur.lastrowid
                added_employees += 1

        # 3. Назначаем ответственного (роль «руководитель»)
        if employee_id:
            # Сначала удаляем всех с ролью «руководитель» у этого проекта
            cur.execute(
                "DELETE FROM project_employees WHERE project_id = ? AND role = 'руководитель'",
                (project_id,)
            )
            # Добавляем текущего ответственного
            cur.execute(
                """
                INSERT OR IGNORE INTO project_employees (project_id, employee_id, role)
                VALUES (?, ?, ?)
                """,
                (project_id, employee_id, "руководитель")
            )

    # Если есть отдельная синхронизация сотрудников — можно добавить сюда
    # for e in emps_raw: ...

    conn.commit()
    conn.close()

    msg = []
    if added_projects:
        msg.append(f"добавлено проектов: {added_projects}")
    if updated_projects:
        msg.append(f"обновлено проектов: {updated_projects}")
    if added_employees:
        msg.append(f"создано сотрудников: {added_employees}")

    if msg:
        flash("Синхронизация: " + ", ".join(msg), "success")
    else:
        flash("Ничего не изменилось", "info")

    return redirect(url_for("index"))



if __name__ == "__main__":
    app.run(debug=True)
