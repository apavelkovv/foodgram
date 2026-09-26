from django.contrib.auth import get_user_model
from django.db import transaction
from djoser.serializers import (
    UserCreateSerializer as DjoserUserCreateSerializer)
from rest_framework import serializers

from api.fields import Base64ImageField
from recipes.models import Ingredient, Recipe, RecipeIngredient, Tag

User = get_user_model()


class UserCreateSerializer(DjoserUserCreateSerializer):
    class Meta(DjoserUserCreateSerializer.Meta):
        model = User
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name', 'password')


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'first_name',
            'last_name', 'is_subscribed', 'avatar')
        read_only_fields = fields


class AvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField()

    class Meta:
        model = User
        fields = ('avatar',)


class RecipeSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class SubscriptionSerializer(UserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = (*UserSerializer.Meta.fields, 'recipes', 'recipes_count')

    def get_recipes(self, author):
        recipes = author.subscription_recipes
        limit = self.context.get('recipes_limit')
        if limit is not None:
            recipes = recipes[:limit]
        return RecipeSummarySerializer(
            recipes, many=True, context=self.context).data


class SubscriptionQuerySerializer(serializers.Serializer):
    recipes_limit = serializers.IntegerField(required=False, min_value=0)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class IngredientAmountReadSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient_id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class IngredientAmountWriteSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(), source='ingredient')
    amount = serializers.IntegerField(min_value=1, max_value=2147483647)


class RecipeReadSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    ingredients = IngredientAmountReadSerializer(
        source='ingredient_amounts', many=True, read_only=True
    )
    is_favorited = serializers.BooleanField(read_only=True, default=False)
    is_in_shopping_cart = serializers.BooleanField(
        read_only=True, default=False)

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time',
        )


class RecipeWriteSerializer(serializers.ModelSerializer):
    ingredients = IngredientAmountWriteSerializer(many=True, allow_empty=False)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, allow_empty=False
    )
    image = Base64ImageField()
    cooking_time = serializers.IntegerField(min_value=1, max_value=2147483647)

    class Meta:
        model = Recipe
        fields = (
            'ingredients', 'tags', 'image', 'name', 'text', 'cooking_time'
        )

    def validate(self, attrs):
        required = ('ingredients', 'tags', 'name', 'text', 'cooking_time')
        missing = {
            field: ['Обязательное поле.'] for field in required if
            field not in attrs
        }
        if missing:
            raise serializers.ValidationError(missing)
        return attrs

    def validate_tags(self, tags):
        if len({tag.pk for tag in tags}) != len(tags):
            raise serializers.ValidationError('Теги не должны повторяться.')
        return tags

    def validate_ingredients(self, ingredients):
        if len(
            {item['ingredient'].pk for item in ingredients}
        ) != len(ingredients):
            raise serializers.ValidationError(
                'Ингредиенты не должны повторяться.')
        return ingredients

    @staticmethod
    def save_ingredients(recipe, ingredients):
        RecipeIngredient.objects.bulk_create(
            [RecipeIngredient(recipe=recipe, **item) for item in ingredients]
        )

    @transaction.atomic
    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        recipe = super().create(validated_data)
        recipe.tags.set(tags)
        self.save_ingredients(recipe, ingredients)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        instance = super().update(instance, validated_data)
        instance.tags.set(tags)
        instance.ingredient_amounts.all().delete()
        self.save_ingredients(instance, ingredients)
        return instance

    def to_representation(self, instance):
        from api.querysets import recipes_for_user

        recipe = recipes_for_user(
            self.context['request'].user).get(pk=instance.pk)
        return RecipeReadSerializer(recipe, context=self.context).data
