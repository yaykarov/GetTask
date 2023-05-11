import React from 'react';
import styles from './Header.module.scss';
import UserMenu from '../UserMenu/UserMenu';

const Header = ({ title }) => {
    return (
        <div className={styles.line1}>
            <div className={styles.title}>{title}</div>
            <UserMenu />
        </div>
    );
};

export default Header;
