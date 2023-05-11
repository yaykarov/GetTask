import React from 'react';

import { Button } from 'antd';
import { Col } from 'antd';
import { Modal } from 'antd';
import { Row } from 'antd';
import { Spin } from 'antd';
import { Tabs } from 'antd';

// Todo: if import this way it badly merges with "base" style
// So it is imported in the template. :(
//import 'antd/dist/antd.css'

import { message } from 'antd';

import ClaimsList from '../components/ClaimsList.jsx';
import ExpensesBlock from '../components/ExpensesBlock.jsx';
import ProviderModal from '../components/ProviderModal.jsx';
import WrappedClaimForm from '../components/ClaimForm.jsx';
import WrappedExpenseForm from '../components/ExpenseForm.jsx';
import WrappedRangeForm from '../components/RangeForm.jsx';

import { getCookie } from '../utils/cookies.jsx';


// Todo
const DATE_FORMAT = 'DD.MM.YYYY';


class App extends React.Component {
    constructor(props) {
        super(props);

        message.config({ top: 120});

        this.lastFetchId = 0;

        this.provider_modal = React.createRef();
        this.expense_form = React.createRef();
        this.claim_form = React.createRef();
        this.expense_modal_form = React.createRef();
        this.range_form_1 = React.createRef();
        this.range_form_2 = React.createRef();

        this.state = {
            fetching: false,
            provider_modal_visible: false,
            provider_modal_initial: undefined,
            expenses: [],
            expense_modal_visible: false,
            expense_modal_initial: undefined,
            first_day: this.props.first_day,
            last_day: this.props.last_day,

            claims: [],

            current_tab: 'expenses',
        };
    }

    onTabChanged = (current_tab) => {
        this.setState({ current_tab: current_tab });
    }

    onSubmitProvider = (data) => {
        const initial = this.state.provider_modal_initial;
        this.setState(
            {
                provider_modal_visible: false,
                provider_modal_initial: undefined,
            }
        );
        if (initial) {
            data.pk = initial.pk;
        }
        this.updateProvider(data);
    }

    onEditProvider = (expense_id) => {
        this.editProvider(expense_id);
    }

    onProviderModalCancel = () => {
        this.setState(
            {
                provider_modal_visible: false,
                provider_modal_initial: undefined,
            }
        );
    }

    onSubmitExpense = (data) => {
        this.setState(
            {
                expense_modal_visible: false,
                expense_modal_initial: undefined,
            }
        );
        this.createExpense(data);
    }

    onExpenseAction = (expense_id, action, comment) => {
        if (action === 'edit') {
            this.editExpense(expense_id);
        } else {
            this.updateExpense(expense_id, action, comment);
        }
    }

    onExpenseEditCancel = () => {
        this.setState(
            {
                expense_modal_visible: false,
                expense_modal_initial: undefined,
            }
        );
    }

    onSubmitClaim = async (data, files) => {
        this.setState({ fetching: true });
        const result = await this.post(
            this.props.urls.create_claim_url,
            data,
            files
        )
        this.setState({ fetching: false });

        if (!result) {
            return;
        }

        if (result.status === 'ok') {
            message.success({ duration: 1.5, content: 'Претензия внесена.' });

            this.updateExpensesAndClaims();
        } else if (result.message) {
            message.error({ content: result.message });
        }
    }

    onSubmitRange = (first_day, last_day) => {
        this.setState(
            {
                first_day: first_day,
                last_day: last_day
            },
            this.updateExpensesAndClaims
        )
    }

    setStateKeepForms = (state) => {
        const form = this.expense_form.current;
        let expenseData = null;
        if (form) {
            expenseData = form.getFieldsValue();
        }

        const claim_form = this.claim_form.current;
        let claim_data = null;
        if (claim_form) {
            claim_data = claim_form.getFieldsValue();
        }

        this.setState(
            state,
            () => {
                if (form && expenseData) {
                    form.setFieldsValue(expenseData);
                }

                if (claim_form && claim_data) {
                    claim_form.setFieldsValue(claim_data);
                }
            }
        );
    }

