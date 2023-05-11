import React from 'react';

import { Checkbox, Form } from 'antd';

import WrappedRangeForm from '../components/RangeForm.jsx';
import RemoteSelect from '../components/RemoteSelect.jsx';


export class DeliveryFilterForm extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            first_day: this.props.first_day,
            last_day: this.props.last_day,
            operator: this.props.operator,
            customer: this.props.customer,
            show_score: this.props.show_score,
        };
    }

    onDatesChange = (first_day, last_day) => {
        this.setState(
            {
                first_day: first_day,
                last_day: last_day,
            }
        );
    }

    onShowScoreChange = (e) => {
        this.setState({show_score: e.target.checked});
    }

    onSubmit = (first_day, last_day) => {
        this.onDatesChange(first_day, last_day);
        this.props.onSubmit(
            first_day,
            last_day,
            this.state.operator,
            this.state.customer,
            this.state.show_score
        );
    }

    render() {
        let operator_item = (
            <Form.Item key='operator'>
                <RemoteSelect
                    url={this.props.urls.operator_ac_url}
                    width='160px'
                    placeholder='Оператор'
                    value={this.state.operator}
                    onChange={(value) => this.setState({ operator: value })}
                />
            </Form.Item>
        );
        let customer_item = (
            <Form.Item key='customer'>
                <RemoteSelect
                    url={this.props.urls.customer_ac_url}
                    width='200px'
                    placeholder='Клиент'
                    value={this.state.customer}
                    onChange={(value) => this.setState({ customer: value })}
                />
            </Form.Item>
        );
        let items = [operator_item, customer_item];
        if (this.props.show_score_flag) {
            let score_flag = (
                <Form.Item key='score'>
                    <Checkbox
                        onChange={this.onShowScoreChange}
                    >
                        Очки, а не кол-во
                    </Checkbox>
                </Form.Item>
            );
            items.push(score_flag);
        }
        return (
            <WrappedRangeForm
                pre_items={items}
                first_day={this.state.first_day}
                last_day={this.state.last_day}
                onDatesChange={this.onDatesChange}
                onSubmit={this.onSubmit}
            />
        );
    }
}


export default DeliveryFilterForm;
