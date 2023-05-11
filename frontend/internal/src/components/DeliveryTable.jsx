import React from 'react';

import 'moment/locale/ru';
import moment from 'moment';

import copy from 'copy-to-clipboard';
import { message } from 'antd';

import { Badge } from 'antd';
import { Icon } from 'antd';
import { Input } from 'antd';
import { Select } from 'antd';
import { Spin } from 'antd';
import { Tooltip } from 'antd';

import { DeliveryWorkerStatusesModal } from './DeliveryWorkerStatusesModal.jsx';

import DeliveryHoursModal from './DeliveryHoursModal.jsx';
import DeliveryPhotosModal from './DeliveryPhotosModal.jsx';
import RemoteSelect from './RemoteSelect.jsx';

import './DeliveryTable.css';


// Todo
const DATE_FORMAT = 'DD.MM.YYYY';


const STATUSES = {
    new: {
        color: '#FFFFFF',
        className: 'delivery_table_row_new',
    },
    declined: {
        color: '#FFCCCC',
        className: 'delivery_table_row_cancelled',
    },
    cancelled: {
        color: '#FFCCCC',
        className: 'delivery_table_row_cancelled',
    },
    driver_callback: {
        color: '#FFFFAA',
        className: 'delivery_table_row_driver_callback',
    },
    no_response: {
        color: '#FFDDDD',
        className: 'delivery_table_row_no_response',
    },
    cancelled_with_payment: {
        color: '#CCFFCC',
        className: 'delivery_table_row_cancelled_with_payment',
    },
    partly_confirmed: {
        color: '#7A57C770',
        className: 'delivery_table_row_partly_confirmed',
    },
    partly_arrival_submitted: {
        color: '#CDCAF6AA',
        className: 'delivery_table_row_partly_arrival_submitted',
    },
    partly_arrived: {
        color: '#D9DDF2AA',
        className: 'delivery_table_row_partly_arrived',
    },
    partly_photo_attached: {
        color: '#D9EEF2AA',
        className: 'delivery_table_row_partly_photo_attached',
    },
    photo_attached: {
        color: '#C6ECDFAA',
        className: 'delivery_table_row_photo_attached',
    },
    finished: {
        color: '#EEFFEE',
        className: 'delivery_table_row_finished',
    },
};


const MANUAL_STATUSES = {
    declined: {
        text: 'Не принята в работу',
    },
    cancelled: {
        text: 'Отмена',
    },
    driver_callback: {
        text: 'Перезвонит сам',
    },
    no_response: {
        text: 'Нет ответа',
    },
    cancelled_with_payment: {
        text: 'Отмена с оплатой',
    },
}


function statusClassName(row) {
    return STATUSES[row.status.value]? STATUSES[row.status.value].className : '';
}


class PKCell extends React.Component {

    tooltipColumns = () => {
        const BANNED_KEYS = [
            'timesheet_photo',
        ];

        return this.props.columns.filter(item => !BANNED_KEYS.includes(item.data));
    }

    copyColumns = () => {
        const ALLOWED_KEYS = [
            'date',
            'customer',
            'time_interval',
            'address',
            'driver_name',
            'driver_phones',
            'mass',
            'shipment_type',
            'volume',
            'place_count'
        ];

        return this.props.columns.filter(item => ALLOWED_KEYS.includes(item.data));
    }

    tooltipContent = () => {
        const rows = this.tooltipColumns().map(
            item => {
                return (
                    <tr
                        key={item.data}
                    >
                        <th>{item.title}</th>
                        <td>{textContent(this.props.row, item.data)}</td>
                    </tr>
                );
            }
        );
        return (
            <table
                className='table table-hover rh-table'
                key='table'
            >
                {rows}
            </table>
        );
    }

    textContent = (key) => {
        if (key === 'time_interval' || key === 'address') {
            return this.props.row.items.value.map(
                item => itemTextContent(item, key, '-')
            ).join(';');
        }
        return textContent(this.props.row, key);
    }

