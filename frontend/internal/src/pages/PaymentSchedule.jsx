import React from 'react';

import 'moment/locale/ru';
import moment from 'moment';

import { Spin } from 'antd';

import PaymentScheduleModal from '../components/PaymentScheduleModal.jsx';
import PaymentScheduleTable from '../components/PaymentScheduleTable.jsx';
import WrappedRangeForm from '../components/RangeForm.jsx';

import { SingleJsonFetcher } from '../utils/fetch.jsx';

import { getCookie } from '../utils/cookies.jsx';

import '../components/Common.css'


// Todo
const DATE_FORMAT = 'DD.MM.YYYY';


class PaymentSchedule extends React.Component {
    constructor(props) {
        super(props);

        this.fetcher = new SingleJsonFetcher();

        this.state = {
            first_day: this.props.first_day,
            last_day: this.props.last_day,

            accounts: [],

            modal_visible: false,
            modal_title: '',
            modal_content_fetching: false,
            modal_content: null,
            modal_initial: {},

            fetching: false,
        }
    }

    onSubmitRange = (first_day, last_day) => {
        this.setState(
            {
                first_day: first_day,
                last_day: last_day,

                accounts: [],
            },
            this.fetchSchedule
        );
    }

    onAccountToggle = (index, pk, type) => {
        const account = this.state.accounts[index];
        if (account.pk !== pk) {
            return;
        }

        let expanded = false;
        if (type === 'debit' && account.debit_operations) {
            expanded = true;
        }
        if (type === 'credit' && account.credit_operations) {
            expanded = true;
        }

        if (expanded) {
            this.setState(
                state => {
                    if (state.accounts[index].pk !== pk) {
                        return;
                    }
                    if (type === 'debit') {
                        state.accounts[index].debit_operations = null;
                    }
                    if (type === 'credit') {
                        state.accounts[index].credit_operations = null;
                    }
                    return state;
                }
            );
        } else {
            this.expand(index, pk, type);
        }
    }

    onAmountClick = (root_account, corresponding_account, day_index, type) => {
        const first_day = moment(this.state.first_day, DATE_FORMAT);
        const day = first_day.clone().add(day_index, 'days');

        const title = (type === 'debit'? 'Доход ' : 'Расход ') + day.format(DATE_FORMAT);

        let opposite_type = 'debit'
        if (type === 'debit') {
            opposite_type = 'credit';
        }

        let modal_initial = { date: day };
        modal_initial[type] = { key: root_account.pk, label: root_account.name };
        if (corresponding_account) {
            modal_initial[opposite_type] = {
                key: corresponding_account.pk,
                label: corresponding_account.name
            };
        }

        this.setState(
            {
                modal_visible: true,
                modal_title: title,
                modal_fetching: true,
                modal_content: null,
                modal_initial: modal_initial
            }
        );

        let url = new URL(this.props.urls.day_operations_url, window.location);
        url.searchParams.set('day', day.format(DATE_FORMAT));
        url.searchParams.set('root_account', root_account.pk);
        if (corresponding_account) {
            url.searchParams.set('corresponding_account', corresponding_account.pk);
        }
        url.searchParams.set('type', type);

        this.fetcher.fetch(
            url
        ).then(
            response => {
                this.setState({ modal_fetching: false });

                if (response.status === 'ok') {
                    this.setState({ modal_content: response.data });
                } else {
                    // Todo: show message?
                }
            }
        );
    }

    onCreateOperation = async (values) => {
        this.clearModal();
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.create_operation_url, window.location);
        url.searchParams.set('date', values.date.format(DATE_FORMAT));
        url.searchParams.set('comment', values.comment);
        url.searchParams.set('debit', values.debit.key);
        url.searchParams.set('credit', values.credit.key);
        url.searchParams.set('amount', values.amount);

