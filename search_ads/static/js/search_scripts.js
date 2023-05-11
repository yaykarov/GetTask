
$("form[name=search_params]").on('submit',function() {
    $.ajax({
        method: $(this).attr('method'),
        url: $(this).attr('action'),
        data: $(this).serializeArray(),

        success: function(response) {
            data = response['data'];
            table = $(".res_table")[0];
            $(".res_table").find(".table_row").remove();
            keys = ["keyword","position","site","date_time","id_or_tel","title","url"];
            for (row of data) {
                tr = document.createElement('tr');
                tr.className = "table_row";
                for (key of keys) {
                    td = document.createElement("td");
                    if (key=="id_or_tel" && row['id'])
                        td.innerHTML = row['id'];
                    else if (key=="id_or_tel" && row["tel"])
                        td.innerHTML = row['tel'];
                    else if (key=='ref') {
                        a = document.createElement('a');
                        a.href = row[key];
                        a.innerHTML = "ссылка";
                        td.appendChild(a);
                    } else
                        td.innerHTML = row[key];
                    td.className = key;
                    tr.appendChild(td);
                }
                table.appendChild(tr);
            }
        },
        error: function(data) {
            $(this).find('.result').html('Ошибка ('+data+")");
        }
    });
    return false;
});