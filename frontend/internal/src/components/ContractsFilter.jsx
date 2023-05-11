import React from 'react';

import { Button } from 'antd';
import { Form } from 'antd';
import { Select } from 'antd';


class ContractsFilterForm extends React.Component {
    onSubmit = (e) => {
        e.preventDefault();

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                this.props.onFilterUpdate(values);
            }
        );
    }

    hint = (flags) => {
        const titles = [
            ['Дата начала', 'есть', 'нет'],          // 0
            ['Справка об УоЗ', 'есть', 'нет'],       // 1
            ['СНИЛС', 'есть', 'нет (или не важно)'], // 2
            ['Дата расторжения', 'есть', 'нет'],     // 3
            ['Справка об УоР', 'есть', 'нет'],       // 4
            ['Отсутствовал больше 7 дней', 'да', 'не важно'],        // 5
            ['Находился в статусе больше 3 дней', 'да', 'не важно'], // 6
        ];

        let text = '';
        for (let i = 0; i < titles.length; ++i) {
            const title = titles[i][0];
            const yes = titles[i][1];
            const no = titles[i][2];

            let answer = no;
            if ((flags >> i) & 1) {
                answer = yes;
            }
            
            text += (title + ': ' + answer + '\n');
        }

        return text;
    }

    filterSelectItem = () => {
        let items = [
            {
                key: 'all',
                title: 'Все договора',
                hint: 'Абсолютно все договора, не важно, активные или нет',
            },
            {
                key: 'active',
                title: 'Договора без дат',
                hint: 'Вообще все активные договора,\nу которых нет ни даты начала,\nни даты окончания'
            },
            {
                key: 'to_register',
                title: 'На оформление',
                hint: 'Есть выходы за последние 4 дня,\nвсего выходов больше 7,\nдокументы заканчиваются не раньше, чем через 7 дней'
            },
            {
                key: 'registration_in_progress',
                title: 'В оформлении',
                hint: this.hint(0b1),
            },
            {
                key: 'registration_expiring',
                title: 'В оформлении, уже просрочены',
                hint: this.hint(0b1000001),
            },
            {
                key: 'snils_expiring',
                title: 'Уведомлено, нет СНИЛС',
                hint: this.hint(0b11),
            },
            {
                key: 'registered_with_notification_with_snils',
                title: 'Уведомлено, СНИЛС есть',
                hint: this.hint(0b10100),
            },
            {
                key: 'to_fire',
                title: 'На расторжение',
                hint: this.hint(0b100011),
            },
            {
                key: 'firing_in_progress',
                title: 'Расторгаются',
                hint: this.hint(0b1011),
            },
            {
                key: 'firing_expiring',
                title: 'Расторгаются, уже просрочены',
                hint: this.hint(0b1001011),
            },
            {
                key: 'fired',
                title: 'Расторгнуто',
                hint: this.hint(0b0011011),
            },
        ];

        let options = items.map(
            item => (
                <Select.Option
                    key={item.key}
                    value={item.key}
                    title={item.hint}
                >
                    {item.title}
                </Select.Option>
            )
        );

        return (
            <Form.Item
                key='filter'
                style={{ marginBottom: 0 }}
                label='Фильтр:'
            >
                {
                    this.props.form.getFieldDecorator(
                        'filter',
                        { rules: [{ required: true, message: 'Это поле необходимо!' }] }
                    )(
                        <Select
                            placeholder=''
                            style={{ width: '240px'}}
                        >
                            {options}
                        </Select>
                    )
                }
            </Form.Item>
        );
    }

    submitItem = () => {
        return (
            <Form.Item
                key='submit'
                style={{ marginBottom: 0 }}
            >
                <Button
                    htmlType='submit'
                >
                    Выбрать
                </Button>
            </Form.Item>
        );
    }

    render() {
        return (
            <Form
                layout='inline'
                onSubmit={this.onSubmit}
            >
                {this.filterSelectItem()}
                {this.submitItem()}
            </Form>
        );
    }
}


const ContractsFilter = Form.create(
    {
        mapPropsToFields(props) {
            let result = {};
            if (props.filter) {
                result.filter = Form.createFormField({ value: props.filter });
            }
            return result;
        }
    }
)(ContractsFilterForm);


export default ContractsFilter;
