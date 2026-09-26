import os
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageDraw

from recipes.models import Ingredient, Recipe, RecipeIngredient, Tag

User = get_user_model()


class Command(BaseCommand):
    help = 'Создать трёх демонстрационных авторов и рецепты. '
    'Пароль задаётся DEMO_PASSWORD.'

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.getenv('DEMO_PASSWORD')
        if not password:
            raise CommandError(
                'Задайте DEMO_PASSWORD; существующие пароли не меняются.'
            )
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError('; '.join(error.messages)) from error
        call_command('import_catalog')
        ingredient, _ = Ingredient.objects.get_or_create(
            name='Яйцо куриное', measurement_unit='шт.'
        )
        salt, _ = Ingredient.objects.get_or_create(
            name='Соль', measurement_unit='г'
        )
        tag = Tag.objects.get(slug='breakfast')
        for username, first_name, staff, title, color in [
            (
                'demo_admin',
                'Администратор',
                True,
                'Омлет с зеленью',
                '#ecb84e',
            ),
            ('demo_anna', 'Анна', False, 'Яйца на завтрак', '#e38856'),
            ('demo_ivan', 'Иван', False, 'Воздушный омлет', '#97b87a'),
        ]:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@example.com',
                    'first_name': first_name,
                    'last_name': 'Демо',
                    'is_staff': staff,
                    'is_superuser': staff,
                },
            )
            if created:
                user.set_password(password)
                user.save()
            if user.recipes.exists():
                continue
            picture = Image.new('RGB', (800, 600), color)
            drawing = ImageDraw.Draw(picture)
            drawing.ellipse((180, 80, 620, 520), fill='#fff9e7')
            drawing.ellipse((300, 200, 500, 400), fill='#eebd39')
            stream = BytesIO()
            picture.save(stream, format='PNG')
            recipe = Recipe.objects.create(
                author=user,
                name=title,
                text=(
                    'Взбейте яйца с солью. '
                    'Готовьте на сковороде до готовности.'
                ),
                cooking_time=10,
                image=ContentFile(stream.getvalue(), name=f'{username}.png'),
            )
            recipe.tags.add(tag)
            RecipeIngredient.objects.bulk_create(
                [
                    RecipeIngredient(
                        recipe=recipe, ingredient=ingredient, amount=2
                    ),
                    RecipeIngredient(recipe=recipe, ingredient=salt, amount=1),
                ]
            )
        self.stdout.write(
            self.style.SUCCESS(
                'Демо: demo_admin, demo_anna, demo_ivan'
                '(email: <username>@example.com).'
            )
        )
