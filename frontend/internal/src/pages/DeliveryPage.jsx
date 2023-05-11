import React from 'react';
import { withRouter } from 'react-router';

import { Checkbox } from 'antd';
import { Col } from 'antd';
import { Row } from 'antd';
import { Spin } from 'antd';

import { message } from 'antd';

import DeliveryFilterForm from '../components/DeliveryFilter.jsx';
import DeliveryImportForm from '../components/DeliveryImportForm.jsx';
import { ColumnsFilter } from '../components/ColumnsFilter.jsx';
import { DeliveryCreateRequestComponent } from '../components/DeliveryCreateRequestComponent.jsx';
import { DeliveryAttachItemModal } from '../components/DeliveryAttachItemModal.jsx';
import { DeliveryTable } from '../components/DeliveryTable.jsx';
import RemoteSelect from '../components/RemoteSelect.jsx';

import { SingleJsonFetcher } from '../utils/fetch.jsx';
import { getCookie } from '../utils/cookies.jsx';


class DeliveryPageReports extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            customer: null,
            location: null
        }
    }

    render() {
        let components = [];
        components.push(
            <span
                style={{
                    position: 'relative',
                    top: '4px',
                }}
            >
                <RemoteSelect
                    url={this.props.urls.customer_ac_url}
                    width='160px'
                    placeholder='Клиент'
                    value={this.state.customer}
                    onChange={(value) => this.setState({ customer: value })}
                />
            </span>
        );
        if (this.state.customer) {
            components.push(
                <span
                    style={{
                        position: 'relative',
                        top: '4px',
                        left: '4px'
                    }}
                >
                    <RemoteSelect
                        url={this.props.urls.location_ac_url}
                        width='80px'
                        placeholder='Филиал'
                        value={this.state.location}
                        forward={{
                            customer: this.state.customer.key,
                        }}
                        onChange={(value) => this.setState({ location: value })}
                    />
                </span>
            );
        }
        if (this.state.location) {
            const dayly_report_url = this.props.urls.day_report_url + '?day=' +
                this.props.last_day + '&customer=' + this.state.customer.key +
                '&location=' + this.state.location.key;
            components.push(
                <a
                    href={dayly_report_url}
                    style={{
                        whiteSpace: 'nowrap',
                        position: 'relative',
                        top: '6px',
                        marginLeft: '10px',
                        marginRight: '12px',
                    }}
                >
                    отчет за {this.props.last_day}
                </a>
            );

            const interval_report_url = this.props.urls.interval_report_url + '?first_day=' +
                this.props.first_day + '&last_day=' + this.props.last_day +
                '&customer=' + this.state.customer.key + '&location=' + this.state.location.key;
            components.push(
                <a
                    href={interval_report_url}
                    style={{
                        whiteSpace: 'nowrap',
                        position: 'relative',
                        top: '6px'
                    }}
                >
                    отчет с {this.props.first_day} по {this.props.last_day}
                </a>
            );
        }

        return components;
    }
}


