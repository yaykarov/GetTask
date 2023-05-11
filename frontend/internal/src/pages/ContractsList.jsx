import React from 'react';

import { saveAs } from 'file-saver';

import { Spin } from 'antd';

import ContractsActions from '../components/ContractsActions.jsx';
import ContractsErrors from '../components/ContractsErrors.jsx';
import ContractsFilter from '../components/ContractsFilter.jsx';
import { ColumnsFilter } from '../components/ColumnsFilter.jsx';
import { ContractsTable } from '../components/ContractsTable.jsx';

import { SingleJsonFetcher } from '../utils/fetch.jsx';

import { getCookie } from '../utils/cookies.jsx';

import '../components/Common.css';


export class ContractsList extends React.Component {
    constructor(props) {
        super(props);

        this.fetcher = new SingleJsonFetcher();

        this.contracts_table = React.createRef();

        const columns_initial = [
            {
                title: 'ФИО',
                data: 'worker',
                checked: true,
                required: true,
            },
            {
                title: 'Номер',
                data: 'number',
                checked: true,
                required: true,
            },
            {
                title: 'Подрядчик',
                data: 'contractor',
                checked: true,
            },
            {
                title: 'Тип',
                data: 'cont_type',
                checked: true,
            },
            {
                title: 'Дата заключения',
                data: 'begin_date',
                checked: true
            },
            {
                title: 'Дата окончания',
                data: 'end_date',
                checked: true
            }
        ];

        this.state = {
            fetching: false,
            columns: columns_initial,
            contracts_filter: 'to_register',
            errors: undefined,
        };
    }

    onColumnsFilterUpdate = (values) => {
        this.setState(
            state => {
                for (let i = 0; i < state.columns.length; ++i) {
                    state.columns[i].checked = values[state.columns[i].data];
                }

                return state;
            }
        );
    }

    onContractsFilterUpdate = (values) => {
        this.setState({ contracts_filter: values.filter });
    }

    onContractAction = async (values) => {
        let is_update_action = ['set_contractor', 'set_begin_date', 'set_end_date'].includes(
            values.action
        );

        let base_url = this.props.urls.download_notifications_url;
        let method = 'GET';
        if (is_update_action) {
            base_url = this.props.urls.change_contracts_url;
            method = 'POST';
        }

        if (is_update_action) {
            this.setState({ fetching: true });
        }

        let url = new URL(base_url, window.location);
        for (let [key, value] of Object.entries(values)) {
            url.searchParams.set(key, value);
        }
        const checked = this.contracts_table.current.checked();
        checked.forEach(
            pk => {
                url.searchParams.append('id', pk);
            }
        );

        let response = await this.fetcher.fetch(
            url,
            {
                method: method,
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                }),
            }
        );

        // Assume it is normal zip file with documents
        if (response instanceof Blob) {
            saveAs(response, 'notifications.zip');
        } else if (response.errors) {
            this.setState({ errors: response.errors });
        }

        if (is_update_action) {
            this.setState({ fetching: false });
        }
    }

    onErrorsCancel = () => {
        this.setState({ errors: undefined });
    }

    render() {
        let components = [
            (
                <h
                    key='header'
                    className='rh-header'
                >
                    Договора
                </h>
            ),
            (
                <ContractsActions
                    key='contracts_actions'
                    urls={this.props.urls}
                    onSubmit={this.onContractAction}
                />
            ),
            (
                <ContractsFilter
                    key='contracts_filter'
                    onFilterUpdate={this.onContractsFilterUpdate}
                    filter={this.state.contracts_filter}
                />
            ),
            (
                <ColumnsFilter
                    key='columns_filter'
                    columns={this.state.columns}
                    onFilterUpdate={this.onColumnsFilterUpdate}
                />
            ),
            (
                <ContractsErrors
                    key='errors'
                    visible={!!this.state.errors}
                    errors={this.state.errors}
                    onCancel={this.onErrorsCancel}
                />
            ),
        ];
        if (this.state.fetching) {
            components.push(
                <Spin
                    key='spinner'
                    size='large'
                    spinning={true}
                    style={{ width: '100%'}}
                />
            );
        } else {
            components.push(
                <ContractsTable
                    key='table'
                    ref={this.contracts_table}
                    columns={this.state.columns.filter(item => item.checked)}
                    urls={this.props.urls}
                    data_extra={{ filter: this.state.contracts_filter }}
                />
            );
        }
        return components;
    }
}

