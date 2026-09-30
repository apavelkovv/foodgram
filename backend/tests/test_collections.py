from http import HTTPStatus

from recipes.models import Favorite, RecipeIngredient, ShoppingCart
from tests.constants import (
    INITIAL_AMOUNT,
    MISSING_ID,
    PAYLOAD_AMOUNT,
    SMALL_PAGE_SIZE,
)
from tests.fixtures import FoodgramTestCase, api_url


class CollectionTests(FoodgramTestCase):
    def test_collections_status_codes_isolation_and_zero_filter(self):
        for action, model, flag in [
            ('recipes-favorite', Favorite, 'is_favorited'),
            ('recipes-shopping-cart', ShoppingCart, 'is_in_shopping_cart'),
        ]:
            with self.subTest(action=action):
                self.login(self.reader)
                endpoint = api_url(action, self.recipe.pk)
                self.assertEqual(
                    self.client.delete(endpoint).status_code,
                    HTTPStatus.BAD_REQUEST,
                )
                self.assertEqual(
                    self.client.post(endpoint).status_code, HTTPStatus.CREATED
                )
                self.assertEqual(
                    self.client.post(endpoint).status_code,
                    HTTPStatus.BAD_REQUEST,
                )
                self.assertEqual(
                    self.client.delete(
                        api_url(action, MISSING_ID)
                    ).status_code,
                    HTTPStatus.NOT_FOUND,
                )
                self.assertTrue(
                    self.client.get(
                        api_url('recipes-detail', self.recipe.pk)
                    ).data[flag]
                )
                self.assertEqual(
                    self.client.get(
                        api_url('recipes-list', **{flag: 1})
                    ).data['count'],
                    1,
                )
                self.login()
                self.assertEqual(
                    self.client.get(
                        api_url('recipes-list', **{flag: 1})
                    ).data['count'],
                    0,
                )
                self.assertEqual(
                    self.client.get(
                        api_url('recipes-list', **{flag: 0})
                    ).data['count'],
                    1,
                )
                self.assertEqual(model.objects.count(), 1)
                self.login(self.reader)
                self.assertEqual(
                    self.client.delete(endpoint).status_code,
                    HTTPStatus.NO_CONTENT,
                )
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(
                api_url('recipes-list', is_favorited=1)
            ).data['count'],
            0,
        )

    def test_shopping_file_sums_only_current_users_ingredients(self):
        other = self.create_recipe(
            author=self.reader,
            name='Второй',
        )
        RecipeIngredient.objects.create(
            recipe=other, ingredient=self.ingredient, amount=PAYLOAD_AMOUNT
        )
        ShoppingCart.objects.create(user=self.reader, recipe=self.recipe)
        ShoppingCart.objects.create(user=self.reader, recipe=other)
        ShoppingCart.objects.create(user=self.author, recipe=self.recipe)
        self.login(self.reader)
        response = self.client.get(api_url('recipes-download-shopping-cart'))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn('attachment;', response['Content-Disposition'])
        ingredient_label = (
            f'{self.ingredient.name} ({self.ingredient.measurement_unit})'
        )
        expected = f'{ingredient_label} — {INITIAL_AMOUNT + PAYLOAD_AMOUNT}'
        self.assertEqual(response.content.decode().count(expected), 1)
        self.login()
        self.assertIn(
            f'{ingredient_label} — {INITIAL_AMOUNT}',
            self.client.get(
                api_url('recipes-download-shopping-cart')
            ).content.decode(),
        )

    def test_favorite_tag_filter_with_pagination(self):
        self.login(self.reader)
        for index in range(3):
            recipe = self.create_recipe(
                author=self.author, name=f'Избранное {index}',
            )
            recipe.tags.add(self.tag)
            Favorite.objects.create(user=self.reader, recipe=recipe)
        filters = {
            'is_favorited': 1, 'tags': self.tag.slug,
            'author': self.author.pk, 'limit': SMALL_PAGE_SIZE,
        }
        url = api_url('recipes-list', **filters)
        response = self.client.get(url)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(
            [item['name'] for item in response.data['results']],
            ['Избранное 2', 'Избранное 1'],
        )
        page = self.client.get(api_url('recipes-list', **filters, page=2))
        self.assertEqual(page.data['results'][0]['name'], 'Избранное 0')
        self.assertEqual(
            self.client.get(api_url(
                'recipes-list', **{**filters, 'tags': self.other_tag.slug}
            )).data['count'],
            0,
        )
