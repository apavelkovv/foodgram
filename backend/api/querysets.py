from django.contrib.auth import get_user_model
from django.db.models import BooleanField, Exists, OuterRef, Prefetch, Value

from recipes.models import Favorite, Recipe, RecipeIngredient, ShoppingCart
from users.models import Subscription

User = get_user_model()


def users_for_user(user):
    subscribed = Value(False, output_field=BooleanField())
    if user.is_authenticated:
        subscribed = Exists(
            Subscription.objects.filter(
                subscriber=user, author_id=OuterRef('pk')))
    return User.objects.annotate(is_subscribed=subscribed)


def recipes_for_user(user):
    flags = {}
    for name, model in [
        ('is_favorited', Favorite), ('is_in_shopping_cart', ShoppingCart)
    ]:
        flags[name] = (
            Exists(model.objects.filter(user=user, recipe_id=OuterRef('pk')))
            if user.is_authenticated
            else Value(False, output_field=BooleanField())
        )
    return Recipe.objects.annotate(**flags).prefetch_related(
        Prefetch('author', queryset=users_for_user(user)),
        'tags',
        Prefetch(
            'ingredient_amounts',
            queryset=RecipeIngredient.objects.select_related('ingredient')
        ),
    )
