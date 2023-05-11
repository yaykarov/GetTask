import logging
from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from rest_framework.permissions import IsAuthenticated

from . import views

dev_logger = logging.getLogger("dev_logger")


def staff_account_required(function):
    def proxy(request, *args, **kwargs):
        try:
            if request.user.is_authenticated:
                account = views.utils.get_customer_account(request)
                if account is None:
                    return function(request, *args, **kwargs)
        except Exception as e:
            dev_logger.error(repr(e))
            raise
        return redirect("login")

    return proxy


class StaffAccountRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        account = views.utils.get_customer_account(request)
        if account:
            return self.handle_no_permission()
        return super(StaffAccountRequiredMixin, self).dispatch(request, *args,
                                                               **kwargs)


def user_in_group(group_name):
    # todo when middleware can handle api views, move this logic there
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):

            if request.user is None:
                return HttpResponseForbidden(
                    content_type='application/json'
                )
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            groups = list(request.user.groups.values_list('name', flat=True))
            if group_name in groups:
                return view_func(request, *args, **kwargs)

            return HttpResponseForbidden(
                content_type='application/json'
            )

        return _wrapped_view
    return decorator


class IsCustomer(IsAuthenticated):
    def has_permission(self, request, view):
        return (
                super(IsCustomer, self).has_permission(request, view) and
                hasattr(request.user, 'customeraccount')
        )
