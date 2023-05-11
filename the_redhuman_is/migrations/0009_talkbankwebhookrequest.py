# Generated by Django 3.2.12 on 2023-01-09 21:36

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('the_redhuman_is', '0008_paysheetentrytalkbankincomeregistration'),
    ]

    operations = [
        migrations.CreateModel(
            name='TalkBankWebhookRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Время получения')),
                ('request_body', models.BinaryField(null=True, verbose_name='Тело запроса')),
            ],
        ),
    ]
