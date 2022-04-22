from django.test import TestCase
from http import HTTPStatus


class CoreTests(TestCase):
    def test_urls_404_custom_template(self):
        """URL-адрес ошибки 404 использует кастомный шаблон."""
        response = self.client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertTemplateUsed(response, 'core/404.html')
