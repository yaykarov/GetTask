import React from 'react';

import { Fragment } from 'react';

import { Col } from 'antd';
import { Row } from 'antd';
import { Spin } from 'antd';

import WrappedRangeForm from '../components/RangeForm.jsx';
import RemoteSelect from '../components/RemoteSelect.jsx';

import { getCookie } from '../utils/cookies.jsx';


export class ImportsReport extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            first_day: this.props.first_day,
            last_day: this.props.last_day,

            customer: null,

            data: [],

            fetching: false
        };

        this.fetchData();
    }

    onSubmitRange = (first_day, last_day) => {
        this.setState(
            {
                first_day: first_day,
                last_day: last_day,
            },
            this.fetchData
        );
    }

    fetchData = async () => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.data_url, window.location);
        url.searchParams.set('first_day', this.state.first_day);
        url.searchParams.set('last_day', this.state.last_day);
        if (this.state.customer) {
            url.searchParams.set('customer', this.state.customer.key);
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
                this.setState({ data: body });
            }
        } catch (exception) {
            // nothing to do
        }

        this.setState({ fetching: false });
    }

    table = () => {
        let rows = this.state.data.map(
            item => {
                let imported_file_label = item.imported_file.name + ' (' +
                    item.imported_file.size + ')';
                let report_cell = '-';
                if (item.report) {
                    let label = item.report.name + ' (' + item.report.size + ')';
                    report_cell = <a href={item.report.url}>{label}</a>;
                }
                return (
                    <tr>
                        <td>{item.timepoint}</td>
                        <td><a href={item.imported_file.url}>{imported_file_label}</a></td>
                        <td>{report_cell}</td>
                        <td>{item.status.text}</td>
                    </tr>
                );
            }
        );
        return (
            <table
                className='table table-hover rh-table mt-4'
            >
                <thead>
                    <th>Дата</th>
                    <th>Файл с заявками (оригинал)</th>
                    <th>Отчет</th>
                    <th>Статус</th>
                </thead>
                <tbody>
                    {rows}
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
                <Col
                    style={{ marginTop: '4px', marginRight: '14px' }}
                >
                    <RemoteSelect
                        url={this.props.urls.customer_ac_url}
                        width='160px'
                        placeholder='Клиент'
                        value={this.state.customer}
                        onChange={(value) => this.setState({ customer: value })}
                    />
                </Col>
                <Col>
                    <WrappedRangeForm
                        first_day={this.state.first_day}
                        last_day={this.state.last_day}
                        onSubmit={this.onSubmitRange}
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


export default ImportsReport;
