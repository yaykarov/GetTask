import React from 'react';

import { Button } from 'antd';
import { Form } from 'antd';
import { Icon } from 'antd';
import { Upload } from 'antd';

import { remoteSelectItem } from './RemoteSelect.jsx';


class DeliveryImportForm extends React.Component {
    onSubmit = (e) => {
        if (e) {
            e.stopPropagation();
            e.preventDefault();
        }

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    console.log(errors);
                    return;
                }

                values.customer = values.customer.key;
                this.props.onSubmit(values);
            }
        );
    }

    onUploadChange = (info) => {
        // God, i'm so sorry for that...
        setTimeout(this.onSubmit, 50);
    }

    customerItem = () => {
        return remoteSelectItem(
            this.props.form,
            'customer',
            'Клиент',
            this.props.urls.customer_ac_url,
            '200px'
        );
    }

    uploadItem = () => {
        const key = 'requests';
        return (
            <Form.Item
                key={key}
            >
                {
                    this.props.form.getFieldDecorator(
                        key,
                        {
                            valuePropName: key,
                            rules: [{ required: true, message: 'Это поле необходимо!' }]
                        }
                    )(
                        <Upload
                            name={key}
                            showUploadList={false}
                            beforeUpload={(file) => { return false; }}
                            onChange={this.onUploadChange}
                        >
                            <Button><Icon type='upload' />импорт заявок</Button>
                        </Upload>
                    )
                }
            </Form.Item>
        )
    }

    render() {
        return (
            <Form
                layout='inline'
                onSubmit={this.onSubmit}
            >
                {this.customerItem()}
                {this.uploadItem()}
            </Form>
        );
    }
}


const WrappedDeliveryImportForm = Form.create({})(DeliveryImportForm);


export default WrappedDeliveryImportForm;
