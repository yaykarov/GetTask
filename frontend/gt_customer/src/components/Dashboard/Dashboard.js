import React, { memo } from 'react';
import styles from './Dashboard.module.scss';
import { DashboardItem } from './DashboardItem';
import { DashboardPieChart } from './DashboardPieChart';

const Dashboard = ({ data }) => {
    const dashboardItemsEl = [...data.items.values()].map(({ groups, title, total }) => {
        return (
            <DashboardItem
                key={title}
                groups={[...groups.values()]}
                dashBoardTotal={data.total}
                itemTotal={total}
                title={title}
            />
        );
    });

    return (
        <div className={styles.dashboard}>
            <DashboardPieChart data={data} />

            {dashboardItemsEl}
        </div>
    );
};

export default memo(Dashboard);
