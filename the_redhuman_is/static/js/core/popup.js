function register_on_click_popup(link_class, modal_id, modal_body_id, on_success=null) {
    $(link_class).on(
        'click',
        function() {
            $(modal_id).modal();

            $(modal_body_id).html('Загрузка...');

            $.ajax({
                type: 'GET',
                url: this.href,
                success: function(data) {
                    $(modal_body_id).html(data);
                    if (on_success) {
                        on_success();
                    }
                },
                error: function(data) {
                    $(modal_body_id).html('Что-то пошло не так.');
                }
            });

            return false;
        }
    );
}
