from django.contrib import admin

from applicants.models import *

from the_redhuman_is.admin import _register

admin.site.register(AllowedStatusTransition)
admin.site.register(Applicant)
_register(ApplicantHistoryHead, ['applicant', 'node'])
_register(ApplicantHistoryNode, ['previous', 'applicant'])
admin.site.register(ApplicantSource)
_register(ApplicantWorkerLink, ['applicant', 'worker'])
admin.site.register(Status)
admin.site.register(StatusFinal)
admin.site.register(StatusInitial)
admin.site.register(VacantCustomerLocation)
