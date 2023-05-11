import React, { memo, useEffect, useState } from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import moment from 'moment';
import _ from 'underscore';
import { Redirect } from 'react-router-dom';
import { fetchReports, confirmReport } from '../../../actions';
import styles from './ReportsPage.module.scss';
import Pagination from '../../Pagination/Pagination';
import PhotoTooltip from '../../PhotoTooltip/PhotoTooltip';
import downloadFile from '../../../utils/download';
import { ITEMS_ON_PAGE, REPORTS_PREFIX } from '../../../utils/constants';
import DatePickerApply from '../../DatePickerApply/DatePickerApply';
import { storageService } from '../../../utils';
import ButtonsContainer from '../../ButtonsContainer/ButtonsContainer';
import CustomSelectWithStorage from '../../CustomSelectWithStorage/CustomSelectWithStorage';
import TableWrapper from '../../TableWrapper/TableWrapper';
import SearchWrapper from '../../SearchWrapper/SearchWrapper';
import Wrapper from '../../Wrapper/Wrapper';
import styled from 'styled-components';
import Popup from 'reactjs-popup';
import PopupInfo from '../../PopupInfo/PopupInfo';

const ShortPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

function currencyFormat(num) {
    return num.toFixed(2).replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1 ');
}

function isMatch(elem, search) {
    return Object.keys(elem)
        .map((k) => elem[k])
        .some((val) => val.toString().includes(search));
}

const localStorageService = storageService(REPORTS_PREFIX);

