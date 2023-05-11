import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import styles from './DailyConfirmation.module.scss';
import Popup from 'reactjs-popup';
import styled from 'styled-components';
import PopupInfo from '../../PopupInfo/PopupInfo';
import axios from 'axios';
import { BACKEND_URL } from '../../../utils/constants';

const StyledPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

const dailyConfirm = (uid, callback) => {
    const formData = new FormData();
    formData.append('uuid', uid);
    axios
        .post(`${BACKEND_URL}gt/customer/daily_reconciliation_confirm/`, formData)
        .then(({ data }) => callback(data))
        .catch((data) => console.log(data));
};

const getDailyInfo = (uid, callback) => {
    axios(`${BACKEND_URL}gt/customer/daily_reconciliation_details?uuid=${uid}`)
        .then(({ data }) => callback(data))
        .catch((data) => console.log(data));
};

const DailyConfirmationPage = React.memo(() => {
    const { uid } = useParams();

    const [popup, setPopup] = useState({ open: false, content: '', title: '' });
    const [dailyInfo, setDailyInfo] = useState({ status: 'gone' });
    const [dailyStatus, setDailyStatus] = useState({ status: 'gone' });

    const status = dailyStatus.status || dailyInfo.status;
    const { hours, amount, date } = dailyInfo;

    const dailyInfoIsGetted = Object.keys(dailyInfo).length > 0;

    const openPopup = () => {
        setPopup({
            open: true,
            content: (
                <span>
                    Вы подтверждаете оказание услуг в размере <b>{hours} часа</b> на сумму{' '}
                    <b>{amount} рублей</b>?
                </span>
            ),
            title: 'Подтверждение сверки',
        });
    };

    React.useEffect(() => {
        getDailyInfo(uid, (data) => {
            const { status } = data;

            setDailyInfo(data);
            setDailyStatus({ status });
        });
    }, []);

    const handleAccept = () => {
        dailyConfirm(uid, (data) => {
            setDailyStatus(data);

            setPopup({ open: false });
        });
    };

    const handleCancel = () => setPopup({ ...popup, open: false });
    const buttons = [
        { onClick: handleAccept, text: 'Подтверждаю' },
        { onClick: handleCancel, text: 'Отмена' },
    ];

    const { title, info, button } =
        status === 'new'
            ? {
                  title: `Сверка за ${date}`,
                  info: (
                      <p>
                          Оказано услуг в размере <b>{hours} часа</b> на сумму{' '}
                          <b>{amount} рублей</b>
                      </p>
                  ),
                  button: (
                      <div onClick={openPopup} className={styles.button}>
                          Подтвердить
                      </div>
                  ),
              }
            : status === 'confirmed'
            ? {
                  title: `Сверка за ${date}`,
                  info: <p>Данная сверка за {date} была ранее подтверждена.</p>,
              }
            : { title: 'Сверка не найдена', info: '' };

    return dailyInfoIsGetted ? (
        <div className={styles.wrapper}>
            <StyledPopup modal closeOnDocumentClick open={popup.open}>
                {(close) => (
                    <PopupInfo title={popup.title} close={close} buttons={buttons}>
                        {popup.content}
                    </PopupInfo>
                )}
            </StyledPopup>
            <img alt='logo' src='/logo.svg' className={styles.logo} />
            <div className={styles.container}>
                <div className={styles.title}>{title}</div>
                <div className={styles.info}>{info}</div>
                <div className={styles.line}>{button && button}</div>
            </div>
            <div className={styles.bottom}>
                <div className={styles.copyright}>GetTask © 2022</div>
            </div>
        </div>
    ) : null;
});

export default DailyConfirmationPage;
