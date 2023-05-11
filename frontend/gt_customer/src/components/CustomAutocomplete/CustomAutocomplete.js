import React, { useState, useEffect } from 'react';
import onClickOutside from 'react-onclickoutside';
import styles from './CustomAutocomplete.module.scss';

function CustomAutocomplete({
    onChange,
    value,
    options,
    placeholder,
    onIdChange,
    disabled,
    defaultId,
}) {
    const [opened, setOpened] = useState(false);
    const [id, setId] = useState(defaultId);
    useEffect(() => {
        setId(defaultId);
    }, [defaultId]);

    CustomAutocomplete.handleClickOutside = (e) => setOpened(false);
    let inputRef = React.createRef();

    useEffect(() => {
        onIdChange(id);
    }, [id]);

    useEffect(() => {
        if (opened) {
            inputRef.current.focus();
        } else {
            inputRef.current.blur();
        }
    }, [opened]);

    const toggleOpened = () => {
        if (!disabled) {
            setOpened(!opened);
        }
    };

    const clearSelection = (e) => {
        e.persist();
        e.stopPropagation();

        onChange('');
        setId(-1);
    };

    return (
        <div className={styles.customSelect + ' ' + styles.dropdownMenu}>
            <div
                onClick={toggleOpened}
                className={
                    styles.selectSelected +
                    ' ' +
                    (opened
                        ? styles.selectArrowActive +
                          ' ' +
                          styles.selectNoBorder +
                          ' ' +
                          styles.selectWhite
                        : '') +
                    (disabled ? styles.disabled : '')
                }
            >
                <input
                    disabled={disabled}
                    className={disabled ? styles.disabled : ''}
                    placeholder={placeholder}
                    ref={inputRef}
                    value={value}
                    onChange={(e) => {
                        onChange(e.target.value);
                        if (id !== -1) {
                            setId(-1);
                        }
                    }}
                />
                {value && (
                    <div style={{ marginRight: '12px' }} onClick={clearSelection}>
                        <img src='/close_icon.svg' width='22px' height='22px' />
                    </div>
                )}
            </div>
            <div
                className={
                    styles.selectItems + ' ' + (!opened ? styles.selectHide : styles.selectWhite)
                }
            >
                {options.map((o, i) => (
                    <div
                        onClick={() => {
                            onChange(o.text);
                            setId(o.id);
                            toggleOpened();
                        }}
                        key={o.id}
                        className={value === o ? styles.sameAsSelected : ''}
                        dangerouslySetInnerHTML={{ __html: o.text }}
                    />
                ))}
            </div>
        </div>
    );
}

const clickOutsideConfig = {
    handleClickOutside: () => CustomAutocomplete.handleClickOutside,
};

export default onClickOutside(CustomAutocomplete, clickOutsideConfig);
