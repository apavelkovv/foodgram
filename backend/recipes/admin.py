from django.contrib import admin
from django.db.models import Count
from django.forms.models import BaseInlineFormSet

from recipes.models import Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_unit')
    search_fields = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class IngredientFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_num = 1
        self.validate_min = True


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    formset = IngredientFormSet
    autocomplete_fields = ('ingredient',)
    extra = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('name', 'author', 'cooking_time', 'favorites_count')
    search_fields = ('name', 'author__username', 'author__email')
    list_filter = ('tags',)
    autocomplete_fields = ('author',)
    filter_horizontal = ('tags',)
    readonly_fields = ('created_at', 'favorites_count')
    inlines = (RecipeIngredientInline,)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('author')
            .annotate(favorite_count=Count('favorites'))
        )

    @admin.display(description='Добавлений в избранное')
    def favorites_count(self, obj):
        return getattr(obj, 'favorite_count', 0)


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ('recipe', 'ingredient', 'amount')
    autocomplete_fields = ('recipe', 'ingredient')


@admin.register(Favorite, ShoppingCart)
class RecipeCollectionAdmin(admin.ModelAdmin):
    list_display = ('user', 'recipe')
    search_fields = ('user__username', 'recipe__name')
    autocomplete_fields = ('user', 'recipe')
