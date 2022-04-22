import shutil
import tempfile

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Follow, Group, Post

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)

User = get_user_model()

POSTS_NUMBER = 13
POSTS_FIRST_PAGE = 10
POSTS_SEC_PAGE = 3

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
    content_type='image/gif',
)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class ViewsTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user = User.objects.create_user(username='NoName')
        cls.following_author = User.objects.create_user(username='Author')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Текст',
            group=cls.group,
            image=uploaded,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self) -> None:
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def checkup_post_context(self, response):
        """Проверка контекста поста от списка постов на странице."""
        post_object = response.context['page_obj'][0]
        self.assertEqual(post_object.text, self.post.text)
        self.assertEqual(post_object.group, self.post.group)
        self.assertEqual(post_object.author, self.post.author)
        self.assertEqual(post_object.image, self.post.image)

    def checkup_form_context(self, query):
        """Типы полей формы страницы соовествуют ожидаемым."""
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = query.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_pages_use_correct_template(self):
        """URL-адрес использует правильный html-шаблон."""
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list', kwargs={'slug': self.group.slug}):
            'posts/group_list.html',
            reverse('posts:profile', kwargs={'username': self.user.username}):
            'posts/profile.html',
            reverse('posts:post_detail', kwargs={'post_id': self.post.pk}):
            'posts/post_detail.html',
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk}):
            'posts/create_post.html',
            reverse('posts:post_create'): 'posts/create_post.html',
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:index'))
        self.checkup_post_context(response)

    def test_group_list_show_correct_context(self):
        """Шаблон group list сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': self.group.slug}))
        self.assertEqual(response.context['group'], self.group)
        self.checkup_post_context(response)

    def test_profile_show_correct_context(self):
        """Шаблон profile сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:profile', kwargs={'username': self.user}))
        self.assertEqual(response.context['author'], self.user)
        self.assertEqual(
            response.context['posts_count'], self.user.posts.count())
        self.checkup_post_context(response)

    def test_post_detail_show_correct_context(self):
        """Шаблон post detail сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.pk}))
        self.assertEqual(response.context['group'], self.post.group)
        self.assertEqual(
            response.context['posts_count'], self.user.posts.count())
        post_object = response.context['post']
        self.assertEqual(post_object.image, self.post.image)

    def test_create_post_show_correct_context(self):
        """Шаблон create post сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:post_create'))
        self.checkup_form_context(response)

    def test_edit_post_show_correct_context(self):
        """Шаблон create post сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk}))
        self.checkup_form_context(response)

    def test_post_with_group_appearance(self):
        """Пост с указанной группой появляется на соотвествующих страницах."""
        page_names = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': self.group.slug}),
            reverse('posts:profile', kwargs={'username': self.user.username}),
        ]
        for page in page_names:
            response = self.authorized_client.get(page)
            self.assertEqual(len(response.context['page_obj']), 1)

    def test_second_group_epmty(self):
        """Пост с указанной группой не появляется во второй пустой группе."""
        self.group_empty = Group.objects.create(
            title='Тестовая группа 2',
            slug='test-slug2',
            description='Тестовое описание 2',
        )
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': self.group_empty.slug})
        )
        self.assertEqual(len(response.context['page_obj']), 0)

    def test_cache_index(self):
        """Проверка работы кеша на главной страницы сайта"""
        cache.clear()
        Post.objects.create(
            author=self.user,
            text='Текст закешированного поста',
        )
        response_01 = self.authorized_client.get(reverse('posts:index'))
        Post.objects.latest('pk').delete()
        response_02 = self.authorized_client.get(reverse('posts:index'))
        self.assertEqual(response_02.content, response_01.content)
        cache.clear()
        response_03 = self.authorized_client.get(reverse('posts:index'))
        self.assertNotEqual(response_03.content, response_01.content)

    def test_auth_client_follow(self):
        '''Авторизованный пользователь может подписываться на автора'''
        self.authorized_client.get(
            reverse('posts:profile_follow',
                    kwargs={'username': self.following_author})
        )
        follow = Follow.objects.filter(
            user=self.user,
            author=self.following_author
        )
        self.assertTrue(follow.exists())

    def test_auth_client_unfollow(self):
        '''Авторизованный пользователь может отписываться от автора'''
        Follow.objects.create(user=self.user, author=self.following_author)
        self.authorized_client.get(
            reverse('posts:profile_unfollow',
                    kwargs={'username': self.following_author})
        )
        follow = Follow.objects.filter(
            user=self.user,
            author=self.following_author
        )
        self.assertFalse(follow.exists())

    def test_post_following_author(self):
        '''Пост автора появляется в ленте подписчика'''
        Follow.objects.create(user=self.user, author=self.following_author)
        self.post_author = Post.objects.create(
            author=self.following_author,
            text='Текст автора в подписке',
        )
        response = self.authorized_client.get(
            reverse('posts:follow_index'),
        )
        self.assertTrue(
            self.post_author in response.context['page_obj'])

    def test_post_unfollowing_author(self):
        '''Пост автора не появляется в ленте НЕподписчика'''
        self.post_author = Post.objects.create(
            author=self.following_author,
            text='Текст автора не в подписке',
        )
        response = self.authorized_client.get(
            reverse('posts:follow_index'),
        )
        self.assertFalse(
            self.post_author in response.context['page_obj'])


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user = User.objects.create_user(username='NoName')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        posts = [Post(
            author=cls.user,
            text=f'Текст поста №{i}',
            group=cls.group,)
            for i in range(POSTS_NUMBER)]
        Post.objects.bulk_create(posts)

    def setUp(self) -> None:
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_correct_paginator(self):
        """Проверка правильной работы паджинатора"""
        page_names = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': self.group.slug}),
            reverse('posts:profile', kwargs={'username': self.user.username}),
        ]
        for page in page_names:
            response = self.authorized_client.get(page)
            self.assertEqual(
                len(response.context['page_obj']), POSTS_FIRST_PAGE)
            response = self.authorized_client.get(
                page + '?page=2')
            self.assertEqual(len(response.context['page_obj']), POSTS_SEC_PAGE)