    onClick = () => {
        let text = '';
        this.copyColumns().forEach(
            item => {
                text += (
                    item.title + ': ' +
                    this.textContent(item.data) + '\n'
                );
            }
        );

        this.props.onClick(text);
    }

    onAddClick = () => {
        this.props.onAddClick(this.props.row.pk.value);
    }

    onToggleClick = () => {
        this.props.onRequestToggle(this.props.request_index, this.props.row.pk.value);
    }

    render() {
        let components = [];
        if (this.props.row.items.value.length > 1) {
            let icon_type = this.props.expanded? 'up-circle' : 'down-circle';
            components.push(
                <Icon
                    type={icon_type}
                    theme='twoTone'
                    onClick={this.onToggleClick}
                />
            );
        } else {
            components.push(
                <Icon
                    type='down-circle'
                    theme='twoTone'
                    twoToneColor='#ffffff00'
                />
            );
        }
        components.push(
            <Tooltip
                placement='right'
                title={this.tooltipContent}
            >
                <span
                    onClick={this.onClick}
                    style={{ padding: '4px' }}
                >
                {this.props.row.pk.value}
                </span>
                <span
                >
                </span>
            </Tooltip>
        );
        components.push(
            <Icon
                type='plus-circle'
                theme='twoTone'
                style={{ marginLeft: '4px' }}
                onClick={this.onAddClick}
            />
        );
        return components;
    }
}


class OperatorCell extends React.Component {

    onClick = (e) => {
        e.stopPropagation();
        e.preventDefault();

        this.props.onCellChanged(
            this.props.request_index,
            this.props.row.pk.value,
            null,
            this.props.field,
            ''
        );
    }

    render() {
        let content = [];
        if (this.props.row.operator.value) {
            content.push(this.props.row.operator.value);
        } else {
            content.push(
                <a
                    href=''
                    onClick={this.onClick}
                >
                    забрать
                </a>
            );
        }
        return <td>{content}</td>;
    }
}


class RouteCell extends React.Component {
    onDetachClick = () => {
        this.props.onDetachClick(
            this.props.item.pk.value
        );
    }

    onCopyClick = () => {
        this.props.onCopyClick(
            this.props.item.pk.value
        );
    }

    onDeleteClick = () => {
        this.props.onDeleteClick(
            this.props.item.pk.value
        );
    }

    render() {
        let content = [];
        content.push(
            this.props.request.route.value
        );
        if (this.props.expanded && this.props.request.items.value.length > 1) {
            content.push(
                <Icon
                    type='minus-circle'
                    theme='twoTone'
                    twoToneColor='#eb2f96'
                    style={{ marginLeft: '6px' }}
                    onClick={this.onDetachClick}
                />
            );
            content.push(
                <Icon
                    type='copy'
                    theme='twoTone'
                    style={{ marginLeft: '6px' }}
                    onClick={this.onCopyClick}
                />
            );
            content.push(
                <Icon
                    type='delete'
                    theme='twoTone'
                    twoToneColor='#ff4d4f'
                    style={{ marginLeft: '6px' }}
                    onClick={this.onDeleteClick}
                />
            );
        }

        return <td>{content}</td>;
    }
}


const _LINE_COLORS = {
    1: '#EF0E18',
    2: '#29BF28',
    3: '#0079BF',
    4: '#00C0FF',
    5: '#8E5B29',
    6: '#EE921B',
    7: '#810081',
    8: '#FFD800',
    '8A': '#FFD800',
    9: '#9A9A9A',
    10: '#9ACD00',
    11: '#83C1C1',
    '11A': '#83C1C1',
    12: '#A4B6D7',
    13: '#0079BF',
    14: '#FFFFFF',
    15: '#DF64A2',
    D1: '#F6A800',
    D2: '#E83F83'
}


class MetroLineCell extends React.Component {
    render() {
        let content = '-';
        let style = {};
        if (this.props.item.metro_line) {
            let value = this.props.item.metro_line.value;
            if (value) {
                content = value;
                const c = _LINE_COLORS[value];
                if (c) {
                    style['background'] = c;
                }
            }
        }
        return <td style={style}>{content}</td>
    }
}


