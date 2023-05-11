import React from 'react';
import styles from './PopupModal.module.scss';

function PopupModal({ close, title, children, onOk, onCancel }) {
    return (
        <div className={styles.popup}>
            <div onClick={close} className={styles.popupClose}>
                <img alt='icon' src='/close_icon.svg' />
            </div>
            <div className={styles.popupTitle}>{title}</div>
            <div className={styles.popupContent}>{children}</div>
            <div className={styles.buttonsWrapper}>
                <div
                    onClick={() => {
                        onOk();
                        close();
                    }}
                    className={styles.button}
                >
                    Подтвердить
                </div>
                <div
                    onClick={() => {
                        onCancel();
                        close();
                    }}
                    onClick={close}
                    className={styles.button}
                >
                    Отмена
                </div>
            </div>
        </div>
    );
}

export default PopupModal;