    headers = () => {
        return {
            'X-CSRFToken': getCookie('csrftoken'),
        }
    }

    normalizedProviderData = (data) => {
        let result = {
            name: data.name,
            cost_type_group: data.cost_type_group
        };
        if (data.pk) {
            result['pk'] = data.pk;
        }
        if (data.tax_code) {
            result['tax_code'] = data.tax_code;
        }
        if (data.cost_type_group === 'administration') {
            result.cost_type_name = data.administration_cost_type.label;
        } else if (data.cost_type_group === 'industrial') {
            result.cost_type_name = data.industrial_cost_type.label;
            result.customer = data.customer.key
        }

        return result;
    }

    // Todo: move this to expense form
    normalizedExpenseData = (data) => {
        let result = Object.assign({}, data);
        if (data.days_interval) {
            result.first_day = data.days_interval[0].format(DATE_FORMAT);
            result.last_day = data.days_interval[1].format(DATE_FORMAT);
        }
        result.provider = data.provider.key;
        delete result.days_interval;
        if (data.cost_type_group === 'administration') {
            result.cost_type_pk = data.administration_cost_type.key;
            delete result.administration_cost_type;
        } else if (data.cost_type_group === 'industrial') {
            result.cost_type_pk = data.industrial_cost_type.key;
            delete result.industrial_cost_type;
            result.customer = data.customer.key;
        } else if (data.cost_type_group === 'material') {
            result.cost_type_pk = data.material_type.key;
            delete result.material_type;
            result.customer = data.customer.key;
        }
        return result;
    }

    updateProvider = async (data) => {
        this.setState({ fetching: true });
        let result = await this.post(
            this.props.urls.update_provider_url,
            this.normalizedProviderData(data)
        );
        this.setState({ fetching: false });

        if (!result) {
            return;
        }

        let normalMessage = data.pk? 'Поставщик изменен.' : 'Поставщик создан.';

        if (result.status === 'ok') {
            message.success({ duration: 1.5, content: normalMessage });
        } else if (result.message) {
            message.error({ content: result.message });
        }

        this.updateExpensesAndClaims();
    }

    createExpense = async (data) => {
        this.setState({ fetching: true });
        let result = await this.post(
            this.props.urls.create_expense_url,
            this.normalizedExpenseData(data)
        );
        this.setState({ fetching: false });

        if (!result) {
            return;
        }

        if (result.status === 'ok') {
            message.success({ duration: 1.5, content: 'Расход заявлен.' });
        } else if (result.message) {
            message.error({ content: result.message });
        }

        this.updateExpensesAndClaims();
    }

    fetchData = async (url) => {
        this.lastFetchId += 1;
        const fetchId = this.lastFetchId;

        try {
            let response = await fetch(url, { headers: this.headers() });
            if (fetchId !== this.lastFetchId || !response.ok) {
                // Todo: exception?
                return null;
            }

            return await response.json();
        } catch (exception) {
            return null;
        }
    }

    fetchExpenses = async () => {
        let url = new URL(this.props.urls.actual_expenses_url, window.location);
        url.searchParams.set('first_day', this.state.first_day);
        url.searchParams.set('last_day', this.state.last_day);
        return await this.fetchData(url);
    }

    fetchExpense = async (expense_id) => {
        let url = new URL(this.props.urls.expense_detail_url, window.location);
        url.searchParams.set('pk', expense_id);
        return await this.fetchData(url);
    }

    fetchProvider = async (expense_id) => {
        let url = new URL(this.props.urls.provider_detail_url, window.location);
        url.searchParams.set('pk', expense_id);
        return await this.fetchData(url);
    }

    fetchClaims = async () => {
        let url = new URL(this.props.urls.claims_list_url, window.location);
        url.searchParams.set('first_day', this.state.first_day);
        url.searchParams.set('last_day', this.state.last_day);
        return await this.fetchData(url);
    }

