# Foodgram

Сервис рецептов: регистрация по email, публикация рецептов с изображениями,
теги и ингредиенты, подписки на авторов, избранное и скачиваемый список покупок.
Бэкенд реализован по `docs/openapi-schema.yml`, фронтенд — готовое React SPA.

**Локальный адрес:** http://localhost/
**Спецификация:** http://localhost/api/docs/
**Админка:** http://localhost/admin/
**Публичный адрес:** http://81.26.181.115:8080/

## Стек и структура

Python 3.12, Django 5.2, DRF, Djoser (обычные DRF-токены), django-filter,
PostgreSQL 16, Gunicorn, nginx, Docker Compose. Версии прямых Python-зависимостей
зафиксированы в `backend/requirements.txt`, фронтенда — в `frontend/package-lock.json`.

- `backend/users/` — пользователь и подписки.
- `backend/recipes/` — рецепты, справочники, состав, избранное, покупки, команды импорта.
- `backend/api/` — HTTP API, сериализаторы, фильтры, пагинация и права.
- `backend/tests/` — регрессионные проверки.
- `infra/` — локальный Compose, nginx и скрипт деплоя.
- `.github/workflows/main.yml` — проверки, публикация образов в Docker Hub и включаемый деплой.

## Запуск в Docker

Из корня репозитория, при установленном Docker с Compose:

```bash
cp .env.example .env
# Укажите случайный SECRET_KEY и собственный POSTGRES_PASSWORD в .env.
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml exec --user foodgram backend python manage.py import_catalog
docker compose -f infra/docker-compose.yml exec --user foodgram backend python manage.py createsuperuser
```

`frontend` копирует сборку в volume и завершается с кодом 0 — это штатное
поведение. `backend` при старте выполняет миграции и collectstatic, затем запускает
Gunicorn от пользователя foodgram. Перед этим entrypoint назначает владельца
volumes для статики и медиа. nginx ждёт готовности backend и завершения frontend. В контейнерах
используется PostgreSQL независимо от локального `USE_SQLITE` в `.env`.

Если порт 80 занят, установите `HTTP_PORT=8080` в `.env` и открывайте
http://localhost:8080/. При старом запуске заготовки остановите её nginx,
прежде чем запускать новый Compose. База и изображения хранятся в volumes.
`docker compose ... down` сохраняет данные; флаг `-v` удаляет их.

```bash
docker compose -f infra/docker-compose.yml ps -a
docker compose -f infra/docker-compose.yml logs --tail=100 backend
```

Для демонстрационных данных задайте временную переменную в своей оболочке:

```bash
read -s DEMO_PASSWORD
export DEMO_PASSWORD
docker compose -f infra/docker-compose.yml exec --user foodgram -e DEMO_PASSWORD backend python manage.py seed_demo
unset DEMO_PASSWORD
```

Команда создаёт `demo_admin@example.com` (суперпользователь),
`demo_anna@example.com`, `demo_ivan@example.com` и по рецепту каждого автора.
Вход на сайте — по email, в админке тоже по email. Повторный запуск не меняет
пароли и не дублирует рецепты существующих демоавторов.

## Локальная разработка на SQLite

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cp .env.example .env
# DEBUG=True, USE_SQLITE=True; задайте SECRET_KEY.
python backend/manage.py migrate
python backend/manage.py import_catalog
python backend/manage.py createsuperuser
python backend/manage.py runserver
```

API: http://127.0.0.1:8000/api/. Для всего приложения с React используйте Docker.
SQLite-поиск по русским названиям выполняет casefold в Python; PostgreSQL использует
регистронезависимый поиск по началу названия в БД.

## Проверки

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py makemigrations --check --dry-run
.venv/bin/python backend/manage.py test tests --verbosity 2
# Те же тесты на PostgreSQL контейнера:
docker compose -f infra/docker-compose.yml exec --user foodgram backend python manage.py test tests --verbosity 2
```

Тесты создают и удаляют отдельную тестовую БД. Проверяются права, статусы ответов,
регистрация и смена пароля, base64, обязательные поля PATCH, уникальность,
транзакции, фильтры, пагинация, подписки, короткая ссылка и суммирование покупок.

Коллекция Postman находится в `postman_collection/`. Запускайте её на отдельной
БД с загруженными ингредиентами и тремя тегами: она создаёт и меняет пользователей
и рецепты. В коллекции исправлено одно сравнение регистра в тесте поиска,
чтобы оно соответствовало заданию; остальные проверки сохранены.
Инструкции ручного запуска — в `postman_collection/README.md`.