class DeliveryPage extends React.Component {
    constructor(props) {
        super(props);

        message.config({ top: 120 });

        this.fetcher = new SingleJsonFetcher();
        this.cellFetchers = {};

        const columns_initial = [
            {
                title: '№',
                data: 'pk',
                checked: true,
                sortable: true,
            },
            {
                title: 'Автор',
                data: 'author',
                checked: false,
                sortable: true,
            },
            {
                title: 'Время создания',
                data: 'timestamp',
                checked: false,
                sortable: true,
            },
            {
                title: 'Время прибытия',
                data: 'arrival_time',
                checked: true,
            },
            {
                title: 'Время подтверждения',
                data: 'confirmation_time',
                checked: false,
                sortable: true,
            },
            {
                title: 'Отв-й',
                data: 'operator',
                checked: true,
                sortable: true,
            },
            {
                title: 'Маршрут',
                data: 'route',
                checked: true,
                sortable: true,
            },
            {
                title: 'Индекс',
                data: 'code',
                checked: true,
            },
            {
                title: 'Масса',
                data: 'mass',
                checked: false,
            },
            {
                title: 'Объем',
                data: 'volume',
                checked: false,
            },
            {
                title: 'Кол-во мест',
                data: 'place_count',
                checked: false,
            },
            {
                title: 'Характер груза',
                data: 'shipment_type',
                checked: false,
            },
            {
                title: 'Дата',
                data: 'date',
                checked: true,
                required: true,
                sortable: true,
            },
            {
                title: 'Клиент',
                data: 'customer',
                checked: true,
                sortable: true,
            },
            {
                title: 'Время выпол-я',
                data: 'time_interval',
                checked: true,
                sortable: true,
            },
            {
                title: 'Время подачи',
                data: 'confirmed_timepoint',
                checked: true,
                sortable: true,
            },
            {
                title: 'Примеч-е',
                data: 'comment',
                checked: true,
            },
            {
                title: 'Адрес',
                data: 'address',
                checked: true,
            },
            {
                title: 'Л-я',
                data: 'metro_line',
                checked: true,
                sortable: true,
            },
            {
                title: 'Метро',
                data: 'metro_name',
                checked: true,
                sortable: true,
            },
            {
                title: 'Водитель',
                data: 'driver_name',
                checked: true,
                sortable: true,
            },
            {
                title: 'Тел. водителя',
                data: 'driver_phones',
                checked: true,
                sortable: true,
            },
            {
                title: 'Статус',
                data: 'status',
                checked: true,
                sortable: true,
            },
            {
                title: 'Фото',
                data: 'timesheet_photo',
                checked: true,
            },
            {
                title: 'Направленные грузчики',
                data: 'assigned_workers',
                checked: true,
                sortable: true,
            },
            {
                title: 'Прибывшие грузчики',
                data: 'arrived_workers',
                checked: true,
                sortable: true,
            },
            {
                title: 'Кол-во гр-в',
                data: 'worker_count',
                checked: true,
            },
            {
                title: 'Филиал',
                data: 'location',
                checked: true,
            },
            {
                title: 'Тариф',
                data: 'service',
                checked: true,
            },
            {
                title: 'Кол-во часов (к оплате)',
                data: 'hours',
                checked: true,
            },
        ];

        const params = new URLSearchParams(this.props.location.search);

        let operator = null;
        const operator_key = params.get('operator_key');
        const operator_label = params.get('operator_label');
        if (operator_key && operator_label) {
            operator = {
                key: operator_key,
                label: operator_label,
            };
        }

        let customer = null;
        const customer_key = params.get('customer_key');
        const customer_label = params.get('customer_label');
        if (customer_key && customer_label) {
            customer = {
                key: customer_key,
                label: customer_label,
            }
        }

        this.state = {
            fetching: false,

            first_day: this.props.first_day,
            last_day: this.props.last_day,

            operator: operator,

            columns: columns_initial,

            requests: [],
            expanded_requests: new Set(),
            expanded_all: false,

            request_to_add_item: null,
            attach_item_modal_visible: false,

            create_request_modal_visible: false,

            customer: customer,

            can_merge: false,
        }
    }

