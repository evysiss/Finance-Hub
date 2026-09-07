import requests
from config import BITRIX24_WEBHOOK_URL

# bitrix24.py

BITRIX24_WEBHOOK_URL = ""  # пока пусто, будет заглушка

def sync_projects():
    """
    Возвращает проекты. Если вебхук не задан — тестовые данные.
    Поле responsible — это ИМЯ сотрудника (для поиска в БД).
    """
    if not BITRIX24_WEBHOOK_URL:
        return [
            {
                "title": "Внедрение ERP-системы",
                "description": "Настройка и интеграция ERP для производственного предприятия",
                "responsible": "Анна Петрова"   # ищем по этому имени
            },
            {
                "title": "Миграция инфраструктуры в облако",
                "description": "Перенос серверов и сервисов в Yandex Cloud",
                "responsible": "Дмитрий Волков"  # ищем по этому имени
            }
        ]

    # Здесь будет реальный запрос к Bitrix24 REST API
    try:
        import requests
        resp = requests.get(BITRIX24_WEBHOOK_URL + "/task.item.list", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("result", [])
    except Exception:
        pass
    return []


def sync_employees():
    """Заглушка: получение пользователей из Bitrix24."""
    if not BITRIX24_WEBHOOK_URL:
        return []

    try:
        resp = requests.get(BITRIX24_WEBHOOK_URL + "/user.user.list", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("result", [])
    except Exception:
        pass
    return []
