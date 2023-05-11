import React from 'react';

import { Button } from 'antd';
import { Col } from 'antd';
import { DatePicker } from 'antd';
import { Form } from 'antd';
import { Icon } from 'antd';
import { Input } from 'antd';
import { Row } from 'antd';
import { Select } from 'antd';
import { Upload } from 'antd';

import RemoteSelect from './RemoteSelect.jsx';


// Todo: move to some common file?
const DATE_FORMAT = 'DD.MM.YYYY';


/**
 * @param onSubmit - callback for submitting values.
 * @param Todo: autocomplete_urls
 */
class ClaimForm extends React.Component {

    normalizedData = (values) => {
        const images = values.images || [];
        const files = [];
        images.forEach(
            image => {
                files.push(image.originFileObj);
            }
        );

        let data = Object.assign({}, values);
        delete data.images;

        // Todo: autoformat for selected items/dates/etc.?
        if (data.customer) {
            data.customer = data.customer.key;
        }
        if (data.provider) {
            data.provider = data.provider.key;
        }
        if (data.worker) {
            data.worker = data.worker.key;
        }
        if (data.turnout) {
            data.turnout = data.turnout.key;
        }
        if (data.industrial_cost_type) {
            data.industrial_cost_type = data.industrial_cost_type.key;
        }
        if (data.expense) {
            data.expense = data.expense.key;
        }

        if (data.fine_date) {
            data.fine_date = data.fine_date.format(DATE_FORMAT);
        }
        if (data.deduction_date) {
            data.deduction_date = data.deduction_date.format(DATE_FORMAT);
        }

        return {
            data: data,
            files: files
        };
    }

    onSubmit = (e) => {
        e.stopPropagation();

        this.props.form.validateFieldsAndScroll(
            (errors, values) => {
                if (errors) {
                    return;
                }

                const normolized = this.normalizedData(values);
                this.props.onSubmit(normolized.data, normolized.files);
            }
        );
    }

    option = (key, text) => {
        return <Select.Option key={key} value={key}>{text}</Select.Option>;
    }

    // Todo: some common func?
    formItem = (key, child) => {
        return (
            <Form.Item
                key={key}
                style={{ marginBottom: 0 }}
            >
                {
                    this.props.form.getFieldDecorator(
                        key,
                        { rules: [{ required: true, message: 'Это поле необходимо!' }] }
                    )(child)
                }
            </Form.Item>
        );
    }

    // Todo: some common func?
    // Todo: remove options param
    remoteSelectItem = (key, label, url, width, forward) => {
        return this.formItem(
            key,
            (
                <RemoteSelect
                    url={url}
                    placeholder={label}
                    width={width}
                    forward={forward}
                />
            )
        );
    }

    claimTypeItem = () => {
        return this.formItem(
            'claim_type',
            (
                <Select
                    placeholder='Вычет/штраф'
                    style={{ width: '200px'}}
                >
                    <Select.Option key='deduction' value='deduction'>Вычет</Select.Option>
                    <Select.Option key='fine' value='fine'>Штраф</Select.Option>
                </Select>
            )
        );
    }

    normFile = (e) => {
        if (Array.isArray(e)) {
          return e;
        }
        return e && e.fileList;
    }

    documentItem = () => {
        const images = this.props.form.getFieldValue('images');
        const images_num = images? images.length : 0;
        const label = 'приложить скан документа (' + images_num + ')';

        let clear_button = null;
        if (images_num > 0) {
            clear_button = (
                <Button
                    key='clear_button'
                    onClick={(e) => { e.stopPropagation(); this.props.form.resetFields(['images']); }}
                >
                    <Icon type='delete' />
                </Button>
            );
        }

        const key = 'images';
        return (
            <Form.Item
                key={key}
                style={{ marginBottom: 0 }}
            >
                {
                    this.props.form.getFieldDecorator(
                        key,
                        {
                            valuePropName: 'images',
                            getValueFromEvent: this.normFile,
                        }
                    )(
                        <Upload
                            name='images'
                            listType='picture'
                            multiple
                            showUploadList={false}
                            beforeUpload={(file) => { return false; }}
                            fileList={images}
                        >
                            <Button.Group>
                                <Button><Icon type='upload' />{label}</Button>
                                { clear_button }
                            </Button.Group>
                        </Upload>
                    )
                }
            </Form.Item>
        );
    }

