$(document).ready(function () {
    $('#unassigned-form').on(
        'show.bs.modal',
        function (e) {
            $('#unassigned-form-body').html('Загрузка...');

            $.ajax(
                {
                    type: 'GET',
                    url: '/applicants/unassigned_list/',
                    success: function (data) {
                        $('#unassigned-form-body').html(data);

                        $('.applicant-assign-link').on(
                            'click',
                            function (e) {
                                link = this
                                $.ajax(
                                    {
                                        type: 'POST',
                                        url: link.href,
                                        success: function () {
                                            $(link).remove();
                                        },
                                        error: function () {
                                        }
                                    }
                                );

                                return false;
                            }
                        );
                    },
                    error: function (data) {
                        $('#unassigned-form-body').html('Что-то пошло не так.');
                    }
                }
            );
        }
    );

    $('#modalForm').on(
        'show.bs.modal',
        function() {
            $('#edit-applicant-submit').show();
            $('#modal-form-alert').hide();
        }
    );

    $('#modalForm').on(
        'submit',
        function() {
            $('#edit-applicant-submit').hide();
            let form = $(this).find('form');
            $.ajax({
                type: form.attr('method'),
                url: form.attr('action'),
                data: form.serialize(),
                context: this,
                success: function(data) {
                    if (data.result == 'ok') {
                        $('#modalForm').modal('hide');
                        location.reload();
                    } else {
                        if (data.result == 'error') {
                            $('#modal-form-alert').html(data.error_text);
                        } else {
                            $('#modal-form-alert').html('Что-то пошло не так.');
                        }
                        $('#modal-form-alert').show(200);
                        $('#edit-applicant-submit').show();
                    }
                },
                erorr: function(XMLHttpRequest, textStatus, errorThrown) {
                },
            });
            return false;
        }
    );

    $('#history-form').on(
        'show.bs.modal',
        function (e) {
            $('#history-form-body').html('Загрузка...');

            $.ajax(
                {
                    type: 'GET',
                    url: '/applicants/history/' + $('#history-form').data('id') + '/',
                    success: function (data) {
                        $('#history-form-body').html(data);
                    },
                    error: function (data) {
                        $('#history-form-body').html('Что-то пошло не так.');
                    }
                }
            );
        }
    );
});