    updateExpenses = async (quiet=false) => {
        if (!quiet) {
            this.setState({ fetching: true });
        }
        let body = await this.fetchExpenses();
        if (!quiet) {
            this.setState({ fetching: false });
        }
        if (body && body.status === 'ok') {
            this.setStateKeepForms({ expenses: body.expenses || [] });
        }
    }

    updateClaims = async () => {
        let body = await this.fetchClaims();
        if (body && body.status === 'ok') {
            this.setStateKeepForms({ claims: body.data || []});
        }
    }

    updateExpensesAndClaims = async (quiet=false) => {
        if (!quiet) {
            this.setState({ fetching: true });
        }

        await this.updateClaims();
        await this.updateExpenses(true);

        if (!quiet) {
            this.setState({ fetching: false });
        }
    }

    updateExpense = async (expense_id, action, comment) => {
        this.setState({ fetching: true });
        let result = await this.post(
            this.props.urls.update_expense_url,
            {
                pk: expense_id,
                action: action,
                comment: comment
            }
        );
        this.setState({ fetching: false });

        if (!result) {
            return;
        }

        if (result.status !== 'ok' && result.message) {
            message.error({ content: result.message });
        }

        this.updateExpensesAndClaims();
    }

    editProvider = async (expense_id) => {
        this.setState({ fetching: true });
        let data = await this.fetchProvider(expense_id);
        this.setState({ fetching: false });

        if (!data) {
            return;
        }

        if (data.status === 'ok') {
            this.setState(
                {
                    provider_modal_visible: true,
                    provider_modal_initial: data.data
                }
            );
        } else if (data.message) {
            message.error({ content: data.message });
        }
    }

    editExpense = async (expense_id) => {
        this.setState({ fetching: true });
        let data = await this.fetchExpense(expense_id);
        this.setState({ fetching: false });

        if (!data) {
            return;
        }

        if (data.status === 'ok') {
            this.setState(
                {
                    expense_modal_visible: true,
                    expense_modal_initial: data.data
                }
            );
        } else if (data.message) {
            message.error({ content: data.message });
        }
    }

    post = async (post_url, data, files=[]) => {
        this.lastFetchId += 1;
        const fetchId = this.lastFetchId;
        let url = new URL(post_url, window.location);
        for (let [key, value] of Object.entries(data)) {
            url.searchParams.set(key, value);
        }
        const form = new FormData();
        files.forEach(
            file => {
                form.append('files', file, file.name);
            }
        );
        try {
            let response = await fetch(
                url,
                {
                    method: 'POST',
                    headers: this.headers(),
                    body: form
                }
            );
            if (fetchId !== this.lastFetchId) {
                // Todo: exception?
                return null;
            }
            if (!response.ok) {
                return {
                    message: 'Что-то пошло не так.'
                };
            }
            let body = await response.json();

            return body;
        } catch (exception) {
            return {
                message: 'Что-то пошло не так.'
            };
        }
    }

    componentDidMount() {
        this.timerId = setInterval(
            () => {
                const form = this.expense_form.current;
                if (form.getFieldValue('cost_type_group')) {
                    return;
                }
                if (this.state.fetching) {
                    return;
                }
                if (this.state.provider_modal_visible) {
                    return;
                }
                if (this.state.expense_modal_visible) {
                    return;
                }
                this.updateExpensesAndClaims(true);
            },
            200000
        );

        this.updateExpensesAndClaims(false);
    }

    componentWillUnmount() {
        clearInterval(this.timerId);
    }

