import React from 'react';

import { Fragment } from 'react';

import { Form } from 'antd';
import { Input } from 'antd';
import { Modal } from 'antd';
import { Tag } from 'antd';

import { Button as BSButton} from 'react-bootstrap';


class CommentForm extends React.Component {
    render() {
        return (
            <Form>
                <Form.Item>
                    {
                        this.props.form.getFieldDecorator(
                            'comment',
                            { rules: [{ required: false }] }
                        )(
                            <Input.TextArea placeholder='Текст комментария'/>
                        )
                    }
                </Form.Item>
            </Form>
        )
    }
}


const WrappedCommentForm = Form.create({})(CommentForm);


class ExpensesBlock extends React.Component {
    constructor(props) {
        super(props);

        this.form = React.createRef();

        this.state = {
            modal_visible: false
        }
    }

    onOk = () => {
        this.props.onExpenseAction(
            this.state.expense_id,
            this.state.code,
            this.form.current.getFieldValue('comment')
        );

        this.setState({ modal_visible: false });
    }

    onProviderClick = (e, expense_id) => {
        e.preventDefault();

        this.props.onEditProvider(expense_id);
    }

    status = (code) => {
        let color = 'red';
        let text = code;
        if (code === 'new') {
            text = 'новый';
            color = 'green';
        } else if (code === 'confirmed') {
            text = 'одобрен';
            color = 'blue';
        } else if (code === 'confirmed_waiting_supply') {
            text = <Fragment>одобрен,<br/>ждем поступления</Fragment>;
            color = 'geekblue';
        } else if (code === 'confirmed_supplied') {
            text = 'одобрен, поступил';
            color = 'blue';
        } else if (code === 'rejected') {
            text = 'отклонен';
            color = 'red';
        } else if (code === 'payed') {
            text = 'оплачен';
            color = 'gold';
        }

        return <Tag color={color}>{text}</Tag>
    }

    action = (expense_id, code) => {
        let type = 'outline-danger';
        let text = code;
        let action = (e => this.props.onExpenseAction(expense_id, code));

        if (code === 'edit') {
            type = 'outline-primary';
            text = <i className="fa fa-edit"></i>;
        } else if (code === 'delete') {
            type = 'outline-danger';
            text = <i className="fa fa-trash"></i>;
        } else if (code === 'confirm') {
            type = 'outline-primary';
            text = 'одобрить';
        } else if (code === 'confirm_supply') {
            type = 'outline-primary';
            text = 'подтвердить поступление';
        } else if (code === 'unconfirm') {
            type = 'outline-danger';
            text = 'отменить одобрение';
        } else if (code === 'reject') {
            type = 'outline-danger';
            text = 'отклонить';
            action = (
                e => this.setState(
                    {
                        modal_visible: true,
                        expense_id: expense_id,
                        code: code
                    }
                )
            );
        }

        return (
            <BSButton
                key={code}
                variant={type}
                size='sm'
                className='ml-2'
                onClick={action}
            >
                {text}
            </BSButton>
        );
    }

    actions = (expense_id, actions) => {
        return actions.map(action => this.action(expense_id, action))
    }

    itemType = (item) => {
        const url = this.props.urls.account_url_template.replace('12345', item.debit);
        return (
            <a href={url} target='_blank'>{item.type}</a>
        );
    }

    render() {
        let children = [];

        children.push(
            <table
                key='table'
                className='table table-hover rh-table mt-4'
                style={{ 'font-size': '12.8px', color: 'black' }}
            >
                <thead>
                    <tr>
                        <th className='text-center'>№</th>
                        <th className='text-center'>Дата заведения</th>
                        <th className='text-center'>Поставщик</th>
                        <th className='text-center'>Клиент</th>
                        <th className='text-center'>Тип расхода</th>
                        <th className='text-center'>С</th>
                        <th className='text-center'>По</th>
                        <th className='text-center'>Сумма заявки</th>
                        <th className='text-center'>Сумма поступления</th>
                        <th className='text-center'>Сумма оплаты</th>
                        <th className='text-center'>Сумма продажи</th>
                        <th className='text-center'>Статус</th>
                        <th className='text-center'>Комментарий</th>
                        <th className='text-center'></th>
                    </tr>
                </thead>
                <tbody>
                {
                    this.props.items.map(
                        item => {
                            return (
                                <tr key={item.id}>
                                    <td key='id' className='text-right'>{item.id}</td>
                                    <td key='timestamp' className='text-right'>{item.timestamp}</td>
                                    <td key='name' className='text-center'>
                                        <a href='#' onClick={e => this.onProviderClick(e, item.id)}>{item.name}</a>
                                    </td>
                                    <td key='customer' className='text-center'>{item.customer}</td>
                                    <td key='type' className='text-center'>{this.itemType(item)}</td>
                                    <td key='first_day' className='text-right'>{item.first_day}</td>
                                    <td key='last_day' className='text-right'>{item.last_day}</td>
                                    <td key='amount' className='text-right'>{item.amount}</td>
                                    <td key='supplied_amount' className='text-right'>{item.supplied_amount}</td>
                                    <td key='payed_amount' className='text-right'>{item.payed_amount}</td>
                                    <td key='sold_amount' className='text-right'>{item.sold_amount}</td>
                                    <td key='status' className='text-center'>{this.status(item.status)}</td>
                                    <td key='comment' className='text-center'>{item.comment}</td>
                                    <td key='buttons' className='text-left' style={{ display: 'inline-block', 'whiteSpace': 'nowrap' }}>{this.actions(item.id, item.actions)}</td>
                                </tr>
                            );
                        }
                    )
                }
                </tbody>
            </table>
        );

        let components = [];
        components.push(
            <Modal
                key='modal'
                visible={this.state.modal_visible}
                title='Комментарий к отклонению'
                width={'480px'}
                onOk={this.onOk}
                onCancel={() => this.setState({ modal_visible: false })}
                okText='Отклонить расход'
                cancelText='Отмена'
            >
                <WrappedCommentForm
                    ref={this.form}
                />
            </Modal>
        );
        components.push(
            <div key='div'>
                {children}
            </div>
        );

        return components;
    }
}

export default ExpensesBlock;
