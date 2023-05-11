import React from 'react';
import { Link } from 'react-router-dom';
import styles from './Sidebar.module.scss';
import { connect } from 'react-redux';

const reportsCallback = ({ info }) =>
    !!info.new_reports_count && <div className={styles.reportsCount}>{info.new_reports_count}</div>;

const LEFT_MENU = [
    { id: 'requests', title: 'Заявки', icon: '/request_icon.svg', info_required: true },
    {
        id: 'requests_on_map',
        title: 'Заявки на карте',
        icon: '/requests_on_map_icon.svg',
        info_required: true,
    },
    {
        id: 'imports',
        title: 'История импорта',
        icon: '/import_page_icon.svg',
        info_required: true,
        callback: (user) =>
            user.info.importsUpdated ? (
                <img alt='icon' src='/info_fill_icon.svg' className={styles.icon} />
            ) : null,
    },
    {
        id: 'reports',
        title: 'Взаиморасчеты',
        icon: '/reports_icon.svg',
        info_required: true,
        callback: reportsCallback,
    },
    { id: 'balance', title: 'Баланс', icon: '/balance_icon.svg', info_required: true },
    { id: 'info', title: 'Инфо', icon: '/info_icon.svg', info_required: false },
];

function Sidebar({ user, menu }) {
    return (
        <div className={styles.wrapper}>
            <div className={styles.logo} />
            <div className={styles.menu}>
                {LEFT_MENU.map((menuItem) => {
                    const activeClass = menuItem.id === menu ? ` ${styles.active}` : '';
                    {
                        return (
                            <Link
                                key={menuItem.id}
                                to={'/' + menuItem.id}
                                className={styles.menuItem + activeClass}
                            >
                                <img alt='icon' src={menuItem.icon} className={styles.icon} />
                                <div className={styles.text}>
                                    {menuItem.title} {menuItem.callback && menuItem.callback(user)}
                                </div>
                            </Link>
                        );
                    }
                })}
            </div>
            <div className={styles.paymentInfo}>
                <div>Не оплачено</div>
                <div>
                    <b>{user.info.unpaid_requests_total}</b> заявок
                </div>
                <div>
                    на сумму{' '}
                    <div className={styles.price}>{user.info.unpaid_requests_sum}&nbsp;&#8381;</div>
                </div>
                <br />
                <div>Из них:</div>
                <div>
                    - в оплате <b>{user.info.unpaid_requests_in_payment}</b>
                </div>
                <div>
                    - не согласованы <b>{user.info.unpaid_requests_active}</b>
                </div>
            </div>
            <div className={styles.socials}>
                <img alt='icon' src='/facebook_icon.svg' className={styles.icon} />
                <img alt='icon' src='/linkedin_icon.svg' className={styles.icon} />
            </div>
            <div className={styles.copyright}>GetTask © 2022</div>
        </div>
    );
}

const mapStateToProps = (state) => ({
    user: state.user,
});

export default connect(mapStateToProps)(Sidebar);
