import React, { useState, useEffect } from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import { withRouter } from 'react-router-dom';
import Popup from 'reactjs-popup';
import styled from 'styled-components';
import styles from './InfoPage.module.scss';
import { fetchOrganization } from '../../../actions';
import ContactsTable from '../../ContactsTable/ContactsTable';
import PopupInfo from '../../PopupInfo/PopupInfo';
import Wrapper from '../../Wrapper/Wrapper';

const StyledPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

const initialState = {
    isLegalEntity: -1,
    fullName: '',
    ceo: '',
    email: '',
    phone: '',
    legalAddress: '',
    mailAddress: '',
    taxNumber: '',
    reasonCode: '',
    bankName: '',
    bankIdentificationCode: '',
    bankAccount: '',
    correspondentAccount: '',
};

function Filled({ fetchOrganization, user, location, history }) {
    const [
        {
            isLegalEntity,
            fullName,
            ceo,
            email,
            phone,
            legalAddress,
            mailAddress,
            taxNumber,
            reasonCode,
            bankName,
            bankIdentificationCode,
            bankAccount,
            correspondentAccount,
        },
        setState,
    ] = useState(initialState);
    const [popup, setPopup] = useState({ open: false, content: '' });
    const { from } = (location && location.state) || { from: '/' };

    useEffect(() => {
        if (from === '/finish_registration') {
            history.push({ state: { from: '/' } });
            setPopup({
                open: true,
                content: 'Регистрация успешно завершена',
            });
        }

        fetchOrganization().then((res) => {
            if (res.payload.data) {
                setState({
                    isLegalEntity: res.payload.data.is_legal_entity,
                    fullName: res.payload.data.full_name,
                    ceo: res.payload.data.ceo,
                    email: res.payload.data.email,
                    phone: res.payload.data.phone,
                    legalAddress: res.payload.data.legal_address,
                    mailAddress: res.payload.data.mail_address,
                    taxNumber: res.payload.data.tax_number,
                    reasonCode: res.payload.data.reason_code,
                    bankName: res.payload.data.bank_name,
                    bankIdentificationCode: res.payload.data.bank_identification_code,
                    bankAccount: res.payload.data.bank_account,
                    correspondentAccount: res.payload.data.correspondent_account,
                });
            }
        });
    }, []);

    return (
        <Wrapper title='Инфо'>
            <StyledPopup
                modal
                closeOnDocumentClick
                open={popup.open}
                onClose={() => setPopup({ ...popup, open: false })}
            >
                {(close) => (
                    <PopupInfo title={'Информация'} close={close}>
                        {popup.content}
                    </PopupInfo>
                )}
            </StyledPopup>
            <div className={styles.container}>
                <div>
                    <div className={styles.smallTitle}>Данные об организации</div>
                    <div className={styles.line5}>
                        <div className={styles.lineContainer}>
                            <div>ООО/ИП</div>
                            <div>{`${isLegalEntity ? 'ООО' : 'ИП'} "${fullName}"`}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Наименование</div>
                            <div>{fullName}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Генеральный директор</div>
                            <div>{ceo}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Электронная почта</div>
                            <div>{email}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Телефон</div>
                            <div>{phone}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>ИНН</div>
                            <div>{taxNumber}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>КПП</div>
                            <div>{reasonCode}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Р/С</div>
                            <div>{bankAccount}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Банк</div>
                            <div>{bankName}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>К/С</div>
                            <div>{correspondentAccount}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>БИК</div>
                            <div>{bankIdentificationCode}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Юр. адрес</div>
                            <div>{legalAddress}</div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Почтовый адрес</div>
                            <div>{mailAddress}</div>
                        </div>
                        <div className={styles.underline} />
                    </div>
                </div>
                <ContactsTable />
            </div>
        </Wrapper>
    );
}

const mapStateToProps = (state) => ({
    user: state.user,
});

const mapDispatchToProps = (dispatch) => bindActionCreators({ fetchOrganization }, dispatch);

export default connect(mapStateToProps, mapDispatchToProps)(withRouter(Filled));
