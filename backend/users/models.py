from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from users.constants import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH


class User(AbstractUser):
    email = models.EmailField(
        'Электронная почта', unique=True, max_length=EMAIL_MAX_LENGTH
    )
    first_name = models.CharField('Имя', max_length=PERSON_NAME_MAX_LENGTH)
    last_name = models.CharField('Фамилия', max_length=PERSON_NAME_MAX_LENGTH)
    avatar = models.ImageField('Аватар', upload_to='avatars/', blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        ordering = ('username',)
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username


class Subscription(models.Model):
    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name='Подписчик',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscribers',
        verbose_name='Автор',
    )

    class Meta:
        ordering = ('id',)
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        constraints = [
            models.UniqueConstraint(
                fields=('subscriber', 'author'), name='unique_subscription'
            ),
            models.CheckConstraint(
                condition=~models.Q(subscriber=models.F('author')),
                name='no_self_subscription',
            ),
        ]

    def __str__(self):
        return f'{self.subscriber} → {self.author}'
