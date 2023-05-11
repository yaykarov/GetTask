import React, { useState, useEffect } from 'react';
import InputMask from 'react-input-mask';
import styles from './TimePicker.module.scss';

function TimePicker({ close, value, onChange }) {
    const [input1, setInput1] = useState(value[0] || '__:__');
    const [input2, setInput2] = useState(value[1] || '__:__');

    function normalize() {
        let i1 = input1;
        let i2 = input2;
        // normalize input1
        if (!input1.includes('_')) {
            const [hh, mm] = input1.split(':');
            const HH = String(Math.min(+hh, 23)).padStart(2, '0');
            const MM = String(Math.min(+mm, 59)).padStart(2, '0');
            i1 = `${HH}:${MM}`;
        }
        // normalize input2
        if (!input2.includes('_')) {
            const [hh, mm] = input2.split(':');
            const HH = String(Math.min(+hh, 23)).padStart(2, '0');
            const MM = String(Math.min(+mm, 59)).padStart(2, '0');
            i2 = `${HH}:${MM}`;
        }
        // swap inputs if second one's time less than the first one's
        if (!input1.includes('_') && !input2.includes('_')) {
            const [hh1, mm1] = input1.split(':');
            const [hh2, mm2] = input2.split(':');
            const ss1 = hh1 * 3600 + mm1 * 60;
            const ss2 = hh2 * 3600 + mm2 * 60;
            if (ss1 > ss2) {
                [i1, i2] = [i2, i1];
            }
            onChange([i1, i2]);
        }
        setInput1(i1);
        setInput2(i2);
    }

    return (
        <div className={styles.popup}>
            <div onClick={close} className={styles.popupClose}>
                <img alt='icon' src='/close_icon.svg' />
            </div>
            <div className={styles.popupTitle}>Выбрать время</div>
            <div className={styles.popupContent}>
                <div className={styles.wrapper}>
                    <InputMask
                        onBlur={normalize}
                        mask='99:99'
                        alwaysShowMask
                        onChange={(e) => setInput1(e.target.value)}
                        value={input1}
                    />
                    <div className={styles.dash} />
                    <InputMask
                        onBlur={normalize}
                        mask='99:99'
                        alwaysShowMask
                        onChange={(e) => setInput2(e.target.value)}
                        value={input2}
                    />
                </div>
            </div>
            <div onClick={close} className={styles.button}>
                Ок
            </div>
        </div>
    );
}

export default TimePicker;
