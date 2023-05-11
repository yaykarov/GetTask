import React from 'react';
import styles from './buttons.module.scss';
import { BACKEND_URL } from '../../utils/constants';

const DownloadExcelButton = () => {
    return (
        <div
            onClick={() =>
                window.open(`${BACKEND_URL}static/files/delivery/delivery_template.xlsx?v=5`)
            }
            className={styles.buttonsContainerItem}
        >
            <img alt='icon' src='/save_xls_icon.svg' className={styles.buttonsContainerIcon3} />
            <div></div>
        </div>
    );
};

export default DownloadExcelButton;
