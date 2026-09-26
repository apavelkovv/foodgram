import base64
import tempfile
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from users.models import Subscription

User = get_user_model()


def image_data():
    stream = BytesIO()
    Image.new('RGB', (8, 8), 'orange').save(stream, 'PNG')
    return 'data:image/png;base64,'
    +base64.b64encode(stream.getvalue()).decode()


class FoodgramTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = tempfile.TemporaryDirectory()
        cls.settings_override = override_settings(MEDIA_ROOT=cls.media.name)
        cls.settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.settings_override.disable()
        cls.media.cleanup()
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username='author',
            email='author@example.com',
            password='Secure-Recipe-486',
            first_name='Анна',
            last_name='Повар',
        )
        cls.reader = User.objects.create_user(
            username='reader',
            email='reader@example.com',
            password='Secure-Reader-918',
            first_name='Иван',
            last_name='Повар',
        )
        cls.tag = Tag.objects.create(name='Завтрак', slug='breakfast')
        cls.other_tag = Tag.objects.create(name='Обед', slug='lunch')
        cls.ingredient = Ingredient.objects.create(
            name='Сахар', measurement_unit='г'
        )
        cls.second = Ingredient.objects.create(
            name='Сахарная пудра', measurement_unit='г'
        )
        cls.recipe = Recipe.objects.create(
            author=cls.author,
            name='Первый рецепт',
            text='Приготовьте',
            cooking_time=10,
            image='recipes/test.png',
        )
        cls.recipe.tags.add(cls.tag)
        RecipeIngredient.objects.create(
            recipe=cls.recipe, ingredient=cls.ingredient, amount=5
        )

    def payload(self, **overrides):
        return dict(
            {
                'name': 'Новый рецепт',
                'text': 'Смешайте ингредиенты',
                'image': image_data(),
                'cooking_time': 20,
                'tags': [self.tag.pk],
                'ingredients': [{'id': self.ingredient.pk, 'amount': 10}],
            },
            **overrides,
        )

    def login(self, user=None):
        self.client.force_authenticate(user=user or self.author)

    def test_registration_and_token_lifecycle(self):
        data = dict(
            email='new@example.com',
            username='new+chef',
            first_name='Новый',
            last_name='Повар',
            password='Strong-Kitchen-783',
        )
        result = self.client.post('/api/users/', data)
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(
            set(result.data),
            {'id', 'email', 'username', 'first_name', 'last_name'},
        )
        self.assertTrue(
            User.objects.get(pk=result.data['id']).check_password(
                data['password']
            )
        )
        result = self.client.post(
            '/api/auth/token/login/',
            {'email': data['email'], 'password': data['password']},
        )
        self.assertEqual(result.status_code, 200)
        self.client.credentials(
            HTTP_AUTHORIZATION='Token ' + result.data['auth_token']
        )
        self.assertEqual(
            self.client.get('/api/users/me/').data['email'], data['email']
        )
        self.assertEqual(
            self.client.post('/api/auth/token/logout/').status_code, 204
        )
        self.assertEqual(self.client.get('/api/users/me/').status_code, 401)

    def test_registration_requires_all_fields_and_unique_identity(self):
        data = dict(
            email='new@example.com',
            username='new',
            first_name='Новый',
            last_name='Повар',
            password='Strong-Kitchen-783',
        )
        for field in data:
            with self.subTest(field=field):
                incomplete = data.copy()
                incomplete.pop(field)
                self.assertEqual(
                    self.client.post('/api/users/', incomplete).status_code,
                    400,
                )
        for field in ('username', 'email'):
            duplicate = dict(data, **{field: getattr(self.author, field)})
            self.assertEqual(
                self.client.post('/api/users/', duplicate).status_code, 400
            )

    def test_public_reads_and_protected_actions(self):
        for path in (
            'users/',
            f'users/{self.author.pk}/',
            'recipes/',
            'tags/',
            'ingredients/',
        ):
            self.assertEqual(self.client.get('/api/' + path).status_code, 200)
        for path in (
            'users/me/',
            'users/subscriptions/',
            'recipes/download_shopping_cart/',
        ):
            self.assertEqual(self.client.get('/api/' + path).status_code, 401)
        for path in (
            f'users/{self.author.pk}/subscribe/',
            f'recipes/{self.recipe.pk}/favorite/',
            f'recipes/{self.recipe.pk}/shopping_cart/',
            'recipes/',
        ):
            self.assertEqual(
                self.client.post(
                    '/api/' + path, {}, format='json'
                ).status_code,
                401,
            )

    def test_change_password(self):
        self.login()
        endpoint = '/api/users/set_password/'
        self.assertEqual(
            self.client.post(
                endpoint,
                {
                    'current_password': 'wrong',
                    'new_password': 'Strong-Changed-937',
                },
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                endpoint,
                {
                    'current_password': 'Secure-Recipe-486',
                    'new_password': 'Strong-Changed-937',
                },
            ).status_code,
            204,
        )
        self.author.refresh_from_db()
        self.assertTrue(self.author.check_password('Strong-Changed-937'))

    def test_avatar_validation_update_and_delete(self):
        self.login()
        for bad in (
            'bad',
            'data:image/png;base64,@@@',
            'data:image/png;base64,aGVsbG8=',
            '',
        ):
            self.assertEqual(
                self.client.put(
                    '/api/users/me/avatar/', {'avatar': bad}, format='json'
                ).status_code,
                400,
            )
        response = self.client.put(
            '/api/users/me/avatar/', {'avatar': image_data()}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(
            response.data['avatar'].startswith('http://testserver/media/')
        )
        self.assertEqual(
            self.client.delete('/api/users/me/avatar/').status_code, 204
        )
        self.assertIsNone(self.client.get('/api/users/me/').data['avatar'])

    def test_create_recipe_response_and_persistence(self):
        self.login()
        result = self.client.post(
            '/api/recipes/', self.payload(), format='json'
        )
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(result.data['author']['id'], self.author.pk)
        self.assertEqual(result.data['ingredients'][0]['amount'], 10)
        self.assertEqual(result.data['tags'][0]['slug'], 'breakfast')
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
            dict(tags=[]),
            dict(tags=[self.tag.pk, self.tag.pk]),
            dict(tags=[999999]),
            dict(ingredients=[]),
            dict(ingredients=[{'id': self.ingredient.pk, 'amount': 0}]),
            dict(ingredients=[{'id': 999999, 'amount': 1}]),
            dict(ingredients=[{'id': self.ingredient.pk, 'amount': 1}] * 2),
            dict(cooking_time=0),
            dict(name=''),
            dict(text=''),
            dict(image='broken'),
        ]
        for data in invalid:
            with self.subTest(data=data):
                response = self.client.post(
                    '/api/recipes/', self.payload(**data), format='json'
                )
                self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Recipe.objects.count(), 1)

    def test_recipe_update_preserves_image_and_replaces_relations(self):
        self.login()
        data = self.payload(
            tags=[self.other_tag.pk],
            ingredients=[{'id': self.second.pk, 'amount': 7}],
        )
        data.pop('image')
        response = self.client.patch(
            f'/api/recipes/{self.recipe.pk}/', data, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.image.name, 'recipes/test.png')
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
            f'/api/recipes/{self.recipe.pk}/',
            {'name': 'Другое'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.recipe.ingredient_amounts.get().amount, 5)
        self.assertEqual(self.recipe.tags.count(), 1)

    def test_recipe_changes_are_atomic(self):
        self.login()
        with patch(
            'api.serializers.RecipeWriteSerializer.save_ingredients',
            side_effect=RuntimeError('failure'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.patch(
                    f'/api/recipes/{self.recipe.pk}/',
                    self.payload(),
                    format='json',
                )
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.name, 'Первый рецепт')
        self.assertEqual(self.recipe.ingredient_amounts.get().amount, 5)

    def test_only_author_can_edit_or_delete(self):
        self.login(self.reader)
        endpoint = f'/api/recipes/{self.recipe.pk}/'
        self.assertEqual(
            self.client.patch(
                endpoint, self.payload(), format='json'
            ).status_code,
            403,
        )
        self.assertEqual(self.client.delete(endpoint).status_code, 403)
        self.login()
        self.assertEqual(self.client.delete(endpoint).status_code, 204)
        self.assertFalse(RecipeIngredient.objects.exists())

    def test_short_link_is_public_stable_and_redirects(self):
        endpoint = f'/api/recipes/{self.recipe.pk}/get-link/'
        link = self.client.get(endpoint).data['short-link']
        self.recipe.name = 'Новое название'
        self.recipe.save()
        self.assertEqual(self.client.get(endpoint).data['short-link'], link)
        response = self.client.get(f'/s/{self.recipe.pk}/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/recipes/{self.recipe.pk}')
        self.assertEqual(
            self.client.get('/api/recipes/999999/get-link/').status_code, 404
        )

    def test_pagination_order_and_tag_or_filter(self):
        for index in range(7):
            recipe = Recipe.objects.create(
                author=self.reader,
                name=f'Рецепт {index}',
                text='Текст',
                cooking_time=1,
                image='test.png',
            )
            recipe.tags.add(self.other_tag)
        self.recipe.tags.add(self.other_tag)
        response = self.client.get('/api/recipes/')
        self.assertEqual(len(response.data['results']), 6)
        self.assertEqual(response.data['results'][0]['name'], 'Рецепт 6')
        self.assertEqual(
            len(
                self.client.get('/api/recipes/?limit=2&page=2').data['results']
            ),
            2,
        )
        response = self.client.get('/api/recipes/?tags=breakfast&tags=lunch')
        self.assertEqual(response.data['count'], 8)
        response = self.client.get(
            f'/api/recipes/?tags=lunch&author={self.author.pk}'
        )
        self.assertEqual(response.data['count'], 1)

    def test_ingredient_search_cyrillic_prefix(self):
        Ingredient.objects.create(
            name='Коричневый сахар', measurement_unit='г'
        )
        response = self.client.get('/api/ingredients/?name=САХ')
        self.assertEqual(
            {item['name'] for item in response.data},
            {'Сахар', 'Сахарная пудра'},
        )

    def test_collections_status_codes_isolation_and_zero_filter(self):
        for action, model in [
            ('favorite', Favorite),
            ('shopping_cart', ShoppingCart),
        ]:
            with self.subTest(action=action):
                self.login(self.reader)
                endpoint = f'/api/recipes/{self.recipe.pk}/{action}/'
                self.assertEqual(self.client.delete(endpoint).status_code, 400)
                self.assertEqual(self.client.post(endpoint).status_code, 201)
                self.assertEqual(self.client.post(endpoint).status_code, 400)
                self.assertEqual(
                    self.client.delete(
                        f'/api/recipes/999999/{action}/'
                    ).status_code,
                    404,
                )
                flag = (
                    'is_favorited'
                    if action == 'favorite'
                    else 'is_in_shopping_cart'
                )
                self.assertTrue(
                    self.client.get(f'/api/recipes/{self.recipe.pk}/').data[
                        flag
                    ]
                )
                self.assertEqual(
                    self.client.get(f'/api/recipes/?{flag}=1').data['count'], 1
                )
                self.login()
                self.assertEqual(
                    self.client.get(f'/api/recipes/?{flag}=1').data['count'], 0
                )
                self.assertEqual(
                    self.client.get(f'/api/recipes/?{flag}=0').data['count'], 1
                )
                self.assertEqual(model.objects.count(), 1)
                self.login(self.reader)
                self.assertEqual(self.client.delete(endpoint).status_code, 204)
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get('/api/recipes/?is_favorited=1').data['count'], 0
        )

    def test_shopping_file_sums_only_current_users_ingredients(self):
        other = Recipe.objects.create(
            author=self.reader,
            name='Второй',
            text='Текст',
            cooking_time=1,
            image='test.png',
        )
        RecipeIngredient.objects.create(
            recipe=other, ingredient=self.ingredient, amount=10
        )
        ShoppingCart.objects.create(user=self.reader, recipe=self.recipe)
        ShoppingCart.objects.create(user=self.reader, recipe=other)
        ShoppingCart.objects.create(user=self.author, recipe=self.recipe)
        self.login(self.reader)
        response = self.client.get('/api/recipes/download_shopping_cart/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response.content.decode().count('Сахар (г) — 15'), 1)
        self.login()
        self.assertIn(
            'Сахар (г) — 5',
            self.client.get(
                '/api/recipes/download_shopping_cart/'
            ).content.decode(),
        )

    def test_subscription_lifecycle_and_limits(self):
        self.login(self.reader)
        endpoint = f'/api/users/{self.author.pk}/subscribe/'
        self.assertEqual(self.client.delete(endpoint).status_code, 400)
        self.assertEqual(
            self.client.post(
                f'/api/users/{self.reader.pk}/subscribe/'
            ).status_code,
            400,
        )
        response = self.client.post(endpoint + '?recipes_limit=0')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['recipes'], [])
        self.assertEqual(response.data['recipes_count'], 1)
        self.assertTrue(response.data['is_subscribed'])
        self.assertEqual(self.client.post(endpoint).status_code, 400)
        self.assertEqual(
            self.client.get('/api/users/subscriptions/?recipes_limit=1').data[
                'count'
            ],
            1,
        )
        for invalid in ('-1', 'abc', '1.5'):
            self.assertEqual(
                self.client.get(
                    '/api/users/subscriptions/?recipes_limit=' + invalid
                ).status_code,
                400,
            )
        self.login()
        self.assertEqual(
            self.client.get('/api/users/subscriptions/').data['count'], 0
        )
        self.login(self.reader)
        self.assertEqual(self.client.delete(endpoint).status_code, 204)

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
        with self.assertNumQueries(5):
            self.client.get('/api/recipes/')
        for index in range(5):
            recipe = Recipe.objects.create(
                author=self.reader,
                name=str(index),
                cooking_time=1,
                image='test.png',
                text='Текст',
            )
            recipe.tags.add(self.tag)
            RecipeIngredient.objects.create(
                recipe=recipe, ingredient=self.ingredient, amount=1
            )
        with self.assertNumQueries(5):
            self.client.get('/api/recipes/')

    def test_import_is_idempotent(self):
        from io import StringIO

        output = StringIO()
        call_command('import_catalog', stdout=output)
        counts = Ingredient.objects.count(), Tag.objects.count()
        call_command('import_catalog', stdout=output)
        self.assertEqual(
            (Ingredient.objects.count(), Tag.objects.count()), counts
        )

    def test_admin_recipe_pages(self):
        self.author.is_staff = self.author.is_superuser = True
        self.author.save()
        self.client.force_login(self.author)
        for path in (
            '/admin/recipes/recipe/',
            f'/admin/recipes/recipe/{self.recipe.pk}/change/',
            '/admin/users/user/',
        ):
            self.assertEqual(self.client.get(path).status_code, 200)
