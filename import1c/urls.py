from django.conf.urls import url

from .views import upload_1c_file, import_operation, add_operation


app_name = 'import1c'

urlpatterns = [
    url(r'^upload-1c-file/$', upload_1c_file, name='upload-1c-file'),
    url(r'^import-operation/$', import_operation, name='import-operation'),
    url(r'^add-operation/$', add_operation, name='add-operation'),
]