function ReportsPage({ list, isLoading, fetchReports, userInfo, confirmReport }) {
    const [itemsOnPage, setItemsOnPage] = useState(
        localStorageService.get('itemsOnPage', ITEMS_ON_PAGE)
    );
    const [page, setPage] = useState(1);
    const pages = Math.ceil(list.length / itemsOnPage);

    const [infoPopup, setInfoPopup] = useState({ title: '', open: false, content: '' });
    const [tooltipContentHover, setTooltipContentHover] = useState(false);
    const [tooltipTriggerHover, setTooltipTriggerHover] = useState(false);
    const [tooltipElement, setTooltipElement] = useState(null);
    const [tooltipImgUrls, setTooltipImgUrls] = useState('');

    function calculateTop() {
        let scrollHeight = Math.max(
            document.body.scrollHeight,
            document.documentElement.scrollHeight,
            document.body.offsetHeight,
            document.documentElement.offsetHeight,
            document.body.clientHeight,
            document.documentElement.clientHeight
        );
        return Math.min(
            tooltipElement && tooltipElement.getBoundingClientRect().top + window.pageYOffset,
            scrollHeight - 520
        );
    }

    function confirm(pk) {
        confirmReport({ pk })
            .then((res) => {
                updateData();
            })
            .catch((err) =>
                setInfoPopup({
                    open: true,
                    title: 'Ошибка',
                    content:
                        err.error.response.data.message ||
                        `${err.error.response.status} ${err.error.response.statusText}`,
                })
            );
    }

    function toggleTooltip({ open, elem, e }) {
        if (elem.scans.length) {
            e.persist();
            open
                ? setTooltipTriggerHover(true)
                : setTimeout(() => setTooltipTriggerHover(false), 500);
            setTooltipElement(e.target);
            setTooltipImgUrls(elem.scans);
        }
    }

    const updateData = _.throttle(updateReports, 500);
    function updateReports() {
        return fetchReports({
            search_text: localStorageService.get('search'),
            status: localStorageService.get('status'),
            first_day: moment(localStorageService.get('startRanges')).format('DD.MM.YYYY'),
            last_day: moment(localStorageService.get('endRanges')).format('DD.MM.YYYY'),
        });
    }

    useEffect(() => {
        updateData();
    }, []);

    useEffect(() => {
        localStorageService.set('itemsOnPage', itemsOnPage);
    }, [itemsOnPage]);

    return (
        <Wrapper title='Взаиморасчеты'>
            <SearchWrapper
                placeHolder='Найти сверку'
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
                            options={['Новая', 'Согласована', 'В оплате', 'Оплачена']}
                            defaultName='Статус сверки'
                            localStorageService={localStorageService}
                            updateData={updateData}
                            optionName='status'
                        />
                    </>
                }
            />

            <TableWrapper
                isLoading={isLoading}
                className={styles.reportTable}
                head={
                    <tr>
                        <td>
                            <div>Дата счета</div>
                        </td>
                        <td>
                            <div>Номер счета</div>
                        </td>
                        <td>
                            <div>Филиал</div>
                        </td>
                        <td>
                            <div>Период</div>
                        </td>
                        <td>
                            <div>Сумма</div>
                        </td>
                        <td>
                            <div>Статус</div>
                        </td>
                        <td>
                            <div>Дедлайн</div>
                        </td>
                        <td>
                            <div>Сканы</div>
                        </td>
                        <td>
                            <div>Номер сверки</div>
                        </td>
                        <td>
                            <div></div>
                        </td>
                    </tr>
                }
                body={list
                    .filter((elem) => isMatch(elem, localStorageService.get('search')))
                    .slice(itemsOnPage * (page - 1), itemsOnPage * page)
                    .map((elem, i) => (
                        <tr key={i}>
                            <td>
                                <div>{elem.account_date}</div>
                            </td>
                            <td>
                                <div>{elem.account_number}</div>
                            </td>
                            <td>
                                <div>{elem.location}</div>
                            </td>
                            <td>
                                <div>{elem.period}</div>
                            </td>
                            <td>
                                <div>{currencyFormat(elem.sum)}</div>
                            </td>
                            <td>
                                <div style={{ fontWeight: 'bold' }}>{elem.status}</div>
                            </td>
                            <td>
                                <div>{elem.deadline}</div>
                            </td>
                            <td className={styles.photoPopup}>
                                <img
                                    onMouseEnter={(e) => toggleTooltip({ open: true, elem, e })}
                                    onMouseLeave={(e) => toggleTooltip({ open: false, elem, e })}
                                    className={
                                        styles.tablePhotoIcon +
                                        ' ' +
                                        (elem.scans.length ? '' : styles.disabled)
                                    }
                                    alt='icon'
                                    src='/photo_icon.svg'
                                />
                            </td>
                            <td>
                                <div>{elem.number}</div>
                            </td>
                            <td className={styles.buttonsTd}>
                                <div className={styles.buttonsContainer2}>
                                    {elem.status == 'Новая' && (
                                        <div
                                            onClick={() => confirm(elem.pk)}
                                            className={styles.button1}
                                        >
                                            <img alt='icon' src='/check_icon.svg' />
                                            <div>Согласовать</div>
                                        </div>
                                    )}
                                    <div
                                        onClick={downloadFile({
                                            url: '/gt/customer/v2/reports/details/',
                                            params: { pk: elem.pk },
                                            filename: 'report.xlsx',
                                        })}
                                        className={styles.button2}
                                    >
                                        <img alt='icon' src='/save_icon2.svg' />
                                    </div>
                                </div>
                            </td>
                        </tr>
                    ))}
            />
            <div
                onMouseEnter={() => setTooltipContentHover(true)}
                onMouseLeave={() => setTooltipContentHover(false)}
                className={styles.tooltipWrapper}
                style={{
                    display: tooltipContentHover || tooltipTriggerHover ? 'block' : 'none',
                    top: calculateTop(),
                    left: 30 + (tooltipElement && tooltipElement.getBoundingClientRect().left),
                }}
            >
                <PhotoTooltip urls={tooltipImgUrls} title='Cкан закрывающих документов' />
            </div>
            <Pagination pages={pages} onPageChange={(p) => setPage(p)} />
            <ShortPopup
                modal
                closeOnDocumentClick
                open={infoPopup.open}
                onClose={() => setInfoPopup({ ...infoPopup, open: false })}
            >
                {(close) => (
                    <PopupInfo title={infoPopup.title} close={close}>
                        <div dangerouslySetInnerHTML={{ __html: infoPopup.content }}></div>
                    </PopupInfo>
                )}
            </ShortPopup>
        </Wrapper>
    );
}

const mapStateToProps = (state) => ({
    list: state.reports.list,
    isLoading: state.reports.isLoading,
    userInfo: state.user.info,
});

const mapDispatchToProps = (dispatch) =>
    bindActionCreators({ fetchReports, confirmReport }, dispatch);

export default connect(mapStateToProps, mapDispatchToProps)(memo(ReportsPage));
