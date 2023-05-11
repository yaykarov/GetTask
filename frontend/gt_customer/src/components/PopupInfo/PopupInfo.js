import React from 'react';
import styles from './PopupInfo.module.scss';

function PopupInfo({ close, title, children, buttons = null }) {
    const renderButtons = buttons ? (
        buttons.map(({ onClick, text }, key) => (
            <div onClick={onClick} className={styles.button} key={key}>
                {text}
            </div>
        ))
    ) : (
        <div onClick={close} className={styles.button}>
            Ок
        </div>
    );

    return (
        <div className={styles.popup}>
            <div onClick={close} className={styles.popupClose}>
                <img alt='icon' src='/close_icon.svg' />
            </div>
            <div className={styles.popupTitle}>{title}</div>
            <div className={styles.popupContent}>{children}</div>
            <div className={styles.buttons}>{renderButtons}</div>
        </div>
    );
}

export default PopupInfo;
