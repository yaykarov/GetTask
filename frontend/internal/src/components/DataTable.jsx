import React from 'react';

import 'datatables.net-dt/css/jquery.dataTables.css';
import 'datatables.net-bs4/css/dataTables.bootstrap4.css';
import 'datatables.net-bs4';

import './DataTable.css';

const $ = require('jquery');
$.DataTable = require('datatables.net');


let lastTableId = 0;

function getTableId() {
    const tableId = lastTableId;
    lastTableId += 1;
    return tableId;
}


export class DataTable extends React.Component {
    constructor(props) {
        super(props);

        this.checked = new Set();

        this.tableId = getTableId();
    }

    wrapperClass = () => {
        return 'data-table-wrapper-' + this.tableId;
    }

    selectAllCheckboxId = () => {
        return 'datatable-' + this.tableId + '-select-all';
    }

    checkboxClass = () => {
        return 'datatable-' + this.tableId + '-selection';
    }

    getTableId = () => {
        return 'id_datatable_' + this.tableId;
    }

    dataTable = () => {
        return $('#' + this.getTableId());
    }

    columns = (props) => {
        let result = props.columns.slice();
        if (props.enable_checkboxes) {
            result.unshift(
                {
                    'title': (
                        '<input type="checkbox" id="' +
                        this.selectAllCheckboxId() + 
                        '">'
                    ),
                    'data': 'checkbox',
                }
            );
        }

        return result;
    }

    processData = (props, json) => {
        let data;
        if (props.data_process) {
            data = props.data_process(json);
        } else {
            data = json.data;
        }

        if (props.enable_checkboxes) {
            for (let i = 0; i < data.length; ++i) {
                data[i].checkbox = (
                    '<input type="checkbox" class="' + 
                    this.checkboxClass() +
                    '" id="datatable-' + this.tableId + '-checkbox-' + data[i].pk +
                    '" name="id" value="' + data[i].pk + '"' +
                    (this.checked.has(String(data[i].pk))? ' checked="true" ' : '') +
                    '>'
                );
            }
        }

        return data;
    }

    dataTableParams = (props) => {
        let ajax = {
            url: props.data_url,
            data: props.data_extra,
            dataSrc: (json) => { return this.processData(props, json); }
        };

        let params = {
            dom: '<"' + this.wrapperClass() + '"lftipr>',
            columns: this.columns(props),
            serverSide: true,
            ajax: ajax,

            fixedHeader: {
                header: true,
                footer: true
            },
            processing: true,
            lengthMenu: [[20, 100, 200], [20, 100, 200]],
            orderCellsTop: true,
            sPaginationType: 'full_numbers',
            oLanguage: {
                'sLengthMenu': 'Отображено _MENU_ записей на страницу',
                'sSearch': 'Поиск:',
                'sZeroRecords': 'Ничего не найдено - извините',
                'sInfo': 'Показано с _START_ по _END_ из _TOTAL_ записей',
                'sInfoEmpty': 'Показано с 0 по 0 из 0 записей',
                'sInfoFiltered': '(filtered from _MAX_ total records)',
                'oPaginate': {
                    'sFirst': 'Первая',
                    'sNext':'>',
                    'sPrevious':'<',
                    'sLast':'Последняя',
                }
            },
        };

        if (props.enable_checkboxes) {
            params.columnDefs = [{
                orderable: false,
                targets: 0
            }];
            params.order = [[1, 'asc']];
        }

        return params;
    }

    initDataTable = (props) => {
        this.dataTable().DataTable(this.dataTableParams(props));

        const checkboxClass = '.' + this.checkboxClass();
        $(document).on(
            'click',
            '#' + this.selectAllCheckboxId(),
            function() {
                $(checkboxClass).prop('checked', this.checked).trigger('change');
            }
        );

        let table = this;
        $(document).on(
            'change',
            checkboxClass,
            function() {
                if (this.checked) {
                    table.checked.add(this.value);
                } else {
                    table.checked.delete(this.value);
                }
            }
        );
    }

    componentDidMount() {
        this.initDataTable(this.props);
    }

    componentWillUnmount() {
        this.dataTable().DataTable().destroy();
    }

    shouldComponentUpdate(nextProps) {
        if (JSON.stringify(this.props) !== JSON.stringify(nextProps)) {
            this.dataTable().DataTable().clear();
            this.dataTable().DataTable().destroy();
            this.dataTable().html('');

            this.initDataTable(nextProps);
        }

        return false;
    }

    render() {
        return (
            <div>
                <table
                    id={this.getTableId()}
                    className='table table-hover rh-table'
                />
            </div>
        );
    }
}
