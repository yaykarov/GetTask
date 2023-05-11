import React, { memo } from 'react';
import { connect } from 'react-redux';
import styles from './UserMenu.module.scss';
import { logout } from '../../actions';
import { removeToken } from '../../utils';
import { userInfoSelector } from '../../utils/reselect';

function UserMenu({ userInfo, logout }) {
    const { name, balance } = userInfo;
    if (balance === null) return null;

    return (
        <div className={styles.user}>
            <div className={styles.usernameWrapper}>
                <div className={styles.username}>{name}</div>
                <img alt='icon' src='/arrow_down_icon.svg' />
            </div>
            <div className={styles.balance + ' ' + (balance.highlight ? styles.red : '')}>
                {balance.text}&nbsp;&#8381;
            </div>
            <div className={styles.underline} />
            <div
                onClick={() => {
                    removeToken();
                    logout();
                }}
                className={styles.logout}
            >
                <img alt='icon' src='/logout_icon.svg' />
                Выйти
            </div>
        </div>
    );
}

const mapStateToProps = (state) => ({
    userInfo: userInfoSelector(state),
});

const mapDispatchToProps = (dispatch) => ({
    logout: () => dispatch(logout()),
});

export default connect(mapStateToProps, mapDispatchToProps)(memo(UserMenu));
