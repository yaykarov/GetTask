from django.contrib import admin

from telegram_bot.models import TelegramUser


class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'chat_id', 'date', 'bot')
    readonly_fields = ('chat_id',)


admin.site.register(TelegramUser, TelegramUserAdmin)
