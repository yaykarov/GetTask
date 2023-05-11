import React from 'react';

import 'moment/locale/ru';
import moment from 'moment';

import { Button } from 'antd';
import { Form } from 'antd';
import { Input } from 'antd';
import { Modal } from 'antd';

import { remoteSelectItem } from './RemoteSelect.jsx';


// Todo
const DATE_FORMAT = 'DD.MM.YYYY';

const _REQUEST_FIELDS = {
    'Планируемая дата': 'data',
    'Индекс груза': 'code',
    'Общий вес, кг': 'mass',
    'Объем, м3': 'volume',
    'Кол-во мест': 'place_count',
    'Характер груза': 'shipment_type',
    'Адрес забора/доставки': 'address',
    'Временной интервал': 'time_interval',
    'Водитель': 'driver_name',
    'Телефон водителя': 'driver_phones',
};

function _compile_rxs() {
    let rxs = [];
    for (let [key, value] of Object.entries(_REQUEST_FIELDS)) {
        const rx = new RegExp('^(' + key + '):\\s+(\\S.*)$');
        rxs.push(rx);
    }
    return rxs;
}

const _REQUEST_RXS = _compile_rxs();


function parseRequestText(text) {
    let result = {};

    const lines = text.split('\n');
    lines.forEach(
        line => {
            _REQUEST_RXS.forEach(
                rx => {
                    const m = line.match(rx);
                    if (m && m.length === 3) {
                        result[_REQUEST_FIELDS[m[1]]] = m[2].replace(',', '.');
                    }
                }
            );
        }
    );

    return result;
}


class DeliveryRequestForm extends React.Component {

    customerItem = () => {
        return remoteSelectItem(
            this.props.form,
            'customer',
            'Клиент',
            this.props.urls.customer_ac_url,
            '300px',
            true
        );
    }

    routeItem = () => {
        let forwarded = {};
        const customer = this.props.form.getFieldValue('customer');
        if (customer) {
            forwarded['customer'] = customer.key;
        }
        const date = this.props.form.getFieldValue('date');
        if (date) {
            forwarded['date'] = date;
        }
        return remoteSelectItem(
            this.props.form,
            'route',
            'Прикрепить к маршруту',
            this.props.urls.route_ac_url,
            '300px',
            true,
            forwarded,
            true
        );
    }

    inputItem = (key, label, placeholder, required, onChange) => {
        return (
            <Form.Item
                key={key}
                style={{ marginBottom: 0 }}
                label={label}
            >
                {
                    this.props.form.getFieldDecorator(
                        key,
                        { rules: [{ required: required, message: 'Это поле необходимо!' }] }
                    )(
                        <Input.TextArea
                            placeholder={placeholder}
                            style={{ width: '300px' }}
                            autosize={{ minRows: 1, maxRows: 3 }}
                            onChange={onChange}
                        />
                    )
                }
            </Form.Item>
        );
    }

    onTextChange = (v) => {
        v.persist();
        let result = parseRequestText(v.target.value);
        this.props.form.setFieldsValue(result);
    }

    render() {
        let components = [];

        if (!this.props.route) {
            components.push(
                this.inputItem('text', 'Весь текст заявки', '', false, this.onTextChange)
            );
            components.push(this.customerItem());
            components.push(this.inputItem('date', 'Дата', true));
            components.push(this.routeItem());
        }
        components.push(this.inputItem('code', 'Индекс', '', true));
        components.push(this.inputItem('volume', 'Объем', 'в формате 2.5', true));
        components.push(this.inputItem('mass', 'Масса', 'в формате 67.3', true));
        components.push(this.inputItem('place_count', 'Кол-во мест', '', true));
        components.push(this.inputItem('shipment_type', 'Характер груза', '', true));
        components.push(this.inputItem('time_interval', 'Время выполнения', 'в формате 11:00-13:45', true));
        components.push(this.inputItem('address', 'Адрес', true));
        if (!this.props.route && !this.props.form.getFieldValue('route')) {
            components.push(this.inputItem('driver_name', 'ФИО водителя', false));
            components.push(this.inputItem('driver_phones', 'Телефоны водителя', false));
        }

        return (
            <Form
                labelCol={{ span: 9, offset: 0}}
                wrapperCol={{ span: 15, offset: 0}}
            >
                {components}
            </Form>
        );
    }
}


const WrappedDeliveryRequestForm = Form.create(
    {
        mapPropsToFields(props) {
            return {
                date: Form.createFormField(
                    {
                        'value': moment().format(DATE_FORMAT)
                    }
                )
            };
        }
    }
)(DeliveryRequestForm);


export class DeliveryCreateRequestComponent extends React.Component {
    constructor(props) {
        super(props);

        this.form = React.createRef();
    }

    onModalOk = () => {
        this.form.current.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                if (values.customer) {
                    values.customer = values.customer.key;
                }
                if (values.route) {
                    values.route = values.route.key;
                }
                if (this.props.route) {
                    values.route = this.props.route;
                }

                values.text = undefined;

                this.props.onCreateRequest(values);
                this.form.current.resetFields();
            }
        );
    }

    onModalCancel = () => {
        this.form.current.resetFields();

        this.props.onModalCancel();
    }

    render() {
        return [
            (
                <Button
                    onClick={() => this.props.onModalOpen()}
                >
                    Создать заявку
                </Button>
            ),
            (
                <Modal
                    visible={this.props.modal_visible}
                    title={'Новая заявка'}

                    onOk={this.onModalOk}
                    onCancel={this.onModalCancel}
                >
                    <WrappedDeliveryRequestForm
                        ref={this.form}
                        urls={this.props.urls}
                        route={this.props.route}
                    />
                </Modal>
            )
        ];
    }
}


export default DeliveryCreateRequestComponent;
