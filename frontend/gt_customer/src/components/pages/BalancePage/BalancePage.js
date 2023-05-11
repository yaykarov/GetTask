import React, { memo, useEffect, useState } from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import { Redirect } from 'react-router-dom';
import { fetchInvoices } from '../../../actions';
import styles from './BalancePage.module.scss';
import _ from 'underscore';
import moment from 'moment';
import DatePickerApply from '../../DatePickerApply/DatePickerApply';
import { BALANCE_PREFIX, ITEMS_ON_PAGE } from '../../../utils/constants';
import Pagination from '../../Pagination/Pagination';
import downloadFile from '../../../utils/download';
import { getToken, storageService } from '../../../utils';
import { userInfoSelector } from '../../../utils/reselect';
import ButtonsContainer from '../../ButtonsContainer/ButtonsContainer';
import TableWrapper from '../../TableWrapper/TableWrapper';
import Wrapper from '../../Wrapper/Wrapper';
import SearchWrapper from '../../SearchWrapper/SearchWrapper';
import { CreateInvoiceButton } from '../../buttons';

const localStorageService = storageService(BALANCE_PREFIX);

function BalancePage({ list, isLoading, fetchInvoices }) {
    const [itemsOnPage, setItemsOnPage] = useState(
        localStorageService.get('itemsOnPage', ITEMS_ON_PAGE)
    );
    const [page, setPage] = useState(1);
    const pages = Math.ceil(list.length / itemsOnPage);

    const updateData = _.throttle(updateIvoices, 500);
    function updateIvoices() {
        return fetchInvoices({
            token: getToken(),
            search: localStorageService.get('search'),
            firstDay: moment(localStorageService.get('startRanges')).format('DD.MM.YYYY'),
            lastDay: moment(localStorageService.get('endRanges')).format('DD.MM.YYYY'),
        });
    }

    useEffect(() => {
        updateData();
    }, []);

    useEffect(() => {
        localStorageService.set('itemsOnPage', itemsOnPage);
    }, [itemsOnPage]);



    return (
        <Wrapper title='Баланс'>
            <SearchWrapper
                placeHolder='Найти счет'
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
                    </>
                }
                right={<CreateInvoiceButton updateData={updateData} />}
            />

            <TableWrapper
                isLoading={isLoading}
                head={
                    <tr>
                        <td>
                            <div>Дата</div>
                        </td>
                        <td>
                            <div>Номер</div>
                        </td>
                        <td>
                            <div>Сумма</div>
                        </td>
                        <td>
                            <div>Скачать</div>
                        </td>
                    </tr>
                }
                body={list
                    .slice(itemsOnPage * (page - 1), itemsOnPage * (page - 1) + itemsOnPage)
                    .map((elem, i) => (
                        <tr key={i}>
                            <td>
                                <div>{moment(elem.timestamp).format('DD.MM.YYYY')}</div>
                            </td>
                            <td>
                                <div>{elem.number}</div>
                            </td>
                            <td>
                                <div>{elem.amount}&nbsp;&#8381;</div>
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
                        </tr>
                    ))}
            />

            <Pagination pages={pages} onPageChange={(p) => setPage(p)} />
        </Wrapper>
    );
}

const mapStateToProps = (state) => ({
    list: state.invoices.list,
    isLoading: state.invoices.isLoading,
});

const mapDispatchToProps = (dispatch) => bindActionCreators({ fetchInvoices }, dispatch);

export default connect(mapStateToProps, mapDispatchToProps)(memo(BalancePage));
