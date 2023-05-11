import React, { useState, useEffect, memo } from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import styles from './Editable.module.scss';
import { updateAdressRequest, updateRequest } from '../../actions';
import axios from 'axios';

function Editable({
    text,
    onSuccess,
    onEnterSuccess,
    pk,
    field,
    item_pk,
    updateRequest,
    updateAdressRequest,
    editable,
    submitFunction,
    inputComponent,
    focused,
    maxLength,
    notOpenedClassName,
    onlyNumber,
    sendRequestOnBlur,
    isRequiredStatus,
}) {
    text = text === null ? '' : text;

    const [value, setValue] = useState(text);
    const [opened, setOpened] = useState(focused);
    const [status, setStatus] = useState(''); // '' (default) | loading | success | error
    const [warning, setWarning] = useState(false);
    const [warningNumber, setWarningNumber] = useState(false);

    useEffect(() => setOpened(focused), [focused]);

    useEffect(() => {
        if (text) setValue(text);
    }, [text]);

    function showSuccess() {
        setStatus('success');
        setTimeout(() => {
            setStatus('');
        }, 1000);
    }

    function showError() {
        setStatus('error');
        setTimeout(() => {
            setStatus('');
        }, 1000);
    }
    async function handleSubmit(val, isEnter = false) {
        try {
            setOpened(false);
            setStatus('loading');

            if (submitFunction) {
                await submitFunction(val !== undefined ? val : value);

                if (isEnter) {
                    if (onEnterSuccess) {
                        onEnterSuccess(value);
                    }
                }
            } else {
                if (item_pk) {
                    await updateAdressRequest(
                        {},
                        {
                            [field]: val !== undefined ? `${val}` : value,
                            request: pk,
                            item: item_pk,
                        }
                    );
                } else {
                    await updateRequest(
                        {},
                        {
                            [field]: val !== undefined ? `${val}` : value,
                            request: pk,
                        }
                    );
                }
            }

            showSuccess();

            if (onSuccess) {
                onSuccess(value);
            }
        } catch (e) {
            showError();
        }
    }

    if (status === 'loading') {
        return (
            <div className={styles.wrapper}>
                <div className={styles.loading}>
                    <div />
                    <div />
                    <div />
                </div>
            </div>
        );
    }
    if (editable) {
        return (
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis' }} title={text}>
                {text}
            </div>
        );
    }
    if (status === 'success') {
        return (
            <div className={styles.wrapper}>
                <div className={styles.success}>
                    <img alt='icon' src='/success_icon.svg' />
                </div>
            </div>
        );
    }

    if (status === 'error') {
        return (
            <div className={styles.wrapper}>
                <div className={styles.error}>
                    <img alt='icon' src='/cross_icon.svg' />
                </div>
            </div>
        );
    }

    if (!opened) {
        return (
            <span
                onClick={() => {
                    setValue(text);
                    setOpened(true);
                }}
                className={styles.notOpened + ' ' + notOpenedClassName}
                style={{
                    border: isRequiredStatus ? '2px solid #FD1B1BAA' : 'none',
                    borderRadius: 5,
                }}
                title={value}
            >
                {value || '-'}
            </span>
        );
    } else {
        const onBlur = () => {
            setOpened(false);

            if (sendRequestOnBlur) {
                handleSubmit();
            }
        };
        return (
            <div className={styles.wrapper}>
                {inputComponent ? (
                    inputComponent(value, setValue, handleSubmit, onBlur, setOpened)
                ) : (
                    <input
                        onBlur={onBlur}
                        autoFocus
                        spellCheck={false}
                        value={value}
                        onChange={(e) => {
                            if (
                                e.target.value &&
                                onlyNumber &&
                                !new RegExp(/^[0-9]+$/gm).test(e.target.value)
                            ) {
                                setWarningNumber(true);
                                return;
                            } else {
                                setWarningNumber(false);
                            }
                            if (
                                e.target.value.length <= maxLength ||
                                maxLength === null ||
                                maxLength === undefined
                            ) {
                                setValue(e.target.value);
                                setWarning(false);
                            } else {
                                setWarning(true);
                            }
                        }}
                        onKeyDown={({ key }) => key === 'Enter' && handleSubmit(undefined, true)}
                        style={{
                            background: warning ? '#F44336' : '#F2F2F2',
                        }}
                    />
                )}
                <div className={styles.tooltip}>
                    {(() => {
                        if (warningNumber) {
                            return `Разрешены только цифры`;
                        }

                        if (warning) {
                            return `Максимальная длина: ${maxLength} знаков`;
                        }

                        return null;
                    })()}
                </div>
            </div>
        );
    }
}

const mapDispatchToProps = (dispatch) =>
    bindActionCreators({ updateRequest, updateAdressRequest }, dispatch);

export default connect(null, mapDispatchToProps)(memo(Editable));
