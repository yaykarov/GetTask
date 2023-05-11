import React from 'react';
import styles from './Wrapper.module.scss';
import Header from '../Header/Header';

const Wrapper = (props) => {
    const { title, children } = props;
    return (
        <div className={styles.wrapper}>
            <Header title={title} />
            {children}
        </div>
    );
};

export default Wrapper;
