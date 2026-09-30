from http import HTTPStatus

from recipes.models import User
from tests.constants import (
    AUTHOR_PASSWORD,
    CHANGED_PASSWORD,
    INVALID_PASSWORD,
    MEDIA_URL_PREFIX,
)
from tests.fixtures import (
    FoodgramTestCase,
    INVALID_IMAGES,
    REGISTRATION_DATA,
    api_url,
    image_data,
)


class UserTests(FoodgramTestCase):
    def test_registration_and_token_lifecycle(self):
        data = REGISTRATION_DATA.copy()
        result = self.client.post(api_url('users-list'), data)
        self.assertEqual(result.status_code, HTTPStatus.CREATED, result.data)
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
            api_url('login'),
            {'email': data['email'], 'password': data['password']},
        )
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.client.credentials(
            HTTP_AUTHORIZATION='Token ' + result.data['auth_token']
        )
        self.assertEqual(
            self.client.get(api_url('users-me')).data['email'], data['email']
        )
        self.assertEqual(
            self.client.post(api_url('logout')).status_code,
            HTTPStatus.NO_CONTENT,
        )
        self.assertEqual(
            self.client.get(api_url('users-me')).status_code,
            HTTPStatus.UNAUTHORIZED,
        )

    def test_registration_requires_all_fields_and_unique_identity(self):
        data = REGISTRATION_DATA.copy()
        for field in data:
            with self.subTest(field=field):
                incomplete = data.copy()
                incomplete.pop(field)
                self.assertEqual(
                    self.client.post(
                        api_url('users-list'), incomplete
                    ).status_code,
                    HTTPStatus.BAD_REQUEST,
                )
        for field in ('username', 'email'):
            duplicate = {**data, field: getattr(self.author, field)}
            self.assertEqual(
                self.client.post(api_url('users-list'), duplicate).status_code,
                HTTPStatus.BAD_REQUEST,
            )

    def test_public_reads_and_protected_actions(self):
        for url in (
            api_url('users-list'),
            api_url('users-detail', self.author.pk),
            api_url('recipes-list'),
            api_url('tags-list'),
            api_url('ingredients-list'),
        ):
            self.assertEqual(self.client.get(url).status_code, HTTPStatus.OK)
        for url in (
            api_url('users-me'),
            api_url('users-subscriptions'),
            api_url('recipes-download-shopping-cart'),
        ):
            self.assertEqual(
                self.client.get(url).status_code, HTTPStatus.UNAUTHORIZED
            )
        protected = (
            api_url('users-subscribe', self.author.pk),
            api_url('recipes-favorite', self.recipe.pk),
            api_url('recipes-shopping-cart', self.recipe.pk),
        )
        for url in (*protected, api_url('recipes-list')):
            self.assertEqual(
                self.client.post(url, {}, format='json').status_code,
                HTTPStatus.UNAUTHORIZED,
            )
        for url in protected:
            self.assertEqual(
                self.client.delete(url).status_code, HTTPStatus.UNAUTHORIZED
            )

    def test_change_password(self):
        self.login()
        endpoint = api_url('users-set-password')
        self.assertEqual(
            self.client.post(
                endpoint,
                {
                    'current_password': INVALID_PASSWORD,
                    'new_password': CHANGED_PASSWORD,
                },
            ).status_code,
            HTTPStatus.BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                endpoint,
                {
                    'current_password': AUTHOR_PASSWORD,
                    'new_password': CHANGED_PASSWORD,
                },
            ).status_code,
            HTTPStatus.NO_CONTENT,
        )
        self.author.refresh_from_db()
        self.assertTrue(self.author.check_password(CHANGED_PASSWORD))

    def test_avatar_validation_update_and_delete(self):
        self.login()
        for bad in INVALID_IMAGES:
            self.assertEqual(
                self.client.put(
                    api_url('users-avatar'), {'avatar': bad}, format='json'
                ).status_code,
                HTTPStatus.BAD_REQUEST,
            )
        response = self.client.put(
            api_url('users-avatar'), {'avatar': image_data()}, format='json'
        )
        self.assertEqual(response.status_code, HTTPStatus.OK, response.data)
        self.assertTrue(response.data['avatar'].startswith(MEDIA_URL_PREFIX))
        self.assertEqual(
            self.client.delete(api_url('users-avatar')).status_code,
            HTTPStatus.NO_CONTENT,
        )
        self.assertIsNone(self.client.get(api_url('users-me')).data['avatar'])
