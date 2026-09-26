from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from users.models import Subscription, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    search_fields = ('email', 'username')
    fieldsets = (*DjangoUserAdmin.fieldsets, ('Изображение', {'fields': ('avatar',)}))
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'username',
                    'email',
                    'first_name',
                    'last_name',
                    'password1',
                    'password2',
                ),
            },
        ),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('subscriber', 'author')
    search_fields = ('subscriber__username', 'author__username')
    autocomplete_fields = ('subscriber', 'author')
