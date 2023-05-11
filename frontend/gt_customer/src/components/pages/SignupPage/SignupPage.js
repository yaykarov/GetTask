import React, { useState } from 'react';
import styles from '../../Authentication/Authentication.module.scss';
import { withAuthentication } from '../../hoc';

function SignupPage({ signup, history, popup, setPopup }) {
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [organizationName, setOrganizationName] = useState('');
    const [phone, setPhone] = useState('');
    const [rulesCheckbox, setRulesCheckbox] = useState(false);
    const [pdpCheckbox, setPdpCheckbox] = useState(false);
    const [success, setSuccess] = useState(false);

    function handleSignup() {
        if (rulesCheckbox && pdpCheckbox) {
            signup(undefined, {
                organization_name: organizationName,
                full_name: fullName,
                email,
                password,
                phone,
            })
                .then(() => {
                    setPopup({
                        open: true,
                        title: 'Информация',
                        content:
                            'Проверьте свою почту и перейдите по ссылке в письме для завершения регистрации.',
                        onClose: () => history.push('/login'),
                    });
                    setSuccess(true);
                })
                .catch((err) =>
                    setPopup({
                        open: true,
                        title: 'Ошибка',
                        content:
                            err?.error?.response?.data?.message ||
                            `${err?.error?.response?.status} ${err?.error?.response?.statusText}`,
                    })
                );
        }
    }

    if (success && popup.open === false) history.push('/login');

    return (
        <>
            <div className={styles.title}>Регистрация</div>
            <div className={styles.label}>Ваше имя</div>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
            <div className={styles.label}>Название организации</div>
            <input value={organizationName} onChange={(e) => setOrganizationName(e.target.value)} />
            <div className={styles.label}>Телефон</div>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
            <div className={styles.label}>Email</div>
            <input value={email} onChange={(e) => setEmail(e.target.value)} />
            <div className={styles.label}>Пароль</div>
            <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={styles.lastInput}
                type={'password'}
            />
            <div className={styles.checkboxAlign}>
                <label className={styles.checkboxContainer}>
                    <input
                        type='checkbox'
                        checked={rulesCheckbox}
                        onChange={() => setRulesCheckbox(!rulesCheckbox)}
                    />
                    <div className={styles.checkboxLabel}>
                        Я соглашаюсь с <a href='https://gettask.ru/rules.doc'>Правилами сервиса</a>
                    </div>
                    <span className={styles.checkmark} />
                </label>
            </div>
            <div className={styles.checkboxAlign}>
                <label className={styles.checkboxContainer}>
                    <input
                        type='checkbox'
                        checked={pdpCheckbox}
                        onChange={() => setPdpCheckbox(!pdpCheckbox)}
                    />
                    <div className={styles.checkboxLabel}>
                        Я соглашаюсь с{' '}
                        <a href='https://gettask.ru/personal_data_policy.doc'>
                            Соглашением на обработку персональных данных
                        </a>
                    </div>
                    <span className={styles.checkmark} />
                </label>
            </div>
            <div
                onClick={handleSignup}
                className={
                    styles.buttonSign + ' ' + (pdpCheckbox && rulesCheckbox ? '' : styles.disabled)
                }
            >
                Зарегистрироваться
            </div>
        </>
    );
}

export default withAuthentication(SignupPage);