class StatusCell extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            status: this.props.row.status.value,
        }
    }

    onSelect = (value) => {
        this.setState(
            { status: value },
            this.commit
        );
    }

    onBlur = () => {
        this.commit();
    }

    commit = () => {
        this.props.onCommit(this.state.status);
    }

    render() {
        if (this.props.editing) {
            let options = [];
            for (let [key, value] of Object.entries(MANUAL_STATUSES)) {
                options.push(
                    <Select.Option
                        key={key}
                        value={key}
                        style={{ backgroundColor: STATUSES[key].color }}
                    >
                        {value.text}
                    </Select.Option>
                );
            }
            return (
                <Select
                    defaultValue={this.state.status}
                    defaultOpen='true'
                    onSelect={this.onSelect}
                    onBlur={this.onBlur}
                    size='small'
                    style={{ width: '120px' }}
                >
                    {options}
                </Select>
            );
        } else {
            return textContent(this.props.row, 'status');
        }
    }
}


class WorkerCell extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            workers: this.props.row[this.props.field].value,
        }
    }

    onChange = (value) => {
        this.setState({ workers: value });
    }

    onBlur = () => {
        this.props.onCommit(this.state.workers);
    }

    onCancel = () => {
        this.props.onStopEdit();
        this.props.requestUpdate(this.props.request_index);
    }

    render() {
        if (this.props.editing) {
            return (
                <DeliveryWorkerStatusesModal
                    visible={true}
                    delivery_request_pk={this.props.row.pk.value}
                    urls={this.props.urls}
                    onCancel={this.onCancel}
                />
            )
        } else {
            return textContent(this.props.row, this.props.field);
        }
    }
}


class ServiceCell extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            service: this.props.row.service.value
        }
    }

    onChange = (value) => {
        this.setState({ service: value }, this.commit);
    }

    onBlur = () => {
        this.commit();
    }

    commit = () => {
        const service = this.state.service;
        const value = service? service.key : null;
        this.props.onCommit(value);
    }

    render() {
        if (this.props.editing) {
            return (
                <RemoteSelect
                    url={this.props.urls.service_ac_url}
                    width='160px'
                    value={this.state.service}
                    forward={{
                        customer: this.props.row.customer.value.key,
                        delivery_request_pk: this.props.row.pk.value,
                    }}
                    extra_select_options={{
                        defaultOpen: true,
                        onBlur: this.onBlur,
                    }}
                    onChange={this.onChange}
                />
            );
        } else {
            return textContent(this.props.row, 'service');
        }
    }
}


class LocationCell extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            location: this.props.row.location.value
        }
    }

    onChange = (value) => {
        this.setState({ location: value }, this.commit);
    }

    onBlur = () => {
        this.commit();
    }

    commit = () => {
        const loc = this.state.location;
        const value = loc? loc.key : null;
        this.props.onCommit(value);
    }

    render() {
        if (this.props.editing) {
            return (
                <RemoteSelect
                    url={this.props.urls.location_ac_url}
                    width='160px'
                    value={this.state.location}
                    forward={{
                        customer: this.props.row.customer.value.key,
                    }}
                    extra_select_options={{
                        defaultOpen: true,
                        onBlur: this.onBlur,
                    }}
                    onChange={this.onChange}
                />
            );
        } else {
            return textContent(this.props.row, 'location');
        }
    }
}


class TimeCell extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            time: this.props.row.arrival_time.value
        }
    }

    onChange = (e) => {
        e.persist();
        this.setState({ time: e.target.value });
    }

    onKeyPress = (e) => {
        e.persist();
        if (e.key === 'Enter') {
            this.commit();
        }
    }

    onBlur = () => {
        this.commit();
    }

    commit = () => {
        this.props.onCommit(this.state.time);
    }

    render() {
        if (this.props.editing) {
            const time = this.state.time?
                moment(this.state.time, 'HH:mm:ss').format('HH:mm') : '08:00';
            return (
                <input
                    type='time'
                    autoFocus
                    value={time}
                    onChange={this.onChange}
                    onKeyPress={this.onKeyPress}
                    onBlur={this.onBlur}
                />
            );
        } else {
            return this.props.row.arrival_time.value;
        }
    }
}


