import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import downloadFile from '../../utils/download';
import { connect } from 'react-redux';
import styles from './PhotoTooltip.module.scss';
import { BACKEND_URL } from '../../utils/constants';
import { getToken } from '../../utils';
import _ from 'underscore';

function PhotoTooltip({ className, urls, title }) {
    const prevUrls = useRef(urls);
    const [img, setImg] = useState(null);
    const [i, setI] = useState(0);
    const token = getToken();

    function download({ url }) {
        axios({
            method: 'get',
            url: `${BACKEND_URL}${url}`,
            headers: {
                Authorization: `Bearer ${token}`,
            },
            responseType: 'blob',
        })
            .then((response) => {
                setImg(new Blob([response.data]));
            })
            .catch((error) => {
                console.error(error);
            });
    }

    useEffect(() => {
        if (!_.isEqual(prevUrls.current, urls)) {
            prevUrls.current = urls;

            setImg(null);
            setI(0);

            if (urls) {
                download(urls[0]);
            }
        }
    }, [urls, prevUrls]);

    const onPhotoChange = (currentI) => {
        setI(currentI);
        download(urls[currentI]);
    };

    if (!urls?.length) {
        return null;
    }
    return (
        <div className={styles.wrapper + ' ' + className}>
            <div className={styles.topLine}>
                <div>{title}</div>
                <div>
                    <img
                        onClick={() => onPhotoChange(Math.max(i - 1, 0))}
                        alt='icon'
                        src='/prev_icon.svg'
                    />
                    <div>{i + 1}</div>
                    <img
                        onClick={() => onPhotoChange(Math.min(i + 1, urls.length - 1))}
                        alt='icon'
                        src='/next_icon.svg'
                    />
                </div>
                <div onClick={downloadFile({ url: urls[i]?.url, filename: 'scan.jpg' })}>
                    <img alt='icon' src='/save_icon.svg' />
                    Скачать
                </div>
            </div>
            <img src={img && window.URL.createObjectURL(img)} alt='img' />
        </div>
    );
}

const mapStateToProps = (state) => ({
    user: state.user,
});

export default connect(mapStateToProps)(PhotoTooltip);
