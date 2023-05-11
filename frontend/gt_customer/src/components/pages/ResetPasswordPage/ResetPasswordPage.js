import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import styles from '../../Authentication/Authentication.module.scss';
import { withAuthentication } from '../../hoc';

const ResetPasswordPage = ({ resetPassword, setPopup, popup, history }) => {
    const [email, setEmail] = useState('');
    const [success, setSuccess] = useState(false);

    const handleResetPassword = () => {
        resetPassword({ email })
            .then((res) => {
                setPopup({
                    open: true,
                    content: 'Вам на почту отправлено письмо с дальнейшими иструкциями.',
                    title: 'Ок',
                });
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
    };

    if (success && popup.open === false) history.push('/login');

    return (
        <React.Fragment>
            <div className={styles.title}>Восстановление пароля</div>
            <div className={styles.info}>
                <p>
                    Введите ваш e-mail, на который мы отправим письмо со ссылкой для смены пароля.
                </p>
            </div>
            <div className={styles.label}>Email</div>
            <input value={email} onChange={(e) => setEmail(e.target.value)} />

            <div className={styles.line}>
                <div onClick={handleResetPassword} className={styles.button}>
                    Отправить
                </div>
                <div>
                    <Link to='/login' className={styles.resetPasswordLink}>
                        Отмена
                    </Link>
                </div>
            </div>
        </React.Fragment>
    );
};

export default withAuthentication(ResetPasswordPage);
