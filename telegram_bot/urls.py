from django.conf.urls import url

from telegram_bot.views import delete_user
from telegram_bot.views import users_list

app_name = 'telegram_bot'

urlpatterns = [
    url(r'^users_list/$', users_list, name='users_list'),
    url(r'^delete_user/(?P<pk>\d+)/$', delete_user, name='delete_user'),
]
