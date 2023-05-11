import React, { useState } from 'react';
import styled from 'styled-components';
import Popup from 'reactjs-popup';
import styles from './buttons.module.scss';
import NewInvoicePopup from '../NewInvoicePopup/NewInvoicePopup';

const LongPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
    &-overlay {
        position: fixed !important;
        height: 100vh !important;
        overflow-y: auto;
    }
`;

const CreateInvoiceButton = ({ updateData }) => {
    const [requestPopup, setRequestPopup] = useState({ open: false, route: null });

    return (
        <>
            <LongPopup
                open={requestPopup.open}
                onClose={() => setRequestPopup({ open: false, route: null })}
                modal
                closeOnDocumentClick
            >
                {(close) => (
                    <NewInvoicePopup
                        close={close}
                        route={requestPopup.route}
                        onSuccess={() => {
                            updateData();
                            close();
                        }}
                    />
                )}
            </LongPopup>
            <div
                onClick={() => {
                    setRequestPopup({ open: true, route: null });
                }}
                className={styles.buttonsContainerItem}
            >
                <img alt='icon' src='/add_icon.svg' className={styles.buttonsContainerIcon1} />
                <div>Пополнить баланс</div>
            </div>
        </>
    );
};

export default CreateInvoiceButton;
