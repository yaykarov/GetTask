import React, { useState } from 'react';
import styles from './buttons.module.scss';
import UploadFilePopup from '../UploadFilePopup/UploadFilePopup';
import PopupInfo from '../PopupInfo/PopupInfo';
import styled from 'styled-components';
import Popup from 'reactjs-popup';
const ShortPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

const ImportsButton = ({ allow_requests_creation, updateData }) => {
    const [infoPopup, setInfoPopup] = useState({ open: false, content: '' });
    return (
        <>
            {allow_requests_creation ? (
                <ShortPopup
                    trigger={
                        <div className={styles.buttonsContainerItem}>
                            <img
                                alt='icon'
                                src='/import_xls_icon.svg'
                                className={styles.buttonsContainerIcon2}
                            />
                            <div></div>
                        </div>
                    }
                    modal
                    closeOnDocumentClick
                >
                    {(close) => (
                        <UploadFilePopup
                            close={close}
                            name={'requests'}
                            endpoint={'/gt/customer/v2/delivery/request/import/'}
                            onSuccess={() => {
                                updateData();
                                setInfoPopup({
                                    open: true,
                                    title: 'Файл импортируется',
                                    content:
                                        'Статус импорта и отчет доступны в разделе "История импорта"',
                                });
                            }}
                            onFailure={(err) => {
                                setInfoPopup({
                                    open: true,
                                    title: 'Ошибка',
                                    content: err,
                                });
                            }}
                        />
                    )}
                </ShortPopup>
            ) : (
                <div
                    onClick={() =>
                        setInfoPopup({
                            open: true,
                            content: 'Пополните баланс для подачи заявок',
                            title: 'Недостаточно средств',
                        })
                    }
                    className={styles.buttonsContainerItem}
                >
                    <img
                        alt='icon'
                        src='/import_xls_icon.svg'
                        className={styles.buttonsContainerIcon2}
                    />
                    <div></div>
                </div>
            )}
            <ShortPopup
                modal
                closeOnDocumentClick
                open={infoPopup.open}
                onClose={() => setInfoPopup({ ...infoPopup, open: false })}
            >
                {(close) => (
                    <PopupInfo title={infoPopup.title} close={close}>
                        <div dangerouslySetInnerHTML={{ __html: infoPopup.content }}></div>
                    </PopupInfo>
                )}
            </ShortPopup>
        </>
    );
};

export default ImportsButton;
