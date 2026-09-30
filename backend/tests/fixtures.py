import base64
import tempfile
from io import BytesIO
from urllib.parse import urlencode

from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from recipes.models import Ingredient, Recipe, RecipeIngredient, Tag, User
from tests.constants import (
    AUTHOR_PASSWORD,
    IMAGE_COLOR,
    IMAGE_DATA_PREFIX,
    IMAGE_FORMAT,
    IMAGE_SIZE,
    INITIAL_AMOUNT,
    PAYLOAD_AMOUNT,
    READER_PASSWORD,
    RECIPE_IMAGE,
    REGISTRATION_PASSWORD,
)

AUTHOR_DATA = {
    'username': 'author',
    'email': 'author@example.com',
    'password': AUTHOR_PASSWORD,
    'first_name': 'Анна',
    'last_name': 'Повар',
}
READER_DATA = {
    'username': 'reader',
    'email': 'reader@example.com',
    'password': READER_PASSWORD,
    'first_name': 'Иван',
    'last_name': 'Повар',
}
REGISTRATION_DATA = {
    'email': 'new@example.com',
    'username': 'new+chef',
    'first_name': 'Новый',
    'last_name': 'Повар',
    'password': REGISTRATION_PASSWORD,
}
BREAKFAST_DATA = {'name': 'Завтрак', 'slug': 'breakfast'}
LUNCH_DATA = {'name': 'Обед', 'slug': 'lunch'}
SUGAR_DATA = {'name': 'Сахар', 'measurement_unit': 'г'}
POWDERED_SUGAR_DATA = {'name': 'Сахарная пудра', 'measurement_unit': 'г'}
BROWN_SUGAR_DATA = {'name': 'Коричневый сахар', 'measurement_unit': 'г'}
RECIPE_DATA = {
    'name': 'Первый рецепт',
    'text': 'Приготовьте',
    'cooking_time': 10,
    'image': RECIPE_IMAGE,
}
RECIPE_PAYLOAD_DATA = {
    'name': 'Новый рецепт',
    'text': 'Смешайте ингредиенты',
    'cooking_time': 20,
}
INVALID_IMAGES = (
    'bad',
    'data:image/png;base64,@@@',
    'data:image/png;base64,aGVsbG8=',
    '',
)


def api_url(route_name, *args, **query):
    url = reverse(route_name, args=args or None)
    return f'{url}?{urlencode(query, doseq=True)}' if query else url


def image_data():
    stream = BytesIO()
    Image.new('RGB', IMAGE_SIZE, IMAGE_COLOR).save(stream, IMAGE_FORMAT)
    return IMAGE_DATA_PREFIX + base64.b64encode(stream.getvalue()).decode()


class FoodgramTestCase(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        media = tempfile.TemporaryDirectory()
        cls.addClassCleanup(media.cleanup)
        settings_override = override_settings(MEDIA_ROOT=media.name)
        settings_override.enable()
        cls.addClassCleanup(settings_override.disable)

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(**AUTHOR_DATA)
        cls.reader = User.objects.create_user(**READER_DATA)
        cls.tag = Tag.objects.create(**BREAKFAST_DATA)
        cls.other_tag = Tag.objects.create(**LUNCH_DATA)
        cls.ingredient = Ingredient.objects.create(**SUGAR_DATA)
        cls.second = Ingredient.objects.create(**POWDERED_SUGAR_DATA)
        cls.recipe = Recipe.objects.create(author=cls.author, **RECIPE_DATA)
        cls.recipe.tags.add(cls.tag)
        RecipeIngredient.objects.create(
            recipe=cls.recipe, ingredient=cls.ingredient, amount=INITIAL_AMOUNT
        )

    def payload(self, **overrides):
        return {
            **RECIPE_PAYLOAD_DATA,
            'image': image_data(),
            'tags': [self.tag.pk],
            'ingredients': [{
                'id': self.ingredient.pk, 'amount': PAYLOAD_AMOUNT,
            }],
            **overrides,
        }

    def create_recipe(self, *, author=None, tags=(), **overrides):
        recipe = Recipe.objects.create(
            author=author or self.author, **{**RECIPE_DATA, **overrides}
        )
        recipe.tags.set(tags)
        return recipe

    def login(self, user=None):
        self.client.force_authenticate(user=user or self.author)
