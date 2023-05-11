import React from 'react';

import { Col } from 'antd';
import { Icon } from 'antd';
import { Row } from 'antd';
import { Spin } from 'antd';

import { getCookie } from '../utils/cookies.jsx';


export class DeliveryCustomersPage extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            data: [],

            fetching: false
        };
    }

    fetchData = async () => {
        this.setState({ fetching: true });

        let url = new URL(this.props.urls.data_url, window.location);

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

    onConfirmClick = async (pk) => {
        let url = new URL(this.props.urls.confirmation_url, window.location);
        url.searchParams.set('pk', pk);

        try {
            let response = await fetch(
                url,
                {
                    method: 'POST',
                    headers: new Headers({
                        'X-CSRFToken': getCookie('csrftoken'),
                    }),
                }
            );
        } catch (exception) {
            // nothing to do
        }

        this.fetchData();
    }

    table = () => {
        let rows = this.state.data.map(
            item => {
                let scans = item.scans.map(
                    (url, i) => {
                        let components = [];

                        components.push(<a href={url} target={'blank'}>скан</a>);
                        if (i < item.scans.length - 1) {
                            components.push(<span>, </span>);
                        }

                        return components;
                    }
                );
                if (scans.length == 0) {
                    scans = '-';
                }
                return (
                    <tr>
                        <td>{item.type}</td>
                        <td>{item.full_name}</td>
                        <td>{item.email}</td>
                        <td>{item.phone}</td>
                        <td>{item.tax_number}</td>
                        <td>{item.reason_code}</td>
                        <td>{item.bank_name}</td>
                        <td>{item.legal_address}</td>
                        <td>{item.mail_address}</td>
                        <td className='text-center'>{scans}</td>
                        <td className='text-center'>
                            <Icon
                                type='plus-square'
                                theme='twoTone'
                                onClick={() => this.onConfirmClick(item.pk)}
                            />
                        </td>
                    </tr>
                );
            }
        );

        return (
            <table
                className='table table-hover rh-table'
            >
                <thead>
                    <th>Тип</th>
                    <th>Название</th>
                    <th>Почта</th>
                    <th>Телефон</th>
                    <th>ИНН</th>
                    <th>КПП</th>
                    <th>Банк</th>
                    <th>Юр. Адрес</th>
                    <th>Почтовый Адрес</th>
                    <th>Сканы</th>
                    <th>Подтвердить</th>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        );
    }

    componentDidMount() {
        this.fetchData();
    }

    render() {
        if (this.state.fetching) {
            return (
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
            return this.table();
        }
    }
}


export default DeliveryCustomersPage;