    commentItem = () => {
        return this.formItem(
            'comment',
            (
                <Input.TextArea
                    placeholder='Комментарий'
                    style={{ width: '320px' }}
                />
            )
        );
    }

    fineAmountItem = () => {
        return this.formItem(
            'fine_amount',
            (
                <Input
                    placeholder='Сумма штрафа'
                    style={{ width: '320px' }}
                    type='number'
                    min='0'
                    step='0.01'
                />
            )
        )
    }

    fineDateItem = () => {
        return this.formItem(
            'fine_date',
            (
                <DatePicker
                    format={DATE_FORMAT}
                    placeholder='Дата штрафа'
                    style={{ width: '240px' }}
                />
            )
        )
    }

    customerItem = () => {
        return this.remoteSelectItem(
            'customer',
            'Клиент',
            this.props.urls.customer_url,
            '200px',
        );
    }

    fineTypeItem = () => {
        return this.formItem(
            'fine_type',
            (
                <Select
                    placeholder='Тип штрафа'
                    style={{ width: '240px'}}
                >
                    <Select.Option key='customer' value='customer'>от клиента</Select.Option>
                    <Select.Option key='provider' value='provider'>от поставщика</Select.Option>
                </Select>
            )
        );
    }

    providerItem = () => {
        return this.remoteSelectItem(
            'provider',
            'Поставщик',
            this.props.urls.provider_url,
            '240px',
        );
    }

    workerItem = (customer) => {
        return this.remoteSelectItem(
            'worker',
            'Работник',
            this.props.urls.worker_ac_url,
            '200px',
            { customer: customer.key }
        );
    }

    deductionDateTypeItem = (claim_type) => {
        let options = [this.option('turnout', 'к выходу')];
        if (claim_type === 'fine') {
            options.push(this.option('fine_date', 'к дате штрафа'));
        } else if (claim_type === 'deduction') {
            options.push(this.option('date', 'к дате'));
        }

        return this.formItem(
            'deduction_date_type',
            (
                <Select
                    placeholder='Вычет привязать'
                    style={{ width: '240px'}}
                >
                    {options}
                </Select>
            )
        );
    }

    deductionDateItem = () => {
        return this.formItem(
            'deduction_date',
            (
                <DatePicker
                    format={DATE_FORMAT}
                    placeholder='Дата вычета'
                    style={{ width: '130px' }}
                />
            )
        )
    }

    turnoutItem = (customer, worker) => {
        return this.remoteSelectItem(
            'turnout',
            'Выход',
            this.props.urls.turnout_ac_url,
            '200px',
            { customer: customer.key, worker: worker.key }
        );
    }

    deductionAmountTypeItem = () => {
        return this.formItem(
            'deduction_amount_type',
            (
                <Select
                    placeholder='Сумма вычета'
                    style={{ width: '320px'}}
                >
                    {this.option('by_fine', 'по сумме штрафа')}
                    {this.option('arbitrary', 'внесена вручную')}
                </Select>
            )
        );
    }

    deductionAmountItem = () => {
        return this.formItem(
            'deduction_amount',
            (
                <Input
                    placeholder='Сумма вычета'
                    style={{ width: '320px' }}
                    type='number'
                    min='0'
                    step='0.01'
                />
            )
        )
    }

    deductionTypeItem = () => {
        return this.formItem(
            'deduction_type',
            (
                <Select
                    placeholder='Тип вычета'
                    style={{ width: '240px'}}
                >
                    <Select.Option key='disciplinary' value='disciplinary'>дисциплинарный</Select.Option>
                    <Select.Option key='industrial_cost' value='industrial_cost'>за наши услуги</Select.Option>
                    <Select.Option key='material' value='material'>за материалы</Select.Option>
                </Select>
            )
        );
    }

    industrialCostTypeItem = () => {
        return this.remoteSelectItem(
            'industrial_cost_type',
            'Услуга',
            this.props.urls.industrial_cost_type_ac_url,
            '240px',
        );
    }

    expenseItem = (customer) => {
        return this.remoteSelectItem(
            'expense',
            'Закупка',
            this.props.urls.expense_ac_url,
            '240px',
            { customer: customer.key }
        );
    }

