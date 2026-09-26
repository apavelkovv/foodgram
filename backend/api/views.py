from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Count, Prefetch, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from djoser.views import UserViewSet as DjoserUserViewSet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.permissions import (
    AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly)
from rest_framework.response import Response

from api.filters import IngredientFilter, RecipeFilter
from api.permissions import IsAuthorOrReadOnly
from api.querysets import recipes_for_user, users_for_user
from api.serializers import (
    AvatarSerializer,
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeSummarySerializer,
    RecipeWriteSerializer,
    SubscriptionQuerySerializer,
    SubscriptionSerializer,
    TagSerializer,
)
from recipes.models import (
    Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag)
from users.models import Subscription

User = get_user_model()


class UserViewSet(DjoserUserViewSet):
    http_method_names = ('get', 'post', 'put', 'delete', 'head', 'options')

    @classmethod
    def get_extra_actions(cls):
        allowed = {
            'me', 'avatar', 'subscriptions', 'subscribe', 'set_password'
        }
        return [
            action
            for action in super().get_extra_actions()
            if action.__name__ in allowed
        ]

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method)

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method)

    def get_queryset(self):
        queryset = users_for_user(self.request.user)
        if self.action in ('subscriptions', 'subscribe'):
            recipes = Recipe.objects.all()
            limit = self.get_serializer_context().get('recipes_limit')
            if limit == 0:
                recipes = recipes.none()
            elif limit is not None:
                recipes = recipes[:limit]
            queryset = queryset.annotate(
                recipes_count=Count('recipes')).prefetch_related(
                Prefetch(
                    'recipes', queryset=recipes,
                    to_attr='subscription_recipes'),
            )
        return queryset.order_by('id')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action in ('subscriptions', 'subscribe'):
            query = SubscriptionQuerySerializer(data=self.request.query_params)
            query.is_valid(raise_exception=True)
            context.update(query.validated_data)
        return context

    @action(
        detail=False, methods=['get'],
        permission_classes=[IsAuthenticated])
    def me(self, request):
        user = self.get_queryset().get(pk=request.user.pk)
        return Response(self.get_serializer(user).data)

    @action(
        detail=False,
        methods=['put', 'delete'],
        url_path='me/avatar',
        permission_classes=[IsAuthenticated],
    )
    def avatar(self, request):
        if request.method == 'DELETE':
            request.user.avatar = ''
            request.user.save(update_fields=['avatar'])
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = AvatarSerializer(
            request.user, data=request.data,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(
        detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        authors = self.get_queryset().filter(
            subscribers__subscriber=request.user)
        page = self.paginate_queryset(authors)
        serializer = SubscriptionSerializer(
            page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True, methods=['post', 'delete'],
        permission_classes=[IsAuthenticated])
    def subscribe(self, request, **kwargs):
        author = self.get_object()
        if request.method == 'DELETE':
            deleted, _ = Subscription.objects.filter(
                subscriber=request.user, author=author
            ).delete()
            if not deleted:
                raise ValidationError('Вы не подписаны на этого автора.')
            return Response(status=status.HTTP_204_NO_CONTENT)
        if author == request.user:
            raise ValidationError('Нельзя подписаться на себя.')
        _, created = Subscription.objects.get_or_create(
            subscriber=request.user, author=author)
        if not created:
            raise ValidationError('Вы уже подписаны на этого автора.')
        author.is_subscribed = True
        return Response(
            SubscriptionSerializer(
                author, context=self.get_serializer_context()).data, status=201
        )


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny,)
    pagination_class = None
    filterset_class = IngredientFilter


class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly)
    filterset_class = RecipeFilter
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')

    def get_queryset(self):
        return recipes_for_user(self.request.user)

    def get_serializer_class(self):
        return (
            RecipeWriteSerializer
            if self.action in ('create', 'partial_update')
            else RecipeReadSerializer
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True, methods=['get'],
        url_path='get-link', permission_classes=[AllowAny])
    def get_link(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        return Response(
            {
                'short-link': request.build_absolute_uri(
                    reverse('recipe-short-link', args=[recipe.pk])
                )
            }
        )

    def change_collection(self, request, pk, model):
        recipe = get_object_or_404(Recipe, pk=pk)
        if request.method == 'DELETE':
            deleted, _ = model.objects.filter(
                user=request.user, recipe=recipe).delete()
            if not deleted:
                raise ValidationError('Рецепт отсутствует в списке.')
            return Response(status=status.HTTP_204_NO_CONTENT)
        _, created = model.objects.get_or_create(
            user=request.user, recipe=recipe)
        if not created:
            raise ValidationError('Рецепт уже добавлен в список.')
        return Response(
            RecipeSummarySerializer(
                recipe, context=self.get_serializer_context()).data, status=201
        )

    @action(
        detail=True, methods=['post', 'delete'],
        permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        return self.change_collection(request, pk, Favorite)

    @action(
        detail=True, methods=['post', 'delete'],
        permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        return self.change_collection(request, pk, ShoppingCart)

    @action(
        detail=False, methods=['get'],
        permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        ingredients = (
            RecipeIngredient.objects.filter(
                recipe__shopping_cart__user=request.user)
            .order_by()
            .values(
                'ingredient_id',
                'ingredient__name',
                'ingredient__measurement_unit',
            )
            .annotate(total=Sum('amount'))
            .order_by('ingredient__name')
        )
        lines = ['Список покупок', '']
        lines.extend(
            f'{item["ingredient__name"]} '
            f'({item["ingredient__measurement_unit"]}) — {item["total"]}'
            for item in ingredients
        )
        response = HttpResponse(
            '\n'.join(lines) + '\n',
            content_type='text/plain; charset=utf-8',
        )
        response['Content-Disposition'] = (
            'attachment; filename="shopping-list.txt"'
        )
        return response


def recipe_short_link(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    return redirect(f'/recipes/{recipe.pk}')


def health(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        cursor.fetchone()
    return JsonResponse({'status': 'ok'})
