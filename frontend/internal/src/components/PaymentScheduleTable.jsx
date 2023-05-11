import React from 'react';

import { Spin } from 'antd';

import 'moment/locale/ru';
import moment from 'moment';

import { amountFormat } from '../utils/format.jsx';

import './PaymentScheduleTable.css'


// Todo
const DATE_FORMAT = 'DD.MM.YYYY';


class AccountBlock extends React.Component {
    balance_cells = () => {
        return [<td>Остаток</td>, <td></td>].concat(
            this.props.balance.map(
                amount => <td className='balance-cell text-right'>{amountFormat(amount)}</td>
            )
        );
    }

    color = (type) => {
        if (type === 'debit') {
            return '#EFE';
        }
        if (type === 'credit') {
            return '#FEE';
        }
        return 'red';
    }

    amountCellColor = (item, type) => {
        if (item.has_planned_operations) {
            return '#DDF';
        } else {
            return this.color(type);
        }
    }

    cellClass = (item, day_index) => {
        let name = 'text-right';
        if (item.has_planned_operations) {
            name += ' planned-operations-cell';
        }

        const cell_day = this.props.first_day.clone().add(day_index, 'days');
        if (moment().isBefore(cell_day)) {
            name += ' future-cell';
        }

        return name;
    }

    cells = (main_cell, items, turnover, type) => {
        return [main_cell, <td>Итого:</td>].concat(
            items.map(
                (item, index) => (
                    <td
                        className={this.cellClass(item, index)}
                        onMouseDown={
                            () => {
                                this.props.onAmountClick(
                                    { pk: this.props.pk, name: this.props.name },
                                    null,
                                    index,
                                    type
                                );
                            }
                        }
                    >
                        {amountFormat(item.amount)}
                    </td>
                )
            )
        ).concat(
            [<td className='text-right'>{amountFormat(turnover)}</td>]
        );
    }

    accountHref = (pk, name) => {
        const url = this.props.urls.account_url_template.replace('12345', pk);
        return (
            <a href={url} target='_blank'>{name}</a>
        );
    }

    childRow = (account, type) => {
        return (
            <tr className={type + '-row'}>
                <td></td>
                <td
                    style={{ 'whiteSpace': 'nowrap' }}
                >
                    {this.accountHref(account.pk, account.name)}
                </td>
                {
                    account.operations.map(
                        (item, index) => (
                            <td
                                className={this.cellClass(item, index)}
                                onMouseDown={
                                    () => {
                                        this.props.onAmountClick(
                                            { pk: this.props.pk, name: this.props.name },
                                            { pk: account.pk, name: account.name },
                                            index,
                                            type
                                        );
                                    }
                                }
                            >
                                {amountFormat(item.amount)}
                            </td>
                        )
                    )
                }
                <td className='text-right'>{amountFormat(account.turnover)}</td>
            </tr>
        );
    }

    mainCell = (operations, fetching, text, type) => {
        let components = [];

        if (operations) {
            components.push('-');
        } else {
            if (fetching) {
                components.push(
                    <Spin
                        key='spinner'
                        size='small'
                        spinning={true}
                    />
                );
            } else {
                components.push('+')
            }
        }
        components.push(' ' + text);

        const onMouseDown = fetching?
            undefined :
            () => this.props.onToggle(this.props.index, this.props.pk, type);

        return (
            <td
                onMouseDown={onMouseDown}
                style={{ 'whiteSpace': 'nowrap' }}
            >
                {components}
            </td>
        );
    }

    render() {
        let name_rowspan = 3;
        if (this.props.debit_operations) {
            name_rowspan += this.props.debit_operations.length;
        }
        if (this.props.credit_operations) {
            name_rowspan += this.props.credit_operations.length;
        }

        let rows = [];
        rows.push(
            <tr
                key='balance'
            >
                <td
                    rowspan={name_rowspan}
                >
                    {this.accountHref(this.props.pk, this.props.name)}
                </td>
                {this.balance_cells()}
            </tr>
        );
        rows.push(
            <tr
                key='debit'
                className='debit-row'
            >
                {
                    this.cells(
                        this.mainCell(
                            this.props.debit_operations,
                            this.props.debit_fetching,
                            'Доход',
                            'debit'
                        ),
                        this.props.debit,
                        this.props.turnover_debit,
                        'debit'
                    )
                }
            </tr>
        );
        if (this.props.debit_operations) {
            this.props.debit_operations.forEach(
                account => { rows.push(this.childRow(account, 'debit')); }
            );
        }
        rows.push(
            <tr
                key='credit'
                className='credit-row'
            >
                {
                    this.cells(
                        this.mainCell(
                            this.props.credit_operations,
                            this.props.credit_fetching,
                            'Расход',
                            'credit'
                        ),
                        this.props.credit,
                        this.props.turnover_credit,
                        'credit'
                    )
                }
            </tr>
        );
        if (this.props.credit_operations) {
            this.props.credit_operations.forEach(
                account => { rows.push(this.childRow(account, 'credit')); }
            );
        }

        return rows;
    }
}


class PaymentScheduleTable extends React.Component {
    render() {
        const first_day = moment(this.props.first_day, DATE_FORMAT);
        const last_day = moment(this.props.last_day, DATE_FORMAT);

        const days = moment.duration(last_day.diff(first_day)).asDays() + 1;

        let header_row_1 = [];
        let header_row_2 = [];

        for (let i = 0; i < days; ++i) {
            const day = first_day.clone().add(i, 'days');
            let className = 'text-center';
            if (day.weekday() > 4) {
                className += ' weekend-cell';
            }
            header_row_1.push(<th className={className}>{day.format('DD.MM.YY')}</th>);
            header_row_2.push(<th className={className}>{day.format('ddd')}</th>);
        }

        const accounts = this.props.accounts.map(
            (account, index) => (
                <AccountBlock
                    key={account.pk}
                    first_day={first_day}
                    {...account}
                    index={index}
                    urls={this.props.urls}
                    onToggle={this.props.onToggle}
                    onAmountClick={this.props.onAmountClick}
                />
            )
        );

        return (
            <table
                className='table table-hover rh-table mt-4'
            >
                <thead>
                    <tr>
                        <th
                            colspan='3'
                            rowspan='2'
                            className='text-center'
                        >
                            Наименование
                        </th>
                        {header_row_1}
                        <th
                            rowspan='2'
                        >
                            Оборот
                        </th>
                    </tr>
                    <tr>
                        {header_row_2}
                    </tr>
                </thead>
                <tbody>
                    {accounts}
                </tbody>
            </table>
        )
    }
}


export default PaymentScheduleTable;
