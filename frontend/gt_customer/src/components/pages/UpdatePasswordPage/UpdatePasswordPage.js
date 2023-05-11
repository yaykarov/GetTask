import React, { useState } from 'react';
import { Redirect } from 'react-router-dom';
import styles from '../../Authentication/Authentication.module.scss';
import { withAuthentication } from '../../hoc';

const UpdatePasswordPage = ({ match, updatePassword, setPopup }) => {
    const [password, setPassword] = useState('');
    const [passwordValid, setPasswordValid] = useState('');
    const [success, setSuccess] = useState(false);
    const uid = match.params.uid;

    const handleUpdatePassword = () => {
        if (!password || password !== passwordValid) {
            setPopup({
                open: true,
                content: 'Введенные пароли не совпадают',
                title: 'Ошибка',
            });
        } else {
            updatePassword({ password, uid })
                .then((res) => {
                    setSuccess(true);
                    return res;
                })
                .then((res) => console.log('res: ', res))
                .catch((err) => {
                    setPopup({
                        open: true,
                        content:
                            err.error.response.data.message ||
                            `${err.error.response.status} ${err.error.response.statusText}`,
                        title: 'Ошибка',
                    });
                });
        }
    };

    if (success) return <Redirect to='/login' />;

    return (
        <React.Fragment>
            <div className={styles.title}>Восстановление пароля</div>
            <div className={styles.info}>
                <p>Введите новый пароль, который будет использоваться для входа</p>
            </div>
            <div className={styles.label}>Новый пароль</div>
            <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type={'password'}
            />
            <div className={styles.label}>Повторите пароль</div>
            <input
                value={passwordValid}
                onChange={(e) => setPasswordValid(e.target.value)}
                type={'password'}
            />

            <div className={styles.line}>
                <div onClick={handleUpdatePassword} className={styles.button}>
                    Сохранить
                </div>
            </div>
        </React.Fragment>
    );
};

export default withAuthentication(UpdatePasswordPage);