## Поведение API

- Авторизация: `Authorization: Token <auth_token>`; JWT-маршруты не подключены.
- Пагинация: `page` и `limit`, по умолчанию 6, максимум 100 объектов.
- Рецепты: новые первыми, фильтры `author`, повторяющийся `tags=<slug>` (ИЛИ),
  `is_favorited=1`, `is_in_shopping_cart=1`. Значение 0 отключает личный фильтр.
- Изменять и удалять рецепт может только его автор.
- PATCH требует `ingredients`, `tags`, `name`, `text`, `cooking_time`, как указано
  в схеме; `image` можно не передавать, тогда старое изображение сохраняется.
- Состав рецепта сохраняется в транзакции; количества и время — целые числа ≥ 1.
- Подписки поддерживают `recipes_limit`; количество всех рецептов возвращается
  отдельно в `recipes_count`. Подписка на себя запрещена также ограничением БД.
- Повторное добавление/удаление отсутствующей связи — 400; неизвестный объект — 404.
- Список покупок — UTF-8 TXT, одинаковые ингредиенты суммируются SQL-запросом.
- `/s/<id>/` перенаправляет на рецепт, ссылка не меняется при редактировании.
- Аватар отсутствующего изображения возвращается как null; заглушку рисует React.

## Публикация

Образы публикуются в Docker Hub: `apavelkov/foodgram-backend`,
`apavelkov/foodgram-frontend`, `apavelkov/foodgram-nginx`.
На сервере с другими проектами задайте свободный `HTTP_PORT`, например 8080.

1. На сервере установите Docker/Compose. Откройте HTTP/HTTPS и настройте домен.
2. Создайте каталог `~/foodgram`; скопируйте туда `docker-compose.production.yml`,
   `infra/deploy.sh` (как `deploy.sh`) и подготовьте `.env` по примеру.
3. В серверном `.env` обязательно задайте случайный `SECRET_KEY`, `DEBUG=False`,
   пароль PostgreSQL, `ALLOWED_HOSTS=<домен>,127.0.0.1,localhost,backend`,
   `CSRF_TRUSTED_ORIGINS=https://<домен>`, `USE_SQLITE=False`.
4. Для TLS настройте внешний reverse proxy и сертификат. Внутренний nginx
   сейчас обслуживает HTTP. Не включайте `HTTPS_ENABLED=True`, пока цепочка
   proxy не передаёт корректный `X-Forwarded-Proto`: в TLS-терминирующем proxy
   он должен перезаписываться, а во внутреннем nginx — передаваться из доверенного
   proxy. Тогда включите `TRUST_PROXY=True`, `HTTPS_ENABLED=True` и закройте прямой
   внешний доступ к внутреннему порту. Для запуска только по HTTP оставьте оба False.
5. После push в main/master CI проверит код на PostgreSQL, соберёт React и
   опубликует три образа `<dockerhub-user>/foodgram-backend`, `-frontend`, `-nginx`
   с тегом SHA коммита и `latest`. Образы должны быть публичными либо
   сервер должен быть авторизован через `docker login` с правом чтения.
6. Запустите вручную из `~/foodgram`:

```bash
IMAGE_PREFIX=apavelkov/foodgram IMAGE_TAG=<commit-sha> sh deploy.sh
# Первое создание администратора:
docker compose -f docker-compose.production.yml exec --user foodgram backend python manage.py createsuperuser
```

Для автоматического деплоя добавьте GitHub environment `production`, secrets
`SSH_HOST`, `SSH_USER`, `SSH_KEY`, `SSH_KNOWN_HOSTS`, `DOCKERHUB_TOKEN` и repository variables
`DOCKERHUB_USERNAME=apavelkov`, `DEPLOY_ENABLED=true`. Проверенный SSH host key добавьте заранее; workflow
не отключает проверку ключа сервера. Серверный пользователь должен иметь доступ к Docker напрямую или через
уже настроенный sudo без пароля и доступ к каталогу `~/foodgram`. `.env` хранится только на сервере и не пересылается CI.

Перед обновлением делайте резервную копию БД и media:

```bash
docker compose -f docker-compose.production.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup.sql
```

Скрипт ждёт готовности сервисов, импортирует справочники и проверяет nginx.
Откат образа сам по себе не отменяет миграции: для несовместимых миграций нужен
проверенный план восстановления БД. После публикации замените строку публичного
адреса в начале этого README и проверьте регистрацию, рецепт, загрузку файла,
админку и сохранность данных после пересоздания контейнеров.
