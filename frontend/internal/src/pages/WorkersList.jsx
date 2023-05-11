import React from 'react';

import { Button } from 'antd';

import { ColumnsFilter } from '../components/ColumnsFilter.jsx';
import { WorkersTable } from '../components/WorkersTable.jsx';

import '../components/Common.css';


export class WorkersList extends React.Component {
    constructor(props) {
        super(props);

        const columns_initial = [
            {
                title: 'Дата занесения',
                data: 'input_date',
                checked: true,
            },
            {
                title: 'ФИО',
                data: 'worker',
                checked: true,
                required: true,
            },
            {
                title: 'Гражданство',
                data: 'citizenship',
                checked: true,
            },
            {
                title: 'Дата окончания МК',
                data: 'm_date_of_exp',
                checked: false,
            },
            {
                title: 'Серия МК',
                data: 'mig_series',
                checked: false,
            },
            {
                title: 'Номер МК',
                data: 'mig_number',
                checked: false,
            },
            {
                title: 'Должность',
                data: 'position',
                checked: true,
            },
            {
                title: 'Дата посл. выхода',
                data: 'last_turnout_date',
                checked: false,
            },
            {
                title: 'Посл. выход на',
                data: 'last_turnout_customer',
                checked: false,
            },
            {
                title: 'Кол-во выходов',
                data: 'turnouts_count',
                checked: true,
            },
            {
                title: 'Кол-во договоров',
                data: 'contracts_count',
                checked: true,
            },
            {
                title: 'Телефон',
                data: 'tel_number',
                checked: true,
            }
        ];

        this.state = {
            columns: columns_initial
        };
    }

    onFilterUpdate = (values) => {
        this.setState(
            state => {
                for (let i = 0; i < state.columns.length; ++i) {
                    state.columns[i].checked = values[state.columns[i].data];
                }

                return state;
            }
        );
    }

    render() {
        return [
            (
                <h
                    className='rh-header'
                >
                    Физ. лица
                </h>
            ),
            (
                <ColumnsFilter
                    columns={this.state.columns}
                    onFilterUpdate={this.onFilterUpdate}
                />
            ),
            (
                <Button
                    href={this.props.urls.new_worker_url}
                    target='_blank'
                    style={{ marginLeft: '20px' }}
                >
                    Добавить рабочего
                </Button>
            ),
            (
                <WorkersTable
                    columns={this.state.columns.filter(item => item.checked)}
                    urls={this.props.urls}
                />
            )
        ];
    }
}
