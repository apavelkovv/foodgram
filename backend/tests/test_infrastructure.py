from http import HTTPStatus
from unittest.mock import patch

from django.db import DatabaseError, IntegrityError, transaction
from django.test import override_settings

from recipes.models import Favorite, Recipe, RecipeIngredient
from tests.constants import (
    DEFAULT_PAGE_SIZE,
    HEALTH_URL,
    LIVENESS_URL,
    READINESS_URL,
    RECIPE_LIST_QUERY_COUNT,
)
from tests.fixtures import FoodgramTestCase, api_url
from users.models import Subscription


class InfrastructureTests(FoodgramTestCase):
    def test_database_constraints(self):
        for create in (
            lambda: Subscription.objects.create(
                subscriber=self.author, author=self.author
            ),
            lambda: RecipeIngredient.objects.create(
                recipe=self.recipe, ingredient=self.second, amount=0
            ),
            lambda: Recipe.objects.create(
                author=self.author, name='Bad', cooking_time=0
            ),
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                create()
        Favorite.objects.create(user=self.reader, recipe=self.recipe)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Favorite.objects.create(user=self.reader, recipe=self.recipe)

    def test_recipe_list_query_count_does_not_grow(self):
        self.login(self.reader)
        with self.assertNumQueries(RECIPE_LIST_QUERY_COUNT):
            self.client.get(api_url('recipes-list'))
        for index in range(DEFAULT_PAGE_SIZE - 1):
            recipe = self.create_recipe(
                author=self.reader,
                name=str(index),
            )
            recipe.tags.add(self.tag)
            RecipeIngredient.objects.create(
                recipe=recipe, ingredient=self.ingredient, amount=1
            )
        with self.assertNumQueries(RECIPE_LIST_QUERY_COUNT):
            self.client.get(api_url('recipes-list'))

    def test_admin_recipe_pages(self):
        self.author.is_staff = self.author.is_superuser = True
        self.author.save()
        self.client.force_login(self.author)
        for path in (
            api_url('admin:recipes_recipe_changelist'),
            api_url('admin:recipes_recipe_change', self.recipe.pk),
            api_url('admin:users_user_changelist'),
        ):
            self.assertEqual(self.client.get(path).status_code, HTTPStatus.OK)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_https_proxy_links_and_health(self):
        response = self.client.get(
            api_url('recipes-detail', self.recipe.pk),
            HTTP_X_FORWARDED_PROTO='https',
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.data['image'].startswith('https://'))
        response = self.client.get(
            api_url('recipes-get-link', self.recipe.pk),
            HTTP_X_FORWARDED_PROTO='https',
        )
        self.assertTrue(response.data['short-link'].startswith('https://'))
        self.assertEqual(
            self.client.get(HEALTH_URL).status_code, HTTPStatus.OK
        )
        self.assertEqual(
            self.client.get(LIVENESS_URL).status_code, HTTPStatus.OK
        )
        self.assertEqual(
            self.client.get(READINESS_URL).status_code, HTTPStatus.OK
        )
        with patch('api.views.connection.cursor', side_effect=DatabaseError):
            self.assertEqual(
                self.client.get(LIVENESS_URL).status_code, HTTPStatus.OK
            )
            self.assertEqual(
                self.client.get(READINESS_URL).status_code,
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
        self.assertEqual(
            self.client.get(api_url('recipes-list')).status_code,
            HTTPStatus.MOVED_PERMANENTLY,
        )
