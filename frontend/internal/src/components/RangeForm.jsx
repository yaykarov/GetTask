import React from 'react';

import 'moment/locale/ru';
import moment from 'moment';

import { Button } from 'antd';
import { DatePicker } from 'antd';
import { Form } from 'antd';
import { Input } from 'antd';
import { Select } from 'antd';


// Todo
const DATE_FORMAT = 'DD.MM.YYYY';


class RangeForm extends React.Component {
    onSubmit = (e) => {
        e.stopPropagation();
        e.preventDefault();

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                this.props.onSubmit(
                    values.range[0].format(DATE_FORMAT),
                    values.range[1].format(DATE_FORMAT)
                );
            }
        );
    }

    onMonthChange = (month) => {
        const year = this.props.form.getFieldValue('year');

        const first_day = moment().year(year).month(month).startOf('month');
        const last_day = moment().year(year).month(month).endOf('month');

        this.props.onSubmit(
            first_day.format(DATE_FORMAT),
            last_day.format(DATE_FORMAT),
        );
    }

    onDatesChange = (dates, strings) => {
        if (this.props.onDatesChange) {
            this.props.onDatesChange(
                strings[0],
                strings[1]
            );
        }
    }

    yearItem = () => {
        return (
            <Form.Item
                key='year'
                style={{ marginBottom: 0 }}
            >
                {
                    this.props.form.getFieldDecorator(
                        'year',
                        {}
                    )(
                        <Input
                            placeholder='Год'
                            style={{ width: '100px' }}
                            type='number'
                            min='2015'
                            step='1'
                        />
                    )
                }
            </Form.Item>
        );
    }

    monthItem = () => {
        const months = [
            'Январь',
            'Февраль',
            'Март',
            'Апрель',
            'Май',
            'Июнь',
            'Июль',
            'Август',
            'Сентябрь',
            'Октябрь',
            'Ноябрь',
            'Декабрь',
        ];

        const options = months.map(
            (month, i) => (
                <Select.Option key={i} value={i}>
                    {month}
                </Select.Option>
            )
        );

        return (
            <Form.Item
                key='month'
            >
                {
                    this.props.form.getFieldDecorator(
                        'month',
                        {}
                    )(
                        <Select
                            placeholder='Месяц'
                            style={{ width: '120px'}}
                            onChange={this.onMonthChange}
                        >
                            {options}
                        </Select>
                    )
                }
            </Form.Item>
        );
    }

    rangeItem = () => {
        return (
            <Form.Item key='range'>
                {
                    this.props.form.getFieldDecorator(
                        'range',
                        { rules: [{ required: true }] }
                    )(
                        <DatePicker.RangePicker
                            format={DATE_FORMAT}
                            placeholder={['С', 'По']}
                            style={{ width: '240px' }}
                            onChange={this.onDatesChange}
                        />
                    )
                }
            </Form.Item>
        );
    }

    submitItem = () => {
        return (
            <Form.Item key='submit'>
                <Button type='primary' htmlType='submit'>
                    Обновить
                </Button>
            </Form.Item>
        );
    }

    render() {
        let components = [];
        if (this.props.pre_items) {
            components.push(...this.props.pre_items);
        }
        components.push(this.yearItem());
        components.push(this.monthItem());
        components.push(this.rangeItem());
        components.push(this.submitItem());
        return (
            <Form
                layout='inline'
                onSubmit={this.onSubmit}
            >
                {components}
            </Form>
        );
    }
}


const WrappedRangeForm = Form.create(
        {
            mapPropsToFields(props) {
                return {
                    'year': Form.createFormField(
                        { 'value': moment(props.first_day, DATE_FORMAT).year() }
                    ),
                    'range': Form.createFormField(
                        {
                            'value': [
                                moment(props.first_day, DATE_FORMAT),
                                moment(props.last_day, DATE_FORMAT),
                            ]
                        }
                    )
                }
            }
        }
    )(RangeForm);


export default WrappedRangeForm;
