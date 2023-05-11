import React from 'react';
import styles from './ButtonsContainer.module.scss';

const ButtonsContainer = ({ left, right }) => {
    return (
        <div className={styles.buttonsContainer}>
            <div className={styles.buttonsContainerLeft}>{left}</div>

            <div className={styles.buttonsContainerRight}>{right}</div>
        </div>
    );
};

export default ButtonsContainer;
