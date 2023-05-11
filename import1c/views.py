import datetime

from django.db import transaction
from django.db.models import (
    Exists,
    OuterRef,
)
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.contrib import messages

from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
)

from finance.models import (
    Account,
    Operation
)

from the_redhuman_is import forms
from the_redhuman_is.auth import staff_account_required
from the_redhuman_is.views.utils import get_first_last_day

from the_redhuman_is.models import (
    Expense,
    ExpensePaymentOperation,
    Reconciliation,
    ReconciliationPaymentOperation,
    Worker,
    WorkerSelfEmploymentData,
    find_closest_paysheet_entry,
    fix_entry_amount_if_need_to,
)
from import1c.models import (
    AccountMapping,
    Import,
    ImportedNode,
    unimported_operations_count,
)
from import1c.forms import Upload1cFileForm
from import1c import parser


@staff_account_required
def upload_1c_file(request):
    form = Upload1cFileForm(request.POST or None, request.FILES or None)

    if not form.is_valid():
        first_day, last_day = get_first_last_day(request)

        imports = Import.objects.filter(
            created__gte=first_day,
            created__lt=(last_day + datetime.timedelta(days=1))
        )

        return render(
            request,
            'import1c/upload_1c_file.html',
            {
                'form': form,
                'interval_form' : forms.DaysIntervalForm(
                    initial={
                        'first_day': first_day,
                        'last_day': last_day
                    }
                ),
                'imports': imports
            }
        )

    f = form.cleaned_data
    file_content = f['uploaded_file'].read().decode('cp1251')
    nodes = list(parser.parse(file_content))

    transaction.set_autocommit(False)
    spoint = transaction.savepoint()

    theimport = Import(
        file_content=file_content,
        file_name=f['uploaded_file'].name,
        comment=(f['comment'] or '')
    )
    theimport.save()

    add = []
    n_docs = 0
    n_already = 0

    for i, node in enumerate(nodes):
        if ImportedNode.is_saved(node):
            n_already += 1
            continue

        db_node = ImportedNode.from_node(theimport, i, node)
        add.append(db_node)
        if isinstance(node, parser.Document):
            n_docs += 1

    if n_docs:
        # not only header and account info
        ImportedNode.objects.bulk_create(add)

        transaction.savepoint_commit(spoint)

        messages.add_message(
            request, messages.SUCCESS,
            'Импорт №{}. Добавлено банковских операций: {}. Пропущено дублей (уже импортировались раньше): {}'.format(theimport.pk, n_docs, n_already)
        )
    else:
        transaction.savepoint_rollback(spoint)

        if n_already:
            msg = 'все {0} операции уже импортировались'.format(n_already)
        else:
            msg = 'передан пустой файл'

        messages.add_message(
            request, messages.WARNING,
            'Ничего не добавлено: {0}.'.format(msg)
        )

    transaction.commit()

    return redirect(reverse('import1c:upload-1c-file'))


@staff_account_required
def import_operation(request):
    bank_statement_item = ImportedNode.objects.filter(
        operation__isnull=True,
        doc_type=ImportedNode.DOCUMENT_DOC_TYPE
    ).order_by(
        'theimport__created',
        'position_in_file'
    ).first()

    if bank_statement_item is None:
        return redirect('the_redhuman_is:operating_account_tree')

    document = bank_statement_item.to_node()
    header = bank_statement_item.document_header().to_node()
    is_incoming = document.is_incoming(header)
    comment = document.comment(is_incoming)

    debit, credit = AccountMapping.find_autocomplete(document)

    bank_account = document['ПолучательСчет']
    bank_identification_code = document['ПолучательБИК']
    tax_number = document['ПолучательИНН']

    try:
        wse_data = WorkerSelfEmploymentData.objects.get(
            bank_account=bank_account,
            bank_identification_code=bank_identification_code,
            deletion_ts__isnull=True,
        )

        debit = wse_data.worker.worker_account.account

    except (ObjectDoesNotExist, MultipleObjectsReturned):
        try:
            worker = Worker.objects.annotate(
                wse_data_exists=Exists(
                    WorkerSelfEmploymentData.objects.filter(
                        worker=OuterRef('pk'),
                        tax_number=tax_number,
                        deletion_ts__isnull=True,
                    )
                )
            ).filter(
                wse_data_exists=True
            ).get()

            debit = worker.worker_account.account

        except (ObjectDoesNotExist, MultipleObjectsReturned):
            pass

    expense_form = forms.ExpenseSelectionForm()
    expense_form.fields['expense'].required = False

    reconciliation_form = forms.UnpaidReconciliationSelectionForm()
    reconciliation_form.fields['reconciliation'].required = False

    account_selection_form = forms.AccountsSelectionForm(
        initial={'debit': debit, 'credit': credit}
    )

    data = {
        'unimported_operations_count': unimported_operations_count(),
        'expense_form': expense_form,
        'reconciliation_form': reconciliation_form,
        'account_selection_form': account_selection_form,
        'imported_node': bank_statement_item,
        'date': document.getdate('Дата'),
        'amount': document.getmoney('Сумма'),
        'comment': comment,
        'node_kv': sorted(document.items()),
        'accounts': bank_statement_item.document_accounts_info(),
    }

    if debit:
        data['debet'] = debit
    if credit:
        data['credit'] = credit

    return render(request, 'import1c/import_operation.html', data)


