import React, { useState, useEffect } from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import Popup from 'reactjs-popup';
import styled from 'styled-components';
import { withRouter } from 'react-router-dom';
import axios from 'axios';
import { AddressSuggestions, BankSuggestions } from 'react-dadata';
import { updateOrganization, accountInfo, fetchOrganization } from '../../../actions';
import styles from './InfoPage.module.scss';
import ContactsTable from '../../ContactsTable/ContactsTable';
import PopupInfo from '../../PopupInfo/PopupInfo';
import CustomSelect from '../../CustomSelect/CustomSelect';
import { BACKEND_URL, DADATA_API_KEY } from '../../../utils/constants';
import UploadFilePopup from '../../UploadFilePopup/UploadFilePopup';
import Editable from '../../Editable/Editable';
import { getToken } from '../../../utils';
import Wrapper from '../../Wrapper/Wrapper';
import Dashboard from '../../Dashboard/Dashboard';

const ShortPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

const initialState = {
    isLegalEntity: -1,
    entityType: '',
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

const mapperState = (state) => {
    return {
        ...state,
        fullName: state.full_name,
        ceo: state.ceo,
        email: state.email,
        phone: state.phone,
        isLegalEntity: state.is_legal_entity,
        legalAddress: state.legal_address,
        mailAddress: state.mail_address,
        taxNumber: state.tax_number,
        reasonCode: state.reason_code,
        bankName: state.bank_name,
        bankIdentificationCode: state.bank_identification_code,
        bankAccount: state.bank_account,
        correspondentAccount: state.correspondent_account,
    };
};

function Unfilled({
    updateOrganization,
    accountInfo,
    user,
    history,
    location,
    registrationStatus,
    fetchOrganization,
}) {
    const [focused, setFocused] = useState('fullName');
    const [infoPopup, setInfoPopup] = useState({ open: false, content: '' });
    const [state, setState] = useState(initialState);
    const [requiredStatusList, setRequiredStatusList] = useState(new Map());
    const {
        entityType,
        fullName,
        ceo,
        email,
        phone,
        isLegalEntity,
        legalAddress,
        mailAddress,
        taxNumber,
        reasonCode,
        bankName,
        bankIdentificationCode,
        bankAccount,
        correspondentAccount,
    } = state;
    const isFocused = (i) => focused === i;

    const isRequiredStatus = (name) => {
        return requiredStatusList.get(name);
    };

    const updateRequiredStatus = (state, notNegative) => {
        for (const [name, value] of Object.entries(state)) {
            if (!value && !notNegative) {
                setRequiredStatusList((prev) => prev.set(name, true));
            } else if (value) {
                setRequiredStatusList((prev) => prev.set(name, false));
            }
        }
    };

    const { from } = (location && location.state) || { from: '/' };

    // TODO: Переписать на функцию downloadFile
    function download() {
        axios({
            method: 'get',
            url: `${BACKEND_URL}gt/customer/get_contract`,
            headers: {
                Authorization: `Bearer ${getToken()}`,
            },
            responseType: 'blob',
        })
            .then((response) => {
                const url = window.URL.createObjectURL(new Blob([response.data]));
                const link = document.createElement('a');

                link.href = url;
                link.setAttribute('download', 'gettask_contract.pdf');
                document.body.appendChild(link);
                link.click();
            })
            .catch(async (error) => {
                const currentError = JSON.parse(await error.response.data.text());
                updateRequiredStatus(state);
                setInfoPopup({
                    open: true,
                    content: currentError.detail || error.message,
                    title: 'Ошибка',
                });
            });
    }

    function Warning() {
        switch (registrationStatus) {
            case 'info_required':
                return (
                    <div className={styles.warning}>
                        <svg style={{ fill: '#FD1B1B' }}>
                            <use xlinkHref='/warning_icon.svg#root' />
                        </svg>
                        Прежде чем начать пользоваться системой заполните данные о вашей организации
                        и добавьте контактное лицо.
                    </div>
                );
            case 'scan_required':
                return (
                    <div className={styles.warning}>
                        <svg style={{ fill: '#FD1B1B' }}>
                            <use xlinkHref='/warning_icon.svg#root' />
                        </svg>
                        Скачайте договор и приложите скан.
                    </div>
                );
            case 'confirmation_required':
                return (
                    <div className={styles.warning} style={{ color: '#00e640' }}>
                        <svg style={{ fill: '#00e640' }}>
                            <use xlinkHref='/warning_icon.svg#root' />
                        </svg>
                        Скан успешно прикреплен и ожидает проверки.
                    </div>
                );
            default:
                return null;
        }
    }

    function edit(updated) {
        const o = {
            ...state,
            ...updated,
        };
        updateRequiredStatus(updated, true);
        if (Object.keys(o).every((k) => o[k]) && user.info.registrationStatus === 'scan_required') {
            setInfoPopup({
                open: true,
                content:
                    'Данные сохранены.\n' +
                    '\n' +
                    'Для начала работы скачайте заполненный договор, распечатайте и подпишите.\n' +
                    'Подписанный скан загрузите нам, чтобы мы могли активировать создание заявок.',
                title: 'Результат',
            });
        }
        return new Promise((resolve, reject) => {
            submitForm(resolve, reject, o);
        });
    }

    function submitForm(resolve, reject, updated = {}) {
        updateOrganization({
            full_name: updated.fullName,
            ceo: updated.ceo,
            email: updated.email,
            phone: updated.phone,
            is_legal_entity: updated.isLegalEntity,
            legal_address: updated.legalAddress,
            mail_address: updated.mailAddress,
            tax_number: updated.taxNumber,
            reason_code: updated.reasonCode,
            bank_name: updated.bankName,
            bank_identification_code: updated.bankIdentificationCode,
            bank_account: updated.bankAccount,
            correspondent_account: updated.correspondentAccount,
        })
            .then(() => {
                resolve && resolve();

                accountInfo();
                fetchOrganization_w();
            })
            .catch((err) => {
                reject && reject();

                setInfoPopup({
                    open: true,
                    content:
                        err.error.response.data.message ||
                        `${err.error.response.status} ${err.error.response.statusText}`,
                    title: 'Ошибка',
                });
            });
    }

    function fetchOrganization_w() {
        fetchOrganization().then(({ payload }) => {
            const currentState = mapperState(payload.data);

            setState(currentState);
        });
    }

    useEffect(() => {
        if (from === '/finish_registration') {
            history.push({ state: { from: '/' } });
            setInfoPopup({
                open: true,
                title: 'Информация',
                content: 'Регистрация успешно завершена',
            });
        }

        fetchOrganization_w();
    }, []);

    useEffect(() => {
        if (typeof isLegalEntity === 'boolean') {
            if (isLegalEntity) {
                setState((prev) => ({ ...prev, entityType: 'ООО' }));
            } else {
                setState((prev) => ({ ...prev, entityType: 'ИП' }));
            }
        } else {
            setState((prev) => ({ ...prev, entityType: '' }));
        }
    }, [isLegalEntity]);

    return (
        <Wrapper title='Инфо'>
            <ShortPopup
                modal
                closeOnDocumentClick
                open={infoPopup.open}
                onClose={() => setInfoPopup({ ...infoPopup, open: false })}
            >
                {(close) => (
                    <PopupInfo title={infoPopup.title} close={close}>
                        {infoPopup.content}
                    </PopupInfo>
                )}
            </ShortPopup>

            <Warning />
            <div className={styles.container}>
                <div>
                    <div className={styles.smallTitle}>Данные об организации</div>
                    <div className={styles.line5}>
                        <div className={styles.lineContainer}>
                            <div>ООО/ИП</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('entityType')}
                                    inputComponent={(value, setValue, handleSubmit) => (
                                        <CustomSelect
                                            options={['Выбрать', 'ООО', 'ИП']}
                                            value={value}
                                            onChange={(val) => {
                                                setValue(val);
                                                handleSubmit(val);
                                            }}
                                            defaultOption={'Выбрать'}
                                            className={styles.mini}
                                        />
                                    )}
                                    text={entityType}
                                    submitFunction={(text) =>
                                        edit({ isLegalEntity: text === 'ООО' })
                                    }
                                    notOpenedClassName={styles.notOpened}
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Наименование</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('fullName')}
                                    focused={isFocused('fullName')}
                                    text={fullName}
                                    onEnterSuccess={() => setFocused('ceo')}
                                    submitFunction={(text) => edit({ fullName: text })}
                                    notOpenedClassName={styles.notOpened}
                                    sendRequestOnBlur
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Генеральный директор</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('ceo')}
                                    focused={isFocused('ceo')}
                                    onEnterSuccess={() => setFocused('email')}
                                    text={ceo}
                                    submitFunction={(text) => edit({ ceo: text })}
                                    notOpenedClassName={styles.notOpened}
                                    sendRequestOnBlur
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Электронная почта</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('email')}
                                    focused={isFocused('email')}
                                    onEnterSuccess={() => setFocused('phone')}
                                    text={email}
                                    submitFunction={(text) => edit({ email: text })}
                                    notOpenedClassName={styles.notOpened}
                                    sendRequestOnBlur
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Телефон</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('phone')}
                                    focused={isFocused('phone')}
                                    onEnterSuccess={() => setFocused('taxNumber')}
                                    text={phone}
                                    submitFunction={(text) => edit({ phone: text })}
                                    notOpenedClassName={styles.notOpened}
                                    sendRequestOnBlur
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>ИНН</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('taxNumber')}
                                    focused={isFocused('taxNumber')}
                                    onEnterSuccess={() =>
                                        setFocused(
                                            entityType !== 'ИП' ? 'reasonCode' : 'bankAccount'
                                        )
                                    }
                                    text={taxNumber}
                                    submitFunction={(text) => edit({ taxNumber: text })}
                                    maxLength={entityType === 'ООО' ? 10 : 12}
                                    notOpenedClassName={styles.notOpened}
                                    onlyNumber
                                    sendRequestOnBlur
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        {entityType !== 'ИП' ? (
                            <React.Fragment>
                                <div className={styles.lineContainer}>
                                    <div>КПП</div>
                                    <div>
                                        <Editable
                                            isRequiredStatus={isRequiredStatus('reasonCode')}
                                            focused={isFocused('reasonCode')}
                                            onEnterSuccess={() => setFocused('bankAccount')}
                                            text={reasonCode}
                                            submitFunction={(text) => edit({ reasonCode: text })}
                                            maxLength={entityType === 'ООО' ? 9 : null}
                                            notOpenedClassName={styles.notOpened}
                                            onlyNumber
                                            sendRequestOnBlur
                                        />
                                    </div>
                                </div>
                                <div className={styles.underline} />
                            </React.Fragment>
                        ) : null}
                        <div className={styles.lineContainer}>
                            <div>Р/С</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('bankAccount')}
                                    focused={isFocused('bankAccount')}
                                    text={bankAccount}
                                    submitFunction={(text) => edit({ bankAccount: text })}
                                    maxLength={20}
                                    notOpenedClassName={styles.notOpened}
                                    onlyNumber
                                    sendRequestOnBlur
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Банк</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('bankName')}
                                    inputComponent={(value, setValue, handleSubmit) => (
                                        <BankSuggestions
                                            inputProps={{
                                                autoFocus: true,
                                            }}
                                            defaultQuery={bankName}
                                            token={DADATA_API_KEY}
                                            value={value}
                                            onChange={(addr) => {
                                                setValue(addr);
                                                handleSubmit({
                                                    bankName: addr.value,
                                                    bankIdentificationCode: addr.data.bic,
                                                    correspondentAccount:
                                                        addr.data.correspondent_account,
                                                });
                                            }}
                                            containerClassName={styles.addressSuggestions}
                                        />
                                    )}
                                    text={bankName}
                                    submitFunction={(text) => edit(text)}
                                    notOpenedClassName={styles.notOpened}
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>К/С</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('correspondentAccount')}
                                    focused={isFocused('correspondentAccount')}
                                    onEnterSuccess={() => setFocused('bankIdentificationCode')}
                                    text={correspondentAccount}
                                    submitFunction={(text) => edit({ correspondentAccount: text })}
                                    maxLength={20}
                                    notOpenedClassName={styles.notOpened}
                                    onlyNumber
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>БИК</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('bankIdentificationCode')}
                                    focused={isFocused('bankIdentificationCode')}
                                    text={bankIdentificationCode}
                                    submitFunction={(text) =>
                                        edit({ bankIdentificationCode: text })
                                    }
                                    maxLength={9}
                                    notOpenedClassName={styles.notOpened}
                                    onlyNumber
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Юр. адрес</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('legalAddress')}
                                    inputComponent={(value, setValue, handleSubmit) => (
                                        <AddressSuggestions
                                            inputProps={{
                                                autoFocus: true,
                                            }}
                                            defaultQuery={legalAddress}
                                            token={DADATA_API_KEY}
                                            value={value}
                                            onChange={(addr) => {
                                                setValue(addr);
                                                mailAddress
                                                    ? handleSubmit({ legalAddress: addr.value })
                                                    : handleSubmit({
                                                          legalAddress: addr.value,
                                                          mailAddress: addr.value,
                                                      });
                                            }}
                                            containerClassName={styles.addressSuggestions}
                                        />
                                    )}
                                    text={legalAddress}
                                    submitFunction={(text) => edit(text)}
                                    notOpenedClassName={styles.notOpened}
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                        <div className={styles.lineContainer}>
                            <div>Почтовый адрес</div>
                            <div>
                                <Editable
                                    isRequiredStatus={isRequiredStatus('mailAddress')}
                                    inputComponent={(value, setValue, handleSubmit) => (
                                        <AddressSuggestions
                                            inputProps={{
                                                autoFocus: true,
                                            }}
                                            defaultQuery={mailAddress}
                                            token={DADATA_API_KEY}
                                            value={value}
                                            onChange={(addr) => {
                                                setValue(addr);
                                                handleSubmit(addr.value);
                                            }}
                                            containerClassName={styles.addressSuggestions}
                                        />
                                    )}
                                    text={mailAddress}
                                    submitFunction={(text) => edit({ mailAddress: text })}
                                    notOpenedClassName={styles.notOpened}
                                />
                            </div>
                        </div>
                        <div className={styles.underline} />
                    </div>
                </div>
                <ContactsTable />
            </div>
            <div className={styles.line3}>
                <div className={styles.buttonsContainer}>
                    <div onClick={download} className={styles.buttonsContainerItem}>
                        <img
                            alt='icon'
                            src='/save_icon.svg'
                            className={styles.buttonsContainerIcon3}
                        />
                        <div>Скачать договор</div>
                    </div>
                    <ShortPopup
                        trigger={
                            <div className={styles.buttonsContainerItem}>
                                <img
                                    alt='icon'
                                    src='/import_icon.svg'
                                    className={styles.buttonsContainerIcon2}
                                />
                                <div>Загрузить скан договора</div>
                            </div>
                        }
                        modal
                        closeOnDocumentClick
                    >
                        {(close) => (
                            <UploadFilePopup
                                close={close}
                                name={'scans'}
                                endpoint={'/gt/customer/upload_contract_scans'}
                                onSuccess={() =>
                                    setInfoPopup({
                                        open: true,
                                        content:
                                            'Спасибо, что прикрепили скан!\n' +
                                            'В ближайшее время с вами свяжется менеджер.',
                                        title: 'Результат',
                                    })
                                }
                                onFailure={(err) =>
                                    setInfoPopup({
                                        open: true,
                                        content: err,
                                        title: 'Ошибка',
                                    })
                                }
                            />
                        )}
                    </ShortPopup>
                </div>
            </div>
        </Wrapper>
    );
}

const mapStateToProps = (state) => ({
    user: state.user,
    registrationStatus: state.user.info.registrationStatus,
});

const mapDispatchToProps = (dispatch) =>
    bindActionCreators({ updateOrganization, accountInfo, fetchOrganization }, dispatch);

export default connect(mapStateToProps, mapDispatchToProps)(withRouter(Unfilled));
