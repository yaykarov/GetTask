function nextId(form_id, id_suffix) {
    let id = $('#' + form_id + ' .in').find('input[type="text"]').last().attr('id');
    let __last_id = 0;
    if (typeof id !== typeof undefined && id !== false) __last_id = id.replace('id_comment_' + id_suffix + '_id_', '');
    __last_id++;
    return "_id_" + __last_id;
}

function onRemove(id) {
    document.getElementById(id).remove();
    if (id.includes('cfine')) {
        var deduction_parent = id.replace('id_div_cfine', 'id_parent_deduction');
        $('#' + deduction_parent).remove();
    }
    return false;
}

function onAdd(id_suffix) {
    let form_id = "container_" + id_suffix;
    let next_id = nextId(form_id, id_suffix);
    addField(form_id, id_suffix + next_id);
    addComment(next_id);
    return false;
}

function addField(form_id, id_suffix) {
    let div = $('#deduction_bonus_init').html().replace(/__prefix__/g, id_suffix);
    $('#' + form_id + ' .in').append(div);
}

function addComment(id) {
    let div = $('#deduction_comment_init').html();
    div = div.replace(/__prefix__/g, id);
    div = div.replace(/__date_prefix__/g, new Date().toJSON().slice(0, 10).split('-').reverse().join('.'));
    $('#deductions_0').append(div);
}

$('body').on("input", ".cfines input", function () {
    let id = $(this).attr('id').replace('cfine', 'deduction');
    let el = $('#' + id);
    if (id.includes('comment')) {
        let re = /"(.*)"/;
        let newstr = el.text().replace(re, '"' + $(this).val() + '"');
        el.html(newstr + "<br>");
    }
    else el.html($(this).val());
    el.parent().parent().show();
});

$(document).on('submit', '#deduction_fine_bonus_form', function () {
    $('#result').html('Загрузка...');
    $.ajax({
        type: $(this).attr('method'),
        url: this.action,
        data: $(this).serialize(),
        context: this,
        success: function (data) {
            $('#result').html('Данные сохранены!');
            let table = $('#calendar').DataTable();
            table.cell(data.row, (data.column + 6)).data(data.cell_data);
            table.cell(data.row, table.cell('.total_fine').index().column).data(data.total_fine);
            table.cell(data.row, table.cell('.total_deduction').index().column).data(data.total_deduction);
            table.cell(data.row, table.cell('.total_bonus').index().column).data(data.total_bonus);
            table.cell(data.row, table.cell('.total_amount').index().column).data(data.total_amount);
            table.draw();
            $('.popup').magnificPopup({type: 'ajax',});
            var magnificPopup = $.magnificPopup.instance;
            magnificPopup.updateItemHTML();
        },
        error: function (data) {
            $('#result').html('Что-то пошло не так...');
        }
    });
    return false;
});
/*
$("form").keypress(function (e) {
    //Enter key
    if (e.which == 13) {
        return false;
    }
});
*/

