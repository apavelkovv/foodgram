from http import HTTPStatus

from tests.fixtures import FoodgramTestCase, api_url


class SubscriptionTests(FoodgramTestCase):
    def test_subscription_lifecycle_and_limits(self):
        self.login(self.reader)
        endpoint = api_url('users-subscribe', self.author.pk)
        self.assertEqual(
            self.client.delete(endpoint).status_code, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(
            self.client.post(
                api_url('users-subscribe', self.reader.pk)
            ).status_code,
            HTTPStatus.BAD_REQUEST,
        )
        response = self.client.post(
            api_url('users-subscribe', self.author.pk, recipes_limit=0)
        )
        self.assertEqual(
            response.status_code, HTTPStatus.CREATED, response.data
        )
        self.assertEqual(response.data['recipes'], [])
        self.assertEqual(response.data['recipes_count'], 1)
        self.assertTrue(response.data['is_subscribed'])
        self.assertEqual(
            self.client.post(endpoint).status_code, HTTPStatus.BAD_REQUEST
        )
        self.assertEqual(
            self.client.get(
                api_url('users-subscriptions', recipes_limit=1)
            ).data['count'],
            1,
        )
        for invalid in ('-1', 'abc', '1.5'):
            self.assertEqual(
                self.client.get(
                    api_url('users-subscriptions', recipes_limit=invalid)
                ).status_code,
                HTTPStatus.BAD_REQUEST,
            )
        self.login()
        self.assertEqual(
            self.client.get(api_url('users-subscriptions')).data['count'], 0
        )
        self.login(self.reader)
        self.assertEqual(
            self.client.delete(endpoint).status_code, HTTPStatus.NO_CONTENT
        )
