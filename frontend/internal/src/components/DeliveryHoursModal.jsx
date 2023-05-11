import React from 'react';

import { Form } from 'antd';
import { Input } from 'antd';
import { Modal } from 'antd';


class DeliveryHoursForm extends React.Component {

    workerItem = (worker_name, worker_pk) => {
        return (
            <Form.Item
                key={worker_pk}
                style={{ marginBottom: 0 }}
                label={worker_name}
            >
                {
                    this.props.form.getFieldDecorator(
                        worker_pk,
                        { rules: [{ required: true, message: 'Это поле необходимо!' }] }
                    )(
                        <Input
                            placeholder='часов'
                            style={{ width: '80px' }}
                            type='number'
                            min='0'
                            step='0.1'
                            disabled={true}
                        />
                    )
                }
            </Form.Item>
        );
    }

    render() {
        const items = this.props.workers?
            this.props.workers.map(
                worker => this.workerItem(worker.label, worker.key)
            ) : [];
        return (
            <Form
                labelCol={{ span: 16, offset: 0}}
                wrapperCol={{ span: 5, offset: 0}}
            >
                {items}
            </Form>
        );
    }
}


const WrappedDeliveryHoursForm = Form.create(
    {
        mapPropsToFields(props) {
            let result = {};
            if (props.workers) {
                props.workers.forEach(
                    worker => {
                        result[worker.key] = Form.createFormField(
                            { value: worker.hours }
                        );
                    }
                );
            }

            return result;
        }
    }
)(DeliveryHoursForm);


class DeliveryHoursModal extends React.Component {
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

                this.props.onSubmit(
                    this.props.row_index,
                    this.props.row_pk,
                    values
                );
            }
        );
    }

    render() {
        return (
            <Modal
                visible={this.props.visible}
                title='Часы к оплате'
                onCancel={this.props.onCancel}
                onOk={this.onOk}
            >
                <WrappedDeliveryHoursForm
                    ref={this.form}
                    workers={this.props.workers}
                />
            </Modal>
        );
    }
}


export default DeliveryHoursModal;
