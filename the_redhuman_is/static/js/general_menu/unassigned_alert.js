function checkUnassigned(url) {
    $.ajax({
        type: 'GET',
        url: url,
        success: function(data) {
            warning = $("#generalMenuWarning");
            if (data.count > 0) {
                warning.html('Есть пропущенные звонки от соискателей, требующие срочной обработки, ' + data.count + ' шт. ' + 'Время ожидания: ' + data.time + '.');
                warning.show(200);
            } else {
                warning.hide(200);
            }
        },
        error: function(data) {
        }
    });
}

let promise;

function sleep(time) {
  return new Promise((resolve) => setTimeout(resolve, time));
}

async function checkLoop(url) {
    for (;;) {
        checkUnassigned(url);
        await sleep(45000);
    }
}

function startPolling(url) {
    promise = checkLoop(url);
}

