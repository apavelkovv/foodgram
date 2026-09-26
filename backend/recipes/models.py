from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Tag(models.Model):
    name = models.CharField('Название', max_length=32, unique=True)
    slug = models.SlugField('Слаг', max_length=32, unique=True)

    class Meta:
        ordering = ('id',)
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField('Название', max_length=128)
    measurement_unit = models.CharField('Единица измерения', max_length=64)

    class Meta:
        ordering = ('name', 'id')
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        constraints = [
            models.UniqueConstraint(
                fields=('name', 'measurement_unit'),
                name='unique_ingredient_unit',
            )
        ]

    def __str__(self):
        return f'{self.name} ({self.measurement_unit})'


class Recipe(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recipes',
        verbose_name='Автор',
    )
    name = models.CharField('Название', max_length=256)
    image = models.ImageField('Изображение', upload_to='recipes/')
    text = models.TextField('Описание')
    cooking_time = models.PositiveIntegerField(
        'Время приготовления (мин)',
        validators=[MinValueValidator(1)],
    )
    created_at = models.DateTimeField('Дата публикации', auto_now_add=True)
    tags = models.ManyToManyField(
        Tag, related_name='recipes', verbose_name='Теги'
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        through='RecipeIngredient',
        related_name='recipes',
        verbose_name='Ингредиенты',
    )

    class Meta:
        ordering = ('-created_at', '-id')
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        indexes = [
            models.Index(
                fields=('-created_at', '-id'), name='recipe_newest_idx'
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cooking_time__gte=1),
                name='positive_cooking_time',
            )
        ]

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='ingredient_amounts',
        verbose_name='Рецепт',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='recipe_amounts',
        verbose_name='Ингредиент',
    )
    amount = models.PositiveIntegerField(
        'Количество', validators=[MinValueValidator(1)]
    )

    class Meta:
        ordering = ('id',)
        verbose_name = 'Ингредиент рецепта'
        verbose_name_plural = 'Ингредиенты рецептов'
        constraints = [
            models.UniqueConstraint(
                fields=('recipe', 'ingredient'),
                name='unique_recipe_ingredient',
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gte=1),
                name='positive_ingredient_amount',
            ),
        ]

    def __str__(self):
        return f'{self.ingredient}: {self.amount}'


class RecipeCollection(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, verbose_name='Рецепт'
    )

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'recipe'),
                name='%(class)s_unique_user_recipe',
            )
        ]

    def __str__(self):
        return f'{self.user}: {self.recipe}'


class Favorite(RecipeCollection):
    class Meta(RecipeCollection.Meta):
        default_related_name = 'favorites'
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'


class ShoppingCart(RecipeCollection):
    class Meta(RecipeCollection.Meta):
        default_related_name = 'shopping_cart'
        verbose_name = 'Покупка'
        verbose_name_plural = 'Список покупок'
