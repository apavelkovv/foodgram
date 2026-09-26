set -eu
if [ "$(id -u)" = "0" ]; then
    chown -R foodgram:foodgram /app/media /app/collected_static
    exec gosu foodgram sh "$0" "$@"
fi
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec "$@"
