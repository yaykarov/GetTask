import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import styles from '../../Authentication/Authentication.module.scss';
import { withAuthentication } from '../../hoc';
import { setToken } from '../../../utils';

function LoginPage({ obtainToken, accountInfo, setPopup }) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [rememberMe, setRememberMe] = useState(false);

    function handleLogin() {
        obtainToken({}, { email, password })
            .then((res) => {
                localStorage.clear();
                setToken(res.payload.data.access_token, rememberMe);
                return accountInfo({ token: res.payload.data.access_token });
            })
            .then((res) => console.log('res: ', res))
            .catch((err) =>
                setPopup({
                    open: true,
                    content:
                        err.error.response.data.message ||
                        `${err.error.response.status} ${err.error.response.statusText}`,
                    title: 'Ошибка',
                })
            );
    }

    return (
        <React.Fragment>
            <div className={styles.title}>Вход</div>
            <div className={styles.info}>
                <p></p>
            </div>
            <div className={styles.label}>Email</div>
            <input value={email} onChange={(e) => setEmail(e.target.value)} />
            <div className={styles.label}>Пароль</div>
            <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type={'password'}
            />
            <div className={styles.resetPasswordWrap}>
                <Link to='/reset_password' className={styles.resetPasswordLink}>
                    Забыли пароль?
                </Link>
            </div>
            <div className={styles.line}>
                <div onClick={handleLogin} className={styles.button}>
                    Войти
                </div>
                <div>
                    <label className={styles.checkboxContainer}>
                        <input
                            type='checkbox'
                            checked={rememberMe}
                            onChange={(e) => setRememberMe(e.target.checked)}
                        />
                        <div className={styles.checkboxLabel}>Запомнить меня</div>
                        <span className={styles.checkmark} />
                    </label>
                </div>
            </div>
            <div className={styles.register}>
                <div>Нет учетной записи?</div>
                <Link to='/signup'>Зарегистрируйтесь</Link>
            </div>
        </React.Fragment>
    );
}

export default withAuthentication(LoginPage);
