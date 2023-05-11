from urllib.parse import quote_plus

from django.urls import reverse


def get_reverse(viewname, args, kwargs=None):
    if kwargs:
        return "%s?%s" % (reverse(viewname,args=args), "&".join([key+"="+quote_plus(value) for (key, value) in kwargs.items()]))
    else:
        return reverse(viewname,args=args)