class TextCell extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            text: this.props.text
        };
    }

    onChange = (e) => {
        e.persist();
        this.setState({ text: e.target.value });
    }

    onPressEnter = () => {
        this.props.onCommit(this.state.text);
    }

    onBlur = () => {
        this.props.onCommit(this.state.text);
    }

    render() {
        if (this.props.editing) {
            return (
                <Input
                    size='small'
                    autoFocus={true}
                    defaultValue={this.state.text}
                    onChange={this.onChange}
                    onPressEnter={this.onPressEnter}
                    onBlur={this.onBlur}
                />
            );
        } else {
            return this.props.shorter_text;
        }
    }
}


let _ADDRESS_RE = /^(Россия, )?(Москва город, )?(Москва,? )?(.*)/;

function _removeMoscow(address) {
    let m = address.match(_ADDRESS_RE);
    if (m) {
        return m[4];
    }
    return address;
}

function shortenAddress(address) {
    return _removeMoscow(address).replace('Московская область', 'МО');
}

function itemTextContent(item, key, defval) {
    if (key === 'pk') {
        return defval;
    } else if (key === 'time_interval') {
        return (
            item['interval_begin'].value.slice(0, 5) +
            '-' +
            item['interval_end'].value.slice(0, 5)
        );
    }

    if (item) {
        if (item[key]) {
            return item[key].value;
        }
    }

    return defval;
}

function textContent(request, key) {
    if (key === 'date') {
        return moment(request['date'].value).format(DATE_FORMAT);
    } else if (key === 'status') {
        return request.status_description.value;
    } else if (key === 'customer') {
        return request.customer.value.label;
    } else if (key === 'worker_count') {
        return request.arrived_workers.value.length;
    } else if (['assigned_workers', 'arrived_workers'].includes(key)) {
        let workers = '';
        request[key].value.forEach(
            item => {
                if (workers) {
                    workers += ', ';
                }
                workers += item.label;
            }
        );
        return workers;
    } else if (key === 'location') {
        return request.location.value.label || '';
    } else if (key === 'service') {
        return request.service.value.label || '';
    } else if (key === 'hours') {
        let hours = 0;
        request.arrived_workers.value.forEach(
            item => {
                hours += parseFloat(item.hours);
            }
        );
        return hours;
    } else if (key === 'timesheet_photo') {
        // Processed in the other place
        return '';
    } else {
        if (request[key] && request[key].value) {
            return request[key].value;
        }
        return itemTextContent(request.items.value[0], key, '');
    }
}


class CellWrapper extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            editing: false,
        };
    }

    onCommit = (value) => {
        this.setState({ editing: false});

        if (this.props.onCellChanged) {
            this.props.onCellChanged(
                this.props.request_index,
                this.props.row.pk.value,
                this.props.item.pk.value,
                this.props.field,
                value
            );
        }
    }

    onStopEdit = () => {
        this.setState({ editing: false});
    }

    render() {
        const editing = this.state.editing && !this.props.readonly;
        const children = React.Children.map(
            this.props.children,
            child => React.cloneElement(
                child,
                {
                    editing: editing,
                    onCommit: this.onCommit,
                    onStopEdit: this.onStopEdit,
                }
            )
        );
        if (editing) {
            return (
                <td>{children}</td>
            );
        } else {
            let content = [];
            if (this.props.error) {
                content.push(
                    <span style={{ color: 'red' }}>! </span>
                );
            } else if (this.props.fetching) {
                content.push(
                    <Spin
                        size='small'
                        spinning='true'
                        style={{ paddingRight: '8px' }}
                    />
                );
            }

            const className = 'delivery_table_cell';
            const onClick = this.props.onClick?
                this.props.onClick : (
                    this.props.readonly? undefined :
                    (e) => {
                        e.stopPropagation();
                        e.preventDefault();

                        this.setState({ editing: true})
                        return false;
                    }
                );
            let tooltip = null;
            if (!this.props.no_tooltip) {
                tooltip = (
                    <div
                        className='tooltip_container'
                    >
                        <span
                            className='tooltip_text'
                        >
                            {children}
                        </span>
                    </div>
                );
            }
            return (
                <td
                    className={className}
                    onClick={onClick}
                    onMouseOver={this.onMouseOver}
                    onMouseOut={this.onMouseOut}
                    style={this.props.style || {}}
                >
                    {tooltip}
                    {content}
                    {children}
                </td>
            );
        }
    }
}