    submitItem = () => {
        return (
            <Form.Item
                key='submit_button'
                style={{ marginBottom: 0}}
            >
                <Button
                    type='primary'
                    onClick={this.onSubmit}
                >
                    Внести претензию
                </Button>
            </Form.Item>
        );
    }

    renderItems = () => {
        let col1 = [this.claimTypeItem(), this.customerItem()];

        const customer = this.props.form.getFieldValue('customer');
        const is_customer_selected = !(!customer);
        const is_worker_visible = is_customer_selected;
        if (is_worker_visible) {
            col1.push(this.workerItem(customer));
        }

        let col2 = [];

        const claim_type = this.props.form.getFieldValue('claim_type');
        const is_claim_selected = !(!claim_type);

        const is_fine_type_visible = (claim_type === 'fine');
        if (is_fine_type_visible) {
            col2.push(this.fineTypeItem());
        }

        const fine_type = this.props.form.getFieldValue('fine_type');
        const is_provider_visible = is_fine_type_visible && fine_type === 'provider';
        if (is_provider_visible) {
            col2.push(this.providerItem());
            col2.push(this.fineDateItem());
        }

        const is_deduction_type_visible = (claim_type === 'deduction');
        if (is_deduction_type_visible) {
            col2.push(this.deductionTypeItem());
        }

        const deduction_type = this.props.form.getFieldValue('deduction_type');

        const is_industrial_cost_type_visible = (
            is_deduction_type_visible && deduction_type === 'industrial_cost'
        );
        if (is_industrial_cost_type_visible) {
            col2.push(this.industrialCostTypeItem());
        }

        const is_expense_item_visible = (
            is_customer_selected && is_deduction_type_visible && deduction_type === 'material'
        )
        if (is_expense_item_visible) {
            col2.push(this.expenseItem(customer));
        }

        const worker = this.props.form.getFieldValue('worker');
        const is_deduction_date_type_visible = (
            claim_type === 'deduction' && is_worker_visible && worker
        );
        if (is_deduction_date_type_visible) {
            col2.push(this.deductionDateTypeItem(claim_type));
        }

        const deduction_date_type = this.props.form.getFieldValue('deduction_date_type');

        const is_turnout_visible = (
            worker && (
                (
                    claim_type === 'deduction' &&
                    is_deduction_date_type_visible &&
                    deduction_date_type === 'turnout'
                ) ||
                (
                    claim_type === 'fine' &&
                    is_worker_visible &&
                    is_fine_type_visible &&
                    fine_type === 'customer'
                )
            )
        );
        if (is_turnout_visible) {
            col2.push(this.turnoutItem(customer, worker));
        }

        const is_deduction_date_visible = (
            is_deduction_date_type_visible && deduction_date_type === 'date'
        );
        if (is_deduction_date_visible) {
            col2.push(this.deductionDateItem());
        }


        let col3 = [];

        const is_fine_amount_visible = claim_type === 'fine';
        if (is_fine_amount_visible) {
            col3.push(this.fineAmountItem());
        }

        const is_deduction_amount_type_visible = (claim_type === 'fine');
        if (is_deduction_amount_type_visible) {
            col3.push(this.deductionAmountTypeItem());
        }

        const deduction_amount_type = this.props.form.getFieldValue('deduction_amount_type');
        if (is_deduction_amount_type_visible && deduction_amount_type === 'arbitrary') {
            col3.push(this.deductionAmountItem());
        }

        if (claim_type === 'deduction') {
            col3.push(this.deductionAmountItem());
        }

        if (is_claim_selected) {
            col3.push(this.commentItem());
        }

        if (is_fine_type_visible) {
            col3.push(this.documentItem());
        }
        col3.push(this.submitItem());

        return (
            <Row
                type='flex'
                gutter={[12, 2]}
            >
                <Col
                    key='col1'
                >
                    {col1}
                </Col>
                <Col
                    key='col2'
                >
                    {col2}
                </Col>
                <Col
                    key='col3'
                >
                    {col3}
                </Col>
            </Row>
        );
    }

    render() {
        return (
            <Form
            >
                {this.renderItems()}
            </Form>
        );
    }
}


const WrappedClaimForm = Form.create({})(ClaimForm);


export default WrappedClaimForm;
