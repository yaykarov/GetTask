import React, { useRef } from 'react';
import styles from './TableRequestsWrapper.module.scss';
import Spinner from '../Spinner/Spinner';
import ScrollSlider from '../ScrollSlider/ScrollSlider';

const TableRequestsWrapper = ({ head, body, isLoading, className, pagination, lead }) => {
    const wrapRef = useRef(null);
    const contentRef = useRef(null);

    return (
        <div className={styles.tableWrapper} ref={wrapRef}>
            {lead}

            <table className={`${styles.table} ${className}`} ref={contentRef}>
                <thead>{head}</thead>
                <tbody>{body}</tbody>
            </table>

            {isLoading && <Spinner />}

            <ScrollSlider wrapRef={wrapRef} contentRef={contentRef}>
                {pagination}
            </ScrollSlider>
        </div>
    );
};

export default TableRequestsWrapper;
