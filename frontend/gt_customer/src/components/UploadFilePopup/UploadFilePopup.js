import React, { useState } from 'react';
import axios from 'axios';
import { connect } from 'react-redux';
import styles from './UploadFilePopup.module.scss';
import { BACKEND_URL } from '../../utils/constants';
import { getToken } from '../../utils';

function UploadFilePopup({ close, name, endpoint, onSuccess, onFailure, user }) {
    const [files, setFiles] = useState([]);
    const token = getToken();
    console.log(files);

    function onFileChange(e) {
        setFiles([...e.target.files]);
    }

    function onFileUpload() {
        close();
        if (files.length) {
            const formData = new FormData();
            files.map((file) => formData.append(name, file, file.name));

            axios
                .post(`${BACKEND_URL}${endpoint}`, formData, {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                })
                .then((res) => {
                    if (onSuccess && res.status === 200) {
                        onSuccess();
                    }
                    if (onFailure && res.status !== 200) {
                        onFailure(res.data.message);
                    }
                })
                .catch((err) => {
                    onFailure(err.response ? err.response.data.message : err.message);
                });
        }
    }

    return (
        <div className={styles.popup}>
            <div onClick={close} className={styles.popupClose}>
                <img alt='icon' src='/close_icon.svg' />
            </div>
            <div className={styles.popupTitle}>Загрузить файл</div>
            <div className={styles.popupContent}>
                <input type='file' multiple onChange={onFileChange} />
            </div>
            <div onClick={onFileUpload} className={styles.button}>
                Отправить
            </div>
        </div>
    );
}

const mapStateToProps = (state) => ({
    user: state.user,
});

export default connect(mapStateToProps)(UploadFilePopup);
