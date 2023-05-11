from django.contrib import admin
from .models import HrSiteAccount, HrSiteReport, HrSiteAdv


admin.site.register(HrSiteReport)
admin.site.register(HrSiteAccount)
admin.site.register(HrSiteAdv)