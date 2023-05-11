$(document).ready(function () {
    $(document).on(
        'submit',
        '#day_details_form',
        function () {
            $('#result').attr('hidden', false);
            $('#result').html('Загрузка...');

            $.ajax({
                type: $(this).attr('method'),
                url: this.action,
                data: $(this).serialize(),
                context: this,
                success: function (data) {
                    error = data['error']
                    if (error) {
                        $('#result').html('Что-то пошло не так.');

                        $('#error').attr('hidden', false);
                        $('#error').html(error);
                    } else {
                        $('#result').html('Данные сохранены!');

                        $('#error').attr('hidden', true);

                        location.reload();
                    }
                },
                error: function (data) {
                    $('#result').html('Что-то пошло совсем не так.');
                }
            });
            return false;
        }
    );
});
