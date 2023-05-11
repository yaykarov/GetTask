from django.db.models import (
    DateTimeField,
    FloatField,
    Func,
)
from django.db.models.functions import (
    ASin,
    Cos,
    Radians,
    Sqrt,
)
from django.db.models.functions.datetime import TimezoneMixin


class ConcatWSPair(Func):
    function = 'CONCAT_WS'


class ConcatWS(Func):
    """
    Concatenate text fields together.
    """
    function = None
    template = "%(expressions)s"

    def __init__(self, *expressions, **extra):
        if len(expressions) < 3:
            raise ValueError('ConcatWS takes at least three expressions')
        paired = self._paired(expressions)
        super().__init__(paired, **extra)

    def _paired(self, expressions):
        # wrap pairs of expressions in successive concat functions
        # exp = [sep, a, b, c, d]
        # -> ConcatWSPair(sep, a, ConcatWSPair(sep, b, ConcatWSPair(sep, c, d))))
        if len(expressions) == 3:
            return ConcatWSPair(*expressions)
        return ConcatWSPair(
            expressions[0],
            expressions[1],
            self._paired((expressions[0],) + expressions[2:])
        )


PostgresConcatWS = ConcatWSPair


class Haversine(Func):
    function = None
    template = '%(expressions)s'
    arity = 4
    output_field = FloatField()

    def get_haversine(self):
        lat1, lat2, lon1, lon2 = self.source_expressions
        return 12742 * ASin(Sqrt(
            (1 - Cos(Radians(lat1 - lat2))) / 2 +
            Cos(Radians(lat1)) * Cos(Radians(lat2)) * (1 - Cos(Radians(lon1 - lon2))) / 2
        ))

    def as_sql(
            self, compiler, connection,
            function=None, template=None, arg_joiner=None, **extra_context
    ):
        return self.get_haversine().as_sql(compiler, connection, **extra_context)


class MakeAware(TimezoneMixin, Func):
    output_field = DateTimeField()
    arity = 1

    def __init__(self, expression, output_field=None, tzinfo=None, **extra):
        self.tzinfo = tzinfo
        super().__init__(expression, output_field=output_field, **extra)

    def as_sql(
            self, compiler, connection,
            function=None, template=None, arg_joiner=None, **extra_context
    ):
        sql, params = compiler.compile(self.get_source_expressions()[0])
        sql = connection.ops._convert_field_to_tz(
            sql,
            self.get_tzname()
        )
        return sql, params