// array
function _cmp_a(a, b) {
    if (a.length != b.length) {
        return (a.length < b.length)? -1 : 1;
    }
    if (a.length === 1) {
        return _cmp_s(a[0], b[0]);
    }
    if (a.length === 0) {
        return 0;
    }
    return _cmp_a(a.slice(1), b.slice(1));
}


// scalar
function _cmp_s(a, b) {
    if (a === b) {
        return 0;
    }
    if (a === null) {
        return -1;
    }
    if (b === null) {
        return 1;
    }
    return a < b? -1 : 1;
}


export class DeliveryTable extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            hours_modal: undefined,

            sort_key: null,
            sort_order: null,
            sorted_requests: this.props.requests,
        };
    }

    sortedRequests(key, order) {
        let requests = this.props.requests.map(r => r);
        if (key === 'confirmed_timepoint') {
            return requests.sort(
                (a, b) => {
                    let v1 = a[key].value? moment(a[key].value, 'HH:mm') : null;
                    let v2 = b[key].value? moment(b[key].value, 'HH:mm') : null;

                    return (order === 'asc')? _cmp_s(v1, v2) : _cmp_s(v2, v1);
                }
            );
        }
        if (key === 'time_interval') {
            return requests.sort(
                (a, b) => {
                    let v1 = a.items.value.map(
                        item => moment(item.interval_begin.value, 'HH:mm:ss')
                    ).sort()[0];
                    let v2 = b.items.value.map(
                        item => moment(item.interval_begin.value, 'HH:mm:ss')
                    ).sort()[0];

                    return (order === 'asc')? _cmp_s(v1, v2) : _cmp_s(v2, v1);
                }
            );
        }
        if (key === 'assigned_workers' || key === 'arrived_workers') {
            return requests.sort(
                (a, b) => {
                    let v1 = a[key].value.map(item => item.key).sort().reverse();
                    let v2 = b[key].value.map(item => item.key).sort().reverse();

                    return (order === 'asc')? _cmp_a(v1, v2) : _cmp_a(v2, v1);
                }
            );
        }
        if (key === 'metro_line' || key === 'metro_name') {
            return requests.sort(
                (a, b) => {
                    let v1 = a.items.value.map(item => item[key].value).sort();
                    let v2 = b.items.value.map(item => item[key].value).sort();

                    return (order === 'asc')? _cmp_a(v1, v2) : _cmp_a(v2, v1);
                }
            );
        }
        if (key === 'customer') {
            return requests.sort(
                (a, b) => {
                    let v1 = a[key].value.key;
                    let v2 = b[key].value.key;
                    return (order === 'asc')? _cmp_s(v1, v2) : _cmp_s(v2, v1);
                }
            );
        }
        return requests.sort(
            (a, b) => {
                let v1 = a[key].value;
                let v2 = b[key].value;
                return (order === 'asc')? _cmp_s(v1, v2) : _cmp_s(v2, v1);
            }
        );
    }

    sortRequests = (key) => {
        for (let index in this.props.columns) {
            let col = this.props.columns[index];
            if (col.data === key && !col.sortable) {
                return;
            }
        }

        let order = 'asc';
        if (this.state.sort_key == key && this.state.sort_order == order) {
            order = 'desc';
        }

        this.setState({
            sort_key: key,
            sort_order: order,
            sorted_requests: this.sortedRequests(key, order)
        });
    }

    onModalCancel = () => {
        this.setState({ hours_modal: undefined });
    }

    onPKClick = (row_content) => {
        message.success({ duration: 1.0, content: 'Скопировано!' });
        copy(row_content);
    }

    // Todo: remove
    onHoursSubmit = (request_index, request_pk, new_value) => {
        // notning to do
    }

    // Todo: remove
    onWorkedHoursClick = (request_index) => {
        const workers = this.props.requests[request_index].arrived_workers.value;
        if (workers.length === 0) {
            return;
        }

        this.setState(
            {
                hours_modal: {
                    workers: workers,
                    request_index: request_index,
                    row_pk: this.props.requests[request_index].pk.value,
                }
            }
        );
    }

    header = () => {
        const columns = this.props.columns.map(
            item => {
                let content = [];

                if (item.data === 'route') {
                    let icon_type = this.props.expanded_all? 'up-circle' : 'down-circle';
                    content.push(
                        <Icon
                            type={icon_type}
                            theme='twoTone'
                            style={{ paddingRight: '8px' }}
                            onClick={() => {this.props.onRequestToggleAll();}}
                        />
                    )
                }

                content.push(
                    <span
                        onClick={() => {this.sortRequests(item.data);}}
                    >
                    {item.title}
                    </span>
                );

                return <th
                    key={item.data}
                    title={item.title}
                >
                    {content}
                </th>
            }
        );
        return (
            <thead>
                <tr>
                    {columns}
                </tr>
            </thead>
        );
    }

    cell = (data, request_index, key) => {
        let content = textContent(data, key);
        let onClick = undefined;
        let no_tooltip = false;
        let expanded = this.props.expanded_requests.has(data.pk.value);

        if (key === 'hours') {
            onClick = () => this.onWorkedHoursClick(request_index);
        } else if (key === 'timesheet_photo') {
            onClick = () => this.onPhotosClick(request_index);
            no_tooltip = true;

            const count = data['new_photos'].value;
            if (count > 0) {
                const url = this.props.urls.photo_checking_url + '?pk=' + data.pk.value;
                content = (
                    <a href={url} target='_blank'>
                        <Badge
                            count={count}
                        />
                    </a>
                );
            }
        }

        let text = content;
        let shorter_text = (key === 'address'? shortenAddress(text) : text);

        let cell = (
            <TextCell
                text={text}
                shorter_text={shorter_text}
            />
        );

        if (key === 'pk') {
            cell = (
                <PKCell
                    columns={this.props.columns}
                    row={data}
                    request_index={request_index}
                    expanded={expanded}
                    onClick={this.onPKClick}
                    onRequestToggle={this.props.onRequestToggle}
                    onAddClick={this.props.onItemAddClick}
                />
            );
        } else if (key === 'operator') {
            return (
                <OperatorCell
                    row={data}
                    request_index={request_index}
                    field={key}
                    onCellChanged={this.props.onCellChanged}
                />
            );
        } else if (key === 'route') {
            return (
                <RouteCell
                    key={key}
                    request={data}
                    expanded={expanded}
                    item={data.items.value[0]}
                    onDetachClick={this.props.onItemDetachClick}
                    onCopyClick={this.props.onItemCopyClick}
                    onDeleteClick={this.props.onItemDeleteClick}
                />
            );
        } else if (key === 'metro_line') {
            return (
                <MetroLineCell
                    item={data.items.value[0]}
                />
            );
        } else if (key === 'status') {
            cell = (
                <StatusCell
                    row={data}
                    urls={this.props.urls}
                />
            );
        } else if (['assigned_workers', 'arrived_workers'].includes(key)) {
            cell = (
                <WorkerCell
                    row={data}
                    request_index={request_index}
                    field={key}
                    urls={this.props.urls}
                    requestUpdate={this.props.requestUpdate}
                />
            );
        } else if (key === 'location') {
            cell = (
                <LocationCell
                    row={data}
                    urls={this.props.urls}
                />
            );
        } else if (key === 'service') {
            cell = (
                <ServiceCell
                    row={data}
                    urls={this.props.urls}
                />
            );
        } else if (key === 'arrival_time') {
            cell = (
                <TimeCell
                    row={data}
                />
            );
        }

        const readonly_fields = [
            'pk',
            'author',
            'timestamp',
            'confirmation_time',
            'customer',
            'date',
            'time_interval',
            'code',
            'metro_line',
            'metro_name',
            'worker_count',
            'hours',
            'timesheet_photo',
            'arrived_workers'
        ];

        const readonly = readonly_fields.includes(key);
        const fetching = data[key]? data[key].fetching : false;
        const error = data[key]? data[key].error : false;

        let style = (key === 'address'? { maxWidth: '360px'} : {});

        return (
            <CellWrapper
                key={key}
                row={data}
                item={data.items.value[0]}
                request_index={request_index}
                field={key}
                readonly={readonly}
                fetching={fetching}
                error={error}
                style={style}
                no_tooltip={no_tooltip}
                onCellChanged={this.props.onCellChanged}
                onClick={onClick}
            >
                {cell}
            </CellWrapper>
        );
    }

    rows = (data, request_index) => {
        let cells = this.props.columns.map(
            item => this.cell(data, request_index, item.data)
        );

        let components = [];
        components.push(
            <tr
                className={'delivery_table_row ' + statusClassName(data)}
            >
                {cells}
            </tr>
        );

        let expanded = this.props.expanded_requests.has(data.pk.value);
        if (expanded) {
            // secondary rows
            for (let i = 1; i < data.items.value.length; ++i) {
                let secondary_cells = this.props.columns.map(
                    item => {
                        let key = item.data;
                        if (key === 'route') {
                            return (
                                <RouteCell
                                    key={key}
                                    request={data}
                                    expanded={true}
                                    item={data.items.value[i]}
                                    onDetachClick={this.props.onItemDetachClick}
                                    onCopyClick={this.props.onItemCopyClick}
                                    onDeleteClick={this.props.onItemDeleteClick}
                                />
                            );
                        } else if (key == 'metro_line') {
                            return (
                                <MetroLineCell
                                    item={data.items.value[i]}
                                />
                            );
                        } else {
                            let text = itemTextContent(data.items.value[i], item.data, '');

                            return (
                                <CellWrapper
                                    key={key}
                                    field={key}
                                    readonly={true}
                                    fetching={false}
                                >
                                    <TextCell
                                        text={text}
                                        shorter_text={text}
                                    />
                                </CellWrapper>
                            );
                        }
                    }
                );
                components.push(
                    <tr
                        className={'delivery_table_row ' + statusClassName(data)}
                    >
                        {secondary_cells}
                    </tr>
                );
            }
        }

        return components;
    }

    body = () => {
        let original_indexes = {};
        this.props.requests.forEach(
            (request, i) => {
                original_indexes[request.pk.value] = i;
            }
        );

        let rows = this.state.sorted_requests.map(
            request => this.rows(request, original_indexes[request.pk.value])
        );
        return (
            <tbody>
                {rows}
            </tbody>
        );
    }

    componentDidUpdate(prevProps, prevState, snapshot) {
        let sorted_requests = this.props.requests;
        if (this.state.sort_key) {
            sorted_requests = this.sortedRequests(this.state.sort_key, this.state.sort_order);
        }
        if (this.state.sorted_requests.length != sorted_requests.length) {
            this.setState({ sorted_requests: sorted_requests });
            return;
        }
        this.state.sorted_requests.forEach(
            (request, i) => {
                if (request.pk.value != sorted_requests[i].pk.value) {
                    this.setState({ sorted_requests: sorted_requests });
                    return;
                }
            }
        );
    }

    render() {
        return [
            (
                <table
                    key='table'
                    className='table table-hover rh-table mt-4 delivery_table'
                >
                    {this.header()}
                    {this.body()}
                </table>
            ),
            (
                <DeliveryHoursModal
                    key='hours_modal'
                    visible={!!this.state.hours_modal}
                    {...(this.state.hours_modal || {})}
                    onCancel={this.onModalCancel}
                    onSubmit={this.onHoursSubmit}
                />
            )
        ];
    }
}
