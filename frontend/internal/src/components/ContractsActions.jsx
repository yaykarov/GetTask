import React from 'react';

import 'moment/locale/ru';
import moment from 'moment';

import { Button } from 'antd';
import { Col } from 'antd';
import { DatePicker } from 'antd';
import { Form } from 'antd';
import { Row } from 'antd';

import { remoteSelectItem } from './RemoteSelect.jsx';


// Todo: move to some common file?
const DATE_FORMAT = 'DD.MM.YYYY';


function submitItem(text, onClick) {
    return (
        <Form.Item
            key='submit'
            style={{ marginBottom: 0 }}
        >
            <Button
                htmlType='submit'
                onClick={onClick}
            >
                {text}
            </Button>
        </Form.Item>
    );
}

function contractorItem(form, url) {
    return remoteSelectItem(
        form,
        'contractor',
        'Подрядчик',
        url,
        '240px',
        false
    );
}


class ContractorForm extends React.Component {
    onSubmit = (e) => {
        e.preventDefault();

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                values.action = 'set_contractor';
                values.contractor = values.contractor.key;

                this.props.onSubmit(values);
            }
        );
    }

    render() {
        return (
            <Form
                layout='inline'
                onSubmit={this.onSubmit}
            >
                {contractorItem(this.props.form, this.props.urls.contractor_ac_url)}
                {submitItem('Установить подрядчика')}
            </Form>
        );
    }
}


const WrappedContractorForm = Form.create({})(ContractorForm);


class DateForm extends React.Component {
    onSubmit = (e) => {
        e.preventDefault();

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                values.action = this.props.action;
                values.date = values.date.format(DATE_FORMAT);

                this.props.onSubmit(values);
            }
        );
    }

    dateItem = () => {
        return (
            <Form.Item
                key='date'
                style={{ marginBottom: 0 }}
            >
                {
                    this.props.form.getFieldDecorator(
                        'date',
                        { rules: [{ required: true, message: 'Это поле необходимо!' }] }
                    )(
                        <DatePicker
                            format={DATE_FORMAT}
                            placeholder={this.props.date_placeholder}
                            style={{ width: '160px' }}
                        />
                    )
                }
            </Form.Item>
        );
    }

    render() {
        return (
            <Form
                layout='inline'
                onSubmit={this.onSubmit}
            >
                {this.dateItem()}
                {submitItem(this.props.button_text)}
            </Form>
        );
    }
}

const WrappedDateForm = Form.create({})(DateForm);


class ProxyForm extends React.Component {
    onSubmit = (e, action) => {
        e.preventDefault();

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                values.action = action;
                values.contractor = values.contractor.key;
                values.proxy = values.proxy.key;

                this.props.onSubmit(values);
            }
        );
    }

    proxyItem = () => {
        const contractor = this.props.form.getFieldValue('contractor');
        return remoteSelectItem(
            this.props.form,
            'proxy',
            'Доверенное лицо',
            this.props.urls.proxy_ac_url,
            '240px',
            false,
            contractor? { contractor: contractor.key } : undefined
        );
    }

    render() {
        return (
            <Form
                layout='inline'
                onSubmit={this.onSubmit}
            >
                {contractorItem(this.props.form, this.props.urls.contractor_ac_url)}
                {this.proxyItem()}
                {submitItem(
                    'Скачать пакеты для подачи УоЗ',
                    (e) => { this.onSubmit(e, 'download_conclude_notifications'); }
                )}
                {submitItem(
                    'Скачать пакеты для подачи УоР',
                    (e) => { this.onSubmit(e, 'download_termination_notifications'); }
                )}
            </Form>
        );
    }
}


const WrappedProxyForm = Form.create({})(ProxyForm);


class ContractsActions extends React.Component {
    render() {
        return [
            <Row
                key='contractor'
                type='flex'
            >
                <Col
                    key='contractor'
                >
                    <WrappedContractorForm
                        urls={this.props.urls}
                        onSubmit={this.props.onSubmit}
                    />
                </Col>
            </Row>,
            <Row
                key='dates'
                type='flex'
            >
                <Col
                    key='begin_date'
                >
                    <WrappedDateForm
                        action='set_begin_date'
                        button_text='Установить дату заключения'
                        date_placeholder='Дата заключения'
                        onSubmit={this.props.onSubmit}
                    />
                </Col>
                <Col
                    key='end_date'
                >
                    <WrappedDateForm
                        action='set_end_date'
                        button_text='Установить дату окончания'
                        date_placeholder='Дата окончания'
                        onSubmit={this.props.onSubmit}
                    />
                </Col>
            </Row>,
            <Row
                key='proxy'
                type='flex'
            >
                <Col>
                    <WrappedProxyForm
                        urls={this.props.urls}
                        onSubmit={this.props.onSubmit}
                    />
                </Col>
            </Row>
        ];
    }
}


export default ContractsActions;