def _add_operation_error(error_text):
    return JsonResponse({'status': 'error', 'error_text': error_text})


# TODO refactor? because it partially duplicates the_redhuman_is.views.operating_account.add_operation()
@staff_account_required
def add_operation(request):
    try:
        debit_pk = int(request.POST.get('debit'))
    except ValueError:
        return _add_operation_error('Укажите Дебет.')

    try:
        credit_pk = int(request.POST.get('credit'))
    except ValueError:
        return _add_operation_error('Укажите Кредит.')

    if debit_pk == credit_pk:
        return _add_operation_error('Кредит должен отличаться от Дебета.')

    try:
        debit = Account.objects.get(pk=debit_pk)
    except Account.DoesNotExist:
        return _add_operation_error('Дебет не найден, id ({}).'.format(debit_pk))

    try:
        credit = Account.objects.get(pk=credit_pk)
    except Account.DoesNotExist:
        return _add_operation_error('Кредит не найден, id ({}).'.format(credit_pk))

    imported_node_pk = request.POST.get('imported_node')
    try:
        imported_node_pk = int(imported_node_pk)
    except ValueError:
        return _add_operation_error(
            'ImportedNode: неправильный id ({}).'.format(request.POST.get('imported_node'))
        )

    comment = request.POST.get('comment', '').strip()
    expense_pk = request.POST.get('expense')
    reconciliation_pks = request.POST.getlist('reconciliation')

    with transaction.atomic():
        imported_node = None
        try:
            imported_node = ImportedNode.objects.select_for_update().get(pk=imported_node_pk)
            if imported_node.operation:
                return _add_operation_error(
                    f'ImportedNode {imported_node_pk} уже привязан к операции'
                )
        except ImportedNode.DoesNotExist:
            return _add_operation_error(
                'ImportedNode: не найден id ({}).'.format(imported_node_pk)
            )

        document = imported_node.to_node()
        date = document.getdate('Дата')
        timepoint = datetime.datetime(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=0,
            minute=0
        )
        amount = document.getmoney('Сумма')

        if reconciliation_pks:
            if len(reconciliation_pks) == 1:
                prefix = f'Оплата по сверке №{reconciliation_pks[0]}. '
            else:
                numbers = ', №'.join(reconciliation_pks)
                prefix = f'Оплата по сверкам №{numbers}. '
            comment = prefix + comment

        operation = None

        def _create_new_operation():
            nonlocal operation
            operation = Operation.objects.create(
                timepoint=timepoint,
                author=request.user,
                comment=comment,
                debet=debit,
                credit=credit,
                amount=amount
            )

            if expense_pk:
                expense = Expense.objects.get(pk=expense_pk)
                ExpensePaymentOperation.objects.create(
                    expense=expense,
                    operation=operation
                )
            elif reconciliation_pks:
                for reconciliation_pk in reconciliation_pks:
                    reconciliation = Reconciliation.objects.get(pk=reconciliation_pk)
                    ReconciliationPaymentOperation.objects.create(
                        reconciliation=reconciliation,
                        operation=operation
                    )

        try:
            operating_account = debit.worker_account

        except ObjectDoesNotExist:
            _create_new_operation()

        else:
            worker = operating_account.worker

            entry = find_closest_paysheet_entry(worker, date, amount)
            if entry:
                fix_entry_amount_if_need_to(entry, amount, request.user)

                operation = entry.operation

                # getting around is_closed flag
                # Todo: get rid of this (don't break standard is_closed mechanism)
                Operation.objects.filter(pk=operation.pk).update(
                    credit=credit,
                    amount=amount,
                    comment=f'{operation.comment}\n{comment}'
                )
                operation.credit = credit
            else:
                _create_new_operation()

        imported_node.operation = operation
        imported_node.save()

        AccountMapping.save_autocomplete(document, operation)

    messages.add_message(request, messages.SUCCESS, 'Добавлена операция «{0}».'.format(operation))

    return JsonResponse({'status': 'ok'})
