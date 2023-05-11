import React, { useEffect, useState, useCallback } from 'react';
import styles from './DatePickerApply.module.scss';
import moment from 'moment';
import { DateRange } from 'react-date-range';
import * as locales from 'react-date-range/dist/locale';
import styled from 'styled-components';
import Popup from 'reactjs-popup';

const ShortPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

const DatePickerApply = ({
    localStorageService,
    updateData,
    defaultRangeStart,
    defaultRangeEnd,
}) => {
    const rangeStart = defaultRangeStart || moment().subtract(7, 'days').toDate();
    const rangeEnd = defaultRangeEnd || moment().toDate();

    const [mounted, setMounted] = useState(false);
    const [ranges, setRanges] = useState([
        {
            startDate: moment(localStorageService.get('startRanges', rangeStart)).toDate(),
            endDate: moment(localStorageService.get('endRanges', rangeEnd)).toDate(),
            key: 'selection',
        },
    ]);

    const [_ranges, _setRanges] = useState(ranges);

    useEffect(() => {
        localStorageService.set('startRanges', ranges[0].startDate);
        localStorageService.set('endRanges', ranges[0].endDate);
        mounted && updateData();
        // eslint-disable-next-line
    }, [ranges]);

    useEffect(() => {
        setMounted(true);
    }, []);

    const handleLeft = useCallback(() => {
        const { startDate, endDate } = ranges[0];

        setRanges([
            {
                startDate: moment(startDate).subtract(1, 'days').toDate(),
                endDate: moment(endDate).subtract(1, 'days').toDate(),
                key: 'selection',
            },
        ]);
    }, [ranges]);

    const handleRight = useCallback(() => {
        const { startDate, endDate } = ranges[0];

        setRanges([
            {
                startDate: moment(startDate).add(1, 'days').toDate(),
                endDate: moment(endDate).add(1, 'days').toDate(),
                key: 'selection',
            },
        ]);
    }, [ranges]);

    return (
        <div className={styles.datePickerContainer}>
            <img
                alt='icon'
                src='/circle_arrow.svg'
                className={styles.arrow__Left}
                onClick={handleLeft}
            />
            <ShortPopup
                trigger={
                    ranges[0].startDate && ranges[0].endDate ? (
                        <div className={styles.datePicker}>
                            <img alt='icon' src='/calendar_icon.svg' />
                            <div>{moment(ranges[0].startDate).format('DD.MM.YYYY')}</div>
                            <div className={styles.datePickerDash} />
                            <div>{moment(ranges[0].endDate).format('DD.MM.YYYY')}</div>
                        </div>
                    ) : (
                        <div className={styles.datePicker}>
                            <img alt='icon' src='/calendar_icon.svg' />
                            Все время
                        </div>
                    )
                }
                modal
                closeOnDocumentClick
            >
                {(close) => (
                    <>
                        <DateRange
                            editableDateInputs={false}
                            onChange={(item) => _setRanges([item.selection])}
                            moveRangeOnFirstSelection={false}
                            ranges={_ranges}
                            locale={locales['ru']}
                            rangeColors={['#000000']}
                            className={styles.dateRange}
                        />
                        <div
                            onClick={() => {
                                close();
                                setRanges(_ranges);
                            }}
                            className={styles.buttonApply}
                        >
                            <div>Применить</div>
                        </div>
                    </>
                )}
            </ShortPopup>
            <img
                alt='icon'
                src='/circle_arrow.svg'
                className={styles.arrow__Right}
                onClick={handleRight}
            />
        </div>
    );
};
export default DatePickerApply;
