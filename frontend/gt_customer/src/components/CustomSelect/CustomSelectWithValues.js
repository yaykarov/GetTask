import { Button, Popover } from 'antd';
import React, { forwardRef, useEffect, useRef, useState } from 'react';
import styles from './CustomSelect.module.scss';
import useOnClickOutside from 'react-cool-onclickoutside';

function CustomSelectWithValues({
    onChange,
    values,
    selected,
    options,
    defaultName = 'Все',
    defaultOption,
    className,
    dontShowDefaultNameInOptions,
    setOpened,
}) {
    const addedEmptyStringArr = dontShowDefaultNameInOptions ? [] : [''];
    const _values = values
        ? [...addedEmptyStringArr, ...values]
        : [...addedEmptyStringArr, ...options];
    const _options = dontShowDefaultNameInOptions ? [...options] : [defaultName, ...options];
    const selectIndex = _values.indexOf(selected);
    const [popupOpened, setPopupOpened] = useState(false);
    const buttonRef = useRef(null);
    const wrapperRef = useOnClickOutside(() => {
        if (setOpened) {
            setOpened(false);
        }
    });

    const toggleOpened = (isVisible) => {
        setPopupOpened(isVisible);
    };
    return (
        <div
            ref={wrapperRef}
            className={`${styles.customSelect} ${styles.dropdownMenu} ${className}`}
        >
            <Popover
                destroyTooltipOnHide
                mouseEnterDelay={0}
                mouseLeaveDelay={0}
                placement='bottom'
                popupVisible={popupOpened}
                trigger='click'
                onVisibleChange={toggleOpened}
                afterVisibleChange={(visible) => {
                    if (!visible && setOpened) {
                        setOpened(false);
                    }
                }}
                overlayInnerStyle={{
                    position: 'absolute',
                    left: `${buttonRef.current?.getBoundingClientRect().x}px`,
                }}
                overlayStyle={{ pointerEvents: 'visible !important' }}
                content={
                    <Options
                        ref={popupOpened ? wrapperRef : null}
                        values={_values}
                        options={_options}
                        onChange={onChange}
                        toggleOpened={toggleOpened}
                        opened={popupOpened}
                        selectIndex={selectIndex}
                    />
                }
            >
                <div
                    ref={buttonRef}
                    className={`${styles.selectSelected} ${
                        popupOpened
                            ? `${styles.selectArrowActive} ${styles.selectNoBorder} ${styles.selectWhite}`
                            : ''
                    }`}
                >
                    {_options[selectIndex]}
                </div>
            </Popover>
        </div>
    );
}

const Options = forwardRef(
    ({ options, onChange, toggleOpened, values, selectIndex, opened }, ref) => {
        if (!opened) {
            return null;
        }
        return (
            <div ref={ref} className={`${styles.selectItems} ${styles.selectWhite}`}>
                {options.map((o, i) => (
                    <div
                        onClick={() => {
                            onChange(values[i]);
                        }}
                        key={o}
                        className={i === selectIndex ? styles.sameAsSelected : ''}
                    >
                        {options[i]}
                    </div>
                ))}
            </div>
        );
    }
);

export default CustomSelectWithValues;
