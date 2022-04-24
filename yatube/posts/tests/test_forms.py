import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Comment, Group, Post

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class FormsTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user = User.objects.create_user(username='NoName')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Текст',
            group=cls.group,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_create_post_database(self):
        """
        Создание записи в базе данных при создании поста с валидной формой.
        """
        post_count = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        form_data = {
            'text': 'Текст 2',
            'group': self.group.pk,
            'image': uploaded,
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(response, reverse(
            'posts:profile', args=[self.user]))
        self.assertEqual(Post.objects.count(), post_count + 1)
        post_object = Post.objects.latest('pk')
        self.assertEqual(post_object.text, form_data['text'])
        self.assertEqual(post_object.group, self.group)
        self.assertEqual(post_object.image, f'posts/{uploaded}')

    def test_edit_post_database(self):
        """Изменение поста в базе данных при отправке
        валидной формы со страницы редактирования поста.
        """
        form_data = {
            'text': 'Измененный текст поста',
            'group': self.group.pk,
        }
        response = self.authorized_client.post(
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk}),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(response, reverse(
            'posts:post_detail', args=[self.post.pk]))
        self.assertTrue(
            Post.objects.filter(
                text=form_data['text'],
                group=self.group.pk,
            ).exists()
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.text, form_data['text'])

    def test_guest_client_edit_create_post(self):
        """
        Неавторизованный пользователь не может создать, редактировать пост
        """
        reverse_redirect = {
            reverse('posts:post_create'): '/auth/login/?next=/create/',
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk}):
            f'/auth/login/?next=/posts/{self.post.pk}/edit/',
        }
        form_data = {
            'text': 'Измененный текст поста гостя',
        }
        for rever, redic in reverse_redirect.items():
            response = self.guest_client.post(
                rever,
                data=form_data,
                follow=True,
            )
            self.assertRedirects(response, redic)
            self.assertFalse(
                Post.objects.filter(
                    text=form_data['text']
                ).exists()
            )

    def test_no_author_edit_post(self):
        """Авторизованный пользователь не может редактировать чужой пост"""
        user2 = User.objects.create_user(username='NoName2')
        self.no_author = Client()
        self.no_author.force_login(user2)
        form_data = {
            'text': 'Измененный текст чужого поста',
        }
        response = self.no_author.post(
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk}),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(response, reverse(
            'posts:post_detail', args=[self.post.pk]))
        self.assertFalse(
            Post.objects.filter(
                text=form_data['text']
            ).exists()
        )

    def test_guest_cannot_comment(self):
        """Неавторизованный пользователь не может комментировать пост"""
        comment_count = Comment.objects.count()
        form_data = {
            'text': 'Текст комментария от неавторизованного пользователя',
        }
        self.guest_client.post(
            reverse('posts:add_comment', kwargs={'post_id': self.post.pk}),
            data=form_data,
            follow=True,
        )
        self.assertFalse(
            Comment.objects.filter(
                text=form_data['text']
            ).exists()
        )
        self.assertEqual(Comment.objects.count(), comment_count)

    def test_create_comment(self):
        """После успешной отправки комментарий появляется на странице поста"""
        comment_count = Comment.objects.count()
        form_data = {
            'text': 'Текст комментария от авторизованного пользователя',
        }
        self.authorized_client.post(
            reverse('posts:add_comment', kwargs={'post_id': self.post.pk}),
            data=form_data,
            follow=True,
        )
        self.assertEqual(Comment.objects.count(), comment_count + 1)
        self.assertTrue(
            Comment.objects.filter(
                text=form_data['text']
            ).exists()
        )
