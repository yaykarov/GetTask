# Generated by Django 3.2.12 on 2022-04-25 16:46

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('the_redhuman_is', '0005_paysheetentrytalkbankpayment_paysheetentrytalkbankpaymentattempt_paysheettalkbankpaymentstatus_talkb'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkerPoll',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Время отправки вопроса')),
                ('question_code', models.TextField(verbose_name='Код опроса (для группировки)')),
                ('question_title', models.TextField(verbose_name='Заголовок вопроса')),
                ('question', models.TextField(verbose_name='Вопрос')),
                ('answer_timestamp', models.DateTimeField(blank=True, null=True, verbose_name='Время ответа')),
                ('answer', models.TextField(blank=True, null=True, verbose_name='Ответ')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='Автор')),
                ('worker', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='the_redhuman_is.worker', verbose_name='Рабочий')),
            ],
        ),
    ]
