# Finance-Hub
Веб приложение для оценки экономической деятельности проектов

Для запуска выполнить следующие команды:
bash
pip install -r requirements.txt
python app.py

Откроется на http://localhost:5000. 

Для интеграции с Bitrix24 укажите URL входящего вебхука в config.py или через переменную окружения:
bash
export BITRIX24_WEBHOOK_URL="https://your-portal.bitrix24.ru/rest/1/yourcode/"
