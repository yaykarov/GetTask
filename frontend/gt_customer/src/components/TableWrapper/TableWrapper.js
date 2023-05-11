import React, { useState, useRef, useEffect } from 'react';
import styles from './TableWrapper.module.scss';
import Spinner from '../Spinner/Spinner';
import ScrollSlider from '../ScrollSlider/ScrollSlider';

const TableWrapper = ({ head, body, isLoading, className, pagination }) => {
    return (
        <div className={styles.tableWrapper}>
            <table className={styles.table + ' ' + className}>
                {head}
                <tr>
                    <td></td>
                </tr>
                {body}
            </table>
            {isLoading && <Spinner />}
        </div>
    );
};

export default TableWrapper;
