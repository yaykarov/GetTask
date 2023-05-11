import React from 'react';

import 'moment/locale/ru';
import moment from 'moment';

import { Button } from 'antd';
import { DatePicker } from 'antd';
import { Form } from 'antd';
import { Input } from 'antd';

import { remoteSelectItem } from './RemoteSelect.jsx';


// Todo
const DATE_FORMAT = 'DD.MM.YYYY';


class OperationForm extends React.Component {
    onSubmit = (e) => {
        e.stopPropagation();
        e.preventDefault();

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                this.props.onSubmit(values);
            }
        );
    }

    dateItem = () => {
        return (
            <Form.Item
                key='date'
                style={{ marginBottom: 0 }}
                label='Дата'
            >
                {
                    this.props.form.getFieldDecorator(
                        'date',
                        { rules: [{ required: true }] }
                    )(
                        <DatePicker
                            format={DATE_FORMAT}
                            placeholder='Дата'
                            style={{ width: '280px' }}
                        />
                    )
                }
            </Form.Item>
        );
    }

    accountItem = (key, label) => {
        return remoteSelectItem(
            this.props.form,
            key,
            label,
            this.props.urls.account_ac_url,
            '280px',
            true
        );
    }

    amountItem = () => {
        return (
            <Form.Item
                key='amount'
                style={{ marginBottom: 0 }}
                label='Сумма'
            >
                {
                    this.props.form.getFieldDecorator(
                        'amount',
                        { rules: [{ required: true, message: 'Это поле необходимо!' }] }
                    )(
                        <Input
                            placeholder='Сумма'
                            style={{ width: '280px' }}
                            type='number'
                            min='0'
                            step='0.01'
                        />
                    )
                }
            </Form.Item>
        );
    }

    commentItem = () => {
        return (
            <Form.Item
                key='comment'
                style={{ marginBottom: 0 }}
                label='Комментарий'
            >
                {
                    this.props.form.getFieldDecorator(
                        'comment',
                        {}
                    )(
                        <Input.TextArea
                            placeholder='Комментарий'
                            style={{ width: '280px' }}
                        />
                    )
                }
            </Form.Item>
        );
    }

    submitButtonItem = () => {
        return (
            <Form.Item
                key='submit'
                style={{
                    marginBottom: 0
                }}
                wrapperCol={{ span: 4, offset: 16}}
            >
                <Button
                    type='primary'
                    htmlType='submit'
                >
                    Создать
                </Button>
            </Form.Item>
        );
    }

    render() {
        return (
            <Form
                labelCol={{ span: 6, offset: 0 }}
                wrapperCol={{ span: 14, offset: 0 }}
                onSubmit={this.onSubmit}
            >
                {this.dateItem()}
                {this.accountItem('debit', 'Дебет')}
                {this.accountItem('credit', 'Кредит')}
                {this.amountItem()}
                {this.commentItem()}
                {this.submitButtonItem()}
            </Form>
        );
    }
}


const WrappedOperationForm = Form.create(
    {
        mapPropsToFields(props) {
            const names = [
                'debit',
                'credit',
                'amount',
                'comment'
            ];

            let result = {};
            if (props.initial) {
                names.forEach(
                    name => {
                        if (props.initial[name]) {
                            result[name] = Form.createFormField(
                                { value: props.initial[name] }
                            )
                        }
                    }
                );
                if (props.initial.date) {
                    result.date = Form.createFormField(
                        { value: moment(props.initial.date, DATE_FORMAT) }
                    );
                }
            }

            return result;
        }
    }
)(OperationForm);


export default WrappedOperationForm;
