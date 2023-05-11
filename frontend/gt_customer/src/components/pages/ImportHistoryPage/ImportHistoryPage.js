import React, { memo, useEffect, useState } from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import { Redirect } from 'react-router-dom';
import { fetchImports } from '../../../actions';
import styles from './ImportHistoryPage.module.scss';
import _ from 'underscore';
import moment from 'moment';
import DatePickerApply from '../../DatePickerApply/DatePickerApply';
import { IMPORTS_PREFIX, ITEMS_ON_PAGE } from '../../../utils/constants';
import Pagination from '../../Pagination/Pagination';
import downloadFile from '../../../utils/download';
import { storageService } from '../../../utils';
import { userInfoSelector } from '../../../utils/reselect';
import { ImportsButton, DownloadExcelButton } from '../../buttons';
import ButtonsContainer from '../../ButtonsContainer/ButtonsContainer';
import TableWrapper from '../../TableWrapper/TableWrapper';
import Wrapper from '../../Wrapper/Wrapper';
import CustomSelectWithStorage from '../../CustomSelectWithStorage/CustomSelectWithStorage';
import SearchWrapper from '../../SearchWrapper/SearchWrapper';

const IMPORTS_STATUSES = [
    { id: 'processing', title: 'Формируется', class: 'import-status-processing' },
    {
        id: 'finished_with_errors',
        title: 'С ошибками',
        class: 'import-status-finished_with_errors',
    },
    { id: 'finished', title: 'Готово', class: 'import-status-finished' },
];

const localStorageService = storageService(IMPORTS_PREFIX);

function ImportHistoryPage({ list, isLoading, userInfo, fetchImports }) {
    const { allow_requests_creation } = userInfo;
    const [itemsOnPage, setItemsOnPage] = useState(
        localStorageService.get('itemsOnPage', ITEMS_ON_PAGE)
    );
    const [page, setPage] = useState(1);
    const pages = Math.ceil(list.length / itemsOnPage);

    function getStatusClass(status) {
        const findStatus = IMPORTS_STATUSES.find((item) => item.id == status.id);
        const statusClass =
            findStatus && findStatus.hasOwnProperty('class')
                ? findStatus.class
                : 'import-status-default';

        return `${styles['import-status']} ${styles[statusClass]}`;
    }

    const updateData = _.throttle(updateImports, 500);
    function updateImports() {
        return fetchImports({
            status: localStorageService.get('status'),
            search_text: localStorageService.get('search'),
            first_ay: moment(localStorageService.get('startRanges')).format('DD.MM.YYYY'),
            last_ay: moment(localStorageService.get('endRanges')).format('DD.MM.YYYY'),
        });
    }

    useEffect(() => {
        updateData();
    }, []);

    useEffect(() => {
        localStorageService.set('itemsOnPage', itemsOnPage);
    }, [itemsOnPage]);

    return (
        <Wrapper title='История импорта'>
            <SearchWrapper
                placeHolder='Найти импорт заявок'
                localStorageService={localStorageService}
                updateData={updateData}
                itemsOnPage={itemsOnPage}
                setItemsOnPage={setItemsOnPage}
            />

            <ButtonsContainer
                left={
                    <>
                        <DatePickerApply
                            localStorageService={localStorageService}
                            updateData={updateData}
                        />

                        <CustomSelectWithStorage
                            options={IMPORTS_STATUSES.map((item) => item.title)}
                            values={IMPORTS_STATUSES.map((item) => item.id)}
                            defaultName='Статус импорта'
                            localStorageService={localStorageService}
                            updateData={updateData}
                            optionName='status'
                        />
                    </>
                }
                right={
                    <>
                        <ImportsButton
                            allow_requests_creation={allow_requests_creation}
                            updateData={updateData}
                        />
                        <DownloadExcelButton />
                    </>
                }
            />

            <TableWrapper
                isLoading={isLoading}
                head={
                    <tr>
                        <td>
                            <div>Дата</div>
                        </td>
                        <td>
                            <div>Файл с заявками</div>
                        </td>
                        <td>
                            <div>Отчет</div>
                        </td>
                        <td>
                            <div>Статус</div>
                        </td>
                    </tr>
                }
                body={list
                    .slice(itemsOnPage * (page - 1), itemsOnPage * (page - 1) + itemsOnPage)
                    .map((elem, i) => (
                        <tr key={i}>
                            <td>
                                <div>{elem.date}</div>
                            </td>
                            <td>
                                <div>
                                    <div>
                                        <div
                                            style={{ display: 'inline-block' }}
                                            className={styles.link}
                                            onClick={downloadFile({
                                                url: elem.file.url,
                                                filename: elem.file.name,
                                            })}
                                        >
                                            {elem.file.name}
                                        </div>{' '}
                                        <span>({elem.file.size})</span>
                                    </div>
                                </div>
                            </td>
                            <td>
                                <div>
                                    {elem.report ? (
                                        <div>
                                            <div
                                                style={{ display: 'inline-block' }}
                                                className={styles.link}
                                                onClick={downloadFile({
                                                    url: elem.report.url,
                                                    filename: elem.report.name,
                                                })}
                                            >
                                                {elem.report.name}
                                            </div>{' '}
                                            <span>({elem.report.size})</span>
                                        </div>
                                    ) : (
                                        '-'
                                    )}
                                </div>
                            </td>
                            <td>
                                <div className={getStatusClass(elem.status)}>
                                    {elem.status.text}
                                </div>
                            </td>
                        </tr>
                    ))}
            />

            <Pagination pages={pages} onPageChange={(p) => setPage(p)} />
        </Wrapper>
    );
}

const mapStateToProps = (state) => ({
    list: state.imports.list,
    isLoading: state.imports.isLoading,
    userInfo: userInfoSelector(state),
});

const mapDispatchToProps = (dispatch) => bindActionCreators({ fetchImports }, dispatch);

export default connect(mapStateToProps, mapDispatchToProps)(memo(ImportHistoryPage));
