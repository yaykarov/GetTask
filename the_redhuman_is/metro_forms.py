from django import forms
from the_redhuman_is.metro_models import City, MetroBranch, MetroStation


class CityForm(forms.ModelForm):
    class Meta:
        model = City
        fields = ('name',)


class MetroBranchForm(forms.ModelForm):
    class Meta:
        model = MetroBranch
        fields = ('name', 'number', 'color', 'city')


class MetroStationForm(forms.ModelForm):
    class Meta:
        model = MetroStation
        fields = ('name', 'branch')
