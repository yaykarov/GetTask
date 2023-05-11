import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { setFilter } from '../../actions';
import styles from './Dashboard.module.scss';
import { DashboardGroup } from './DashboardGroup';

const getPercent = (count, total) => {
    return total ? Math.round((count / total) * 100) : 0;
};
const groupNames = {
    preprocessing: 'В обработке',
    in_work: 'Выполняется',
    no_contact: 'Нет контакта',
    cancelled: 'Отменены',
};

const getFilterStatus = (store) => store.requests.filterStatus;

export const DashboardItem = ({ dashBoardTotal, itemTotal, title, groups }) => {
    const filterStatus = useSelector(getFilterStatus);
    const dispatch = useDispatch();
    const dashboardGroupsEl = groups.map(({ title, total }) => {
        return <DashboardGroup key={title} total={total} title={title} itemTotal={itemTotal} />;
    });

    const onGroupSelect = () => {
        const currentGroup = title === filterStatus ? null : title;

        dispatch(setFilter(currentGroup));
    };

    return (
        <div
            className={`${styles.block} ${styles[title]} ${
                filterStatus === title ? styles.selected : ''
            } ${filterStatus ? [styles.noSelected] : ''}`}
            onClick={onGroupSelect}
        >
            <div className={styles.title}>
                {groupNames[title]}
                <span className={styles.blockTotal}>{itemTotal}</span>
            </div>

            <div className={`${styles.row} ${styles.mb3}`}>
                <div className={styles.loader}>
                    <div
                        className={styles.persent}
                        style={{ width: `${getPercent(itemTotal, dashBoardTotal)}%` }}
                    ></div>
                </div>
            </div>

            {dashboardGroupsEl}
        </div>
    );
};
