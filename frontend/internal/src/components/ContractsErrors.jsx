import React from 'react';

import { Modal } from 'antd';


class ErrorsTable extends React.Component {
    rows = () => {
        return this.props.errors.map(
            item => {
                let errors = item.errors.map(
                    error => (
                        <a
                            href={error.url} 
                            target='_blank'
                        >
                            {error.name}
                        </a>
                    )
                );
                return (
                    <tr>
                        <td>{item.name}</td>
                        <td>{errors}</td>
                    </tr>
                );
            }
        );
    }

    render() {
        if (!this.props.errors) {
            return '';
        }

        return (
            <table
                className='table table-hover rh-table'
            >
                <thead>
                    <tr>
                        <th>Рабочий</th>
                        <th>Ошибки</th>
                    </tr>
                </thead>
                <tbody>
                    {this.rows()}
                </tbody>
            </table>
        );
    }
}


class ContractsErrors extends React.Component {
    render() {
        return (
            <Modal
                visible={this.props.visible}
                title='Возникшие проблемы'
                onCancel={this.props.onCancel}
                footer={null}
            >
                <ErrorsTable
                    errors={this.props.errors}
                />
            </Modal>
        );
    }
}


export default ContractsErrors;
