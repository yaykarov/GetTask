import React from 'react';

import 'moment/locale/ru';
import moment from 'moment';


// Todo
const DATE_FORMAT = 'DD.MM.YYYY';


class ClaimRow extends React.Component {

    timestamp = () => {
        return moment(this.props.timestamp).format(DATE_FORMAT);
    }

    claimType = () => {
        const type = this.props.claim_type;
        if (type === 'fine') {
            if (this.props.first_photo !== null) {
                const template = this.props.urls.claims_photos_url_template;
                const url = template.replace('12345', this.props.id);
                return <a href={url} target='_blank'>штраф</a>
            } else {
                return 'штраф';
            }
        } else if (type === 'deduction') {
            return 'вычет'
        } else {
            return 'неизвестный тип О_о';
        }
    }

    operationUrl = (id) => {
        return this.props.urls.operation_url_template.replace('12345', id);
    }

    amountLink = (id, amount) => {
        if (amount !== null) {
            return <a href={this.operationUrl(id)} target='_blank'>{amount}</a>
        } else {
            return '-';
        }
    }

    fineAmount = () => {
        return this.amountLink(this.props.fine_id, this.props.fine_amount);
    }

    deductionAmount = () => {
        return this.amountLink(this.props.id, this.props.amount);
    }

    worker = () => {
        const url = this.props.urls.worker_url_template.replace('12345', this.props.worker_id);
        return <a href={url} target='_blank'>{this.props.worker_full_name}</a>;
    }

    render() {
        return (
            <tr
                style={this.props.warning? { background: '#FDD'} : {}}
            >
                <td key='timestamp' className='text-right'>{this.timestamp()}</td>
                <td key='claim_type' className='text-right'>{this.claimType()}</td>
                <td key='claim_type' className='text-right'>{this.props.deduction_type}</td>
                <td key='customer_name' className='text-center'>{this.props.customer_name}</td>
                <td key='claim_by' className='text-center'>{this.props.claim_by}</td>
                <td key='fine_amount' className='text-right'>{this.fineAmount()}</td>
                <td key='deduction_amount' className='text-right'>{this.deductionAmount()}</td>
                <td key='comment' className='text-center'>{this.props.comment}</td>
                <td key='worker' className='text-center'>{this.worker()}</td>
            </tr>
        );
    }
}


class ClaimsList extends React.Component {
    render() {
        return (
            <table
                key='claims_list'
                className='table table-hover rh-table mt-4'
                style={{ 'font-size': '12.8px', color: 'black' }}
            >
                <thead>
                    <tr>
                        <th className='text-center'>Дата заведения</th>
                        <th className='text-center'>Тип</th>
                        <th className='text-center'>Тип вычета</th>
                        <th className='text-center'>Клиент</th>
                        <th className='text-center'>Претензия от</th>
                        <th className='text-center'>Сумма штрафа</th>
                        <th className='text-center'>Сумма вычета</th>
                        <th className='text-center'>Комментарий<br/>(к вычету)</th>
                        <th className='text-center'>Работник</th>
                    </tr>
                </thead>
                <tbody>
                    {
                        this.props.claims.map(
                            item => (
                                <ClaimRow
                                    key={item.id}
                                    urls={this.props.urls}
                                    {...item}
                                />
                            )
                        )
                    }
                </tbody>
            </table>
        );
    }
}


export default ClaimsList;
