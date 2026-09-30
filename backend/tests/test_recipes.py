from http import HTTPStatus
from unittest.mock import patch

from recipes.constants import MAX_COOKING_TIME, MAX_INGREDIENT_AMOUNT
from recipes.models import Recipe, RecipeIngredient
from tests.constants import (
    DEFAULT_PAGE_SIZE,
    INITIAL_AMOUNT,
    MISSING_ID,
    PAYLOAD_AMOUNT,
    RECIPE_IMAGE,
    SMALL_PAGE_SIZE,
    UPDATED_AMOUNT,
)
from tests.fixtures import FoodgramTestCase, RECIPE_DATA, api_url


class RecipeTests(FoodgramTestCase):
    def test_create_recipe_response_and_persistence(self):
        self.login()
        result = self.client.post(
            api_url('recipes-list'), self.payload(), format='json'
        )
        self.assertEqual(result.status_code, HTTPStatus.CREATED, result.data)
        self.assertEqual(result.data['author']['id'], self.author.pk)
        self.assertEqual(
            result.data['ingredients'][0]['amount'], PAYLOAD_AMOUNT
        )
        self.assertEqual(result.data['tags'][0]['slug'], self.tag.slug)
        self.assertFalse(result.data['is_favorited'])
        self.assertEqual(
            Recipe.objects.get(
                pk=result.data['id']
            ).ingredient_amounts.count(),
            1,
        )

    def test_invalid_recipe_payloads_do_not_write(self):
        self.login()
        invalid = [
            {'tags': []},
            {'tags': [self.tag.pk, self.tag.pk]},
            {'tags': [MISSING_ID]},
            {'ingredients': []},
            {'ingredients': [{'id': self.ingredient.pk, 'amount': 0}]},
            {'ingredients': [{'id': MISSING_ID, 'amount': 1}]},
            {'ingredients': [{'id': self.ingredient.pk, 'amount': 1}] * 2},
            {'cooking_time': 0},
            {'cooking_time': MAX_COOKING_TIME + 1},
            {'ingredients': [{
                'id': self.ingredient.pk,
                'amount': MAX_INGREDIENT_AMOUNT + 1,
            }]},
            {'name': ''},
            {'text': ''},
            {'image': 'broken'},
        ]
        for data in invalid:
            with self.subTest(data=data):
                response = self.client.post(
                    api_url('recipes-list'),
                    self.payload(**data),
                    format='json',
                )
                self.assertEqual(
                    response.status_code, HTTPStatus.BAD_REQUEST, response.data
                )
        self.assertEqual(Recipe.objects.count(), 1)

    def test_recipe_update_preserves_image_and_replaces_relations(self):
        self.login()
        data = self.payload(
            tags=[self.other_tag.pk],
            ingredients=[{'id': self.second.pk, 'amount': UPDATED_AMOUNT}],
        )
        data.pop('image')
        response = self.client.patch(
            api_url('recipes-detail', self.recipe.pk), data, format='json'
        )
        self.assertEqual(response.status_code, HTTPStatus.OK, response.data)
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.image.name, RECIPE_IMAGE)
        self.assertEqual(
            list(self.recipe.tags.values_list('pk', flat=True)),
            [self.other_tag.pk],
        )
        self.assertEqual(
            self.recipe.ingredient_amounts.get().ingredient_id, self.second.pk
        )

    def test_patch_required_fields_keep_existing_relations(self):
        self.login()
        response = self.client.patch(
            api_url('recipes-detail', self.recipe.pk),
            {'name': 'Другое'},
            format='json',
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            self.recipe.ingredient_amounts.get().amount, INITIAL_AMOUNT
        )
        self.assertEqual(self.recipe.tags.count(), 1)

    def test_recipe_changes_are_atomic(self):
        self.login()
        with patch(
            'api.serializers.RecipeWriteSerializer.save_ingredients',
            side_effect=RuntimeError('failure'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.patch(
                    api_url('recipes-detail', self.recipe.pk),
                    self.payload(),
                    format='json',
                )
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.name, RECIPE_DATA['name'])
        self.assertEqual(
            self.recipe.ingredient_amounts.get().amount, INITIAL_AMOUNT
        )

    def test_only_author_can_edit_or_delete(self):
        self.login(self.reader)
        endpoint = api_url('recipes-detail', self.recipe.pk)
        self.assertEqual(
            self.client.patch(
                endpoint, self.payload(), format='json'
            ).status_code,
            HTTPStatus.FORBIDDEN,
        )
        self.assertEqual(
            self.client.delete(endpoint).status_code, HTTPStatus.FORBIDDEN
        )
        self.login()
        self.assertEqual(
            self.client.delete(endpoint).status_code, HTTPStatus.NO_CONTENT
        )
        self.assertFalse(RecipeIngredient.objects.exists())

    def test_short_link_is_public_stable_and_redirects(self):
        endpoint = api_url('recipes-get-link', self.recipe.pk)
        link = self.client.get(endpoint).data['short-link']
        self.recipe.name = 'Новое название'
        self.recipe.save()
        self.assertEqual(self.client.get(endpoint).data['short-link'], link)
        response = self.client.get(
            api_url('recipe-short-link', self.recipe.pk)
        )
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, f'/recipes/{self.recipe.pk}')
        self.assertEqual(
            self.client.get(
                api_url('recipes-get-link', MISSING_ID)
            ).status_code,
            HTTPStatus.NOT_FOUND,
        )

    def test_pagination_order_and_tag_or_filter(self):
        for index in range(DEFAULT_PAGE_SIZE + 1):
            recipe = self.create_recipe(
                author=self.reader,
                name=f'Рецепт {index}',
            )
            recipe.tags.add(self.other_tag)
        self.recipe.tags.add(self.other_tag)
        response = self.client.get(api_url('recipes-list'))
        self.assertEqual(len(response.data['results']), DEFAULT_PAGE_SIZE)
        self.assertEqual(
            response.data['results'][0]['name'],
            f'Рецепт {DEFAULT_PAGE_SIZE}',
        )
        page = self.client.get(
            api_url('recipes-list', limit=SMALL_PAGE_SIZE, page=2)
        )
        self.assertEqual(len(page.data['results']), SMALL_PAGE_SIZE)
        response = self.client.get(
            api_url('recipes-list', tags=[self.tag.slug, self.other_tag.slug])
        )
        self.assertEqual(response.data['count'], DEFAULT_PAGE_SIZE + 2)
        response = self.client.get(
            api_url(
                'recipes-list',
                tags=self.other_tag.slug,
                author=self.author.pk,
            )
        )
        self.assertEqual(response.data['count'], 1)
