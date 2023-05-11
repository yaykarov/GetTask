import React from 'react';

import 'moment/locale/ru';
import moment from 'moment';

import { Button } from 'antd';
import { Col } from 'antd';
import { DatePicker } from 'antd';
import { Form } from 'antd';
import { Input } from 'antd';
import { Row } from 'antd';
import { Select } from 'antd';

import { remoteSelectItem } from './RemoteSelect.jsx';


// Todo
const DATE_FORMAT = 'DD.MM.YYYY';


class ExpenseForm extends React.Component {
    onSubmit = (e) => {
        e.preventDefault();

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                if (this.props.initial) {
                    values.pk = this.props.initial.pk;
                }
                this.props.onSubmit(values);
            }
        );
    }

    remoteSelectItem = (key, label, url, width) => {
        return remoteSelectItem(
            this.props.form,
            key,
            label,
            url,
            width,
            this.props.show_labels
        );
    }

    providerItem = () => {
        return this.remoteSelectItem(
            'provider',
            'Поставщик',
            this.props.urls.provider_url,
            '200px'
        );
    }

    costTypeItem = () => {
        let options = [];
        if (this.props.show_administration_expenses || this.props.initial) {
            options.push(
                <Select.Option key='administration' value='administration'>
                    Офисные расходы
                </Select.Option>
            );
        }
        options.push(
            <Select.Option key='industrial' value='industrial'>
                Производственные расходы
            </Select.Option>
        );
        options.push(
            <Select.Option key='material' value='material'>
                Материалы
            </Select.Option>
        );

        return (
            <Form.Item
                key='cost_type_group'
                style={{ marginBottom: 0 }}
                label={this.props.show_labels? 'Группа расходов' : undefined}
            >
                {
                    this.props.form.getFieldDecorator(
                        'cost_type_group',
                        { rules: [{ required: true, message: 'Это поле необходимо!' }] }
                    )(
                        <Select
                            placeholder='Группа расходов'
                            style={{ width: '200px'}}
                        >
                            {options}
                        </Select>
                    )
                }
            </Form.Item>
        );
    }

    customerItem = () => {
        return this.remoteSelectItem(
            'customer',
            'Клиент',
            this.props.urls.customer_url,
            '200px'
        );
    }

    administrationCostTypeItem = () => {
        return this.remoteSelectItem(
            'administration_cost_type',
            'Тип расхода',
            this.props.urls.administration_cost_type_url,
            '200px'
        );
    }

    industrialCostTypeItem = () => {
        return this.remoteSelectItem(
            'industrial_cost_type',
            'Тип расхода',
            this.props.urls.industrial_cost_type_url,
            '120px'
        );
    }

    materialTypeItem = () => {
        return this.remoteSelectItem(
            'material_type',
            'Материал',
            this.props.urls.material_type_ac_url,
            '160px'
        )
    }

    amountItem = () => {
        return (
            <Form.Item
                key='amount'
                style={{ marginBottom: 0 }}
                label={this.props.show_labels? 'Сумма' : undefined}
            >
                {
                    this.props.form.getFieldDecorator(
                        'amount',
                        { rules: [{ required: true, message: 'Это поле необходимо!' }] }
                    )(
                        <Input
                            placeholder='Сумма'
                            style={{ width: '100px' }}
                            type='number'
                            min='0'
                            step='0.01'
                        />
                    )
                }
            </Form.Item>
        );
    }

    daysIntervalItem = () => {
        return (
            <Form.Item
                key='days_interval'
                style={{ marginBottom: 0 }}
                label={this.props.show_labels? 'Интервал' : undefined}
            >
                {
                    this.props.form.getFieldDecorator(
                        'days_interval',
                        { rules: [{ required: true, message: 'Это поле необходимо!' }] }
                    )(
                        <DatePicker.RangePicker
                            format={DATE_FORMAT}
                            placeholder={['С', 'По']}
                            style={{ width: '240px' }}
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
                label={this.props.show_labels? 'Комментарий' : undefined}
            >
                {
                    this.props.form.getFieldDecorator(
                        'comment',
                        { rules: [{ required: true, message: 'Это поле необходимо!' }] }
                    )(
                        <Input.TextArea
                            placeholder='Комментарий'
                            style={{ width: '320px' }}
                        />
                    )
                }
            </Form.Item>
        );
    }

    submitButtonItem = () => {
        return (
            <Form.Item key='submit' style={{ marginBottom: 0 }}>
                <Button type='primary' htmlType='submit'>
                    Заявить расход
                </Button>
            </Form.Item>
        );
    }

    render() {
        let col1 = [];
        col1.push(this.providerItem());
        col1.push(this.costTypeItem());

        const cost_type_group = this.props.form.getFieldValue('cost_type_group');

        if (cost_type_group === 'administration') {
            col1.push(this.administrationCostTypeItem());
        } else if (cost_type_group === 'industrial') {
            col1.push(this.industrialCostTypeItem());
            col1.push(this.customerItem());
        } else if (cost_type_group === 'material') {
            col1.push(this.materialTypeItem());
            col1.push(this.customerItem());
        }

        let col2 = [];
        col2.push(this.amountItem());
        if (cost_type_group && cost_type_group !== 'material') {
            col2.push(this.daysIntervalItem());
        }
        col2.push(this.commentItem());
        if (this.props.show_submit_button) {
            col2.push(this.submitButtonItem());
        }

        return (
            <Form
                id={this.props.id}
                labelCol={this.props.show_labels? { span: 10, offset: 0} : undefined}
                wrapperCol={this.props.show_labels? { span: 10, offset: 0} : undefined}
                layout={this.props.layout}
                onSubmit={this.onSubmit}
            >
                <Row
                    type='flex'
                    gutter={[12, 2]}
                >
                    <Col
                        key='col1'
                    >
                        {col1}
                    </Col>
                    <Col
                        key='col2'
                    >
                        {col2}
                    </Col>
                </Row>
            </Form>
        );
    }
}


const WrappedExpenseForm = Form.create(
    {
        mapPropsToFields(props) {
            const names = [
                'provider',
                'cost_type_group',
                'administration_cost_type',
                'customer',
                'industrial_cost_type',
                'material_type',
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
                result.days_interval = Form.createFormField(
                    {
                        'value': [
                            moment(props.initial.first_day, DATE_FORMAT),
                            moment(props.initial.last_day, DATE_FORMAT),
                        ]
                    }
                );
            }

            return result;
        }
    }
)(ExpenseForm);


export default WrappedExpenseForm;
