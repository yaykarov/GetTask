# -*- coding: utf-8 -*-

from django.conf.urls import url
from django.urls import path

from the_redhuman_is.views import photo_load_views

from the_redhuman_is.views.photo_load_views import (
    AddComment,
    PhotoLoadAddView,
    PhotoLoadCloseView,
    PhotoLoadListView,
    PhotoLoadSortContractView,
    PhotoLoadSortTimesheetAfterView,
    PhotoLoadSortTimesheetBeforeView,
    PhotoLoadSortWorkerView,
    PhotoLoadUpdateView,
    delete_photo_load_session,
)


urlpatterns = [
    url(
        r'^$',
        PhotoLoadListView.as_view(),
        name='photo_load_session_list'
    ),
    path(
        '<int:pk>/delete/',
        delete_photo_load_session,
        name='photo_load_session_delete'
    ),
    url(
        r'^add/(?P<name>(worker|contract|timesheet))/$',
        PhotoLoadAddView.as_view(),
        name='photo_load_session_add'
    ),
    url(
        r'^add_comment/(?P<pk>[0-9]+)/$',
        AddComment.as_view(),
        name='photo_load_add_comment'
    ),
    url(
        r'^close/(?P<pk>[0-9]+)/$', 
        PhotoLoadCloseView.as_view(),
        name='photo_load_close_session'
    ),
    # Todo: photo_load_session_sort name is not unique, is it ok?
    url(
        r'^sort/(?P<pk>[0-9]+)/(?P<name>(contract))/$',
        PhotoLoadSortContractView.as_view(),
        name='photo_load_session_sort'
    ),
    url(
        r'^sort/(?P<pk>[0-9]+)/(?P<name>(timesheet))/$',
        PhotoLoadSortTimesheetBeforeView.as_view(),
        name='photo_load_session_sort'
    ),
    url(
        r'^sort/(?P<pk>[0-9]+)/(?P<name>(timesheet))/(?P<timesheet_pk>[0-9]+)/$',
        PhotoLoadSortTimesheetAfterView.as_view(),
        name='photo_load_session_sort'
    ),
    url(
        r'^sort/(?P<pk>[0-9]+)/(?P<name>(worker))/$',
        PhotoLoadSortWorkerView.as_view(),
        name='photo_load_session_sort'
    ),
    url(
        r'^update/(?P<pk>[0-9]+)/(?P<name>(worker|contract|timesheet))/$',
        PhotoLoadUpdateView.as_view(),
        name='photo_load_session_update'
    ),
    url(
        r'^worker_turnout_output/$',
        photo_load_views.worker_turnout_output,
        name='worker_turnout_output'
    ),
    url(
        r'^bad_photo_alert/$',
        photo_load_views.bad_photo_alert,
        name='photo_load_bad_photo_alert'
    ),
]
