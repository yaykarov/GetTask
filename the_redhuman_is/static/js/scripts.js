$('.manager_form select').on('change', function () {
    $($(this).parent()).submit();
});

$(document).on('submit', '.manager_form', function () {
    $.ajax({
        type: $(this).attr('method'),
        url: this.action,
        data: $(this).serialize(),
        context: this,

        success: function (data, status) {
            $(this).find('.result').html('Данные изменены');
        },

        error: function (data, status) {
            $(this).find('.result').html('Данные изменены');
        }
    });
    return false;
});