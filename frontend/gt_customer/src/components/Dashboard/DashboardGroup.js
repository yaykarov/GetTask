import React from 'react';

import styles from './Dashboard.module.scss';

const GROUP_NAMES = {
    autotarification_attempt: { title: 'Тарифицируется', class: 'status-autotarification_attempt' },
    new: { title: 'Новая', class: 'status-new' },
    timepoint_confirmed: { title: 'Поиск исполнителя', class: 'status-timepoint_confirmed' },
    partly_confirmed: { title: 'Назначен', class: 'status-partly_confirmed' },

    partly_arrived: { title: 'Принята исполнителем', class: 'status-partly_arrived' },
    partly_arrival_submitted: { title: 'Принята исполнителем', class: 'status-partly_arrived' },
    partly_photo_attached: { title: 'На месте', class: 'status-partly_photo_attached' },
    photo_attached: { title: 'Проверка табеля', class: 'status-photo_attached' },
    finished: { title: 'Выполнена', class: 'status-finished' },

    no_response: { title: 'Нет ответа', class: 'status-no_response' },
    driver_callback: { title: 'Перезвонит сам', class: 'status-driver_callback' },

    declined: { title: 'Не принята', class: 'status-declined' },
    cancelled: { title: 'Отмена', class: 'status-cancelled' },
    removed: { title: 'Удалена', class: 'status-removed' },
    failed: { title: 'Срыв заявки', class: 'status-failed' },
    cancelled_with_payment: { title: 'Отмена с оплатой', class: 'status-cancelled_with_payment' },
};

const getPercent = (count, total) => {
    return total ? Math.round((count / total) * 100) : 0;
};

export const DashboardGroup = ({ title, total, itemTotal }) => {
    const scrollBarWidthStyle = { width: `${getPercent(total, itemTotal)}%` };

    return (
        <div className={`${styles.element} ${styles[title]}`}>
            <div className={styles.label}>
                <span>{GROUP_NAMES[title].title}</span>
                <span>
                    <b>{total}</b>
                </span>
            </div>

            <div className={styles.loader}>
                <div className={styles.persent} style={scrollBarWidthStyle}></div>
            </div>
        </div>
    );
};
