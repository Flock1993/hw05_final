from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CommentForm, PostForm
from .models import Follow, Group, Post, User


def page_object(post_list, request):
    paginator = Paginator(post_list, settings.POSTS_NUM1)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


def index(request):
    post_list = Post.objects.order_by('-pub_date')
    context = {
        'page_obj': page_object(post_list, request),
    }
    return render(request, 'posts/index.html', context)


def group_posts(request, slug):
    group = get_object_or_404(Group, slug=slug)
    posts = group.posts.order_by('-pub_date')
    context = {
        'group': group,
        'page_obj': page_object(posts, request),
    }
    return render(request, 'posts/group_list.html', context)


def profile(request, username):
    author = get_object_or_404(User, username=username)
    posts = author.posts.order_by('-pub_date')
    posts_count = author.posts.count()
    following = (
        request.user.is_authenticated
        and Follow.objects.filter(
            user=request.user,
            author=author,
        ).exists()
    )
    context = {
        'author': author,
        'posts_count': posts_count,
        'page_obj': page_object(posts, request),
        'following': following,
    }
    return render(request, 'posts/profile.html', context)


def post_detail(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    group = post.group
    author = post.author
    posts_count = author.posts.count()
    comments = post.comments.all()
    form = CommentForm(request.POST or None)
    context = {
        'post': post,
        'group': group,
        'posts_count': posts_count,
        'comments': comments,
        'form': form,
    }
    return render(request, 'posts/post_detail.html', context)


@login_required
def post_create(request):
    form = PostForm(
        request.POST or None,
        files=request.FILES or None,
    )
    if form.is_valid():
        form.instance.author = request.user
        form.save()
        return redirect('posts:profile', username=request.user.username)
    context = {
        'is_edit': False,
        'title': 'Новый пост',
        'groups': Group.objects.all(),
        'form': form,
    }
    return render(request, 'posts/create_post.html', context)


@login_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.user != post.author:
        return redirect('posts:post_detail', post_id)
    form = PostForm(
        request.POST or None,
        files=request.FILES or None,
        instance=post,
    )
    if form.is_valid():
        form.save()
        return redirect('posts:post_detail', post_id)
    return render(request, 'posts/create_post.html', {
        'form': form,
        'is_edit': True,
        'post': post,
    })


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('posts:post_detail', post_id=post_id)


@login_required
def follow_index(request):
    following_authors = request.user.follower.values_list('author')
    post_list = Post.objects.filter(author__id__in=following_authors)
    context = {
        'page_obj': page_object(post_list, request),
    }
    return render(request, 'posts/follow.html', context)


@login_required
def profile_follow(request, username):
    author = get_object_or_404(User, username=username)
    already_following = Follow.objects.filter(
        user=request.user,
        author=author,
    ).exists()
    if request.user != author and not already_following:
        Follow.objects.create(
            user=request.user,
            author=author,
        )
    return redirect('posts:profile', username=username)


@login_required
def profile_unfollow(request, username):
    Follow.objects.filter(
        author__username=username,
        user=request.user
    ).delete()
    return redirect('posts:profile', username=username)
