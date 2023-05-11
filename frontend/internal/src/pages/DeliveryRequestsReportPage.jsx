import React from 'react';

import { Col } from 'antd';
import { Row } from 'antd';
import { Spin } from 'antd';

import DeliveryFilterForm from '../components/DeliveryFilter.jsx';

import { getCookie } from '../utils/cookies.jsx';


export class RequestsReport extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            first_day: this.props.first_day,
            last_day: this.props.last_day,

            operator: null,
            customer: null,
            show_score: false,

            data: {},

            fetching: false
        };

        this.fetchData();
    }

    onSubmitRange = (first_day, last_day, operator, customer, show_score) => {
        this.setState(
            {
                first_day: first_day,
                last_day: last_day,
                operator: operator,
                customer: customer,
                show_score: show_score
            },
            this.fetchData
        );
    }

    fetchData = async () => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.data_url, window.location);
        url.searchParams.set('first_day', this.state.first_day);
        url.searchParams.set('last_day', this.state.last_day);
        if (this.state.operator) {
            url.searchParams.set('operator', this.state.operator.key);
        }
        if (this.state.customer) {
            url.searchParams.set('customer', this.state.customer.key);
        }
        if (this.state.show_score) {
            url.searchParams.set('scores', 'true');
        }

        try {
            let response = await fetch(
                url,
                {
                    headers: new Headers({
                        'X-CSRFToken': getCookie('csrftoken'),
                    }),
                }
            );

            if (response.ok) {
                const body = await response.json();

                if (body.status === 'ok') {
                    this.setState(
                        {
                            data: body.data
                        }
                    );
                }
            }
        } catch (exception) {
            // nothing to do
        }

        this.setState({ fetching: false });
    }

    table = () => {
        let headers = [];

        const statuses = [
            ['Готовых', 'finished_count'],
            ['Отмен с оплатой', 'cancelled_with_payment_count'],
            ['Отмен', 'cancelled_count'],
            ['Просрочено', 'overdue_count']
        ];
        let rows = statuses.map(item => [<td>{item[0]}</td>]);

        for (const [customer, values] of Object.entries(this.state.data)) {
            headers.push(<th>{customer}</th>);
            for (let i = 0; i < statuses.length; ++i) {
                rows[i].push(<td className='text-center'>{values[statuses[i][1]]}</td>);
            }
        }

        return (
            <table
                className='table table-hover rh-table mt-4'
            >
                <thead>
                    <th></th>
                    {headers}
                </thead>
                <tbody>
                    {rows.map(item => <tr>{item}</tr>)}
                </tbody>
            </table>
        );
    }

    render() {
        let components = [];
        components.push(
            <Row
                type='flex'
                gutter={[4, 12]}
            >
                <Col>
                    <DeliveryFilterForm
                        urls={this.props.urls}
                        first_day={this.state.first_day}
                        last_day={this.state.last_day}
                        operator={this.state.operator}
                        onSubmit={this.onSubmitRange}
                        show_score_flag={true}
                    />
                </Col>
            </Row>
        );
        if (this.state.fetching) {
            components.push(
                <Row>
                    <Col>
                        <Spin
                            key='spinner'
                            size='large'
                            spinning={true}
                            style={{ width: '100%'}}
                        />
                    </Col>
                </Row>
            );
        } else {
            components.push(
                <Row>
                    <Col>
                        {this.table()}
                    </Col>
                </Row>
            );
        }
        return components;
    }
}


export default RequestsReport;
