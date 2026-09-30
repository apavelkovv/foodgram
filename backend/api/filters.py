from django.db import connection
from django_filters import rest_framework as filters

from recipes.models import Ingredient, Recipe, Tag


class RecipeFilter(filters.FilterSet):
    is_favorited = filters.BooleanFilter(method='filter_collection')
    is_in_shopping_cart = filters.BooleanFilter(method='filter_collection')
    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all(),
    )

    class Meta:
        model = Recipe
        fields = ('author', 'tags')

    def filter_collection(self, queryset, name, value):
        return queryset.filter(**{name: True}) if value else queryset


class IngredientFilter(filters.FilterSet):
    name = filters.CharFilter(method='filter_name')

    class Meta:
        model = Ingredient
        fields = ('name',)

    def filter_name(self, queryset, name, value):
        if connection.vendor == 'sqlite':
            ids = [
                pk
                for pk, title in queryset.values_list('pk', 'name')
                if title.casefold().startswith(value.casefold())
            ]
            return queryset.filter(pk__in=ids)
        return queryset.filter(name__istartswith=value)
