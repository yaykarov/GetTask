import React from 'react';

import { Form } from 'antd';
import { Input } from 'antd';
import { Modal } from 'antd';


class ProviderForm extends React.Component {

    render() {
        let items = [];

        items.push(
            <Form.Item key='name' label='Название' style={{ marginBottom: 0 }}>
                {
                    this.props.form.getFieldDecorator(
                        'name',
                        { rules: [{ required: true, message: 'Это поле необходимо!' }] }
                    )(
                        <Input placeholder='Название поставщика'></Input>
                    )
                }
            </Form.Item>
        );
        items.push(
            <Form.Item key='tax_code' label='ИНН' style={{ marginBottom: 0 }}>
                {
                    this.props.form.getFieldDecorator(
                        'tax_code',
                        { rules: [{ required: false, message: 'Это поле необходимо!' }] }
                    )(
                        <Input placeholder='ИНН'></Input>
                    )
                }
            </Form.Item>
        );

        return (
            <Form
                labelCol={{ span:6, offset: 0}}
                wrapperCol={{ span: 10, offset: 0}}
            >
                { items }
            </Form>
        );
    }
}


const WrappedProviderForm = Form.create(
        {
            mapPropsToFields(props) {
                const names = [
                    'name',
                    'tax_code',
                    'cost_type_group',
                    'administration_cost_type',
                    'customer',
                    'industrial_cost_type'
                ];
                let result = {};
                names.forEach(
                    name => {
                        if (props[name]) {
                            result[name] = Form.createFormField({ value: props[name] })
                        }
                    }
                );

                return result;
            }
        }
    )(ProviderForm);


class ProviderModal extends React.Component {
    constructor(props) {
        super(props);

        this.form = React.createRef();
    }

    onOk = () => {
        this.form.current.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                this.props.onSubmit(values);
            }
        );
    }

    render() {
        return (
            <Modal
                visible={this.props.visible}
                title="Завести поставщика"
                width={'50%'}
                onOk={this.onOk}
                onCancel={this.props.onCancel}
                okText="Сохранить"
                cancelText="Отмена"
            >
                <WrappedProviderForm
                    ref={this.form}
                    urls={this.props.urls}
                    {...this.props.initial}
                >
                </WrappedProviderForm>
            </Modal>
        );
    }
}


export default ProviderModal;