    onImport = async (values) => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.import_requests_url, window.location);
        url.searchParams.set('customer', values.customer);
        const form = new FormData();
        form.append('requests', values.requests.file, values.requests.file.name);

        let response = await this.fetcher.fetch(
            url,
            {
                method: 'POST',
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                }),
                body: form
            }
        );
        if (response && response.status === 'ok') {
            message.success(
                {
                    duration: 1.5,
                    content: 'Файл импортируется. ' +
                        'Можно посмотреть отчет на странице Доставка/История импорта'
                }
            );
            await this.fetchRequests();
        } else if (response && response.status === 'error' && response.message) {
            message.error({ content: response.message });
        }
        this.setState({ fetching: false });
    }

    onCreateRequestClick = () => {
        this.setState({
            create_request_modal_visible: true,
        });
    }

    onCreateRequestCancel = () => {
        this.setState({
            create_request_modal_visible: false,
        });
    }

    onCreateRequest = async (values) => {
        this.setState({
            fetching: true,
            request_to_add_item: null,
            create_request_modal_visible: false,
        });

        let url = new URL(this.props.urls.create_request_url, window.location);
        for (let [key, value] of Object.entries(values)) {
            if (value !== undefined && value !== null) {
                url.searchParams.set(key, value);
            }
        }

        let response = await this.fetcher.fetch(
            url,
            {
                method: 'POST',
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                }),
            }
        );

        if (response && response.status === 'ok') {
            await this.fetchRequests();
        } else if (response && response.status === 'error' && response.message) {
            message.error({ content: response.message });
        }
        this.setState({ fetching: false });
    }

    onUploadChange = (info) => {
        // Todo: success or error message
        console.log(info)
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

    onSubmitRange = (first_day, last_day, operator, customer) => {
        this.setState(
            {
                first_day: first_day,
                last_day: last_day,
                operator: operator,
                customer: customer,

                requests: [],
            },
            this.fetchRequests
        );
    }

    // Todo: fix "cell fetching" and "cell error" state
    onCellChanged = async (request_index, request_pk, item_pk, field, new_value) => {
        // Todo: avoid race with content (requests) reload
        this.setState(
            state => {
                if (!state.requests[request_index][field]) {
                    state.requests[request_index][field] = {}
                }
                state.requests[request_index][field].fetching = true;
                return state;
            }
        );

        let url = new URL(this.props.urls.update_request_url, window.location);
        url.searchParams.set('pk', request_pk);
        url.searchParams.set('item_pk', item_pk);
        url.searchParams.set('field', field);
        let body = undefined;
        if (['hours'].includes(field)) {
            body = JSON.stringify(new_value);
        } else if (Array.isArray(new_value)) {
            new_value.forEach(
                value => {
                    url.searchParams.append('value', value.key);
                }
            );
        } else {
            url.searchParams.set('value', new_value);
        }

        // Todo: not sure if it is necessary
        if (!this.cellFetchers[request_pk]) {
            this.cellFetchers[request_pk] = { [field]: new SingleJsonFetcher() };
        } else if (!this.cellFetchers[request_pk][field]) {
            this.cellFetchers[request_pk][field] = new SingleJsonFetcher();
        }
        const fetcher = this.cellFetchers[request_pk][field];

        let response = await fetcher.fetch(
            url,
            {
                method: 'POST',
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                }),
                body: body,
            }
        );

        if (!response) {
            // ignore
        } else {
            this.setState(
                state => {
                    if (!state.requests[request_index][field]) {
                        state.requests[request_index][field] = {}
                    }

                    if (state.requests[request_index].pk.value !== request_pk) {
                        console.log('Request pks mismatch O_o');
                    } else {
                        state.requests[request_index][field].fetching = false;
                        if (response.status === 'ok') {
                            state.requests[request_index] = response.updated;
                        } else {
                            state.requests[request_index][field].error = true;
                        }
                    }
                    return state;
                }
            );
            if (response.status === 'error' && response.message) {
                message.error({ content: response.message });
            }
        }
    }

    moveItem = async (item_pk, request_pk) => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.move_item_url, window.location);
        url.searchParams.set('item_pk', item_pk);
        if (request_pk) {
            url.searchParams.set('target_pk', request_pk);
        }

        let response = await this.fetcher.fetch(
            url,
            {
                method: 'POST',
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                }),
            }
        );

        if (response && response.status === 'ok') {
            await this.fetchRequests();
        } else if (response && response.status === 'error' && response.message) {
            message.error({ content: response.message });
        }
        this.setState({ fetching: false });
    }

    onItemDetachClick = (item_pk) => {
        this.moveItem(item_pk, null);
    }

    onItemCopyClick = async (item_pk) => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.copy_item_url, window.location);
        url.searchParams.set('item_pk', item_pk);

        let response = await this.fetcher.fetch(
            url,
            {
                method: 'POST',
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                }),
            }
        );

        if (response && response.status === 'ok') {
            await this.fetchRequests();
        } else if (response && response.status === 'error' && response.message) {
            message.error({ content: response.message });
        }
        this.setState({ fetching: false });
    }

    onItemDeleteClick = async (item_pk) => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.remove_item_url, window.location);
        url.searchParams.set('item_pk', item_pk);

        let response = await this.fetcher.fetch(
            url,
            {
                method: 'POST',
                headers: new Headers({
                    'X-CSRFToken': getCookie('csrftoken'),
                }),
            }
        );

        if (response && response.status === 'ok') {
            await this.fetchRequests();
        } else if (response && response.status === 'error' && response.message) {
            message.error({ content: response.message });
        }
        this.setState({ fetching: false });
    }

    onItemAttachClick = (request_pk, item_pk) => {
        this.onItemAddCancel();
        this.moveItem(item_pk, request_pk);
    }

    onItemAddClick = async (request_pk) => {
        this.setState({
            request_to_add_item: request_pk,
            attach_item_modal_visible: true,
        });
    }

    onItemAddCancel = () => {
        this.setState({
            request_to_add_item: null,
            attach_item_modal_visible: false,
        });
    }

    onAddNewItemClick = (request_pk) => {
        this.setState({
            attach_item_modal_visible: false,
            create_request_modal_visible: true,
        });
    }

    onRequestToggle = (request_index, request_pk) => {
        let request = this.state.requests[request_index];
        if (request && request.pk.value === request_pk) {
            this.setState(
                state => {
                    if (state.expanded_requests.has(request.pk.value)) {
                        state.expanded_requests.delete(request.pk.value);
                    } else {
                        state.expanded_requests.add(request.pk.value);
                    }

                    return state;
                }
            );
        }
    }

    onRequestToggleAll = () => {
        this.setState(
            state => {
                if (state.expanded_all) {
                    state.expanded_all = false;
                    state.expanded_requests = new Set();
                } else {
                    state.expanded_all = true;
                    state.expanded_requests = new Set(
                        state.requests.map(request => request.pk.value)
                    );
                }

                return state;
            }
        );
    }

    fetchRequests = async () => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.requests_list_url, window.location);
        url.searchParams.set('first_day', this.state.first_day);
        url.searchParams.set('last_day', this.state.last_day);
        if (this.state.operator) {
            url.searchParams.set('operator', this.state.operator.key);
        }
        if (this.state.customer) {
            url.searchParams.set('customer', this.state.customer.key);
        }
        if (this.state.can_merge) {
            url.searchParams.set('can_merge', this.state.can_merge);
        }

        let response = await this.fetcher.fetch(url);
        this.setState({ fetching: false });
        if (response.status === 'ok') {
            this.setState({ requests: response.data });
        } else if (response.status === 'error' && response.message) {
            message.error({ content: response.message });
        }
    }

    requestUpdate = (request_index) => {
        // Using fake field to update row
        this.onCellChanged(
            request_index,
            this.state.requests[request_index].pk.value,
            this.state.requests[request_index].items.value[0].pk.value,
            'fake_field',
            ''
        );
    }

    componentDidMount() {
        this.fetchRequests();
    }

    render() {
        let components = [];

        components.push(
            <Row
                key='upload'
                type='flex'
                gutter={[4, 12]}
            >
                <Col>
                    <div
                        style={{
                            marginTop: '4px',
                            marginRight: '12px',
                        }}
                    >
                        <DeliveryCreateRequestComponent
                            modal_visible={this.state.create_request_modal_visible}
                            route={this.state.request_to_add_item}
                            urls={this.props.urls}
                            onModalOpen={this.onCreateRequestClick}
                            onModalCancel={this.onCreateRequestCancel}
                            onCreateRequest={this.onCreateRequest}

                        />
                    </div>
                </Col>
                <Col>
                    <DeliveryImportForm
                        urls={this.props.urls}
                        onSubmit={this.onImport}
                    />
                </Col>
                <Col
                    span={4}
                    style={{ position: 'relative' }}
                >
                    <a
                        href={this.props.urls.import_template_url + '?v=4'}
                        style={{
                            position: 'absolute',
                            whiteSpace: 'nowrap',
                            top: '14px'
                        }}
                    >
                        шаблон.xlsx
                    </a>
                </Col>
            </Row>
        );

        if (this.state.fetching) {
            components.push(
                <Row
                    key='spinner'
                    type='flex'
                >
                    <Col
                        span={24}
                    >
                        <Spin
                            size='large'
                            spinning={true}
                            style={{ width: '100%', paddingTop: '250px' }}
                        />
                    </Col>
                </Row>
            );
        } else {
            components.push(
                <Row
                    key='columns_filter'
                    type='flex'
                    gutter={[4, 12]}
                >
                    <Col
                        style={{ marginTop: '4px', marginRight: '14px' }}
                    >
                        <ColumnsFilter
                            columns={this.state.columns}
                            onFilterUpdate={this.onFilterUpdate}
                        />
                    </Col>
                    <Col
                        style={{ marginTop: '4px' }}
                    >
                        <Checkbox
                            checked={this.state.can_merge}
                            onChange={(e) => { this.setState({can_merge: e.target.checked}); }}
                        >
                            Только объединяемые заявки
                        </Checkbox>
                    </Col>
                    <Col>
                        <DeliveryFilterForm
                            urls={this.props.urls}
                            first_day={this.state.first_day}
                            last_day={this.state.last_day}
                            operator={this.state.operator}
                            customer={this.state.customer}
                            onSubmit={this.onSubmitRange}
                        />
                    </Col>
                    <Col>
                        <DeliveryPageReports
                            urls={this.props.urls}
                            first_day={this.state.first_day}
                            last_day={this.state.last_day}
                        />
                    </Col>
                </Row>
            );

            components.push(
                <Row
                    key='table'
                    type='flex'
                    gutter={[4, 12]}
                >
                    <Col>
                        <DeliveryTable
                            requests={this.state.requests}
                            expanded_requests={this.state.expanded_requests}
                            expanded_all={this.state.expanded_all}
                            urls={this.props.urls}
                            columns={this.state.columns.filter(item => item.checked)}
                            onCellChanged={this.onCellChanged}
                            onItemDetachClick={this.onItemDetachClick}
                            onItemCopyClick={this.onItemCopyClick}
                            onItemDeleteClick={this.onItemDeleteClick}
                            onItemAddClick={this.onItemAddClick}
                            onRequestToggle={this.onRequestToggle}
                            onRequestToggleAll={this.onRequestToggleAll}
                            onTableReload={this.fetchRequests}
                            requestUpdate={this.requestUpdate}
                        />
                    </Col>
                </Row>
            );

            components.push(
                <DeliveryAttachItemModal
                    visible={this.state.attach_item_modal_visible}
                    request={this.state.request_to_add_item}
                    urls={this.props.urls}
                    onCancel={this.onItemAddCancel}
                    onNewItemClick={this.onAddNewItemClick}
                    onItemAttachClick={this.onItemAttachClick}
                />
            );
        }

        return components;
    }
}


export default withRouter(DeliveryPage);

