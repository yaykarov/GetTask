import React, { useState } from 'react';
import styles from './Pagination.module.scss';

function pagination(c, m) {
    let current = c,
        last = m,
        delta = 1,
        left = current - delta,
        right = current + delta + 1,
        range = [],
        rangeWithDots = [],
        l;

    for (let i = 1; i <= last; i++) {
        if (i === 1 || i === last || (i >= left && i < right)) {
            range.push(i);
        }
    }

    for (let i of range) {
        if (l) {
            if (i - l === 2) {
                rangeWithDots.push(l + 1);
            } else if (i - l !== 1) {
                rangeWithDots.push('...');
            }
        }
        rangeWithDots.push(i);
        l = i;
    }

    return rangeWithDots;
}

function Pagination({ pages, onPageChange, stylesRef }) {
    const [page, setPage] = useState(1);
    pages = pages || 1;

    if (pages <= 7) {
        return (
            <div className={styles.bottomNav} style={stylesRef?.wrap}>
                <img
                    onClick={() => {
                        setPage(Math.max(page - 1, 1));
                        onPageChange(Math.max(page - 1, 1));
                    }}
                    alt='icon'
                    src='/prev_icon.svg'
                    className={styles.bottomNavItem}
                    style={stylesRef?.item}
                />
                {[...Array(pages).keys()].map((p) => (
                    <div
                        key={p}
                        className={
                            styles.bottomNavItem +
                            ' ' +
                            (page === p + 1 ? styles.bottomNavActive : '')
                        }
                        style={stylesRef?.item}
                        onClick={() => {
                            setPage(p + 1);
                            onPageChange(p + 1);
                        }}
                    >
                        {p + 1}
                    </div>
                ))}
                <img
                    onClick={() => {
                        setPage(Math.min(page + 1, pages));
                        onPageChange(Math.min(page + 1, pages));
                    }}
                    alt='icon'
                    src='/next_icon.svg'
                    className={styles.bottomNavItem}
                    style={stylesRef?.item}
                />
            </div>
        );
    } else {
        return (
            <div className={styles.bottomNav} style={stylesRef?.wrap}>
                <img
                    onClick={() => {
                        setPage(Math.max(page - 1, 1));
                        onPageChange(Math.max(page - 1, 1));
                    }}
                    alt='icon'
                    src='/prev_icon.svg'
                    className={styles.bottomNavItem}
                    style={stylesRef?.item}
                />
                {pagination(page, pages).map((el) => (
                    <div
                        onClick={() => {
                            setPage(el);
                            onPageChange(el);
                        }}
                        className={
                            (el === '...' ? styles.bottomNavDots : styles.bottomNavItem) +
                            ' ' +
                            (page === el ? styles.bottomNavActive : '')
                        }
                        style={stylesRef?.item}
                    >
                        {el}
                    </div>
                ))}
                <img
                    onClick={() => {
                        setPage(Math.min(page + 1, pages));
                        onPageChange(Math.min(page + 1, pages));
                    }}
                    alt='icon'
                    src='/next_icon.svg'
                    className={styles.bottomNavItem}
                    style={stylesRef?.item}
                />
            </div>
        );
    }
}

export default Pagination;
