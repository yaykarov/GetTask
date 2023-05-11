from django import forms
from .models import HrSiteAccount, HrSiteReport, HrSiteAdv
from dal import autocomplete


class HrSiteAccountForm(forms.ModelForm):

    class Meta:
        model = HrSiteAccount
        fields = ('name',
                  'phone')


class HrSiteReportForm(forms.ModelForm):

    class Meta:
        model = HrSiteReport
        fields = ('create_time',)


class HrSiteAdvForm(forms.ModelForm):

    class Meta:
        model = HrSiteAdv
        fields = ("keyword",
                  "report",
                  "account",
                  "date_time",
                  "title",
                  "ref")
