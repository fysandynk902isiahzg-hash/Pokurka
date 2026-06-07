КОЛЕСО ПОКУРА — Telegram Bot для Railway

Команды:
/start — меню
/add Имя — добавить участника
/remove Имя — удалить участника
/list — список участников
/spin — крутить
/rating — рейтинг
/reset_rating — сбросить рейтинг, участники останутся

ВАЖНО:
Бот хранит отдельный список и рейтинг для каждого Telegram-чата.
Если добавить бота в группу, список будет общий именно для этой группы.

ЗАПУСК НА RAILWAY:
1. Создай бота через @BotFather и скопируй BOT_TOKEN.
2. Создай GitHub-репозиторий.
3. Загрузи в репозиторий ВСЕ файлы из этой папки:
   main.py
   requirements.txt
   Procfile
   railway.json
   runtime.txt
4. Railway → New Project → Deploy from GitHub repo.
5. Variables → Add variable:
   BOT_TOKEN = токен от BotFather
6. Нажми Redeploy/Deploy.
7. В логах должно быть:
   DB initialized
   Bot started: @username
   Health server started on port ...

Если бот не отвечает:
- Проверь, что токен называется строго BOT_TOKEN.
- Проверь, что бот не запущен в другом месте одновременно.
- Напиши боту /start лично, не только в группе.
- Если бот в группе не видит команды, отключи Privacy Mode у @BotFather:
  /setprivacy → выбери бота → Disable
