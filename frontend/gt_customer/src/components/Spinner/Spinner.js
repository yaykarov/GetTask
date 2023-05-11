import React from 'react';
import styles from './Spinner.module.scss';

export default function Spinner() {
    return (
        <div className={styles.spinner}>
            <div className={styles.loadingiospinner}>
                <div className={styles.ldio2ackyrwzevd}>
                    <div></div>
                    <div></div>
                    <div></div>
                </div>
            </div>
        </div>
    );
}
