import styles from './buttons.module.scss';
import React from 'react';
import styled from 'styled-components';
import Popup from 'reactjs-popup';

const LongPopup = styled(Popup)`
    &-content {
        margin: 4% auto auto !important;
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
    &-overlay {
        position: absolute !important;
        height: 1080px !important;
    }
`;

const ViewButton = ({ columns, setColumns }) => {
    return (
        <LongPopup
            trigger={
                <div className={styles.view}>
                    <img alt='icon' src='/view_icon.svg' />
                    <div>Вид</div>
                </div>
            }
            modal
            closeOnDocumentClick
        >
            {(close) => (
                <div className={styles.viewPopup}>
                    <div onClick={close} className={styles.viewPopupClose}>
                        <img alt='icon' src='/close_icon.svg' />
                    </div>
                    <div className={styles.viewPopupTitle}>Настроить столбцы</div>
                    {Object.keys(columns).map((c) => (
                        <div key={c}>
                            <label className={styles.checkboxContainer}>
                                <input
                                    type='checkbox'
                                    checked={columns[c].isVisible}
                                    onChange={() =>
                                        setColumns({
                                            ...columns,
                                            [c]: {
                                                ...columns[c],
                                                isVisible: !columns[c].isVisible,
                                            },
                                        })
                                    }
                                />
                                <div className={styles.checkboxLabel}>{columns[c].text}</div>
                                <span className={styles.checkmark} />
                            </label>
                        </div>
                    ))}
                    <div onClick={close} className={styles.button}>
                        Сохранить
                    </div>
                </div>
            )}
        </LongPopup>
    );
};

export default ViewButton;
