import React, { useState } from 'react';
import useOnclickOutside from 'react-cool-onclickoutside';
import styles from './CustomSelect.module.scss';

function CustomSelect({ onChange, value, options, defaultOption, className }) {
    const [opened, setOpened] = useState(false);
    const ref = useOnclickOutside(() => {
        setOpened(false);
    });

    function toggleOpened() {
        setOpened(!opened);
    }

    return (
        <div
            ref={ref}
            className={styles.customSelect + ' ' + styles.dropdownMenu + ' ' + className}
        >
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
                        : '')
                }
            >
                {value === '' ? options[0] : value}
            </div>
            <div
                className={
                    styles.selectItems + ' ' + (!opened ? styles.selectHide : styles.selectWhite)
                }
            >
                {options.map((o, i) => (
                    <div
                        onClick={() => {
                            onChange(i === 0 ? '' : o);
                            toggleOpened();
                        }}
                        key={o}
                        className={
                            (i === 0 ? value === '' : value === o) ? styles.sameAsSelected : ''
                        }
                    >
                        {i === 0 ? defaultOption : o}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default CustomSelect;
