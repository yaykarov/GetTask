from django.db import models


class City(models.Model):
    name = models.CharField('Имя', max_length=100)
    has_metro = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def get_dict(self):
        return {'pk': self.pk, 'name': self.name}


class MetroBranch(models.Model):
    number = models.IntegerField(
        'Номер ветки',
        null=False
    )
    name = models.CharField(
        'Имя ветки',
        null=False,
        max_length=100
    )
    color = models.CharField(
        'Цвет ветки',
        max_length=20
    )
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        verbose_name='Город'
    )

    class Meta:
        unique_together = (('color', 'city'), ('number', 'city'), ('name', 'city'))

    def __str__(self):
        return 'Ветка №{} {} города {}'.format(self.number, self.name, self.city.name)

    def get_dict(self):
        return {'pk': self.pk, 'name': self.name, 'number': self.number, 'color': self.color, 'city': self.city.pk}


class MetroStation(models.Model):
    name = models.CharField(
        'Имя',
        max_length=100
    )
    branch = models.ForeignKey(
        MetroBranch,
        on_delete=models.PROTECT,
        verbose_name='Ветка'
    )

    def __str__(self):
        return 'Станция '+self.name

    def get_dict(self):
        return {'pk': self.pk, 'name': self.name, 'branch': self.branch.pk}
