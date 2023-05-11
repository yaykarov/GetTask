import React from 'react';

import { Button } from 'antd';
import { Checkbox } from 'antd';
import { Form } from 'antd';
import { Modal } from 'antd';


class ColumnsForm extends React.Component {
    render() {
        let fields = [];
        this.props.columns.forEach(
            field => {
                fields.push(
                    <Form.Item
                        key={field.data}
                        name={field.data}
                        style={{ marginBottom: 0}}
                    >
                        {
                            this.props.form.getFieldDecorator(
                                field.data,
                                {
                                    valuePropName: 'checked',
                                    initialValue: field.checked,
                                    rules: [{
                                        type: 'boolean',
                                    }],
                                }
                            )(
                                <Checkbox
                                    disabled={field.required? true : undefined}
                                >
                                    {field.title}
                                </Checkbox>
                            )
                        }
                    </Form.Item>
                );
            }
        );
        return (
            <Form>
                {fields}
            </Form>
        )
    }
}


const WrappedColumnsForm = Form.create()(ColumnsForm);


export class ColumnsFilter extends React.Component {
    constructor(props) {
        super(props);

        this.form = React.createRef();

        this.state = {
            modal_visible: false
        };
    }

    onSetupClick = () => {
        this.setState({ modal_visible: true});
    }

    onModalOk = () => {
        this.form.current.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                this.setState({ modal_visible: false});

                this.props.onFilterUpdate(values);
            }
        )
    }

    onModalCancel = () => {
        this.setState({ modal_visible: false});
    }

    render() {
        return [
            (
                <Button
                    key='button'
                    onClick={this.onSetupClick}
                >
                    Настроить столбцы
                </Button>
            ),
            (
                <Modal
                    key='modal'
                    visible={this.state.modal_visible}
                    title='Выбор столбцов'

                    onOk={this.onModalOk}
                    onCancel={this.onModalCancel}
                >
                    <WrappedColumnsForm
                        ref={this.form}
                        columns={this.props.columns}
                    />
                </Modal>
            )
        ];
    }
}