    expensesTab = () => {
        let components = [];

        components.push(
            <Row
                key='provider_row'
                type='flex'
                align='middle'
            >
                <Col
                    key='expense_form'
                    span={1}
                    push={23}
                >
                    <Button
                        key='provider_button'
                        onClick={() => this.setState({ provider_modal_visible: true })}
                        style={{ float: 'right' }}
                    >
                    Завести поставщика
                    </Button>
                </Col>
            </Row>
        );
        components.push(
            <Row
                key='expense_row'
                type='flex'
                align='middle'
            >
                <Col
                    key='expense_form'
                    span={24}
                >
                    <WrappedExpenseForm
                        key='expense_form'
                        ref={this.expense_form}
                        urls={this.props.urls}
                        show_administration_expenses={this.props.show_administration_expenses}
                        show_submit_button
                        onSubmit={this.onSubmitExpense}
                    >
                    </WrappedExpenseForm>
                </Col>
            </Row>
        );

        components.push(
            <h5
                key='interval_title'
                className='mt-4 mb-4'
                style={{ color: 'black' }}
            >
                Расходы за интервал
            </h5>
        );
        components.push(
            <WrappedRangeForm
                key='range_form_1'
                ref={this.range_form_1}
                first_day={this.state.first_day}
                last_day={this.state.last_day}
                onSubmit={this.onSubmitRange}
            />
        );
        components.push(
            <ExpensesBlock
                key='expenses_block'
                items={this.state.expenses}
                first_day={this.state.first_day}
                last_day={this.state.last_day}
                urls={this.props.urls}
                onExpenseAction={this.onExpenseAction}
                onEditProvider={this.onEditProvider}
            />
        );

        return components;
    }

    claimsTab = () => {
        let components = [];

        components.push(
            <WrappedClaimForm
                key='claims_form'
                ref={this.claim_form}
                onSubmit={this.onSubmitClaim}
                urls={this.props.urls}
            />
        );

        components.push(
            <h5
                key='claims_title'
                className='mt-4 mb-4'
                style={{ color: 'black' }}
            >
                Претензии за интервал
            </h5>
        );
        components.push(
            <WrappedRangeForm
                key='range_form_2'
                ref={this.range_form_2}
                first_day={this.state.first_day}
                last_day={this.state.last_day}
                onSubmit={this.onSubmitRange}
            />
        );
        components.push(
            <ClaimsList
                key='claims_list'
                claims={this.state.claims}
                urls={this.props.urls}
            />
        );

        return components;
    }

    render() {
        let components = [];
        if (this.state.fetching) {
            components.push(
                <Spin
                    key='spinner'
                    size='large'
                    spinning={true}
                    style={{ width: '100%'}}
                >
                </Spin>
            );
        } else {
            components.push(
                <Tabs
                    defaultActiveKey={this.state.current_tab}
                    size='large'
                    onChange={this.onTabChanged}
                >
                    <Tabs.TabPane tab='Расходы' key='expenses' style={{ overflow: 'auto' }}>
                        {this.expensesTab()}
                    </Tabs.TabPane>
                    <Tabs.TabPane tab='Претензии' key='claims' style={{ overflow: 'auto' }}>
                        {this.claimsTab()}
                    </Tabs.TabPane>
                </Tabs>
            )

            components.push(
                <ProviderModal
                    key='provider_modal'
                    ref={this.provider_modal}
                    visible={this.state.provider_modal_visible}
                    initial={this.state.provider_modal_initial}
                    onSubmit={this.onSubmitProvider}
                    onCancel={this.onProviderModalCancel}
                    {...this.props}
                />
            );

            components.push(
                <Modal
                    key='expense_modal'
                    visible={this.state.expense_modal_visible}
                    title='Изменить расход'
                    width={'70%'}
                    onCancel={this.onExpenseEditCancel}
                    okButtonProps={{ form: 'expense_modal_form', htmlType: 'submit' }}
                >
                    <WrappedExpenseForm
                        ref={this.expense_modal_form}
                        id='expense_modal_form'
                        initial={this.state.expense_modal_initial}
                        urls={this.props.urls}
                        show_labels
                        onSubmit={this.onSubmitExpense}
                    />
                </Modal>
            );
        }
        return components;
    }
}

export default App;
