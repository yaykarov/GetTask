from django.db import models
from django.db.models import signals
import re
from datetime import datetime


class HrSiteAccount(models.Model):
    name = models.CharField(max_length=30, blank=False, null=False)
    phone = models.CharField("Телефон", max_length=100, blank=False, null=True, unique=True)

    def __str__(self):
        return self.name

    def get_dict(self):
        return {"name": self.name, "phone": self.phone}

class HrSiteReport(models.Model):
    create_time = models.DateTimeField('Дата создания', blank=True, null=True)
    positionCount = models.IntegerField('число позиций поиска', null=True)
    sites = models.CharField(max_length=300, blank=True, null=True)
    managers = models.CharField(max_length=300, blank=True, null=True)
    current_status = models.CharField(max_length=500, blank=True, null=True)
    key = models.IntegerField(null=False)

    def __str__(self):
        return "#{} ({})".format(self.pk, self.sites)

    def get_dict(self):
        result = {"pk": self.pk,"create_time": datetime.strftime(self.create_time,'%d.%m.%Y'), "positionCount": self.positionCount, "sites": self.sites, "managers": self.managers }
        return result


class HrSiteAdv(models.Model):
    keyword = models.CharField(max_length=50, blank=False, null=False)
    report = models.ForeignKey(HrSiteReport, null=False, verbose_name="Отчет", on_delete=models.CASCADE)
    account = models.ForeignKey(HrSiteAccount, null=True, verbose_name="Аккаунт сайта вакансий",
                                on_delete=models.CASCADE)
    position = models.IntegerField(blank=False, null=True)
    site = models.CharField(max_length=50, blank=False, null=True)
    date_time = models.DateTimeField('Дата размещения', blank=True, null=True)
    date_time_str = models.CharField('Дата размещения', max_length=300, blank=True, null=True)
    title = models.CharField("Заголовок", max_length=300, blank=False, null=False)
    ref = models.CharField("Ссылка на объявление", max_length=300, blank=False, null=False)

    def __str__(self):
        return "#{} ({})".format(self.keyword, str(self.account))

    def get_dict(self):
        result = {"keyword": self.keyword, "position": self.position, "site": self.site, "date_time_str": self.date_time_str, "title": self.title, "ref": self.ref, "account": self.account.get_dict() }
        return result


def get_digit_str(str):
    digit_list = [l if l in '0123456789' else '' for l in str]
    res = ''
    for digit in digit_list:
        res += digit
    return res


#signals.post_save.connect(set_account_id, sender=HrSiteAccount)
