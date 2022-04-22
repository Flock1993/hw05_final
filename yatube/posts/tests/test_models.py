from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Group, Post

User = get_user_model()


class PostModelTest(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user = User.objects.create()
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Текст длиной более пятнадцати символов',
        )

    def test_models_post_have_correct_object_names(self):
        """Проверка, что у моделей постов корректно работает __str__."""
        post = PostModelTest.post
        result = str(post)
        self.assertEqual(result, post.text[:15])

    def test_models_group_have_correct_object_names(self):
        """Проверка, что у моделей групп корректно выводится название."""
        group = PostModelTest.group
        result = str(group)
        self.assertEqual(result, group.title)
