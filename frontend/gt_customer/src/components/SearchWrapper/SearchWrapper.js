import React, { useEffect, useState } from 'react';
import styles from './SearchWrapper.module.scss';

const stack = [];

const SearchWrapper = ({
    localStorageService,
    updateData,
    itemsOnPage,
    setItemsOnPage,
    placeHolder,
    children,
}) => {
    const [mounted, setMounted] = useState(false);
    const [search, setSearch] = useState(localStorageService.get('search', ''));

    useEffect(() => {
        localStorageService.set('search', search);
        stack.push('delay');
        setTimeout(() => {
            stack.pop();
            if (stack.length === 0) {
                mounted && updateData();
            }
        }, 600);
    }, [search]);

    useEffect(() => {
        setMounted(true);
    }, []);

    return (
        <>
            <div className={styles.line2}>
                <div className={styles.searchBar}>
                    <img alt='icon' src='/search_icon.svg' />
                    <input
                        placeholder={placeHolder}
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
                {children}
                <div className={styles.itemsCountWrapper}>
                    <div className={styles.itemsCount}>
                        <span>На странице</span> {itemsOnPage}{' '}
                        <img alt='icon' src='/arrow_down_icon.svg' />
                    </div>
                    <div className={styles.itemsCountDropdown}>
                        <div onClick={() => setItemsOnPage(25)} className={styles.itemsCountSelect}>
                            25
                        </div>
                        <div onClick={() => setItemsOnPage(50)} className={styles.itemsCountSelect}>
                            50
                        </div>
                        <div
                            onClick={() => setItemsOnPage(100)}
                            className={styles.itemsCountSelect}
                        >
                            100
                        </div>
                    </div>
                </div>
            </div>
            <div className={styles.underline} />
        </>
    );
};

export default SearchWrapper;
