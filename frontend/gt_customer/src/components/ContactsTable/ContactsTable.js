import React, { useState, useEffect } from 'react';
import { bindActionCreators } from 'redux';
import { connect } from 'react-redux';
import styles from './ContactsTable.module.scss';
import PopupInfo from '../PopupInfo/PopupInfo';
import { addContact, fetchContacts, updateContacts } from '../../actions';
import styled from 'styled-components';
import Popup from 'reactjs-popup';
import Editable from '../Editable/Editable';

const ShortPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

function ContactsTable({ contacts, addContact, fetchContacts, updateContacts }) {
    const [infoPopup, setInfoPopup] = useState({ open: false, content: '' });
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [phone, setPhone] = useState('');
    const [position, setPosition] = useState('');

    function updateContactsHandler() {
        fetchContacts();
    }

    useEffect(updateContactsHandler, []);

    function clearInputs() {
        setName('');
        setEmail('');
        setPhone('');
        setPosition('');
    }

    function submitForm(onClose) {
        addContact({
            full_name: name,
            email,
            phone,
            position,
        })
            .then(() => {
                setInfoPopup({
                    open: true,
                    content: 'Контакт успешно создан',
                    title: 'Результат',
                    onClose,
                });
                fetchContacts();
            })
            .catch((err) => {
                setInfoPopup({
                    open: true,
                    content:
                        err.error.response.data.message ||
                        `${err.error.response.status} ${err.error.response.statusText}`,
                    title: 'Ошибка',
                    onClose: null,
                });
            });
    }

    return (
        <div className={styles.contacts}>
            <div className={styles.line4}>
                <div className={styles.smallTitle}>Контактные лица</div>
                <ShortPopup
                    trigger={
                        <div className={styles.buttonsContainerItem}>
                            <img
                                alt='icon'
                                src='/add_icon.svg'
                                className={styles.buttonsContainerIcon1}
                            />
                            <div>Добавить контакт</div>
                        </div>
                    }
                    onClose={clearInputs}
                    modal
                    closeOnDocumentClick
                >
                    {(close) => (
                        <div className={styles.viewPopup}>
                            <div onClick={close} className={styles.viewPopupClose}>
                                <img alt='icon' src='/close_icon.svg' />
                            </div>
                            <div className={styles.viewPopupTitle}>Новый контакт</div>
                            <div className={styles.container1}>
                                <div className={styles.inputWrapper}>
                                    <div className={styles.label}>ФИО</div>
                                    <input value={name} onChange={(e) => setName(e.target.value)} />
                                </div>
                                <div className={styles.inputWrapper}>
                                    <div className={styles.label}>Почта</div>
                                    <input
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                    />
                                </div>
                                <div className={styles.inputWrapper}>
                                    <div className={styles.label}>Телефон</div>
                                    <input
                                        value={phone}
                                        onChange={(e) => setPhone(e.target.value)}
                                    />
                                </div>
                                <div className={styles.inputWrapper}>
                                    <div className={styles.label}>Должность</div>
                                    <input
                                        value={position}
                                        onChange={(e) => setPosition(e.target.value)}
                                    />
                                </div>
                            </div>
                            <div
                                onClick={() => {
                                    submitForm(close);
                                }}
                                className={styles.popupButton}
                            >
                                Создать новый контакт
                            </div>
                            <ShortPopup
                                modal
                                closeOnDocumentClick
                                open={infoPopup.open}
                                onClose={() => {
                                    setInfoPopup({ ...infoPopup, open: false });
                                    if (infoPopup.onClose) {
                                        infoPopup.onClose();
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
                    )}
                </ShortPopup>
            </div>
            <table className={styles.table}>
                <tbody>
                    <tr>
                        <td>
                            <div>ФИО</div>
                        </td>
                        <td>
                            <div>Почта</div>
                        </td>
                        <td>
                            <div>Телефон</div>
                        </td>
                        <td>
                            <div>Должность</div>
                        </td>
                    </tr>
                    <tr>
                        <td></td>
                    </tr>
                    {contacts.map((c, i) => (
                        <tr key={i}>
                            <td>
                                <div>
                                    <Editable
                                        text={c.full_name}
                                        onSuccess={updateContactsHandler}
                                        submitFunction={(value) =>
                                            updateContacts({ field: 'full_name', value, pk: c.pk })
                                        }
                                    />
                                </div>
                            </td>
                            <td>
                                <div>
                                    <Editable
                                        text={c.email}
                                        onSuccess={updateContactsHandler}
                                        submitFunction={(value) =>
                                            updateContacts({ field: 'email', value, pk: c.pk })
                                        }
                                    />
                                </div>
                            </td>
                            <td>
                                <div>
                                    <Editable
                                        text={c.phone}
                                        onSuccess={updateContactsHandler}
                                        submitFunction={(value) =>
                                            updateContacts({ field: 'phone', value, pk: c.pk })
                                        }
                                    />
                                </div>
                            </td>
                            <td>
                                <div>
                                    <Editable
                                        text={c.position}
                                        onSuccess={updateContactsHandler}
                                        submitFunction={(value) =>
                                            updateContacts({ field: 'position', value, pk: c.pk })
                                        }
                                    />
                                </div>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

const mapStateToProps = (state) => ({
    contacts: state.contacts.list,
    user: state.user,
});

const mapDispatchToProps = (dispatch) =>
    bindActionCreators({ addContact, fetchContacts, updateContacts }, dispatch);

export default connect(mapStateToProps, mapDispatchToProps)(ContactsTable);
