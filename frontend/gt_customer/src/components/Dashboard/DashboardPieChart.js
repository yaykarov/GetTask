import React from 'react';
import { PieChart } from 'react-minimal-pie-chart';
import { useDispatch } from 'react-redux';
import { setFilter } from '../../actions';
import { formatToMoney } from '../../utils';

import styles from './Dashboard.module.scss';

const getItemTotal = (data, item) => {
    return data.items.get(item)?.total || 1;
};

const getPieChartLabel = (totalNumber) => {
    if (!totalNumber) {
        return (
            <div>
                Всего <br />
                заявок
            </div>
        );
    }

    return (
        <div>
            Всего <br />
            заявок на <br />
            {formatToMoney(totalNumber)}&nbsp;&#8381;
        </div>
    );
};

export const DashboardPieChart = ({ data }) => {
    const dispatch = useDispatch();
    const dataPieChart = [
        { title: 'preprocessing', value: getItemTotal(data, 'preprocessing'), color: '#7DA2FF' },
        { title: 'in_work', value: getItemTotal(data, 'in_work'), color: '#67E1B5' },
        { title: 'no_contact', value: getItemTotal(data, 'no_contact'), color: '#FFCF24' },
        { title: 'cancelled', value: getItemTotal(data, 'cancelled'), color: '#FF4F4F' },
    ];

    const onClearClick = () => {
        dispatch(setFilter(null));
    };

    return (
        <div className={`${styles.block} ${styles.chart}`} onClick={onClearClick}>
            <div className={styles.pie}>
                <PieChart
                    key={data.total}
                    data={dataPieChart}
                    lineWidth={16}
                    animate={true}
                    animationDuration={500}
                />
                <div className={styles.count}>{data.total}</div>
            </div>

            {getPieChartLabel(data.totalMoney)}
        </div>
    );
};
