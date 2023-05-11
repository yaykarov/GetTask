import React from 'react';

import 'moment/locale/ru';
import moment from 'moment';

import { Modal } from 'antd';
import { Spin } from 'antd';

import { Button as BSButton} from 'react-bootstrap';

import WrappedOperationForm from './PlannedOperationForm.jsx';

import { amountFormat } from '../utils/format.jsx';

import './Common.css';


class OperationRow extends React.Component {
    render() {
        let cells = [
            <td>{this.props.debit_name}</td>,
            <td>{this.props.credit_name}</td>,
            <td>{this.props.comment}</td>,
            <td>{amountFormat(this.props.amount)}</td>
        ];
        if (this.props.onDeleteOperation) {
            cells.push(
                <td>
                    <BSButton
                        variant='outline-danger'
                        size='sm'
                        onClick={() => this.props.onDeleteOperation(this.props.pk)}
                    >
                        <i className="fa fa-trash"></i>
                    </BSButton>
                </td>
            );
        }
        return (
            <tr>
                {cells}
            </tr>
        );
    }
}


class PaymentScheduleModal extends React.Component {

    table = (operations, onDeleteOperation) => {
        return (
            <table
                className='table table-hover rh-table'
                style={{ 'font-size': '12.8px', color: 'black' }}
            >
                <thead>
                    <th>Дебет</th>
                    <th>Кредит</th>
                    <th>Комментарий</th>
                    <th>Сумма</th>
                    {onDeleteOperation? <th/> : undefined}
                </thead>
                <tbody>
                    {
                        operations.map(
                            operation => (
                                <OperationRow
                                    {...operation}
                                    onDeleteOperation={onDeleteOperation}
                                />
                            )
                        )
                    }
                </tbody>
            </table>
        );
    }

    content = () => {
        if (!this.props.visible) {
            return undefined;
        }

        let components = [];
        if (this.props.fetching) {
            components.push(
                <Spin
                    key='spinner'
                    size='large'
                    spinning={true}
                    style={{ width: '100%'}}
                />
            );
        } else {
            if (this.props.content) {
                const operations = this.props.content.operations;
                if (operations && operations.length > 0) {
                    components.push(<h className='rh-header'>Фактические операции</h>);
                    components.push(this.table(operations));
                } else {
                    components.push(<h className='rh-header'>Фактических операций нет</h>);
                }

                const planned_operations = this.props.content.planned_operations;
                if (planned_operations && planned_operations.length > 0) {
                    components.push(<h className='rh-header'>Планируемые операции</h>);
                    components.push(
                        this.table(planned_operations, this.props.onDeleteOperation)
                    );
                } else {
                    components.push(<h className='rh-header'>Планируемых операций нет</h>);
                }
            } else {
                components.push(<h className='rh-header'>Что-то пошло не так :(</h>);
            }
        }

        // Todo: maybe 'show_planned' flag is better.
        if (moment().isBefore(this.props.initial.date)) {
            components.push(
                <h
                    key='operation_title'
                    className='rh-header'
                >
                    Запланировать операцию
                </h>
            );
            components.push(
                <WrappedOperationForm
                    urls={this.props.urls}
                    initial={this.props.initial}
                    onSubmit={this.props.onCreateOperation}
                />
            );
        }

        return components;
    }

    render() {
        return (
            <Modal
                visible={this.props.visible}
                title={this.props.title}
                width='800px'
                onCancel={this.props.onCancel}
                footer={null}

                transitionName='none'
                maskTransitionName='none'
                style={this.props.visible? undefined : { display: 'none' }}
            >
                {this.content()}
            </Modal>
        )
    }
}


export default PaymentScheduleModal;