        let response = await this.fetcher.fetch(
            url,
            {
                method: 'POST',
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                }),
            }
        );

        if (response.status === 'ok') {
            await this.updateAndReExpand();
        } else {
            // Todo: show error message?
            this.setState({ fetching: false });
        }
    }

    onDeleteOperation = async (pk) => {
        this.clearModal();
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.delete_operation_url, window.location);
        url.searchParams.set('pk', pk);

        let response = await this.fetcher.fetch(
            url,
            {
                method: 'POST',
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                }),
            }
        );

        if (response.status === 'ok') {
            await this.updateAndReExpand();
        } else {
            // Todo: show error message?
            this.setState({ fetching: false });
        }
    }

    updateAndReExpand = async () => {
        let expanded_debit = [];
        let expanded_credit = [];

        this.state.accounts.forEach(
            account => {
                if (account.debit_operations) {
                    expanded_debit.push(account.pk);
                }
                if (account.credit_operations) {
                    expanded_credit.push(account.pk);
                }
            }
        );

        this.fetchSchedule(
            () => {
                this.state.accounts.forEach(
                    (account, index) => {
                        if (expanded_debit.includes(account.pk)) {
                            this.expand(index, account.pk, 'debit');
                        }
                        if (expanded_credit.includes(account.pk)) {
                            this.expand(index, account.pk, 'credit');
                        }
                    }
                );
            }
        );
    }

    clearModal = () => {
        this.setState(
            {
                modal_visible: false,
                modal_title: '',
                modal_content_fetching: false,
                modal_content: null,
                modal_initial: {}
            }
        );
    }

    expand = async (index, pk, type) => {
        this.setState(
            state => {
                if (type === 'debit') {
                    state.accounts[index].debit_fetching = true;
                }
                if (type === 'credit') {
                    state.accounts[index].credit_fetching = true;
                }
                return state;
            }
        );

        let url = new URL(this.props.urls.operations_url, window.location);
        url.searchParams.set('first_day', this.state.first_day);
        url.searchParams.set('last_day', this.state.last_day);
        url.searchParams.set('account', pk);
        url.searchParams.set('type', type);

        let response = await fetch(url);
        if (response.ok) {
            let result = await response.json();
            if (result.status === 'ok') {
                this.setState(
                    state => {
                        if (state.accounts[index].pk !== pk) {
                            return;
                        }

                        if (type === 'debit') {
                            state.accounts[index].debit_operations = result.data;
                            state.accounts[index].debit_fetching = false;
                        }
                        if (type === 'credit') {
                            state.accounts[index].credit_operations = result.data;
                            state.accounts[index].credit_fetching = false;
                        }
                        return state;
                    }
                )
                return;
            }
        }

        this.setState(
            state => {
                if (type === 'debit') {
                    state.accounts[index].debit_fetching = false;
                }
                if (type === 'credit') {
                    state.accounts[index].credit_fetching = false;
                }
                return state;
            }
        );

        // Todo: something is wrong
    }

    componentDidMount() {
        this.fetchSchedule();
    }

    fetchSchedule = async (callback) => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.payment_schedule_url, window.location);
        url.searchParams.set('first_day', this.state.first_day);
        url.searchParams.set('last_day', this.state.last_day);

        let response = await this.fetcher.fetch(url);
        this.setState({ fetching: false });
        if (response.status === 'ok') {
            this.setState({ accounts: response.data }, callback);
        } else {
            // Todo: show message?
        }
    }

    render() {
        let components = [];

        components.push(
            <h
                key='title'
                className='rh-header'
            >
                Платежный календарь
            </h>
        );

        components.push(
            <WrappedRangeForm
                key='range_form'
                first_day={this.state.first_day}
                last_day={this.state.last_day}
                onSubmit={this.onSubmitRange}
            />
        );

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
                <PaymentScheduleTable
                    key='table'
                    first_day={this.state.first_day}
                    last_day={this.state.last_day}
                    accounts={this.state.accounts}
                    urls={this.props.urls}
                    onToggle={this.onAccountToggle}
                    onAmountClick={this.onAmountClick}
                />
            );
        }

        components.push(
            <PaymentScheduleModal
                urls={this.props.urls}
                visible={this.state.modal_visible}
                title={this.state.modal_title}
                fetching={this.state.modal_fetching}
                content={this.state.modal_content}
                initial={this.state.modal_initial}
                onOk={this.clearModal}
                onCancel={this.clearModal}
                onCreateOperation={this.onCreateOperation}
                onDeleteOperation={this.onDeleteOperation}
            />
        );

        return components;
    }
}


export default PaymentSchedule;
