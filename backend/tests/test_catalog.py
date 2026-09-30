from io import StringIO

from django.core.management import call_command

from recipes.models import Ingredient, Tag
from tests.fixtures import BROWN_SUGAR_DATA, FoodgramTestCase, api_url


class CatalogTests(FoodgramTestCase):
    def test_ingredient_search_cyrillic_prefix(self):
        Ingredient.objects.create(**BROWN_SUGAR_DATA)
        response = self.client.get(
            api_url('ingredients-list', name=self.ingredient.name[:3].upper())
        )
        self.assertEqual(
            {item['name'] for item in response.data},
            {self.ingredient.name, self.second.name},
        )

    def test_import_is_idempotent(self):
        output = StringIO()
        call_command('import_catalog', stdout=output)
        counts = Ingredient.objects.count(), Tag.objects.count()
        call_command('import_catalog', stdout=output)
        self.assertEqual(
            (Ingredient.objects.count(), Tag.objects.count()), counts
        )
