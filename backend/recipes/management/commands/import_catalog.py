import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from recipes.models import Ingredient, Tag


class Command(BaseCommand):
    help = (
        'Загрузить ингредиенты и теги из JSON; '
        'повторный запуск не создаёт дубликаты.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--data-dir', type=Path, default=settings.DATA_DIR)

    @transaction.atomic
    def handle(self, *args, **options):
        for filename, model, fields in [
            ('ingredients.json', Ingredient, ('name', 'measurement_unit')),
            ('tags.json', Tag, ('name', 'slug')),
        ]:
            path = options['data_dir'] / filename
            try:
                records = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(records, list):
                    raise ValueError('Ожидается JSON-массив.')
                objects = []
                for record in records:
                    obj = model(**{field: record[field] for field in fields})
                    obj.full_clean(
                        validate_unique=False, validate_constraints=False
                    )
                    objects.append(obj)
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                ValidationError,
            ) as error:
                raise CommandError(f'{path}: {error}') from error
            before = model.objects.count()
            model.objects.bulk_create(objects, ignore_conflicts=True)
            added = model.objects.count() - before
            self.stdout.write(f'{model._meta.verbose_name_plural}: +{added}')
