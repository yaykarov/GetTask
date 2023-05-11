from rest_framework import serializers
from .models import HrSiteAccount, HrSiteReport, HrSiteAdv


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = HrSiteAccount
        fields = ('name', 'phone')


class AdvSerializer(serializers.ModelSerializer):
    #account = AccountSerializer(many=True, read_only=True)

    class Meta:
        model = HrSiteAdv
        fields = ('keyword','account','position','site','date_time_str','title','ref')


class ReportSerializer(serializers.ModelSerializer):
    ads = AdvSerializer(many=True, read_only=True)

    class Meta:
        model = HrSiteReport
        fields = ('create_time','position_count','sites','managers','ads')