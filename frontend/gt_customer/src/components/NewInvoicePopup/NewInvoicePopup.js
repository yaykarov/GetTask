import React, { useState, useEffect } from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import Popup from 'reactjs-popup';
import 'react-dadata/dist/react-dadata.css';
import styles from '../NewRequestPopup/NewRequestPopup.module.scss';
import styled from 'styled-components';
import PopupInfo from '../PopupInfo/PopupInfo';
import { getToken } from '../../utils';
import downloadFile from '../../utils/download';

const ShortPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

function NewInvoicePopup({ close, onSuccess }) {
    const [amount, setAmount] = useState('');

    const [infoPopup, setInfoPopup] = useState({ open: false, content: '' });
    const [isRequiredFilled, setIsRequiredFilled] = useState(false);

    useEffect(() => {
        setIsRequiredFilled(checkRequired());
    }, [amount]);

    function checkRequired() {
        let result = !!amount;
        return result;
    }

    function submitForm() {
        downloadFile({
            method: 'post',
            url: '/gt/customer/create_invoice',
            params: { amount },
            filename: 'invoice.pdf',
        })().then(() => onSuccess());
    }

    return (
        <div className={styles.viewPopup}>
            <div onClick={close} className={styles.viewPopupClose}>
                <img alt='icon' src='/close_icon.svg' />
            </div>
            <div className={styles.viewPopupTitle}>Пополнить баланс</div>
            <div className={styles.container}>
                <div className={`${styles.inputWrapper} ${styles.adjacent}`}>
                    <div required className={styles.label}>
                        Сумма
                    </div>
                    <input value={amount} onChange={(e) => setAmount(e.target.value)} />
                </div>
            </div>
            <div
                onClick={() => (isRequiredFilled ? submitForm() : null)}
                className={styles.button + ' ' + (!isRequiredFilled ? styles.disabled : '')}
            >
                Скачать счет
            </div>
            <ShortPopup
                modal
                closeOnDocumentClick
                open={infoPopup.open}
                onClose={() => {
                    if (infoPopup.title === 'Результат') {
                        close();
                    } else {
                        setInfoPopup({ ...infoPopup, open: false });
                    }
                }}
            >
                {(close) => (
                    <PopupInfo title={infoPopup.title} close={close}>
                        {infoPopup.content}
                    </PopupInfo>
                )}
            </ShortPopup>
        </div>
    );
}

const mapStateToProps = (state) => ({
    user: state.user,
});

const mapDispatchToProps = (dispatch) => bindActionCreators({}, dispatch);

export default connect(mapStateToProps, mapDispatchToProps)(NewInvoicePopup);
