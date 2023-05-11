import React from 'react';

import { Button } from 'antd';
import { Form } from 'antd';
import { Modal } from 'antd';

import { remoteSelectItem } from './RemoteSelect.jsx';


class DeliveryAttachItemForm extends React.Component {

    onSubmit = (e) => {
        e.stopPropagation();

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                this.props.onSubmit(values.code.key);
            }
        );
    }

    codeItem = () => {
        return remoteSelectItem(
            this.props.form,
            'code',
            'Прикрепить индекс',
            this.props.urls.item_ac_url,
            '450px',
            false,
            { request: this.props.request }
        );
    }

    submitItem = () => {
        return (
            <Form.Item
                key='submit_button'
            >
                <Button
                    type='primary'
                    onClick={this.onSubmit}
                >
                    Прикрепить
                </Button>
            </Form.Item>
        );
    }

    render() {
        return (
            <Form
                layout='inline'
                onFieldsChange={this.onFieldsChange}
            >
                {this.codeItem()}
                {this.submitItem()}
            </Form>
        );
    }
}


const WrappedDeliveryAttachItemForm = Form.create({})(DeliveryAttachItemForm);


export class DeliveryAttachItemModal extends React.Component {

    onItemAttachClick = (item_pk) => {
        this.props.onItemAttachClick(this.props.request, item_pk);
    }

    render() {
        return (
            <Modal
                visible={this.props.visible}
                title={'Добавить адрес в маршрут'}
                width={'640px'}
                onCancel={this.props.onCancel}
                footer={null}
            >
                <WrappedDeliveryAttachItemForm
                    urls={this.props.urls}
                    request={this.props.request}
                    onSubmit={this.onItemAttachClick}
                />
                <Button
                    type='primary'
                    className='mt-4'
                    onClick={() => this.props.onNewItemClick(this.props.route)}
                >
                    Прикрепить новую заявку
                </Button>
            </Modal>
        );
    }
}
